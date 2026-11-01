#!/usr/bin/env python3
"""NX-710 regression report verifier."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "ci"))

from regression_report import run_report  # noqa: E402


def verify() -> dict[str, object]:
    report = run_report()
    assert report["schemaVersion"] == "work-lab/regression-report/v1"
    assert report["mode"] == "LOCAL_OFFLINE_READ_ONLY"
    assert report["tree"]["trackedFiles"] > 0
    assert report["tree"]["trackedBytes"] > 0
    assert report["tree"]["nodeModulesTracked"] is False

    for name, metric in report["performance"].items():
        assert metric["samples"] == 25, name
        assert metric["p50Ms"] >= 0, name
        assert metric["p95Ms"] < 5000, f"{name} p95 regression: {metric['p95Ms']}ms"

    quality = report["quality"]
    assert quality["tokenDedupCount"] == quality["tokenDedupExpected"]
    assert quality["unknownModelCostStatus"] == "unknown"
    assert quality["designReadbackLossless"] is True
    assert quality["contaminationControls"] == 7
    assert quality["observerMutationSurface"] == []

    boundaries = report["boundaries"]
    assert boundaries["network"] is False
    assert boundaries["credentials"] is False
    assert boundaries["externalWrites"] is False
    return report


def main() -> int:
    try:
        report = verify()
    except (AssertionError, ValueError, KeyError, OSError) as exc:
        print(f"REGRESSION_REPORT_FAIL {exc}")
        return 1
    performance = report["performance"]
    print(
        "REGRESSION_REPORT_PASS "
        f"tracked_files={report['tree']['trackedFiles']} tracked_bytes={report['tree']['trackedBytes']} "
        f"rollup_p95_ms={performance['usageRollup']['p95Ms']} "
        f"contract_p95_ms={performance['designContract']['p95Ms']} "
        f"pilot_p95_ms={performance['offlinePilot']['p95Ms']} "
        "dedup=ok unknown=preserved contamination=7 mutation_surface=empty calibration=pending"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
