#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Score an evidence-based design critique record."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def load_json(path: str | Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def score_critique(critique: dict[str, Any], threshold: float = 8.0) -> dict[str, Any]:
    scores = critique.get("scores", [])
    if not isinstance(scores, list):
        scores = []
    total = 0.0
    weight = 0.0
    invalid_scores: list[str] = []
    missing_evidence: list[str] = []
    for item in scores:
        if not isinstance(item, dict):
            invalid_scores.append(str(item))
            continue
        axis = str(item.get("axis", "unknown"))
        try:
            value = float(item.get("score"))
            axis_weight = float(item.get("weight", 1))
        except (TypeError, ValueError):
            invalid_scores.append(axis)
            continue
        if value < 0 or value > 10 or axis_weight <= 0:
            invalid_scores.append(axis)
            continue
        if not item.get("evidence"):
            missing_evidence.append(axis)
        total += value * axis_weight
        weight += axis_weight
    weighted_score = round(total / weight, 2) if weight else 0.0
    blockers = [
        check
        for check in critique.get("automated_checks", [])
        if isinstance(check, dict)
        and check.get("result") == "fail"
        and check.get("severity", "blocker") == "blocker"
    ]
    accept = weighted_score >= threshold and not blockers and not invalid_scores and not missing_evidence
    return {
        "weighted_score": weighted_score,
        "threshold": threshold,
        "blockers": [str(check.get("id", "unknown")) for check in blockers],
        "invalid_scores": invalid_scores,
        "missing_evidence": missing_evidence,
        "accept": accept,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Score design critique record")
    parser.add_argument("critique")
    parser.add_argument("--threshold", type=float, default=8.0)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    result = score_critique(load_json(args.critique), threshold=args.threshold)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"WEIGHTED_SCORE={result['weighted_score']:.2f}")
        print(f"BLOCKERS={len(result['blockers'])}")
        if result["invalid_scores"]:
            print("INVALID_SCORES=" + ",".join(result["invalid_scores"]))
        if result["missing_evidence"]:
            print("MISSING_EVIDENCE=" + ",".join(result["missing_evidence"]))
        print("ACCEPT=" + ("YES" if result["accept"] else "NO"))
    return 0 if result["accept"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
