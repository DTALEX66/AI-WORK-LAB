"""Model usage mapping with honest nullability (WL3-520 / MR-12).

Extends nullable usage: DeepSeek cache hit/miss, Codex unknown, local KV
unknown are separated; provider lifecycle gains ACTIVE/RETIRED; field-level
quality_state.

Contract rules (taskpack §MR-12 acceptance):
- unknown never becomes 0
- exact / estimated / derived / unavailable are distinguishable
- cache_hit_rate computed only when fields are complete
- subscription cost is never faked as 0
- local not-metered != zero cost
- historical Kimi usage readable but never routable
"""
from __future__ import annotations

from typing import Any

SCHEMA_VERSION = "workflow/usage-observation/v1"

QUALITY_EXACT = "exact"
QUALITY_ESTIMATED = "estimated"
QUALITY_DERIVED = "derived"
QUALITY_UNAVAILABLE = "unavailable"


def map_usage(observation: dict[str, Any]) -> dict[str, Any]:
    """Map one provider usage observation into an honest usage record."""
    provider = observation.get("provider", "unknown")
    lifecycle = observation.get("lifecycle", "ACTIVE")

    input_tokens = _nullable_int(observation.get("input_tokens"))
    output_tokens = _nullable_int(observation.get("output_tokens"))
    cache_hit = _nullable_int(observation.get("cache_hit_tokens"))
    cache_miss = _nullable_int(observation.get("cache_miss_tokens"))

    # DeepSeek: hit/miss separate
    if provider == "deepseek":
        return _deepseek(observation, input_tokens, output_tokens, cache_hit, cache_miss)
    # Codex: unknown cache fields -> unavailable, never 0
    if provider == "codex":
        return _codex(observation, input_tokens, output_tokens)
    # Local KV: not metered -> not zero
    if provider == "local":
        return _local(observation, input_tokens, output_tokens)
    # Kimi historical
    if provider == "kimi":
        return _kimi(observation)
    return _generic(observation, input_tokens, output_tokens)


def _nullable_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _cache_hit_rate(hit: int | None, miss: int | None) -> float | None:
    if hit is None or miss is None:
        return None
    total = hit + miss
    if total == 0:
        return None  # denominator zero -> unavailable, never 0
    return round(hit / total, 4)


def _token_quality(value: int | None, observed: bool) -> str:
    if value is None:
        return QUALITY_UNAVAILABLE
    return QUALITY_EXACT if observed else QUALITY_ESTIMATED


def _deepseek(obs: dict[str, Any], inp: int | None, out: int | None,
              hit: int | None, miss: int | None) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "provider": "deepseek",
        "lifecycle": obs.get("lifecycle", "ACTIVE"),
        "input_tokens": inp,
        "input_quality": _token_quality(inp, obs.get("observed", True)),
        "output_tokens": out,
        "output_quality": _token_quality(out, obs.get("observed", True)),
        "cache_hit_tokens": hit,
        "cache_miss_tokens": miss,
        "cache_quality": QUALITY_EXACT if (hit is not None and miss is not None) else QUALITY_UNAVAILABLE,
        "cache_hit_rate": _cache_hit_rate(hit, miss),
        "cost_cents": obs.get("cost_cents"),
        "cost_quality": QUALITY_UNAVAILABLE if obs.get("cost_cents") is None else QUALITY_EXACT,
        "routable": obs.get("lifecycle", "ACTIVE") == "ACTIVE",
    }


def _codex(obs: dict[str, Any], inp: int | None, out: int | None) -> dict[str, Any]:
    # Codex subscription: cost unknown, never faked as 0
    return {
        "schema_version": SCHEMA_VERSION,
        "provider": "codex",
        "lifecycle": obs.get("lifecycle", "ACTIVE"),
        "input_tokens": inp,
        "input_quality": _token_quality(inp, obs.get("observed", True)),
        "output_tokens": out,
        "output_quality": _token_quality(out, obs.get("observed", True)),
        "cache_hit_tokens": None,
        "cache_miss_tokens": None,
        "cache_quality": QUALITY_UNAVAILABLE,
        "cache_hit_rate": None,
        "cost_cents": None,
        "cost_quality": QUALITY_UNAVAILABLE,
        "cost_note": "subscription_not_metered",
        "routable": obs.get("lifecycle", "ACTIVE") == "ACTIVE",
    }


def _local(obs: dict[str, Any], inp: int | None, out: int | None) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "provider": "local",
        "lifecycle": obs.get("lifecycle", "ACTIVE"),
        "input_tokens": inp,
        "input_quality": _token_quality(inp, obs.get("observed", True)),
        "output_tokens": out,
        "output_quality": _token_quality(out, obs.get("observed", True)),
        "cache_hit_tokens": None,
        "cache_miss_tokens": None,
        "cache_quality": QUALITY_UNAVAILABLE,
        "cache_hit_rate": None,
        "cost_cents": None,
        "cost_quality": QUALITY_UNAVAILABLE,
        "cost_note": "local_not_metered_not_zero_cost",
        "routable": obs.get("lifecycle", "ACTIVE") == "ACTIVE",
    }


def _kimi(obs: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "provider": "kimi",
        "lifecycle": "RETIRED",
        "input_tokens": _nullable_int(obs.get("input_tokens")),
        "output_tokens": _nullable_int(obs.get("output_tokens")),
        "cache_hit_tokens": None,
        "cache_miss_tokens": None,
        "cache_quality": QUALITY_UNAVAILABLE,
        "cache_hit_rate": None,
        "cost_cents": None,
        "cost_quality": QUALITY_UNAVAILABLE,
        "historical_only": True,
        "routable": False,  # historical usage readable, never routed
    }


def _generic(obs: dict[str, Any], inp: int | None, out: int | None) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "provider": obs.get("provider", "unknown"),
        "lifecycle": obs.get("lifecycle", "ACTIVE"),
        "input_tokens": inp,
        "input_quality": _token_quality(inp, obs.get("observed", True)),
        "output_tokens": out,
        "output_quality": _token_quality(out, obs.get("observed", True)),
        "cache_hit_tokens": None,
        "cache_miss_tokens": None,
        "cache_quality": QUALITY_UNAVAILABLE,
        "cache_hit_rate": None,
        "cost_cents": obs.get("cost_cents"),
        "cost_quality": QUALITY_UNAVAILABLE if obs.get("cost_cents") is None else QUALITY_EXACT,
        "routable": obs.get("lifecycle", "ACTIVE") == "ACTIVE",
    }


if __name__ == "__main__":
    import json
    samples = [
        {"provider": "deepseek", "input_tokens": 100, "output_tokens": 50,
         "cache_hit_tokens": 80, "cache_miss_tokens": 20, "cost_cents": 0.3},
        {"provider": "codex", "input_tokens": 200, "output_tokens": 100},
        {"provider": "local", "input_tokens": None, "output_tokens": None},
        {"provider": "kimi", "input_tokens": 500, "output_tokens": 300},
    ]
    for s in samples:
        print(json.dumps(map_usage(s), ensure_ascii=False))
