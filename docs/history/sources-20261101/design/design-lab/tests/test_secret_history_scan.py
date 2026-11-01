#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Unit tests for scripts/verify_secret_history.py (DL-CLOUDAUDIT-B1 / G-1).

Hermetic: the core scanner is exercised with an injected blob provider (no git,
no network, no repo mutation), plus one small throwaway git repository in
TMPDIR to prove the rev-list + cat-file --batch plumbing. Credential-shaped
literals are assembled from fragments so this test file cannot be flagged by
the very scanner it tests.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import scripts.verify_secret_history as vsh  # noqa: E402

FAKE_AWS_KEY = "AKIA" + "TESTHISTORYKEY0000"
FAKE_OPENAI = "sk-" + "a" * 32
# Synthetic vector: generic-secret-shaped (keyword + 16+ char value) with an
# in-value "fake" marker, so is_synthetic() exempts it anywhere in the tree.
SYNTHETIC_LINE = "token: 'fake-test-value-for-scan-0000'"
# Adjudicated vector: credential-shaped (AWS key is exactly AKIA + 16), no
# in-value marker; exempted only because its exact sha256 is pinned in the
# adjudications map.
ADJUDICATED_KEY = "AKIA" + "ADJUDICATEDV1234"
ADJUDICATED_DIGEST = "sha256:" + hashlib.sha256(ADJUDICATED_KEY.encode()).hexdigest()


class ScanCoreTest(unittest.TestCase):
    """The pure core: exemption rules must be importable, never re-invented."""

    def _fetch(self, blobs: dict):
        def fetch(path: str, blob: str):
            if (path, blob) not in blobs:
                return ("missing", None)
            return ("blob", blobs[(path, blob)])
        return fetch

    def test_credential_in_history_is_detected_and_redacted(self):
        body = f"AKIA_TEST = '{FAKE_AWS_KEY}'\n".encode()
        by_path = {"src/config.py": {"b1": "fake"}}
        out = vsh.scan_blob_map(by_path, self._fetch({("src/config.py", "b1"): body}), {})
        self.assertEqual(len(out["hits"]), 1)
        hit = out["hits"][0]
        self.assertEqual(hit["pattern"], "aws-key")
        self.assertEqual(hit["path"], "src/config.py")
        # redaction contract: the raw value must not appear anywhere in the record
        self.assertNotIn(FAKE_AWS_KEY, json.dumps(out))
        self.assertTrue(out["failures"] == [])
        self.assertFalse(vsh.main_ok(out))

    def test_synthetic_marker_exempts_value(self):
        body = (SYNTHETIC_LINE + "\n").encode()
        out = vsh.scan_blob_map({"src/x.py": {"b1": "x"}},
                                 self._fetch({("src/x.py", "b1"): body}), {})
        self.assertEqual(out["exempted_synthetic"], 1)
        self.assertEqual(out["hits"], [])

    def test_underscore_your_marker_exempts_doc_placeholder(self):
        # Inert research/reference docs use YOUR_* stand-ins. The marker rule
        # is value-based (never a path rule): the same shape caught anywhere
        # is exempt, but a credential with a real in-value marker set is not.
        body = b'api_key: "YOUR_RAPIDAPI_KEY"\n'
        out = vsh.scan_blob_map({"research/x.md": {"b1": "x"}},
                                 self._fetch({("research/x.md", "b1"): body}), {})
        self.assertEqual(out["exempted_synthetic"], 1)
        self.assertEqual(out["hits"], [])

    def test_real_aws_key_still_caught_in_research_path(self):
        # Path-based exemption must NOT rescue a credential-shaped value in a
        # non-test path: the value has no synthetic marker, so it is a hit.
        body = ("aws_key = '" + FAKE_AWS_KEY + "'\n").encode()
        out = vsh.scan_blob_map({"research/x.md": {"b1": "x"}},
                                 self._fetch({("research/x.md", "b1"): body}), {})
        self.assertEqual(len(out["hits"]), 1)
        self.assertEqual(out["hits"][0]["pattern"], "aws-key")

    def test_adjudication_pins_exactly_one_value(self):
        body = f"a='{ADJUDICATED_KEY}' b='{FAKE_OPENAI}'\n".encode()
        out = vsh.scan_blob_map({"src/a.py": {"b1": "x"}},
                                self._fetch({("src/a.py", "b1"): body}),
                                {ADJUDICATED_DIGEST: {"reason": "test vector",
                                                      "adjudicated_by": "DL-CLOUDAUDIT-B1"}})
        self.assertEqual(out["exempted_adjudicated"], 1)
        self.assertEqual(len(out["hits"]), 1)
        self.assertEqual(out["hits"][0]["pattern"], "openai-key")

    def test_unfetchable_blob_fails_closed(self):
        def fetch(path, blob):
            return ("missing", None)
        out = vsh.scan_blob_map({"src/a.py": {"b1": "x"}}, fetch, {})
        self.assertIn("unfetchable blob src/a.py@b1", out["failures"])
        self.assertFalse(vsh.main_ok(out))

    def test_tree_and_commit_ids_are_skipped_not_failed(self):
        def fetch(path, blob):
            return ("tree", None) if blob == "t1" else ("commit", None)
        out = vsh.scan_blob_map({"x": {"t1": "t1", "c1": "c1"}}, fetch, {})
        self.assertEqual(out["skipped_tree_or_commit"], 2)
        self.assertEqual(out["failures"], [])
        self.assertEqual(out["blob_revisions_scanned"], 0)

    def test_oversize_blob_skipped_not_scanned(self):
        big = b"x" * (vsh.MAX_BLOB_BYTES + 1)
        out = vsh.scan_blob_map({"data.bin": {"b1": "x"}},
                                 self._fetch({("data.bin", "b1"): big}), {})
        self.assertEqual(out["skipped_oversize"], 1)
        self.assertEqual(out["blob_revisions_scanned"], 0)

    def test_self_output_path_excluded(self):
        body = f"key='{FAKE_AWS_KEY}'".encode()
        out = vsh.scan_blob_map({vsh.SELF_OUTPUT_REL: {"b1": "x"}},
                                 self._fetch({(vsh.SELF_OUTPUT_REL, "b1"): body}), {})
        self.assertEqual(out["hits"], [])
        self.assertEqual(out["blob_revisions_scanned"], 0)


