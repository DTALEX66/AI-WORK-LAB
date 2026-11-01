# SPDX-License-Identifier: MIT
"""DL-TP-T05 (MULTIMODAL-2026-09-05): durable Job/Attempt state service tests.

Proves: restart recovery, idempotent begin_attempt (no duplicate attempts),
terminal states cannot be rewritten to RUNNING/PENDING (a failed/cancelled
attempt is never reported completed), and allowed transitions apply.
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
import sys

SRC = Path(__file__).resolve().parents[2] / "src"
sys.path.insert(0, str(SRC))


class JobStoreTests(unittest.TestCase):
    def _db(self):
        parent = SRC.parent / '.project-local/task-runtime/job-store-tests'
        parent.mkdir(parents=True, exist_ok=True)
        tmp = tempfile.TemporaryDirectory(dir=parent)
        self.addCleanup(tmp.cleanup)
        return Path(tmp.name) / "jobs.db"

    def _begin(self, conn, job_id="job-1", *, operation_id="op-1"):
        from design_lab.runtime.job_store import begin_attempt

        return begin_attempt(
            conn, job_id, operation_id=operation_id,
            idempotency_scope="scope-1", idempotency_key="key-1", request_hash="sha256:" + "a" * 64,
        )

    def test_begin_then_restart_recovery(self):
        from design_lab.runtime.job_store import connect, latest_attempt, transition

        db = self._db()
        conn = connect(db)
        att = self._begin(conn)
        transition(conn, att["attempt_id"], "RUNNING")
        transition(conn, att["attempt_id"], "RECEIPTED", evidence={
            "operation_id": "op-1", "attempt_id": att["attempt_id"],
            "artifact_sha256": "b" * 64, "readback_sha256": "c" * 64,
        })
        conn.close()

        conn2 = connect(db)  # restart
        rec = latest_attempt(conn2, "job-1")
        self.assertEqual(rec["state"], "RECEIPTED")
        self.assertEqual(rec["attempt_no"], 1)
        conn2.close()

    def test_begin_attempt_is_idempotent(self):
        from design_lab.runtime.job_store import connect

        conn = connect(self._db())
        a1 = self._begin(conn)
        a2 = self._begin(conn)  # retry
        self.assertEqual(a1["attempt_id"], a2["attempt_id"])
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM attempt_state").fetchone()[0], 1)
        conn.close()

    def test_terminal_cannot_return_to_running_or_pending(self):
        from design_lab.runtime.job_store import AttemptError, connect, transition

        conn = connect(self._db())
        att = self._begin(conn)
        transition(conn, att["attempt_id"], "RUNNING")
        transition(conn, att["attempt_id"], "FAILED", note="ckpt missing")
        for bad in ("RUNNING", "PENDING", "RECEIPTED"):
            with self.assertRaises(AttemptError):
                transition(conn, att["attempt_id"], bad)
        conn.close()

    def test_cancelled_terminal_stays_cancelled_on_retry(self):
        from design_lab.runtime.job_store import connect, transition

        conn = connect(self._db())
        att = self._begin(conn)
        transition(conn, att["attempt_id"], "CANCELLED")
        # a retry must return the terminal record, not fabricate a fresh attempt
        retried = self._begin(conn)
        self.assertEqual(retried["attempt_id"], att["attempt_id"])
        self.assertEqual(retried["state"], "CANCELLED")
        conn.close()

    def test_disallowed_transition_rejected(self):
        from design_lab.runtime.job_store import AttemptError, connect, transition

        conn = connect(self._db())
        att = self._begin(conn)
        with self.assertRaises(AttemptError):
            transition(conn, att["attempt_id"], "RECEIPTED")  # PENDING -> RECEIPTED not allowed
        conn.close()

    def test_sql_check_rejects_invalid_state_enum(self):
        """attempt_state CHECK constraint rejects a fabricated state (T18 negative)."""
        from design_lab.runtime.job_store import connect

        conn = connect(self._db())
        self._begin(conn)
        with self.assertRaises(Exception):
            conn.execute(
                "UPDATE attempt_state SET state='COMPLETED' WHERE job_id='job-1'"
            )
        conn.close()


if __name__ == "__main__":
    unittest.main()
