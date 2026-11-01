"""Gate: the unbound-record triage must stay derived from the ledger it describes.

The debt figure is the honest part of this record - 95 PASS entries with no pinned cause - and it will move
as records get bound. A typed number would either rot or tempt someone to "fix" the audit instead of the
debt, so every count here is recomputed from the ledger and the targets audit in the test itself.
"""
from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LEDGER = ROOT / "taskpacks/current/error-ledger.json"
TARGETS = ROOT / "docs/audits/LEDGER_REGRESSION_COMMAND_TARGETS_2026-10-07.json"
TRIAGE = ROOT / "docs/audits/LEDGER_UNBOUND_TRIAGE_2026-10-07.json"


class LedgerUnboundTriageGate(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.ledger = json.loads(LEDGER.read_text(encoding="utf-8"))
        cls.targets = {r["errorId"]: r for r in
                       json.loads(TARGETS.read_text(encoding="utf-8"))["rows"]}
        cls.doc = json.loads(TRIAGE.read_text(encoding="utf-8"))

    def unbound_ids(self) -> set[str]:
        return {e["error_id"] for e in self.ledger["errors"]
                if e.get("status_after") == "PASS"
                and not (e.get("lifecycle") or {}).get("fixedCommit")}

    def test_the_triage_declares_itself_read_only_and_binding_free(self) -> None:
        self.assertTrue(self.doc["readOnly"])
        self.assertTrue(self.doc["bindsNothing"])
        self.assertIn("scripts/audit/triage_unbound_ledger_records.py",
                      self.doc["generatedByCommand"])

    def test_the_unbound_count_is_the_ledger_own(self) -> None:
        self.assertEqual(len(self.unbound_ids()),
                         self.doc["counts"]["unboundPassRecords"])
        self.assertEqual(sorted(self.unbound_ids()), sorted(r["errorId"] for r in self.doc["rows"]))

    def test_every_state_is_the_targets_audit_own_label(self) -> None:
        for row in self.doc["rows"]:
            self.assertEqual(self.targets[row["errorId"]]["state"], row["state"], row["errorId"])
        derived: dict[str, int] = {}
        for row in self.doc["rows"]:
            derived[row["state"]] = derived.get(row["state"], 0) + 1
        self.assertEqual(derived, self.doc["counts"]["byState"])

    def test_the_state_partition_covers_every_record_exactly_once(self) -> None:
        self.assertEqual(sum(self.doc["counts"]["byState"].values()),
                         self.doc["counts"]["unboundPassRecords"])
        clear = self.doc["clearCandidates"]
        self.assertEqual(len(clear), self.doc["counts"]["clearCandidates"],
                         "the listed candidates and the published count must be the same number")
        self.assertEqual(len(clear), len(set(clear)), "a candidate listed twice would inflate progress")
        self.assertTrue(set(clear) <= self.unbound_ids(),
                        "only an unbound record may be a binding candidate")

    def test_a_clear_candidate_must_have_a_guard_commit_within_the_window(self) -> None:
        window = self.doc["clearWindowDays"]
        for eid in self.doc["clearCandidates"]:
            row = next(r for r in self.doc["rows"] if r["errorId"] == eid)
            self.assertEqual("RESOLVES", row["state"], eid)
            self.assertIsNotNone(row.get("guardFirstCommit"), eid)
            self.assertLessEqual(abs(row["guardVsRecordDays"]), window, eid)

    def test_records_with_a_gone_guard_are_named_not_absorbed(self) -> None:
        gone = {r["errorId"] for r in self.doc["rows"] if r["state"] == "PATH_GONE"}
        self.assertEqual(gone, {eid for eid, row in self.targets.items()
                                if eid in self.unbound_ids() and row["state"] == "PATH_GONE"})
        self.assertGreaterEqual(len(gone), 1,
                                "a PASS claim whose recorded check no longer exists must stay visible")

    def test_a_bindable_row_needs_a_single_record_birth_commit(self) -> None:
        # The structural finding of this triage: 86 of the 94 unbound PASS records were born inside the
        # 2026-09 cutover import, which added the whole 2026-08 batch at once. An import commit is not a
        # fix commit, so no row on this branch may be bound by pointing at it (ERR-16).
        rows = {r["errorId"]: r for r in self.doc["rows"]}
        for eid in self.doc["bindableByBirthCommit"]:
            row = rows[eid]
            self.assertTrue(row["birthTouchesNamedPath"], eid)
            self.assertIs(True, row["birthContainsPromisedScript"], eid)
            self.assertLessEqual(row["birthAddedRecords"], 1, eid)
        import_born = {r["errorId"] for r in self.doc["rows"]
                       if (r.get("birthAddedRecords") or 0) > 1}
        self.assertEqual(import_born, set(self.doc["bornInAnImportCommit"]))
        self.assertEqual(set(self.doc["bindableByBirthCommit"]) & import_born, set())

    def test_the_debt_figure_is_reported_as_debt_not_progress(self) -> None:
        # 37 records have a resolvable guard but only one has a commit close enough to be a candidate
        # binding; the rest are ambiguous because their guard is far from the record date or because the
        # 2026-08 batch carries no date at all. Anything else would be a binder inventing provenance (ERR-16).
        counts = self.doc["counts"]
        self.assertEqual(counts["byState"].get("RESOLVES", 0),
                         len(self.doc["clearCandidates"])
                         + len(self.doc["heldForUncommittedRecord"])
                         + len(self.doc["resolvesGuardUndatedRecord"])
                         + len(self.doc["resolvesGuardDistant"]))
        self.assertLessEqual(len(self.doc["clearCandidates"]), 5)
        # The held partition is the ceiling made explicit: an in-window record that no commit has ever
        # carried cannot be bound, and naming it keeps that from being read as a candidate whose SHA just
        # has not been written yet (measured 2026-10-10, ERR-245 -- its guard file is older than its own
        # uncommitted fix, so proximity was a coincidence). At the time the working set is committed, all
        # six currently-held records can become real candidates at once; that is the moment to re-derive
        # the ceiling from the commit graph, not to raise the number to make the run green.
        rows = {r["errorId"]: r for r in self.doc["rows"]}
        for eid in self.doc["heldForUncommittedRecord"]:
            self.assertIsNone(rows[eid].get("birthCommit"), eid)
            self.assertIsNotNone(rows[eid].get("guardVsRecordDays"), eid)
        for eid in self.doc["clearCandidates"]:
            self.assertIsNotNone(rows[eid].get("birthCommit"),
                                 f"{eid}: a candidate must have a commit that carries the record")
        for eid in self.doc["resolvesGuardUndatedRecord"]:
            row = next(r for r in self.doc["rows"] if r["errorId"] == eid)
            self.assertIsNone(row.get("date"), f"{eid}: undated partition must mean no record date")
            self.assertIsNone(row.get("guardVsRecordDays"), eid)


if __name__ == "__main__":
    unittest.main(verbosity=2)
