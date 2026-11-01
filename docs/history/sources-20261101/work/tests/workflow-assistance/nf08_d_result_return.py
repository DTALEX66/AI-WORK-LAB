"""NF-08-D: result return, read-back and explicit review-trigger.

Proves the acceptance rows for AT-22 / AT-23 / AT-24 on the self-executable
slice (real remote receipt write stays authorization-gated and BLOCKED):
  * a receipt is bound to project/task/revision/run/baseline/artifact digest
    and DISTINGUISHES execution_completed from accepted;
  * a planner's fresh read sees the result for the exact revision, without the
    user hauling logs back;
  * a lost acknowledgement produces no duplicate result; a retry re-sends the
    SAME receipt, never re-runs the task;
  * the task body / private session log never enters public telemetry;
  * RECEIPT_PUBLISHED vs REVIEW_REQUESTED are shown as different; a missing
    supported review channel yields REVIEW_PENDING and it never claims to have
    woken a previous chat;
  * a reverse edit of the projected task-page status passes the SAME
    permission + version check.

Pure and deterministic: no network, no remote write, no paid call.
"""
from __future__ import annotations

import json
import os
import sys
import unittest

_PKG = os.path.abspath(os.path.join(
    os.path.abspath(os.path.dirname(__file__)), "..", "..",
    "packages", "client-neutral-core", "scripts"))
if _PKG not in sys.path:
    sys.path.insert(0, _PKG)

import result_return as rr  # noqa: E402


def _receipt(**over) -> dict:
    base = dict(
        receiptId="r-1", project="work-lab", task_id="t-1", task_revision=3,
        run_session_id="run-9", baseline="0" * 40,
        artifact_digest="sha256:abc", execution_completed=True, accepted=False,
        status="RECEIPT_PUBLISHED", changes=["a.py"], tests={"unit": "pass"},
        commit="0" * 40, pull_request=None, blockers=[], open_items=["verify readback"],
        token_usage="UNKNOWN", cost="UNKNOWN")
    base.update(over)
    return base


class TestReceiptBinding(unittest.TestCase):
    def test_execution_completed_is_distinct_from_accepted(self):
        r = rr.build_receipt(
            receipt_id="r-2", project="work-lab", task_id="t-1", task_revision=3,
            run_session_id="run-9", baseline="0" * 40, artifact_digest="sha256:abc",
            execution_completed=True, accepted=False)
        self.assertTrue(r.execution_completed)
        self.assertFalse(r.accepted)  # finished is not the same as approved

    def test_missing_token_cost_stay_unknown_never_zero(self):
        r = rr.build_receipt(
            receipt_id="r-3", project="work-lab", task_id="t-1", task_revision=1,
            run_session_id="run-1", baseline="0" * 40, artifact_digest="d",
            execution_completed=True)
        self.assertEqual(r.token_usage, "UNKNOWN")
        self.assertEqual(r.cost, "UNKNOWN")
        metrics = rr.missing_metrics_as_unknown(r.to_dict())
        self.assertEqual(metrics, {"token_usage": "UNKNOWN", "cost": "UNKNOWN"})

    def test_commit_pr_are_optional_fields(self):
        r = rr.build_receipt(
            receipt_id="r-4", project="work-lab", task_id="t-1", task_revision=1,
            run_session_id="run-1", baseline="b", artifact_digest="d",
            execution_completed=True, commit=None, pull_request=None)
        self.assertIsNone(r.commit)
        self.assertIsNone(r.pull_request)


