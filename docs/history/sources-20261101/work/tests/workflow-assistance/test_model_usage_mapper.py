"""Contract tests for usage mapping truth values (WL3-520 / MR-12).

Covers taskpack §20.5 + §MR-12: unknown never 0, exact/estimated/derived/
unavailable distinguishable, cache_hit_rate only with complete fields,
subscription cost not faked as 0, local not-metered != zero, Kimi readable
but not routable.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts/workflow"))

from model_usage_mapper import map_usage, QUALITY_UNAVAILABLE


class UsageMapperTests(unittest.TestCase):
    def test_unknown_never_zero(self) -> None:
        result = map_usage({"provider": "codex", "input_tokens": None, "output_tokens": None})
        self.assertIsNone(result["input_tokens"])
        self.assertEqual(result["input_quality"], QUALITY_UNAVAILABLE)

    def test_deepseek_cache_hit_rate(self) -> None:
        result = map_usage({"provider": "deepseek", "input_tokens": 100,
                            "output_tokens": 50, "cache_hit_tokens": 80,
                            "cache_miss_tokens": 20, "cost_cents": 0.3})
        self.assertEqual(result["cache_hit_rate"], 0.8)
        self.assertEqual(result["cache_quality"], "exact")

    def test_cache_hit_rate_unavailable_when_incomplete(self) -> None:
        result = map_usage({"provider": "deepseek", "cache_hit_tokens": None,
                            "cache_miss_tokens": None})
        self.assertIsNone(result["cache_hit_rate"])
        self.assertEqual(result["cache_quality"], QUALITY_UNAVAILABLE)

    def test_cache_hit_rate_denominator_zero(self) -> None:
        result = map_usage({"provider": "deepseek", "cache_hit_tokens": 0,
                            "cache_miss_tokens": 0})
        self.assertIsNone(result["cache_hit_rate"])

    def test_codex_subscription_cost_not_zero(self) -> None:
        result = map_usage({"provider": "codex", "input_tokens": 10, "output_tokens": 5})
        self.assertIsNone(result["cost_cents"])
        self.assertEqual(result["cost_quality"], QUALITY_UNAVAILABLE)
        self.assertEqual(result["cost_note"], "subscription_not_metered")

    def test_local_not_metered_not_zero_cost(self) -> None:
        result = map_usage({"provider": "local"})
        self.assertIsNone(result["cost_cents"])
        self.assertEqual(result["cost_note"], "local_not_metered_not_zero_cost")

    def test_kimi_historical_readable_not_routable(self) -> None:
        result = map_usage({"provider": "kimi", "input_tokens": 500, "output_tokens": 300})
        self.assertEqual(result["lifecycle"], "RETIRED")
        self.assertEqual(result["input_tokens"], 500)  # readable
        self.assertFalse(result["routable"])  # never routed

    def test_lifecycle_active_routable(self) -> None:
        result = map_usage({"provider": "deepseek", "lifecycle": "ACTIVE"})
        self.assertTrue(result["routable"])

    def test_lifecycle_retired_not_routable(self) -> None:
        result = map_usage({"provider": "deepseek", "lifecycle": "RETIRED"})
        self.assertFalse(result["routable"])

    def test_string_tokens_normalized_to_int(self) -> None:
        result = map_usage({"provider": "deepseek", "input_tokens": "100",
                            "output_tokens": "50"})
        self.assertEqual(result["input_tokens"], 100)

    def test_schema_version_present(self) -> None:
        result = map_usage({"provider": "deepseek"})
        self.assertEqual(result["schema_version"], "workflow/usage-observation/v1")


if __name__ == "__main__":
    unittest.main()
