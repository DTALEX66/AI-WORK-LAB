# SPDX-License-Identifier: MIT
"""DL-P0-030 Requirement ledger: what the job must satisfy, and its evidence.

Requirements are append-only events, so a status change never erases the state
a delivery was judged under. ``MET`` needs both an artifact digest and a
readback digest: a claim without readback is not acceptance, it is a claim.
``MUST`` requirements gate delivery; waiving one requires a named human actor
and a reason.
"""
from __future__ import annotations

import re

from .store import CreativeError, digest, dumps, now, require_job, transaction

STATUSES = ("OPEN", "MET", "FAILED", "WAIVED", "CONTRADICTED")
PRIORITIES = ("MUST", "SHOULD", "MAY")
# Join point with the delivery-receipt contract (DL-P0-161).
RECEIPT_STATUS = {
    "OPEN": "NOT_RUN",
    "MET": "PASS",
    "FAILED": "FAIL",
    "CONTRADICTED": "FAIL",
    "WAIVED": "SKIPPED_OPTIONAL",
}
_IDENTITY = re.compile(r"^REQ-[A-Za-z0-9_.-]{1,64}$")
_TERMINAL_OK = {"MET", "WAIVED"}
_TRANSITIONS = {
    "VERIFIED": {"OPEN", "FAILED", "CONTRADICTED", "MET"},
    "FAILED": {"OPEN", "MET", "CONTRADICTED"},
    "WAIVED": {"OPEN", "FAILED", "CONTRADICTED"},
    "CONTRADICTED": {"OPEN", "MET", "FAILED"},
    "REOPENED": {"MET", "WAIVED", "FAILED", "CONTRADICTED"},
}


def _identity(value) -> str:
    if not isinstance(value, str) or not _IDENTITY.match(value):
        raise CreativeError(f"requirement id must match REQ-<name>: {value!r}")
    return value


def _text(value, field) -> str:
    if not isinstance(value, str) or not value.strip():
        raise CreativeError(f"{field} must be a nonempty string")
    return value


def _current(conn, req_id: str):
    return conn.execute("SELECT job_id, kind, status, statement, acceptance, priority FROM requirement_event "
                        "WHERE req_id=? ORDER BY event_no DESC LIMIT 1", (req_id,)).fetchone()


def requirement(conn, req_id: str) -> dict:
    row = _current(conn, _identity(req_id))
    if not row:
        raise CreativeError(f"unknown requirement: {req_id!r}")
    return {"req_id": req_id, "job_id": row[0], "status": row[2], "statement": row[3],
            "acceptance": row[4], "priority": row[5], "last_event": row[1]}


def define_requirement(conn, *, job_id: str, req_id: str, statement: str, acceptance: str,
                       actor: str, priority: str = "MUST") -> dict:
    """Define a requirement once; redefinition is refused, not overwritten."""
    require_job(conn, job_id)
    req_id = _identity(req_id)
    statement = _text(statement, "statement")
    acceptance = _text(acceptance, "acceptance")
    actor = _text(actor, "actor")
    if priority not in PRIORITIES:
        raise CreativeError(f"invalid priority: {priority!r}")
    with transaction(conn):
        if _current(conn, req_id):
            raise CreativeError("requirement is already defined; reopen or supersede it instead")
        conn.execute("INSERT INTO requirement_event "
                     "(req_id, job_id, kind, status, statement, acceptance, priority, actor, at) "
                     "VALUES (?,?,?,?,?,?,?,?,?)",
                     (req_id, job_id, "DEFINED", "OPEN", statement, acceptance, priority, actor, now()))
    return requirement(conn, req_id)


def _transition(conn, req_id: str, kind: str, status: str, *, actor: str, note=None, evidence_ref=None,
                artifact_sha256=None, readback_sha256=None) -> dict:
    current = requirement(conn, req_id)
    if status not in STATUSES:
        raise CreativeError(f"invalid requirement status: {status!r}")
    if current["status"] not in _TRANSITIONS[kind]:
        raise CreativeError(f"requirement {req_id} cannot move {current['status']} -> {status}")
    actor = _text(actor, "actor")
    with transaction(conn):
        conn.execute("INSERT INTO requirement_event "
                     "(req_id, job_id, kind, status, evidence_ref, artifact_sha256, readback_sha256, "
                     "actor, note, at) VALUES (?,?,?,?,?,?,?,?,?,?)",
                     (req_id, current["job_id"], kind, status, evidence_ref, artifact_sha256,
                      readback_sha256, actor, note, now()))
    return requirement(conn, req_id)


