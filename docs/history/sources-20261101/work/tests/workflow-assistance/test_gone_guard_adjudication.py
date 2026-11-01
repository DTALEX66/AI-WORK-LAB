"""Gate: the gone-guard adjudication must keep its verdicts derivable and non-vacuous.

The first version of the tool reported all fifteen records as "moved" because it matched the row-level label
`PATH_GONE` against per-operand categories that say `GONE`, and `all()` over an empty list is True. That is
the exact shape this file refuses to let back in: a verdict needs a non-empty list of missing files, a
missing file has to look like a file, and a record with no lost file operand gets its own named verdict
instead of being absorbed into one of the real three.
"""
from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ADJUDICATION = ROOT / "docs/audits/LEDGER_GONE_GUARD_ADJUDICATION_2026-10-07.json"
FILE_SUFFIXES = (".py", ".js", ".ts", ".tsx", ".mjs", ".cjs", ".json", ".md", ".yaml", ".yml",
                 ".sh", ".ps1", ".txt", ".html", ".css")


class GoneGuardAdjudicationGate(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.doc = json.loads(ADJUDICATION.read_text(encoding="utf-8"))
        cls.rows = cls.doc["rows"]

    def test_it_declares_itself_read_only(self) -> None:
        self.assertTrue(self.doc["readOnly"])

    def test_counts_equal_the_rows(self) -> None:
        derived: dict[str, int] = {}
        for row in self.rows:
            derived[row["verdict"]] = derived.get(row["verdict"], 0) + 1
        self.assertEqual(derived, self.doc["counts"]["verdicts"])
        self.assertEqual(len(self.rows), self.doc["counts"]["records"])

    def test_a_lost_guard_is_a_file_and_the_list_is_never_empty(self) -> None:
        for row in self.rows:
            if row["verdict"] in {"MOVED_ONLY_CITATION_STALE", "PARTIALLY_GONE",
                                  "DELETED_NO_SUCCEEDER"}:
                self.assertTrue(row["goneOperands"], f"{row['errorId']}: verdict with nothing lost")
                for token in row["goneOperands"]:
                    self.assertTrue(token.lower().endswith(FILE_SUFFIXES),
                                    f"{row['errorId']}: {token} is not a file operand")
                    self.assertNotIn("://", token, row["errorId"])

    def test_a_record_with_no_lost_file_operand_gets_its_own_verdict(self) -> None:
        for row in self.rows:
            if not row["goneOperands"]:
                self.assertEqual("GONE_LABEL_WITHOUT_A_GONE_FILE_OPERAND", row["verdict"],
                                 f"{row['errorId']}: an empty loss list must not read as moved")

    def test_deleted_means_no_surviving_operand_in_the_same_command(self) -> None:
        for row in self.rows:
            if row["verdict"] == "DELETED_NO_SUCCEEDER":
                self.assertEqual([], row["stillResolvingOperands"], row["errorId"])
                self.assertEqual({}, row["sameNameNowTracked"], row["errorId"])
            if row["verdict"] == "PARTIALLY_GONE":
                self.assertTrue(row["stillResolvingOperands"], row["errorId"])

    def test_the_three_real_verdicts_are_all_populated(self) -> None:
        # 6 records lost a file with no successor, 3 lost only part of a multi-file command, and six were
        # the upstream matcher calling a URL, a fraction and an identifier pair a path.
        verdicts = self.doc["counts"]["verdicts"]
        self.assertEqual(6, verdicts["DELETED_NO_SUCCEEDER"])
        self.assertEqual(3, verdicts["PARTIALLY_GONE"])
        self.assertEqual(6, verdicts["GONE_LABEL_WITHOUT_A_GONE_FILE_OPERAND"])

    def test_a_guard_cited_from_the_ignored_root_is_named_not_buried(self) -> None:
        # A regression command that points into the ignored root can never be verified by a fresh checkout,
        # so it must stay visible as its own problem rather than count as a lost test file.
        ignored = [row["errorId"] for row in self.rows
                   for token in row["goneOperands"] if token.startswith(".project-local/")]
        self.assertEqual(["ERR-104"], ignored,
                         "a check that only exists in the ignored root needs its own adjudication")


if __name__ == "__main__":
    unittest.main(verbosity=2)
