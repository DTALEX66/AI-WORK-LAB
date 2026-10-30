"""Evidence-driven LIVE gate (WLGM-170).

LIVE requires ALL of:

1. snapshot schema valid;
2. SSE connected;
3. heartbeat within threshold;
4. cursor/revision valid and advancing;
5. canonical writer watermark fresh;
6. key collector coverage meets declared scope;
7. data is not fixture or bundled snapshot.

Any single unmet condition drops LIVE. ``last-good`` is only marked STALE with
its original time; exact-SHA CI is exact only when SHA matches AND the run is
verifiable. Missing/unsupported/denied are distinct states; unknown is never
turned into 0/LIVE/exact/complete.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class LiveVerdict:
    live: bool
    missing: list[str]
    state: str = "UNKNOWN"  # LIVE | DELAYED | OFFLINE | UNKNOWN

    def as_dict(self) -> dict[str, Any]:
        return {"live": self.live, "missing": self.missing, "state": self.state}


def evaluate_live(
    *,
    snapshot_valid: bool,
    sse_connected: bool,
    heartbeat_age_seconds: float | None,
    heartbeat_threshold_seconds: float,
    cursor_valid: bool,
    writer_watermark_age_seconds: float | None,
    writer_watermark_threshold_seconds: float,
    coverage: dict[str, Any] | None = None,
    is_fixture: bool = False,
) -> LiveVerdict:
    """Return LIVE only when every condition holds; never fabricate partial."""
    missing: list[str] = []
    if not snapshot_valid:
        missing.append("snapshot_schema")
    if not sse_connected:
        missing.append("sse_connected")
    if heartbeat_age_seconds is None or heartbeat_age_seconds > heartbeat_threshold_seconds:
        missing.append("heartbeat_fresh")
    if not cursor_valid:
        missing.append("cursor_valid")
    if writer_watermark_age_seconds is None or writer_watermark_age_seconds > writer_watermark_threshold_seconds:
        missing.append("writer_watermark_fresh")
    if is_fixture:
        missing.append("no_fixture")

    coverage_ok = True
    if coverage:
        numerator = coverage.get("numerator")
        denominator = coverage.get("denominator")
        if numerator is None or denominator is None or denominator == 0 or numerator < denominator:
            coverage_ok = False
            missing.append("collector_coverage")
    elif coverage is None:
        coverage_ok = False
        missing.append("collector_coverage")

    live = not missing
    if live:
        return LiveVerdict(live=True, missing=[], state="LIVE")
    # State classification: OFFLINE when connection or watermark is gone.
    if not sse_connected or writer_watermark_age_seconds is None:
        return LiveVerdict(live=False, missing=missing, state="OFFLINE")
    # Connected but something is stale -> DELAYED.
    if heartbeat_age_seconds is None or heartbeat_age_seconds > heartbeat_threshold_seconds:
        return LiveVerdict(live=False, missing=missing, state="DELAYED")
    if writer_watermark_age_seconds > writer_watermark_threshold_seconds:
        return LiveVerdict(live=False, missing=missing, state="DELAYED")
    return LiveVerdict(live=False, missing=missing, state="UNKNOWN")
