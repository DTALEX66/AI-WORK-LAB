# SPDX-License-Identifier: MIT
"""Wave B migration: additive only, backed up, and invisible to v1 writers."""
from __future__ import annotations

import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from design_lab.creative import store  # noqa: E402
from design_lab.runtime import asset_store  # noqa: E402

WAVE_B_TABLES = {
    "creative_job", "creative_job_deliverable", "operation_lineage", "lineage_input",
    "lineage_output", "version_rejection", "requirement_event", "decision_event",
    "worklab_session_link",
}


class CreativeMigrationTests(unittest.TestCase):
    def setUp(self):
        parent = ROOT / '.project-local/task-runtime/creative-migration-tests'
        parent.mkdir(parents=True, exist_ok=True)
        temporary = tempfile.TemporaryDirectory(dir=parent)
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)

    def _legacy(self) -> Path:
        db = self.root / "legacy.db"
        conn = sqlite3.connect(db)
        conn.executescript(asset_store._BASE_SCHEMA.read_text(encoding="utf-8"))
        conn.executescript(asset_store._SCHEMA.read_text(encoding="utf-8"))
        conn.execute("INSERT INTO project VALUES ('p','demo','2026-09-13T00:00:00+00:00')")
        conn.execute("INSERT INTO asset VALUES ('poster','p','psd','2026-09-13T00:00:00+00:00')")
        conn.execute("INSERT INTO asset_version (version_id, asset_id, version_no, content_sha256, state, created_at) "
                     "VALUES ('v-legacy','poster',1,?,'ACTIVE','2026-09-13T00:00:00+00:00')",
                     ("sha256:" + "a" * 64,))
        conn.execute("INSERT INTO artifact VALUES ('a-1','v-legacy','legacy.psd',?,64,'output')",
                     ("sha256:" + "a" * 64,))
        conn.commit()
        conn.close()
        return db

    def test_fresh_database_gets_wave_b_tables(self):
        conn = store.connect(self.root / "fresh.db")
        self.addCleanup(conn.close)
        tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        self.assertTrue(WAVE_B_TABLES <= tables, WAVE_B_TABLES - tables)
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM runtime_migration WHERE name='creative-v1'")
                         .fetchone()[0], 1)

    def test_populated_database_is_backed_up_and_preserved(self):
        db = self._legacy()
        conn = store.connect(db)
        self.addCleanup(conn.close)
        backups = list(self.root.glob("legacy.db.pre-creative-v1-*.bak"))
        self.assertEqual(len(backups), 1, "populated database must be backed up before migrating")
        backup = sqlite3.connect(backups[0])
        try:
            columns = [row[1] for row in backup.execute("PRAGMA table_info(asset_version)")]
        finally:
            backup.close()
        self.assertEqual(columns, ["version_id", "asset_id", "version_no", "content_sha256", "state", "created_at"])
        row = conn.execute("SELECT version_id, content_sha256, state, branch, generation, parent_version_id "
                           "FROM asset_version WHERE version_id='v-legacy'").fetchone()
        self.assertEqual(row, ("v-legacy", "sha256:" + "a" * 64, "ACTIVE", "main", 1, None))
        self.assertEqual(conn.execute("PRAGMA foreign_key_check").fetchall(), [])

    def test_reconnect_is_a_no_op(self):
        db = self._legacy()
        first = store.connect(db)
        first.close()
        second = store.connect(db)
        self.addCleanup(second.close)
        self.assertEqual(len(list(self.root.glob("legacy.db.pre-creative-v1-*.bak"))), 1)

    def test_v1_writer_still_works_after_migration(self):
        db = self._legacy()
        conn = store.connect(db)
        self.addCleanup(conn.close)
        version_id = asset_store.record_version(
            conn, "poster", "sha256:" + "b" * 64,
            artifacts=[("next.psd", "sha256:" + "b" * 64, 128, "deliverable")])
        self.assertEqual(asset_store.latest_active_version(conn, "poster")["version_id"], version_id)
        row = conn.execute("SELECT version_no, branch, generation FROM asset_version WHERE version_id=?",
                           (version_id,)).fetchone()
        self.assertEqual(row, (2, "main", 1))

    def test_migration_does_not_lose_writer_locks_or_publications(self):
        db = self._legacy()
        conn = store.connect(db)
        self.addCleanup(conn.close)
        self.assertTrue(asset_store.acquire_writer(conn, "asset:poster", "attempt-1"))
        generation = asset_store.writer_token(conn, "asset:poster", "attempt-1")
        self.assertTrue(asset_store.release_writer(conn, "asset:poster", "attempt-1", generation=generation))
        with self.assertRaises(asset_store.AssetError):
            asset_store.writer_token(conn, "asset:poster", "attempt-1")
        self.assertEqual(conn.execute("SELECT state FROM asset_writer_lock").fetchone()[0], "RELEASED")


if __name__ == "__main__":
    unittest.main()
