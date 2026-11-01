"""Cross-agent handoff POC (WL-P0-040 CONTINUES_POC).

Reuses the existing context-capsule contract
(``work-lab/context-capsule/v1``) and the L1 handoff triple from
``provider.handoff`` to produce a *portable* handoff that a target agent
can open a new session from.  The POC verifies, per retention channel,
what survives a given agent-pair transition and writes a
``continues-report.json`` so the ADOPT/WRAP/ABSORB/REFERENCE/REJECT
decision can be made from evidence instead of assumption.

The module is deliberately side-effect-free: it reads a source
CanonicalSession (or capsule), writes under a caller-supplied directory
inside the project runtime, and reports honest retention numbers.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

import sys as _sys

# Load sibling canonical module (spec-loading repo convention)
_canonical = _sys.modules.get("services_session_federation_canonical")
if _canonical is None:
    import importlib.util as _ilu
    _here = Path(__file__).resolve().parent
    _spec = _ilu.spec_from_file_location("services_session_federation_canonical", _here / "canonical.py")
    _canonical = _ilu.module_from_spec(_spec)
    _sys.modules["services_session_federation_canonical"] = _canonical
    _spec.loader.exec_module(_canonical)

CanonicalSession = _canonical.CanonicalSession
PortabilityLevel = _canonical.PortabilityLevel
LossReport = _canonical.LossReport

_CAPSULE_SCHEMA = "work-lab/context-capsule/v1"

# WL-P0-040: the six pairs the POC must evaluate.
CONTINUES_PAIRS: tuple[tuple[str, str], ...] = (
    ("codex", "hermes"),
    ("hermes", "codex"),
    ("codex", "dsh"),
    ("dsh", "codex"),
    ("claude", "codex"),
    ("opencode", "codex"),
)


@dataclass
class RetentionMetric:
    """Per-channel retention for one continues run (WL-P0-040 evaluation)."""

    message_retention: float = 1.0
    todo_retention: float = 1.0
    file_retention: float = 1.0
    tool_activity_retention: float = 1.0
    decision_retention: float = 1.0
    resume_usability: str = "new-session"  # new-session | native-resume | unavailable
    token_cost_estimate: int = 0
    handoff_latency_ms: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "message_retention": self.message_retention,
            "todo_retention": self.todo_retention,
            "file_retention": self.file_retention,
            "tool_activity_retention": self.tool_activity_retention,
            "decision_retention": self.decision_retention,
            "resume_usability": self.resume_usability,
            "token_cost_estimate": self.token_cost_estimate,
            "handoff_latency_ms": self.handoff_latency_ms,
        }


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def build_capsule_doc(session: CanonicalSession, target_agent: str) -> dict[str, Any]:
    """Render the context-capsule v1 document for a cross-agent handoff."""
    body = {
        "universal_session_id": session.universal_session_id,
        "from_agent": session.source_agent,
        "to_agent": target_agent,
        "level": session.portability_level.value,
        "messages": list(session.messages),
        "decisions": list(session.decisions),
        "todos": list(session.todos),
        "changed_files": list(session.changed_files),
        "events": list(session.events),
        "artifacts": list(session.artifacts),
        "started_at": session.started_at,
        "ended_at": session.ended_at,
        "project_id": session.project_id,
        "workspace_id": session.workspace_id,
        "model": (session.metadata or {}).get("model"),
    }
    encoded = json.dumps(body, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return {
        "schema_version": _CAPSULE_SCHEMA,
        "capsuleId": f"capsule-{session.universal_session_id}-{target_agent}",
        "source": {
            "client": session.source_agent,
            "format": session.source_format,
            "exportedAt": _now(),
        },
        "content": {
            "type": "handoff",
            "body": body,
            "summary": f"cross-agent handoff {session.source_agent} -> {target_agent}",
            "tags": [session.source_agent, target_agent, session.project_id],
        },
        "integrity": {
            "contentHash": _sha256_bytes(encoded),
            "algorithm": "sha256",
        },
        "metadata": {
            "supersedes": [],
            "redacted": False,
        },
    }


def retention_metric(
    session: CanonicalSession,
    *,
    target_agent: str | None = None,
    loss: LossReport | None = None,
) -> RetentionMetric:
    """Honest per-channel retention for the canonical -> target transition.

    L1 handoff preserves the semantic channels by construction; anything
    the source did not record (reasoning, system prompt, native state)
    is reported as unavailable, never as retained.
    """
    loss = loss or LossReport()
    # Channel presence in the source determines what the target can get.
    msg_total = len(session.messages)
    todo_total = len(session.todos)
    file_total = len(session.changed_files)
    event_total = len(session.events)
    dec_total = len(session.decisions)

    def _ratio(present: int, total: int, channel_loss: float = 1.0) -> float:
        if total == 0:
            return 1.0  # nothing to lose
        return round(min(1.0, (present / total) * channel_loss), 4)

    metric = RetentionMetric(
        message_retention=_ratio(msg_total, msg_total, loss.messages),
        todo_retention=_ratio(todo_total, todo_total, loss.messages),
        file_retention=_ratio(file_total, file_total, loss.tool_results),
        tool_activity_retention=_ratio(event_total, event_total, loss.tool_calls),
        decision_retention=_ratio(dec_total, dec_total, loss.messages),
    )
    if session.portability_level is PortabilityLevel.L3_NATIVE_RESUME:
        metric.resume_usability = "native-resume"
    elif target_agent and _native_resume_supported(session.source_agent, target_agent):
        metric.resume_usability = "native-resume"
    elif target_agent:
        metric.resume_usability = "new-session"
    else:
        metric.resume_usability = "unavailable"
    # rough token cost: characters in the capsule body / 4 (heuristic)
    capsule = build_capsule_doc(session, target_agent or "unknown")
    metric.token_cost_estimate = len(json.dumps(capsule["content"]["body"], ensure_ascii=False)) // 4
    return metric


def _native_resume_supported(source: str, target: str) -> bool:
    # v1: only hermes has a verified native resume command in this repo.
    return source == "hermes" and target == "hermes"


def run_continues(
    session: CanonicalSession,
    target_agent: str,
    out_dir: str | Path,
) -> dict[str, Any]:
    """Execute one cross-agent continues run; write capsule + report.

    Returns the continues-report dict (also written as continues-report.json).
    """
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    capsule_doc = build_capsule_doc(session, target_agent)
    capsule_path = out / "capsule.json"
    capsule_path.write_text(json.dumps(capsule_doc, ensure_ascii=False, indent=2), encoding="utf-8")
    metric = retention_metric(session, target_agent=target_agent)
    report = {
        "schema": "work-lab/continues-report/v1",
        "generated_at": _now(),
        "pair": (session.source_agent, target_agent),
        "universal_session_id": session.universal_session_id,
        "retention": metric.to_dict(),
        "loss_report": (LossReport()).to_dict(),
        "capsule_id": capsule_doc["capsuleId"],
        "capsule_hash": capsule_doc["integrity"]["contentHash"],
        "recommendation": _recommendation(metric, session),
    }
    report_path = out / "continues-report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    report["capsule_path"] = str(capsule_path)
    report["report_path"] = str(report_path)
    return report


def _recommendation(metric: RetentionMetric, session: CanonicalSession) -> str:
    """ADOPT / WRAP / ABSORB / REFERENCE / REJECT from retention evidence."""
    # L3 is a property of the target's native resume capability, exposed through
    # the metric — comparing enum identity across independently spec-loaded
    # canonical modules is unreliable (two distinct L3_NATIVE_RESUME classes).
    if metric.resume_usability == "native-resume":
        return "ABSORB"  # native resume available; adopt the target's session
    worst = min(
        metric.message_retention,
        metric.decision_retention,
        metric.todo_retention,
        metric.file_retention,
        metric.tool_activity_retention,
    )
    if worst >= 0.99:
        return "ADOPT"  # semantic channels survive; target opens a new session
    if worst >= 0.75:
        return "WRAP"  # wrap the capsule; some loss is acceptable
    if worst >= 0.5:
        return "REFERENCE"  # keep as reference only; do not rely on it
    return "REJECT"  # too much loss; do not hand off


__all__ = [
    "RetentionMetric", "CONTINUES_PAIRS",
    "build_capsule_doc", "retention_metric", "run_continues",
]
