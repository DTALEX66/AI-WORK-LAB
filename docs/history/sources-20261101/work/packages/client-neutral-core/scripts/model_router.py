"""WORK-LAB Model Router (WLR-400/410).

Deterministic rule-based routing: classify a task by risk/type/privacy/context/
budget, recommend a capability Lane, and emit an InvocationPlan. Zero model
calls for routing itself (WLR-410: regular routing never calls a model).
Borrows RouteLLM's cost-threshold idea: budget limits degrade to a cheaper lane.

Boundary: this module only produces a plan; credentials/request bodies stay
with the client (Hermes/Codex/DSH). It never proxies anything.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# Capability lanes (ModelReference level; actual model chosen by client)
LANES = {
    "A": {"label": "fast-cheap", "model": "deepseek-v4-flash", "class": "fast", "cost": "low"},
    "B": {"label": "strong-reasoning", "model": "gpt-5.6-terra", "class": "reasoning", "cost": "high"},
    "C": {"label": "vision-local", "model": "qwen2.5vl", "class": "vision", "cost": "local"},
    "D": {"label": "local-privacy", "model": "minimax-h3", "class": "local", "cost": "local"},
}

# Deterministic classification signals (keyword-based, zero model)
_VISION_HINTS = ("image", "图片", "截图", "screenshot", "ocr", "vision", "ui", "visual", "识别", "看到")
_PRIVACY_HINTS = ("secret", "key", "token", "credential", "私密", "密码", "凭据", "api key")
_COMPLEX_HINTS = ("architecture", "架构", "debug", "调试", "refactor", "重构", "design", "设计", "migration", "迁移", "complex", "复杂", "优化", "performance")
_SIMPLE_HINTS = ("translate", "翻译", "summary", "摘要", "format", "格式化", "rename", "重命名", "typo", "typos", "简单", "formatting")


@dataclass
class TaskSignal:
    task: str
    risk: str = "low"            # low | medium | high
    task_type: str = "general"   # code | research | visual | config | doc
    context_tokens: int = 0
    budget_usd: float | None = None
    privacy_required: bool = False
    tool_requirement: str | None = None


@dataclass
class InvocationPlan:
    lane: str
    model_ref: str
    model_class: str
    cost_class: str
    reason: str
    budget_after: float | None = None
    cache_policy: str = "stable-prefix"
    client: str | None = None   # recommended client, may be None (client-neutral)

    def to_dict(self) -> dict[str, Any]:
        return {
            "lane": self.lane,
            "modelRef": self.model_ref,
            "modelClass": self.model_class,
            "costClass": self.cost_class,
            "reason": self.reason,
            "budgetAfter": self.budget_after,
            "cachePolicy": self.cache_policy,
            "client": self.client,
            "unknownStaysUnknown": True,
        }


def _contains(text: str, hints: tuple[str, ...]) -> bool:
    t = text.lower()
    return any(h.lower() in t for h in hints)


def route(signal: TaskSignal, lanes: dict[str, Any] | None = None) -> InvocationPlan:
    """Deterministic routing with cost-threshold degradation (RouteLLM-style)."""
    lanes = lanes or LANES
    text = signal.task

    # 1. privacy trumps everything
    if signal.privacy_required or _contains(text, _PRIVACY_HINTS):
        return _plan("D", lanes, "privacy-sensitive -> local lane")

    # 2. vision
    if signal.task_type == "visual" or _contains(text, _VISION_HINTS):
        return _plan("C", lanes, "visual task -> local vision lane")

    # 3. complexity / risk (strong signal words trigger reasoning lane directly)
    if signal.risk in ("high", "medium") or _contains(text, _COMPLEX_HINTS):
        return _plan("B", lanes, "high complexity/reasoning -> strong reasoning lane")

    # 4. simple / daily
    if _contains(text, _SIMPLE_HINTS) or signal.task_type == "doc":
        return _plan("A", lanes, "simple/daily -> fast lane")

    # 5. default
    return _plan("A", lanes, "default -> fast lane")


def _plan(lane: str, lanes: dict[str, Any], reason: str) -> InvocationPlan:
    cfg = lanes[lane]
    return InvocationPlan(
        lane=lane,
        model_ref=cfg["model"],
        model_class=cfg["class"],
        cost_class=cfg["cost"],
        reason=reason,
    )


def route_with_budget(signal: TaskSignal, budget_usd: float | None = None) -> InvocationPlan:
    """Route then degrade by budget (RouteLLM cost-threshold): if the chosen
    lane's cost class is high and budget is tight, downgrade to fast lane."""
    plan = route(signal)
    budget = budget_usd if budget_usd is not None else signal.budget_usd
    if budget is not None and budget < 0.10 and plan.cost_class == "high":
        downgraded = _plan("A", LANES, plan.reason + "; budget < $0.10 -> downgraded to fast lane")
        downgraded.budget_after = budget
        return downgraded
    plan.budget_after = budget
    return plan
