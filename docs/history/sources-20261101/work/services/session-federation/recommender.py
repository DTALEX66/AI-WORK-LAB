"""Session recommendation engine (WL-P0-070).

Answers "which past session should I continue / reference for this task?"
against the WL-P0-050 index.  Recommendations are evidence-based, not
guesses: each candidate carries a ``score_breakdown`` (semantic match,
retention quality, recency, agent fit) so a human can audit why it was
recommended before resuming it.

Score components (all in [0,1], weighted sum):
    semantic_match  — FTS5 relevance against the target query (0 if no FTS hit)
    retention       — worst retention channel of the source session (1.0 = full)
    recency         — exponential decay on started_at (half-life configurable)
    agent_fit       — 1.0 same agent as target, 0.5 different-but-compatible, 0 otherwise
    loss_penalty    — (1 - loss_rate) where loss_rate is fraction of channels dropped
"""
from __future__ import annotations

import json
import math
import sys as _sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping

# Load sibling canonical module (spec-loading safe)
_here = _Path(__file__).resolve().parent if False else None  # placeholder
from pathlib import Path as _Path

_canonical = _sys.modules.get("services_session_federation_canonical")
if _canonical is None:
    import importlib.util as _ilu
    _spec = _ilu.spec_from_file_location(
        "services_session_federation_canonical", _Path(__file__).resolve().parent / "canonical.py"
    )
    _canonical = _ilu.module_from_spec(_spec)
    _sys.modules["services_session_federation_canonical"] = _canonical
    _spec.loader.exec_module(_canonical)


@dataclass
class Candidate:
    universal_session_id: str
    source_agent: str
    source_session_id: str
    score: float
    score_breakdown: dict[str, float]
    summary: str
    changed_files: tuple[str, ...]
    started_at: str | None
    portability_level: str
    loss_report: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "universal_session_id": self.universal_session_id,
            "source_agent": self.source_agent,
            "source_session_id": self.source_session_id,
            "score": self.score,
            "score_breakdown": dict(self.score_breakdown),
            "summary": self.summary,
            "changed_files": list(self.changed_files),
            "started_at": self.started_at,
            "portability_level": self.portability_level,
            "loss_report": dict(self.loss_report),
        }


