"""NF-08-A: cloud/planner publication planning + per-action permission audit.

Proves the acceptance rows for AT-11 / AT-12 / AT-13 on the self-executable
slice (design + code + synthetic tests; real server publication stays
authorization-gated and BLOCKED):
  * a publication plan returns a readable artifact version and the entry
    point carries only a summary + reference (body not copied by hand);
  * a repeated request does not create a duplicate task; a lost response is
    resolved by querying first, then resending;
  * routing to different projects is correct; a public target REJECTS a
    private / internal / classified canary.

Pure and deterministic: no network, no credential read, no paid call.
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

import publish_planner as pp  # noqa: E402

PUBLIC = {"work-lab": "github:public/WORK-LAB", "aether-radar": "github:public/Aether-Radar"}
PRIVATE = {"work-lab": "github:private/WORK-LAB-secrets", "aether-radar": "github:private/Aether-Radar-private"}


class TestRouting(unittest.TestCase):
    def test_private_material_routes_to_private_target(self):
        r = pp.route_target("work-lab", "private", PUBLIC, PRIVATE)
        self.assertTrue(r["routed"])
        self.assertEqual(r["visibility"], pp.TARGET_PRIVATE)
        self.assertIn("private", r["target"])

    def test_public_material_may_use_public_target(self):
        r = pp.route_target("aether-radar", "public", PUBLIC, PRIVATE)
        self.assertTrue(r["routed"])
        self.assertEqual(r["visibility"], pp.TARGET_PUBLIC)

    def test_no_target_registered_is_not_routed(self):
        r = pp.route_target("unknown-proj", "public", PUBLIC, PRIVATE)
        self.assertFalse(r["routed"])

    def test_private_material_without_private_target_refused_not_auto_public(self):
        r = pp.route_target("only-public", "private",
                            {"only-public": "github:public/X"}, {})
        self.assertFalse(r["routed"])
        self.assertIn("private", r["reason"])

    def test_unknown_material_class_refused(self):
        r = pp.route_target("work-lab", "top-secret-x", PUBLIC, PRIVATE)
        self.assertFalse(r["routed"])


class TestCanaryRejection(unittest.TestCase):
    def test_internal_canary_rejected_in_public_target(self):
        res = pp.reject_private_canary_in_public(pp.TARGET_PUBLIC, "internal")
        self.assertFalse(res["accepted"])

    def test_private_canary_rejected_in_public_target(self):
        res = pp.reject_private_canary_in_public(pp.TARGET_PUBLIC, "private")
        self.assertFalse(res["accepted"])

    def test_classified_canary_rejected_in_public_target(self):
        res = pp.reject_private_canary_in_public(pp.TARGET_PUBLIC, "classified")
        self.assertFalse(res["accepted"])

    def test_private_material_in_public_project_plan_fails_closed(self):
        # a project that only has a public target cannot receive private material
        plan = pp.build_publication_plan(
            project="only-public", task_id="t1", body="x",
            material_class="private",
            public_targets={"only-public": "github:public/X"},
            private_targets={})
        self.assertFalse(plan["planned"])

    def test_public_canary_accepted_in_public_target(self):
        res = pp.reject_private_canary_in_public(pp.TARGET_PUBLIC, "public")
        self.assertTrue(res["accepted"])


class TestPublicationPlan(unittest.TestCase):
    def test_large_body_goes_to_fixed_artifact_first_with_summary_ref(self):
        body = "body " * 1000  # ~5000 chars, well above the threshold
        plan = pp.build_publication_plan(
            project="work-lab", task_id="task-9", body=body,
            material_class="public",
            public_targets=PUBLIC, private_targets=PRIVATE)
        self.assertTrue(plan["planned"])
        self.assertIn(":", plan["artifact_version"])  # fixed version tag
        self.assertEqual(plan["steps"][0]["action"], "file_write")
        self.assertTrue(plan["steps"][0]["large_body"])
        # the entry point carries a summary + reference, not the full body
        entry = plan["steps"][1]
        self.assertEqual(entry["action"], "issue_write")
        self.assertLessEqual(len(entry["summary"]), 128)
        self.assertEqual(entry["artifact_ref"], plan["artifact_version"])
        self.assertNotIn(body, json_dump_of(plan))

    def test_idempotency_key_is_stable_for_same_content(self):
        p1 = pp.build_publication_plan(
            project="work-lab", task_id="task-9", body="abc",
            material_class="public", public_targets=PUBLIC, private_targets=PRIVATE)
        p2 = pp.build_publication_plan(
            project="work-lab", task_id="task-9", body="abc",
            material_class="public", public_targets=PUBLIC, private_targets=PRIVATE)
        self.assertEqual(p1["idempotency_key"], p2["idempotency_key"])

    def test_user_does_not_copy_body_when_planned(self):
        plan = pp.build_publication_plan(
            project="work-lab", task_id="task-9", body="hello world",
            material_class="public", public_targets=PUBLIC, private_targets=PRIVATE)
        # the plan itself carries a readable artifact version + digest
        self.assertTrue(plan["planned"])
        self.assertTrue(plan["artifact_version"])
        self.assertTrue(plan["body_digest"])


def json_dump_of(obj):
    import json as _json
    return _json.dumps(obj, ensure_ascii=False, default=str)


class TestPerActionPermissionAudit(unittest.TestCase):
    def test_one_push_false_does_not_infer_other_actions(self):
        cap = {"push": False, "file_write": "granted", "issue_write": "granted",
               "comment_write": "granted"}
        audit = pp.PublishAudit(cap)
        res = audit.can_proceed()
        # push dimension is separate; the three required actions are all granted
        self.assertEqual(res["status"], "PUBLISH_READY")
        self.assertNotIn("push", res["verdicts"])

    def test_denied_issue_write_blocks_publication(self):
        cap = {"file_write": "granted", "issue_write": "denied",
               "comment_write": "granted"}
        res = pp.PublishAudit(cap).can_proceed()
        self.assertEqual(res["status"], "PUBLISH_PENDING_AUTHORIZATION")
        self.assertFalse(res["claimed_success"])
        self.assertIn("issue_write", res["denied"])

    def test_unknown_capability_is_not_guessed_granted(self):
        cap = {"file_write": "granted"}  # issue_write / comment_write unknown
        res = pp.PublishAudit(cap).can_proceed()
        self.assertEqual(res["status"], "PUBLISH_PENDING_AUTHORIZATION")
        self.assertIn("issue_write", res["unknown"])
        self.assertFalse(res["claimed_success"])


class TestReadbackVerification(unittest.TestCase):
    def test_matching_readback_confirms_published(self):
        plan = pp.build_publication_plan(
            project="work-lab", task_id="task-9", body="abc",
            material_class="public", public_targets=PUBLIC, private_targets=PRIVATE)
        server = {"id": "ISSUE-42", "revision": 3, "digest": plan["body_digest"]}
        res = pp.verify_readback(plan, server)
        self.assertTrue(res["verified"])
        self.assertEqual(res["status"], "PUBLISHED")
        self.assertEqual(res["id"], "ISSUE-42")

    def test_digest_mismatch_is_not_success(self):
        plan = pp.build_publication_plan(
            project="work-lab", task_id="task-9", body="abc",
            material_class="public", public_targets=PUBLIC, private_targets=PRIVATE)
        server = {"id": "ISSUE-42", "revision": 3, "digest": "other"}
        res = pp.verify_readback(plan, server)
        self.assertFalse(res["verified"])
        self.assertEqual(res["status"], "DIGEST_MISMATCH")

    def test_incomplete_readback_is_not_success(self):
        plan = pp.build_publication_plan(
            project="work-lab", task_id="task-9", body="abc",
            material_class="public", public_targets=PUBLIC, private_targets=PRIVATE)
        res = pp.verify_readback(plan, {"id": "ISSUE-42"})
        self.assertFalse(res["verified"])
        self.assertEqual(res["status"], "READBACK_INCOMPLETE")


class TestIdempotentPublication(unittest.TestCase):
    def test_repeated_request_does_not_create_duplicate(self):
        store = pp.PublicationStore()
        plan = pp.build_publication_plan(
            project="work-lab", task_id="task-9", body="abc",
            material_class="public", public_targets=PUBLIC, private_targets=PRIVATE)
        first = store.publish(plan)
        second = store.publish(plan)
        self.assertTrue(first["created"])
        self.assertFalse(second["created"])
        self.assertTrue(second["duplicate"])
        self.assertEqual(first["id"], second["id"])

    def test_lost_response_queries_first_then_resends_only_if_absent(self):
        store = pp.PublicationStore()
        plan = pp.build_publication_plan(
            project="work-lab", task_id="task-9", body="abc",
            material_class="public", public_targets=PUBLIC, private_targets=PRIVATE)
        store.publish(plan)  # first publish, response lost
        res = store.reconcile_lost_response(plan)
        self.assertTrue(res["already"])
        self.assertFalse(res["resent"])
        # a key that was never published is resent exactly once
        plan2 = pp.build_publication_plan(
            project="work-lab", task_id="task-9", body="DIFFERENT",
            material_class="public", public_targets=PUBLIC, private_targets=PRIVATE)
        res2 = store.reconcile_lost_response(plan2)
        self.assertTrue(res2["resent"])
        self.assertFalse(res2["already"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
