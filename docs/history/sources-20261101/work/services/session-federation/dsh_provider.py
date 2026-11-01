"""L0 discovery + L1 normalisation of native DSH sessions (WL-P0-080).

DSH (DeepSeek Harness) keeps two stores per session:

* ``~/.dsh/sessions/<encoded-project>/<uuid>/session.jsonl.zstd`` — the full
  event transcript, **zstd-compressed**.  It is the lossless source but
  requires a zstd codec to decode.
* ``~/.dsh/storages/session_projcache/sessions/<uuid>.json`` — an
  **uncompressed** projection cache (schema ``session_projcache/v5``):
  ``record.identity`` (cwd, createdAt) plus a ``record.rows`` map with
  turnOutline (per-turn prompt/response), todos, modelSelection,
  permissions, tokenUsage, contextPressure and goal.

This adapter reads the projection cache only, so it has **no external
dependency** (no zstd codec, no CLI) and stays strictly read-only.  The
trade-off is honest: the projection carries a per-turn *summary*, not the
full tool_call/tool_result/event stream, so the reader degrades to L1
handoff and reports the dropped channels in its metadata loss notes instead
of claiming L2/L3.  The zstd transcript path is recorded for provenance but
never decoded here.

``home`` is injectable so tests point the adapter at a scratch tree rather
than the real ``~/.dsh``.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import importlib.util as _ilu


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

_PROJ_CACHE_RELPATH = ("storages", "session_projcache", "sessions")


def _safe_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except (OSError, json.JSONDecodeError):
        return None


def _ms_to_iso(value: Any) -> str | None:
    """Convert an epoch-milliseconds timestamp to ISO-8601 UTC."""
    if isinstance(value, (int, float)) and value > 0:
        dt = datetime.fromtimestamp(value / 1000.0, tz=timezone.utc)
        return dt.strftime("%Y-%m-%dT%H:%M:%S")
    return None


def _norm_segment(path: str) -> str:
    """Normalise a cwd's final path segment for loose project matching.

    DSH stores cwd as a native path (``D:\\All projects\\WORK-LAB``).  Project
    ids are looser logical names (``work-lab``).  Comparing the last segment
    case-insensitively and stripping non-alphanumerics makes the two agree.
    """
    if not path:
        return ""
    last = str(path).replace("\\", "/").rstrip("/").split("/")[-1]
    return "".join(ch for ch in last.lower() if ch.isalnum())


def _row_val(rows: Any, key: str) -> Any:
    """Unwrap a projcache row: each ``rows[key]`` is ``{ver, seq, val}``.

    The actual value lives under ``val``.  Missing/malformed rows yield
    ``None`` (fail-soft — a projection can lag behind the live transcript).
    """
    if not isinstance(rows, dict):
        return None
    cell = rows.get(key)
    if isinstance(cell, dict) and "val" in cell:
        return cell.get("val")
    return cell


class DshSessionProvider:
    """Read-only DSH projection-cache discovery (L0) + normalisation (L1).

    Native stores (never written by this adapter):
      * ``~/.dsh/sessions/<proj>/<uuid>/session.jsonl.zstd``  (zstd transcript)
      * ``~/.dsh/storages/session_projcache/sessions/<uuid>.json`` (projection)
    """

    source_agent = "dsh"

    def __init__(self, home: str | Path | None = None) -> None:
        if home is not None:
            base = Path(home).expanduser().resolve()
        elif os.environ.get("DSH_HOME"):
            base = Path(os.environ["DSH_HOME"]).expanduser().resolve()
        else:
            base = (Path.home() / ".dsh").resolve()
        self.home = base
        self.projcache_dir = base.joinpath(*_PROJ_CACHE_RELPATH)
        # Full zstd transcripts, recorded for provenance only (not decoded).
        self.zstd_sessions_dir = base / "sessions"

    # -- L0 discovery -----------------------------------------------------
    def discover(self, project_id: str) -> Iterable[SessionRef]:
        refs: list[SessionRef] = []
        if not self.projcache_dir.is_dir():
            return refs
        target = _norm_segment(project_id)
        seen: set[str] = set()
        for path in sorted(self.projcache_dir.glob("*.json")):
            rec = _safe_json(path)
            identity = (rec or {}).get("record", {}).get("identity") if isinstance(rec, dict) else None
            if not isinstance(identity, dict):
                continue
            cwd = str(identity.get("cwd") or "")
            # Loose project match: cwd's final segment equals the requested
            # project, or the request is empty (enumerate everything).
            if target and _norm_segment(cwd) != target:
                continue
            uuid = path.stem
            if uuid in seen:
                continue
            seen.add(uuid)
            rows0 = (rec.get("record", {}).get("rows", {}) or {})
            model_sel = _row_val(rows0, "modelSelection") or {}
            last_used = model_sel.get("lastUsed") if isinstance(model_sel, dict) else None
            model = str(last_used.get("model")) if isinstance(last_used, dict) and last_used.get("model") else None
            slm = _row_val(rows0, "sessionListMetadata")
            last_prompt_at = slm.get("lastPromptAt") if isinstance(slm, dict) else None
            refs.append(
                SessionRef(
                    source_agent=self.source_agent,
                    source_session_id=uuid,
                    native_path=str(path),
                    project_id=cwd or project_id,
                    workspace_id="dsh",
                    started_at=_ms_to_iso(identity.get("createdAt")),
                    ended_at=_ms_to_iso(last_prompt_at),
                    native_hash=None,
                    model=model,
                )
            )
        return refs

    # -- L1 normalisation -------------------------------------------------
    def read(self, ref: SessionRef) -> "Any":
        rec = _safe_json(Path(ref.native_path)) or {}
        record = rec.get("record", {}) if isinstance(rec, dict) else {}
        identity = record.get("identity", {}) if isinstance(record, dict) else {}
        rows = record.get("rows", {}) if isinstance(record, dict) else {}
        cwd = str(identity.get("cwd") or ref.project_id or "")

        # turnOutline -> user/assistant message pairs (per-turn summary)
        outline = _row_val(rows, "turnOutline")
        turns = outline.get("turns", []) if isinstance(outline, dict) else []
        messages: list[dict[str, Any]] = []
        for t in turns:
            if not isinstance(t, dict):
                continue
            if t.get("prompt"):
                messages.append({"role": "user", "text": str(t["prompt"]), "turn": t.get("turn"), "seq": t.get("seq")})
            if t.get("response"):
                messages.append({"role": "assistant", "text": str(t["response"]), "turn": t.get("turn"), "seq": t.get("seq")})

        todos_raw = _row_val(rows, "todos")
        todos = [dict(x) for x in todos_raw if isinstance(x, dict)] if isinstance(todos_raw, list) else []

        model_sel = _row_val(rows, "modelSelection") or {}
        last_used = model_sel.get("lastUsed") if isinstance(model_sel, dict) else None
        model = str(last_used.get("model")) if isinstance(last_used, dict) and last_used.get("model") else None
        provider = str(last_used.get("provider")) if isinstance(last_used, dict) and last_used.get("provider") else None
        reasoning = str(last_used.get("reasoningEffort")) if isinstance(last_used, dict) and last_used.get("reasoningEffort") else None

        perms = _row_val(rows, "permissions") or {}
        tokens = _row_val(rows, "tokenUsage") or {}
        pressure = _row_val(rows, "contextPressure") or {}
        goal = _row_val(rows, "goal") or {}

        metadata: dict[str, Any] = {
            "model": model,
            "model_provider": provider,
            "reasoning_effort": reasoning,
            "agent_preset": _row_val(rows, "agentPreset"),
            "sandbox_mode": _row_val(rows, "sandboxMode"),
            "permissions": perms if isinstance(perms, dict) else None,
            "token_usage_totals": tokens.get("totals") if isinstance(tokens, dict) else None,
            "context_pressure": pressure if isinstance(pressure, dict) else None,
            "goal_current": (goal.get("current") if isinstance(goal, dict) else None),
            "source_format_detail": "dsh-projcache-v5",
        }
        # Honest loss accounting: the projection is a summary, not the full
        # event stream.  The lossless transcript is zstd-compressed and is
        # NOT decodable in this environment (no codec/CLI), so tool channels
        # are unavailable here.  We never claim L2/L3.
        loss_notes = {
            "messages": "retained as per-turn outline (prompt/response), not the full message stream",
            "tool_calls": "unavailable in projection cache; only in the zstd transcript",
            "tool_results": "unavailable in projection cache; only in the zstd transcript",
            "reasoning": "unavailable",
        }
        zstd_path = self.zstd_sessions_dir  # recorded for provenance only
        metadata["loss_report"] = {
            "messages": 0.5,
            "tool_calls": 0.0,
            "tool_results": 0.0,
            "reasoning": None,
            "native_state_available": False,
            "notes": {
                **loss_notes,
                "zstd_transcript": "full event transcript at ~/.dsh/sessions/<proj>/<uuid>/session.jsonl.zstd is zstd-compressed; no codec available in this runtime, so only the uncompressed projection is served",
            },
        }
        metadata["zstd_transcript_dir"] = str(zstd_path)

        import sys as _sys
        canonical = _sys.modules.get("services_session_federation_canonical")
        if canonical is None:
            here = Path(__file__).resolve().parent
            spec = _ilu.spec_from_file_location(
                "services_session_federation_canonical", here / "canonical.py"
            )
            canonical = _ilu.module_from_spec(spec)
            _sys.modules["services_session_federation_canonical"] = canonical
            spec.loader.exec_module(canonical)

        return canonical.CanonicalSession(
            universal_session_id=f"dsh:{ref.source_session_id}",
            workspace_id=ref.workspace_id or "dsh",
            project_id=cwd or ref.project_id,
            source_agent=self.source_agent,
            source_session_id=ref.source_session_id,
            source_format="dsh-projcache",
            native_path=str(ref.native_path),
            cwd=cwd or None,
            started_at=ref.started_at,
            ended_at=ref.ended_at,
            portability_level=canonical.PortabilityLevel.L1_HANDOFF,
            messages=tuple(messages),
            todos=tuple(todos),
            changed_files=(),
            metadata=metadata,
        )

    # -- health -----------------------------------------------------------
    def health(self) -> dict[str, Any]:
        available = self.projcache_dir.is_dir()
        notes: list[str] = []
        count = 0
        if available:
            count = len(list(self.projcache_dir.glob("*.json")))
        else:
            notes.append("projcache dir missing — no DSH sessions discovered")
        notes.append("full zstd transcripts not decoded (no codec) — projection-only L1 handoff")
        return {
            "ok": available,
            "agent": self.source_agent,
            "projcache_dir": str(self.projcache_dir),
            "session_count": count,
            "notes": notes,
        }


__all__ = ["DshSessionProvider"]
