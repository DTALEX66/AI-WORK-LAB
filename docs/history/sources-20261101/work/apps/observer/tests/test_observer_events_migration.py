"""Contract tests for observer-events.jsonl retirement migration (WL3-610)."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from migrate_observer_events import (
    legacy_authority_retired,
    migration_manifest,
    read_legacy_events,
)


class ObserverEventsMigrationTests(unittest.TestCase):
    def test_absent_file_yields_empty_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            manifest = migration_manifest(Path(temporary) / "missing.jsonl")
            self.assertFalse(manifest["legacy_present"])
            self.assertEqual(manifest["event_count"], 0)
            self.assertFalse(manifest["write_side_effects"])

    def test_legacy_events_read_and_digested_without_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "observer-events.jsonl"
            path.write_text(
                json.dumps({"eventId": "e1", "eventType": "task"}) + "\n"
                + json.dumps({"eventId": "e2", "eventType": "usage"}) + "\n",
                encoding="utf-8",
            )
            events = read_legacy_events(path)
            self.assertEqual(len(events), 2)
            manifest = migration_manifest(path)
            self.assertTrue(manifest["legacy_present"])
            self.assertEqual(manifest["event_count"], 2)
            self.assertEqual(manifest["event_ids"], ["e1", "e2"])
            self.assertEqual(len(manifest["events_digest"]), 64)
            self.assertFalse(manifest["write_side_effects"])
            # Legacy file is untouched.
            self.assertEqual(len(path.read_text(encoding="utf-8").splitlines()), 2)

    def test_output_manifest_written_to_evidence_path(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            legacy = Path(temporary) / "observer-events.jsonl"
            legacy.write_text(json.dumps({"eventId": "e1"}) + "\n", encoding="utf-8")
            output = Path(temporary) / "retirement-evidence.json"
            manifest = migration_manifest(legacy, output)
            written = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(written["event_count"], 1)
            self.assertEqual(written["canonical_authority"], "workflow-assistance-canonical-sqlite-wal")

    def test_malformed_line_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "observer-events.jsonl"
            path.write_text("not-json\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                read_legacy_events(path)

    def test_legacy_authority_is_retired(self) -> None:
        self.assertTrue(legacy_authority_retired())


if __name__ == "__main__":
    unittest.main()