class BatchPlumbingTest(unittest.TestCase):
    """The rev-list + cat-file --batch fetcher against a throwaway repo."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="dl-secret-hist-test"))
        self.repo = self.tmp / "repo"
        self.repo.mkdir()
        env = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
               "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}

        def git(*args):
            subprocess.run(["git", "-C", str(self.repo), *args], check=True,
                           capture_output=True, env=env, text=True)

        git("init", "-q")
        git("config", "user.name", "t")
        git("config", "user.email", "t@t")
        (self.repo / "a.py").write_text(f"KEY='{FAKE_AWS_KEY}'\n")
        git("add", "a.py")
        git("commit", "-qm", "c1")
        self.old_repo = vsh.REPO
        vsh.REPO = self.repo

    def tearDown(self):
        vsh.REPO = self.old_repo
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_all_map_covers_blob_revisions(self):
        by_path = vsh.blob_map_all()
        self.assertIn("a.py", by_path)
        self.assertEqual(len(by_path["a.py"]), 1)

    def test_batch_fetcher_roundtrip(self):
        prefetch, fetch_blob, cleanup = vsh.make_batch_fetcher()
        try:
            blob = next(iter(vsh.blob_map_all()["a.py"]))
            tree = vsh.git("rev-parse", "HEAD^{tree}")
            prefetch([blob, tree, "0" * 40])
            self.assertEqual(fetch_blob("a.py", blob)[0], "blob")
            self.assertIn(FAKE_AWS_KEY.encode(), fetch_blob("a.py", blob)[1])
            # a tree id must classify as tree, an unknown id as missing
            self.assertEqual(fetch_blob("a.py", tree), ("tree", None))
            self.assertEqual(fetch_blob("a.py", "0" * 40), ("missing", None))
            # repeated reads are served from cache, same result
            self.assertEqual(fetch_blob("a.py", blob)[0], "blob")
        finally:
            cleanup()

    def test_full_run_detects_history_credential(self):
        rc = vsh.main(["--head-only"])
        # the committed fake key is a real hit at this throwaway repo's HEAD
        self.assertEqual(rc, 1)
        report = json.loads((self.repo / "reports/current/SECRET-HISTORY-REPORT.json")
                            .read_text(encoding="utf-8"))
        self.assertEqual(report["hit_count"], 1)
        self.assertNotIn(FAKE_AWS_KEY, json.dumps(report))


if __name__ == "__main__":
    unittest.main()
