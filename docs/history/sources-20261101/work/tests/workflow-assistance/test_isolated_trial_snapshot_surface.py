"""WUI-21: the isolated-trial read models reach the v3 snapshot, and stay honest when they cannot.

The contract pair (worklab/operation-progress/v1, worklab/isolated-trial/v1) and their producer already
existed (2026-10-10); what did not exist was a carrier. The three pages therefore had nothing to read,
and the temptation was to invent fields in the UI. These tests pin the carrier instead:

  * the sections are PRESENT and validate against the closed snapshot schema;
  * every item is the contract document itself (schema_version spoken), not a paraphrase;
  * when the ledger cannot answer, the answer is UNKNOWN / NO_PRODUCER — never PASSED, and the gap list
    names what has no producer;
  * absent stays absent: a snapshot built without the producer carries no key at all, because "the
    producer was never wired" and "the producer ran and there is nothing" are different statements.
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "packages" / "client-neutral-core" / "scripts"))
sys.path.insert(0, str(ROOT / "services" / "orchestration"))

from canonical_store import CanonicalStore  # noqa: E402
from composition_root import build_v3_snapshot, load_approved_index  # noqa: E402
from snapshot_api import build_snapshot  # noqa: E402
from snapshot_validator import validate_snapshot  # noqa: E402

PROGRESS_SCHEMA = "worklab/operation-progress/v1"
TRIAL_SCHEMA = "worklab/isolated-trial/v1"


def _snap_with_task(tmp: str) -> dict:
    store = CanonicalStore(Path(tmp) / "c.sqlite")
    try:
        store.register_project("work-lab", str(ROOT), display_name="WORK-LAB")
        store.upsert_task({"task_id": "t1", "project_id": "work-lab", "status": "RUNNING"})
        return build_v3_snapshot(store, load_approved_index(store), revision=0)
    finally:
        store.close()


class SnapshotCarriesTheReadModelsTests(unittest.TestCase):
    def test_both_sections_are_present_and_validate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            snap = _snap_with_task(tmp)
            self.assertIn("operationProgress", snap)
            self.assertIn("isolatedTrials", snap)
            self.assertTrue(snap["operationProgress"], "a projected section must not be empty here")
            self.assertTrue(validate_snapshot(snap)["valid"])

    def test_each_item_is_the_contract_document_itself(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            snap = _snap_with_task(tmp)
            self.assertEqual(snap["operationProgress"][0]["schema_version"], PROGRESS_SCHEMA)
            self.assertEqual(snap["isolatedTrials"][0]["schema_version"], TRIAL_SCHEMA)
            for key in ("state", "ledger_status", "last_trusted_progress", "producer_gaps"):
                self.assertIn(key, snap["operationProgress"][0])
            for key in ("isolation", "separated_results", "producer_gaps"):
                self.assertIn(key, snap["isolatedTrials"][0])

    def test_absent_stays_absent(self) -> None:
        snap = build_snapshot(revision=1)
        self.assertNotIn("operationProgress", snap)
        self.assertNotIn("isolatedTrials", snap)

    def test_an_unreadable_ledger_answers_unknown_and_never_passed(self) -> None:
        # This box has no task ledger under .hermes/task-runtime/task-ledger, which is the honest
        # "cannot answer" case; the records must say so rather than borrow a verdict.
        with tempfile.TemporaryDirectory() as tmp:
            snap = _snap_with_task(tmp)
            for record in snap["operationProgress"]:
                self.assertIn(record["state"], {"UNKNOWN", "UNKNOWN_OR_TIMEOUT"})
                self.assertNotEqual(record["state"], "PASSED")
                self.assertEqual(record["last_trusted_progress"]["basis"], "NONE")
                self.assertTrue(record["producer_gaps"], "an unanswered record must name its gaps")
            for trial in snap["isolatedTrials"]:
                stages = trial["separated_results"]
                for name, stage in stages.items():
                    self.assertIn(stage["basis"], {"NO_PRODUCER", "LEDGER_STATE",
                                                   "EXTERNAL_EFFECT_RECONCILED"}, name)
                    if stage["basis"] == "NO_PRODUCER":
                        self.assertNotEqual(stage["status"], "PASSED",
                                            f"{name} reported PASSED with no producer")
                self.assertTrue(trial["producer_gaps"])

    def test_no_aggregate_verdict_is_carried(self) -> None:
        # The trial document must not grow a single success field: that is how three separated stages
        # get summarised into a sentence one of them never earned.
        with tempfile.TemporaryDirectory() as tmp:
            snap = _snap_with_task(tmp)
            for trial in snap["isolatedTrials"]:
                for forbidden in ("success", "passed", "verdict", "outcome", "overall"):
                    self.assertNotIn(forbidden, trial)


if __name__ == "__main__":
    unittest.main()