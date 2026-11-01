#!/usr/bin/env python3
from __future__ import annotations

from datetime import datetime, timezone

from usage_rollup import price_status_for, rollup


def verify() -> dict:
    as_of = datetime(2026, 8, 11, tzinfo=timezone.utc)
    pricing = {
        "fixture-metered": {
            "billing": "metered", "source": "test-fixture",
            "observed_at": "2026-08-10T00:00:00Z", "valid_until": "2026-08-12T00:00:00Z",
            "currency": "USD", "input_per_million": 1.0, "output_per_million": 2.0,
        }
    }
    event = {"usage": {"provider": "fixture", "model": "fixture-metered", "inputTokens": 100, "outputTokens": 50, "observedAt": "2026-08-11T00:00:00Z"}}
    first = rollup([event, event], pricing, as_of=as_of)
    second = rollup([event, event], pricing, as_of=as_of)
    if first != second or first["totals"]["count"] != 1:
        raise ValueError("rollup is not deterministic and idempotent")
    if price_status_for("fixture-metered", pricing, as_of=as_of)["status"] != "estimated":
        raise ValueError("fresh caller-supplied pricing was not accepted")
    if rollup([event], {}, as_of=as_of)["totals"]["estimatedCostUsd"] is not None:
        raise ValueError("unknown pricing fabricated USD")
    return {"idempotent": True, "rebuildable": True, "embedded_catalog": False}


def main() -> int:
    try:
        verify()
    except ValueError as exc:
        print(f"USAGE_ROLLUP_FAIL {exc}")
        return 1
    print("USAGE_ROLLUP_PASS idempotent=true rebuildable=true embedded_catalog=false pricing=caller-supplied")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
