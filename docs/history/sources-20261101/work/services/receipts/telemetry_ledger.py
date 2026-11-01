"""Workflow-owned append-only telemetry ledger.

Only normalized metadata and numeric usage are accepted. Observer consumes a
projection; it never owns or mutates this ledger.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

SENSITIVE_FRAGMENTS = {
    "apikey", "authorization", "body", "cookie", "credential", "password",
    "prompt", "response", "secret",
}
# WLR-120 (2026-08-20): typed token handling. Usage token COUNTS are legal;
# credential-style token VALUES are sensitive. A bare "token" substring no
# longer rejects legal input_tokens/output_tokens/cached_tokens fields.
ALLOWED_USAGE_TOKEN_FIELDS = {
    "inputtokens", "outputtokens", "totaltokens", "cachedtokens",
    "reasoningtokens", "cachecreationtokens", "cachereadtokens",
}
SENSITIVE_TOKEN_FIELDS = {
    "accesstoken", "bearertoken", "refreshtoken", "authtoken", "apitoken",
    "tokensecret", "tokenvalue", "oauthtoken", "idtoken", "sessiontoken",
}
RESERVED_KEYS = {"schemaversion", "sequence", "producer", "dedupekey", "payloaddigest", "redactionstate"}


def _normalize_key(value: object) -> str:
    return "".join(character for character in str(value).lower() if character.isalnum())


def _keys(value: Any) -> set[str]:
    if isinstance(value, dict):
        return {_normalize_key(k) for k in value} | set().union(*(_keys(v) for v in value.values()))
    if isinstance(value, list):
        return set().union(*(_keys(v) for v in value)) if value else set()
    return set()


def _validate_keys(value: Any, *, reject_reserved: bool) -> None:
    keys = _keys(value)
    if any(fragment in key for key in keys for fragment in SENSITIVE_FRAGMENTS):
        raise ValueError("sensitive telemetry key")
    # WLR-120: token fields are typed — usage counts allowed, credential values rejected.
    for key in keys:
        if "token" in key:
            if key in ALLOWED_USAGE_TOKEN_FIELDS:
                continue
            if key in SENSITIVE_TOKEN_FIELDS or key.endswith("token"):
                raise ValueError(f"sensitive token field: {key}")
    if reject_reserved and keys & RESERVED_KEYS:
        raise ValueError("reserved telemetry key")


class TelemetryLedger:
    def __init__(self, path: Path) -> None:
        self.path = path.resolve()

    def read(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        rows = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            if row.get("schema_version") != "workflow/telemetry-ledger/v1":
                raise ValueError("unsupported telemetry schema")
            _validate_keys(row, reject_reserved=False)
            rows.append(row)
        return rows

    def append(self, event: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(event, dict) or not event.get("event_id"):
            raise ValueError("event_id is required")
        _validate_keys(event, reject_reserved=True)
        existing = self.read()
        if any(row["event_id"] == event["event_id"] for row in existing):
            raise ValueError("duplicate event_id")
        record = {
            **event,
            "schema_version": "workflow/telemetry-ledger/v1",
            "sequence": len(existing) + 1,
            "project_id": "unknown",
            "sourceRef": "unknown",
            "producer": "workflow-assistance",
            "occurredAt": event.get("occurred_at", "unknown"),
            "observedAt": event.get("observed_at", "unknown"),
            "freshness": "UNKNOWN",
            "coverage": "UNKNOWN",
            "quality": "UNKNOWN",
            "dedupe_key": event["event_id"],
            "payload_digest": "REDACTED",
            "redaction_state": "REDACTED",
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
        return record

    def trace(self, trace_id: str) -> list[dict[str, Any]]:
        """Events belonging to one trace, ordered by sequence.

        Trace-level observability (absorbed 2026-08-12): a trace_id links a
        task's events across sub-operations; parent_id links a child span to
        its parent within the same trace.
        """
        return [row for row in self.read() if row.get("trace_id") == trace_id]

    def trace_tree(self, trace_id: str) -> list[dict[str, Any]]:
        """Nested trace tree: events with parent_id are children of their parent.

        Returns a flat list ordered parent-first; children carry their resolved
        depth and path. A parent_id that points at a missing event is surfaced
        as a broken edge (never silently dropped).
        """
        rows = self.trace(trace_id)
        by_id = {row["event_id"]: row for row in rows}
        roots: list[dict[str, Any]] = []
        children: dict[str, list[dict[str, Any]]] = {}
        for row in rows:
            parent = row.get("parent_id")
            if parent and parent in by_id:
                children.setdefault(parent, []).append(row)
            else:
                roots.append(row)
        ordered: list[dict[str, Any]] = []

        def visit(row: dict[str, Any], depth: int, path: str) -> None:
            decorated = dict(row)
            decorated["trace_depth"] = depth
            decorated["trace_path"] = path
            ordered.append(decorated)
            for child in children.get(row["event_id"], []):
                visit(child, depth + 1, f"{path}.{child['event_id']}")

        for root in roots:
            visit(root, 0, root["event_id"])
        return ordered

    def projection(self) -> dict[str, Any]:
        rows = self.read()
        return {"schema_version": "workflow/telemetry-projection/v1", "event_count": len(rows), "last_sequence": len(rows), "events": [{"event_id": r["event_id"], "occurred_at": r.get("occurred_at"), "source": r.get("source"), "outcome": r.get("outcome")} for r in rows]}
