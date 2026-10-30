# SPDX-License-Identifier: MIT
"""DL-P0-032 Rejected version guard: a rejected version can never be served.

Rejection is recorded beside the version, never by rewriting it. The v1 row
keeps its original state and digest, so historical evidence keeps its meaning
while every delivery path fails closed. Rejection is terminal: the same
rejection is idempotent, a different one is refused, and database triggers make
the record append-only even for a direct SQL writer.
"""
from __future__ import annotations

import sqlite3

from .store import CreativeError, now, transaction

_UNSERVABLE = {"REJECTED", "FAILED", "CANCELLED"}
_FIELDS = ("reason", "actor", "evidence_ref")


def _text(value, field):
    if not isinstance(value, str) or not value.strip():
        raise CreativeError(f"rejection {field} must be a nonempty string")
    return value


def _known_version(conn, version_id) -> None:
    if not isinstance(version_id, str) or not version_id.strip():
        raise CreativeError("version_id must be a nonempty string")
    if not conn.execute("SELECT 1 FROM asset_version WHERE version_id=?", (version_id,)).fetchone():
        raise CreativeError(f"unknown asset version: {version_id!r}")


def reject_version(conn, version_id: str, *, reason: str, actor: str, evidence_ref: str) -> dict:
    """Record a terminal rejection; identical replay returns the same record."""
    _known_version(conn, version_id)
    values = {"reason": _text(reason, "reason"), "actor": _text(actor, "actor"),
              "evidence_ref": _text(evidence_ref, "evidence_ref")}
    with transaction(conn):
        row = conn.execute("SELECT reason, actor, evidence_ref, rejected_at FROM version_rejection "
                           "WHERE version_id=?", (version_id,)).fetchone()
        if row:
            if (row[0], row[1], row[2]) != (values["reason"], values["actor"], values["evidence_ref"]):
                raise CreativeError("version rejection is terminal: a different rejection cannot replace it")
            return {"version_id": version_id, "created": False, "rejected_at": row[3], **values}
        conn.execute("INSERT INTO version_rejection VALUES (?,?,?,?,?)",
                     (version_id, values["reason"], values["actor"], values["evidence_ref"], now()))
        return {"version_id": version_id, "created": True, **values}


def rejection(conn, version_id: str):
    row = conn.execute("SELECT reason, actor, evidence_ref, rejected_at FROM version_rejection "
                       "WHERE version_id=?", (version_id,)).fetchone()
    if not row:
        return None
    return {"version_id": version_id, "reason": row[0], "actor": row[1], "evidence_ref": row[2],
            "rejected_at": row[3]}


def is_rejected(conn, version_id: str) -> bool:
    return bool(conn.execute("SELECT 1 FROM version_rejection WHERE version_id=?", (version_id,)).fetchone())


def rejection_status(conn, version_id: str) -> str:
    """Why a version is not servable, or SERVABLE."""
    row = conn.execute("SELECT state, (SELECT 1 FROM version_rejection r WHERE r.version_id=asset_version.version_id) "
                       "FROM asset_version WHERE version_id=?", (version_id,)).fetchone()
    if not row:
        raise CreativeError(f"unknown asset version: {version_id!r}")
    if row[1]:
        return "REJECTED"
    return "SERVABLE" if row[0] not in _UNSERVABLE else row[0]


def assert_servable(conn, version_id: str) -> None:
    """Delivery/publish gate: fail closed on rejected, failed or cancelled."""
    status = rejection_status(conn, version_id)
    if status != "SERVABLE":
        detail = rejection(conn, version_id)
        extra = f": {detail['reason']}" if detail else ""
        raise CreativeError(f"version is not servable ({status}): {version_id!r}{extra}")


def guard_delivery(conn, version_ids) -> list:
    for version_id in version_ids:
        assert_servable(conn, version_id)
    return list(version_ids)


def rejected_versions(conn, asset_id=None) -> list:
    query = ("SELECT r.version_id, r.reason, r.actor, r.rejected_at, v.asset_id FROM version_rejection r "
             "JOIN asset_version v USING (version_id)")
    if asset_id is None:
        rows = conn.execute(query + " ORDER BY r.rejected_at").fetchall()
    else:
        rows = conn.execute(query + " WHERE v.asset_id=? ORDER BY r.rejected_at", (asset_id,)).fetchall()
    return [{"version_id": row[0], "reason": row[1], "actor": row[2], "rejected_at": row[3], "asset_id": row[4]}
            for row in rows]


def servable_versions(conn, asset_id: str) -> list:
    """Versions of an asset that a delivery or publish path may still use."""
    rows = conn.execute("SELECT version_id, version_no, branch, state FROM asset_version "
                        "WHERE asset_id=? ORDER BY version_no", (asset_id,)).fetchall()
    return [{"version_id": row[0], "version_no": row[1], "branch": row[2], "state": row[3]}
            for row in rows if rejection_status(conn, row[0]) == "SERVABLE"]


def assert_append_only(conn) -> None:
    """Verify the immutability guards on this database.

    Trigger presence alone is checked first; when a rejection row exists the
    module also probes a mutation inside a rolled-back savepoint, so the check
    proves behaviour rather than a name.
    """
    names = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='trigger'")}
    missing = {"version_rejection_no_update", "version_rejection_no_delete"} - names
    if missing:
        raise CreativeError("missing rejection guards: " + ", ".join(sorted(missing)))
    if conn.in_transaction or not conn.execute("SELECT 1 FROM version_rejection LIMIT 1").fetchone():
        return
    conn.execute("SAVEPOINT guard_probe")
    blocked = False
    try:
        conn.execute("UPDATE version_rejection SET reason=reason")
    except sqlite3.DatabaseError:
        blocked = True
    finally:
        conn.execute("ROLLBACK TO guard_probe")
        conn.execute("RELEASE guard_probe")
    if not blocked:
        raise CreativeError("rejection record is mutable: append-only guard did not fire")
