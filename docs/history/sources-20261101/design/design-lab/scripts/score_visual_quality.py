#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Score a visual-quality report against a weighted rubric.

Hard gates and evidence completeness are fail-closed: a high numeric score does
not override missing required evidence, invalid axis scores, or failed gates.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def load_json(path: str | Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _axis_item(axes: dict[str, Any], axis_id: str) -> dict[str, Any] | None:
    item = axes.get(axis_id)
    if item is None:
        return None
    if isinstance(item, dict):
        return item
    if isinstance(item, (int, float)):
        return {"score": item, "evidence": []}
    return {"score": item, "evidence": []}


def _hard_gate_maps(report: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    gates: dict[str, Any] = {}
    malformed: list[str] = []
    for gate in report.get("hard_gates", []):
        if not isinstance(gate, dict) or not gate.get("id"):
            malformed.append(str(gate))
            continue
        gates[str(gate["id"])] = gate
    return gates, malformed


def score_report(report: dict[str, Any], rubric: dict[str, Any]) -> dict[str, Any]:
    axes = report.get("axes", {})
    if not isinstance(axes, dict):
        axes = {}

    scale = rubric.get("scale", {})
    minimum = float(scale.get("min", 0))
    maximum = float(scale.get("max", 10))
    total = 0.0
    weight = 0.0
    missing_axes: list[str] = []
    invalid_axes: list[str] = []
    missing_evidence: list[str] = []
    expected_axes: set[str] = set()

    for spec in rubric.get("axes", []):
        axis_id = str(spec.get("id", ""))
        expected_axes.add(axis_id)
        item = _axis_item(axes, axis_id)
        if not axis_id or item is None:
            missing_axes.append(axis_id)
            continue
        try:
            score = float(item.get("score"))
        except (TypeError, ValueError):
            invalid_axes.append(axis_id)
            continue
        if score < minimum or score > maximum:
            invalid_axes.append(axis_id)
            continue
        evidence = item.get("evidence", [])
        if spec.get("requires_evidence") and not evidence:
            missing_evidence.append(axis_id)
        axis_weight = float(spec.get("weight", 1))
        total += score * axis_weight
        weight += axis_weight

    gate_map, malformed_gates = _hard_gate_maps(report)
    required_gate_ids = [str(gate) for gate in rubric.get("hard_gates", [])]
    missing_hard_gates = [gate_id for gate_id in required_gate_ids if gate_id not in gate_map]
    failed_gates: list[str] = []
    warning_gates: list[str] = []
    for gate_id, gate in gate_map.items():
        result = gate.get("result")
        passed = gate.get("pass")
        if passed is False or result == "fail":
            failed_gates.append(gate_id)
        elif result == "warning":
            warning_gates.append(gate_id)

    score = round(total / weight, 2) if weight else 0.0
    acceptance = rubric.get("acceptance", {})
    reject_below = float(acceptance.get("reject_below", acceptance.get("revise", 7.0)))
    accept_at = float(acceptance.get("accept", 8.0))
    blocking = bool(missing_axes or invalid_axes or missing_evidence or failed_gates or missing_hard_gates or malformed_gates)
    if blocking or score < reject_below:
        decision = "reject"
    elif score < accept_at or warning_gates:
        decision = "revise"
    else:
        decision = "accept"

    return {
        "score": score,
        "decision": decision,
        "failed_gates": failed_gates,
        "warning_gates": warning_gates,
        "missing_hard_gates": missing_hard_gates,
        "malformed_gates": malformed_gates,
        "missing_axes": missing_axes,
        "invalid_axes": invalid_axes,
        "missing_evidence": missing_evidence,
        "unknown_axes": sorted(set(axes) - expected_axes),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Score visual quality report")
    parser.add_argument("report")
    parser.add_argument("--rubric", required=True)
    args = parser.parse_args()
    result = score_report(load_json(args.report), load_json(args.rubric))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["decision"] == "accept" else 1


if __name__ == "__main__":
    raise SystemExit(main())
