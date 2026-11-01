"""Execution Evidence standard contract (WLGM-060).

All agent adapters emit unified, auditable facts. The contract:

- never accepts prompt/response bodies, full command lines, environment values
  or credentials;
- projects paths by default (project-relative or hashed);
- defines start / running / waiting / end / failed / heartbeat / invisible
  event types;
- handles out-of-order, duplicates, missing terminal states and clock skew;
- prefers the source event ID; derived events use a stable dedupe key.

Event objects are validated by ``ExecutionEvidence``; invalid records raise
``EvidenceValidationError`` and must never pollute current state.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

EVIDENCE_SCHEMA_VERSION = "workflow/execution-evidence/v1"

EVENT_TYPES = {
    "execution_started",
    "execution_running",
    "execution_waiting_user",
    "execution_waiting_approval",
    "execution_blocked",
    "execution_completed",
    "execution_failed",
    "execution_cancelled",
    "execution_heartbeat",
    "execution_invisible",
}

EVIDENCE_LEVELS = {"A", "B", "C", "D", "E"}

QUALITY_VALUES = {"EXACT", "SOURCE_REPORTED", "CORRELATED", "DERIVED", "INFERRED", "PARTIAL", "UNKNOWN"}

PRIVACY_CLASSIFICATIONS = {"public", "project_internal", "sensitive"}

FORBIDDEN_KEY_PATTERNS = (
    re.compile(r"(?i)api[_-]?key"),
    re.compile(r"(?i)(authorization|bearer|token|secret|password|credential|cookie)"),
    re.compile(r"(?i)(\.env|env[_-]?file)"),
    re.compile(r"prompt|response|body"),
)

CREDENTIAL_VALUE_PATTERNS = (
    re.compile(r"(?i)\bsk-[a-z0-9]{8,}"),
    re.compile(r"(?i)\bbearer\s+[a-z0-9._-]{16,}"),
    re.compile(r"(?i)\bghp_[a-z0-9]{20,}"),
)


class EvidenceValidationError(ValueError):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def stable_dedupe_key(source_event_id: str, event_type: str, occurred_at: str) -> str:
    """Stable key for derived events: same source -> same key."""
    raw = f"{source_event_id}|{event_type}|{occurred_at}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


@dataclass
class ExecutionEvidence:
    event_id: str
    event_type: str
    occurred_at: str
    observed_at: str = field(default_factory=_now)
    source_event_id: str | None = None
    collector_id: str = ""
    adapter_id: str = ""
    agent_instance_id: str | None = None
    session_id: str | None = None
    execution_id: str | None = None
    task_id: str | None = None
    anchor_project_id: str | None = None
    repository_id: str | None = None
    worktree_id: str | None = None
    working_area: str | None = None
    reported_state: str | None = None
    expires_at: str | None = None
    source_ref: str = ""
    evidence_level: str = "C"
    quality: str = "SOURCE_REPORTED"
    sequence: int = 0
    dedupe_key: str | None = None
    privacy_classification: str = "project_internal"
    payload: dict[str, Any] = field(default_factory=dict)

    def validate(self) -> None:
        if self.event_type not in EVENT_TYPES:
            raise EvidenceValidationError(f"unknown event type: {self.event_type}")
        if self.evidence_level not in EVIDENCE_LEVELS:
            raise EvidenceValidationError(f"invalid evidence level: {self.evidence_level}")
        if self.quality not in QUALITY_VALUES:
            raise EvidenceValidationError(f"invalid quality: {self.quality}")
        if self.privacy_classification not in PRIVACY_CLASSIFICATIONS:
            raise EvidenceValidationError(f"invalid privacy classification: {self.privacy_classification}")
        if not self.event_id:
            raise EvidenceValidationError("event_id is required")
        _validate_no_forbidden_content(self.payload)

    def as_record(self) -> dict[str, Any]:
        self.validate()
        return {
            "schema_version": EVIDENCE_SCHEMA_VERSION,
            "eventId": self.event_id,
            "sourceEventId": self.source_event_id,
            "collectorId": self.collector_id,
            "adapterId": self.adapter_id,
            "agentInstanceId": self.agent_instance_id,
            "sessionId": self.session_id,
            "executionId": self.execution_id,
            "taskId": self.task_id,
            "anchorProjectId": self.anchor_project_id,
            "repositoryId": self.repository_id,
            "worktreeId": self.worktree_id,
            "workingArea": self.working_area,
            "eventType": self.event_type,
            "reportedState": self.reported_state,
            "occurredAt": self.occurred_at,
            "observedAt": self.observed_at,
            "expiresAt": self.expires_at,
            "sourceRef": self.source_ref,
            "evidenceLevel": self.evidence_level,
            "quality": self.quality,
            "sequence": self.sequence,
            "dedupeKey": self.dedupe_key or stable_dedupe_key(self.source_event_id or self.event_id, self.event_type, self.occurred_at),
            "privacyClassification": self.privacy_classification,
            "payload": _sanitize_payload(self.payload),
        }


def _validate_no_forbidden_content(payload: dict[str, Any]) -> None:
    if not isinstance(payload, dict):
        raise EvidenceValidationError("payload must be an object")
    for key, value in payload.items():
        for pattern in FORBIDDEN_KEY_PATTERNS:
            if pattern.search(str(key)):
                raise EvidenceValidationError(f"forbidden sensitive field name: {pattern.pattern}")
        if isinstance(value, str):
            for pattern in CREDENTIAL_VALUE_PATTERNS:
                if pattern.search(value):
                    raise EvidenceValidationError(f"credential-looking value: {pattern.pattern}")


def _sanitize_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Project paths by default: drop any value that looks like an absolute path."""
    clean: dict[str, Any] = {}
    for key, value in payload.items():
        if isinstance(value, str) and ("\\" in value or "/" in value):
            clean[key] = "<path-projected>"
        else:
            clean[key] = value
    return clean
