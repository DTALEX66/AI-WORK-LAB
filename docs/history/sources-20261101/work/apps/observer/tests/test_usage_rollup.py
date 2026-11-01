from __future__ import annotations

import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from usage_rollup import price_status_for, rollup  # noqa: E402

AS_OF = datetime(2026, 8, 11, tzinfo=timezone.utc)
PRICING = {
    "metered-model": {
        "billing": "metered", "source": "workflow-observation",
        "observed_at": "2026-08-10T00:00:00Z", "valid_until": "2026-08-12T00:00:00Z",
        "currency": "USD", "input_per_million": 1.0, "output_per_million": 2.0,
    },
    "subscription-model": {
        "billing": "subscription", "source": "workflow-observation",
        "observed_at": "2026-08-10T00:00:00Z", "valid_until": "2026-08-12T00:00:00Z",
    },
    "expired-model": {
        "billing": "metered", "source": "workflow-observation",
        "observed_at": "2026-08-01T00:00:00Z", "valid_until": "2026-08-02T00:00:00Z",
        "currency": "USD", "input_per_million": 3.0, "output_per_million": 4.0,
        "stale": False,
    },
}


def sample() -> list[dict]:
    first = {"usage": {"provider": "p", "model": "metered-model", "inputTokens": 100, "outputTokens": 50, "cacheReadTokens": 10, "observedAt": "2026-08-11T00:00:00Z"}}
    return [first, dict(first), {"usage": {"provider": "p", "model": "subscription-model", "inputTokens": 500, "outputTokens": 200, "observedAt": "2026-08-11T00:01:00Z"}}]


class UsageRollupTests(unittest.TestCase):
    def test_rollup_is_idempotent_and_uses_caller_pricing(self) -> None:
        first = rollup(sample(), PRICING, as_of=AS_OF)
        second = rollup(sample(), PRICING, as_of=AS_OF)
        self.assertEqual(first, second)
        self.assertEqual(first["totals"]["count"], 2)
        self.assertEqual(first["totals"]["costStatus"], "estimated")
        self.assertIsNotNone(first["totals"]["estimatedCostUsd"])

    def test_expiry_is_computed_not_trusted_from_stale_flag(self) -> None:
        status = price_status_for("expired-model", PRICING, as_of=AS_OF)
        self.assertEqual(status["status"], "stale")
        self.assertEqual(status["freshness"], "stale")

    def test_subscription_is_not_metered(self) -> None:
        status = price_status_for("subscription-model", PRICING, as_of=AS_OF)
        self.assertEqual(status["status"], "not-metered")

    def test_unknown_or_partial_pricing_never_emits_aggregate_usd(self) -> None:
        events = sample() + [{"usage": {"provider": "p", "model": "unknown-model", "inputTokens": 1, "outputTokens": 1, "observedAt": "2026-08-11T00:02:00Z"}}]
        result = rollup(events, PRICING, as_of=AS_OF)
        self.assertEqual(result["totals"]["costStatus"], "partial")
        self.assertIsNone(result["totals"]["estimatedCostUsd"])

    def test_module_contains_no_embedded_model_or_price_catalog(self) -> None:
        source = (ROOT / "scripts" / "usage_rollup.py").read_text(encoding="utf-8")
        self.assertNotIn("PRICING_CATALOG", source)
        self.assertNotIn("deepseek-v4", source)
        self.assertNotIn("gpt-5", source)
        self.assertNotIn("claude-", source)


if __name__ == "__main__":
    unittest.main()
