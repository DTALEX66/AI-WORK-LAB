"""Rebuildable usage rollup with caller-supplied, expiring pricing facts."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Iterable


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _event_fingerprint(event: dict[str, Any]) -> str:
    usage = event.get("usage") or {}
    payload = {
        key: usage.get(key)
        for key in (
            "provider", "model", "operation", "inputTokens", "outputTokens",
            "cacheReadTokens", "cacheWriteTokens", "taskDigest", "observedAt",
        )
    }
    return hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()


def price_status_for(
    model: str,
    pricing_catalog: dict[str, dict[str, Any]] | None = None,
    *,
    as_of: datetime | None = None,
) -> dict[str, Any]:
    fact = (pricing_catalog or {}).get(model)
    if not isinstance(fact, dict):
        return {"status": "unknown", "coverage": "unknown", "freshness": "unknown"}
    required = ("billing", "source", "observed_at", "valid_until")
    if any(not fact.get(key) for key in required):
        return {"status": "invalid", "coverage": "partial", "freshness": "unknown"}
    try:
        observed_at = _iso(str(fact["observed_at"]))
        valid_until = _iso(str(fact["valid_until"]))
    except (TypeError, ValueError):
        return {"status": "invalid", "coverage": "partial", "freshness": "unknown"}
    current = (as_of or _now()).astimezone(timezone.utc)
    common = {
        "coverage": "full",
        "source": str(fact["source"]),
        "observed_at": observed_at.isoformat(),
        "valid_until": valid_until.isoformat(),
    }
    if current > valid_until:
        return {"status": "stale", "freshness": "stale", **common}
    if fact["billing"] == "subscription":
        return {"status": "not-metered", "freshness": "fresh", **common}
    rates = (fact.get("input_per_million"), fact.get("output_per_million"))
    if fact["billing"] != "metered" or any(
        isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0
        for value in rates
    ):
        return {"status": "invalid", "freshness": "unknown", "coverage": "partial", **{k: v for k, v in common.items() if k != "coverage"}}
    return {
        "status": "estimated",
        "freshness": "fresh",
        "input_per_million": float(rates[0]),
        "output_per_million": float(rates[1]),
        "currency": str(fact.get("currency") or "UNKNOWN"),
        **common,
    }


def rollup(
    events: Iterable[dict[str, Any]],
    pricing_catalog: dict[str, dict[str, Any]] | None = None,
    *,
    as_of: datetime | None = None,
) -> dict[str, Any]:
    seen: set[str] = set()
    unique: list[dict[str, Any]] = []
    for event in events:
        fingerprint = _event_fingerprint(event)
        if fingerprint not in seen:
            seen.add(fingerprint)
            unique.append(event)

    totals: dict[str, Any] = {
        "inputTokens": 0,
        "outputTokens": 0,
        "cacheReadTokens": 0,
        "cacheWriteTokens": 0,
        "latencyMs": 0,
        "count": 0,
        "estimatedCostUsd": None,
        "costStatus": "unknown",
    }
    by_model: dict[str, dict[str, Any]] = {}
    for event in unique:
        usage = event.get("usage") or {}
        model = str(usage.get("model") or "unknown")
        item = by_model.setdefault(
            model,
            {
                "inputTokens": 0,
                "outputTokens": 0,
                "cacheReadTokens": 0,
                "cacheWriteTokens": 0,
                "count": 0,
                "costStatus": "unknown",
                "estimatedCostUsd": None,
            },
        )
        for key in ("inputTokens", "outputTokens", "cacheReadTokens", "cacheWriteTokens"):
            value = usage.get(key)
            if isinstance(value, (int, float)) and not isinstance(value, bool) and value >= 0:
                totals[key] += value
                item[key] += value
        latency = usage.get("latencyMs")
        if isinstance(latency, (int, float)) and not isinstance(latency, bool) and latency >= 0:
            totals["latencyMs"] += latency
        totals["count"] += 1
        item["count"] += 1

    aggregate_cost = 0.0
    statuses: list[str] = []
    subscription_models: list[str] = []
    for model, item in by_model.items():
        status = price_status_for(model, pricing_catalog, as_of=as_of)
        item["pricing"] = status
        item["costStatus"] = status["status"]
        statuses.append(status["status"])
        if status["status"] == "not-metered":
            subscription_models.append(model)
        elif status["status"] == "estimated":
            cost = (
                item["inputTokens"] / 1_000_000 * status["input_per_million"]
                + item["outputTokens"] / 1_000_000 * status["output_per_million"]
            )
            item["estimatedCostUsd"] = round(cost, 8)
            aggregate_cost += cost

    if statuses and all(status in {"estimated", "not-metered"} for status in statuses):
        if any(status == "estimated" for status in statuses):
            totals["estimatedCostUsd"] = round(aggregate_cost, 8)
            totals["costStatus"] = "estimated"
        else:
            totals["costStatus"] = "not-metered"
    elif "stale" in statuses:
        totals["costStatus"] = "stale"
    elif statuses:
        totals["costStatus"] = "partial"

    return {
        "schemaVersion": "work-lab/usage-rollup/v2",
        "generatedAt": (as_of or _now()).astimezone(timezone.utc).isoformat(),
        "totals": totals,
        "byModel": by_model,
        "subscriptionModels": subscription_models,
        "idempotent": True,
        "rebuildable": True,
        "privacy": {"rawBodies": False, "sensitiveBodies": False},
    }
