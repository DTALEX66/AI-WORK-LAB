# SPDX-License-Identifier: MIT
"""Durable operation/attempt ledger with explicit reconciliation and retries.

Write APIs own a short IMMEDIATE transaction. Workers must claim PENDING ->
RUNNING before adapter dispatch. A failed dispatch has an unknown outcome.
Receipts come from trusted adapter output/readback verifiers; this module
validates bindings, not the host itself.
"""
from __future__ import annotations

from contextlib import contextmanager
import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

from .attempt_contract import canonical_hash, request_hash, validate_evidence
from .paths import PathPolicyError, resolve_paths
from .state_resources import state_schema

_SCHEMA = state_schema("design-lab-state-attempt-v1.sql")
_BASE_SCHEMA = state_schema("design-lab-state-v1.sql")
_V2_SCHEMA = state_schema("design-lab-state-attempt-v2.sql")
TERMINAL = {"RECEIPTED", "FAILED", "TIMED_OUT", "CANCELLED"}
ALLOWED = {
    "PENDING": {"RUNNING", "CANCELLED", "FAILED"},
    "RUNNING": {"RECEIPTED", "FAILED", "TIMED_OUT", "OUTCOME_UNKNOWN", "CANCEL_REQUESTED"},
    "OUTCOME_UNKNOWN": {"RECONCILING", "CANCEL_REQUESTED"},
    "CANCEL_REQUESTED": {"RECEIPTED", "RECONCILING"},
    "RECONCILING": {"RECEIPTED", "CANCEL_REQUESTED"},
    **{state: set() for state in TERMINAL},
}
VALID_STATES = set(ALLOWED)


