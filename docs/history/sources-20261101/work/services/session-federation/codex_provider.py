"""L0 discovery + L1 normalisation of native Codex sessions (WL-P0-070).

Codex CLI keeps rollouts under ``~/.codex/sessions/YYYY/MM/DD/rollout-*.jsonl``.
Each line is an envelope ``{timestamp, ordinal, type, payload}`` where ``type``
is one of ``session_meta``, ``turn_context``, ``response_item``, ``event_msg``,
``token_usage_record`` and friends.

This adapter is strictly *read-only* against that store and only exposes L0
discovery plus L1 semantic normalisation.  It never mutates the source, never
reads ``auth.json`` / credentials, and degrades to an empty result set (with a
health note) when the native store is absent — it does not fail-closed the
federation layer.

``home`` is injectable so tests can point the adapter at a scratch tree instead
of the real ``~/.codex``.
"""
from __future__ import annotations

import json
import os
import re
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

# rollout-<UTC ts>-<uuid>.jsonl
_ROLLOUT_RE = re.compile(r"rollout-(?P<ts>\d{4}-\d{2}-\d{2}T[\d-]+)-(?P<uuid>[0-9a-f-]+)\.jsonl$")


def _safe_json(text: str) -> Any:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def _text_of_content(content: Any) -> str:
    """Flatten an OpenAI-style content field into plain text (no bodies leaked)."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, dict):
                parts.append(str(block.get("text") or block.get("summary") or ""))
            elif isinstance(block, str):
                parts.append(block)
        return " ".join(p for p in parts if p)
    if isinstance(content, dict):
        return str(content.get("text") or content.get("summary") or "")
    return ""


class CodexSessionProvider:
    """Read-only Codex rollout discovery (L0) + JSONL normalisation (L1).

    Native store (never written by this adapter):
      * ``~/.codex/sessions/YYYY/MM/DD/rollout-*.jsonl`` – per-session rollouts
    """

    source_agent = "codex"

    def __init__(self, home: str | Path | None = None) -> None:
        if home is not None:
            base = Path(home).expanduser().resolve()
        elif os.environ.get("CODEX_HOME"):
            base = Path(os.environ["CODEX_HOME"]).expanduser().resolve()
        else:
            base = (Path.home() / ".codex").resolve()
        self.home = base
        self.sessions_dir = base / "sessions"

    # -- L0 discovery -----------------------------------------------------
    def discover(self, project_id: str) -> Iterable[SessionRef]:
        refs: list[SessionRef] = []
        if not self.sessions_dir.is_dir():
            return refs
        for path in sorted(self.sessions_dir.glob("**/rollout-*.jsonl")):
            ref = self._ref_from_rollout(path, project_id)
            if ref is not None and ref not in refs:
                refs.append(ref)
        return refs

    def _ref_from_rollout(self, path: Path, project_id: str) -> SessionRef | None:
        # The first line of a rollout is the session_meta envelope; read only
        # the head so a 70 MB session costs a single line, not a full scan.
        meta = None
        try:
            with path.open(encoding="utf-8", errors="replace") as fh:
                for _ in range(4):
                    record = _safe_json(fh.readline())
                    if isinstance(record, dict) and record.get("type") == "session_meta":
                        meta = record.get("payload")
                        break
        except OSError:
            return None

        match = _ROLLOUT_RE.search(path.name)
        file_uuid = match.group("uuid") if match else path.stem
        payload = meta if isinstance(meta, dict) else {}
        cwd = str(payload.get("cwd") or "") or None
        model_provider = payload.get("model_provider")
        session_id = str(payload.get("session_id") or file_uuid)
        # The rollout filename encodes the UTC start with dashes instead of
        # colons (filesystem-safe): "rollout-2026-09-13T02-58-28-<uuid>.jsonl".
        started_at: str | None = None
        if match:
            raw_ts = match.group("ts")  # "2026-09-13T02-58-28"
            if "T" in raw_ts:
                date_part, time_part = raw_ts.split("T", 1)
                started_at = f"{date_part}T{time_part.replace('-', ':')}"
        ref = SessionRef(
            source_agent=self.source_agent,
            source_session_id=session_id,
            native_path=str(path),
            project_id=cwd or project_id,
            workspace_id=str(payload.get("workspace") or "codex"),
            started_at=started_at,
            ended_at=None,
            # ref.model carries the *model name* when known; the provider is
            # captured separately in metadata by read().
            model=None,
        )
        return ref

    # -- L1 normalisation --------------------------------------------------
    def read(self, ref: SessionRef) -> Any:
        """Normalise a Codex rollout into a CanonicalSession (L1 handoff)."""
        import sys as _sys

        canonical = _sys.modules.get("services_session_federation_canonical")
        if canonical is None:
            spec = _ilu.spec_from_file_location(
                "services_session_federation_canonical",
                Path(__file__).resolve().parent / "canonical.py",
            )
            canonical = _ilu.module_from_spec(spec)
            _sys.modules["services_session_federation_canonical"] = canonical
            spec.loader.exec_module(canonical)

        path = Path(ref.native_path)
        messages: list[dict[str, Any]] = []
        events: list[dict[str, Any]] = []
        decisions: list[dict[str, Any]] = []
        todos: list[dict[str, Any]] = []
        changed: set[str] = set()
        git_commit: str | None = None
        model: str | None = ref.model          # model *name* (turn_context.model)
        model_provider: str | None = None      # model *provider* (session_meta.model_provider)
        usage_total: int | None = None
        ended_at = ref.ended_at
        started_at = ref.started_at
        project_id = ref.project_id
        if path.suffix == ".jsonl" and path.is_file():
            for line in path.open(encoding="utf-8", errors="replace"):
                record = _safe_json(line)
                if not isinstance(record, dict):
                    continue
                rtype = record.get("type")
                payload = record.get("payload")
                ts = record.get("timestamp")
                if ts and not started_at:
                    started_at = str(ts)
                if ts:
                    ended_at = str(ts)

                if rtype == "session_meta" and isinstance(payload, dict):
                    git = payload.get("git")
                    if isinstance(git, dict):
                        git_commit = git.get("commit") or git.get("sha") or git_commit
                    if payload.get("model_provider"):
                        model_provider = str(payload["model_provider"])
                    if payload.get("cwd") and not project_id:
                        project_id = str(payload["cwd"])

                elif rtype == "turn_context" and isinstance(payload, dict):
                    if payload.get("model") and not model:
                        model = str(payload["model"])
                    if payload.get("cwd") and not project_id:
                        project_id = str(payload["cwd"])

                elif rtype == "token_usage_record" and isinstance(payload, dict):
                    usage = payload.get("usage") or payload.get("turn_token_usage")
                    if isinstance(usage, dict) and usage.get("total_tokens") is not None:
                        usage_total = int(usage["total_tokens"])

                elif rtype == "response_item" and isinstance(payload, dict):
                    self._fold_response_item(payload, ts, messages, events, decisions, todos, changed)

                elif rtype == "event_msg" and isinstance(payload, dict):
                    sub = payload.get("type")
                    events.append({"type": f"event_msg:{sub}" if sub else "event_msg", "ts": ts})

        metadata: dict[str, Any] = {"model": model, "model_provider": model_provider, "usage_total_tokens": usage_total}
        if git_commit:
            metadata["git_commit"] = git_commit
        return canonical.CanonicalSession(
            universal_session_id=f"codex:{ref.source_session_id}",
            workspace_id=ref.workspace_id,
            project_id=project_id or ref.project_id,
            source_agent=self.source_agent,
            source_session_id=ref.source_session_id,
            source_format="codex-rollout-jsonl",
            native_path=str(path),
            cwd=project_id,
            git_commit=git_commit,
            started_at=started_at,
            ended_at=ended_at,
            portability_level=canonical.PortabilityLevel.L1_HANDOFF,
            messages=tuple(messages),
            events=tuple(events),
            decisions=tuple(decisions),
            todos=tuple(todos),
            changed_files=tuple(sorted(changed)),
            metadata=metadata,
        )

    @staticmethod
    def _fold_response_item(
        payload: dict[str, Any],
        ts: Any,
        messages: list,
        events: list,
        decisions: list,
        todos: list,
        changed: set,
    ) -> None:
        sub = payload.get("type")
        # chat messages (role user/assistant/developer)
        if sub in ("message", "agent_message"):
            role = str(payload.get("role") or "assistant")
            text = _text_of_content(payload.get("content"))
            messages.append({"role": role, "text": text})
            events.append({"type": "user_message" if role == "user" else "assistant_message", "ts": ts, "text": text})
        elif sub == "reasoning":
            summary = _text_of_content(payload.get("summary"))
            events.append({"type": "reasoning", "ts": ts, "summary": summary})
        elif sub in ("function_call", "custom_tool_call"):
            name = str(payload.get("name") or "tool")
            events.append({"type": "tool_call", "ts": ts, "name": name, "id": payload.get("call_id")})
            CodexSessionProvider._extract_file_target(payload, name, changed)
        elif sub in ("function_call_output", "custom_tool_call_output"):
            events.append({"type": "tool_result", "ts": ts, "id": payload.get("call_id")})

    @staticmethod
    def _extract_file_target(payload: dict[str, Any], tool_name: str, changed: set) -> None:
        """Best-effort: record file paths touched by patch/edit/shell tools."""
        if tool_name not in ("apply_patch", "edit_file", "write_file", "patch", "shell", "sh", "bash"):
            return
        inp = payload.get("input") or payload.get("arguments")
        candidates: list[Any] = []
        if isinstance(inp, dict):
            candidates = [inp.get("path"), inp.get("file"), inp.get("cmd")]
        elif isinstance(inp, str):
            candidates = [inp]
        for cand in candidates:
            if cand and not str(cand).startswith(("[", "{")):
                changed.add(str(cand))

    # -- health -----------------------------------------------------------
    def health(self) -> dict[str, Any]:
        notes: list[str] = []
        if not self.sessions_dir.is_dir():
            notes.append("sessions dir missing")
        ok = self.sessions_dir.is_dir()
        return {
            "source_agent": self.source_agent,
            "ok": ok,
            "notes": notes,
            "home": str(self.home),
        }

    # -- native resume (L3) -----------------------------------------------
    def resume_native(self, session: Any) -> str:
        return f"codex exec resume {session.source_session_id}"


__all__ = ["CodexSessionProvider"]
