"""Contract tests for memory governance (WL3-310)."""

from __future__ import annotations

import unittest
from pathlib import Path

from growth_watcher import validate_memory
from memory_governance import (
    compaction_manifest,
    detect_conflicts,
    is_expired,
    latest_instruction_wins,
    project_isolation,
    supersedes_active,
)


def _record(memory_id: str, **overrides) -> dict:
    record = {
        "schema_version": "workflow/runtime-context-record/v1",
        "memory_id": memory_id,
        "layer": "project",
        "kind": "fact",
        "status": "approved",
        "project_id": "work-lab",
        "scope": "project",
        "valid_from": "2026-01-01T00:00:00Z",
        "valid_to": None,
        "ttl_days": None,
        "supersedes": None,
        "conflicts_with": [],
        "last_used_at": None,
        "pinned_context": False,
        "source_digest": "a" * 64,
        "content_digest": "b" * 64,
        "confidence": "medium",
        "promotion": "manual-approval",
        "redaction": {"prompt_response_bodies": "excluded", "credentials": "excluded"},
    }
    record.update(overrides)
    return record


class MemoryGovernanceTests(unittest.TestCase):
    def test_schema_accepts_extended_fields(self) -> None:
        record = _record("m1", ttl_days=30)
        self.assertEqual(validate_memory(record)["memory_id"], "m1")

    def test_ttl_expiry(self) -> None:
        record = _record("m1", ttl_days=30, valid_from="2020-01-01T00:00:00Z")
        self.assertTrue(is_expired(record, at="2026-01-01T00:00:00Z"))
        fresh = _record("m2", ttl_days=30, valid_from="2026-01-01T00:00:00Z")
        self.assertFalse(is_expired(fresh, at="2026-01-10T00:00:00Z"))

    def test_pinned_context_never_expires(self) -> None:
        record = _record("m3", pinned_context=True, ttl_days=1, valid_from="2020-01-01T00:00:00Z")
        self.assertFalse(is_expired(record, at="2026-01-01T00:00:00Z"))

    def test_supersedes_retires_old_memory(self) -> None:
        old = _record("old-rule")
        new = _record("new-rule", supersedes="old-rule")
        self.assertTrue(supersedes_active("old-rule", [old, new]))

    def test_project_isolation(self) -> None:
        records = [
            _record("a", project_id="project-a", scope="project"),
            _record("b", project_id="project-b", scope="project"),
            _record("c", project_id="project-c", scope="global"),
        ]
        visible = project_isolation(records, "project-a")
        ids = {record["memory_id"] for record in visible}
        self.assertEqual(ids, {"a", "c"})  # project-b memory must not leak

    def test_compaction_keeps_pinned_and_drops_expired_with_trace(self) -> None:
        records = [
            _record("pinned-safety", pinned_context=True, ttl_days=1, valid_from="2020-01-01T00:00:00Z"),
            _record("expired", ttl_days=30, valid_from="2020-01-01T00:00:00Z"),
            _record("fresh", ttl_days=365, valid_from="2026-01-01T00:00:00Z"),
        ]
        manifest = compaction_manifest(records, at="2026-06-01T00:00:00Z")
        self.assertIn("pinned-safety", manifest["retained"])
        self.assertEqual(manifest["dropped"][0]["reason"], "expired-ttl")
        self.assertTrue(manifest["traceable"])

    def test_conflict_detection(self) -> None:
        records = [_record("x", conflicts_with=["y"]), _record("y")]
        groups = detect_conflicts(records)
        self.assertTrue(any("x" in group and "y" in group for group in groups))

    def test_latest_instruction_wins_prefers_pinned_and_newer(self) -> None:
        records = [
            _record("old", confidence="high", valid_from="2020-01-01T00:00:00Z"),
            _record("new", confidence="medium", valid_from="2026-01-01T00:00:00Z"),
        ]
        result = latest_instruction_wins(records)
        self.assertEqual(result["winner"], "new")


if __name__ == "__main__":
    unittest.main()