from __future__ import annotations

import importlib.util
import io
import json
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "integrations/executors/hermes/switch_model.py"
spec = importlib.util.spec_from_file_location("switch_model", SCRIPT)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)


class SwitchModelTests(unittest.TestCase):
    def test_default_is_schema_shaped_plan_only(self) -> None:
        output = io.StringIO()
        with patch.object(sys, "argv", [str(SCRIPT), "deepseek", "--model", "user-model", "--no-verify"]), \
             patch.object(module, "set_config") as setter, redirect_stdout(output):
            self.assertEqual(module.main(), 0)
        setter.assert_not_called()
        rendered = output.getvalue()
        plan = json.loads(rendered[: rendered.index("\nACTION_PLAN_ONLY")])
        self.assertEqual(plan["schema_version"], "workflow/action-plan/v1")
        self.assertEqual(plan["status"], "WAITING_APPROVAL")

    def test_apply_without_approval_is_blocked(self) -> None:
        with patch.object(sys, "argv", [str(SCRIPT), "deepseek", "--model", "user-model", "--no-verify", "--apply"]), \
             patch.object(module, "set_config") as setter:
            self.assertEqual(module.main(), 2)
        setter.assert_not_called()

    def test_apply_and_approved_uses_official_writer(self) -> None:
        with patch.object(sys, "argv", [str(SCRIPT), "deepseek", "--model", "user-model", "--no-verify", "--apply", "--approved"]), \
             patch.object(module, "set_config") as setter:
            self.assertEqual(module.main(), 0)
        setter.assert_called_once()

    def test_absent_field_rollback_uses_official_unset(self) -> None:
        completed = module.subprocess.CompletedProcess([], 0, "")
        with patch.object(module, "run", return_value=completed) as runner:
            self.assertEqual(module._restore_config([("model.base_url", module.MISSING)]), [])
        runner.assert_called_once_with(["hermes", "config", "unset", "model.base_url"], timeout=30)

    def test_status_does_not_guess_fixed_ports(self) -> None:
        source = SCRIPT.read_text(encoding="utf-8")
        self.assertNotIn("127.0.0.1:7890", source)
        self.assertNotIn("127.0.0.1:15721", source)


if __name__ == "__main__":
    unittest.main()
