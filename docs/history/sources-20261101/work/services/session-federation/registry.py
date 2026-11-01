"""Session Registry — the write-side authority for known sessions (WL-050).

The taskpack (ch 41) lists *Session Registry*, *Single Writer* and *Lease* as
things WORK-LAB must own itself.  This module is that write-side authority,
and it is deliberately **separate** from :mod:`index` (which is the read-side
FTS projection):

* ``SessionIndex``   — read-mostly FTS search over discovered sessions.
* ``SessionRegistry`` — the single authoritative register of which
  canonical sessions the federation knows about, who registered them, and
  when.  It is the record of truth for "which sessions exist".

Guarantees this register provides:

* **Idempotent registration** — re-registering the same
  ``universal_session_id`` updates the row instead of duplicating; a
  ``content_digest`` mismatch flags a stale re-register of the same id.
* **Single-writer + lease** — writes require holding the registry write
  lease.  The lease is a TTL-bearing row: a crashed writer's lease
  expires on its own (TTL) and the next writer may take over.  A writer
  whose lease is still live is refused (fail-closed) rather than double-written.
* **No native writes** — the registry only ever writes under
  ``.project-local/sessions/registry.sqlite``; it never touches a native
  agent store.

``writer_id`` and the lease TTL are injectable so tests can run a scratch
tree.
"""
from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

REGISTRY_SCHEMA_VERSION = 1


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


class LeaseHeldError(RuntimeError):
    """Raised when a registry write is attempted while another live lease is held."""