class AttemptError(RuntimeError):
    """Attempt state contract violation."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


@contextmanager
def _transaction(conn):
    if conn.in_transaction:
        raise AttemptError("write API requires an idle connection; caller transaction is preserved")
    conn.execute("BEGIN IMMEDIATE")
    try:
        yield
        conn.commit()
    except BaseException:
        conn.rollback()
        raise


def connect(db_path: Path, *, project_root=None) -> sqlite3.Connection:
    """Migrate once with a backup of existing attempts; stop workers first.

    Legacy receipts are preserved, but need new readback to qualify success.
    """
    try:
        db_path = resolve_paths(project_root=project_root).database_path(db_path)
    except PathPolicyError as exc:
        raise AttemptError(str(exc)) from exc
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), timeout=15)
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.executescript(_BASE_SCHEMA.read_text(encoding="utf-8"))
        conn.executescript(_SCHEMA.read_text(encoding="utf-8"))
        conn.execute("CREATE TABLE IF NOT EXISTS runtime_migration (name TEXT PRIMARY KEY, applied_at TEXT NOT NULL)")
        conn.commit()
        if not conn.execute("SELECT 1 FROM runtime_migration WHERE name='attempt-v2'").fetchone():
            if conn.execute("SELECT 1 FROM attempt_state LIMIT 1").fetchone():
                backup_path = db_path.with_name(f"{db_path.name}.pre-attempt-v2-{uuid.uuid4().hex}.bak")
                backup = sqlite3.connect(str(backup_path))
                try:
                    conn.backup(backup)
                finally:
                    backup.close()
            with _transaction(conn):
                if not conn.execute("SELECT 1 FROM runtime_migration WHERE name='attempt-v2'").fetchone():
                    statement = ""
                    for line in _V2_SCHEMA.read_text(encoding="utf-8").splitlines(keepends=True):
                        statement += line
                        if sqlite3.complete_statement(statement):
                            conn.execute(statement)
                            statement = ""
                    if statement.strip():
                        raise AttemptError("incomplete migration SQL")
                    conn.execute("INSERT INTO runtime_migration VALUES ('attempt-v2', ?)", (_now(),))
        return conn
    except BaseException:
        conn.close()
        raise


def _op(conn, operation_id, state):
    conn.execute("INSERT INTO operation_state VALUES (?,?,?) ON CONFLICT(operation_id) "
                 "DO UPDATE SET state=excluded.state, updated_at=excluded.updated_at",
                 (operation_id, state, _now()))


def _record(conn, attempt_id):
    row = conn.execute("SELECT attempt_id, job_id, attempt_no, state, started_at, ended_at, note "
                       "FROM attempt_state WHERE attempt_id=?", (attempt_id,)).fetchone()
    if row is None:
        raise AttemptError(f"unknown attempt_id: {attempt_id!r}")
    return dict(zip(("attempt_id", "job_id", "attempt_no", "state", "started_at", "ended_at", "note"), row))


def latest_attempt(conn, job_id):
    row = conn.execute("SELECT attempt_id FROM attempt_state WHERE job_id=? ORDER BY attempt_no DESC LIMIT 1",
                       (job_id,)).fetchone()
    return _record(conn, row[0]) if row else None


def operation_status(conn, operation_id):
    row = conn.execute("SELECT state, updated_at FROM operation_state WHERE operation_id=?", (operation_id,)).fetchone()
    return dict(operation_id=operation_id, state=row[0], updated_at=row[1]) if row else None


def _current(conn, attempt_id):
    attempt = _record(conn, attempt_id)
    if latest_attempt(conn, attempt["job_id"])["attempt_id"] != attempt_id:
        raise AttemptError("stale attempt cannot change current operation")
    op = conn.execute("SELECT operation_id FROM job WHERE job_id=?", (attempt["job_id"],)).fetchone()[0]
    if conn.execute("SELECT COUNT(*) FROM job WHERE operation_id=?", (op,)).fetchone()[0] != 1:
        raise AttemptError("ambiguous legacy operation ownership; reconcile job bindings before dispatch")
    return attempt, op


def _event(conn, attempt_id, before, after, detail):
    conn.execute("INSERT INTO attempt_event (attempt_id,from_state,to_state,detail,at) VALUES (?,?,?,?,?)",
                 (attempt_id, before, after, detail, _now()))


def _resolution(conn, attempt_id, proof, evidence=None):
    conn.execute("INSERT INTO attempt_resolution (attempt_id,proof,evidence_json,updated_at) VALUES (?,?,?,?) "
                 "ON CONFLICT(attempt_id) DO UPDATE SET proof=excluded.proof, "
                 "evidence_json=excluded.evidence_json,updated_at=excluded.updated_at",
                 (attempt_id, proof, json.dumps(evidence, sort_keys=True) if evidence else None, _now()))


def _change(conn, attempt, new_state, note=None):
    conn.execute("UPDATE attempt_state SET state=?, ended_at=?, note=? WHERE attempt_id=?",
                 (new_state, _now() if new_state in TERMINAL else None, note, attempt["attempt_id"]))
    _event(conn, attempt["attempt_id"], attempt["state"], new_state, note or "transition")


def _new_attempt(conn, job_id, operation_id, number):
    aid = "att-" + uuid.uuid4().hex
    now = _now()
    conn.execute("INSERT INTO attempt_state (attempt_id,job_id,attempt_no,state,started_at) VALUES (?,?,?,'PENDING',?)",
                 (aid, job_id, number, now))
    conn.execute("INSERT INTO job_attempt (job_id,attempt_no,started_at) VALUES (?,?,?)", (job_id, number, now))
    _op(conn, operation_id, "PENDING")
    _event(conn, aid, None, "PENDING", "attempt created")
    return _record(conn, aid)


def begin_attempt(conn, job_id, *, operation_id, idempotency_scope, idempotency_key, request_hash):
    """Return existing work only when all stable identity fields match."""
    try:
        digest = canonical_hash(request_hash)
    except ValueError as exc:
        raise AttemptError(str(exc)) from exc
    if not all(isinstance(v, str) and v.strip() for v in (job_id, operation_id, idempotency_scope, idempotency_key)):
        raise AttemptError("identity fields must be nonempty strings")
    with _transaction(conn):
        rows = conn.execute("SELECT operation_id,idempotency_scope,idempotency_key,request_hash "
                            "FROM operation_intent WHERE operation_id=? OR (idempotency_scope=? AND idempotency_key=?)",
                            (operation_id, idempotency_scope, idempotency_key)).fetchall()
        for row in rows:
            try:
                matching = tuple(row[:3]) == (operation_id, idempotency_scope, idempotency_key) and canonical_hash(row[3]) == digest
            except ValueError:
                matching = False
            if not matching:
                raise AttemptError("idempotency conflict: operation/key already bound to a different request")
        bound_jobs = conn.execute("SELECT job_id,operation_id FROM job WHERE job_id=? OR operation_id=?", (job_id, operation_id)).fetchall()
        if any(tuple(row) != (job_id, operation_id) for row in bound_jobs):
            raise AttemptError("job/operation binding conflict")
        if not rows:
            conn.execute("INSERT INTO operation_intent VALUES (?,?,?,?,?)",
                         (operation_id, idempotency_scope, idempotency_key, digest, _now()))
        if not bound_jobs:
            conn.execute("INSERT INTO job (job_id,operation_id) VALUES (?,?)", (job_id, operation_id))
        return latest_attempt(conn, job_id) or _new_attempt(conn, job_id, operation_id, 1)


def retry_attempt(conn, job_id, *, previous_attempt_id):
    """Compare-and-set predecessor: repeated requests reuse the same successor."""
    with _transaction(conn):
        previous = _record(conn, previous_attempt_id)
        latest = latest_attempt(conn, job_id)
        if previous["job_id"] != job_id or latest is None:
            raise AttemptError("retry predecessor belongs to another job")
        if latest["attempt_no"] == previous["attempt_no"] + 1:
            return latest
        if latest["attempt_id"] != previous_attempt_id:
            raise AttemptError("stale retry request")
        op = conn.execute("SELECT operation_id FROM job WHERE job_id=?", (job_id,)).fetchone()[0]
        resolution = conn.execute("SELECT proof FROM attempt_resolution WHERE attempt_id=?", (previous_attempt_id,)).fetchone()
        if (previous["state"] not in {"FAILED", "TIMED_OUT"} or not resolution
                or resolution[0] != "effect_not_started" or operation_status(conn, op)["state"] != "RETRYABLE"):
            raise AttemptError("retry requires a failed attempt and reconciled absence of effects")
        return _new_attempt(conn, job_id, op, previous["attempt_no"] + 1)


def _evidence(evidence, op, aid):
    try:
        return validate_evidence(evidence, operation_id=op, attempt_id=aid)
    except (ValueError, TypeError) as exc:
        raise AttemptError(str(exc)) from exc


def transition(conn, attempt_id, new_state, *, note=None, evidence=None):
    with _transaction(conn):
        attempt, op = _current(conn, attempt_id)
        current = attempt["state"]
        if current in TERMINAL and new_state == current:
            return attempt
        if new_state not in ALLOWED[current]:
            raise AttemptError(f"attempt {attempt_id}: {current} -> {new_state} not allowed")
        if new_state in {"CANCEL_REQUESTED", "RECONCILING"}:
            raise AttemptError("use explicit cancellation/reconciliation APIs")
        if new_state == "RECEIPTED":
            receipt = _evidence(evidence, op, attempt_id)
            _resolution(conn, attempt_id, "effect_verified", receipt)
            _op(conn, op, "SUCCEEDED")
        elif new_state == "RUNNING":
            _op(conn, op, "DISPATCHING")
        elif new_state == "CANCELLED":
            _resolution(conn, attempt_id, "effect_not_started")
            _op(conn, op, "CANCELLED")
        elif new_state == "FAILED" and current == "PENDING":
            _resolution(conn, attempt_id, "effect_not_started")
            _op(conn, op, "RETRYABLE")
        else:
            _op(conn, op, "OUTCOME_UNKNOWN")
        _change(conn, attempt, new_state, note)
        return _record(conn, attempt_id)


def request_cancel(conn, attempt_id):
    with _transaction(conn):
        attempt, op = _current(conn, attempt_id)
        if attempt["state"] == "CANCEL_REQUESTED":
            return attempt
        if attempt["state"] in TERMINAL:
            raise AttemptError("terminal attempt cannot be cancelled")
        _resolution(conn, attempt_id, "cancel_requested")
        conn.execute("UPDATE attempt_resolution SET cancel_requested=1 WHERE attempt_id=?", (attempt_id,))
        if attempt["state"] == "PENDING":
            _change(conn, attempt, "CANCELLED", "cancelled before dispatch")
            _op(conn, op, "CANCELLED")
        else:
            _change(conn, attempt, "CANCEL_REQUESTED", "adapter cancellation requested")
            _op(conn, op, "CANCEL_REQUESTED")
        return _record(conn, attempt_id)


def acknowledge_cancel(conn, attempt_id):
    with _transaction(conn):
        attempt, op = _current(conn, attempt_id)
        ack = conn.execute("SELECT cancel_acked FROM attempt_resolution WHERE attempt_id=?", (attempt_id,)).fetchone()
        if attempt["state"] == "RECONCILING" and ack and ack[0] == 1:
            return attempt
        if attempt["state"] != "CANCEL_REQUESTED":
            raise AttemptError("cancellation acknowledgement requires outstanding request")
        conn.execute("UPDATE attempt_resolution SET cancel_acked=1 WHERE attempt_id=?", (attempt_id,))
        _change(conn, attempt, "RECONCILING", "adapter acknowledged cancellation; readback still required")
        _op(conn, op, "RECONCILING")
        return _record(conn, attempt_id)


def reconcile_attempt(conn, attempt_id, proof, *, evidence=None):
    with _transaction(conn):
        attempt, op = _current(conn, attempt_id)
        status = operation_status(conn, op)["state"]
        if status in {"SUCCEEDED", "CANCELLED", "RETRYABLE"}:
            previous = conn.execute("SELECT proof,evidence_json FROM attempt_resolution WHERE attempt_id=?", (attempt_id,)).fetchone()
            receipt = _evidence(evidence, op, attempt_id) if proof == "effect_verified" else None
            if previous and previous == (proof, json.dumps(receipt, sort_keys=True) if receipt else None):
                return attempt
            raise AttemptError("resolved operation cannot be rewritten")
        if attempt["state"] not in {"OUTCOME_UNKNOWN", "RECONCILING", "FAILED", "TIMED_OUT", "RECEIPTED", "CANCELLED"}:
            raise AttemptError("attempt requires an unknown outcome before reconciliation")
        receipt = None
        resolution = conn.execute("SELECT cancel_requested,cancel_acked FROM attempt_resolution WHERE attempt_id=?", (attempt_id,)).fetchone()
        cancelling = bool(resolution and resolution[0])
        if proof == "effect_verified":
            receipt = _evidence(evidence, op, attempt_id)
            next_op, next_attempt = "SUCCEEDED", "RECEIPTED"
        elif proof == "effect_not_started":
            if attempt["state"] == "RECEIPTED":
                raise AttemptError("legacy success conflicts with absent effects; manual reconciliation required")
            if cancelling and not resolution[1]:
                raise AttemptError("cancel acknowledgement required before final cancellation")
            cancelled = cancelling or attempt["state"] == "CANCELLED"
            next_op, next_attempt = ("CANCELLED", "CANCELLED") if cancelled else ("RETRYABLE", "FAILED")
        elif proof in {"verified_idempotent", "needs_user", "document_reverted"}:
            next_op, next_attempt = "PAUSED_NEEDS_USER", "RECONCILING"
        else:
            raise AttemptError(f"unresolvable proof: {proof}")
        if attempt["state"] not in TERMINAL:
            _change(conn, attempt, next_attempt, f"reconciled: {proof}")
        else:
            _event(conn, attempt_id, attempt["state"], attempt["state"], f"late reconciliation: {proof}")
        _resolution(conn, attempt_id, proof, receipt)
        _op(conn, op, next_op)
        return _record(conn, attempt_id)


def recover_interrupted(conn):
    """Stopped-worker recovery. Caller must stop old workers, not steal live work."""
    with _transaction(conn):
        rows = conn.execute("SELECT attempt_id FROM attempt_state WHERE state='RUNNING'").fetchall()
        for (aid,) in rows:
            attempt, op = _current(conn, aid)
            _change(conn, attempt, "OUTCOME_UNKNOWN", "worker interrupted; reconcile before any retry")
            _op(conn, op, "OUTCOME_UNKNOWN")
        return [aid for (aid,) in rows]


def recover_orphaned_attempts(conn, *, holder_is_gone):
    """Relabel RUNNING attempts whose executing process is provably gone.

    `recover_interrupted` above assumes its caller already stopped every worker.
    A service that simply starts cannot assume that, so this variant demands a
    per-attempt liveness probe and skips anything still held. Derived from the
    non-blocking OS lock in runtime/native_recovery_lock.py, "free" means "there
    is no holder", never "the holder looks old".

    Relabelling is over-pessimistic by design: it creates no objects, claims no
    retry and leaves the host guard intact, so the worst a probe race can cost is
    one extra reconciliation step -- never a lost or duplicated publication.
    """
    if not callable(holder_is_gone):
        raise TypeError('RECOVERY_LIVENESS_PROBE_REQUIRED')
    with _transaction(conn):
        running = [aid for (aid,) in conn.execute(
            "SELECT attempt_id FROM attempt_state WHERE state='RUNNING'").fetchall()]
    orphans = [aid for aid in running if holder_is_gone(aid)]
    if not orphans:
        return []
    with _transaction(conn):
        for aid in orphans:
            attempt, op = _current(conn, aid)
            if attempt['state'] != 'RUNNING':
                continue
            _change(conn, attempt, "OUTCOME_UNKNOWN", "worker interrupted; reconcile before any retry")
            _op(conn, op, "OUTCOME_UNKNOWN")
    return orphans
