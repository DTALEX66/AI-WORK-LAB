"""Contract tests for model-lane/billing policy (WL3-330)."""

from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("model_policy", ROOT / "services/policy/model_policy.py")
assert SPEC and SPEC.loader
MOD = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MOD
SPEC.loader.exec_module(MOD)

def _base_policy(**overrides):
    policy = {
        "schema_version": "workflow/model-policy/v1",
        "policy_id": "lane-default",
        "task_class": "coding",
        "model_class": "general",
        "selection": "user-selected",
        "context_budget": {
            "input_tokens": 100000,
            "output_tokens": 100000,
            "reserved_tokens": 1000,
            "overflow": "fail-closed",
        },
        "cost": {"mode": "unknown", "source": "unknown-profile"},
        "redaction": {"prompt_response_bodies": "excluded", "credentials": "excluded"},
        "degradation": "blocked-when-unavailable",
    }
    policy.update(overrides)
    return policy


SUBSCRIPTION_POLICY = _base_policy(
    policy_id="codex-subscription",
    cost={"mode": "unknown", "source": "subscription"},
)
API_POLICY = _base_policy(
    policy_id="deepseek-api",
    cost={"mode": "unknown", "source": "billing-profile"},
)


class ModelLaneBillingTests(unittest.TestCase):
    def test_subscription_usage_is_not_metered_as_cost(self) -> None:
        result = MOD.evaluate_policy(SUBSCRIPTION_POLICY, {"input_tokens": 1000, "output_tokens": 500})
        self.assertEqual(result["status"], "UNKNOWN_COST")
        self.assertIn("COST_UNKNOWN", result["reason_codes"])
        # A subscription must not fabricate a dollar amount.
        self.assertIsNone(result["cost"]["amount"])
        self.assertNotIn("estimated", result["cost"]["mode"])

    def test_api_unknown_rate_stays_unknown_not_zero(self) -> None:
        result = MOD.evaluate_policy(API_POLICY, {"input_tokens": 1000, "output_tokens": 500})
        self.assertEqual(result["status"], "UNKNOWN_COST")
        self.assertIsNone(result["cost"]["amount"])

    def test_capability_lane_selects_by_capability_not_model_id(self) -> None:
        available = [
            {"id": "model-a", "provider": "p1", "available": True, "capabilities": ["code-review"]},
            {"id": "model-b", "provider": "p2", "available": True, "capabilities": ["code-review"]},
            {"id": "model-c", "provider": "p3", "available": False, "capabilities": ["code-review"]},
        ]
        result = MOD.choose_model(available, "code-review")
        self.assertEqual(result["status"], "CAPABILITY_MATCH")
        self.assertEqual(result["selected"]["id"], "model-a")
        # Unavailable models never win.
        self.assertNotEqual(result["selected"]["id"], "model-c")

    def test_no_silent_fallback_when_capability_missing(self) -> None:
        result = MOD.choose_model([{"id": "x", "available": True, "capabilities": ["chat"]}], "code-review")
        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(result["reason"], "CAPABILITY_UNAVAILABLE")
        self.assertIsNone(result["selected"])

    def test_usage_fields_are_allowlisted(self) -> None:
        sanitized = MOD.sanitize_usage(
            {
                "input_tokens": 10,
                "output_tokens": 5,
                "total_tokens": 15,
                "api_key": "secret",
                "prompt": "body",
                "latency_ms": 42,
            }
        )
        self.assertNotIn("api_key", sanitized)
        self.assertNotIn("prompt", sanitized)
        self.assertNotIn("total_tokens", sanitized)  # derived field excluded
        self.assertEqual(sanitized["latency_ms"], 42)


if __name__ == "__main__":
    unittest.main()
