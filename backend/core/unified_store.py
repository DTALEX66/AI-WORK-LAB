# SPDX-License-Identifier: MIT
"""Unified Task/Attempt/Result/Verification store (stdlib sqlite3).

One outer envelope per 08_前后端交接约定.json:

* Task lifecycle and Attempt execution are separate; a result received does not
  complete a task — technical and (when required) professional acceptance both
  have to pass first, server-side.
* A retry mints a new Attempt; a failed attempt is never overwritten.
* Every write is a compare-and-swap on ``revision``; a stale writer is refused.
* Idempotency: ``(task_id, idempotency_key)`` is unique — repeating the same
  attempt request reads back the same attempt instead of minting a second one.
* Crash safety: WAL mode + a single writer connection; on restart the reader
  sees committed rows only. Unknown executor states stay DISCONNECTED_UNKNOWN
  until reconciled — nothing is auto-replayed.

Two invariants the 2026-10-30 audit (F04, F07) found missing, and how they are
implemented here rather than in a caller that could be bypassed:

* **A row cannot point at nothing.** ``attempts.task_id``, ``results.task_id``
  and ``results.attempt_id`` and ``verifications.result_id`` are checked on
  every write *in code*, and declared as foreign keys for a freshly created
  database. Code-level checks are deliberate: an existing database written
  before the constraints existed still has no FK metadata, and a constraint the
  old rows ignore protects nothing — ``integrity_report()`` therefore reads the
  whole store and names every pre-existing violation instead of pretending the
  new schema retroactively fixed them.
* **COMPLETED is not writable on request.** Setting a task to COMPLETED runs
  ``completion_support()`` against the rows that exist now. A bare lifecycle
  edit, a PASS on an orphan result, or a superseded verdict no longer closes a
  task, whichever caller tried it.
* **Origin is inherited, never re-declared upward.** project → task → attempt →
  result → verification each carry the least authoritative origin of the chain
  above them (backend.core.origins), plus ``origin_provenance`` so a row written
  before this rule existed is read as ``UNENFORCED_LEGACY`` and is never live
  evidence on its own account.

SQL note: every statement is an inline single-literal string with ``?``
placeholders and precomputed parameter variables; nothing is assembled from
request data.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

from backend.core import binding as binding_rules
from backend.core import origins

TASK_KINDS = ("work", "design", "repair", "improvement")
TASK_LIFECYCLE = ("DRAFT", "READY", "ACTIVE", "COMPLETED", "CANCELLED", "ARCHIVED")
ATTEMPT_STATES = ("PREPARED", "WAITING_HANDOFF", "HANDOFF_DECLARED", "QUEUED", "RUNNING",
                  "WAITING_INPUT", "WAITING_PERMISSION", "DISCONNECTED_UNKNOWN",
                  "CANCEL_REQUESTED", "CANCELLED", "RESULT_RECEIVED", "FAILED")
EXECUTION_MODES = ("MANUAL_COPY", "LOCAL_TOOL", "NATIVE_AGENT", "ACP", "MCP_TOOL")
VERIFICATION_AXES = ("technical", "professional", "migration", "host_readback")
VERIFICATION_OUTCOMES = ("PENDING", "RUNNING", "PASS", "FAIL", "BLOCKED", "NOT_RUN")
#: Only these technical verdicts can support a completion claim *right now*.
SUPPORTING_OUTCOMES = ("PASS",)

#: ``digest v1`` is the pre-audit serialization (``json.dumps`` default
#: separators); ``v2`` is the compact canonical form this module writes now.
#: Both are readable so an existing database's rows can still be audited rather
#: than silently reported as tampered.
DIGEST_V1 = "v1-default-separators"
DIGEST_V2 = "v2-canonical-compact"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS projects (
  project_id   TEXT PRIMARY KEY,
  source       TEXT NOT NULL,
  display_name TEXT NOT NULL,
  root_path    TEXT,
  data_origin  TEXT NOT NULL DEFAULT 'live',
  origin_provenance TEXT,
  registered_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS tasks (
  task_id     TEXT PRIMARY KEY,
  project_id  TEXT NOT NULL,
  kind        TEXT NOT NULL,
  lifecycle   TEXT NOT NULL DEFAULT 'DRAFT',
  title       TEXT NOT NULL,
  input_refs  TEXT NOT NULL DEFAULT '[]',
  acceptance  TEXT NOT NULL DEFAULT '{}',
  professional_required INTEGER NOT NULL DEFAULT 0,
  current_attempt_id TEXT,
  revision    INTEGER NOT NULL DEFAULT 1,
  data_origin TEXT NOT NULL DEFAULT 'live',
  origin_provenance TEXT,
  created_at  TEXT NOT NULL,
  updated_at  TEXT NOT NULL,
  FOREIGN KEY(project_id) REFERENCES projects(project_id)
);
CREATE TABLE IF NOT EXISTS attempts (
  attempt_id     TEXT PRIMARY KEY,
  task_id        TEXT NOT NULL,
  base_fingerprint TEXT NOT NULL DEFAULT '',
  execution_mode TEXT NOT NULL,
  executor_ref   TEXT,
  execution_state TEXT NOT NULL DEFAULT 'PREPARED',
  idempotency_key TEXT NOT NULL,
  pack_plan_id   TEXT,
  pack_ref       TEXT,
  binding_sha256 TEXT,
  candidate_version TEXT,
  handoff        TEXT,
  revision       INTEGER NOT NULL DEFAULT 1,
  data_origin    TEXT NOT NULL DEFAULT 'live',
  origin_provenance TEXT,
  started_at     TEXT,
  finished_at    TEXT,
  created_at     TEXT NOT NULL,
  updated_at     TEXT NOT NULL,
  UNIQUE(task_id, idempotency_key),
  FOREIGN KEY(task_id) REFERENCES tasks(task_id)
);
CREATE TABLE IF NOT EXISTS results (
  result_id    TEXT PRIMARY KEY,
  task_id      TEXT NOT NULL,
  attempt_id   TEXT NOT NULL,
  pack_id      TEXT,
  declared_result_id TEXT,
  subject_fingerprint TEXT NOT NULL DEFAULT '',
  artifact_refs TEXT NOT NULL DEFAULT '[]',
  content_sha256 TEXT NOT NULL,
  digest_vocabulary TEXT,
  binding        TEXT,
  candidate_version TEXT,
  origin_chain   TEXT,
  raw          TEXT NOT NULL,
  data_origin  TEXT NOT NULL DEFAULT 'live',
  origin_provenance TEXT,
  received_at  TEXT NOT NULL,
  FOREIGN KEY(task_id) REFERENCES tasks(task_id),
  FOREIGN KEY(attempt_id) REFERENCES attempts(attempt_id)
);
CREATE TABLE IF NOT EXISTS verifications (
  verification_id TEXT PRIMARY KEY,
  result_id    TEXT NOT NULL,
  axis         TEXT NOT NULL,
  outcome      TEXT NOT NULL,
  subject_fingerprint TEXT NOT NULL DEFAULT '',
  command_ref  TEXT,
  evidence_refs TEXT NOT NULL DEFAULT '[]',
  verifier_ref TEXT,
  approval_ref TEXT,
  identity_state TEXT,
  checks       TEXT,
  current_validity TEXT,
  candidate_version TEXT,
  origin_chain TEXT,
  detail       TEXT,
  data_origin  TEXT NOT NULL DEFAULT 'live',
  origin_provenance TEXT,
  observed_at  TEXT NOT NULL,
  FOREIGN KEY(result_id) REFERENCES results(result_id)
);
"""

