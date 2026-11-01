"""NF-09-SYNC: multi-project task projection + run-evidence visibility.

Proves the acceptance rows for AT-24 / AT-34 / AT-38 on the self-executable
slice (a real Observer UI / live telemetry stays authorization-gated):
  * A and B are viewable independently; a task that ran but has not returned
    is NEVER shown as "all failed" or "cloud received" (it stays
    PENDING_RETURN);
  * a stale snapshot after a client disconnect is marked STALE; an unknown
    value is not back-filled with 0;
  * cost is grouped by task and call source, and subscription usage is not
    inferred into an API billed amount;
  * another project's title / body never leaks through the shared projection;
  * no Observer write capability is added.

Pure and deterministic: no network, no Observer write, no leaked body.
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

import multi_project_projection as mpp  # noqa: E402


def two_projects() -> mpp.ProjectProjection:
    proj = mpp.ProjectProjection()
    # project A: one task that ran but has not returned yet
    proj.add_project(
        "A", tasks=[{"task_id": "a1", "status": "RUNNING",
                     "executed": True, "returned": False}],
        source_software="hermes", target_software="codex",
        material_version="v3", fact_updated_at="2026-09-16T10:00:00Z")
    # project B: an independent project with a received task
    proj.add_project(
        "B", tasks=[{"task_id": "b1", "status": "RECEIVED",
                     "executed": True, "returned": True}],
        source_software="codex", target_software="hermes",
        material_version="v1", fact_updated_at="2026-09-16T09:30:00Z")
    return proj


class TestIndependentProjects(unittest.TestCase):
    def test_a_and_b_are_viewed_independently(self):
        proj = two_projects()
        res = proj.independent_projects(["A", "B"])
        self.assertTrue(res["views"]["A"]["available"])
        self.assertTrue(res["views"]["B"]["available"])
        # a ran-but-not-returned task stays PENDING_RETURN, not all-failed /
        # not cloud-received
        a_task = res["views"]["A"]["tasks"][0]
        self.assertEqual(a_task["status"], "RUNNING")
        self.assertEqual(a_task["stage_states"]["return"], "in_progress")
        self.assertNotIn(a_task["status"], ("FAILED", "RECEIVED"))

    def test_b_not_affected_by_a_problem(self):
        proj = two_projects()
        res = proj.independent_projects(["A", "B"])
        # B's task is RECEIVED (a completed pipeline); A's state does not
        # pollute B's view
        b_task = res["views"]["B"]["tasks"][0]
        self.assertEqual(b_task["status"], "RECEIVED")
        self.assertEqual(b_task["stage_states"]["review"], "done")


class TestHonestValueDisplay(unittest.TestCase):
    def test_unknown_value_not_back_filled_with_zero(self):
        proj = two_projects()
        task = proj._projects["A"]["tasks"]["a1"]
        self.assertIsNone(task.get("token_usage"))
        view = proj.view_project("A")
        # no token_usage -> shown as UNKNOWN, not as 0
        self.assertEqual(view["tasks"][0]["token_usage"], "UNKNOWN")

    def test_actual_zero_shown_as_zero(self):
        proj = two_projects()
        proj._projects["B"]["tasks"]["b1"]["token_usage"] = 0
        view = proj.view_project("B")
        self.assertEqual(view["tasks"][0]["token_usage"], "ZERO")

    def test_stale_snapshot_marked_after_disconnect(self):
        proj = two_projects()
        self.assertEqual(proj.view_project("A")["snapshot_state"], "LIVE")
        proj.set_client_online("A", online=False)
        view = proj.view_project("A")
        self.assertEqual(view["snapshot_state"], "STALE")
        self.assertFalse(view["client_online"])
        # a reconnect clears the stale mark
        proj.set_client_online("A", online=True)
        self.assertEqual(proj.view_project("A")["snapshot_state"], "LIVE")

    def test_update_time_comes_from_fact_not_ui_refresh(self):
        proj = two_projects()
        view = proj.view_project("A")
        self.assertEqual(view["updated_at"], "2026-09-16T10:00:00Z")
        self.assertTrue(view["updated_from_fact"])


class TestCostGrouping(unittest.TestCase):
    def test_cost_grouped_by_task_and_source(self):
        cg = mpp.CostGrouping()
        cg.record("t-1", "hermes", cost="$0.02", token_usage="120")
        cg.record("t-1", "codex", cost=None, token_usage=None)
        group = cg.group("t-1")
        self.assertEqual(group["cost:hermes"], "$0.02")
        # an absent cost is UNKNOWN, never a fabricated 0 / billed amount
        self.assertEqual(group["cost:codex"], "UNKNOWN")
        self.assertEqual(group["tokens:codex"], "UNKNOWN")

    def test_subscription_usage_not_inferred_as_api_billed(self):
        cg = mpp.CostGrouping()
        res = cg.subscription_not_inferred_as_api_billed()
        self.assertFalse(res["treated_as_api_billed"])
        self.assertIn("estimate", res["label"])


class TestNoLeak(unittest.TestCase):
    def test_no_project_title_or_body_leaks(self):
        proj = two_projects()
        self.assertFalse(proj.did_any_task_leak(["A", "B"]))
        # task views carry no title or body at all
        view = proj.view_project("A")
        for t in view["tasks"]:
            self.assertIsNone(t["title"])
            self.assertIsNone(t["body"])


class TestReadOnlyInvariant(unittest.TestCase):
    def test_observer_adds_no_write_capability(self):
        # a projection that does not hold a write is allowed
        self.assertTrue(mpp.read_only_invariant(holds_write=False)["allowed"])
        # one that somehow gained a write is rejected
        self.assertFalse(mpp.read_only_invariant(holds_write=True)["allowed"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
