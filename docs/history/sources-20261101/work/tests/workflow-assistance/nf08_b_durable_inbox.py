"""NF-08-B: durable inbox/outbox on the existing TaskLedger boundary.

Proves the acceptance rows for AT-14/15/16/17:
  * process A claims then "exits"; a FRESH process B (new DurableInbox, same
    persistent root) reads the same record and does NOT start the task again;
  * two processes contending for the same task: only one dispatches (lease
    fence), the loser cannot begin new side effects;
  * project B keeps working while project A has a network fault (namespace
    isolation, separate roots);
  * a sync check makes no model call; an unchanged task does not rewrite all
    artifacts.

Simulated cross-process = two DurableInbox instances over the SAME root (the
persistence boundary is the file; a real process B just re-opens it).  No
network, no model, no credential access.
"""
from __future__ import annotations

import os
import shutil
import sys
import unittest

_PKG = os.path.abspath(os.path.join(
    os.path.abspath(os.path.dirname(__file__)), "..", "..",
    "packages", "client-neutral-core", "scripts"))
if _PKG not in sys.path:
    sys.path.insert(0, _PKG)

import durable_inbox as di  # noqa: E402
import project_temp  # noqa: E402


class _NamedRootMixin(unittest.TestCase):
    def setUp(self):
        self.dir = str(project_temp.fixture_dir(prefix="nf08b-"))
        self.rootA = di.Path(self.dir, "projectA")
        self.rootB = di.Path(self.dir, "projectB")
        self.boxA = di.DurableInbox("projectA", self.rootA)
        self.boxB = di.DurableInbox("projectB", self.rootB)

    def tearDown(self):
        # `ignore_errors=True` here would hide exactly the ERR-140 failure class (a fixture that
        # cannot be removed while still looking green), so a failed release is announced with the
        # same token project_temp's at-exit sweeper uses; the dir stays tracked until then.
        try:
            shutil.rmtree(self.dir)
        except OSError as error:
            print(f"TEMP_RESIDUE_NOT_REMOVED {self.dir} {type(error).__name__}: {error}")


class TestRestartNoDuplicate(_NamedRootMixin):
    def test_process_a_claims_then_process_b_does_not_restart(self):
        self.boxA.ledger.create("t-1", "nsA:t-1")
        # process A claims (persists intent + lease) then EXITS (GC boxA)
        self.boxA.claim("t-1", holder="procA", intent_digest="d1")
        del self.boxA
        # process B re-opens the SAME persistent root and reconciles
        box_b = di.DurableInbox("projectA", self.rootA)
        res = box_b.reconcile_or_resume("t-1")
        # a pending durable claim intent -> reconcile native evidence first,
        # do NOT blindly start the task again
        self.assertNotEqual(res.get("resume"), True)
        self.assertEqual(res.get("resume"), "reconcile")

    def test_confirmed_effect_blocks_reinvoke(self):
        self.boxA.ledger.create("t-2", "nsA:t-2")
        c = self.boxA.claim("t-2", holder="procA", intent_digest="d1")
        # reconcile the FENCE-SCOPED claim effect to CONFIRMED
        self.boxA.ledger.reconcile_external_effect("t-2", c["effect_id"], "CONFIRMED", "d1")
        res = self.boxA.reconcile_or_resume("t-2")
        self.assertFalse(res["resume"])
        self.assertEqual(res["reason"], "effect already CONFIRMED; not re-invoked")

    def test_no_durable_record_is_safe_to_start(self):
        self.boxA.ledger.create("t-3", "nsA:t-3")
        res = self.boxA.reconcile_or_resume("t-3")
        self.assertTrue(res["resume"])


class TestSingleDispatch(_NamedRootMixin):
    def test_lease_fence_allows_only_one_holder(self):
        self.boxA.ledger.create("t-10", "nsA:t-10")
        cA = self.boxA.claim("t-10", holder="procA", intent_digest="dA", executor=lambda tid: "ran")
        self.assertTrue(cA["dispatched"])
        self.assertEqual(cA["executor_result"], "ran")
        # procB trying to claim the same task while procA holds the lease:
        # acquire_lease must refuse (fence held) — procB cannot dispatch.
        with self.assertRaises(ValueError):
            boxB2 = di.DurableInbox("projectA", self.rootA)
            boxB2.claim("t-10", holder="procB", intent_digest="dB")
        # and procB's reconcile reports it may NOT start side effects
        boxB = di.DurableInbox("projectA", self.rootA)
        res = boxB.reconcile_or_resume("t-10", holder="procB")
        self.assertFalse(res["resume"])
        self.assertFalse(res["side_effects_allowed"])
        self.assertEqual(res["active_holder"], "procA")

    def test_fresh_holder_after_expiry_can_take_over(self):
        self.boxA.ledger.create("t-11", "nsA:t-11")
        import datetime as dt
        now = dt.datetime.now(dt.timezone.utc)
        # t0 is in the PAST so its 1s lease is already expired by the time we
        # acquire at `now`
        t0 = (now - dt.timedelta(seconds=5)).isoformat().replace("+00:00", "Z")
        self.boxA.claim("t-11", holder="procA", intent_digest="d", ttl_seconds=1, now=t0)
        later = now.isoformat().replace("+00:00", "Z")
        # after the lease expired, a different holder may acquire (fence bumps)
        cB = self.boxA.claim("t-11", holder="procB", intent_digest="d2", ttl_seconds=60, now=later)
        self.assertEqual(cB["holder"], "procB")
        self.assertGreater(cB["fence"], 1)


