"""L0 discovery of native Hermes sessions (WL-P0-030, first adapter).

Hermes keeps session records in its global state DB and JSONL ledgers
under ``HERMES_HOME`` / user home (``state.db``, session JSONL).  This
adapter is strictly *read-only* against those stores and only exposes
L0 discovery plus L1 normalisation for sessions that exist as JSONL
transcripts.  Missing or unreadable stores degrade to an empty result
set with a health note — they never fail-closed the federation layer.
"""
from __future__ import annotations

import json
import os
import sqlite3
import importlib.util as _ilu
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import quote


def _load_provider():
    here = Path(__file__).resolve().parent
    import sys as _sys
    name = "services_session_federation_provider"
    existing = _sys.modules.get(name)
    if existing is not None and getattr(existing, "SessionRef", None) is not None:
        return existing
    spec = _ilu.spec_from_file_location(name, here / "provider.py")
    module = _ilu.module_from_spec(spec)
    _sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


_SFP = _load_provider()
SessionRef = _SFP.SessionRef


class HermesSessionProvider:
    """Read-only Hermes session discovery (L0) + JSONL normalisation (L1).

    Native stores (never written by this adapter):
      * ``~/.hermes/sessions/*.jsonl``  – per-session JSONL transcripts
      * ``$HERMES_HOME/state.db``      – global state DB (session table)
    """

    source_agent = "hermes"

    def __init__(self, home: str | Path | None = None) -> None:
        if home is not None:
            base = Path(home).expanduser().resolve()
        elif os.environ.get("HERMES_HOME"):
            base = Path(os.environ["HERMES_HOME"]).expanduser().resolve()
        else:
            base = (Path.home() / ".hermes").resolve()
        self.home = base
        self.sessions_dir = base / "sessions"
        self.state_db = base / "state.db"

    # -- L0 discovery ----------------------------------------------------
    def discover(self, project_id: str) -> Iterable[SessionRef]:
        refs: list[SessionRef] = []
        if self.sessions_dir.is_dir():
            for path in sorted(self.sessions_dir.glob("*.jsonl")):
                ref = self._ref_from_jsonl(path, project_id)
                if ref is not None:
                    refs.append(ref)
        for ref in self._refs_from_state_db(project_id):
            if ref not in refs:
                refs.append(ref)
        return refs

    def _ref_from_jsonl(self, path: Path, project_id: str) -> SessionRef | None:
        try:
            first_line = next(iter(path.open(encoding="utf-8", errors="replace")), "")
        except OSError:
            return None
        record = _safe_json(first_line)
        if not isinstance(record, dict):
            return None
        project = str(record.get("project") or record.get("cwd") or project_id or "")
        ref = SessionRef(
            source_agent=self.source_agent,
            source_session_id=str(record.get("session_id") or path.stem),
            native_path=str(path),
            project_id=project or project_id,
            workspace_id=str(record.get("workspace") or "default"),
            started_at=record.get("started_at"),
            ended_at=record.get("ended_at"),
            model=record.get("model"),
        )
        return ref

    def _refs_from_state_db(self, project_id: str) -> list[SessionRef]:
        refs: list[SessionRef] = []
        if not self.state_db.is_file():
            return refs
        try:
            # Percent-encode the path: a literal `#` truncated the URI to a
            # writable file (same defect as CanonicalStore readonly), `%XX` was
            # silently decoded; safe="/" keeps as_posix() separators literal.
            conn = sqlite3.connect(
                f"file:{quote(self.state_db.as_posix(), safe='/')}?mode=ro", uri=True
            )
            try:
                tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
                if "sessions" not in tables:
                    return refs
                columns = [c[1] for c in conn.execute("PRAGMA table_info(sessions)")]
                select = ["session_id"] + [
                    c for c in ("project", "workspace", "started_at", "ended_at", "model") if c in columns
                ]
                rows = [list(r) for r in conn.execute(f"SELECT {', '.join(select)} FROM sessions")]
            finally:
                conn.close()
        except sqlite3.Error:
            return refs
        width = len(rows[0]) if rows else 0
        for value in rows:
            refs.append(
                SessionRef(
                    source_agent=self.source_agent,
                    source_session_id=str(value[0]),
                    native_path=str(self.state_db),
                    project_id=str(value[1]) if width > 1 and value[1] else project_id,
                    workspace_id=str(value[2]) if width > 2 and value[2] else "default",
                    started_at=str(value[3]) if width > 3 and value[3] else None,
                    ended_at=str(value[4]) if width > 4 and value[4] else None,
                    model=str(value[5]) if width > 5 and value[5] else None,
                )
            )
        return refs

    # -- L1 normalisation --------------------------------------------------
    def read(self, ref: SessionRef) -> Any:
        """Normalise a JSONL transcript into a CanonicalSession (L1 handoff)."""
        import sys as _sys

        canonical = _sys.modules.get("services_session_federation_canonical")
        if canonical is None:
            import importlib.util as _ilu

            here = Path(__file__).resolve().parent
            spec = _ilu.spec_from_file_location("services_session_federation_canonical", here / "canonical.py")
            canonical = _ilu.module_from_spec(spec)
            _sys.modules["services_session_federation_canonical"] = canonical
            spec.loader.exec_module(canonical)

        path = Path(ref.native_path)
        events: list[dict[str, Any]] = []
        messages: list[dict[str, Any]] = []
        decisions: list[dict[str, Any]] = []
        todos: list[dict[str, Any]] = []
        changed: set[str] = set()
        started_at = ref.started_at
        ended_at = ref.ended_at
        if path.suffix == ".jsonl" and path.is_file():
            for line in path.open(encoding="utf-8", errors="replace"):
                record = _safe_json(line)
                if not isinstance(record, dict):
                    continue
                kind = str(record.get("type") or record.get("event") or "")
                ts = record.get("ts") or record.get("timestamp")
                if ts and not started_at:
                    started_at = str(ts)
                if ts:
                    ended_at = str(ts)
                if kind in ("user_message", "assistant_message"):
                    messages.append({"role": kind.split("_")[0], "text": str(record.get("text") or record.get("content") or "")})
                    events.append({"type": kind, "ts": ts, "text": messages[-1]["text"]})
                elif kind in ("tool_call", "tool_result", "shell", "file_read", "file_write", "patch"):
                    events.append({"type": kind, "ts": ts, "data": record.get("data")})
                    target = record.get("path") or record.get("file")
                    if target and kind in ("file_write", "patch", "file_read"):
                        changed.add(str(target))
                elif kind == "decision":
                    decisions.append({"decision": str(record.get("choice") or record.get("text")), "why": str(record.get("reason") or "")})
                elif kind == "todo":
                    todos.append({"text": str(record.get("text")), "state": str(record.get("state") or "open")})
        return canonical.CanonicalSession(
            universal_session_id=f"hermes:{ref.source_session_id}",
            workspace_id=ref.workspace_id,
            project_id=ref.project_id,
            source_agent=self.source_agent,
            source_session_id=ref.source_session_id,
            source_format="hermes-jsonl" if path.suffix == ".jsonl" else "hermes-state-db",
            native_path=str(path),
            cwd=ref.project_id,
            started_at=started_at,
            ended_at=ended_at,
            portability_level=canonical.PortabilityLevel.L1_HANDOFF,
            messages=tuple(messages),
            events=tuple(events),
            decisions=tuple(decisions),
            todos=tuple(todos),
            changed_files=tuple(sorted(changed)),
        )

    # -- health ------------------------------------------------------------
    def health(self) -> dict[str, Any]:
        notes: list[str] = []
        if not self.sessions_dir.is_dir():
            notes.append("sessions dir missing")
        if not self.state_db.is_file():
            notes.append("state.db missing")
        # healthy when at least one native source is reachable
        ok = self.sessions_dir.is_dir() or self.state_db.is_file()
        return {"source_agent": self.source_agent, "ok": ok, "notes": notes, "home": str(self.home)}

    # -- native resume (L3) ------------------------------------------------
    def resume_native(self, session: Any) -> str:
        return f"hermes --resume {session.source_session_id}"


def _safe_json(text: str) -> Any:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


__all__ = ["HermesSessionProvider"]
