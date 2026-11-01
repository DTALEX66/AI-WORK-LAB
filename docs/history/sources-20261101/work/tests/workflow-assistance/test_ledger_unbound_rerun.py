"""Gate: the re-run receipt must be an observation, not a restatement of the ledger's own claims.

Ninety-four PASS records carry no pinned cause. Re-running their commands is the one thing that can be
established without inventing history, so the receipt that records it is held to the same standard as the
claims it tests: counts derived from the rows, every non-zero outcome named, no shell involved, and the
scope stated as the set of records whose command still resolves to a file.
"""
from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RECEIPT = ROOT / "docs/audits/LEDGER_UNBOUND_RERUN_2026-10-07.json"
TRIAGE = ROOT / "docs/audits/LEDGER_UNBOUND_TRIAGE_2026-10-07.json"


class UnboundRerunReceiptGate(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if not RECEIPT.is_file():
            raise unittest.SkipTest("the re-run receipt has not been produced on this machine")
        cls.doc = json.loads(RECEIPT.read_text(encoding="utf-8"))
        cls.rows = cls.doc["results"]

    def test_no_shell_was_used_and_the_interpreters_are_the_declared_ones(self) -> None:
        self.assertIs(False, self.doc["shellUsed"])
        self.assertTrue(self.doc["interpretersDeclared"])
        for row in self.rows:
            for part in row.get("partsRun") or []:
                self.assertIn(part["interpreter"], {"python", "node"}, row["errorId"])
                self.assertGreater(len(part["argv0"]), 0, row["errorId"])

    def test_counts_are_derived_from_the_rows(self) -> None:
        derived: dict[str, int] = {}
        for row in self.rows:
            derived[row["verdict"]] = derived.get(row["verdict"], 0) + 1
        self.assertEqual(derived, self.doc["counts"])
        failure: dict[str, int] = {}
        for row in self.rows:
            if row.get("failureClass"):
                failure[row["failureClass"]] = failure.get(row["failureClass"], 0) + 1
        self.assertEqual(failure, self.doc["byFailureClass"])
        self.assertEqual(sum(failure.values()), derived.get("FAIL", 0),
                         "every FAIL needs a cause class, and no PASS may carry one")
        for row in self.rows:
            if row["verdict"] == "PASS":
                self.assertNotIn("failureClass", row, row["errorId"])

    def test_every_verdict_carries_evidence_of_its_own_kind(self) -> None:
        for row in self.rows:
            with self.subTest(errorId=row["errorId"]):
                if row["verdict"] == "PASS":
                    self.assertEqual(0, row["exitCode"])
                elif row["verdict"] == "FAIL":
                    self.assertNotEqual(0, row["exitCode"])
                    self.assertTrue(row.get("tail"), "a FAIL without any captured output is unusable")
                elif row["verdict"] == "TIMEOUT":
                    self.assertGreater(row["timeoutSeconds"], 0)
                elif row["verdict"] == "REFUSED":
                    self.assertTrue(row.get("reason"), row["errorId"])

    def test_the_scope_is_the_resolvable_command_set(self) -> None:
        triage = json.loads(TRIAGE.read_text(encoding="utf-8"))
        resolvable = {r["errorId"] for r in triage["rows"] if r["state"] == "RESOLVES"}
        ran = {row["errorId"] for row in self.rows}
        self.assertTrue(ran, "an empty receipt proves nothing and must not pass")
        self.assertTrue(ran <= resolvable,
                        "the receipt must not claim to have run commands outside the resolvable scope")

    def test_a_fail_is_not_relabelled_as_unknown(self) -> None:
        # A non-zero exit is the finding; turning it into TIMEOUT or REFUSED after the fact is how a stale
        # PASS keeps its place in the ledger.
        for row in self.rows:
            if row.get("exitCode") not in (0, None):
                self.assertEqual("FAIL", row["verdict"], row["errorId"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
