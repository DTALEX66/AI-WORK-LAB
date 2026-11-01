"""Gate: local `--changed` must consult the ONE canonical impact planner and can only widen.

P2-04 asked for a single changed-path truth instead of a second classifier. The two vocabularies
(profile CI jobs vs this runner's local gates) are not merged here — that is a delivery-structure
decision — so the wiring gives the canonical planner the two calls the local table cannot honestly make
alone: is this change classified at all, and is it critical. Everything the planner cannot answer is
treated as unclassified, which runs the full suite. A helper that fails open would be the exact defect
this file pins.
"""
from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RUNNER = ROOT / "services/orchestration/run_quality_gate.py"


def load_runner():
    spec = importlib.util.spec_from_file_location("run_quality_gate", RUNNER)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class CanonicalWiringTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.m = load_runner()

    def test_a_declared_supporting_surface_is_classified_as_non_critical(self) -> None:
        plan, note = self.m.canonical_impact_plan(["services/control/control_service.py"])
        self.assertEqual(note, "ok", note)
        assert plan is not None
        self.assertNotEqual(plan["risk"], "critical")
        self.assertIn("workflow", plan["required_gates"])

    def test_an_undeclared_surface_is_reported_by_the_planner_as_critical(self) -> None:
        plan, note = self.m.canonical_impact_plan(["apps/control-surface/index.html"])
        self.assertEqual(note, "ok", note)
        assert plan is not None
        self.assertEqual(plan["risk"], "critical")
        self.assertIn("changed_paths", plan)

    def test_an_unreadable_profile_returns_none_rather_than_a_pass(self) -> None:
        original = self.m.PROJECT_PROFILE
        self.m.PROJECT_PROFILE = ROOT / ".project/governance/does-not-exist.yaml"
        try:
            plan, note = self.m.canonical_impact_plan(["services/control/x.py"])
        finally:
            self.m.PROJECT_PROFILE = original
        self.assertIsNone(plan)
        self.assertTrue(note.startswith("profile unreadable"), note)

    def test_the_planner_and_the_local_table_never_disagree_about_the_whole_suite(self) -> None:
        """For a critical change the local runner must select exactly VERIFY_ORDER."""
        selected = self.m.select_gates_for_changed(["apps/control-surface/index.html"])
        self.assertEqual(selected, tuple(self.m.VERIFY_ORDER))

    def test_plan_carries_the_identity_the_report_needs(self) -> None:
        plan, _ = self.m.canonical_impact_plan(["config/config-ownership.json"])
        assert plan is not None
        self.assertEqual(plan["plan_id"], "local-changed")
        self.assertTrue(plan["source_identity"]["commit"]["oid"])
        self.assertTrue(plan["source_identity"]["tree"]["oid"])
        self.assertEqual(len(plan["plan_digest"]["value"]), 64)


if __name__ == "__main__":
    unittest.main(verbosity=2)
