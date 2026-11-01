"""NF-08-I: multi-environment routing and controlled takeover.

Proves the acceptance rows for AT-15 / AT-16 / AT-35 on the self-executable
slice (a real dual-device takeover stays authorization-gated and BLOCKED):
  * two environments with different local paths resolve the SAME
    project/task/revision identity;
  * after a takeover the old node returning online does NOT re-dispatch the
    task; if the old run state is unconfirmable it is an explicit BLOCK, not a
    silent re-dispatch / double writer;
  * a dual-device takeover declaration requires two REAL-environment handles;
    a simulated environment counts only as a test.

Pure and deterministic: no network, no real node join, no credentials.
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

import environment_takeover as et  # noqa: E402


class TestPathIndependentIdentity(unittest.TestCase):
    def test_same_identity_different_paths_across_environments(self):
        reg = et.EnvironmentBinding()
        # same project/task/revision, different local paths, two environments
        ia = reg.register("pc-a", project_id="work-lab", task_id="t-1",
                          revision=3, local_path="D:/All projects/WORK-LAB")
        ib = reg.register("pc-b", project_id="work-lab", task_id="t-1",
                          revision=3, local_path="C:/Users/ALEX/WORK-LAB")
        cmp = reg.same_across_environments("pc-a", "pc-b")
        self.assertTrue(cmp["same_identity"])
        self.assertTrue(cmp["different_paths"])
        # both resolve to the same identity CORE (path/env-independent hash)
        self.assertEqual(reg.resolve("pc-a")["identity"].split("@", 1)[0],
                         reg.resolve("pc-b")["identity"].split("@", 1)[0])
        # the environment-qualified tag differs (routing), the core does not
        self.assertNotEqual(ia, ib)

    def test_different_revision_is_a_different_identity(self):
        reg = et.EnvironmentBinding()
        reg.register("pc-a", project_id="work-lab", task_id="t-1",
                     revision=3, local_path="D:/x")
        reg.register("pc-b", project_id="work-lab", task_id="t-1",
                     revision=4, local_path="C:/y")
        cmp = reg.same_across_environments("pc-a", "pc-b")
        self.assertFalse(cmp["same_identity"])

    def test_unbound_environment_is_not_guessed(self):
        reg = et.EnvironmentBinding()
        reg.register("pc-a", project_id="work-lab", task_id="t-1",
                     revision=3, local_path="D:/x")
        res = reg.resolve("pc-z")
        self.assertFalse(res["resolved"])


class TestControlledTakeover(unittest.TestCase):
    def test_old_node_return_does_not_re_dispatch_when_other_owner(self):
        co = et.TakeoverCoordinator()
        co.register_node("node-a")
        co.register_node("node-b")
        co.dispatch("t-1", "node-a")
        # node-b takes over dispatch
        co.dispatch("t-1", "node-b")
        # node-a returns online: it must NOT re-dispatch / be a second writer
        res = co.node_returned_online("t-1", "node-a", confirmed_state=True)
        self.assertFalse(res["re_dispatched"])
        self.assertFalse(res["took_over"])
        self.assertEqual(res["state"], "REJOINED_NOT_WRITER")
        self.assertEqual(co.owner("t-1"), "node-b")  # single dispatcher unchanged

    def test_unconfirmed_old_state_is_explicit_block_not_redispatch(self):
        co = et.TakeoverCoordinator()
        co.register_node("node-a")
        co.dispatch("t-1", "node-a")
        res = co.node_returned_online("t-1", "node-a", confirmed_state=False)
        self.assertFalse(res["re_dispatched"])
        self.assertEqual(res["state"], "BLOCKED_UNCONFIRMED")
        self.assertEqual(co.owner("t-1"), "node-a")  # still the only writer, blocked
        node = co._nodes["node-a"]
        self.assertEqual(node.last_known_run_state, "UNKNOWN")

    def test_confirmed_state_may_resume_as_single_writer(self):
        co = et.TakeoverCoordinator()
        co.register_node("node-a")
        co.dispatch("t-1", "node-a")
        res = co.node_returned_online("t-1", "node-a", confirmed_state=True)
        self.assertFalse(res["re_dispatched"])
        self.assertTrue(res["took_over"])
        self.assertEqual(res["state"], "CONFIRMED_RESUME")


class TestDualEnvironmentEvidence(unittest.TestCase):
    def test_dual_takeover_requires_two_real_handles(self):
        ev = et.DualEnvironmentEvidence()
        ev.record("cloud-x", kind="real", handle="cloud-run-1")
        ev.record("local-y", kind="real", handle="local-run-2")
        res = ev.can_declare_dual_takeover("cloud-x", "local-y")
        self.assertTrue(res["can_declare"])

    def test_simulated_environment_is_a_test_not_proof(self):
        ev = et.DualEnvironmentEvidence()
        ev.record("cloud-x", kind="real", handle="cloud-run-1")
        ev.record("local-y", kind="simulated", handle="sim-test-2")
        res = ev.can_declare_dual_takeover("cloud-x", "local-y")
        self.assertFalse(res["can_declare"])
        self.assertIn("simulation", res["note"])

    def test_missing_environment_evidence_cannot_declare(self):
        ev = et.DualEnvironmentEvidence()
        ev.record("cloud-x", kind="real", handle="h1")
        res = ev.can_declare_dual_takeover("cloud-x", "ghost")
        self.assertFalse(res["can_declare"])

    def test_invalid_evidence_kind_refused(self):
        ev = et.DualEnvironmentEvidence()
        with self.assertRaises(ValueError):
            ev.record("x", kind="mystery", handle="h")


if __name__ == "__main__":
    unittest.main(verbosity=2)
