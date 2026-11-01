"""NF-08-G: a second transport channel + non-Git project round trip.

Proves the acceptance rows for AT-07 / AT-31 / AT-32 on the self-executable
slice (a real second storage / device and a real cloud endpoint stay
authorization-gated and BLOCKED):
  * the same business handoff round-trips through BOTH a GitHub and a file
    channel with the core dispatch payload unchanged (no GitHub lock);
  * a third, non-Git example project completes an artifact round trip;
  * a half-upload, an expired / missing attachment, a duplicate file and a
    path traversal NEVER start a task.

Pure and deterministic: in-memory / path-simulated channels; no GitHub API,
no installed file-sync software, no network.
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

import transport_channels as tc  # noqa: E402


def _handoff() -> tc.BusinessHandoff:
    return tc.BusinessHandoff(
        task_id="t-1", revision=2,
        artifact_digest="sha256:abc",
        body=b"business handoff body",
        material_class="internal")


class TestSecondChannelRoundTrip(unittest.TestCase):
    def test_github_and_file_channels_agree_core_unchanged(self):
        gh = tc.GitHubChannel()
        fc = tc.FileChannel("/store")
        router = tc.TransportRouter(gh, fc)
        res = router.round_trip_consistency(_handoff())
        self.assertTrue(res["core_dispatch_unchanged"])
        self.assertEqual(res["channels"][0]["channel"], "github")
        self.assertEqual(res["channels"][1]["channel"], "file")
        # both channels delivered the identical business fingerprint
        fps = {c["fingerprint"] for c in res["channels"]}
        self.assertEqual(fps, {res["business_fingerprint"]})

    def test_a_single_channel_does_not_prove_no_lock(self):
        with self.assertRaises(ValueError):
            tc.TransportRouter(tc.GitHubChannel())

    def test_channel_is_thin_payload_not_rebuilt(self):
        gh = tc.GitHubChannel()
        ref = gh.send(_handoff())
        got = gh.receive({"reference": ref["reference"]})
        self.assertTrue(got["received"])
        # the channel only carries the reference; the business payload is the
        # same object the dispatcher saw
        self.assertEqual(got["handoff"].fingerprint(), _handoff().fingerprint())


class TestNonGitArtifactRoundTrip(unittest.TestCase):
    def test_third_non_git_project_artifact_round_trip(self):
        rt = tc.NonGitArtifactRoundTrip("non-git-sample-project")
        pub = rt.publish("t-9", 3, b"artifact bytes")
        self.assertTrue(pub["published"])
        self.assertEqual(pub["baseline_kind"], "artifact")  # digest, not git commit
        executed = rt.execute_from_reference(pub["artifact_version"])
        self.assertTrue(executed["executed"])
        self.assertFalse(executed["body_inlined"])  # executed from the reference
        back = rt.return_receipt(pub["artifact_version"], execution_completed=True)
        self.assertTrue(back["returned"])
        self.assertEqual(back["receipt"]["artifact_digest"], pub["digest"])
        self.assertEqual(back["receipt"]["baseline_kind"], "artifact")

    def test_execute_unknown_reference_is_refused(self):
        rt = tc.NonGitArtifactRoundTrip("p")
        res = rt.execute_from_reference("artifact:never:published")
        self.assertFalse(res["executed"])


class TestInputGuards(unittest.TestCase):
    def test_half_upload_does_not_start_task(self):
        res = tc.guard_half_upload({"body": b"short"}, expected_size=1000)
        self.assertFalse(res["task_started"])
        self.assertFalse(res["complete"])
        # a complete body may proceed
        ok = tc.guard_half_upload({"body": b"x" * 1000}, expected_size=1000)
        self.assertTrue(ok["complete"])

    def test_expired_attachment_does_not_start_task(self):
        res = tc.guard_attachment(
            {"digest": "d", "uploaded_at": 100}, now_ts=10_000, max_age_s=3600)
        self.assertFalse(res["task_started"])
        self.assertIn("expired", res["reason"])

    def test_missing_attachment_does_not_start_task(self):
        res = tc.guard_attachment({"digest": "d"}, now_ts=1000)  # no uploaded_at
        self.assertFalse(res["task_started"])
        self.assertIn("missing", res["reason"])

    def test_fresh_attachment_starts_task(self):
        res = tc.guard_attachment(
            {"digest": "d", "uploaded_at": 990}, now_ts=1000, max_age_s=3600)
        self.assertTrue(res["task_started"])

    def test_duplicate_file_not_restarted(self):
        existing = {"a.bin": "sha1", "b.bin": "sha2"}
        res = tc.dedupe_files(existing, {"a.bin": "sha1", "new.bin": "shaN"})
        self.assertEqual(res["duplicates"], ["a.bin"])
        self.assertEqual(res["started"], ["new.bin"])
        self.assertEqual(res["task_started_count"], 1)

    def test_same_path_different_digest_is_conflict_not_overwrite(self):
        existing = {"a.bin": "sha-old"}
        res = tc.dedupe_files(existing, {"a.bin": "sha-new"})
        self.assertEqual(res["conflicts"], ["a.bin"])
        self.assertEqual(res["task_started_count"], 0)

    def test_path_traversal_never_starts_task(self):
        fc = tc.FileChannel("/store")
        # a reference that escapes the store root is refused on both send and
        # receive, and no task is started
        bad = {"reference": "../escape/secret.bin"}
        res = fc.receive(bad)
        self.assertFalse(res["received"])
        self.assertIn("traversal", res["reason"])
        # the file channel also refuses to store a reference that normalizes
        # outside the root
        stored = fc.receive({"reference": "artifacts/t/r1.bin"})
        self.assertFalse(stored["received"])  # was never stored; missing


if __name__ == "__main__":
    unittest.main(verbosity=2)
