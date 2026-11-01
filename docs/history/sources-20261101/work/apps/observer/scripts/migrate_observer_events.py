"""One-shot read-only migration from legacy observer-events.jsonl (WL3-610).

The canonical SQLite WAL (workflow-assistance) is the single authority for
business facts. This migrator reads the legacy observer event file read-only
and writes an evidence manifest of what was found (count, event ids, digest).
It never writes to the canonical store, never mutates the legacy file, and is
safe to delete after use. The legacy file's authoritative role is retired.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


def read_legacy_events(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    events: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"legacy observer event malformed at line {line_number}") from exc
        if not isinstance(event, dict):
            raise ValueError(f"legacy observer event not an object at line {line_number}")
        events.append(event)
    return events


def migration_manifest(legacy_path: Path, output_path: Path | None = None) -> dict[str, Any]:
    """Read-only migration evidence; never mutates the legacy file or canonical store."""
    events = read_legacy_events(legacy_path)
    event_ids = [str(event.get("eventId", "")) for event in events if event.get("eventId")]
    digest = hashlib.sha256()
    for event in events:
        digest.update(json.dumps(event, ensure_ascii=False, sort_keys=True).encode("utf-8"))
        digest.update(b"\0")
    manifest = {
        "schema_version": "workflow/observer-events-retirement/v1",
        "legacy_path": str(legacy_path),
        "legacy_present": legacy_path.is_file(),
        "event_count": len(events),
        "event_ids": event_ids,
        "events_digest": digest.hexdigest(),
        "canonical_authority": "workflow-assistance-canonical-sqlite-wal",
        "legacy_role": "RETIRED_FROM_AUTHORITY",
        "write_side_effects": False,
        "migrated_at": None,
    }
    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest


def legacy_authority_retired() -> bool:
    """The legacy file no longer holds authority regardless of its existence."""
    return True


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Produce read-only retirement evidence for observer-events.jsonl")
    parser.add_argument("--legacy", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    manifest = migration_manifest(args.legacy.resolve(), args.output.resolve() if args.output else None)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
