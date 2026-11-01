"""Contract tests for the growth watcher collector (WL3-300 real trigger chain)."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from canonical_store import CanonicalStore
from collectors import collect_growth_watcher


class GrowthWatcherCollectorTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temporary = tempfile.TemporaryDirectory()
        self.root = Path(self._temporary.name)
        self.store = CanonicalStore(self.root / "canonical.sqlite")

    def tearDown(self) -> None:
        self.store.close()
        self._temporary.cleanup()

    def _seed_candidates(self) -> None:
        candidates = self.root / ".hermes" / "growth-candidates"
        candidates.mkdir(parents=True)
        (candidates / "candidate-a.md").write_text("# candidate\n", encoding="utf-8")
        (candidates / "candidate-b.json").write_text('{"name": "b"}', encoding="utf-8")

    def test_watcher_discovers_candidates_without_promoting(self) -> None:
        self._seed_candidates()
        result = collect_growth_watcher(self.store, "work-lab", self.root)
        self.assertTrue(result.ok)
        self.assertEqual(len(result.records), 2)
        statuses = {record["candidate_status"] for record in result.records}
        self.assertEqual(statuses, {"discovered"})  # never auto-promotes
        risks = {record["candidate_risk"] for record in result.records}
        self.assertEqual(risks, {"low"})

    def test_watcher_records_are_canonical_telemetry(self) -> None:
        self._seed_candidates()
        result = collect_growth_watcher(self.store, "work-lab", self.root)
        # Collector returns records; the worker is the single writer.
        self.assertEqual(len(result.records), 2)
        for record in result.records:
            event_id = self.store.append_telemetry(record)
            self.assertTrue(event_id)
        projection = self.store.projection()
        self.assertGreater(projection["telemetry_events"], 0)

    def test_watcher_ignores_non_candidate_files(self) -> None:
        (self.root / ".hermes" / "growth-candidates").mkdir(parents=True)
        (self.root / ".hermes" / "growth-candidates" / "notes.txt").write_text("x", encoding="utf-8")
        result = collect_growth_watcher(self.store, "work-lab", self.root)
        self.assertEqual(len(result.records), 0)

    def test_watcher_never_reads_content_bodies(self) -> None:
        self._seed_candidates()
        result = collect_growth_watcher(self.store, "work-lab", self.root)
        serialized = json.dumps(result.records, ensure_ascii=False)
        for record in result.records:
            self.assertNotIn("candidate-a.md", record.get("source_digest", ""))
        # Records contain metadata only: no body text.
        self.assertNotIn("# candidate", serialized)
        self.assertNotIn('{"name": "b"}', serialized)


if __name__ == "__main__":
    unittest.main()
