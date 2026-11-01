# SPDX-License-Identifier: MIT
"""DL-TP-T05 (MULTIMODAL-2026-09-05): asset registry + single-writer lock tests.

Covers the plan §8 guarantees: restart-recoverable records, idempotent retry
(no double artifact creation), failed/cancelled attempts never reported as
completed versions, and single-writer per document with recorded takeover.
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
import sys

SRC = Path(__file__).resolve().parents[2] / "src"
sys.path.insert(0, str(SRC))


class AssetStoreTests(unittest.TestCase):
    def _db(self):
        parent = SRC.parent / '.project-local/task-runtime/asset-store-tests'
        parent.mkdir(parents=True, exist_ok=True)
        tmp = tempfile.TemporaryDirectory(dir=parent)
        self.addCleanup(tmp.cleanup)
        return Path(tmp.name) / "assets.db"

    def test_create_and_restart_recovery(self):
        """A committed version survives close + reopen (restart recovery)."""
        from design_lab.runtime.asset_store import (
            connect, create_project, latest_active_version, record_version, register_asset,
        )

        db_path = self._db()
        conn = connect(db_path)
        create_project(conn, "p1", "demo")
        register_asset(conn, "p1", "poster", "psd")
        record_version(conn, "poster", "sha256:" + "a" * 64, artifacts=[("out.psd", "sha256:" + "b" * 64, 10, "deliverable")])
        conn.close()

        conn2 = connect(db_path)  # simulated restart
        active = latest_active_version(conn2, "poster")
        self.assertIsNotNone(active)
        self.assertEqual(active["content_sha256"], "sha256:" + "a" * 64)
        rows = conn2.execute("SELECT COUNT(*) FROM artifact").fetchone()[0]
        self.assertEqual(rows, 1)
        conn2.close()

    def test_duplicate_retry_is_idempotent(self):
        """Same content retried returns the existing version; no double artifacts."""
        from design_lab.runtime.asset_store import connect, create_project, record_version, register_asset

        conn = connect(self._db())
        create_project(conn, "p1", "demo")
        register_asset(conn, "p1", "poster", "psd")
        v1 = record_version(conn, "poster", "sha256:" + "c" * 64, artifacts=[("a.psd", "sha256:" + "d" * 64, 10, "deliverable")])
        v2 = record_version(conn, "poster", "sha256:" + "c" * 64, artifacts=[("a.psd", "sha256:" + "d" * 64, 10, "deliverable")])
        self.assertEqual(v1, v2)
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM asset_version").fetchone()[0], 1)
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM artifact").fetchone()[0], 1)
        conn.close()

    def test_failed_attempt_never_reported_completed(self):
        """A FAILED record stays FAILED; latest_active_version does not return it."""
        from design_lab.runtime.asset_store import connect, create_project, latest_active_version, record_version, register_asset

        conn = connect(self._db())
        create_project(conn, "p1", "demo")
        register_asset(conn, "p1", "poster", "psd")
        record_version(conn, "poster", "sha256:" + "e" * 64, state="FAILED")
        self.assertIsNone(latest_active_version(conn, "poster"))
        conn.close()

    def test_cancelled_state_never_promoted_by_retry(self):
        """Retrying content that previously ended CANCELLED must not flip to ACTIVE."""
        from design_lab.runtime.asset_store import connect, create_project, record_version, register_asset

        conn = connect(self._db())
        create_project(conn, "p1", "demo")
        register_asset(conn, "p1", "poster", "psd")
        record_version(conn, "poster", "sha256:" + "f" * 64, state="CANCELLED")
        # a blind retry with ACTIVE must not silently override the cancelled terminal state
        returned = record_version(conn, "poster", "sha256:" + "f" * 64, state="ACTIVE")
        row = conn.execute(
            "SELECT state FROM asset_version WHERE version_id=?", (returned,)
        ).fetchone()
        self.assertEqual(row[0], "CANCELLED")
        conn.close()

    def test_single_writer_no_silent_takeover(self):
        """Second writer cannot acquire while held; takeover is explicit and audited."""
        from design_lab.runtime.asset_store import acquire_writer, connect, release_writer, takeover_writer

        conn = connect(self._db())
        self.assertTrue(acquire_writer(conn, "doc:poster", "attempt-1"))
        self.assertFalse(acquire_writer(conn, "doc:poster", "attempt-2"))
        takeover_writer(conn, "doc:poster", "attempt-2")
        self.assertTrue(release_writer(conn, "doc:poster", "attempt-2", generation=2))
        self.assertTrue(acquire_writer(conn, "doc:poster", "attempt-3"))
        audits = conn.execute("SELECT COUNT(*) FROM audit_event WHERE action LIKE 'writer_takeover:%'").fetchone()[0]
        self.assertEqual(audits, 1)
        conn.close()


if __name__ == "__main__":
    unittest.main()
