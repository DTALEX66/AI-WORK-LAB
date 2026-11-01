#!/usr/bin/env python3
"""Offline evaluator for model-class, context, cost and redaction policy.

The evaluator never selects a live provider, reads credentials, or sends
telemetry. It consumes a small allowlisted usage fixture instead.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

SCHEMA_PATH = Path(__file__).resolve().parents[2] / "packages" / "contracts" / "schemas" / "workflow" / "model-policy.schema.json"
_USAGE_FIELDS = {"input_tokens", "output_tokens", "cache_read_tokens", "cache_write_tokens", "latency_ms", "tool_calls"}


def sanitize_usage(raw: dict[str, Any]) -> dict[str, int | float]:
    result: dict[str, int | float] = {}
    for key in _USAGE_FIELDS:
        value = raw.get(key)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
            continue
        result[key] = value
    return result


def choose_model(
    available_models: list[dict[str, Any]],
    required_capability: str,
    *,
    requested_model: str | None = None,
) -> dict[str, Any]:
    """Choose only from a caller-provided availability snapshot."""
    candidates = [
        item for item in available_models
        if isinstance(item, dict)
        and item.get("available") is True
        and required_capability in item.get("capabilities", [])
    ]
    if requested_model is not None:
        selected = next((item for item in candidates if item.get("id") == requested_model), None)
        if selected is None:
            return {"status": "BLOCKED", "reason": "REQUESTED_MODEL_UNAVAILABLE", "selected": None}
        return {"status": "USER_SELECTED", "reason": None, "selected": {"id": selected["id"], "provider": selected.get("provider", "unknown"), "capability": required_capability}}
    if not candidates:
        return {"status": "BLOCKED", "reason": "CAPABILITY_UNAVAILABLE", "selected": None}
    selected = sorted(candidates, key=lambda item: str(item.get("id", "")))[0]
    return {"status": "CAPABILITY_MATCH", "reason": None, "selected": {"id": selected["id"], "provider": selected.get("provider", "unknown"), "capability": required_capability}}


def _validate(policy: dict[str, Any]) -> None:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    errors = sorted(Draft202012Validator(schema).iter_errors(policy), key=lambda item: list(item.path))
    if errors:
        raise ValueError(f"invalid model policy: {errors[0].message}")


def evaluate_policy(policy: dict[str, Any], raw_usage: dict[str, Any]) -> dict[str, Any]:
    _validate(policy)
    usage = sanitize_usage(raw_usage)
    input_present = "input_tokens" in usage
    output_present = "output_tokens" in usage
    input_tokens = int(usage.get("input_tokens", 0))
    output_tokens = int(usage.get("output_tokens", 0))
    usage_complete = input_present and output_present
    total_tokens = input_tokens + output_tokens if usage_complete else None
    reasons: list[str] = []
    if not usage_complete:
        reasons.append("USAGE_PARTIAL")

    context = policy["context_budget"]
    if input_tokens > context["input_tokens"] or output_tokens > context["output_tokens"]:
        reasons.append("CONTEXT_BUDGET_EXCEEDED")
    if policy["selection"] == "unavailable":
        reasons.append("SELECTION_UNAVAILABLE")

    cost_policy = policy["cost"]
    mode = cost_policy["mode"]
    amount: float | None = None
    currency: str | None = None
    if mode == "estimated":
        if total_tokens is None:
            reasons.append("COST_UNKNOWN_FROM_PARTIAL_USAGE")
        else:
            amount = total_tokens / 1_000_000 * float(cost_policy["unit_price_per_million_tokens"])
            currency = cost_policy["currency"]
    elif mode == "unknown":
        reasons.append("COST_UNKNOWN")
    else:
        reasons.append("COST_NOT_RECONCILED")

    if reasons and any(reason in {"CONTEXT_BUDGET_EXCEEDED", "SELECTION_UNAVAILABLE"} for reason in reasons):
        status = "BLOCKED"
    elif "USAGE_PARTIAL" in reasons:
        status = "UNKNOWN_USAGE"
    elif mode == "unknown":
        status = "UNKNOWN_COST"
    else:
        status = "ALLOW"

    return {
        "status": status,
        "reason_codes": reasons,
        "policy_id": policy["policy_id"],
        "model_class": policy["model_class"],
        "usage": {**usage, "total_tokens": total_tokens},
        "cost": {"mode": mode, "amount": amount, "currency": currency, "source": cost_policy["source"]},
        "redaction": policy["redaction"],
    }


if __name__ == "__main__":
    raise SystemExit("Use evaluate_policy() with an offline fixture; no live provider command is exposed.")
