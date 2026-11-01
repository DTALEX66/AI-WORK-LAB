"""NF-14-SYNC: layered delivery, the universal goal must be genuinely signed
off.

Proves the acceptance rows on the self-executable slice (a real publish / merge
stays authorization-gated and BLOCKED):
  * the universal label is granted ONLY when every check is met by REAL
    evidence AND a real external project + a second executor exist;
  * a missing real external project OR a missing second executor yields a stage
    completion, never a full completion;
  * simulation / no-evidence never masks a required REAL check;
  * an uninstalled software is not given a fake LIVE PASS;
  * a condition-study / unrelated-maintenance gap is preserved but does not
    push the delivery into an unbounded re-audit loop;
  * intermediate results keep distinct names from the final universal goal.

Pure and deterministic: no publish, no merge, no deploy.
"""
from __future__ import annotations

import os
import sys
import unittest

_PKG = os.path.abspath(os.path.join(
    os.path.abspath(os.path.dirname(__file__)), "..", "..",
    "packages", "client-neutral-core", "scripts"))
if _PKG not in sys.path:
    sys.path.insert(0, _PKG)

import universal_signoff as us  # noqa: E402


def _full(signoff: us.UniversalDeliverySignoff) -> None:
    """Fill every check with REAL evidence + a real external project + a
    second executor."""
    for chk in us.UNIVERSAL_CHECKS:
        signoff.record_check(chk, "REAL", handle="run/real-xyz")
    # a real external project (not work-lab) with real execution evidence
    signoff.add_cell(us.MatrixCell("alpha-project", "codex", "task_execution",
                                    "cloud", level="REAL", handle="run/c1"))
    # a second executor (non-hermes) executing for real
    signoff.add_cell(us.MatrixCell("work-lab", "codex", "execute", "local",
                                    level="REAL", handle="run/e1"))


class TestUniversalLabel(unittest.TestCase):
    def test_full_real_matrix_grants_universal_label(self):
        s = us.UniversalDeliverySignoff()
        _full(s)
        res = s.sign_off()
        self.assertEqual(res["label"], us.FULL_LABEL)
        self.assertTrue(res["full_completion_claimed"])
        self.assertFalse(res["is_stage_only"])
        self.assertTrue(res["preconditions_ok"])

    def test_missing_real_external_project_is_stage_only(self):
        s = us.UniversalDeliverySignoff()
        _full(s)
        # clear the external-project cell: remove all non-work-lab real cells
        s2 = us.UniversalDeliverySignoff()
        for chk in us.UNIVERSAL_CHECKS:
            s2.record_check(chk, "REAL", handle="run/real-xyz")
        # only work-lab execution evidence, no external project
        s2.add_cell(us.MatrixCell("work-lab", "hermes", "execute", "local",
                                   level="REAL", handle="run/e0"))
        res = s2.sign_off()
        self.assertEqual(res["label"], us.STAGE_LABEL)
        self.assertFalse(res["full_completion_claimed"])
        self.assertTrue(res["is_stage_only"])
        self.assertFalse(res["real_external_project"])

    def test_missing_second_executor_is_stage_only(self):
        s = us.UniversalDeliverySignoff()
        # real external project but NO second executor executing
        for chk in us.UNIVERSAL_CHECKS:
            s.record_check(chk, "REAL", handle="run/real-xyz")
        s.add_cell(us.MatrixCell("alpha-project", "hermes", "task_execution",
                                   "cloud", level="REAL", handle="run/c1"))
        res = s.sign_off()
        self.assertEqual(res["label"], us.STAGE_LABEL)
        self.assertTrue(res["is_stage_only"])
        self.assertFalse(res["second_executor"])

    def test_simulation_does_not_mask_a_required_real_check(self):
        s = us.UniversalDeliverySignoff()
        # every check REAL except receipt_readback which only has SIMULATED
        for chk in us.UNIVERSAL_CHECKS:
            lvl = "SIMULATED" if chk == "receipt_readback" else "REAL"
            s.record_check(chk, lvl, handle="x")
        s.add_cell(us.MatrixCell("alpha-project", "codex", "task_execution",
                                   "cloud", level="REAL", handle="run/c1"))
        s.add_cell(us.MatrixCell("work-lab", "codex", "execute", "local",
                                   level="REAL", handle="run/e1"))
        res = s.sign_off()
        self.assertNotEqual(res["label"], us.FULL_LABEL)
        self.assertTrue(res["is_stage_only"])
        self.assertIn("receipt_readback", res["unmet_checks"])


class TestLayeredAndLive(unittest.TestCase):
    def test_uninstalled_software_gets_no_fake_live_pass(self):
        s = us.UniversalDeliverySignoff()
        self.assertTrue(s.no_fake_live_pass_for_uninstalled("obsidian", True)["live_pass"])
        self.assertFalse(s.no_fake_live_pass_for_uninstalled("linear", False)["live_pass"])

    def test_intermediate_results_keep_distinct_names(self):
        names = us.UniversalDeliverySignoff().layer_names()
        self.assertNotEqual(names["single_link_result"], names["universal_result"])
        self.assertNotEqual(names["stage_result"], names["universal_result"])

    def test_cond_hold_preserved_but_no_infinite_reaudit(self):
        s = us.UniversalDeliverySignoff()
        s.hold_gap("condition_study", "edge not covered by this round")
        s.hold_gap("unrelated_maintenance", "unrelated housekeeping")
        self.assertTrue(s.no_infinite_reaudit())
        self.assertEqual(len(s._holds), 2)
        # a held gap does not block the in-scope delivery
        for h in s._holds.values():
            self.assertFalse(h["blocks_in_scope_delivery"])

    def test_check_level_only_improves_not_downgrades(self):
        s = us.UniversalDeliverySignoff()
        s.record_check("project_isolation", "REAL", handle="r")
        s.record_check("project_isolation", "SIMULATED")  # attempt downgrade
        self.assertEqual(s._check_level("project_isolation"), "REAL")


if __name__ == "__main__":
    unittest.main(verbosity=2)
