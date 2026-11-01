"""W10 (2026-10-17): the run-summary artifact, and the rule that made it necessary.

Two things are being pinned here, and they are different.
  * the local route -- `scripts/ci/ci_run_summary.py` is invoked by CI, and a check that exists only in CI is
    a rule a writer cannot see (`verify_ci_check_reachability.py` says so in as many words);
  * the rule itself -- **an absent input must never be rendered as success**. The plan named that failure
    mode explicitly ("缺JSON不能默认为通过"), and it is the whole reason the summary carries an `incomplete`
    list instead of relying on a reader to notice a missing key.
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "ci" / "ci_run_summary.py"
# project_temp lives with the workflow scripts, not with the CI scripts: it is the bounded temp root every
# module uses, and importing it from the wrong directory is what the first version of this test did.
sys.path.insert(0, str(ROOT / "packages" / "client-neutral-core" / "scripts"))

import project_temp  # noqa: E402


def load_module():
    spec = importlib.util.spec_from_file_location("ci_run_summary", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class RunSummaryTests(unittest.TestCase):
    def _isolate(self, module):
        """Point the module at a temp CI dir so a real `.project-local/runs/ci/` never leaks into a verdict."""
        tmp = project_temp.fixture_dir(prefix="wl-ci-summary-")
        module.CI_DIR = tmp
        module.PLAN_FILE = tmp / "plan.json"
        module.GATE_STAGES_FILE = tmp / "gate-stages.json"
        return tmp

    def test_absent_inputs_become_missing_never_success(self) -> None:
        module = load_module()
        tmp = self._isolate(module)
        try:
            summary = module.build_summary("probe", [("gate", "failure")])
            self.assertEqual({"status": "MISSING"}, summary["plan"])
            self.assertEqual({"status": "MISSING"}, summary["gates"])
            self.assertEqual(2, len(summary["incomplete"]),
                             "both absent inputs must be declared, not implied by a missing key")
            self.assertIn("plan.json", summary["incomplete"][0])
        finally:
            project_temp.force_release(tmp)

    def test_present_inputs_are_sliced_to_the_whitelist(self) -> None:
        module = load_module()
        tmp = self._isolate(module)
        try:
            module.PLAN_FILE.write_text(json.dumps({
                "plan_id": "p-1", "risk": "critical", "required_gates": ["workflow"],
                # Not on the whitelist: a field nobody named must not reach the artifact, so a future
                # addition to the plan cannot silently widen what the artifact publishes.
                "unlisted_field": "should not appear",
            }), encoding="utf-8")
            module.GATE_STAGES_FILE.write_text(json.dumps({
                "schemaVersion": "work-lab/gate-stages/v1", "exit": 1, "failed_gate": "governance",
                "stages": [{"gate": "governance", "exit": 1, "seconds": 124.4}],
                "unlisted_field": "should not appear",
            }), encoding="utf-8")
            summary = module.build_summary("probe", [])
            self.assertEqual([], summary["incomplete"])
            self.assertEqual("critical", summary["plan"]["risk"])
            self.assertEqual("governance", summary["gates"]["failed_gate"])
            self.assertNotIn("unlisted_field", summary["plan"])
            self.assertNotIn("unlisted_field", summary["gates"])
            self.assertEqual("work-lab/ci-run-summary/v1", summary["schemaVersion"])
        finally:
            project_temp.force_release(tmp)

    def test_main_writes_the_file_and_reports_incompleteness(self) -> None:
        module = load_module()
        tmp = self._isolate(module)
        try:
            out = tmp / "ci-summary-probe.json"
            argv = sys.argv
            sys.argv = ["ci_run_summary.py", "--job", "probe", "--step", "gate=success", "--out", str(out)]
            try:
                self.assertEqual(0, module.main())
            finally:
                sys.argv = argv
            written = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual([{"name": "gate", "status": "success"}], written["steps"])
            self.assertEqual("probe", written["run"]["job"])
            self.assertEqual(2, len(written["incomplete"]))
        finally:
            project_temp.force_release(tmp)

    def test_a_malformed_step_is_refused_by_name(self) -> None:
        module = load_module()
        tmp = self._isolate(module)
        try:
            argv = sys.argv
            sys.argv = ["ci_run_summary.py", "--job", "probe", "--step", "no-equals-sign"]
            try:
                self.assertEqual(2, module.main())
            finally:
                sys.argv = argv
        finally:
            project_temp.force_release(tmp)


class PlanHandoffTests(unittest.TestCase):
    """The plan is produced in a different job on a different runner, so its file cannot reach the summary.

    Measured on the first CI run with artifacts (2026-10-16, run 38937961649): the observer job reported
    `plan: MISSING` while its plan was fine. An `incomplete` list that is always non-empty is worse than no
    list, because it teaches readers to skip it -- so the workflow hands the plan over explicitly and this
    class pins both halves: the hand-off wins, and a broken hand-off is NAMED rather than silently ignored.
    """

    def _isolate(self, module):
        tmp = project_temp.fixture_dir(prefix="wl-ci-summary-handoff-")
        module.CI_DIR = tmp
        module.PLAN_FILE = tmp / "plan.json"
        module.GATE_STAGES_FILE = tmp / "gate-stages.json"
        return tmp

    def test_the_handoff_wins_over_a_missing_file(self) -> None:
        module = load_module()
        tmp = self._isolate(module)
        previous = os.environ.get("PLAN_JSON")
        try:
            os.environ["PLAN_JSON"] = json.dumps({"plan_id": "handoff", "risk": "medium"})
            summary = module.build_summary("probe", [])
            self.assertEqual("handoff", summary["plan"]["plan_id"])
            self.assertEqual([], [entry for entry in summary["incomplete"] if "plan" in entry])
        finally:
            project_temp.force_release(tmp)
            if previous is None:
                os.environ.pop("PLAN_JSON", None)
            else:
                os.environ["PLAN_JSON"] = previous

    def test_a_malformed_handoff_is_named_not_ignored(self) -> None:
        module = load_module()
        tmp = self._isolate(module)
        previous = os.environ.get("PLAN_JSON")
        try:
            os.environ["PLAN_JSON"] = "{not json"
            summary = module.build_summary("probe", [])
            self.assertEqual({"status": "MISSING"}, summary["plan"])
            self.assertTrue(any("PLAN_JSON" in entry for entry in summary["incomplete"]),
                            "a hand-off that did not parse must be named, not silently dropped")
        finally:
            project_temp.force_release(tmp)
            if previous is None:
                os.environ.pop("PLAN_JSON", None)
            else:
                os.environ["PLAN_JSON"] = previous


if __name__ == "__main__":
    unittest.main(verbosity=2)
