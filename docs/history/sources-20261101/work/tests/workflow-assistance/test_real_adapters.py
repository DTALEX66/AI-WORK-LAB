"""Contract tests for four real adapters (WL3-700)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts/workflow"))
from real_adapters import ADAPTERS, conformance_report


class RealAdaptersTests(unittest.TestCase):
    def test_four_adapters_registered(self) -> None:
        self.assertEqual(set(ADAPTERS), {"hermes", "codex", "cc-switch", "github"})

    def test_all_adapters_pass_real_conformance(self) -> None:
        report = conformance_report()
        self.assertTrue(report["passed"])
        self.assertFalse(report["fake_adapter_used"])
        for adapter_id, item in report["adapters"].items():
            self.assertTrue(item["passed"], f"{adapter_id} failed")
            self.assertTrue(item["real_impl"])

    def test_detect_is_real_and_never_fabricates_installed(self) -> None:
        for adapter_id, adapter in ADAPTERS.items():
            detected = adapter.detect({})
            self.assertIn(detected["state"], {
                "UNIQUE", "ALIAS_DUPLICATE", "STALE_SHORTCUT", "CONFIG_SPLIT",
                "VERSION_COLLISION", "DUAL_INSTALLATION", "PROFILE_SPLIT",
                "IDENTITY_AMBIGUOUS", "UNAVAILABLE",
            })
            if detected["state"] == "UNAVAILABLE":
                self.assertFalse(detected["installed"])

    def test_unimplemented_mutations_are_unsupported_even_after_approval(self) -> None:
        for adapter in ADAPTERS.values():
            plan = adapter.plan({"task_id": "t", "action": "write"})
            approved = {**plan, "approval": {**plan["approval"], "status": "APPROVED"}}
            self.assertEqual(adapter.apply(plan)["status"], "UNSUPPORTED")
            self.assertEqual(adapter.apply(approved)["status"], "UNSUPPORTED")
            self.assertEqual(adapter.rollback(approved)["status"], "UNSUPPORTED")
            self.assertNotIn("apply", adapter.capabilities()["operations"])

    def test_invoke_is_unsupported_not_faked(self) -> None:
        for adapter in ADAPTERS.values():
            result = adapter.invoke({"task_id": "t"})
            self.assertEqual(result["status"], "UNSUPPORTED")

    def test_config_ownership_is_declared(self) -> None:
        for adapter in ADAPTERS.values():
            ownership = adapter.config_ownership()
            self.assertEqual(ownership["status"], "OWNERSHIP_READ")
            self.assertGreaterEqual(ownership["declared_fields"], 0)


if __name__ == "__main__":
    unittest.main()
