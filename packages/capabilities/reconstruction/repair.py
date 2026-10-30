# SPDX-License-Identifier: MIT
"""Bounded, immutable repair acceptance for reconstruction RIR proposals."""
from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from .contracts import validate_rir


MAX_GLOBAL_ITERATIONS = 20
MAX_LOCAL_ITERATIONS = 10


@dataclass(frozen=True)
class RepairMetrics:
    match_ratio: float
    ssim: float
    mean_rgba_error: float
    editability_violations: tuple[str, ...]


@dataclass(frozen=True)
class RepairPlan:
    operation: str
    patch: dict[str, Any]


@dataclass(frozen=True)
class RepairResult:
    rir: dict[str, Any]
    rir_hash: str
    metrics: RepairMetrics
    accepted: bool
    state: str
    iterations: int


def hash_rir(rir: dict[str, Any]) -> str:
    """Hash canonical JSON without mutating or serializing non-finite values."""

    payload = json.dumps(rir, allow_nan=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def plan_repair(rir: dict[str, Any], _metrics: RepairMetrics, diff_map: Path) -> RepairPlan:
    """Return an explicit no-op when no bounded deterministic diff interpretation is available."""

    validate_rir(rir)
    if not isinstance(diff_map, Path):
        raise ValueError("diff map must be a Path")
    return RepairPlan("noop", {})


def apply_repair(rir: dict[str, Any], plan: RepairPlan) -> dict[str, Any]:
    """Apply a closed repair operation to a deep copy, never the caller's RIR object."""

    candidate = copy.deepcopy(rir)
    if plan.operation == "noop":
        pass
    elif plan.operation == "set-canvas-background":
        color = plan.patch.get("color")
        if not isinstance(color, str) or not color:
            raise ValueError("background repair requires a non-empty color")
        candidate["canvas"]["background"] = {"color": color, "recorded": True}
    else:
        raise ValueError("repair operation is not in the closed operation set")
    validate_rir(candidate)
    return candidate


def accept_repair(before: RepairMetrics, after: RepairMetrics) -> bool:
    """Accept only strict visual improvement with no editability violations."""

    return (
        not after.editability_violations
        and (after.match_ratio, after.ssim, -after.mean_rgba_error)
        > (before.match_ratio, before.ssim, -before.mean_rgba_error)
    )


def repair_once(
    rir: dict[str, Any],
    metrics: RepairMetrics,
    planner: Callable[[dict[str, Any], RepairMetrics], RepairPlan],
    evaluator: Callable[[dict[str, Any]], RepairMetrics],
) -> RepairResult:
    """Evaluate one proposal and retain the original RIR unless it is strictly better."""

    original = copy.deepcopy(rir)
    plan = planner(copy.deepcopy(original), metrics)
    candidate = apply_repair(original, plan)
    after = evaluator(candidate)
    if accept_repair(metrics, after):
        return RepairResult(candidate, hash_rir(candidate), after, True, "PARTIAL", 1)
    return RepairResult(original, hash_rir(original), metrics, False, "PARTIAL", 1)


def optimize(
    rir: dict[str, Any],
    metrics: RepairMetrics,
    planner: Callable[[dict[str, Any], RepairMetrics], RepairPlan],
    evaluator: Callable[[dict[str, Any]], RepairMetrics],
    *,
    global_budget: int = MAX_GLOBAL_ITERATIONS,
) -> RepairResult:
    """Run a bounded repair loop; only deterministic verification can later promote its result."""

    if isinstance(global_budget, bool) or not isinstance(global_budget, int) or not 1 <= global_budget <= MAX_GLOBAL_ITERATIONS:
        raise ValueError("global repair budget must be between one and twenty")
    current_rir = copy.deepcopy(rir)
    current_metrics = metrics
    accepted = False
    for iteration in range(1, global_budget + 1):
        result = repair_once(current_rir, current_metrics, planner, evaluator)
        if not result.accepted:
            return RepairResult(current_rir, hash_rir(current_rir), current_metrics, accepted, "PARTIAL", iteration)
        current_rir, current_metrics, accepted = result.rir, result.metrics, True
    return RepairResult(current_rir, hash_rir(current_rir), current_metrics, accepted, "PARTIAL", global_budget)
