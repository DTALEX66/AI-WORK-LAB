#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""DL-REL-001 / DL-QLT-001: E1-assisted scoring for a design artifact.

Takes a rubric (evals/rubrics/*.rubric.json) + a human score sheet
(scores JSON: {"artifact": "path", "scores": {"axis-id": 0..10}, "reviewer": "..."}),
computes weighted score, applies acceptance thresholds, and emits a
JuryRecord-shaped verdict (human-calibrated, machine-computed).

Usage:
  python score_artifact.py --rubric design-lab/evals/rubrics/3d.rubric.json \
      --scores scores/3d-sample.json
  python score_artifact.py --list     # list available rubrics
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
RUBRICS = ROOT / "design-lab" / "evals" / "rubrics"


def list_rubrics() -> None:
    for p in sorted(RUBRICS.glob("*.rubric.json")):
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
            axes = len(d.get("axes", []))
            acc = d.get("acceptance", {})
            print(f"  {p.name}: {axes} axes | accept>={acc.get('accept')} revise>={acc.get('revise')}")
        except (OSError, json.JSONDecodeError) as exc:
            print(f"  {p.name}: ERROR ({exc})")


def score(rubric_path: Path, scores_path: Path) -> tuple[dict, int]:
    try:
        rubric = json.loads(rubric_path.read_text(encoding="utf-8"))
        sheet = json.loads(scores_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {"error": str(exc)}, 1

    axes = rubric.get("axes", [])
    if not axes:
        return {"error": "rubric has no axes"}, 1

    scores_in = sheet.get("scores", {})
    scale = rubric.get("scale", {"min": 0, "max": 10})
    lo, hi = scale.get("min", 0), scale.get("max", 10)

    rows = []
    total_w = 0.0
    total_ws = 0.0
    missing = []
    for ax in axes:
        aid = ax["id"]
        w = ax.get("weight", 1.0)
        total_w += w
        s = scores_in.get(aid)
        if s is None:
            missing.append(aid)
            continue
        s = float(s)
        if not (lo <= s <= hi):
            return {"error": f"axis {aid} score {s} out of range [{lo},{hi}]"}, 1
        rows.append({"axis": aid, "weight": w, "score": s, "weighted": round(w * s, 3)})
        total_ws += w * s

    if missing:
        return {"error": f"missing scores for axes: {missing}"}, 1

    weighted = round(total_ws / total_w, 2)
    acc = rubric.get("acceptance", {})
    accept, revise, reject_below = acc.get("accept", 8.0), acc.get("revise", 6.5), acc.get("reject_below", 6.5)
    if weighted >= accept:
        verdict = "ACCEPT"
    elif weighted >= revise:
        verdict = "REVISE"
    else:
        verdict = "REJECT"

    result = {
        "schema_version": "design-lab/jury-record/v1",
        "rubric_id": rubric.get("id", rubric_path.stem),
        "rubric_version": rubric.get("version", "?"),
        "artifact": sheet.get("artifact", "?"),
        "reviewer": sheet.get("reviewer", "unset"),
        "scale": {"min": lo, "max": hi},
        "axes": rows,
        "weighted_score": weighted,
        "thresholds": {"accept": accept, "revise": revise, "reject_below": reject_below},
        "verdict": verdict,
        "human_calibration": True,
        "machine_computed": True,
    }
    return result, 0


def main() -> int:
    ap = argparse.ArgumentParser(description="E1-assisted artifact scoring")
    ap.add_argument("--rubric", type=Path)
    ap.add_argument("--scores", type=Path)
    ap.add_argument("--list", action="store_true")
    args = ap.parse_args()

    if args.list:
        list_rubrics()
        return 0
    if not args.rubric or not args.scores:
        ap.error("--rubric and --scores required (or --list)")

    result, code = score(args.rubric, args.scores)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result.get("verdict"):
        print(f"\nSCORE_ARTIFACT={result['verdict']} weighted={result['weighted_score']}")
    return code


if __name__ == "__main__":
    sys.exit(main())
