#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""DL-V2 P1-E: Quality Gate engine.

分层评分 Q = sum(w_i * d_i)。hard blockers 与总分独立：
blocker 存在 -> decision=fail（无论加权平均多高）。RULE 6：Quality FAIL 永不静默降级。
"""
from __future__ import annotations

from typing import Any

VALID_DECISIONS = {"pass", "fail"}


def evaluate(
    scores: dict[str, float],
    gate: dict[str, Any],
    blockers: list[str],
) -> dict[str, Any]:
    dims = {d["id"]: d for d in gate.get("dimensions", [])}
    total_weight = sum(d.get("weight", 0) for d in gate.get("dimensions", []))
    if total_weight <= 0:
        return {"score": 0.0, "decision": "fail", "blocking_issues": blockers, "dimensions": scores, "error": "no dimensions"}

    weighted = sum(scores.get(did, 0.0) * d.get("weight", 0) for did, d in dims.items()) / total_weight
    min_dims = gate.get("minimum_dimensions", {})
    below = {k: v for k, v in min_dims.items() if scores.get(k, 0.0) < v}

    blocking_issues = list(blockers)
    for k, v in below.items():
        blocking_issues.append(f"{k}_below_minimum({scores.get(k, 0.0):.1f}<{v})")

    threshold = gate.get("minimum_total", 0)
    blocked = bool(blocking_issues)
    decision = "fail" if (blocked or weighted < threshold) else "pass"
    return {
        "score": round(weighted, 2),
        "decision": decision,
        "blocking_issues": blocking_issues,
        "dimensions": scores,
    }
