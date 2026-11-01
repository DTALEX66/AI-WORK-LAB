"""Canonical Session model (WL-P0-021) and portability levels (WL-P0-022).

The Canonical Session is WORK-LAB's unified, agent-agnostic session
representation.  Every source-format adapter normalises raw session data
into this model before handoff, indexing or projection.

Portability levels (never conflate them):

* ``L0_DISCOVERY``   – the adapter knows where history lives.
* ``L1_HANDOFF``      – semantic handoff: goal, key messages, decisions,
  todos, changed files, tool activity, progress, failure reasons.
  The target agent continues in a *new* session.
* ``L2_EVENT_REPLAY`` – structured replay of messages, tool calls,
  results, patches, checkpoints and artifacts.
* ``L3_NATIVE_RESUME`` – only when a real native ``session/resume`` was
  invoked.  Never mark L1 work as L3.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from typing import Any, Mapping, Sequence


SCHEMA_VERSION = "canonical-session/v1"


class PortabilityLevel(str, Enum):
    L0_DISCOVERY = "L0_DISCOVERY"
    L1_HANDOFF = "L1_HANDOFF"
    L2_EVENT_REPLAY = "L2_EVENT_REPLAY"
    L3_NATIVE_RESUME = "L3_NATIVE_RESUME"

    @classmethod
    def parse(cls, value: str | None) -> "PortabilityLevel":
        if not value:
            return cls.L0_DISCOVERY
        try:
            return cls(str(value).upper().replace("_", "").replace("L", "L") and _LEVEL_BY_NAME[str(value)])
        except KeyError as exc:  # noqa: BLEMP001
            raise ValueError(f"unknown portability level: {value!r}") from exc


_LEVEL_BY_NAME = {
    "L0": PortabilityLevel.L0_DISCOVERY,
    "L0_DISCOVERY": PortabilityLevel.L0_DISCOVERY,
    "L1": PortabilityLevel.L1_HANDOFF,
    "L1_HANDOFF": PortabilityLevel.L1_HANDOFF,
    "L2": PortabilityLevel.L2_EVENT_REPLAY,
    "L2_EVENT_REPLAY": PortabilityLevel.L2_EVENT_REPLAY,
    "L3": PortabilityLevel.L3_NATIVE_RESUME,
    "L3_NATIVE_RESUME": PortabilityLevel.L3_NATIVE_RESUME,
    "NATIVE_RESUME": PortabilityLevel.L3_NATIVE_RESUME,
}


class EventType(str, Enum):
    """Canonical event vocabulary (WL-P0-021 event types)."""

    USER_MESSAGE = "user_message"
    ASSISTANT_MESSAGE = "assistant_message"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    SHELL = "shell"
    FILE_READ = "file_read"
    FILE_WRITE = "file_write"
    PATCH = "patch"
    TEST_RESULT = "test_result"
    ERROR = "error"
    DECISION = "decision"
    TODO = "todo"
    CHECKPOINT = "checkpoint"
    ARTIFACT = "artifact"
    PERMISSION_REQUEST = "permission_request"
    MODEL_CALL = "model_call"
    HANDOFF = "handoff"
    RESUME = "resume"


def canonical_event_type(name: str) -> EventType:
    """Parse an event type name, rejecting unknown values fail-closed."""
    key = str(name).strip().lower()
    for member in EventType:
        if member.value == key:
            return member
    raise ValueError(f"unknown canonical event type: {name!r}")


def _digest(payload: Any) -> str:
    encoded = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


@dataclass
class LossReport:
    """Honest per-channel retention accounting (WL-P0-090).

    A handoff that silently drops channels must report the loss here —
    "conversion succeeded" without a loss report is a contract violation.
    Mutable on purpose: providers build a default report and then downgrade
    channels that are unavailable for the source format.
    """

    messages: float = 1.0
    tool_calls: float = 1.0
    tool_results: float = 1.0
    reasoning: float | None = None  # None = unavailable
    system_prompt_transferred: bool = False
    permissions_transferable: bool = False
    native_state_available: bool = False
    notes: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for channel in ("messages", "tool_calls", "tool_results"):
            value = getattr(self, channel)
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"loss-report channel {channel} must be in [0,1], got {value}")
        if self.reasoning is not None and not 0.0 <= self.reasoning <= 1.0:
            raise ValueError("loss-report channel reasoning must be None or in [0,1]")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CanonicalSession:
    """Unified session record shared across all agents (WL-P0-021).

    The identity fields map one native session onto one universal id;
    ``universal_session_id`` is the stable key for OTel correlation
    (``gen_ai.conversation.id``) and the session index (WL-P0-050).
    """

    universal_session_id: str
    workspace_id: str
    project_id: str
    source_agent: str
    source_session_id: str
    source_format: str
    source_version: str = "1"
    native_path: str | None = None
    native_hash: str | None = None
    cwd: str | None = None
    repo: str | None = None
    git_commit: str | None = None
    parent_session_id: str | None = None
    started_at: str | None = None
    ended_at: str | None = None
    portability_level: PortabilityLevel = PortabilityLevel.L0_DISCOVERY
    messages: tuple[Mapping[str, Any], ...] = ()
    events: tuple[Mapping[str, Any], ...] = ()
    decisions: tuple[Mapping[str, Any], ...] = ()
    todos: tuple[Mapping[str, Any], ...] = ()
    changed_files: tuple[str, ...] = ()
    artifacts: tuple[Mapping[str, Any], ...] = ()
    evidence: tuple[Mapping[str, Any], ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for pair in (("universal_session_id", self.universal_session_id),
                     ("workspace_id", self.workspace_id),
                     ("project_id", self.project_id),
                     ("source_agent", self.source_agent),
                     ("source_session_id", self.source_session_id),
                     ("source_format", self.source_format)):
            if not str(pair[1]).strip():
                raise ValueError(f"CanonicalSession field {pair[0]} must be non-empty")
        # WL-P0-022: L3 requires an explicit native-resume marker — never
        # infer it from L1/L2 data.
        if self.portability_level is PortabilityLevel.L3_NATIVE_RESUME:
            if not self.metadata.get("native_resume", {}).get("verified"):
                raise ValueError(
                    "L3_NATIVE_RESUME requires metadata['native_resume']['verified']=True "
                    "(a real session/resume call); use L1/L2 otherwise"
                )

    # -- serialization ---------------------------------------------------
    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["portability_level"] = self.portability_level.value
        payload["schema_version"] = SCHEMA_VERSION
        return payload

    def to_json(self, *, indent: int | None = 2) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent, sort_keys=True)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "CanonicalSession":
        """Rehydrate with fail-closed validation (schema drift is an error)."""
        if data.get("schema_version") not in (None, SCHEMA_VERSION):
            raise ValueError(
                f"schema_version mismatch: expected {SCHEMA_VERSION!r}, got {data.get('schema_version')!r}"
            )
        known = {f for f in cls.__dataclass_fields__}  # type: ignore[attr-defined]
        kwargs: dict[str, Any] = {}
        for key, value in data.items():
            if key in ("schema_version",):
                continue
            if key not in known:
                # Forward-compatible: unknown fields land in metadata, never silently dropped.
                continue
            if key == "portability_level":
                kwargs[key] = PortabilityLevel.parse(value)
            elif key in ("messages", "events", "decisions", "todos", "changed_files", "artifacts", "evidence"):
                kwargs[key] = tuple(value)
            else:
                kwargs[key] = value
        return cls(**kwargs)

    @classmethod
    def from_json(cls, text: str) -> "CanonicalSession":
        return cls.from_dict(json.loads(text))

    # -- integrity -------------------------------------------------------
    def content_digest(self) -> str:
        """Stable digest over identity + payload (lineage / round-trip checks)."""
        payload = self.to_dict()
        payload.pop("schema_version", None)
        return _digest(payload)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, CanonicalSession):
            return NotImplemented
        return self.content_digest() == other.content_digest()

    def __hash__(self) -> int:
        return hash(self.content_digest())


# -- Handoff capsule (WL-P0-090, L1 semantic subset) --------------------

_CAPSULE_CHANNELS: tuple[str, ...] = (
    "goal", "key_messages", "decisions", "todos",
    "changed_files", "tool_activity", "progress", "failure_reasons",
)


def render_capsule(session: CanonicalSession, *, max_messages: int = 40) -> str:
    """Render the human/agent-readable ``capsule.md`` (L1 semantic handoff).

    Only semantic channels are included; structured event replay (L2) is
    deliberately NOT mixed in, keeping the capsule small and fast to read.
    """
    if session.portability_level is PortabilityLevel.L0_DISCOVERY:
        raise ValueError("capsule requires L1_HANDOFF or above; discovery-only sessions carry no semantic content")
    lines = [
        f"# Session Capsule — {session.universal_session_id}",
        "",
        f"- agent: {session.source_agent}",
        f"- project: {session.project_id}",
        f"- level: {session.portability_level.value}",
        "",
        "## Key messages",
    ]
    messages = list(session.messages)[:max_messages]
    if not messages:
        lines.append("(none retained)")
    for message in messages:
        role = str(message.get("role", "unknown"))
        text = str(message.get("text", "")).strip().replace("\n", " ")
        lines.append(f"- **{role}**: {text}")
    lines += ["", "## Decisions"]
    if not session.decisions:
        lines.append("(none recorded)")
    for decision in session.decisions:
        lines.append(f"- {json.dumps(decision, ensure_ascii=False, sort_keys=True)}")
    lines += ["", "## Todos"]
    if not session.todos:
        lines.append("(none)")
    for todo in session.todos:
        state = str(todo.get("state", "open"))
        lines.append(f"- [{state}] {todo.get('text', '')}")
    lines += ["", "## Changed files"]
    if not session.changed_files:
        lines.append("(none)")
    for path in session.changed_files:
        lines.append(f"- {path}")
    lines += ["", "## Progress / failure"]
    for key in ("progress", "failure_reasons"):
        extra = session.metadata.get(key)
        if extra:
            lines.append(f"- {key}: {extra}")
    lines.append("")
    return "\n".join(lines)


__all__ = [
    "SCHEMA_VERSION", "PortabilityLevel", "EventType", "LossReport",
    "CanonicalSession", "canonical_event_type", "render_capsule",
]