class Registry:
    """Single-writer, lease-guarded session register (SQLite, per-process WAL)."""

    def __init__(self, path: str | Path, *, writer_id: str = "registry-writer",
                 lease_ttl_seconds: float = 60.0) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.writer_id = writer_id
        self.lease_ttl_seconds = lease_ttl_seconds
        self._local = threading.local()
        self._init_schema()

    # -- plumbing ---------------------------------------------------------
    def _conn(self) -> sqlite3.Connection:
        conn = getattr(self._local, "conn", None)
        if conn is None:
            conn = sqlite3.connect(str(self.path), check_same_thread=False)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA busy_timeout=5000")
            self._local.conn = conn
        return conn

    def _init_schema(self) -> None:
        conn = self._conn()
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS meta (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            INSERT OR IGNORE INTO meta(key, value) VALUES
                ('schema_version', '{v}');

            CREATE TABLE IF NOT EXISTS sessions (
                rowid INTEGER PRIMARY KEY AUTOINCREMENT,
                universal_session_id TEXT NOT NULL UNIQUE,
                source_agent TEXT NOT NULL,
                source_session_id TEXT NOT NULL,
                workspace_id TEXT NOT NULL,
                project_id TEXT NOT NULL,
                source_format TEXT NOT NULL,
                portability_level TEXT NOT NULL DEFAULT 'L0_DISCOVERY',
                content_digest TEXT NOT NULL DEFAULT '',
                registered_at TEXT NOT NULL,
                registered_by TEXT NOT NULL,
                UNIQUE(source_agent, source_session_id)
            );
            CREATE INDEX IF NOT EXISTS idx_reg_agent ON sessions(source_agent);
            CREATE INDEX IF NOT EXISTS idx_reg_project ON sessions(project_id);

            -- single-writer lease: exactly one live lease at a time.
            CREATE TABLE IF NOT EXISTS write_lease (
                slot INTEGER PRIMARY KEY CHECK (slot = 0),
                writer_id TEXT NOT NULL,
                acquired_at TEXT NOT NULL,
                lease_until TEXT NOT NULL
            );
            """ .replace("{v}", str(REGISTRY_SCHEMA_VERSION))
        )
        conn.commit()

    # -- lease ------------------------------------------------------------
    def acquire_lease(self) -> dict[str, Any]:
        """Take the single-writer lease for this ``writer_id``.

        Succeeds when no lease is recorded, the current lease is expired
        (TTL — the way a crashed writer is recovered), or this same writer
        re-acquires its own lease.  Fails closed when *another* writer
        holds a live lease.
        """
        conn = self._conn()
        now = _utcnow_iso()
        conn.execute("BEGIN IMMEDIATE")
        try:
            row = conn.execute(
                "SELECT writer_id, lease_until FROM write_lease WHERE slot=0"
            ).fetchone()
            if row is not None:
                holder = row["writer_id"]
                until = row["lease_until"]
                # expired? (crashed writer recovery)
                expired = until is None or _utcnow_iso() >= until
                if holder != self.writer_id and not expired:
                    # let the except handler roll back; do not double-rollback
                    raise LeaseHeldError(
                        f"registry lease held by {holder!r} until {until}; "
                        f"{self.writer_id!r} cannot write"
                    )
            ttl = timedelta(seconds=self.lease_ttl_seconds)
            lease_until = (datetime.now(timezone.utc) + ttl).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
            conn.execute(
                "INSERT INTO write_lease(slot, writer_id, acquired_at, lease_until) "
                "VALUES (0, ?, ?, ?) "
                "ON CONFLICT(slot) DO UPDATE SET writer_id=excluded.writer_id, "
                "acquired_at=excluded.acquired_at, lease_until=excluded.lease_until",
                (self.writer_id, now, lease_until),
            )
            conn.commit()
            return {"acquired_by": self.writer_id, "acquired_at": now, "lease_until": lease_until}
        except Exception:
            # Only roll back if a transaction is still open (the raise path
            # above did not roll back, but neither did a successful commit).
            try:
                conn.execute("ROLLBACK")
            except sqlite3.OperationalError:
                pass
            raise

    def release_lease(self) -> None:
        """Drop the lease (only meaningful for the holder)."""
        conn = self._conn()
        conn.execute(
            "DELETE FROM write_lease WHERE slot=0 AND writer_id=?",
            (self.writer_id,),
        )
        conn.commit()

    def lease_holder(self) -> dict[str, Any] | None:
        row = self._conn().execute(
            "SELECT writer_id, acquired_at, lease_until FROM write_lease WHERE slot=0"
        ).fetchone()
        if not row:
            return None
        d = dict(row)
        d["expired"] = _utcnow_iso() >= d.get("lease_until", "")
        return d

    def _require_lease(self) -> None:
        holder = self.lease_holder()
        if holder is None:
            raise LeaseHeldError("no registry lease held — acquire_lease() before writing")
        if holder["writer_id"] != self.writer_id:
            if not holder.get("expired"):
                raise LeaseHeldError(
                    f"write blocked: live lease held by {holder['writer_id']!r}"
                )
            # expired foreign lease — take it over
            self.acquire_lease()

    # -- register ---------------------------------------------------------
    @staticmethod
    def _session_fields(session: Any) -> dict[str, Any]:
        if hasattr(session, "to_dict"):
            data = session.to_dict()
            digest = session.content_digest() if hasattr(session, "content_digest") else ""
        else:
            data = dict(session)
            digest = data.get("content_digest", "")
        level = data.get("portability_level", "L0_DISCOVERY")
        if hasattr(level, "value"):
            level = level.value
        return {
            "universal_session_id": data.get("universal_session_id", ""),
            "source_agent": data.get("source_agent", ""),
            "source_session_id": data.get("source_session_id", ""),
            "workspace_id": data.get("workspace_id", ""),
            "project_id": data.get("project_id", ""),
            "source_format": data.get("source_format", ""),
            "portability_level": str(level),
            "content_digest": digest or "",
        }

    def register(self, session: Any) -> dict[str, Any]:
        """Register one canonical session (idempotent by universal id).

        Requires the write lease.  Re-registering the same id updates the row;
        a differing ``content_digest`` is surfaced as ``stale_re_register`` so
        callers can detect same-id/changed-payload drift.
        """
        self._require_lease()
        conn = self._conn()
        f = self._session_fields(session)
        now = _utcnow_iso()
        existing = conn.execute(
            "SELECT content_digest FROM sessions WHERE universal_session_id=?",
            (f["universal_session_id"],),
        ).fetchone()
        stale = bool(existing and existing["content_digest"] and
                     existing["content_digest"] != f["content_digest"])
        conn.execute(
            """
            INSERT INTO sessions(
                universal_session_id, source_agent, source_session_id,
                workspace_id, project_id, source_format, portability_level,
                content_digest, registered_at, registered_by
            ) VALUES (?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(source_agent, source_session_id) DO UPDATE SET
                universal_session_id = excluded.universal_session_id,
                workspace_id = excluded.workspace_id,
                project_id = excluded.project_id,
                source_format = excluded.source_format,
                portability_level = excluded.portability_level,
                content_digest = excluded.content_digest,
                registered_at = excluded.registered_at,
                registered_by = excluded.registered_by
            """,
            (
                f["universal_session_id"], f["source_agent"], f["source_session_id"],
                f["workspace_id"], f["project_id"], f["source_format"],
                f["portability_level"], f["content_digest"], now, self.writer_id,
            ),
        )
        conn.commit()
        status = "ALREADY_REGISTERED" if existing else "REGISTERED"
        if stale:
            status = "STALE_REREGISTER"
        return {
            "status": status,
            "universal_session_id": f["universal_session_id"],
            "content_digest": f["content_digest"],
        }

    # -- query ------------------------------------------------------------
    def get(self, universal_session_id: str) -> dict[str, Any] | None:
        row = self._conn().execute(
            "SELECT * FROM sessions WHERE universal_session_id=?",
            (universal_session_id,),
        ).fetchone()
        return dict(row) if row else None

    def list_sessions(self, *, agent: str | None = None, project: str | None = None,
                      limit: int = 200) -> list[dict[str, Any]]:
        where: list[str] = []
        params: list[Any] = []
        if agent:
            where.append("source_agent = ?"); params.append(agent)
        if project:
            where.append("project_id = ?"); params.append(project)
        sql = "SELECT * FROM sessions"
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY rowid ASC LIMIT ?"
        params.append(limit)
        return [dict(r) for r in self._conn().execute(sql, params).fetchall()]

    def count(self) -> int:
        return self._conn().execute("SELECT COUNT(*) FROM sessions").fetchone()[0]

    def known_projects(self) -> list[str]:
        rows = self._conn().execute(
            "SELECT DISTINCT project_id FROM sessions WHERE project_id != '' ORDER BY 1"
        ).fetchall()
        return [r["project_id"] for r in rows]

    def close(self) -> None:
        conn = getattr(self._local, "conn", None)
        if conn is not None:
            conn.close()
            self._local.conn = None

    def health(self) -> dict[str, Any]:
        conn = self._conn()
        version = conn.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()
        return {
            "ok": True,
            "path": str(self.path),
            "sessions": int(self.count()),
            "schema_version": int(version[0]) if version else REGISTRY_SCHEMA_VERSION,
            "lease": self.lease_holder(),
        }

    def close(self) -> None:
        conn = getattr(self._local, "conn", None)
        if conn is not None:
            conn.close()
            self._local.conn = None


__all__ = ["Registry", "LeaseHeldError", "REGISTRY_SCHEMA_VERSION"]
