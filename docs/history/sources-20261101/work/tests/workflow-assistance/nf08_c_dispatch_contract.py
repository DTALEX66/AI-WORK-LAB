"""NF-08-C: dispatch-to-execution contract.

Proves the acceptance rows for AT-11 / AT-18 / AT-21 on the self-executable
slice (design + code + synthetic tests; real native launch / model calls stay
authorization-gated and BLOCKED):
  * the dispatch freezes task/revision/baseline/executor/authorization and
    records the real instruction source (never a global --last);
  * a dirty local worktree is kept as-is, never auto pull/reset;
  * a launch records a real run/session id; a fake executor is contract
    evidence only;
  * risk ordering runs deterministic tasks before agent tasks, and holds agent
    tasks without a cost grant instead of silently running or dropping them;
  * switching executor hands over ONLY the remaining work after the old
    runtime is COMPLETED / PAUSED, never the whole package again;
  * a startup failure is attributed to exactly one layer and never blocks
    other projects;
  * exit code 0 / model DONE alone is NOT acceptance.
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

import dispatch_contract as dc  # noqa: E402


class TestFreeze(unittest.TestCase):
    def test_freeze_records_real_instruction_source_not_last(self):
        f = dc.build_freeze(
            task_id="t-1", task_revision=2, baseline="0" * 40,
            executor="hermes-native", authorization_ref="grant-7",
            workspace="D:/work/t-1", instruction_source="artifacts/t-1/v2:sha1")
        self.assertEqual(f.task_revision, 2)
        self.assertEqual(f.executor, "hermes-native")
        self.assertTrue(f.intent_digest)
        # a missing instruction source is refused — --last is not acceptable
        with self.assertRaises(ValueError):
            dc.build_freeze(
                task_id="t-1", task_revision=2, baseline="0" * 40,
                executor="hermes-native", authorization_ref="grant-7",
                workspace="D:/work/t-1", instruction_source="")

    def test_dirty_worktree_is_not_auto_cleaned(self):
        res = dc.workspace_clean_check(["a.py", "b.md"])
        self.assertFalse(res["clean"])
        self.assertFalse(res["auto_cleaned"])
        self.assertEqual(res["dirty_files"], ["a.py", "b.md"])
        self.assertTrue(dc.workspace_clean_check([])["clean"])


class TestLaunchRecord(unittest.TestCase):
    def test_launch_requires_a_real_run_session_id(self):
        lr = dc.LaunchRecord()
        f = dc.build_freeze(
            task_id="t-1", task_revision=1, baseline="0" * 40,
            executor="hermes-native", authorization_ref="g",
            workspace="w", instruction_source="src")
        # an empty run/session id is refused
        with self.assertRaises(ValueError):
            lr.record(f, run_session_id="", instruction_source="src")
        rec = lr.record(f, run_session_id="run-abc", instruction_source="src")
        self.assertEqual(rec["run_session_id"], "run-abc")
        self.assertEqual(lr.latest_for(f)["run_session_id"], "run-abc")

    def test_fake_executor_is_contract_evidence_only(self):
        lr = dc.LaunchRecord()
        f = dc.build_freeze(
            task_id="t-2", task_revision=1, baseline="0" * 40,
            executor="mock", authorization_ref="g",
            workspace="w", instruction_source="src")
        rec = lr.record(f, run_session_id="run-mock", instruction_source="src",
                        fake_executor=True)
        self.assertTrue(rec["contract_evidence_only"])
        self.assertTrue(rec["fake_executor"])


class TestRiskOrdering(unittest.TestCase):
    def test_deterministic_before_agent(self):
        ro = dc.RiskOrdering()
        plan = ro.plan({"det": "deterministic", "ag": "agent"}, cost_grant=True)
        order = [e["task_id"] for e in plan]
        self.assertEqual(order, ["det", "ag"])
        self.assertTrue(all(e["state"] == "SCHEDULED" for e in plan))

    def test_agent_without_cost_grant_is_held_not_run(self):
        ro = dc.RiskOrdering()
        plan = ro.plan({"det": "deterministic", "ag": "agent"}, cost_grant=False)
        by_id = {e["task_id"]: e for e in plan}
        self.assertEqual(by_id["det"]["state"], "SCHEDULED")
        self.assertEqual(by_id["ag"]["state"], "HELD_NO_COST_GRANT")


class TestExecutorHandoff(unittest.TestCase):
    def test_handoff_only_after_old_runtime_safe(self):
        prior = {"remaining_work": [
            {"step": "a", "done": True}, {"step": "b", "done": False}]}
        # an old runtime that is RUNNING is not safe to hand off
        blocked = dc.handoff_remaining_work(prior, old_state="RUNNING")
        self.assertFalse(blocked["handed_over"])
        self.assertFalse(blocked["whole_package_again"])
        # once PAUSED, only the remaining work is handed over
        ok = dc.handoff_remaining_work(prior, old_state="PAUSED")
        self.assertTrue(ok["handed_over"])
        self.assertEqual(ok["remaining_work"], [{"step": "b", "done": False}])
        self.assertFalse(ok["whole_package_again"])


class TestFailureAttribution(unittest.TestCase):
    def test_failure_is_attributed_to_exactly_one_layer(self):
        res = dc.startup_failure_attribution({"layer": "model", "detail": "quota"})
        self.assertEqual(res["layer"], "model")
        self.assertTrue(res["other_projects_continue"])
        self.assertFalse(res["blocks_other_projects"])

    def test_unattributed_failure_is_refused(self):
        with self.assertRaises(ValueError):
            dc.startup_failure_attribution({"layer": "mystery"})
        with self.assertRaises(ValueError):
            dc.startup_failure_attribution({})


class TestAcceptanceNotCommandZero(unittest.TestCase):
    def test_exit_code_zero_alone_is_not_acceptance(self):
        res = dc.acceptance_is_not_command_zero({"exit_code": 0})
        self.assertFalse(res["accepted"])

    def test_model_done_alone_is_not_acceptance(self):
        res = dc.acceptance_is_not_command_zero({"model_said_done": True})
        self.assertFalse(res["accepted"])

    def test_a_verified_artifact_is_acceptance(self):
        res = dc.acceptance_is_not_command_zero(
            {"exit_code": 0, "artifact_verified": True})
        self.assertTrue(res["accepted"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