class TestOutboxIdempotency(unittest.TestCase):
    def test_duplicate_receipt_not_rerun(self):
        box = rr.OutboxDedupe()
        r = _receipt()
        self.assertTrue(box.enqueue(r)["enqueued"])
        self.assertTrue(box.enqueue(r)["duplicate"])

    def test_lost_ack_retries_receipt_not_task(self):
        box = rr.OutboxDedupe()
        r = _receipt(receiptId="r-10")
        box.enqueue(r)
        # remote unavailable: the local completion fact is retained, the receipt
        # stays pending, and a retry re-sends the RECEIPT — never the task
        res = box.send_attempt(r, ack=False)
        self.assertFalse(res["sent"])
        self.assertTrue(res["local_fact_retained"])
        self.assertEqual(res["attempts"], 1)
        # reconcile a lost ack: it was not yet acknowledged -> resend, no dup
        recon = box.lost_ack_reconcile(r)
        self.assertTrue(recon["resent"])
        # now acknowledged: a further same-receipt send is a no-op
        ok = box.send_attempt(r, ack=True)
        self.assertTrue(ok["sent"])
        final = box.lost_ack_reconcile(r)
        self.assertTrue(final["already"])
        self.assertFalse(final["resent"])

    def test_lost_ack_produces_no_duplicate_result(self):
        box = rr.OutboxDedupe()
        r = _receipt(receiptId="r-11")
        box.enqueue(r)
        box.send_attempt(r, ack=True)
        # re-sending the same receipt after ack is a duplicate no-op
        dup = box.enqueue(r)
        self.assertTrue(dup["duplicate"])


class TestReadbackForRevision(unittest.TestCase):
    def test_planner_fresh_read_sees_exact_revision(self):
        receipts = [
            _receipt(receiptId="r-a", task_revision=2, execution_completed=True),
            _receipt(receiptId="r-b", task_revision=3, execution_completed=True,
                     token_usage="1200", cost="$0.02"),
        ]
        res = rr.read_back_for_revision(receipts, task_id="t-1", revision=3)
        self.assertTrue(res["found"])
        self.assertEqual(res["receipt_id"], "r-b")
        self.assertEqual(res["token_usage"], "1200")
        # revision 4 has no receipt -> not guessed from another revision
        miss = rr.read_back_for_revision(receipts, task_id="t-1", revision=4)
        self.assertFalse(miss["found"])
        self.assertIn("not guessed", miss["note"])


class TestPrivacy(unittest.TestCase):
    def test_task_body_and_session_log_never_enter_public_telemetry(self):
        r = _receipt()
        r["task_body"] = "SECRET task body"
        telemetry = rr._public_telemetry(r)
        self.assertFalse(telemetry["body_included"])
        self.assertFalse(telemetry["session_log_included"])
        self.assertNotIn("SECRET", str(telemetry))


class TestReviewTrigger(unittest.TestCase):
    def test_review_pending_when_no_supported_channel(self):
        gate = rr.ProjectionGate()
        res = gate.trigger_review("t-1", channel=None)
        self.assertEqual(res["status"], "REVIEW_PENDING")
        self.assertIn("PENDING", res["note"])

    def test_supported_channel_requests_review(self):
        gate = rr.ProjectionGate()
        gate.register_review_channel("t-1", "github-notification")
        res = gate.trigger_review("t-1", channel="github-notification")
        self.assertEqual(res["status"], "REVIEW_REQUESTED")

    def test_trigger_never_carry_body(self):
        gate = rr.ProjectionGate()
        with self.assertRaises(AssertionError):
            gate.trigger_review("t-1", channel=None, task_body="SECRET")

    def test_never_claims_woken_a_previous_chat(self):
        gate = rr.ProjectionGate()
        self.assertTrue(gate.did_not_wake_previous_chat())

    def test_receipt_published_vs_review_requested_distinguished(self):
        pub = rr.distinguish_receipt_published_vs_review_requested(
            _receipt(status="RECEIPT_PUBLISHED"))
        self.assertFalse(pub["review_requested"])
        req = rr.distinguish_receipt_published_vs_review_requested(
            _receipt(receiptId="r-2", status="REVIEW_REQUESTED"))
        self.assertTrue(req["review_requested"])


