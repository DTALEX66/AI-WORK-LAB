#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Aggregate host-produced repeatability records; never invent a host run."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


DESIGN_LAB = Path(__file__).resolve().parents[1]
PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(DESIGN_LAB))
sys.path.insert(0, str(PROJECT_ROOT / "packages" / "capabilities"))

from reconstruction.qualification import aggregate, run_from_record  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("record", type=Path, help="host-produced qualification-runs/v1 JSON")
    args = parser.parse_args()
    try:
        payload = json.loads(args.record.read_text(encoding="utf-8"))
        if payload.get("schemaVersion") != "design-lab/reconstruction-qualification-runs/v1":
            raise ValueError("unsupported qualification record schema")
        case_id = payload.get("caseId")
        if not isinstance(case_id, str) or not case_id:
            raise ValueError("caseId must be a non-empty string")
        raw_runs = payload.get("runs")
        if not isinstance(raw_runs, list):
            raise ValueError("runs must be a list")
        report = aggregate(tuple(run_from_record(raw) for raw in raw_runs))
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"RECONSTRUCTION_QUALIFICATION=BLOCKED reason={exc}")
        return 1
    print(f"RECONSTRUCTION_QUALIFICATION={report.status} case={case_id}" + (f" reason={report.reason}" if report.reason else ""))
    return 0 if report.status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
