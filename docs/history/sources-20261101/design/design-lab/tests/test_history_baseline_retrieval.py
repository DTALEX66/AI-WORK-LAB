# SPDX-License-Identifier: MIT
"""History baseline retrieval fixture (PR115 audit F09).

The frozen history artifacts (evidence manifest + task-id crosswalk CSVs) must
be present in the committed tree and byte-identical to the hashes sealed in
reports/history-baseline.json — otherwise the baseline is not retrievable.
"""
from __future__ import annotations

import hashlib
import json
import csv
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]  # repo root
BASELINE = ROOT / "reports" / "history-baseline.json"
R3_INPUTS = ROOT / "docs" / "history" / "r3-audit-inputs-2026-09-06"


class HistoryBaselineRetrievalTests(unittest.TestCase):
    def test_r3_verified_git_locators_actually_retrieve_original_bytes(self):
        path = ROOT / "docs/history/r3-recovery-2026-09-07-public-complete.json"
        self.assertTrue(path.is_file(), "Per-record recovery manifest missing")
        recovery = json.loads(path.read_text(encoding="utf-8"))
        commit = recovery["repo_sha"]
        self.assertRegex(commit, r"^[0-9a-f]{40}$")
        listing = subprocess.check_output(["git", "ls-tree", "-rz", "--full-tree", commit], cwd=ROOT)
        tree = {}
        for entry in listing.split(b"\0"):
            if entry:
                metadata, name = entry.split(b"\t", 1)
                mode, kind, oid = metadata.decode("ascii").split()
                if kind == "blob" and mode in {"100644", "100755"}:
                    tree[name.decode("utf-8")] = oid
        observed = {}
        for row in recovery["records"]:
            for locator in row["verified_locators"]:
                self.assertEqual(locator["git_commit"], commit)
                self.assertEqual(tree[locator["path"]], locator["git_blob_oid"])
                oid = locator["git_blob_oid"]
                if oid not in observed:
                    raw = subprocess.check_output(["git", "cat-file", "blob", oid], cwd=ROOT)
                    observed[oid] = (len(raw), hashlib.sha256(raw).hexdigest())
                self.assertEqual(observed[oid], (row["size_bytes"], row["sha256"]))
        self.assertEqual(len(observed), 136)

    def test_r3_recovery_classifies_all_records_without_promoting_placeholders(self):
        path = ROOT / "docs/history/r3-recovery-2026-09-07-public-complete.json"
        self.assertTrue(path.is_file(), "Per-record recovery manifest missing")
        recovery = json.loads(path.read_text(encoding="utf-8"))
        rows = recovery["records"]
        self.assertEqual(len(rows), 536)
        self.assertEqual(len({row["record_id"] for row in rows}), 536)
        self.assertFalse(recovery["history_complete"])
        placeholders = [row for row in rows if row["material_state"] == "transport_placeholder"]
        self.assertEqual(len(placeholders), 4)
        for row in placeholders:
            self.assertEqual(row["state"], "TRANSPORT_PLACEHOLDER")
            self.assertEqual(row["verified_locators"], [])
        unresolved = [row for row in rows if row["state"] == "UNRESOLVED"]
        self.assertGreaterEqual(len(unresolved), 260)
        for row in unresolved:
            self.assertEqual(row["verified_locators"], [])
            self.assertTrue(row["reason"])
        for row in rows:
            if row["state"] == "RETRIEVABLE_GIT_BLOB":
                self.assertTrue(row["verified_locators"])
                for locator in row["verified_locators"]:
                    self.assertEqual(locator["sha256"], row["sha256"])
                    self.assertEqual(locator["size_bytes"], row["size_bytes"])
                    self.assertEqual(len(locator["git_blob_oid"]), 40)

    def test_r3_audit_inputs_retrievable_with_original_bytes(self):
        # Losing either archive-only queue made R3-03 non-self-contained.
        expected = {
            "history-current-tree-coverage.json": (262249, "46e2504f51caa61e7287b201da2977946f28324a38f7bc40cf9ebd386489ff96"),
            "old-new-crosswalk.csv": (3152, "a52e0a01e3cd3c89ea6dcc7d818e221676bdea5619a9acfe353dd2df7a942eea"),
        }
        for name, (size, digest) in expected.items():
            with self.subTest(name=name):
                path = R3_INPUTS / name
                self.assertTrue(path.is_file(), f"R3 audit input not recoverable in checkout: {name}")
                raw = path.read_bytes()
                self.assertEqual(len(raw), size)
                self.assertEqual(hashlib.sha256(raw).hexdigest(), digest)

    def test_r3_coverage_preserves_every_frozen_manifest_identity(self):
        path = R3_INPUTS / "history-current-tree-coverage.json"
        self.assertTrue(path.is_file(), "R3 coverage queue missing")
        coverage = json.loads(path.read_text(encoding="utf-8-sig"))
        with (ROOT / "docs/history/DESIGN-LAB-HISTORY-EVIDENCE-MANIFEST-2026-09-04.csv").open(encoding="utf-8-sig", newline="") as stream:
            manifest = list(csv.DictReader(stream))
        self.assertEqual(len(coverage), 536)
        self.assertEqual(len({row["record_id"] for row in coverage}), 536)
        self.assertEqual(
            {(row["record_id"], row["sha256"], row["declared_material_state"]) for row in coverage},
            {(row["record_id"], row["sha256"], row["material_state"]) for row in manifest},
        )
        self.assertEqual(sum(row["current_tree_retrieval"] == "NOT_PROVEN_IN_CURRENT_TREE" for row in coverage), 260)
        self.assertEqual(sum(row["declared_material_state"] == "transport_placeholder" for row in coverage), 4)

    def test_r3_legacy_bridge_targets_existing_tasks_without_erasing_scope(self):
        path = R3_INPUTS / "old-new-crosswalk.csv"
        self.assertTrue(path.is_file(), "Legacy-to-R3 bridge missing")
        with path.open(encoding="utf-8-sig", newline="") as stream:
            rows = list(csv.DictReader(stream))
        active = json.loads((ROOT / "design-lab/config/task-ledger-r3.json").read_text(encoding="utf-8"))
        # R5 preserves this R3 bridge as history; its targets must resolve in
        # the sealed predecessor, not in the differently named R5 task set.
        frozen = (ROOT / 'docs/history/taskpacks/r3-ledger-pre-r5-20260909.json').read_bytes()
        predecessor = active['predecessor']
        self.assertEqual(predecessor['taskpack'], 'DL-TP-20260906-R3')
        self.assertEqual(hashlib.sha256(frozen).hexdigest(), predecessor['sha256'])
        self.assertEqual(predecessor['ledger'], json.loads(frozen))
        task_ids = {row['id'] for row in predecessor['ledger']['tasks']}
        self.assertEqual(len(rows), 28)
        self.assertEqual(len({(row["legacy_source"], row["legacy_id"]) for row in rows}), 28)
        for row in rows:
            with self.subTest(legacy=row["legacy_id"]):
                targets = set(row["new_targets"].split("|"))
                self.assertTrue(targets)
                self.assertTrue(targets <= task_ids)
                self.assertTrue(row["disposition"].startswith("SCOPE_PRESERVED"))

    def test_baseline_exists(self):
        self.assertTrue(BASELINE.is_file(), "reports/history-baseline.json missing")

    def test_frozen_csvs_exist_and_match_sealed_hashes(self):
        baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
        expected = {
            "historyManifestSha": "docs/history/DESIGN-LAB-HISTORY-EVIDENCE-MANIFEST-2026-09-04.csv",
            "historyCrosswalkSha": "docs/history/DESIGN-LAB-HISTORY-TASK-ID-CROSSWALK-2026-09-04.csv",
        }
        for key, rel in expected.items():
            sealed = baseline.get(key)
            self.assertTrue(sealed, f"{key} missing from history-baseline.json")
            path = ROOT / rel
            self.assertTrue(path.is_file(), f"baseline artifact not in tree: {rel}")
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            self.assertEqual(digest, sealed, f"{rel} no longer matches sealed {key}")

    def test_crosswalk_retrievable_rows(self):
        csv = ROOT / "docs/history/DESIGN-LAB-HISTORY-TASK-ID-CROSSWALK-2026-09-04.csv"
        self.assertTrue(csv.is_file())
        header = csv.read_text(encoding="utf-8").splitlines()[0].lower()
        self.assertIn("occurrence", header)
        with csv.open(encoding="utf-8") as stream:
            self.assertGreaterEqual(sum(1 for _ in stream), 1000)


if __name__ == "__main__":
    unittest.main(verbosity=2)
