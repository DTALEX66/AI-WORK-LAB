"""Radar scoring (WL-380 / ch 33): the 12-axis weighted ruler.

ch 33 fixes the weights (they sum to 100)::

    20 capability_fit   10 growth      10 usage        10 quality
    10 license          10 api/cli/mcp  8 local_offline  7 maintenance
     5 benchmark        4 windows       3 cost          3 community

and maps a total to a disposition::

    85+  P0 AUDIT      70-84  P1 POC     55-69  REFERENCE     <55  ARCHIVE

The scorer reads only the candidate's metadata (the ch 35 external-asset
fields), so it never pulls the artifact in.  Axes that have no evidence
(benchmark, in particular) score 0 rather than a guessed number — an
unevidenced axis must not inflate the total.  Weights are injectable so
the framework stays testable; the ch 33 set is the default.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

# ch 33 default weights.
DEFAULT_WEIGHTS: Dict[str, int] = {
    "capability_fit": 20,
    "growth": 10,
    "usage": 10,
    "quality": 10,
    "license": 10,
    "api_cli_mcp": 10,
    "local_offline": 8,
    "maintenance": 7,
    "benchmark": 5,
    "windows": 4,
    "cost": 3,
    "community": 3,
}

# acceptable open licenses (ch 33 license axis).
_ACCEPTABLE_LICENSES = {"apache-2.0", "mit", "mpl-2.0", "bsd-2-clause",
                       "bsd-3-clause", "isc", "unlicense"}

# cost axis: free is best, paid is worst (0..1 multiplier).
_COST_POINTS = {"free": 1.0, "tiered": 0.5, "paid": 0.0, "unknown": 0.0}


class Tier:
    P0_AUDIT = "P0_AUDIT"
    P1_POC = "P1_POC"
    REFERENCE = "REFERENCE"
    ARCHIVE = "ARCHIVE"

    @classmethod
    def for_score(cls, total: float) -> str:
        if total >= 85:
            return cls.P0_AUDIT
        if total >= 70:
            return cls.P1_POC
        if total >= 55:
            return cls.REFERENCE
        return cls.ARCHIVE


@dataclass
class AxisScore:
    axis: str
    raw: float            # points actually earned for this axis
    weight: int
    detail: str = ""

    @property
    def fraction(self) -> float:
        return self.raw / self.weight if self.weight else 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {"axis": self.axis, "raw": self.raw, "weight": self.weight,
                "detail": self.detail}


@dataclass
class ScoreReceipt:
    candidate_key: str
    total: float
    tier: str
    axes: List[AxisScore] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {"candidate_key": self.candidate_key, "total": self.total,
                "tier": self.tier, "axes": [a.to_dict() for a in self.axes]}

    def receipt_sha256(self) -> str:
        import hashlib
        payload = json.dumps(self.to_dict(), sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class RadarScorer:
    """Deterministic 12-axis scoring with ch 33's default weights."""

    SCHEMA = "work-lab/radar-scoring/v1"

    def __init__(self, weights: Optional[Dict[str, int]] = None) -> None:
        self.weights = dict(DEFAULT_WEIGHTS)
        if weights:
            self.weights.update(weights)

    # -- per-axis scorers (read candidate metadata only) -----------------
    def _axis(self, cand: Any, name: str, fraction: float, detail: str) -> AxisScore:
        w = self.weights.get(name, 0)
        return AxisScore(name, round(fraction * w, 3), w, detail)

    def score(self, cand: Any) -> ScoreReceipt:
        axes: List[AxisScore] = []
        key = getattr(cand, "canonical_url", "") or \
            f"{getattr(cand, 'owner', '')}/{getattr(cand, 'repo', '')}"

        # 20 capability_fit — only awarded when project_fit was actually
        # filled in (the LLM-authored fit note); no note, no points.
        fit_note = str(getattr(cand, "project_fit", "") or "").strip()
        axes.append(self._axis(cand, "capability_fit",
                               1.0 if fit_note else 0.0,
                               fit_note[:60] or "no fit note"))

        # 10 growth — candidate.growth is a normalised 0..1 signal.
        g = getattr(cand, "growth", 0.0) or 0.0
        g = max(0.0, min(1.0, g))
        axes.append(self._axis(cand, "growth", g, f"growth={g:.2f}"))

        # 10 usage — downloads, normalised against a generous 100k cap.
        dl = getattr(cand, "downloads", 0) or 0
        u = min(1.0, dl / 100000.0)
        axes.append(self._axis(cand, "usage", u, f"downloads={dl}"))

        # 10 quality — proxy: a pinned commit (reproducible) + stars.
        pinned = bool(getattr(cand, "commit", ""))
        stars = getattr(cand, "stars", 0) or 0
        star_frac = min(1.0, stars / 5000.0)
        q = (0.5 + 0.5 * star_frac) if pinned else 0.5 * star_frac
        axes.append(self._axis(cand, "quality", max(0.0, min(1.0, q)),
                               f"commit_pinned={pinned} stars={stars}"))

        # 10 license — acceptable open license or zero.
        lic = str(getattr(cand, "license", "unknown")).lower()
        axes.append(self._axis(cand, "license",
                               1.0 if lic in _ACCEPTABLE_LICENSES else 0.0,
                               lic or "unknown"))

        # 10 api/cli/mcp — how many of the three interfaces it exposes.
        surfaces = sum(bool(getattr(cand, s, False)) for s in ("api", "cli", "mcp"))
        axes.append(self._axis(cand, "api_cli_mcp", surfaces / 3.0,
                               f"{surfaces}/3 interfaces"))

        # 8 local/offline — must be runnable locally/offline.
        axes.append(self._axis(cand, "local_offline",
                               1.0 if getattr(cand, "local", False) else 0.0,
                               "local" if getattr(cand, "local", False) else "not local"))

        # 7 maintenance — proxy: pinned commit means a maintained,
        # reproducible snapshot is available.
        axes.append(self._axis(cand, "maintenance",
                               1.0 if pinned else 0.0,
                               "pinned" if pinned else "unpinned"))

        # 5 benchmark — NO benchmark is available for a metadata-only
        # candidate, so this axis is 0, never a guessed number.
        axes.append(self._axis(cand, "benchmark", 0.0,
                               "no live benchmark (metadata-only candidate)"))

        # 4 windows — first-class Windows support.
        axes.append(self._axis(cand, "windows",
                               1.0 if getattr(cand, "windows", False) else 0.0,
                               "windows" if getattr(cand, "windows", False) else "not windows"))

        # 3 cost — free > tiered > paid.
        cost = str(getattr(cand, "cost", "unknown")).lower()
        axes.append(self._axis(cand, "cost", _COST_POINTS.get(cost, 0.0), cost))

        # 3 community — stars proxy, generous 10k cap.
        comm = min(1.0, stars / 10000.0)
        axes.append(self._axis(cand, "community", comm, f"stars={stars}"))

        total = sum(a.raw for a in axes)
        return ScoreReceipt(key, round(total, 2), Tier.for_score(total), axes)

    def score_many(self, candidates: List[Any]) -> List[ScoreReceipt]:
        receipts = [self.score(c) for c in candidates]
        receipts.sort(key=lambda r: (-r.total, r.candidate_key))
        return receipts
