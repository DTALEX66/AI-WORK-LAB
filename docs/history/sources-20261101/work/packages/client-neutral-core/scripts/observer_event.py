#!/usr/bin/env python
"""Append-only, project-local observer events and deterministic projections."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "workflow/observer-event/v1"
REQUIRED = {"event_id", "run_id", "task_id", "event_type", "occurred_at", "source", "payload"}
SENSITIVE_KEYS = {"token", "password", "secret", "cookie", "authorization", "auth", "prompt", "response"}


def _keys(value: Any) -> set[str]:
    if isinstance(value, dict):
        return {str(k).lower() for k in value} | {item for child in value.values() for item in _keys(child)}
    if isinstance(value, list):
        return {item for child in value for item in _keys(child)}
    return set()


class ObserverEventStore:
    def __init__(self, path: Path) -> None:
        self.path = path.resolve()

    def read_events(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        events: list[dict[str, Any]] = []
        seen_ids: set[str] = set()
        expected_sequence = 1
        for line_number, raw in enumerate(self.path.read_text(encoding="utf-8").splitlines(), 1):
            if not raw.strip():
                continue
            try:
                event = json.loads(raw)
            except json.JSONDecodeError as exc:
                raise ValueError(f"invalid observer event at line {line_number}") from exc
            if event.get("schema_version") != SCHEMA_VERSION:
                raise ValueError(f"unsupported observer schema at line {line_number}")
            if event.get("event_id") in seen_ids:
                raise ValueError(f"duplicate observer event id at line {line_number}")
            if event.get("sequence") != expected_sequence:
                raise ValueError(f"non-monotonic observer sequence at line {line_number}")
            if _keys(event) & SENSITIVE_KEYS:
                raise ValueError(f"sensitive observer event key at line {line_number}")
            seen_ids.add(event["event_id"])
            events.append(event)
            expected_sequence += 1
        return events

    def append(self, event: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(event, dict) or not REQUIRED.issubset(event):
            raise ValueError("observer event missing required fields")
        if not isinstance(event["payload"], dict):
            raise ValueError("observer event payload must be an object")
        if _keys(event) & SENSITIVE_KEYS:
            raise ValueError("sensitive observer event key")
        existing = self.read_events()
        if any(item["event_id"] == event["event_id"] for item in existing):
            raise ValueError("duplicate observer event id")
        record = {
            "schema_version": SCHEMA_VERSION,
            "sequence": len(existing) + 1,
            **event,
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
        return record

    def rebuild_projection(self) -> dict[str, dict[str, Any]]:
        projection: dict[str, dict[str, Any]] = {}
        for event in self.read_events():
            key = event.get("projection_key")
            if key:
                projection[str(key)] = dict(event["payload"])
        return projection

    def rebuild_task_projection(self) -> dict[str, dict[str, Any]]:
        """Return the latest task status/heartbeat/budget/block/evidence view."""
        return {
            key: value
            for key, value in self.rebuild_projection().items()
            if key.startswith("task:")
        }
