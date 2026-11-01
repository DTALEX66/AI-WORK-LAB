#!/usr/bin/env python3
"""NX-700 three-branch offline pilot verifier."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "ci"))

from offline_pilot import run_pilots  # noqa: E402


def verify() -> dict[str, object]:
    report = run_pilots()
    assert report["schemaVersion"] == "work-lab/offline-pilot/v1"
    assert report["mode"] == "OFFLINE_FIXTURES_ONLY"
    assert report["allOfflineVerified"] is True
    assert report["externalWrites"] is False
    assert report["credentialsAccessed"] is False
    assert report["liveClaims"] == "NONE"
    pilots = {pilot["branch"]: pilot for pilot in report["pilots"]}
    assert set(pilots) == {"workflow-agent", "observer"}

    workflow = pilots["workflow-agent"]
    assert workflow["credentialsRead"] is False
    assert workflow["promptResponseRead"] is False
    assert workflow["taskReplay"]["outcome"] == "PASS"
    assert workflow["qwenFixture"]["status"] == "UNAVAILABLE"

    observer = pilots["observer"]
    assert observer["restartRebuildEqual"] is True
    assert observer["duplicateIngestIdempotent"] is True
    assert observer["corruptEventsIsolated"] == 1
    assert observer["mutationSurface"] == []

    return {"pilots": 2, "offline": True}


def main() -> int:
    try:
        result = verify()
    except (AssertionError, ValueError, TypeError, KeyError) as exc:
        print(f"OFFLINE_PILOT_FAIL {exc}")
        return 1
    print(
        f"OFFLINE_PILOT_PASS pilots={result['pilots']} offline_verified={result['offline']} "
        "external_writes=false credentials=false live_claims=none human_calibration=pending"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
