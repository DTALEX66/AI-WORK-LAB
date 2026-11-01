# SPDX-License-Identifier: MIT
"""R3-06 transaction, lease/fencing and immutable-file publication regressions."""
from concurrent.futures import ThreadPoolExecutor
import hashlib
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from design_lab.runtime import asset_store as assets


class AssetSafetyTests(unittest.TestCase):
    def setUp(self):
        runtime = ROOT / ".project-local/task-runtime/r3-asset-tests"
        runtime.mkdir(parents=True, exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(dir=runtime)
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.db = self.root / "assets.db"
        self.conn = assets.connect(self.db)
        self.addCleanup(self.conn.close)
        assets.create_project(self.conn, "project", "Fixture")
        assets.register_asset(self.conn, "project", "poster", "psd")

    def record(self, char, **kwargs):
        return assets.record_version(self.conn, "poster", "sha256:" + char * 64,
                                     artifacts=[("poster.psd", "sha256:" + char * 64, 1, "output")], **kwargs)

    def acquire(self, holder="worker"):
        self.assertTrue(assets.acquire_writer(self.conn, "asset:poster", holder))
        return assets.writer_token(self.conn, "asset:poster", holder)

    def publish(self, content=b"PSD fixture one", *, token=None, holder="worker"):
        source = self.root / "source.psd"
        source.write_bytes(content)
        return assets.publish_version(self.conn, "poster", source, store_root=self.root / "store",
                                      artifact_name="poster.psd", expected_sha256=hashlib.sha256(content).hexdigest(),
                                      holder_attempt_id=holder, generation=token)

    def test_same_path_three_versions_use_independent_artifact_ids(self):
        versions = [self.record(char) for char in "abc"]
        rows = self.conn.execute("SELECT artifact_id,version_id,path FROM artifact").fetchall()
        self.assertEqual(len(set(row[0] for row in rows)), 3)
        self.assertEqual({row[1] for row in rows}, set(versions))
        self.assertEqual({row[2] for row in rows}, {"poster.psd"})

    def test_scoped_recovery_preserves_other_attempt_staging(self):
        assets.register_asset(self.conn,'project','other','psd')
        token=self.acquire('owner')
        self.assertTrue(assets.acquire_writer(self.conn,'asset:other','other-owner'))
        other_token=assets.writer_token(self.conn,'asset:other','other-owner')
        source=self.root/'source.psd';source.write_bytes(b'controlled')
        for identity,holder,generation in [('poster','owner',token),('other','other-owner',other_token)]:
            with patch.object(assets,'_after_stage',side_effect=OSError('stopped at stage')):
                with self.assertRaises(OSError):
                    assets.publish_version(self.conn,identity,source,store_root=self.root/'store',artifact_name='native.psd',
                        expected_sha256=hashlib.sha256(b'controlled').hexdigest(),holder_attempt_id=holder,generation=generation)
        recovered=assets.recover_publications(self.conn,store_root=self.root/'store',asset_id='poster',
                                             holder_attempt_id='owner',generation=token)
        self.assertEqual(len(recovered),1)
        other=self.conn.execute("SELECT state,stage_path FROM asset_publication WHERE asset_id='other'").fetchone()
        self.assertEqual(other[0],'PREPARED')
        self.assertEqual(Path(other[1]).read_bytes(),b'controlled')
        with self.assertRaises(assets.AssetError):
            assets.recover_publications(self.conn,store_root=self.root/'store',asset_id='other')

    def test_expected_owner_takeover_cannot_fence_an_unrelated_writer(self):
        token=self.acquire('other-worker')
        with self.assertRaises(assets.AssetError):
            assets.takeover_writer(self.conn,'asset:poster','recovery',expected_holder='recovery')
        self.assertEqual(assets.writer_token(self.conn,'asset:poster','other-worker'),token)

    def test_failed_artifact_insert_cannot_leak_empty_active_version(self):
        self.record("a")
        self.conn.execute("CREATE TRIGGER reject_artifact BEFORE INSERT ON artifact "
                          "BEGIN SELECT RAISE(ABORT, 'injected artifact error'); END")
        with self.assertRaises(sqlite3.IntegrityError):
            self.record("b")
        self.assertFalse(self.conn.in_transaction)
        assets.create_project(self.conn, "unrelated", "commit must not leak failed version")
        self.assertEqual(self.conn.execute("SELECT version_no FROM asset_version").fetchall(), [(1,)])

    def test_new_active_version_requires_artifacts(self):
        with self.assertRaises(assets.AssetError):
            assets.record_version(self.conn, "poster", "a" * 64)

    def test_three_published_versions_preserve_old_bytes_after_restart(self):
        token = self.acquire()
        ids = [self.publish(content, token=token) for content in (b"first", b"second", b"third")]
        reopened = assets.connect(self.db)
        try:
            contents = []
            for vid in ids:
                path, = reopened.execute("SELECT path FROM artifact WHERE version_id=?", (vid,)).fetchone()
                contents.append(Path(path).read_bytes())
            self.assertEqual(contents, [b"first", b"second", b"third"])
        finally:
            reopened.close()

    def test_expired_and_replaced_tokens_cannot_publish_or_release(self):
        with patch.object(assets, "_clock", return_value=100):
            old = self.acquire()
        with patch.object(assets, "_clock", return_value=200):
            with self.assertRaises(assets.AssetError):
                self.publish(token=old)
            new = self.acquire("replacement")
            self.assertGreater(new, old)
            self.assertFalse(assets.release_writer(self.conn, "asset:poster", "worker", generation=old))
            with self.assertRaises(assets.AssetError):
                self.publish(token=old)
            self.publish(token=new, holder="replacement")

    def test_takeover_during_staging_fences_old_publisher(self):
        token = self.acquire()
        def takeover(*_):
            other = assets.connect(self.db)
            try:
                assets.takeover_writer(other, "asset:poster", "new-worker")
            finally:
                other.close()
        with patch.object(assets, "_after_stage", side_effect=takeover), self.assertRaises(assets.AssetError):
            self.publish(token=token)
        self.assertIsNone(assets.latest_active_version(self.conn, "poster"))

    def test_publish_db_failure_keeps_recoverable_journal_not_active(self):
        token = self.acquire()
        self.conn.execute("CREATE TRIGGER reject_artifact BEFORE INSERT ON artifact "
                          "BEGIN SELECT RAISE(ABORT, 'injected publication failure'); END")
        with self.assertRaises(sqlite3.IntegrityError):
            self.publish(token=token)
        self.assertIsNone(assets.latest_active_version(self.conn, "poster"))
        result = assets.recover_publications(self.conn, store_root=self.root / "store")
        self.assertEqual(result[0]["state"], "QUARANTINED")
        self.assertEqual(Path(result[0]["path"]).read_bytes(), b"PSD fixture one")
        self.assertEqual(self.conn.execute("PRAGMA foreign_key_check").fetchall(), [])

    def test_atomic_rename_failure_does_not_activate_metadata(self):
        token = self.acquire()
        with patch.object(assets.os, "replace", side_effect=OSError("rename failure")), self.assertRaises(OSError):
            self.publish(token=token)
        self.assertIsNone(assets.latest_active_version(self.conn, "poster"))
        self.assertEqual(assets.recover_publications(self.conn, store_root=self.root / "store")[0]["state"], "QUARANTINED")

    def test_parallel_acquire_grants_one_holder(self):
        barrier = threading.Barrier(2)
        def acquire(holder):
            conn = assets.connect(self.db)
            try:
                barrier.wait(timeout=10)
                return assets.acquire_writer(conn, "asset:poster", holder)
            finally:
                conn.close()
        with ThreadPoolExecutor(2) as pool:
            self.assertEqual(sorted(pool.map(acquire, ["one", "two"])), [False, True])

    def test_bad_hash_and_traversal_never_create_active_artifact(self):
        token = self.acquire()
        source = self.root / "source.psd"
        source.write_bytes(b"data")
        for name, digest in (("../outside.psd", hashlib.sha256(b"data").hexdigest()), ("poster.psd", "a" * 64)):
            with self.subTest(name=name), self.assertRaises(assets.AssetError):
                assets.publish_version(self.conn, "poster", source, store_root=self.root / "store",
                                       artifact_name=name, expected_sha256=digest,
                                       holder_attempt_id="worker", generation=token)
        self.assertIsNone(assets.latest_active_version(self.conn, "poster"))

    def test_imported_failed_version_cannot_be_reported_as_published(self):
        content = b"same bytes as failed attempt"
        digest = hashlib.sha256(content).hexdigest()
        assets.record_version(self.conn, "poster", digest, state="FAILED")
        token = self.acquire()
        with self.assertRaises(assets.AssetError):
            self.publish(content, token=token)
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM asset_publication WHERE state='COMMITTED'").fetchone()[0], 0)

    def test_release_requires_generation_even_with_same_holder(self):
        old = self.acquire()
        new = assets.takeover_writer(self.conn, "asset:poster", "worker")
        self.assertFalse(assets.release_writer(self.conn, "asset:poster", "worker"))
        self.assertFalse(assets.release_writer(self.conn, "asset:poster", "worker", generation=old))
        self.assertTrue(assets.release_writer(self.conn, "asset:poster", "worker", generation=new))

    def test_process_crash_after_rename_is_recovered_without_dangling_version(self):
        token = self.acquire()
        source = self.root / "source.psd"
        source.write_bytes(b"staged PSD fixture")
        script = """
import os, pathlib, sys
sys.path.insert(0, sys.argv[1])
from design_lab.runtime import asset_store as assets
conn = assets.connect(pathlib.Path(sys.argv[2]))
assets._after_rename = lambda publication_id: os._exit(24)
assets.publish_version(conn, 'poster', pathlib.Path(sys.argv[3]), store_root=pathlib.Path(sys.argv[4]),
    artifact_name='poster.psd', expected_sha256=sys.argv[5], holder_attempt_id='worker', generation=int(sys.argv[6]))
"""
        result = subprocess.run([sys.executable, "-B", "-c", script, str(ROOT / "src"), str(self.db),
                                 str(source), str(self.root / "store"), hashlib.sha256(source.read_bytes()).hexdigest(), str(token)],
                                cwd=ROOT, capture_output=True, timeout=20)
        self.assertEqual(result.returncode, 24, result.stderr.decode())
        self.assertIsNone(assets.latest_active_version(self.conn, "poster"))
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM artifact").fetchone()[0], 0)
        restored = assets.recover_publications(self.conn, store_root=self.root / "store")
        self.assertEqual(restored[0]["state"], "QUARANTINED")
        self.assertEqual(Path(restored[0]["path"]).read_bytes(), source.read_bytes())
        self.assertEqual(assets.recover_publications(self.conn, store_root=self.root / "store"), [])

    def test_staging_tamper_rejected_before_metadata_commit(self):
        token = self.acquire()
        def tamper(pid):
            (self.root / "store/staging" / pid / "poster.psd").write_bytes(b"tampered")
        with patch.object(assets, "_after_stage", side_effect=tamper), self.assertRaises(assets.AssetError):
            self.publish(token=token)
        self.assertIsNone(assets.latest_active_version(self.conn, "poster"))

    def test_lease_renewal_cannot_revive_expired_generation(self):
        with patch.object(assets, "_clock", return_value=100):
            token = self.acquire()
        with patch.object(assets, "_clock", return_value=150):
            assets.renew_writer(self.conn, "asset:poster", "worker", generation=token, lease_seconds=100)
        with patch.object(assets, "_clock", return_value=200):
            self.assertEqual(assets.writer_token(self.conn, "asset:poster", "worker"), token)
        with patch.object(assets, "_clock", return_value=300), self.assertRaises(assets.AssetError):
            assets.renew_writer(self.conn, "asset:poster", "worker", generation=token)

    def test_asset_v1_migration_keeps_ids_paths_and_backup(self):
        db = self.root / "legacy.db"
        old = sqlite3.connect(db)
        old.executescript(assets._BASE_SCHEMA.read_text(encoding="utf-8"))
        old.executescript(assets._SCHEMA.read_text(encoding="utf-8"))
        old.execute("INSERT INTO project VALUES ('p','name','time')")
        old.execute("INSERT INTO asset VALUES ('a','p','psd','time')")
        old.execute("INSERT INTO asset_version VALUES ('v','a',1,?,'ACTIVE','time')", ("sha256:" + "a" * 64,))
        old.execute("INSERT INTO artifact VALUES ('old.psd','v','old.psd',?,3,'output')", ("a" * 64,))
        old.commit()
        expected = old.execute("SELECT * FROM artifact").fetchall()
        old.close()
        migrated = assets.connect(db)
        try:
            self.assertEqual(migrated.execute("SELECT * FROM artifact").fetchall(), expected)
            self.assertEqual(migrated.execute("PRAGMA foreign_key_check").fetchall(), [])
        finally:
            migrated.close()
        backups = list(self.root.glob("legacy.db.pre-assets-v2-*.bak"))
        self.assertEqual(len(backups), 1)
        backup = sqlite3.connect(backups[0])
        try:
            self.assertEqual(backup.execute("SELECT * FROM artifact").fetchall(), expected)
        finally:
            backup.close()

    def test_invalid_lease_expiry_requires_explicit_takeover(self):
        self.acquire()
        for expiry in ('corrupt', 'NaN', 'Infinity'):
            self.conn.execute("UPDATE asset_writer_lock SET expires_at=? WHERE resource_key='asset:poster'", (expiry,))
            self.conn.commit()
            with self.subTest(expiry=expiry):
                self.assertFalse(assets.acquire_writer(self.conn, 'asset:poster', 'another'))

    def test_nonportable_name_is_rejected_before_journal(self):
        token = self.acquire()
        source = self.root / 'source.psd'
        source.write_bytes(b'data')
        for name in ('NUL.psd', 'CON', 'bad?.psd', 'bad\x00.psd'):
            with self.subTest(name=name), self.assertRaises(assets.AssetError):
                assets.publish_version(self.conn, 'poster', source, store_root=self.root/'store', artifact_name=name,
                                       expected_sha256=hashlib.sha256(b'data').hexdigest(), holder_attempt_id='worker', generation=token)
        self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM asset_publication').fetchone()[0], 0)


if __name__ == "__main__":
    unittest.main()
