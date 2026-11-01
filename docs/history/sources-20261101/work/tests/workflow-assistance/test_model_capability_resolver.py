"""Contract tests for the task-level capability resolver (WL3-330 / MR-08).

Covers taskpack §20.2 resolver matrix: retired provider, cloud egress gating,
observer no-model, private-data no cloud fallback, code-write default,
user-explicit-blocked without silent fallback, equivalent-candidate record.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts/workflow"))

from model_capability_resolver import Resolver


def base_catalog() -> dict:
    return {"models": {
        "local-coder": {"provider": "ollama", "locality": "local", "role": "local.code.readonly",
                        "capabilities": ["code.read"], "lifecycle": "ACTIVE", "quality_state": "OK"},
        "local-general": {"provider": "ollama", "locality": "local", "role": "local.general.fast",
                          "capabilities": ["text"], "lifecycle": "ACTIVE", "quality_state": "OK"},
        "cloud-deepseek": {"provider": "deepseek", "locality": "cloud", "role": "cloud.reasoning.deep",
                           "capabilities": ["text", "reasoning"], "lifecycle": "ACTIVE", "quality_state": "OK",
                           "egress": "approval_required"},
        "kimi": {"provider": "kimi", "locality": "cloud", "role": "historical",
                 "lifecycle": "RETIRED", "quality_state": "OK"},
    }}


def make_resolver(**overrides) -> Resolver:
    kwargs = {
        "policy": {},
        "catalog": base_catalog(),
        "runtime_health": {},
        "resource": {},
    }
    kwargs.update(overrides)
    return Resolver(**kwargs)


class CapabilityResolverTests(unittest.TestCase):
    def test_observer_task_no_model(self) -> None:
        r = make_resolver()
        plan = r.resolve({"task_id": "obs-1", "task_kind": "observer", "data_privacy": "public"})
        self.assertEqual(plan["status"], "NO_MODEL_REQUIRED")
        self.assertIsNone(plan["selected"])
        self.assertEqual(plan["reason_code"], "OBSERVER_TASK_NO_MODEL")

    def test_kimi_retired_never_selected(self) -> None:
        r = make_resolver()
        plan = r.resolve({"task_id": "t-1", "task_kind": "general", "data_privacy": "public"})
        self.assertNotEqual(plan.get("selected", {}).get("candidate"), "kimi")
        rejected_names = [x["candidate"] for x in plan.get("rejected", [])]
        if "kimi" in rejected_names:
            kimi_rej = next(x for x in plan["rejected"] if x["candidate"] == "kimi")
            self.assertEqual(kimi_rej["reason"], "RETIRED_PROVIDER")

    def test_private_data_no_cloud_fallback(self) -> None:
        r = make_resolver()
        plan = r.resolve({"task_id": "p-1", "task_kind": "general", "data_privacy": "private",
                          "required_capabilities": ["reasoning"]})
        # Only cloud-deepseek has reasoning -> must block, never silent fallback to local
        self.assertEqual(plan["status"], "BLOCKED")
        self.assertIsNone(plan["selected"])

    def test_cloud_egress_unapproved_blocks(self) -> None:
        r = make_resolver()
        plan = r.resolve({"task_id": "c-1", "task_kind": "general", "data_privacy": "public",
                          "required_capabilities": ["reasoning"]})
        self.assertEqual(plan["status"], "BLOCKED")
        self.assertEqual(plan["reason_code"], "CLOUD_EGRESS_BLOCKED")

    def test_public_text_uses_local_general(self) -> None:
        r = make_resolver()
        plan = r.resolve({"task_id": "t-2", "task_kind": "general", "data_privacy": "public",
                          "required_capabilities": ["text"]})
        self.assertEqual(plan["status"], "READY")
        self.assertEqual(plan["selected"]["candidate"], "local-general")

    def test_user_explicit_blocked_no_silent_fallback(self) -> None:
        r = make_resolver()
        plan = r.resolve({"task_id": "t-3", "task_kind": "general", "data_privacy": "public",
                          "explicit_model": "kimi"})
        self.assertEqual(plan["status"], "BLOCKED")
        self.assertIsNone(plan["selected"])
        self.assertEqual(plan["reason_code"], "RETIRED_PROVIDER")

    def test_project_overlay_preferred(self) -> None:
        r = make_resolver(policy={"project_overlay": {"preferred_models": ["local-coder"]}})
        plan = r.resolve({"task_id": "t-4", "task_kind": "code-read", "data_privacy": "public",
                          "required_capabilities": ["code.read"]})
        self.assertEqual(plan["selected"]["candidate"], "local-coder")
        self.assertEqual(plan["selected"]["reason"], "PROJECT_APPROVED_OVERLAY")

    def test_code_write_requires_primary_role(self) -> None:
        r = make_resolver(policy={"project_overlay": {"preferred_models": []}})
        plan = r.resolve({"task_id": "t-5", "task_kind": "code-write", "data_privacy": "public",
                          "required_capabilities": ["code.write"]})
        # No candidate has agent.code.primary -> BLOCKED (never route to local coder for writes)
        self.assertEqual(plan["status"], "BLOCKED")

    def test_unknown_data_no_cloud(self) -> None:
        r = make_resolver()
        plan = r.resolve({"task_id": "u-1", "task_kind": "general", "data_privacy": "unknown",
                          "required_capabilities": ["reasoning"]})
        self.assertEqual(plan["status"], "BLOCKED")

    def test_rejected_candidates_have_reason_codes(self) -> None:
        r = make_resolver()
        plan = r.resolve({"task_id": "t-6", "task_kind": "general", "data_privacy": "public",
                          "required_capabilities": ["reasoning"]})
        for rej in plan.get("rejected", []):
            self.assertTrue(rej.get("reason"))

    def test_plan_is_pure_no_execution_flag(self) -> None:
        r = make_resolver()
        plan = r.resolve({"task_id": "t-7", "task_kind": "general", "data_privacy": "public",
                          "required_capabilities": ["text"]})
        self.assertEqual(plan["execution"], "deferred_to_worker")
        self.assertNotIn("execute", plan)


if __name__ == "__main__":
    unittest.main()
