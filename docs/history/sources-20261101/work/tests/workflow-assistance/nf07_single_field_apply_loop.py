"""NF-07 single-field controlled apply/restore closed-loop tests (synthetic)."""
from __future__ import annotations

import importlib.util
import os
import sys
import tempfile
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
MOD = os.path.join(ROOT, "services", "policy", "single_field_apply_loop.py")


def _load():
    spec = importlib.util.spec_from_file_location("sfal", MOD)
    m = importlib.util.module_from_spec(spec)
    sys.modules["sfal"] = m
    spec.loader.exec_module(m)
    return m


class SingleFieldClosedLoopTests(unittest.TestCase):
    def setUp(self):
        self.mod = _load()
        self._tmp = tempfile.TemporaryDirectory()
        self.loop = self.mod.SingleFieldApplyLoop(self._tmp.name, "op-a1")

    def tearDown(self):
        self._tmp.cleanup()

    def test_previous_apply_readback_restore(self):
        plan = self.loop.plan({"path": "display.language", "old_value": "en", "new_value": "zh", "adapter": "hermes"})
        self.assertEqual(plan["status"], "PLANNED")
        self.assertEqual(plan["previous_value"], "en")
        out = self.loop.apply(plan)
        self.assertEqual(out["status"], "APPLIED")
        self.assertEqual(out["readback"]["status"], "PASS")
        self.assertTrue(out["readback"]["file_value"] == "zh")
        self.loop.restore("display.language", "en")
        self.assertEqual(self.loop.readback("display.language", "en")["status"], "PASS")

    def test_idempotent_no_duplicate_write(self):
        plan = self.loop.plan({"path": "display.language", "old_value": "en", "new_value": "zh"})
        self.assertEqual(self.loop.apply(plan)["status"], "APPLIED")
        self.assertTrue(self.loop.apply(plan)["idempotent"])

    def test_concurrent_change_refuses_blind_restore(self):
        plan = self.loop.plan({"path": "display.language", "old_value": "en", "new_value": "zh"})
        self.loop.apply(plan)  # records last_written = "zh"
        self.loop._write_field("display.language", "de")  # concurrent user change
        with self.assertRaises(self.mod.FieldConflictRefused):
            self.loop.restore("display.language", "en")
        self.assertEqual(self.loop.readback("display.language", "de")["status"], "PASS")

    def test_unknown_field_isolated(self):
        co = {"fields": [{"path": "display.language", "layer": "USER_OVERLAY", "mode": "MANAGE", "adapter": "hermes"}]}
        coord = _load_coordinator()
        p = coord.three_way_compare(co, previous_upstream={}, new_upstream={}, user_overlay={"sessions.custom": 1}, identity_apply_allowed=False)
        self.assertEqual(p["write_set"], [])
        self.assertIn("sessions.custom", p["quarantined_fields"])
        self.assertFalse(p["apply_allowed"])


def _load_coordinator():
    c = os.path.join(ROOT, "services", "policy", "config_coordinator.py")
    spec = importlib.util.spec_from_file_location("cfg_coord", c)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


if __name__ == "__main__":
    unittest.main(verbosity=2)
