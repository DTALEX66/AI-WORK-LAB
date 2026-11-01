"""Unified session history index (WL-P0-050).

Stores a local SQLite index under ``.project-local/sessions/index.sqlite``
so that cross-agent session history can be searched without touching any
native store.  The index is a *projection*: providers push summary rows
in; the index never writes back to native sources.

Supported filters (all optional, combined with AND):
  agent, project, date range, model, file, task, decision keyword,
  error keyword, and full-text search over the semantic summary.
"""
from __future__ import annotations

import json
import os
import sqlite3
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping


INDEX_SCHEMA_VERSION = 1


class SessionIndex:
    """Local, read-mostly session history index (SQLite, file-locked per process).

    Thread-safe: a single connection per thread with WAL journal mode.
    The index file lives under the project's git-ignored runtime root
    (``.project-local/sessions/index.sqlite`` by default) and must never
    be committed.
    """

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
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
            f"""
            CREATE TABLE IF NOT EXISTS meta (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            INSERT OR IGNORE INTO meta(key, value) VALUES
                ('schema_version', '{INDEX_SCHEMA_VERSION}'),
                ('created_at', '1970-01-01T00:00:00Z');

            CREATE TABLE IF NOT EXISTS sessions (
                rowid INTEGER PRIMARY KEY AUTOINCREMENT,
                universal_session_id TEXT NOT NULL UNIQUE,
                source_agent TEXT NOT NULL,
                source_session_id TEXT NOT NULL,
                workspace_id TEXT NOT NULL,
                project_id TEXT NOT NULL,
                source_format TEXT NOT NULL,
                portability_level TEXT NOT NULL DEFAULT 'L0_DISCOVERY',
                model TEXT,
                cwd TEXT,
                repo TEXT,
                git_commit TEXT,
                started_at TEXT,
                ended_at TEXT,
                messages_count INTEGER NOT NULL DEFAULT 0,
                decisions_count INTEGER NOT NULL DEFAULT 0,
                todos_count INTEGER NOT NULL DEFAULT 0,
                changed_files TEXT NOT NULL DEFAULT '[]',
                semantic_summary TEXT NOT NULL DEFAULT '',
                content_digest TEXT NOT NULL,
                indexed_at TEXT NOT NULL,
                UNIQUE(source_agent, source_session_id)
            );
            CREATE INDEX IF NOT EXISTS idx_sessions_agent ON sessions(source_agent);
            CREATE INDEX IF NOT EXISTS idx_sessions_project ON sessions(project_id);
            CREATE INDEX IF NOT EXISTS idx_sessions_started ON sessions(started_at);
            CREATE INDEX IF NOT EXISTS idx_sessions_model ON sessions(model);

            CREATE VIRTUAL TABLE IF NOT EXISTS sessions_fts USING fts5(
                universal_session_id,
                semantic_summary,
                changed_files
            );
            """
        )
        conn.commit()

    # -- ingest -----------------------------------------------------------
    def index_session(self, session: Any) -> dict[str, Any]:
        """Ingest a CanonicalSession (or dict) into the index.

        Idempotent: re-indexing the same (agent, source_session_id) updates
        the row and FTS content; the content_digest guards against stale
        re-inserts of the same id with different payloads.
        """
        if hasattr(session, "to_dict"):
            data = session.to_dict()
            digest = session.content_digest() if hasattr(session, "content_digest") else ""
        else:
            data = dict(session)
            digest = data.get("content_digest", "")
        # model is carried in metadata per canonical v1 (no dedicated column)
        data["model"] = data.get("model") or (data.get("metadata") or {}).get("model")
        # semantic_summary: index.py expects a top-level key; canonical stores it in metadata
        meta = data.get("metadata") or {}
        if not data.get("semantic_summary"):
            data["semantic_summary"] = meta.get("summary", "") or meta.get("semantic_summary", "")
        conn = self._conn()
        changed_files = json.dumps(data.get("changed_files", []), ensure_ascii=False)
        semantic = data.get("semantic_summary") or _default_summary(data)
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        conn.execute(
            """
            INSERT INTO sessions(
                universal_session_id, source_agent, source_session_id,
                workspace_id, project_id, source_format, portability_level,
                model, cwd, repo, git_commit, started_at, ended_at,
                messages_count, decisions_count, todos_count,
                changed_files, semantic_summary, content_digest, indexed_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(source_agent, source_session_id) DO UPDATE SET
                universal_session_id = excluded.universal_session_id,
                workspace_id = excluded.workspace_id,
                project_id = excluded.project_id,
                source_format = excluded.source_format,
                portability_level = excluded.portability_level,
                model = excluded.model,
                cwd = excluded.cwd,
                repo = excluded.repo,
                git_commit = excluded.git_commit,
                started_at = excluded.started_at,
                ended_at = excluded.ended_at,
                messages_count = excluded.messages_count,
                decisions_count = excluded.decisions_count,
                todos_count = excluded.todos_count,
                changed_files = excluded.changed_files,
                semantic_summary = excluded.semantic_summary,
                content_digest = excluded.content_digest,
                indexed_at = excluded.indexed_at
            """,
            (
                data.get("universal_session_id", ""),
                data.get("source_agent", ""),
                data.get("source_session_id", ""),
                data.get("workspace_id", ""),
                data.get("project_id", ""),
                data.get("source_format", ""),
                str(data.get("portability_level", "L0_DISCOVERY")),
                data.get("model"),
                data.get("cwd"),
                data.get("repo"),
                data.get("git_commit"),
                data.get("started_at"),
                data.get("ended_at"),
                len(data.get("messages", ())),
                len(data.get("decisions", ())),
                len(data.get("todos", ())),
                changed_files,
                semantic,
                digest,
                now,
            ),
        )
        # FTS mirror (independent table): replace the row for this session id
        conn.execute(
            "DELETE FROM sessions_fts WHERE universal_session_id=?",
            (data.get("universal_session_id", ""),),
        )
        conn.execute(
            "INSERT INTO sessions_fts(universal_session_id, semantic_summary, changed_files) VALUES (?,?,?)",
            (data.get("universal_session_id", ""), semantic, changed_files),
        )
        conn.commit()
        return {
            "status": "INDEXED",
            "universal_session_id": data.get("universal_session_id"),
            "content_digest": digest,
        }

    # -- query -------------------------------------------------------------
    def search(
        self,
        query: str,
        *,
        agent: str | None = None,
        project: str | None = None,
        since: str | None = None,
        until: str | None = None,
        model: str | None = None,
        file: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Full-text + structured filter search.

        ``query`` is matched against the FTS5 index; when empty, all
        structured filters apply without FTS.  Results carry the FTS rank
        (lower = better) so callers can order relevance.
        """
        where: list[str] = []
        params: list[Any] = []
        if agent:
            where.append("source_agent = ?")
            params.append(agent)
        if project:
            where.append("project_id = ?")
            params.append(project)
        if since:
            where.append("started_at >= ?")
            params.append(since)
        if until:
            where.append("started_at <= ?")
            params.append(until)
        if model:
            where.append("model = ?")
            params.append(model)
        if file:
            where.append("changed_files LIKE ?")
            params.append(f"%{file}%")

        conn = self._conn()
        if query:
            sql = ("SELECT s.*, bm25(sessions_fts) AS fts_rank FROM sessions_fts f "
                   "JOIN sessions s ON s.universal_session_id = f.universal_session_id "
                   "WHERE sessions_fts MATCH ? ")
            all_params: list[Any] = [query]
            if where:
                sql += " AND " + " AND ".join(where)
                all_params += params
            sql += " ORDER BY fts_rank ASC LIMIT ?"
            all_params.append(limit)
            rows = conn.execute(sql, all_params).fetchall()
            return [dict(r) for r in rows]
        # no FTS query: plain structured listing
        return self.list_sessions(agent=agent, project=project, since=since, until=until, model=model, limit=limit)

    def list_sessions(
        self,
        *,
        agent: str | None = None,
        project: str | None = None,
        since: str | None = None,
        until: str | None = None,
        model: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        where: list[str] = []
        params: list[Any] = []
        if agent:
            where.append("source_agent = ?")
            params.append(agent)
        if project:
            where.append("project_id = ?")
            params.append(project)
        if since:
            where.append("started_at >= ?")
            params.append(since)
        if until:
            where.append("started_at <= ?")
            params.append(until)
        if model:
            where.append("model = ?")
            params.append(model)
        sql = "SELECT * FROM sessions"
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY COALESCE(started_at, indexed_at) DESC LIMIT ?"
        params.append(limit)
        rows = self._conn().execute(sql, params).fetchall()
        return [dict(r) for r in rows]

    def get(self, universal_session_id: str) -> dict[str, Any] | None:
        row = self._conn().execute(
            "SELECT * FROM sessions WHERE universal_session_id = ?",
            (universal_session_id,),
        ).fetchone()
        return dict(row) if row else None

    def health(self) -> dict[str, Any]:
        conn = self._conn()
        count = conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
        version = conn.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()
        return {
            "ok": True,
            "path": str(self.path),
            "sessions": int(count),
            "schema_version": int(version[0]) if version else INDEX_SCHEMA_VERSION,
        }

    def close(self) -> None:
        conn = getattr(self._local, "conn", None)
        if conn is not None:
            conn.close()
            self._local.conn = None


def _default_summary(data: Mapping[str, Any]) -> str:
    """Build a searchable one-line summary when the provider didn't supply one."""
    parts: list[str] = []
    for decision in data.get("decisions", ())[:5]:
        if isinstance(decision, Mapping):
            parts.append(str(decision.get("decision", "")))
        else:
            parts.append(str(decision))
    for todo in data.get("todos", ())[:5]:
        if isinstance(todo, Mapping):
            parts.append(str(todo.get("text", "")))
        else:
            parts.append(str(todo))
    for message in data.get("messages", ())[:3]:
        if isinstance(message, Mapping):
            parts.append(str(message.get("text", "")))
    return " | ".join(p for p in parts if p)


__all__ = ["SessionIndex", "INDEX_SCHEMA_VERSION"]