def verify(conn, *, req_id: str, evidence_ref: str, artifact_sha256: str, readback_sha256: str,
           actor: str, note=None) -> dict:
    """Acceptance: artifact digest plus readback digest, both required."""
    try:
        artifact = digest(artifact_sha256)
        readback = digest(readback_sha256)
    except CreativeError as exc:
        raise CreativeError(f"verification evidence is incomplete: {exc}") from exc
    return _transition(conn, req_id, "VERIFIED", "MET", actor=actor, note=note,
                       evidence_ref=_text(evidence_ref, "evidence_ref"),
                       artifact_sha256=artifact, readback_sha256=readback)


def fail(conn, *, req_id: str, evidence_ref: str, actor: str, note=None) -> dict:
    current = requirement(conn, req_id)
    if current["status"] == "WAIVED":
        raise CreativeError("waived requirement must be reopened before it can fail")
    return _transition(conn, req_id, "FAILED", "FAILED", actor=actor, note=note,
                       evidence_ref=_text(evidence_ref, "evidence_ref"))


def contradict(conn, *, req_id: str, evidence_ref: str, actor: str, note=None) -> dict:
    return _transition(conn, req_id, "CONTRADICTED", "CONTRADICTED", actor=actor, note=note,
                       evidence_ref=_text(evidence_ref, "evidence_ref"))


def waive(conn, *, req_id: str, actor: str, reason: str) -> dict:
    """A waiver is a human decision with a reason, never a silent omission."""
    return _transition(conn, req_id, "WAIVED", "WAIVED", actor=_text(actor, "actor"),
                       note=_text(reason, "waiver reason"), evidence_ref=None)


def reopen(conn, *, req_id: str, actor: str, reason: str) -> dict:
    return _transition(conn, req_id, "REOPENED", "OPEN", actor=_text(actor, "actor"),
                       note=_text(reason, "reopen reason"))


def requirements(conn, job_id: str) -> list:
    require_job(conn, job_id)
    ids = [row[0] for row in conn.execute("SELECT DISTINCT req_id FROM requirement_event WHERE job_id=? "
                                          "ORDER BY req_id", (job_id,))]
    return [requirement(conn, req_id) for req_id in ids]


def coverage(conn, job_id: str) -> dict:
    items = requirements(conn, job_id)
    unmet = sorted(r["req_id"] for r in items if r["priority"] == "MUST" and r["status"] not in _TERMINAL_OK)
    waived = sorted(r["req_id"] for r in items if r["status"] == "WAIVED")
    failed = sorted(r["req_id"] for r in items if r["status"] in {"FAILED", "CONTRADICTED"})
    return {"job_id": job_id, "total": len(items),
            "by_status": {status: sum(1 for r in items if r["status"] == status) for status in STATUSES},
            "unmet_must": unmet, "waived": waived, "failed": failed,
            "gate": "OPEN" if unmet or failed else "SATISFIED"}


def gate(conn, job_id: str) -> dict:
    """Delivery gate: every MUST requirement is MET or explicitly WAIVED."""
    report = coverage(conn, job_id)
    if report["unmet_must"]:
        raise CreativeError("unmet MUST requirements block delivery: " + dumps(report["unmet_must"]))
    if report["failed"]:
        raise CreativeError("failed/contradicted requirements block delivery: " + dumps(report["failed"]))
    return report


def delivery_requirements(conn, job_id: str) -> list:
    """Project this ledger into the delivery-receipt requirement vocabulary.

    The receipt contract (DL-P0-161) speaks about verification outcomes
    (``PASS``/``FAIL``/``NOT_RUN``/``UNVERIFIED``/``BLOCKED``/``SKIPPED_OPTIONAL``)
    while this ledger speaks about requirement state. The join is explicit here
    rather than left to a caller to guess:

    ``MET`` -> ``PASS``, ``OPEN`` -> ``NOT_RUN``, ``FAILED`` -> ``FAIL``,
    ``CONTRADICTED`` -> ``FAIL``, ``WAIVED`` -> ``SKIPPED_OPTIONAL``.
    """
    projection = []
    for item in requirements(conn, job_id):
        status = RECEIPT_STATUS.get(item["status"])
        if status is None:
            raise CreativeError(f"no receipt projection for requirement status {item['status']!r}")
        projection.append({"req_id": item["req_id"], "status": status})
    return projection


def history(conn, req_id: str) -> list:
    _identity(req_id)
    return [{"event_no": row[0], "kind": row[1], "status": row[2], "actor": row[3], "note": row[4],
             "evidence_ref": row[5], "at": row[6]} for row in conn.execute(
        "SELECT event_no, kind, status, actor, note, evidence_ref, at FROM requirement_event "
        "WHERE req_id=? ORDER BY event_no", (req_id,))]
