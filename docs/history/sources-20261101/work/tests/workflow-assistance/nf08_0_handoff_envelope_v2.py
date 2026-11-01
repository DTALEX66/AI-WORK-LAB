"""NF-08-0: compatible extension of the federation handoff envelope (v2).

Proves the acceptance rows without duplicating a parallel authoritative format:
  * a legacy v1 message stays readable by ``read_v1``;
  * a v2 reader EXPLICITLY rejects v1 (no silent truncation), and an old reader
    rejects v2 symmetrically;
  * project id and client id are distinct fields (a project is never mistaken
    for a software id);
  * task revision / code-baseline kind / immutable digest / receipt location /
    target capability / authorization reference / supersedes are present and
    explicit;
  * a delivery whose task+revision carries a DIFFERENT digest is a CONFLICT,
    never a silent overwrite of previously approved content;
  * authorization comes only from a trusted local grant record; payload
    self-claims (``approved=true`` / ``scope`` text) are ignored;
  * the Ready pointer is published only after the immutable snapshot is
    complete.

Pure and deterministic: no network, no filesystem, no paid call, no native
private store.
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

import handoff_envelope as he  # noqa: E402


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _git_baseline(commit: str = "0" * 40) -> dict:
    return {"kind": "git", "commit": commit, "worktree": "refs/heads/main"}


def _artifact_baseline(digest: str = "sha256:0") -> dict:
    return {"kind": "artifact", "digest": digest}


def _draft(**overrides) -> dict:
    d = {
        "messageId": "msg-1",
        "producer": "proj-a",
        "consumer": "proj-b",
        "sourceSoftware": "hermes",
        "targetSoftware": "codex",
        "environment": "local",
        "workUnitId": "task-42",
        "taskRevision": 3,
        "baseline": _git_baseline(),
        "bodyDigest": "digest-3",
        "receiptLocation": "runs/task-42/r3.json",
        "targetCapability": "apply",
        "authorizationRef": "grant-0007",
        "classification": "internal",
        "rightsStatus": "owned",
        "createdAt": "2026-09-16T00:00:00Z",
        "idempotencyKey": "task-42:3:abc",
    }
    d.update(overrides)
    return d


class TestV1Compat(unittest.TestCase):
    def test_v1_still_readable(self):
        v1 = he.read_v1({
            "schemaVersion": "workflow/federation-envelope/v1",
            "messageId": "m", "producer": "work-lab", "consumer": "aether-radar",
            "correlationId": "c", "contentHash": "h", "classification": "internal",
            "rightsStatus": "owned", "createdAt": "t", "idempotencyKey": "k",
        })
        self.assertTrue(v1["readable"])
        self.assertEqual(v1["schema"], "workflow/federation-envelope/v1")

    def test_v1_read_rejects_v2(self):
        with self.assertRaises(ValueError):
            he.read_v1(he.build_v2_envelope(_draft()))

    def test_v2_reader_explicitly_rejects_v1_no_truncation(self):
        res = he.read_v2({
            "schemaVersion": "workflow/federation-envelope/v1",
            "messageId": "m", "producer": "work-lab", "consumer": "aether-radar",
            "correlationId": "c", "contentHash": "h", "classification": "internal",
            "rightsStatus": "owned", "createdAt": "t", "idempotencyKey": "k",
        })
        self.assertFalse(res["readable"])
        self.assertIn("explicit", res["reason"])

    def test_v1_to_v2_migration_requires_registered_refs(self):
        v1 = {
            "schemaVersion": "workflow/federation-envelope/v1",
            "messageId": "m", "producer": "work-lab", "consumer": "aether-radar",
            "correlationId": "c", "contentHash": "h", "classification": "internal",
            "rightsStatus": "owned", "createdAt": "t", "idempotencyKey": "k",
        }
        reg = {"work-lab": "opaque-wl", "aether-radar": "opaque-ar"}
        out = he.migrate_v1_to_v2(v1, registry_projects=reg,
                                  source_software="hermes", target_software="codex")
        self.assertEqual(out["producer"], "opaque-wl")
        self.assertEqual(out["consumer"], "opaque-ar")
        self.assertEqual(out["migrated_from"], "workflow/federation-envelope/v1")
        # unregistered legacy name -> fail-closed, no guess
        with self.assertRaises(ValueError):
            he.migrate_v1_to_v2(v1, registry_projects={"work-lab": "opaque-wl"},
                                source_software="h", target_software="c")


class TestV2Fields(unittest.TestCase):
    def test_project_id_is_not_software_id(self):
        env = he.build_v2_envelope(_draft())
        self.assertNotEqual(env["producer"], env["sourceSoftware"])
        self.assertNotEqual(env["consumer"], env["targetSoftware"])

    def test_all_explicit_fields_present(self):
        env = he.build_v2_envelope(_draft())
        for f in ("taskRevision", "baseline", "bodyDigest", "artifactRef",
                  "receiptLocation", "targetCapability", "authorizationRef",
                  "sourceSoftware", "targetSoftware", "environment"):
            self.assertIn(f, env, f"missing {f}")
        self.assertEqual(env["taskRevision"], 3)

    def test_artifact_baseline_requires_digest(self):
        with self.assertRaises(ValueError):
            he.build_v2_envelope(_draft(baseline={"kind": "artifact"}))

    def test_git_baseline_requires_commit(self):
        with self.assertRaises(ValueError):
            he.build_v2_envelope(_draft(baseline={"kind": "git"}))

    def test_unknown_classification_rejected(self):
        with self.assertRaises(ValueError):
            he.build_v2_envelope(_draft(classification="secret"))


class TestRevisionConflict(unittest.TestCase):
    def test_same_task_revision_different_digest_is_conflict_not_overwrite(self):
        reg = he.RevisionRegistry()
        r1 = reg.record(he.build_v2_envelope(_draft()))
        self.assertEqual(r1["status"], "RECORDED")
        # same taskRevision=3, different body digest -> CONFLICT, no overwrite
        r2 = reg.record(he.build_v2_envelope(
            _draft(bodyDigest="digest-B", messageId="msg-2")))
        self.assertEqual(r2["status"], "CONFLICT")
        self.assertFalse(r2["recorded"])
        # the originally-approved digest survives, un-overwritten
        self.assertEqual(reg.chain("task-42")[0]["bodyDigest"], "digest-3")

    def test_higher_revision_appends_supersede_chain_not_merge(self):
        reg = he.RevisionRegistry()
        reg.record(he.build_v2_envelope(_draft()))
        r2 = reg.record(he.build_v2_envelope(
            _draft(bodyDigest="digest-4", taskRevision=4, messageId="m4")))
        self.assertEqual(r2["status"], "RECORDED")
        self.assertEqual(r2["supersedes_rev"], 3)
        self.assertEqual(reg.active_revision("task-42"), 4)
        chain = reg.chain("task-42")
        self.assertEqual([c["revision"] for c in chain], [3, 4])
        self.assertEqual(chain[1]["supersedes_rev"], 3)

    def test_late_low_revision_result_held_not_accepted(self):
        reg = he.RevisionRegistry()
        reg.record(he.build_v2_envelope(_draft()))
        reg.record(he.build_v2_envelope(
            _draft(bodyDigest="digest-5", taskRevision=5, messageId="m5")))
        res = reg.late_low_revision_result("task-42", result_revision=3)
        self.assertEqual(res["status"], "HELD_STALE")
        self.assertEqual(res["active_revision"], 5)


class TestAuthorization(unittest.TestCase):
    def test_authorization_bound_to_trusted_local_grant_only(self):
        env = he.build_v2_envelope(_draft())
        res = he.check_authorization(env, trusted_grants={"grant-0007": "apply"})
        self.assertTrue(res["authorized"])
        self.assertEqual(res["scope"], "apply")

    def test_missing_grant_is_unauthorized_not_self_conferred(self):
        env = he.build_v2_envelope(_draft())
        res = he.check_authorization(env, trusted_grants={})  # grant-0007 absent
        self.assertFalse(res["authorized"])
        self.assertIn("not found", res["reason"])

    def test_no_authorization_ref_means_no_grant(self):
        env = he.build_v2_envelope(_draft(authorizationRef=""))
        res = he.check_authorization(env, trusted_grants={"grant-0007": "apply"})
        self.assertFalse(res["authorized"])

    def test_payload_self_claims_are_ignored(self):
        env = he.build_v2_envelope(_draft())
        env["payload_claims"] = {"approved": True, "scope": "admin",
                                 "permission_scope": "*"}
        res = he.check_authorization(env, trusted_grants={"grant-0007": "apply"})
        self.assertTrue(res["authorized"])
        self.assertEqual(res["scope"], "apply")  # the LOCAL grant, not 'admin'
        self.assertIn("IGNORED", res["note"])


class TestReadyPointer(unittest.TestCase):
    def test_ready_only_after_immutable_snapshot(self):
        env = he.build_v2_envelope(_draft())  # git baseline w/ commit
        self.assertTrue(he.publish_ready_pointer(env)["ready"])
        # an INCOMPLETE git baseline (no commit) is not ready — checked at the
        # Ready-pointer layer with a raw dict (build itself is strict/fail-fast
        # and refuses to mint an envelope from an incomplete baseline).
        bad = dict(env)
        bad["baseline"] = {"kind": "git", "commit": ""}
        self.assertFalse(he.publish_ready_pointer(bad)["ready"])
        # and build refuses to mint that incomplete envelope up front
        with self.assertRaises(ValueError):
            he.build_v2_envelope(_draft(baseline={"kind": "git", "commit": ""}))

    def test_artifact_baseline_requires_digest_for_ready(self):
        env = he.build_v2_envelope(
            _draft(baseline=_artifact_baseline("sha256:deadbeef")))
        self.assertTrue(he.publish_ready_pointer(env)["ready"])
        # incomplete artifact baseline (no digest) -> not ready at the pointer
        bad = dict(env)
        bad["baseline"] = {"kind": "artifact", "digest": ""}
        self.assertFalse(he.publish_ready_pointer(bad)["ready"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