class SessionRecommender:
    """Recommend prior sessions for a new task query.

    Parameters
    ----------
    index : object
        A ``SessionIndex`` instance (WL-P0-050).
    target_agent : str
        The agent the *new* task will run on; boosts same-agent candidates.
    half_life_hours : float
        Recency half-life; default 24 h.
    min_score : float
        Candidates below this score are dropped; default 0.2.
    """

    def __init__(
        self,
        index: Any,
        target_agent: str,
        *,
        half_life_hours: float = 24.0,
        min_score: float = 0.2,
    ) -> None:
        self._index = index
        self._target_agent = target_agent
        self._half_life_hours = half_life_hours
        self._min_score = min_score
        self._weights = {
            "semantic_match": 0.35,
            "retention": 0.25,
            "recency": 0.25,
            "agent_fit": 0.15,
        }

    def recommend(self, query: str, *, limit: int = 5) -> list[Candidate]:
        """Return top-``limit`` candidates for ``query``, sorted by score desc."""
        fts_rows = self._index.search(query, limit=50)
        if not fts_rows:
            return []

        now = datetime.now(timezone.utc)
        scored: list[Candidate] = []
        for row in fts_rows:
            semantic = self._fts_rank(row)
            retention = self._retention_score(row)
            recency = self._recency(row.get("started_at"), now)
            agent_fit = self._agent_fit(row.get("source_agent"), self._target_agent)
            loss_rate = self._loss_rate(row)

            raw = (
                self._weights["semantic_match"] * semantic
                + self._weights["retention"] * retention
                + self._weights["recency"] * recency
                + self._weights["agent_fit"] * agent_fit
            )
            # Penalise dropped channels linearly
            score = max(0.0, raw * (1.0 - loss_rate * 0.5))

            if score < self._min_score:
                continue

            level = row.get("portability_level")
            level_name = level.name if hasattr(level, "name") else str(level)
            meta = json.loads(row.get("metadata") or "{}") if isinstance(row.get("metadata"), str) else (row.get("metadata") or {})
            loss_report = meta.get("loss_report", {})
            summary = meta.get("summary", "")
            changed = tuple(meta.get("changed_files", []))

            scored.append(Candidate(
                universal_session_id=row["universal_session_id"],
                source_agent=row.get("source_agent", ""),
                source_session_id=row.get("source_session_id", ""),
                score=round(score, 4),
                score_breakdown={
                    "semantic_match": round(semantic, 4),
                    "retention": round(retention, 4),
                    "recency": round(recency, 4),
                    "agent_fit": round(agent_fit, 4),
                    "loss_penalty": round(1.0 - loss_rate * 0.5, 4),
                },
                summary=summary,
                changed_files=changed,
                started_at=row.get("started_at"),
                portability_level=level_name,
                loss_report=loss_report,
            ))

        scored.sort(key=lambda c: c.score, reverse=True)
        return scored[:limit]

    # -- scoring helpers ---------------------------------------------------

    @staticmethod
    def _fts_rank(row: Mapping[str, Any]) -> float:
        """Normalise bm25 FTS5 rank into [0,1].

        ``bm25()`` returns a positive float where *lower* = more relevant.
        ``index.search`` exposes this as the ``fts_rank`` column.  We scale
        the top hit (minimum value) to 1.0 and everything else proportionally
        within a single result set; here we use a simple 1/(1+rank) curve.
        """
        rank = row.get("fts_rank")
        if rank is None:
            return 0.5  # no FTS rank available → neutral
        rank = float(rank)
        if rank <= 0:
            return 1.0
        # 1/(1+rank): rank 0.5 → 0.667, rank 1.0 → 0.5, rank 3.0 → 0.25
        relevance = 1.0 / (1.0 + rank)
        return max(0.0, min(1.0, relevance))

    @staticmethod
    def _retention_score(row: Mapping[str, Any]) -> float:
        meta = json.loads(row.get("metadata") or "{}") if isinstance(row.get("metadata"), str) else (row.get("metadata") or {})
        loss_report = meta.get("loss_report", {})
        channels = [loss_report.get("messages", 1.0),
                    loss_report.get("tool_calls", 1.0),
                    loss_report.get("tool_results", 1.0)]
        worst = min(channels)
        return max(0.0, min(1.0, worst))

    def _recency(self, started_at: str | None, now: datetime) -> float:
        if not started_at:
            return 0.5
        try:
            t = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
            age_hours = max(0.0, (now - t).total_seconds() / 3600.0)
            return math.exp(-age_hours / (self._half_life_hours * math.log(2)))
        except (ValueError, AttributeError):
            return 0.5

    @staticmethod
    def _agent_fit(candidate_agent: str | None, target_agent: str) -> float:
        if candidate_agent is None:
            return 0.3
        if candidate_agent.lower() == target_agent.lower():
            return 1.0
        compatible = {"codex", "hermes", "dsh"}
        if candidate_agent.lower() in compatible and target_agent.lower() in compatible:
            return 0.6
        return 0.2

    @staticmethod
    def _loss_rate(row: Mapping[str, Any]) -> float:
        meta = json.loads(row.get("metadata") or "{}") if isinstance(row.get("metadata"), str) else (row.get("metadata") or {})
        lr = meta.get("loss_report", {})
        channels = [lr.get("messages", 1.0), lr.get("tool_calls", 1.0), lr.get("tool_results", 1.0)]
        dropped = sum(1.0 - c for c in channels) / len(channels)
        return dropped


def build_recommendation_report(
    query: str,
    candidates: list[Candidate],
    *,
    target_agent: str,
    project_id: str,
) -> dict[str, Any]:
    """Serialisable recommendation report for audit / dashboard use."""
    return {
        "schema": "work-lab/session-recommendations/v1",
        "query": query,
        "target_agent": target_agent,
        "project_id": project_id,
        "candidates": [c.to_dict() for c in candidates],
        "recommended": candidates[0].universal_session_id if candidates else None,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


__all__ = ["Candidate", "SessionRecommender", "build_recommendation_report"]
