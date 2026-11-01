#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Compare two visual-quality iterations and surface regressions."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def load_json(path: str | Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _score_for(report: dict[str, Any], axis: str) -> float:
    item = report.get("axes", {}).get(axis, {})
    if isinstance(item, dict):
        return float(item.get("score", 0))
    if isinstance(item, (int, float)):
        return float(item)
    return 0.0


def _overall(report: dict[str, Any]) -> float:
    if "overall" in report:
        return float(report.get("overall", 0))
    if "score" in report:
        return float(report.get("score", 0))
    axes = report.get("axes", {})
    values = [_score_for(report, axis) for axis in axes]
    return sum(values) / len(values) if values else 0.0


def compare_reports(before: dict[str, Any], after: dict[str, Any], tolerance: float = 0.0) -> dict[str, Any]:
    axes = sorted(set(before.get("axes", {})) | set(after.get("axes", {})))
    deltas = {axis: round(_score_for(after, axis) - _score_for(before, axis), 2) for axis in axes}
    regressions = [axis for axis, delta in deltas.items() if delta < -abs(tolerance)]
    return {
        "overall_delta": round(_overall(after) - _overall(before), 2),
        "axis_deltas": deltas,
        "regressions": regressions,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare visual quality iterations")
    parser.add_argument("before")
    parser.add_argument("after")
    parser.add_argument("--tolerance", type=float, default=0.0)
    args = parser.parse_args()
    result = compare_reports(load_json(args.before), load_json(args.after), tolerance=args.tolerance)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not result["regressions"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
