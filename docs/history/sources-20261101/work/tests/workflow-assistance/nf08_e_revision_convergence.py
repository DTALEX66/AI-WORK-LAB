"""NF-08-E: revision / cancellation / out-of-order / unknown-effect convergence.

Proves the acceptance rows for AT-25/26/27/28:
  * rev1 running, rev2 published -> rev1's late completion does not end rev2;
  * after cancellation no new effect starts; already-happened / still-unknown
    effects remain queryable;
  * an unknown effect is not blindly retried (reconciled against evidence
    first), and the refusal is scoped to the affected task only;
  * out-of-order deliveries keep the newest revision authoritative while older
    results are retained for audit.

Pure and deterministic: no network, no process termination, no paid call.
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

import revision_convergence as rc  # noqa: E402


class TestLateRevision(unittest.TestCase):
    def test_late_rev1_result_does_not_end_rev2(self):
        conv = rc.RevisionConvergence("t-1")
        conv.publish(1)
        conv.publish(2)  # rev2 is now active
        self.assertEqual(conv.active_revision, 2)
        # rev1's late completion arrives while rev2 is active
        late = conv.late_result(1, "COMPLETED")
        self.assertTrue(late["held"])
        self.assertFalse(late["ended_active"])
        self.assertEqual(late["active_revision"], 2)
        # the active pointer has not advanced / regressed
        self.assertEqual(conv.active_revision, 2)
        # only a rev2 result may finish rev2
        r2 = conv.late_result(2, "COMPLETED")
        self.assertTrue(r2["ended_active"])
        self.assertEqual(r2["held"], False)

    def test_publishing_a_lower_revision_is_held_not_a_regression(self):
        conv = rc.RevisionConvergence("t-1")
        conv.publish(3)
        res = conv.publish(2)  # lower than active 3
        self.assertFalse(res["advanced"])
        self.assertTrue(res["held_as_stale"])
        self.assertEqual(conv.active_revision, 3)


class TestCancellation(unittest.TestCase):
    def test_cancelled_task_starts_no_new_effect(self):
        guard = rc.CancellationGuard("t-1", "CANCELLED")
        res = guard.try_start_effect("eff-1")
        self.assertFalse(res["started"])
        self.assertEqual(res["decision"], "REJECTED_CANCELLED")
        self.assertEqual(res["scoped_to_task"], "t-1")

    def test_terminal_failed_task_also_refuses_new_effects(self):
        guard = rc.CancellationGuard("t-1", "FAILED")
        self.assertFalse(guard.try_start_effect("eff-1")["started"])

    def test_already_happened_and_unknown_effects_are_queryable(self):
        guard = rc.CancellationGuard("t-1", "CANCELLED")
        guard.record_effect("eff-confirmed", "CONFIRMED")
        guard.record_effect("eff-unknown", "UNKNOWN")
        q = guard.queryable_effects()
        self.assertEqual(q["eff-confirmed"], "CONFIRMED")
        self.assertEqual(q["eff-unknown"], "UNKNOWN")


class TestUnknownEffectNotBlindlyRetried(unittest.TestCase):
    def test_unknown_effect_reconciled_not_blind_retried(self):
        guard = rc.CancellationGuard("t-1", "RUNNING")
        guard.record_effect("eff-1", "UNKNOWN")
        self.assertFalse(guard.blind_retry_allowed("eff-1"))
        res = guard.reconcile_unknown("eff-1", observed_state="CONFIRMED")
        self.assertFalse(res["blind_retry"])
        self.assertEqual(res["reconciled_to"], "CONFIRMED")

    def test_conflict_effect_not_blind_retried(self):
        guard = rc.CancellationGuard("t-1", "RUNNING")
        guard.record_effect("eff-2", "CONFLICT")
        self.assertFalse(guard.blind_retry_allowed("eff-2"))

    def test_absent_effect_may_rerun(self):
        guard = rc.CancellationGuard("t-1", "RUNNING")
        guard.record_effect("eff-3", "ABSENT")
        self.assertTrue(guard.blind_retry_allowed("eff-3"))

    def test_confirmed_cannot_be_downgraded(self):
        guard = rc.CancellationGuard("t-1", "RUNNING")
        guard.record_effect("eff-4", "CONFIRMED")
        res = guard.reconcile_unknown("eff-4", observed_state="ABSENT")
        self.assertTrue(res["rejected"])

    def test_refusal_scoped_to_affected_task_not_global(self):
        guard_a = rc.CancellationGuard("t-A", "CANCELLED")
        guard_b = rc.CancellationGuard("t-B", "RUNNING")
        # A is cancelled: it rejects; B is unaffected and still accepts
        self.assertFalse(guard_a.try_start_effect("e")["started"])
        self.assertTrue(guard_b.try_start_effect("e")["started"])
        # the rejection decision carries the task scope
        self.assertEqual(guard_a.attempts()[0]["decision"], "REJECTED_CANCELLED")


class TestOutOfOrder(unittest.TestCase):
    def test_newest_revision_is_authoritative_older_retained(self):
        ooo = rc.OutOfOrderConvergence("t-1")
        ooo.deliver(2, "done")   # out of order: 2 first
        ooo.deliver(1, "done")   # then the older one
        auth = ooo.authoritative()
        self.assertEqual(auth["revision"], 2)
        self.assertEqual(auth["outcomes"], ["done"])
        # the older rev1 result is retained for audit
        self.assertIn(1, ooo.results_by_revision)

    def test_deliver_records_newest_flag(self):
        ooo = rc.OutOfOrderConvergence("t-1")
        self.assertTrue(ooo.deliver(3, "x")["is_newest"])
        self.assertFalse(ooo.deliver(2, "x")["is_newest"])
        self.assertEqual(ooo.deliver(2, "x")["authoritative_revision"], 3)


if __name__ == "__main__":
    unittest.main(verbosity=2)