class TestReceiptSerialization(unittest.TestCase):
    def test_to_dict_is_json_serializable_and_fingerprint_is_a_digest(self):
        r = rr.build_receipt(
            receipt_id="r-20", project="work-lab", task_id="t-1", task_revision=3,
            run_session_id="run-9", baseline="0" * 40, artifact_digest="sha256:abc",
            execution_completed=True)
        data = r.to_dict()
        # the fingerprint is a value, not the bound method the first version leaked
        self.assertRegex(data["fingerprint"], r"^[0-9a-f]{64}$")
        self.assertEqual(data["fingerprint"], r.fingerprint())
        encoded = json.dumps(data, sort_keys=True)
        self.assertIn('"fingerprint": "' + r.fingerprint() + '"', encoded)


class TestRevisionConflict(unittest.TestCase):
    def test_same_receipt_id_with_a_new_revision_is_a_conflict(self):
        box = rr.OutboxDedupe()
        first = _receipt(receiptId="r-20", task_revision=3)
        self.assertTrue(box.enqueue(first)["enqueued"])
        second = _receipt(receiptId="r-20", task_revision=4)
        conflict = box.enqueue(second)
        self.assertFalse(conflict["enqueued"])
        self.assertTrue(conflict["conflict"])
        self.assertEqual(conflict["reason"], "IDEMPOTENCY_CONFLICT")
        self.assertEqual(len(box.pending()), 1)
        send = box.send_attempt(second, ack=False)
        self.assertFalse(send["sent"])
        self.assertEqual(send["reason"], "IDEMPOTENCY_CONFLICT")
        recon = box.lost_ack_reconcile(second)
        self.assertFalse(recon["resent"])
        self.assertEqual(recon["reason"], "IDEMPOTENCY_CONFLICT")


class TestEgressPolicy(unittest.TestCase):
    def test_egress_is_default_deny(self):
        policy = rr.EgressPolicy()
        denied = policy.check("review-page", _receipt())
        self.assertFalse(denied["allowed"])
        self.assertEqual(denied["reason"], "DESTINATION_NOT_AUTHORISED")
        policy.authorize("review-page")
        allowed = policy.check("review-page", _receipt())
        self.assertTrue(allowed["allowed"])
        self.assertEqual(allowed["payload"]["receipt_id"], "r-1")
        self.assertFalse(allowed["payload"]["body_included"])
        self.assertFalse(allowed["payload"]["session_log_included"])

    def test_egress_never_carries_private_fields_even_when_authorized(self):
        policy = rr.EgressPolicy()
        policy.authorize("review-page")
        res = policy.check("review-page", _receipt(task_body="SECRET"))
        self.assertFalse(res["allowed"])
        self.assertEqual(res["reason"], "PRIVATE_FIELD_REFUSED")
        self.assertIn("task_body", res["fields"])

    def test_egress_authorization_does_not_imply_acceptance(self):
        policy = rr.EgressPolicy()
        policy.authorize("review-page")
        payload = policy.check("review-page", _receipt(accepted=False))["payload"]
        self.assertTrue(payload["execution_completed"])
        self.assertFalse(payload["accepted"])


class TestProjectionReverseEdit(unittest.TestCase):
    def test_reverse_edit_must_pass_version_check(self):
        gate = rr.ProjectionGate()
        # current page version is 0; editing from base 0 is fine
        ok = gate.reverse_edit("t-1", base_version=0, permission="editor")
        self.assertTrue(ok["edit_applied"])
        # a stale base version is rejected (the SAME version check gates it)
        stale = gate.reverse_edit("t-1", base_version=0, permission="editor")
        self.assertFalse(stale["edit_applied"])
        self.assertEqual(stale["current_version"], 1)

    def test_expected_version_mismatch_rejected(self):
        gate = rr.ProjectionGate()
        res = gate.reverse_edit("t-1", base_version=0, permission="editor",
                                expected_version=5)
        self.assertFalse(res["edit_applied"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
