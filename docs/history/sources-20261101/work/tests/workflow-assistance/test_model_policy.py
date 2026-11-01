from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "services/policy/model_policy.py"
SCHEMA = ROOT / "packages/contracts/schemas/workflow/model-policy.schema.json"


def load_module():
    spec = importlib.util.spec_from_file_location("model_policy", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def policy(**overrides: object) -> dict:
    value = {
        "schema_version": "workflow/model-policy/v1",
        "policy_id": "offline-review",
        "task_class": "review",
        "model_class": "reasoning",
        "selection": "offline-fixture",
        "context_budget": {
            "input_tokens": 1000,
            "output_tokens": 400,
            "reserved_tokens": 100,
            "overflow": "fail-closed",
        },
        "cost": {
            "mode": "estimated",
            "currency": "USD",
            "unit_price_per_million_tokens": 2.0,
            "effective_at": "2026-08-07T00:00:00Z",
            "source": "local-fixture",
        },
        "redaction": {
            "prompt_response_bodies": "excluded",
            "credentials": "excluded",
        },
        "degradation": "unknown-when-unavailable",
    }
    value.update(overrides)
    return value


class ModelPolicyTests(unittest.TestCase):
    def test_valid_policy_is_allowed_and_estimates_cost(self) -> None:
        module = load_module()
        result = module.evaluate_policy(policy(), {"input_tokens": 500, "output_tokens": 100})
        self.assertEqual(result["status"], "ALLOW")
        self.assertEqual(result["usage"]["total_tokens"], 600)
        self.assertAlmostEqual(result["cost"]["amount"], 0.0012, places=8)

    def test_unavailable_selection_is_blocked_without_fallback(self) -> None:
        module = load_module()
        value = policy(selection="unavailable")
        result = module.evaluate_policy(value, {})
        self.assertEqual(result["status"], "BLOCKED")
        self.assertIn("SELECTION_UNAVAILABLE", result["reason_codes"])

    def test_context_overflow_fails_closed(self) -> None:
        module = load_module()
        result = module.evaluate_policy(policy(), {"input_tokens": 1001, "output_tokens": 0})
        self.assertEqual(result["status"], "BLOCKED")
        self.assertIn("CONTEXT_BUDGET_EXCEEDED", result["reason_codes"])

    def test_unknown_cost_does_not_become_zero(self) -> None:
        module = load_module()
        value = policy(cost={"mode": "unknown", "source": "local-fixture"})
        result = module.evaluate_policy(value, {"input_tokens": 2, "output_tokens": 3})
        self.assertEqual(result["status"], "UNKNOWN_COST")
        self.assertIsNone(result["cost"]["amount"])

    def test_usage_allowlist_excludes_bodies_and_credentials(self) -> None:
        module = load_module()
        result = module.sanitize_usage({
            "input_tokens": 4,
            "output_tokens": 5,
            "prompt": "REDACTED_BODY",
            "response": "REDACTED_BODY",
            "api_key": "REDACTED",
            "latency_ms": 12,
        })
        self.assertEqual(result, {"input_tokens": 4, "output_tokens": 5, "latency_ms": 12})

    def test_malformed_policy_is_rejected_before_evaluation(self) -> None:
        module = load_module()
        with self.assertRaisesRegex(ValueError, "invalid model policy"):
            module.evaluate_policy({"schema_version": "workflow/model-policy/v1"}, {})

    def test_dynamic_capability_snapshot_never_silently_falls_back(self) -> None:
        module = load_module()
        available = [{"id": "reasoning-a", "provider": "codex", "capabilities": ["review"], "available": True}]
        self.assertEqual(module.choose_model(available, "review", requested_model="missing")["status"], "BLOCKED")
        self.assertEqual(module.choose_model(available, "review")["status"], "CAPABILITY_MATCH")

    def test_partial_usage_is_unknown_not_zero_cost(self) -> None:
        module = load_module()
        result = module.evaluate_policy(policy(), {"input_tokens": 10})
        self.assertEqual(result["status"], "UNKNOWN_USAGE")
        self.assertIsNone(result["cost"]["amount"])
        self.assertIn("USAGE_PARTIAL", result["reason_codes"])


if __name__ == "__main__":
    unittest.main()
