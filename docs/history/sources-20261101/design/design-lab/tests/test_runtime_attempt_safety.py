# SPDX-License-Identifier: MIT
"""R3-05 regressions using durable SQLite and real independent connections."""
from __future__ import annotations

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
from design_lab.runtime import job_store as jobs


class AttemptSafetyTests(unittest.TestCase):
    def setUp(self):
        runtime = ROOT / ".project-local/task-runtime/r3-attempt-tests"
        runtime.mkdir(parents=True, exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(dir=runtime)
        self.addCleanup(self.tmp.cleanup)
        self.db = Path(self.tmp.name) / "state.db"
        self.conn = jobs.connect(self.db)
        self.addCleanup(self.conn.close)

    def begin(self, conn=None, **overrides):
        values = dict(operation_id="op1", idempotency_scope="project1",
                      idempotency_key="save1", request_hash="sha256:" + "a" * 64)
        values.update(overrides)
        return jobs.begin_attempt(conn or self.conn, "job1", **values)

    def evidence(self, attempt):
        return dict(operation_id="op1", attempt_id=attempt["attempt_id"],
                    artifact_sha256="b" * 64, readback_sha256="c" * 64)

    def test_same_key_changed_request_rejected_without_residue(self):
        first = self.begin()
        with self.assertRaises(jobs.AttemptError):
            self.begin(request_hash="sha256:" + "d" * 64)
        self.assertFalse(self.conn.in_transaction)
        self.assertEqual(jobs.latest_attempt(self.conn, "job1"), first)

    def test_operation_and_job_identity_cannot_be_rebound(self):
        self.begin()
        for changes in (dict(operation_id="op2"), dict(idempotency_key="save2"),
                        dict(idempotency_scope="project2")):
            with self.subTest(changes=changes), self.assertRaises(jobs.AttemptError):
                self.begin(**changes)
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM operation_intent").fetchone()[0], 1)

    def test_hash_is_canonical_and_invalid_hashes_rejected(self):
        first = self.begin(request_hash="A" * 64)
        self.assertEqual(first, self.begin())
        for value in ("not-a-hash", "0" * 64, "sha256:" + "z" * 64):
            with self.subTest(value=value), self.assertRaises(jobs.AttemptError):
                self.begin(request_hash=value)

    def test_three_retries_have_distinct_numbers_and_preserve_history(self):
        attempt = self.begin()
        ids = [attempt["attempt_id"]]
        for number in range(1, 4):
            old = jobs.transition(self.conn, attempt["attempt_id"], "FAILED", note="pre-dispatch failure")
            attempt = jobs.retry_attempt(self.conn, "job1", previous_attempt_id=old["attempt_id"])
            ids.append(attempt["attempt_id"])
            self.assertEqual(attempt["attempt_no"], number + 1)
            self.assertEqual(jobs.retry_attempt(self.conn, "job1", previous_attempt_id=old["attempt_id"]), attempt)
        self.assertEqual(len(set(ids)), 4)
        self.assertEqual(self.conn.execute("SELECT state FROM attempt_state ORDER BY attempt_no").fetchall(),
                         [("FAILED",), ("FAILED",), ("FAILED",), ("PENDING",)])

    def test_crash_after_dispatch_never_silently_retries(self):
        attempt = self.begin()
        jobs.transition(self.conn, attempt["attempt_id"], "RUNNING")
        self.conn.close()
        self.conn = jobs.connect(self.db)
        self.addCleanup(self.conn.close)
        jobs.recover_interrupted(self.conn)
        self.assertEqual(jobs.latest_attempt(self.conn, "job1")["state"], "OUTCOME_UNKNOWN")
        with self.assertRaises(jobs.AttemptError):
            jobs.retry_attempt(self.conn, "job1", previous_attempt_id=attempt["attempt_id"])
        jobs.reconcile_attempt(self.conn, attempt["attempt_id"], "effect_not_started")
        successor = jobs.retry_attempt(self.conn, "job1", previous_attempt_id=attempt["attempt_id"])
        self.assertEqual(successor["attempt_no"], 2)

    def test_dispatch_failure_needs_readback_before_retry(self):
        attempt = self.begin()
        jobs.transition(self.conn, attempt["attempt_id"], "RUNNING")
        jobs.transition(self.conn, attempt["attempt_id"], "FAILED")
        with self.assertRaises(jobs.AttemptError):
            jobs.retry_attempt(self.conn, "job1", previous_attempt_id=attempt["attempt_id"])
        jobs.reconcile_attempt(self.conn, attempt["attempt_id"], "effect_not_started")
        self.assertEqual(jobs.retry_attempt(self.conn, "job1", previous_attempt_id=attempt["attempt_id"])["attempt_no"], 2)

    def test_lost_receipt_reconciles_success_without_second_dispatch(self):
        attempt = self.begin()
        jobs.transition(self.conn, attempt["attempt_id"], "RUNNING")
        # Dedicated host fixture: a committed effect survives worker restart.
        target = Path(self.tmp.name) / "host-effects.txt"
        target.write_text("saved once", encoding="utf-8")
        jobs.recover_interrupted(self.conn)
        digest = hashlib.sha256(target.read_bytes()).hexdigest()
        receipt = {**self.evidence(attempt), "artifact_sha256": digest, "readback_sha256": digest}
        jobs.reconcile_attempt(self.conn, attempt["attempt_id"], "effect_verified", evidence=receipt)
        self.assertEqual(jobs.operation_status(self.conn, "op1")["state"], "SUCCEEDED")
        with self.assertRaises(jobs.AttemptError):
            jobs.retry_attempt(self.conn, "job1", previous_attempt_id=attempt["attempt_id"])
        self.assertEqual(target.read_text(encoding="utf-8"), "saved once")
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM attempt_state").fetchone()[0], 1)

    def test_success_requires_bound_nonzero_output_and_readback(self):
        attempt = self.begin()
        jobs.transition(self.conn, attempt["attempt_id"], "RUNNING")
        for evidence in (None, {}, {**self.evidence(attempt), "attempt_id": "someone-else"},
                         {**self.evidence(attempt), "readback_sha256": "0" * 64}):
            with self.subTest(evidence=evidence), self.assertRaises(jobs.AttemptError):
                jobs.transition(self.conn, attempt["attempt_id"], "RECEIPTED", evidence=evidence)
        result = jobs.transition(self.conn, attempt["attempt_id"], "RECEIPTED", evidence=self.evidence(attempt))
        self.assertEqual(result["state"], "RECEIPTED")

    def test_cancel_ack_and_readback_are_separate(self):
        attempt = self.begin()
        aid = attempt["attempt_id"]
        jobs.transition(self.conn, aid, "RUNNING")
        with self.assertRaises(jobs.AttemptError):
            jobs.transition(self.conn, aid, "CANCELLED")
        jobs.request_cancel(self.conn, aid)
        self.assertEqual(jobs.latest_attempt(self.conn, "job1")["state"], "CANCEL_REQUESTED")
        jobs.acknowledge_cancel(self.conn, aid)
        self.assertEqual(jobs.latest_attempt(self.conn, "job1")["state"], "RECONCILING")
        jobs.reconcile_attempt(self.conn, aid, "effect_not_started")
        self.assertEqual(jobs.latest_attempt(self.conn, "job1")["state"], "CANCELLED")
        self.assertEqual(jobs.operation_status(self.conn, "op1")["state"], "CANCELLED")

    def test_cancel_receipt_race_preserves_confirmed_success(self):
        attempt = self.begin()
        aid = attempt["attempt_id"]
        jobs.transition(self.conn, aid, "RUNNING")
        jobs.request_cancel(self.conn, aid)
        jobs.transition(self.conn, aid, "RECEIPTED", evidence=self.evidence(attempt))
        with self.assertRaises(jobs.AttemptError):
            jobs.acknowledge_cancel(self.conn, aid)
        self.assertEqual(jobs.latest_attempt(self.conn, "job1")["state"], "RECEIPTED")

    def test_terminal_rows_are_immutable_even_via_sql(self):
        attempt = self.begin()
        jobs.transition(self.conn, attempt["attempt_id"], "FAILED", note="original")
        with self.assertRaises(sqlite3.IntegrityError):
            self.conn.execute("UPDATE attempt_state SET note='rewritten' WHERE attempt_id=?", (attempt["attempt_id"],))
        self.conn.rollback()
        with self.assertRaises(sqlite3.IntegrityError):
            self.conn.execute("DELETE FROM attempt_state WHERE attempt_id=?", (attempt["attempt_id"],))
        self.conn.rollback()

    def test_parallel_begin_and_retry_create_single_successor(self):
        # Initialize schemas before workers share the database.
        barrier = threading.Barrier(2)
        def worker(previous=None):
            conn = jobs.connect(self.db)
            try:
                barrier.wait(timeout=10)
                return (jobs.retry_attempt(conn, "job1", previous_attempt_id=previous)
                        if previous else self.begin(conn))["attempt_id"]
            finally:
                conn.close()
        with ThreadPoolExecutor(2) as pool:
            ids = list(pool.map(worker, [None, None]))
        self.assertEqual(ids[0], ids[1])
        jobs.transition(self.conn, ids[0], "FAILED")
        with ThreadPoolExecutor(2) as pool:
            successors = list(pool.map(worker, ids))
        self.assertEqual(successors[0], successors[1])
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM attempt_state").fetchone()[0], 2)

    def test_concurrent_dispatch_only_one_worker_can_claim(self):
        attempt = self.begin()
        barrier = threading.Barrier(2)
        def claim(_):
            conn = jobs.connect(self.db)
            try:
                barrier.wait(timeout=10)
                try:
                    jobs.transition(conn, attempt["attempt_id"], "RUNNING")
                    return True
                except jobs.AttemptError:
                    return False
            finally:
                conn.close()
        with ThreadPoolExecutor(2) as pool:
            self.assertEqual(sorted(pool.map(claim, range(2))), [False, True])

    def test_subprocess_crashes_after_real_effect_before_receipt(self):
        attempt = self.begin()
        target = Path(self.tmp.name) / "effect.txt"
        script = """
import os, pathlib, sys
sys.path.insert(0, sys.argv[1])
from design_lab.runtime import job_store as jobs
conn = jobs.connect(pathlib.Path(sys.argv[2]))
jobs.transition(conn, sys.argv[3], 'RUNNING')
with open(sys.argv[4], 'xb') as out:
    out.write(b'one committed effect')
    out.flush()
    os.fsync(out.fileno())
os._exit(23)
"""
        result = subprocess.run([sys.executable, "-B", "-c", script, str(ROOT / "src"),
                                 str(self.db), attempt["attempt_id"], str(target)],
                                cwd=ROOT, capture_output=True, timeout=20)
        self.assertEqual(result.returncode, 23, result.stderr.decode())
        jobs.recover_interrupted(self.conn)
        digest = hashlib.sha256(target.read_bytes()).hexdigest()
        receipt = {**self.evidence(attempt), "artifact_sha256": digest, "readback_sha256": digest}
        jobs.reconcile_attempt(self.conn, attempt["attempt_id"], "effect_verified", evidence=receipt)
        for _ in range(3):
            self.assertEqual(self.begin()["attempt_id"], attempt["attempt_id"])
            with self.assertRaises(jobs.AttemptError):
                jobs.retry_attempt(self.conn, "job1", previous_attempt_id=attempt["attempt_id"])
        self.assertEqual(target.read_bytes(), b"one committed effect")
        self.assertEqual(jobs.operation_status(self.conn, "op1")["state"], "SUCCEEDED")

    def test_sql_failure_rolls_back_entire_attempt_transaction(self):
        self.conn.execute("CREATE TRIGGER deny_event BEFORE INSERT ON attempt_event "
                          "BEGIN SELECT RAISE(ABORT, 'injected event I/O failure'); END")
        with self.assertRaises(sqlite3.IntegrityError):
            self.begin()
        self.assertFalse(self.conn.in_transaction)
        for table in ("job", "operation_intent", "attempt_state", "job_attempt", "operation_state"):
            self.assertEqual(self.conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0], 0, table)
        self.conn.execute("DROP TRIGGER deny_event")
        self.begin()

    def test_stale_attempt_cannot_reconcile_after_successor(self):
        first = self.begin()
        jobs.transition(self.conn, first["attempt_id"], "FAILED")
        second = jobs.retry_attempt(self.conn, "job1", previous_attempt_id=first["attempt_id"])
        with self.assertRaises(jobs.AttemptError):
            jobs.reconcile_attempt(self.conn, first["attempt_id"], "effect_verified", evidence=self.evidence(first))
        self.assertEqual(jobs.latest_attempt(self.conn, "job1"), second)

    def test_request_hash_canonicalization(self):
        self.assertEqual(jobs.request_hash({"a": 1, "b": {"x": 2}}),
                         jobs.request_hash({"b": {"x": 2}, "a": 1}))
        self.assertNotEqual(jobs.request_hash({"a": [1, 2]}), jobs.request_hash({"a": [2, 1]}))
        with self.assertRaises(ValueError):
            jobs.request_hash({"a": float("nan")})

    def legacy_database(self, state="RECEIPTED"):
        db = Path(self.tmp.name) / "legacy.db"
        conn = sqlite3.connect(db)
        conn.executescript(jobs._BASE_SCHEMA.read_text(encoding="utf-8"))
        conn.executescript(jobs._SCHEMA.read_text(encoding="utf-8"))
        conn.execute("INSERT INTO operation_intent VALUES ('legacy-op','scope','key',?,'old-time')", ("a" * 64,))
        conn.execute("INSERT INTO job (job_id,operation_id) VALUES ('legacy-job','legacy-op')")
        conn.execute("INSERT INTO job_attempt VALUES ('legacy-job',1,'old-time')")
        conn.execute("INSERT INTO attempt_state VALUES ('legacy-att','legacy-job',1,?,'old-time','end-time','old-note')", (state,))
        conn.commit()
        expected = conn.execute("SELECT * FROM attempt_state").fetchall()
        conn.close()
        return db, expected

    def test_v1_migration_preserves_history_and_creates_recoverable_backup(self):
        db, expected = self.legacy_database()
        migrated = jobs.connect(db)
        try:
            self.assertEqual(migrated.execute("SELECT * FROM attempt_state").fetchall(), expected)
            self.assertEqual(jobs.operation_status(migrated, "legacy-op")["state"], "OUTCOME_UNKNOWN")
            self.assertEqual(migrated.execute("PRAGMA foreign_key_check").fetchall(), [])
        finally:
            migrated.close()
        backups = list(db.parent.glob("legacy.db.pre-attempt-v2-*.bak"))
        self.assertEqual(len(backups), 1)
        saved = sqlite3.connect(backups[0])
        try:
            self.assertEqual(saved.execute("SELECT * FROM attempt_state").fetchall(), expected)
        finally:
            saved.close()
        again = jobs.connect(db)
        again.close()
        self.assertEqual(len(list(db.parent.glob("legacy.db.pre-attempt-v2-*.bak"))), 1)

    def test_legacy_cancelled_with_no_effect_stays_cancelled(self):
        db, expected = self.legacy_database(state="CANCELLED")
        conn = jobs.connect(db)
        try:
            jobs.reconcile_attempt(conn, 'legacy-att', 'effect_not_started')
            self.assertEqual(jobs.operation_status(conn, 'legacy-op')['state'], 'CANCELLED')
            self.assertEqual(conn.execute('SELECT * FROM attempt_state').fetchall(), expected)
        finally:
            conn.close()

    def test_legacy_success_conflicting_readback_needs_manual_resolution(self):
        db, _ = self.legacy_database()
        conn = jobs.connect(db)
        try:
            with self.assertRaises(jobs.AttemptError):
                jobs.reconcile_attempt(conn, 'legacy-att', 'effect_not_started')
            self.assertEqual(jobs.operation_status(conn, 'legacy-op')['state'], 'OUTCOME_UNKNOWN')
        finally:
            conn.close()

    def test_ambiguous_legacy_job_ownership_cannot_dispatch(self):
        attempt = self.begin()
        self.conn.execute("INSERT INTO job (job_id,operation_id) VALUES ('legacy-job2','op1')")
        self.conn.commit()
        with self.assertRaises(jobs.AttemptError):
            jobs.transition(self.conn, attempt['attempt_id'], 'RUNNING')
        self.assertEqual(jobs.latest_attempt(self.conn, 'job1')['state'], 'PENDING')

    def test_repeated_cancel_ack_after_restart_is_idempotent(self):
        attempt = self.begin()
        jobs.transition(self.conn, attempt['attempt_id'], 'RUNNING')
        jobs.request_cancel(self.conn, attempt['attempt_id'])
        acknowledged = jobs.acknowledge_cancel(self.conn, attempt['attempt_id'])
        conn = jobs.connect(self.db)
        try:
            self.assertEqual(jobs.acknowledge_cancel(conn, attempt['attempt_id']), acknowledged)
        finally:
            conn.close()

    def test_failed_migration_restores_v1_schema_and_data(self):
        db, expected = self.legacy_database()
        bad = Path(self.tmp.name) / "bad-migration.sql"
        bad.write_text(jobs._V2_SCHEMA.read_text(encoding="utf-8") + "\nSELECT * FROM missing_table;\n", encoding="utf-8")
        with patch.object(jobs, "_V2_SCHEMA", bad), self.assertRaises(sqlite3.OperationalError):
            jobs.connect(db)
        original = sqlite3.connect(db)
        try:
            self.assertEqual(original.execute("SELECT * FROM attempt_state").fetchall(), expected)
            self.assertIsNone(original.execute("SELECT 1 FROM sqlite_master WHERE name='operation_state'").fetchone())
            self.assertEqual(original.execute("SELECT COUNT(*) FROM runtime_migration").fetchone()[0], 0)
        finally:
            original.close()
        jobs.connect(db).close()


if __name__ == "__main__":
    unittest.main()