class TestNamespaceIsolation(_NamedRootMixin):
    def test_project_a_fault_does_not_block_project_b(self):
        # independent roots: writing to A's ledger never touches B's
        self.boxA.ledger.create("tA", "nsA:tA")
        self.boxB.ledger.create("tB", "nsB:tB")
        b_pending = self.boxB.outbox_pending()
        self.assertEqual(b_pending, [])
        # a paused / faulted subscription on A leaves B's poll due
        self.boxA.pause_subscription("srcA", "network fault on A")
        self.assertEqual(self.boxA.poll_due("srcA"), {"due": False, "reason": "paused", "pause_reason": "network fault on A"})
        self.boxB.subscribe("srcB")
        self.assertTrue(self.boxB.poll_due("srcB")["due"])
        self.assertTrue(di.namespace_isolated(self.rootA)["isolated_roots"])

    def test_event_identity_is_namespaced(self):
        iA = di.event_identity("projectA", "src", "e1", "d1")
        iB = di.event_identity("projectB", "src", "e1", "d1")
        self.assertNotEqual(iA, iB)  # same event, different project -> distinct


class TestIngestDedupe(_NamedRootMixin):
    def test_duplicate_notifications_are_dropped_not_restarted(self):
        self.boxA.subscribe("gh")
        batch = [
            {"event_id": "e1", "task_id": "t1", "payload_digest": "p1"},
            {"event_id": "e2", "task_id": "t2", "payload_digest": "p2"},
        ]
        r1 = self.boxA.ingest("gh", batch)
        self.assertEqual(r1["ingested"], 2)
        # same complete identity delivered again
        r2 = self.boxA.ingest("gh", batch)
        self.assertEqual(r2["ingested"], 0)
        self.assertEqual(r2["duplicates_dropped"], 2)
        self.assertEqual(len(r2["duplicate_ids"]), 2)
        # ledger holds exactly one task per distinct event
        self.assertIsNotNone(self.boxA.ledger.get("t1"))
        self.assertIsNotNone(self.boxA.ledger.get("t2"))


class TestSyncCheckNoModelCall(_NamedRootMixin):
    def test_conditional_request_makes_no_model_call(self):
        self.boxA.subscribe("gh", initial_etag="abc123")
        req = self.boxA.conditional_request("gh")
        self.assertFalse(req["make_model_call"])
        self.assertEqual(req["if_none_match"], "abc123")
        self.assertEqual(req["cursor"], "")

    def test_retry_after_is_honoured_not_busy_polled(self):
        self.boxA.subscribe("gh")
        import datetime as dt
        t0 = dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")
        note = self.boxA.note_retry_after("gh", 60, now=t0)
        self.assertTrue(note["throttled"])
        due_now = self.boxA.poll_due("gh", now=t0)
        self.assertFalse(due_now["due"])
        self.assertEqual(due_now["reason"], "retry_after")
        # one second later it is still throttled (no busy poll)
        t1 = (dt.datetime.fromisoformat(t0.replace("Z","+00:00")) + dt.timedelta(seconds=5)).isoformat().replace("+00:00","Z")
        self.assertFalse(self.boxA.poll_due("gh", now=t1)["due"])

    def test_unchanged_content_does_not_rewrite_artifacts(self):
        self.boxA.ledger.create("t-9", "nsA:t-9")
        first = self.boxA.artifact_rewrite_needed("t-9", "digest-1")
        self.assertTrue(first["rewrite"])
        same = self.boxA.artifact_rewrite_needed("t-9", "digest-1")
        self.assertFalse(same["rewrite"])
        self.assertIn("unchanged", same["reason"])
        changed = self.boxA.artifact_rewrite_needed("t-9", "digest-2")
        self.assertTrue(changed["rewrite"])


class TestOutboxIdempotency(_NamedRootMixin):
    def test_same_pending_receipt_not_duplicated(self):
        self.boxA.ledger.create("t-7", "nsA:t-7")
        a = self.boxA.enqueue_outbox("t-7", receipt={"workUnitId": "t-7"})
        b = self.boxA.enqueue_outbox("t-7", receipt={"workUnitId": "t-7"})
        self.assertTrue(a["enqueued"])
        self.assertTrue(b["duplicate"])
        self.assertEqual(len(self.boxA.outbox_pending()), 1)
        self.assertEqual(self.boxA.mark_outbox_delivered("t-7"), 1)
        self.assertEqual(self.boxA.outbox_pending(), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