#: Columns an existing pre-audit database is missing; added on open, never by
#: deleting the file. NULL in these columns means "written before this build".
_ADDED_COLUMNS = (
    ("tasks", "origin_provenance"),
    ("projects", "origin_provenance"),
    ("attempts", "origin_provenance"),
    ("attempts", "binding_sha256"),
    ("attempts", "candidate_version"),
    ("results", "declared_result_id"),
    ("results", "digest_vocabulary"),
    ("results", "binding"),
    ("results", "candidate_version"),
    ("results", "origin_chain"),
    ("results", "origin_provenance"),
    ("verifications", "approval_ref"),
    ("verifications", "identity_state"),
    ("verifications", "checks"),
    ("verifications", "current_validity"),
    ("verifications", "candidate_version"),
    ("verifications", "origin_chain"),
    ("verifications", "origin_provenance"),
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _id() -> str:
    return uuid.uuid4().hex


def _dumps(value) -> str:
    return json.dumps(value, ensure_ascii=False)


class StoreError(ValueError):
    """A state transition or payload the envelope contract refuses."""


def _unknown(label: str, value, vocabulary) -> str:
    return label + " " + repr(value) + " outside " + repr(list(vocabulary))


def result_digest(raw: dict, vocabulary: str | None) -> str:
    """Recompute the digest of one stored result under its own vocabulary.

    ``v1`` hashed the ``json.dumps`` text with default separators; ``v2`` hashes
    the compact canonical form. Both are derivable so an existing database's rows
    can be audited instead of being reported as tampered.
    """
    if vocabulary == DIGEST_V1:
        text = json.dumps(raw, ensure_ascii=False, sort_keys=True)
        return hashlib.sha256(text.encode("utf-8")).hexdigest()
    return binding_rules.canonical_digest(raw)


def _provenance(row) -> str:
    value = row.get("origin_provenance") if isinstance(row, dict) else None
    return origins.PROVENANCE_ENFORCED if value == origins.PROVENANCE_ENFORCED \
        else origins.PROVENANCE_LEGACY_UNENFORCED


def _json_column(row: dict, name: str, default):
    """Decode a JSON column, tolerating a database written before it existed.

    A read-only audit of an old store must report what is absent, not crash on a
    missing key — the absence itself is the finding.
    """
    if name not in row:
        return default
    value = row[name]
    if value in (None, ""):
        return default
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return default


class UnifiedStore:
    def __init__(self, path: Path, *, read_only: bool = False):
        path = Path(path)
        if not read_only:
            path.parent.mkdir(parents=True, exist_ok=True)
        self.read_only = read_only
        self.path = path
        if read_only:
            # A gate must not be able to migrate the database it is auditing. An
            # old store is read as it is and its gaps are reported, never repaired
            # by opening it for write.
            self.conn = sqlite3.connect("file:" + str(path).replace("\\", "/") + "?mode=ro",
                                        uri=True, check_same_thread=False)
        else:
            self.conn = sqlite3.connect(str(path), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        if read_only:
            self.conn.execute("PRAGMA foreign_keys=ON")
        else:
            self.conn.execute("PRAGMA journal_mode=WAL")
            self.conn.execute("PRAGMA foreign_keys=ON")
            self.conn.executescript(_SCHEMA)
            self._add_missing_columns()
            self.conn.commit()

    @classmethod
    def open_readonly(cls, path: Path) -> "UnifiedStore":
        return cls(Path(path), read_only=True)

    def _add_missing_columns(self) -> None:
        for table, column in _ADDED_COLUMNS:
            existing = {row["name"] for row in self.conn.execute(
                "SELECT name FROM pragma_table_info(?)", (table,))}
            if column not in existing:
                self.conn.execute("ALTER TABLE " + table + " ADD COLUMN " + column + " TEXT")

    def close(self) -> None:
        self.conn.close()

    # -- projects -----------------------------------------------------------
    def register_project(self, *, source: str, display_name: str,
                         root_path: str | None = None, data_origin: str = "live") -> dict:
        if source not in ("work", "design"):
            raise StoreError(_unknown("PROJECT_SOURCE_UNKNOWN", source, ("work", "design")))
        origins.check(data_origin)
        project_id = _id()
        registered_at = _now()
        self.conn.execute(
            "INSERT INTO projects(project_id, source, display_name, root_path, data_origin, origin_provenance, registered_at) VALUES(?,?,?,?,?,?,?)",
            (project_id, source, display_name, root_path, data_origin,
             origins.PROVENANCE_ENFORCED, registered_at))
        self.conn.commit()
        return self.get_project(project_id)

    def get_project(self, project_id: str) -> dict | None:
        row = self.conn.execute(
            "SELECT * FROM projects WHERE project_id=?",
            (project_id,)).fetchone()
        return dict(row) if row else None

    def list_projects(self) -> list[dict]:
        return [dict(r) for r in self.conn.execute(
            "SELECT * FROM projects ORDER BY registered_at, project_id")]

    # -- tasks ---------------------------------------------------------------
    def create_task(self, *, project_id: str, kind: str, title: str,
                    input_refs: list | None, acceptance: dict | None,
                    professional_required: bool = False, data_origin: str = "live",
                    candidate_version: str = "") -> dict:
        if kind not in TASK_KINDS:
            raise StoreError(_unknown("TASK_KIND_UNKNOWN", kind, TASK_KINDS))
        origins.check(data_origin)
        if self.get_project(project_id) is None:
            raise StoreError("PROJECT_NOT_FOUND " + repr(project_id)
                             + " a task cannot exist under a project that was never registered")
        clean_title = str(title or "").strip()
        if not clean_title:
            raise StoreError("TASK_TITLE_REQUIRED")
        task_id = _id()
        now = _now()
        input_refs_json = _dumps(list(input_refs or []))
        acceptance_json = _dumps(dict(acceptance or {}))
        prof_flag = 1 if professional_required else 0
        effective = origins.combine(data_origin, self.get_project(project_id)["data_origin"])
        self.conn.execute(
            "INSERT INTO tasks(task_id, project_id, kind, lifecycle, title, input_refs, acceptance, professional_required, data_origin, origin_provenance, created_at, updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
            (task_id, project_id, kind, "DRAFT", clean_title, input_refs_json, acceptance_json,
             prof_flag, effective, origins.PROVENANCE_ENFORCED, now, now))
        self.conn.commit()
        return self.get_task(task_id)

    def get_task(self, task_id: str) -> dict | None:
        row = self.conn.execute(
            "SELECT * FROM tasks WHERE task_id=?",
            (task_id,)).fetchone()
        if row is None:
            return None
        task = dict(row)
        task["input_refs"] = json.loads(task["input_refs"])
        task["acceptance"] = json.loads(task["acceptance"])
        task["attempts"] = self.list_attempts(task_id)
        task["results"] = self.list_results(task_id=task_id)
        return task

    def list_tasks(self, project_id: str | None = None) -> list[dict]:
        if project_id:
            rows = self.conn.execute(
                "SELECT * FROM tasks WHERE project_id=? ORDER BY created_at, task_id",
                (project_id,)).fetchall()
        else:
            rows = self.conn.execute(
                "SELECT * FROM tasks ORDER BY created_at, task_id").fetchall()
        out = []
        for row in rows:
            task = dict(row)
            task["input_refs"] = json.loads(task["input_refs"])
            task["acceptance"] = json.loads(task["acceptance"])
            out.append(task)
        return out

    def set_task_lifecycle(self, task_id: str, lifecycle: str, *,
                           expected_revision: int | None = None,
                           current_attempt_id: str | None = None) -> dict:
        if lifecycle not in TASK_LIFECYCLE:
            raise StoreError(_unknown("TASK_LIFECYCLE_UNKNOWN", lifecycle, TASK_LIFECYCLE))
        row = self.conn.execute(
            "SELECT * FROM tasks WHERE task_id=?",
            (task_id,)).fetchone()
        if row is None:
            raise StoreError("TASK_NOT_FOUND")
        if expected_revision is not None and expected_revision != row["revision"]:
            raise StoreError("TASK_REVISION_CONFLICT store revision is " + repr(row["revision"]))
        if lifecycle == "COMPLETED":
            support = self.completion_support(task_id)
            if not support["supported"]:
                raise StoreError("COMPLETION_UNSUPPORTED " + "; ".join(support["problems"]))
        new_revision = row["revision"] + 1
        new_attempt = row["current_attempt_id"]
        if current_attempt_id is not None:
            new_attempt = current_attempt_id
        updated_at = _now()
        self.conn.execute(
            "UPDATE tasks SET lifecycle=?, revision=?, current_attempt_id=?, updated_at=? WHERE task_id=?",
            (lifecycle, new_revision, new_attempt, updated_at, task_id))
        self.conn.commit()
        return self.get_task(task_id)

    # -- attempts --------------------------------------------------------------
    def create_attempt(self, task_id: str, *, idempotency_key: str, execution_mode: str,
                       base_fingerprint: str = "", executor_ref: str | None = None,
                       data_origin: str | None = None,
                       candidate_version: str = "") -> tuple[dict, bool]:
        """(attempt, created). Idempotent on (task_id, idempotency_key)."""
        if execution_mode not in EXECUTION_MODES:
            raise StoreError(_unknown("EXECUTION_MODE_UNKNOWN", execution_mode, EXECUTION_MODES))
        clean_key = str(idempotency_key or "").strip()
        if not clean_key:
            raise StoreError("IDEMPOTENCY_KEY_REQUIRED")
        existing = self.conn.execute(
            "SELECT * FROM attempts WHERE task_id=? AND idempotency_key=?",
            (task_id, clean_key)).fetchone()
        if existing is not None:
            return dict(existing), False
        task = self.conn.execute(
            "SELECT * FROM tasks WHERE task_id=?",
            (task_id,)).fetchone()
        if task is None:
            raise StoreError("TASK_NOT_FOUND")
        if task["lifecycle"] in ("COMPLETED", "CANCELLED", "ARCHIVED"):
            raise StoreError("TASK_NOT_OPEN lifecycle " + repr(task["lifecycle"]) + " accepts no new attempts")
        # An attempt inherits its task's origin. A caller may add a *less*
        # authoritative origin, never a more authoritative one.
        effective = origins.combine(data_origin, task["data_origin"])
        attempt_id = _id()
        now = _now()
        self.conn.execute(
            "INSERT INTO attempts(attempt_id, task_id, base_fingerprint, execution_mode, executor_ref, execution_state, idempotency_key, candidate_version, data_origin, origin_provenance, started_at, created_at, updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (attempt_id, task_id, base_fingerprint, execution_mode, executor_ref, "PREPARED",
             clean_key, candidate_version, effective, origins.PROVENANCE_ENFORCED, now, now, now))
        self.conn.commit()
        return self.get_attempt(attempt_id), True

    def get_attempt(self, attempt_id: str) -> dict | None:
        row = self.conn.execute(
            "SELECT * FROM attempts WHERE attempt_id=?",
            (attempt_id,)).fetchone()
        if row is None:
            return None
        attempt = dict(row)
        attempt["pack_ref"] = json.loads(attempt["pack_ref"]) if attempt["pack_ref"] else None
        attempt["handoff"] = json.loads(attempt["handoff"]) if attempt["handoff"] else None
        return attempt

    def update_attempt(self, attempt_id: str, *, expected_revision: int | None = None,
                       execution_state: str | None = None, pack_plan_id: str | None = None,
                       pack_ref: dict | None = None, handoff: dict | None = None,
                       binding_sha256: str | None = None, finished_at: str | None = None) -> dict:
        row = self.conn.execute(
            "SELECT * FROM attempts WHERE attempt_id=?",
            (attempt_id,)).fetchone()
        if row is None:
            raise StoreError("ATTEMPT_NOT_FOUND")
        if expected_revision is not None and expected_revision != row["revision"]:
            raise StoreError("ATTEMPT_REVISION_CONFLICT store revision is " + repr(row["revision"]))
        if execution_state is not None and execution_state not in ATTEMPT_STATES:
            raise StoreError(_unknown("ATTEMPT_STATE_UNKNOWN", execution_state, ATTEMPT_STATES))
        new_revision = row["revision"] + 1
        new_state = row["execution_state"]
        if execution_state is not None:
            new_state = execution_state
        new_plan = row["pack_plan_id"]
        if pack_plan_id is not None:
            new_plan = pack_plan_id
        new_pack_ref = row["pack_ref"]
        if pack_ref is not None:
            new_pack_ref = _dumps(pack_ref)
        new_handoff = row["handoff"]
        if handoff is not None:
            new_handoff = _dumps(handoff)
        new_binding = row["binding_sha256"]
        if binding_sha256 is not None:
            new_binding = binding_sha256
        new_finished = row["finished_at"]
        if finished_at is not None:
            new_finished = finished_at
        updated_at = _now()
        self.conn.execute(
            "UPDATE attempts SET revision=?, execution_state=?, pack_plan_id=?, pack_ref=?, binding_sha256=?, handoff=?, finished_at=?, updated_at=? WHERE attempt_id=?",
            (new_revision, new_state, new_plan, new_pack_ref, new_binding, new_handoff,
             new_finished, updated_at, attempt_id))
        self.conn.commit()
        return self.get_attempt(attempt_id)

    def list_attempts(self, task_id: str) -> list[dict]:
        out = []
        for row in self.conn.execute(
                "SELECT * FROM attempts WHERE task_id=? ORDER BY created_at, attempt_id",
                (task_id,)):
            attempt = dict(row)
            attempt["pack_ref"] = json.loads(attempt["pack_ref"]) if attempt["pack_ref"] else None
            attempt["handoff"] = json.loads(attempt["handoff"]) if attempt["handoff"] else None
            out.append(attempt)
        return out

    # -- results ------------------------------------------------------------
    def record_result(self, *, task_id: str, attempt_id: str, pack_id: str | None,
                      subject_fingerprint: str, artifact_refs: list, content_sha256: str,
                      raw: dict, data_origin: str = "live", declared_result_id: str = "",
                      binding: dict | None = None, candidate_version: str = "",
                      origin_chain: dict | None = None,
                      digest_vocabulary: str = DIGEST_V2) -> dict:
        """Store one accepted result. Refuses a row that would point at nothing.

        The attempt must exist and must belong to the task; the task must exist.
        A caller that wants to record a result against an attempt it cannot name
        has to fail here, not in a later audit script.
        """
        origins.check(data_origin)
        attempt = self.get_attempt(attempt_id)
        if attempt is None:
            raise StoreError("RESULT_ATTEMPT_NOT_FOUND " + repr(attempt_id)
                             + " a result cannot bind to an attempt that does not exist")
        if attempt["task_id"] != task_id:
            raise StoreError("RESULT_TASK_MISMATCH attempt " + repr(attempt_id)
                             + " belongs to task " + repr(attempt["task_id"]) + ", not " + repr(task_id))
        task = self.get_task(task_id)
        if task is None:
            raise StoreError("RESULT_TASK_NOT_FOUND " + repr(task_id))
        declared = origins.check(data_origin)
        effective = origins.combine(declared, attempt["data_origin"])
        result_id = _id()
        received_at = _now()
        artifact_json = _dumps(list(artifact_refs or []))
        raw_json = _dumps(raw)
        binding_json = _dumps(dict(binding or {}))
        chain_json = _dumps(dict(origin_chain or {}))
        self.conn.execute(
            "INSERT INTO results(result_id, task_id, attempt_id, pack_id, declared_result_id, subject_fingerprint, artifact_refs, content_sha256, digest_vocabulary, binding, candidate_version, origin_chain, raw, data_origin, origin_provenance, received_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (result_id, task_id, attempt_id, pack_id, declared_result_id, subject_fingerprint,
             artifact_json, content_sha256, digest_vocabulary, binding_json, candidate_version,
             chain_json, raw_json, effective, origins.PROVENANCE_ENFORCED,
             received_at))
        self.conn.commit()
        return self.get_result(result_id)

    def get_result(self, result_id: str) -> dict | None:
        row = self.conn.execute(
            "SELECT * FROM results WHERE result_id=?",
            (result_id,)).fetchone()
        if row is None:
            return None
        result = dict(row)
        result["artifact_refs"] = json.loads(result["artifact_refs"])
        result["raw"] = json.loads(result["raw"])
        result["binding"] = _json_column(result, "binding", {})
        result["origin_chain"] = _json_column(result, "origin_chain", {})
        result["verifications"] = self.list_verifications(result_id)
        return result

    def list_results(self, task_id: str | None = None, attempt_id: str | None = None) -> list[dict]:
        """In write order: ``rowid`` breaks same-second ties deterministically."""
        if task_id is not None and attempt_id is not None:
            ids = self.conn.execute(
                "SELECT result_id FROM results WHERE task_id=? AND attempt_id=? ORDER BY received_at, rowid",
                (task_id, attempt_id))
        elif task_id is not None:
            ids = self.conn.execute(
                "SELECT result_id FROM results WHERE task_id=? ORDER BY received_at, rowid",
                (task_id,))
        elif attempt_id is not None:
            ids = self.conn.execute(
                "SELECT result_id FROM results WHERE attempt_id=? ORDER BY received_at, rowid",
                (attempt_id,))
        else:
            ids = self.conn.execute(
                "SELECT result_id FROM results ORDER BY received_at, rowid")
        return [self.get_result(row["result_id"]) for row in ids]

    # -- verifications --------------------------------------------------------
    def record_verification(self, *, result_id: str, axis: str, outcome: str,
                            subject_fingerprint: str = "", command_ref: str | None = None,
                            evidence_refs: list | None = None, verifier_ref: str | None = None,
                            detail: str | None = None, data_origin: str = "live",
                            approval_ref: str | None = None, identity_state: str | None = None,
                            checks: dict | None = None, current_validity: str | None = None,
                            candidate_version: str = "") -> dict:
        """One verdict row. The result must exist, and the origin is inherited."""
        if axis not in VERIFICATION_AXES:
            raise StoreError(_unknown("VERIFICATION_AXIS_UNKNOWN", axis, VERIFICATION_AXES))
        if outcome not in VERIFICATION_OUTCOMES:
            raise StoreError(_unknown("VERIFICATION_OUTCOME_UNKNOWN", outcome, VERIFICATION_OUTCOMES))
        result = self.get_result(result_id)
        if result is None:
            raise StoreError("VERIFICATION_RESULT_NOT_FOUND " + repr(result_id)
                             + " a verdict cannot be minted for a result that does not exist")
        origins.check(data_origin)
        effective = origins.combine(data_origin, result["data_origin"])
        # The verdict's chain is the result's chain plus the result itself, so a
        # reader can see every hop that made this row non-live without re-querying.
        chain = dict(result.get("origin_chain") or {})
        chain["result"] = result["data_origin"]
        chain["verdict_declared"] = data_origin
        chain["verdict_effective"] = effective
        verification_id = _id()
        observed_at = _now()
        evidence_json = _dumps(list(evidence_refs or []))
        checks_json = _dumps(dict(checks or {}))
        validity = current_validity if current_validity in binding_rules.CURRENT_VALIDITY \
            else "CURRENT" if outcome == "PASS" else "NOT_APPLICABLE"
        self.conn.execute(
            "INSERT INTO verifications(verification_id, result_id, axis, outcome, subject_fingerprint, command_ref, evidence_refs, verifier_ref, approval_ref, identity_state, checks, current_validity, candidate_version, origin_chain, detail, data_origin, origin_provenance, observed_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (verification_id, result_id, axis, outcome, subject_fingerprint, command_ref,
             evidence_json, verifier_ref, approval_ref, identity_state, checks_json, validity,
             candidate_version, _dumps(chain), detail, effective,
             origins.PROVENANCE_ENFORCED, observed_at))
        self.conn.commit()
        return self.get_verification(verification_id)

    def get_verification(self, verification_id: str) -> dict | None:
        row = self.conn.execute(
            "SELECT * FROM verifications WHERE verification_id=?",
            (verification_id,)).fetchone()
        if row is None:
            return None
        verification = dict(row)
        verification["evidence_refs"] = json.loads(verification["evidence_refs"])
        verification["checks"] = _json_column(verification, "checks", {})
        verification["origin_chain"] = _json_column(verification, "origin_chain", {})
        return verification

    def list_verifications(self, result_id: str) -> list[dict]:
        """In write order. ``rowid`` is the tie-breaker, not the random id.

        Two verdicts inside the same second made ``ORDER BY observed_at,
        verification_id`` resolve in whatever order the uuid4 hex happened to
        sort, so "the newest verdict" was a coin flip — a FAIL written right
        after a PASS could sit *below* it and keep supporting readiness.
        """
        out = []
        for row in self.conn.execute(
                "SELECT * FROM verifications WHERE result_id=? ORDER BY observed_at, rowid",
                (result_id,)):
            verification = dict(row)
            verification["evidence_refs"] = json.loads(verification["evidence_refs"])
            verification["checks"] = _json_column(verification, "checks", {})
            verification["origin_chain"] = _json_column(verification, "origin_chain", {})
            out.append(verification)
        return out

    def latest_verdict(self, result_id: str, axis: str) -> dict | None:
        """The newest verdict on this axis — what says what is true *now*.

        Ordered by (observed_at, verification_id) so a tie inside one second still
        resolves the same way on every read. An earlier PASS does not answer a
        later FAIL.
        """
        rows = [row for row in self.list_verifications(result_id) if row["axis"] == axis]
        return rows[-1] if rows else None

    # -- readiness ------------------------------------------------------------
    def completion_support(self, task_id: str) -> dict:
        """Why this task is or is not currently backed by a valid verdict chain.

        The audit's F04 counterexample was a store where a forged PASS and a later
        FAIL sat side by side and the oldest PASS still "supported" readiness. So
        the answer comes from the *current attempt's latest result and its latest
        verdict per axis*, and every relation is re-checked here rather than
        trusted from the row that wrote it.
        """
        problems: list[str] = []
        task = self.get_task(task_id)
        if task is None:
            return {"supported": False, "problems": ["TASK_NOT_FOUND " + repr(task_id)],
                    "chain": {}, "historical_fact": False}
        attempt = self.get_attempt(task["current_attempt_id"] or "") if task["current_attempt_id"] else None
        if attempt is None:
            problems.append("NO_CURRENT_ATTEMPT the task names no attempt that exists")
        results = self.list_results(task_id=task_id) if task else []
        technical: dict | None = None
        subject = None
        if attempt is not None:
            attempt_results = [row for row in results if row["attempt_id"] == attempt["attempt_id"]]
            if not attempt_results:
                problems.append("NO_RESULT_FOR_CURRENT_ATTEMPT a result was never imported for "
                                + repr(attempt["attempt_id"]))
            else:
                subject = attempt_results[-1]
                technical = self.latest_verdict(subject["result_id"], "technical")
                if technical is None:
                    problems.append("NO_TECHNICAL_VERDICT the current attempt's result has no "
                                    "technical verdict")
        elif results and task["current_attempt_id"] is None:
            problems.append("ORPHAN_RESULTS results exist under a task with no current attempt")

        if technical is not None:
            if technical["outcome"] not in SUPPORTING_OUTCOMES:
                problems.append("LATEST_TECHNICAL_VERDICT_NOT_PASS the newest technical verdict is "
                                + repr(technical["outcome"]) + "; an earlier PASS does not survive it")
            elif technical.get("current_validity") not in (None, "CURRENT"):
                problems.append("VERDICT_NOT_CURRENT the supporting verdict says "
                                + repr(technical.get("current_validity")) + " about its own subject")
            elif subject is not None and technical["subject_fingerprint"] != subject["content_sha256"]:
                problems.append("VERDICT_SUBJECT_MISMATCH the verdict certifies "
                                + repr(technical["subject_fingerprint"])[:16] + "… but the result "
                                "content is " + repr(subject["content_sha256"])[:16] + "…")
            if subject is not None and not (technical["evidence_refs"] or []):
                problems.append("VERDICT_WITHOUT_EVIDENCE a PASS with no evidence reference is a "
                                "conclusion, not a verification")

        professional = None
        if technical is not None and subject is not None:
            professional = self.latest_verdict(subject["result_id"], "professional")
        if task["professional_required"] and not (
                professional and professional["outcome"] == "PASS"
                and professional.get("identity_state") == "ATTESTED_AT_LOCAL_GATE"
                and professional.get("approval_ref")):
            problems.append("PROFESSIONAL_ACCEPTANCE_MISSING the task requires a named human verdict; "
                            "an agent reference or a bare string does not satisfy it")

        historical = any(row["axis"] == "technical" and row["outcome"] == "PASS"
                         for result_row in results
                         for row in self.list_verifications(result_row["result_id"]))
        chain = {
            "task_id": task_id, "task_origin": task["data_origin"],
            "task_provenance": _provenance(task),
            "attempt_id": attempt["attempt_id"] if attempt else None,
            "attempt_origin": attempt["data_origin"] if attempt else None,
            "result_id": subject["result_id"] if subject else None,
            "result_origin": subject["data_origin"] if subject else None,
            "technical_outcome": technical["outcome"] if technical else None,
            "technical_validity": technical.get("current_validity") if technical else None,
            "technical_origin": technical["data_origin"] if technical else None,
            "professional_outcome": professional["outcome"] if professional else None,
            "professional_identity_state": professional.get("identity_state") if professional else None,
        }
        return {"supported": not problems, "problems": problems, "chain": chain,
                "historical_fact": historical}

    def integrity_report(self) -> dict:
        """Every relation this store cannot vouch for, including pre-existing rows.

        New writes are refused by the checks above; this answers the other half of
        the audit's F04 — the database that already contains forged or orphaned
        rows written before the constraints landed. Nothing is deleted or repaired
        here; it names them.
        """
        problems: list[dict] = []
        tasks = {row["task_id"]: row for row in self.conn.execute("SELECT * FROM tasks")}
        attempts = {row["attempt_id"]: row for row in self.conn.execute("SELECT * FROM attempts")}
        results = {row["result_id"]: dict(row)
                   for row in self.conn.execute("SELECT * FROM results")}
        projects = {row["project_id"] for row in self.conn.execute("SELECT * FROM projects")}
        for task_id, task in tasks.items():
            if task["project_id"] not in projects:
                problems.append(dict(kind="TASK_ORPHAN_PROJECT", id=task_id,
                                     detail="project " + repr(task["project_id"]) + " is not registered"))
            if task["current_attempt_id"] and task["current_attempt_id"] not in attempts:
                problems.append(dict(kind="TASK_ORPHAN_ATTEMPT", id=task_id,
                                     detail="names a current attempt that does not exist"))
            if task["lifecycle"] == "COMPLETED" and not self.completion_support(task_id)["supported"]:
                problems.append(dict(kind="COMPLETION_UNSUPPORTED", id=task_id,
                                     detail="; ".join(self.completion_support(task_id)["problems"])))
        for attempt_id, attempt in attempts.items():
            if attempt["task_id"] not in tasks:
                problems.append(dict(kind="ATTEMPT_ORPHAN_TASK", id=attempt_id,
                                     detail="task " + repr(attempt["task_id"]) + " does not exist"))
        for result_id, result in results.items():
            if result["attempt_id"] not in attempts:
                problems.append(dict(kind="RESULT_ORPHAN_ATTEMPT", id=result_id,
                                     detail="attempt " + repr(result["attempt_id"]) + " does not exist"))
            if result["task_id"] not in tasks:
                problems.append(dict(kind="RESULT_ORPHAN_TASK", id=result_id,
                                     detail="task " + repr(result["task_id"]) + " does not exist"))
            raw = json.loads(result["raw"])
            vocabulary = result.get("digest_vocabulary")
            recomputed = result_digest(raw, vocabulary)
            legacy_recomputed = result_digest(raw, DIGEST_V1)
            if recomputed != result["content_sha256"] and legacy_recomputed != result["content_sha256"]:
                problems.append(dict(kind="RESULT_DIGEST_MISMATCH", id=result_id,
                                     detail="stored content_sha256 does not recompute from the raw row"))
            if vocabulary is None:
                problems.append(dict(kind="RESULT_PROVENANCE_LEGACY", id=result_id,
                                     detail="written before the binding contract; never live evidence "
                                            "on its own account"))
        for row in self.conn.execute("SELECT * FROM verifications"):
            verification = dict(row)
            if verification["result_id"] not in results:
                problems.append(dict(kind="VERIFICATION_ORPHAN_RESULT", id=verification["verification_id"],
                                     detail="references result " + repr(verification["result_id"])))
            if verification["outcome"] == "PASS" and not json.loads(
                    verification["evidence_refs"] or "[]"):
                problems.append(dict(kind="VERIFICATION_PASS_WITHOUT_EVIDENCE",
                                     id=verification["verification_id"],
                                     detail="a PASS carrying no evidence reference"))
            if verification.get("origin_provenance") is None:
                problems.append(dict(kind="VERIFICATION_PROVENANCE_LEGACY",
                                     id=verification["verification_id"],
                                     detail="written before origin enforcement"))
            if (verification["axis"] == "professional" and verification["outcome"] == "PASS"
                    and not verification.get("approval_ref")):
                problems.append(dict(kind="PROFESSIONAL_PASS_WITHOUT_APPROVAL",
                                     id=verification["verification_id"],
                                     detail="no local human approval resolves behind it"))
            if (verification["axis"] == "technical" and verification["outcome"] == "PASS"
                    and verification["result_id"] in results
                    and verification["subject_fingerprint"]
                    != results[verification["result_id"]]["content_sha256"]):
                problems.append(dict(kind="VERIFICATION_SUBJECT_MISMATCH",
                                     id=verification["verification_id"],
                                     detail="certifies a digest the stored result does not carry"))
        return {"problems": problems, "counts": {"tasks": len(tasks), "attempts": len(attempts),
                                                 "results": len(results)}}
