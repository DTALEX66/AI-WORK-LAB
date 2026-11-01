# SPDX-License-Identifier: MIT
"""DL-P0-022 / DL-P0-032: version V2 lineage fields and the rejected guard."""
from __future__ import annotations

import sqlite3
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest import mock
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from design_lab.creative import asset_versions, creative_job, store, version_guard  # noqa: E402


def brief():
    return {
        "schemaVersion": "design-lab/creative-job/v1",
        "project_id": "p-guard",
        "brief_ref": {"brief_id": "brief-guard", "sha256": "sha256:" + "a" * 64},
        "rights_profile": {"profile_id": "rights-1", "gate_state": "CHECKED"},
        "deliverables": [{"deliverable_id": "poster", "asset_kind": "psd",
                          "host_target": "photoshop-2025", "editable": True}],
        "host_targets": [{"host_id": "photoshop-2025", "mode": "process-isolated",
                          "editable_source": True, "evidence_level": "E2"}],
    }


class VersionGuardTests(unittest.TestCase):
    def setUp(self):
        parent = ROOT / '.project-local/task-runtime/creative-guard-tests'
        parent.mkdir(parents=True, exist_ok=True)
        temporary = tempfile.TemporaryDirectory(dir=parent)
        self.addCleanup(temporary.cleanup)
        self.conn = store.connect(Path(temporary.name) / 'creative.db')
        self.addCleanup(self.conn.close)
        created = creative_job.create_job(self.conn, brief(), idempotency_scope="s", idempotency_key="job")
        self.job_id = created["job_id"]
        asset_versions.register_asset_for_job(self.conn, self.job_id, "poster", "psd")

    def _version(self, digit, **kwargs):
        return asset_versions.create_version(
            self.conn, "poster", "sha256:" + digit * 64,
            artifacts=[(f"v{digit}.psd", "sha256:" + digit * 64, 256, "deliverable")], **kwargs)

    def test_v2_fields_record_parent_branch_and_generation(self):
        root = self._version("1")
        child = self._version("2", parent_version_id=root["version_id"], branch="main", label="candidate")
        self.assertTrue(child["created"])
        self.assertEqual(child["generation"], 2)
        self.assertEqual(child["parent_version_id"], root["version_id"])
        stored = asset_versions.version(self.conn, child["version_id"])
        self.assertEqual(stored["branch"], "main")
        self.assertEqual(stored["label"], "candidate")
        self.assertEqual(asset_versions.version(self.conn, root["version_id"])["generation"], 1)

    def test_chain_is_root_first_and_carries_branch_metadata(self):
        root = self._version("1")
        child = self._version("2", parent_version_id=root["version_id"])
        grandchild = self._version("3", parent_version_id=child["version_id"], branch="main")
        walk = asset_versions.chain(self.conn, grandchild["version_id"])
        self.assertEqual([node["version_id"] for node in walk],
                         [root["version_id"], child["version_id"], grandchild["version_id"]])
        self.assertEqual([node["generation"] for node in walk], [1, 2, 3])

    def test_identical_bytes_reuse_the_existing_version(self):
        first = self._version("1")
        again = asset_versions.create_version(
            self.conn, "poster", "sha256:" + "1" * 64,
            artifacts=[("v1.psd", "sha256:" + "1" * 64, 256, "deliverable")],
            parent_version_id=None, branch="other-branch")
        self.assertFalse(again["created"])
        self.assertEqual(again["version_id"], first["version_id"])
        self.assertEqual(asset_versions.version(self.conn, first["version_id"])["branch"], "main")

    def test_fork_moves_to_a_new_branch_and_rejects_a_same_branch_fork(self):
        root = self._version("1")
        forked = asset_versions.fork(self.conn, root["version_id"], branch="alternate",
                                     content_sha256="sha256:" + "4" * 64,
                                     artifacts=[("alt.psd", "sha256:" + "4" * 64, 64, "deliverable")])
        self.assertEqual(asset_versions.version(self.conn, forked["version_id"])["branch"], "alternate")
        with self.assertRaisesRegex(store.CreativeError, "new branch name"):
            asset_versions.fork(self.conn, root["version_id"], branch="main",
                                content_sha256="sha256:" + "5" * 64)

    def test_parent_must_belong_to_the_same_asset(self):
        other = asset_versions.create_version
        asset_versions.register_asset_for_job(self.conn, self.job_id, "logo", "vector")
        foreign = other(self.conn, "logo", "sha256:" + "9" * 64,
                        artifacts=[("logo.svg", "sha256:" + "9" * 64, 32, "deliverable")])
        with self.assertRaisesRegex(store.CreativeError, "different asset"):
            self._version("2", parent_version_id=foreign["version_id"])

    def test_branch_tip_and_branch_inventory(self):
        root = self._version("1")
        child = self._version("2", parent_version_id=root["version_id"])
        self._version("3", parent_version_id=root["version_id"], branch="alternate")
        self.assertEqual(asset_versions.branch_tip(self.conn, "poster", "main"), child["version_id"])
        self.assertEqual([row["branch"] for row in asset_versions.branches(self.conn, "poster")],
                         ["alternate", "main"])

    def test_branch_inventory_tip_uses_version_order_not_uuid_order(self):
        # A UUID is an identity, not a version ordering. Keep this counterexample
        # in the repository so branches() cannot regress to MAX(version_id).
        uuids = [
            SimpleNamespace(hex="f" * 32), SimpleNamespace(hex="e" * 32),
            SimpleNamespace(hex="0" * 32), SimpleNamespace(hex="1" * 32),
        ]
        with mock.patch.object(asset_versions.asset_store.uuid, "uuid4", side_effect=uuids):
            root = self._version("1")
            child = self._version("2", parent_version_id=root["version_id"])
        rows = asset_versions.branches(self.conn, "poster")
        self.assertEqual(rows, [{"branch": "main", "versions": 2, "tip": child["version_id"]}])

    def test_rejection_is_terminal_and_blocks_serving(self):
        version = self._version("1")
        recorded = version_guard.reject_version(self.conn, version["version_id"], reason="off-brand",
                                                actor="DTALEX66", evidence_ref="review-2026-09-13")
        self.assertTrue(recorded["created"])
        self.assertTrue(version_guard.is_rejected(self.conn, version["version_id"]))
        self.assertEqual(version_guard.rejection_status(self.conn, version["version_id"]), "REJECTED")
        with self.assertRaisesRegex(store.CreativeError, "not servable"):
            version_guard.assert_servable(self.conn, version["version_id"])
        with self.assertRaisesRegex(store.CreativeError, "not servable"):
            version_guard.guard_delivery(self.conn, [version["version_id"]])

    def test_rejection_replay_is_idempotent_but_a_different_one_is_refused(self):
        version = self._version("1")
        version_guard.reject_version(self.conn, version["version_id"], reason="off-brand",
                                     actor="DTALEX66", evidence_ref="review-1")
        replay = version_guard.reject_version(self.conn, version["version_id"], reason="off-brand",
                                              actor="DTALEX66", evidence_ref="review-1")
        self.assertFalse(replay["created"])
        with self.assertRaisesRegex(store.CreativeError, "terminal"):
            version_guard.reject_version(self.conn, version["version_id"], reason="changed mind",
                                         actor="DTALEX66", evidence_ref="review-2")

    def test_rejection_never_rewrites_the_version_row(self):
        version = self._version("1")
        before = asset_versions.version(self.conn, version["version_id"])
        version_guard.reject_version(self.conn, version["version_id"], reason="off-brand",
                                     actor="DTALEX66", evidence_ref="review-1")
        self.assertEqual(asset_versions.version(self.conn, version["version_id"]), before)

    def test_rejection_record_is_append_only_against_direct_sql(self):
        version = self._version("1")
        version_guard.reject_version(self.conn, version["version_id"], reason="off-brand",
                                     actor="DTALEX66", evidence_ref="review-1")
        version_guard.assert_append_only(self.conn)
        with self.assertRaises(sqlite3.DatabaseError):
            self.conn.execute("DELETE FROM version_rejection WHERE version_id=?", (version["version_id"],))
        self.conn.rollback()

    def test_failed_or_cancelled_versions_are_not_servable(self):
        failed = asset_versions.create_version(self.conn, "poster", "sha256:" + "7" * 64,
                                               state="FAILED", artifacts=[("f.psd", "sha256:" + "7" * 64, 8, "x")])
        self.assertEqual(version_guard.rejection_status(self.conn, failed["version_id"]), "FAILED")
        with self.assertRaisesRegex(store.CreativeError, "FAILED"):
            version_guard.assert_servable(self.conn, failed["version_id"])

    def test_rejected_parent_cannot_spawn_a_child_version(self):
        version = self._version("1")
        version_guard.reject_version(self.conn, version["version_id"], reason="off-brand",
                                     actor="DTALEX66", evidence_ref="review-1")
        with self.assertRaisesRegex(store.CreativeError, "not servable"):
            self._version("2", parent_version_id=version["version_id"])

    def test_servable_listing_excludes_rejected_versions(self):
        keep = self._version("1")
        drop = self._version("2", parent_version_id=keep["version_id"])
        version_guard.reject_version(self.conn, drop["version_id"], reason="bad crop",
                                     actor="DTALEX66", evidence_ref="review-2")
        servable = [row["version_id"] for row in version_guard.servable_versions(self.conn, "poster")]
        self.assertEqual(servable, [keep["version_id"]])
        self.assertEqual([row["version_id"] for row in version_guard.rejected_versions(self.conn, "poster")],
                         [drop["version_id"]])


if __name__ == "__main__":
    unittest.main()
