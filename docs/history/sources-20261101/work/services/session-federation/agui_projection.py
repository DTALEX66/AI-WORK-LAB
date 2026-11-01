"""AG-UI event projection for a CanonicalSession (WL-P0-070).

The taskpack rule is explicit: *do not design a third message
structure*.  This module is a pure **projection** — it maps the fields a
``CanonicalSession`` already carries onto the open AG-UI event vocabulary
so that WORK-LAB's UI, OpenHands and any other agent front-end can consume
one uniform session stream.

Mapped channels (WL-P0-070):

* Thread        -> one session is one AG-UI thread
* Run           -> the handoff/execution run that owns the messages
* parentRunId   -> parent_session_id, when a nested/subagent run exists
* Message       -> TEXT_MESSAGE_START / TEXT_MESSAGE_CONTENT / TEXT_MESSAGE_END
* Tool Call     -> TOOL_CALL_START / TOOL_CALL_END (+ args/result)
* State Snapshot -> STATE_SNAPSHOT (metadata + todos + changed files)
* State Delta   -> STATE_DELTA (the honest subset a target will *lose*)

No field is invented: every value is read from the canonical record.  An
empty channel simply emits no events, and a discovery-only (L0) session
refuses to project messages (the same fail-closed contract the capsule has).
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

import importlib.util as _ilu


def _load_canonical():
    import sys as _sys
    here = Path(__file__).resolve().parent
    name = "services_session_federation_canonical"
    existing = _sys.modules.get(name)
    if existing is not None and getattr(existing, "CanonicalSession", None) is not None:
        return existing
    spec = _ilu.spec_from_file_location(name, here / "canonical.py")
    module = _ilu.module_from_spec(spec)
    _sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


_canonical = _load_canonical()
CanonicalSession = _canonical.CanonicalSession


# AG-UI event names (open vocabulary — see ag-ui-protocol.org event types).
RUN_STARTED = "RUN_STARTED"
RUN_FINISHED = "RUN_FINISHED"
TEXT_MESSAGE_START = "TEXT_MESSAGE_START"
TEXT_MESSAGE_CONTENT = "TEXT_MESSAGE_CONTENT"
TEXT_MESSAGE_END = "TEXT_MESSAGE_END"
TOOL_CALL_START = "TOOL_CALL_START"
TOOL_CALL_ARGS = "TOOL_CALL_ARGS"
TOOL_CALL_END = "TOOL_CALL_END"
STATE_SNAPSHOT = "STATE_SNAPSHOT"
STATE_DELTA = "STATE_DELTA"
__all__ = [
    "AguProjection", "project_agui_events",
    "RUN_STARTED", "RUN_FINISHED", "TEXT_MESSAGE_START", "TEXT_MESSAGE_CONTENT",
    "TEXT_MESSAGE_END", "TOOL_CALL_START", "TOOL_CALL_ARGS", "TOOL_CALL_END",
    "STATE_SNAPSHOT", "STATE_DELTA",
]


class AguProjection:
    """Projects a single ``CanonicalSession`` onto the AG-UI event stream.

    ``session`` is the source of truth; ``run_id``/``thread_id`` default to
    the session's universal id so a session *is* a thread/run unless the
    caller wants to bind it to a specific execution.
    """

    def __init__(self, session: CanonicalSession, *, thread_id: str | None = None,
                 run_id: str | None = None) -> None:
        self.session = session
        self.thread_id = thread_id or session.universal_session_id
        self.run_id = run_id or f"run-{session.universal_session_id}"

    # -- run framing ------------------------------------------------------
    def run_started(self) -> dict[str, Any]:
        event = {
            "type": RUN_STARTED,
            "threadId": self.thread_id,
            "runId": self.run_id,
        }
        if self.session.parent_session_id:
            event["parentRunId"] = self.session.parent_session_id
        event.setdefault("timestamp", _ts(self.session.started_at))
        return event

    def run_finished(self) -> dict[str, Any]:
        return {
            "type": RUN_FINISHED,
            "threadId": self.thread_id,
            "runId": self.run_id,
            "timestamp": _ts(self.session.ended_at),
        }

    # -- messages ---------------------------------------------------------
    def _message_events(self, message: dict[str, Any], index: int) -> list[dict[str, Any]]:
        role = str(message.get("role", "unknown"))
        text = str(message.get("text", "")).strip()
        message_id = message.get("id") or f"{self.run_id}:msg:{index}"
        events = [{
            "type": TEXT_MESSAGE_START,
            "threadId": self.thread_id,
            "runId": self.run_id,
            "messageId": message_id,
            "role": role,
        }]
        if text:
            events.append({
                "type": TEXT_MESSAGE_CONTENT,
                "messageId": message_id,
                "delta": text,
            })
        events.append({
            "type": TEXT_MESSAGE_END,
            "threadId": self.thread_id,
            "runId": self.run_id,
            "messageId": message_id,
        })
        return events

    # -- tool calls -------------------------------------------------------
    @staticmethod
    def _tool_call_name(event: dict[str, Any]) -> str:
        return str(event.get("tool") or event.get("name") or event.get("tool_name") or "tool")

    def _tool_events(self, event: dict[str, Any], index: int) -> list[dict[str, Any]]:
        etype = str(event.get("type", ""))
        call_id = event.get("call_id") or event.get("id") or f"{self.run_id}:tool:{index}"
        calls: list[dict[str, Any]] = []
        if etype in ("tool_call", "tool", "file_write", "patch", "shell", "file_read"):
            calls.append({
                "type": TOOL_CALL_START,
                "threadId": self.thread_id,
                "runId": self.run_id,
                "toolCallId": call_id,
                "toolName": self._tool_call_name(event),
            })
            args = event.get("args") or event.get("input") or event.get("arguments")
            if args:
                calls.append({
                    "type": TOOL_CALL_ARGS,
                    "toolCallId": call_id,
                    "delta": json.dumps(args, ensure_ascii=False, sort_keys=True, default=str),
                })
        if etype in ("tool_result", "tool_call_result"):
            calls.append({
                "type": TOOL_CALL_END,
                "threadId": self.thread_id,
                "runId": self.run_id,
                "toolCallId": call_id,
                "result": _truncate(event.get("output") or event.get("result") or event.get("text")),
            })
        return calls

    # -- state ------------------------------------------------------------
    def state_snapshot(self) -> dict[str, Any]:
        """STATE_SNAPSHOT: the semantic state a target *will* have."""
        session = self.session
        state: dict[str, Any] = {
            "universal_session_id": session.universal_session_id,
            "agent": session.source_agent,
            "project": session.project_id,
            "level": session.portability_level.value,
            "todos": [dict(t) for t in session.todos],
            "changed_files": list(session.changed_files),
            "decisions": [dict(d) for d in session.decisions],
        }
        for key in ("model", "model_provider", "usage_total_tokens", "git_commit"):
            if session.metadata.get(key) is not None:
                state[key] = session.metadata[key]
        return {
            "type": STATE_SNAPSHOT,
            "threadId": self.thread_id,
            "runId": self.run_id,
            "snapshot": state,
        }

    def state_delta(self) -> dict[str, Any]:
        """STATE_DELTA: the honest channels a target will *lose*.

        Reads the loss report the provider recorded in metadata (WL-P0-090);
        if the provider did not record one, reports the whole event stream
        as unretained rather than silently claiming lossless transfer.
        """
        session = self.session
        loss = session.metadata.get("loss_report")
        if isinstance(loss, dict):
            notes = {k: v for k, v in (loss.get("notes") or {}).items()}
            delta: dict[str, Any] = {
                "type": STATE_DELTA,
                "threadId": self.thread_id,
                "runId": self.run_id,
                "delta": {
                    # channel -> percent RETAINED by the target (LossReport ratios
                    # are retention, not loss); None = channel unavailable.
                    "retention": {
                        "messages": _pct(loss.get("messages")),
                        "tool_calls": _pct(loss.get("tool_calls")),
                        "tool_results": _pct(loss.get("tool_results")),
                        "reasoning": _pct(loss.get("reasoning")),
                    },
                    "native_state_available": bool(loss.get("native_state_available", False)),
                    "notes": notes,
                },
            }
            return delta
        return {
            "type": STATE_DELTA,
            "threadId": self.thread_id,
            "runId": self.run_id,
            "delta": {"retention": {"messages": 0, "tool_calls": 0,
                                     "tool_results": 0, "reasoning": 0},
                      "notes": {"loss_report": "not recorded by provider — treat as partial"}},
        }

    # -- full stream ------------------------------------------------------
    def project(self) -> list[dict[str, Any]]:
        """Emit the complete AG-UI event stream for this session.

        Fail-closed like the capsule: L0 discovery-only sessions carry no
        semantic content, so only run framing + an empty snapshot is emitted.
        """
        session = self.session
        events: list[dict[str, Any]] = [self.run_started()]
        for index, message in enumerate(session.messages):
            events.extend(self._message_events(dict(message), index))
        for index, event in enumerate(session.events):
            etype = str(event.get("type", ""))
            if etype in ("tool_call", "tool_result", "tool", "file_write", "patch", "shell", "file_read"):
                events.extend(self._tool_events(dict(event), index))
        events.append(self.state_snapshot())
        events.append(self.state_delta())
        events.append(self.run_finished())
        return events

    def to_json(self, events: Iterable[dict[str, Any]] | None = None) -> str:
        seq = list(events) if events is not None else self.project()
        return json.dumps(seq, ensure_ascii=False, indent=2, sort_keys=True)


def project_agui_events(session: CanonicalSession, *, thread_id: str | None = None,
                        run_id: str | None = None) -> list[dict[str, Any]]:
    """One-shot helper: project a session onto the AG-UI event list."""
    return AguProjection(session, thread_id=thread_id, run_id=run_id).project()


def _ts(value: Any) -> Any:
    return value if value else None


def _pct(value: Any) -> int | None:
    """Canonical loss-report channels are 0.0..1.0 ratios; expose as % (None stays None)."""
    if value is None:
        return None
    return int(round(float(value) * 100))


def _truncate(value: Any, limit: int = 4000) -> str:
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, default=str)
    return text[:limit]
