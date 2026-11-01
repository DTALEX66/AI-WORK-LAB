from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "packages/client-neutral-core/scripts/adapter_conformance.py"


def load_module():
    spec = importlib.util.spec_from_file_location("adapter_conformance", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class AdapterConformanceTests(unittest.TestCase):
    def test_fake_adapter_passes_all_seven_operations(self) -> None:
        module = load_module()
        result = module.run_conformance(module.FakeAdapter("fake-client"))
        self.assertTrue(result["passed"])
        self.assertEqual(result["operations"], ["detect", "capabilities", "plan", "apply", "invoke", "observe", "rollback"])
        self.assertEqual(result["evidence_state"], "ISOLATED_PASS")

    def test_apply_rejects_unapproved_action_plan(self) -> None:
        module = load_module()
        adapter = module.FakeAdapter("fake-client")
        plan = adapter.plan({"task_id": "task-a", "action": "write"})
        with self.assertRaisesRegex(PermissionError, "approval"):
            adapter.apply(plan)

    def test_conformance_rejects_adapter_without_required_operation(self) -> None:
        module = load_module()

        class Incomplete(module.FakeAdapter):
            observe = None

        result = module.run_conformance(Incomplete("incomplete"))
        self.assertFalse(result["passed"])
        self.assertIn("observe", result["missing_operations"])

    def test_conformance_rejects_success_for_unadvertised_apply(self) -> None:
        module = load_module()

        class Liar(module.FakeAdapter):
            def capabilities(self):
                return {"status": "CAPABILITIES_READ", "operations": ["detect", "capabilities", "plan", "observe"]}

        result = module.run_conformance(Liar("liar"))
        self.assertFalse(result["passed"])


if __name__ == "__main__":
    unittest.main()
