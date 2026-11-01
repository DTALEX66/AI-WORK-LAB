"""NF-11-SYNC: thin deployment, existing-module reuse and exit paths.

Proves the acceptance rows for AT-29 / AT-30 / AT-40 on the self-executable
slice (a real install / global asset change stays deployment-authorization-
gated and BLOCKED):
  * adding a project adds ONLY config + local state — no new core-source copy,
    daemon or scheduler; a binding that introduces one is refused;
  * none of the four task-core stacks is layered on;
  * at least one component is GENUINELY reused (call site + tests +
    substitution point handed over); a candidate-only registration is NOT an
    adoption;
  * the exit paths (pause / revoke / rollback / remove-asset) do not affect
    native tasks and PRESERVE un-returned records (pause is not a history
    delete); with the enhancement off the native software still runs.

Pure and deterministic: no install, no launch, no global asset change.
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

import thin_deployment as td  # noqa: E402


def _thin_binding(pid: str) -> td.ProjectBinding:
    return td.ProjectBinding(
        project_id=pid, config_path=f".project/governance/{pid}.json",
        local_state_root=f".project-local/{pid}/")


class TestThinDeployment(unittest.TestCase):
    def test_adding_a_project_is_config_plus_local_state_only(self):
        dep = td.ThinDeployment()
        res = dep.add_project(_thin_binding("new-proj"))
        self.assertTrue(res["accepted"])
        self.assertTrue(res["thin"])
        self.assertEqual(res["added"], ["config", "local_state"])
        self.assertEqual(dep.project_count(), 1)

    def test_a_binding_with_new_core_is_refused(self):
        dep = td.ThinDeployment()
        fat = td.ProjectBinding(
            project_id="fat", config_path="x", local_state_root="y",
            extra_daemons=1)
        res = dep.add_project(fat)
        self.assertFalse(res["accepted"])
        self.assertEqual(dep.project_count(), 0)

    def test_a_binding_with_resident_llm_polling_is_refused(self):
        dep = td.ThinDeployment()
        fat = td.ProjectBinding(project_id="poller", config_path="x",
                                local_state_root="y", extra_llm_pollers=1)
        self.assertFalse(dep.add_project(fat)["accepted"])

    def test_no_forbidden_task_core_is_layed_on(self):
        dep = td.ThinDeployment()
        for core in ("n8n", "linear", "vibe_kanban", "symphony"):
            res = dep.add_task_core(core)
            self.assertFalse(res["added"])
        self.assertEqual(dep._task_cores, [])

    def test_all_projects_stay_thin(self):
        dep = td.ThinDeployment()
        dep.add_project(_thin_binding("p-a"))
        dep.add_project(_thin_binding("p-b"))
        self.assertTrue(dep.thin_all())


class TestReuseIsNotRegistration(unittest.TestCase):
    def test_a_real_reuse_has_call_site_tests_and_substitution(self):
        ledger = td.ReuseLedger()
        ledger.adopt(td.ReusedComponent(
            name="task_ledger", call_site="services/orchestration/worker.py:120",
            tests=["tests/test_task_ledger.py"],
            substitution_point="worker.py:use ledger backend"))
        self.assertTrue(ledger.has_real_reuse())
        self.assertIn("task_ledger", ledger.real_adoptions())

    def test_a_candidate_registration_is_not_an_adoption(self):
        ledger = td.ReuseLedger()
        ledger.register_candidate("some-future-adapter")
        self.assertFalse(ledger.has_real_reuse())
        self.assertIn("some-future-adapter", ledger.candidates_only())
        self.assertNotIn("some-future-adapter", ledger.real_adoptions())


class TestExitPaths(unittest.TestCase):
    def test_pause_preserves_unreturned_and_does_not_delete_history(self):
        ep = td.ExitPaths()
        ep.record_unreturned({"task": "t-1", "receipt": "r-1"})
        ep.record_unreturned({"task": "t-2", "receipt": "r-2"})
        res = ep.pause_sync("proj-A")
        self.assertTrue(res["paused"])
        self.assertEqual(res["unreturned_preserved"], 2)
        self.assertFalse(res["history_deleted"])
        self.assertFalse(res["native_tasks_affected"])

    def test_revoke_one_project_does_not_touch_others_or_native(self):
        ep = td.ExitPaths()
        res = ep.revoke_project_binding("proj-A")
        self.assertFalse(res["other_projects_affected"])
        self.assertFalse(res["native_tasks_affected"])

    def test_rollback_preserves_unreturned(self):
        ep = td.ExitPaths()
        ep.record_unreturned({"task": "t-9"})
        res = ep.rollback_adapter_version("hermes", "0.20.4")
        self.assertTrue(res["rolled_back"])
        self.assertEqual(res["unreturned_preserved"], 1)
        self.assertFalse(res["native_tasks_affected"])

    def test_remove_managed_asset_preserves_unreturned_not_native(self):
        ep = td.ExitPaths()
        ep.record_unreturned({"task": "t-3"})
        res = ep.remove_managed_asset("asset-x")
        self.assertTrue(res["removed"])
        self.assertEqual(res["unreturned_preserved"], 1)
        self.assertFalse(res["native_tasks_affected"])

    def test_with_enhancement_off_native_software_runs_standalone(self):
        ep = td.ExitPaths()
        res = ep.native_software_still_works()
        self.assertTrue(res["native_independent"])
        self.assertIn("standalone", res["note"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
