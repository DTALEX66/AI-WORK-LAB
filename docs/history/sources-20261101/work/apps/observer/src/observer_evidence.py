from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Iterable

from observer_runtime import ObserverInputError, validate_event


SENSITIVE_KEYS = {
    "api_key",
    "apikey",
    "authorization",
    "auth",
    "cookie",
    "password",
    "prompt",
    "response",
    "secret",
    "token",
}
WORKFLOW_SCHEMA = "workflow/evidence-envelope/v1"
EVENT_SCHEMA = "work-lab/observer-event/v1"


def _keys(value: Any) -> set[str]:
    if isinstance(value, dict):
        return {str(key).lower() for key in value} | set().union(*(_keys(item) for item in value.values()))
    if isinstance(value, list):
        return set().union(*(_keys(item) for item in value)) if value else set()
    return set()


def _digest(value: Any) -> str:
    canonical = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _is_digest(value: Any) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[a-f0-9]{64}", value) is not None


def _reject_sensitive(value: Any) -> None:
    sensitive = sorted(_keys(value) & SENSITIVE_KEYS)
    if sensitive:
        raise ObserverInputError(f"sensitive evidence keys rejected: {', '.join(sensitive)}")


def _event(*, event_id: str, task_id: str, event_type: str, source_id: str, source_digest: str, quality: str, evidence_refs: list[str]) -> dict[str, Any]:
    event = {
        "eventId": event_id,
        "schemaVersion": EVENT_SCHEMA,
        "eventType": event_type,
        "sourceModule": "workflow-assistance",
        "sourceId": source_id,
        "taskId": task_id,
        "observedAt": "source-bound",
        "contentDigest": source_digest,
        "coverage": "full",
        "quality": quality,
        "evidenceRefs": evidence_refs,
    }
    return validate_event(event)


def token_usage_events(summaries: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Normalize Token Monitor summaries into read-only Observer usage events."""
    events: list[dict[str, Any]] = []
    allowed = {"input_tokens", "output_tokens", "total_tokens", "records"}
    for summary in summaries:
        if not isinstance(summary, dict) or set(summary) != allowed:
            raise ObserverInputError("token usage summary must contain only explicit metrics")
        if any(isinstance(summary[key], bool) or not isinstance(summary[key], int) or summary[key] < 0 for key in allowed):
            raise ObserverInputError("token usage metrics must be non-negative integers")
        digest = _digest(summary)
        event = {
            "eventId": f"token-usage:{digest[:16]}",
            "schemaVersion": EVENT_SCHEMA,
            "eventType": "usage.summary",
            "sourceModule": "workflow-assistance",
            "sourceId": "token-monitor",
            "taskId": "WL-USAGE",
            "observedAt": "source-bound",
            "contentDigest": digest,
            "coverage": "full",
            "quality": "source-exact",
            "usage": {**dict(summary), "observation_state": "observed"},
        }
        events.append(validate_event(event))
    return events


def workflow_evidence_events(envelopes: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for envelope in envelopes:
        if not isinstance(envelope, dict) or envelope.get("schema_version") != WORKFLOW_SCHEMA:
            raise ObserverInputError("unsupported workflow evidence envelope")
        _reject_sensitive(envelope)
        required = {"evidence_id", "task_id", "state", "level", "source", "artifacts", "redaction"}
        if not required.issubset(envelope):
            raise ObserverInputError("workflow evidence envelope is incomplete")
        if envelope["state"] not in {"NOT_RUN", "PASS", "FAIL", "BLOCKED", "UNVERIFIED", "SKIPPED_OPTIONAL"}:
            raise ObserverInputError("unsupported workflow evidence state")
        if envelope["redaction"].get("secrets_stored") is not False:
            raise ObserverInputError("workflow evidence must declare secrets_stored=false")
        refs = [item["path"] for item in envelope["artifacts"] if isinstance(item, dict) and isinstance(item.get("path"), str)]
        events.append(
            _event(
                event_id=f"workflow-evidence:{envelope['evidence_id']}",
                task_id=envelope["task_id"],
                event_type=f"evidence.{envelope['state'].lower()}",
                source_id=envelope["evidence_id"],
                source_digest=_digest(envelope),
                quality="source-exact" if envelope["state"] == "PASS" else "partial",
                evidence_refs=refs,
            )
        )
    return events


def telemetry_events(summaries: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Normalize OTel/OpenInference-like summaries without retaining bodies."""
    events: list[dict[str, Any]] = []
    telemetry_fields = {
        "operation", "provider", "model", "input_tokens", "output_tokens", "total_tokens",
        "reasoning_tokens", "cache_read_tokens", "cache_write_tokens", "latency_ms", "outcome", "error_class",
    }
    integer_fields = {"input_tokens", "output_tokens", "total_tokens", "reasoning_tokens", "cache_read_tokens", "cache_write_tokens"}
    for summary in summaries:
        if not isinstance(summary, dict):
            raise ObserverInputError("telemetry summary must be an object")
        _reject_sensitive(summary)
        if not {"operation", "provider", "task_id"}.issubset(summary):
            raise ObserverInputError("telemetry summary is incomplete")
        unknown = set(summary) - telemetry_fields - {"task_id", "source_digest"}
        if unknown:
            raise ObserverInputError("telemetry summary contains non-allowlisted fields")
        safe = {key: summary[key] for key in telemetry_fields if key in summary}
        for key in integer_fields:
            if key in safe and (isinstance(safe[key], bool) or not isinstance(safe[key], int) or safe[key] < 0):
                raise ObserverInputError("telemetry token fields must be non-negative integers")
        if "latency_ms" in safe and (isinstance(safe["latency_ms"], bool) or not isinstance(safe["latency_ms"], (int, float)) or safe["latency_ms"] < 0):
            raise ObserverInputError("telemetry latency must be non-negative")
        source_digest = summary.get("source_digest") or _digest(safe)
        if not _is_digest(source_digest):
            raise ObserverInputError("telemetry source_digest must be a lowercase SHA-256")
        complete_fields = {"operation", "provider", "model", "latency_ms", "outcome"}
        has_usage = bool(integer_fields & safe.keys())
        event = {
            "eventId": f"telemetry:{source_digest[:16]}",
            "schemaVersion": EVENT_SCHEMA,
            "eventType": "telemetry.summary",
            "sourceModule": "workflow-assistance",
            "sourceId": "otel-openinference-fixture",
            "taskId": summary["task_id"],
            "observedAt": "source-bound",
            "contentDigest": _digest(safe),
            "coverage": "full" if complete_fields.issubset(safe) and has_usage else "partial",
            "quality": "source-exact",
            "telemetry": safe,
        }
        events.append(validate_event(event))
    return events