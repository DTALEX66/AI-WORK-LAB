"""The register's tables must be rectangular, and the checker must not be fooled by escaped pipes.

Nine rows in this register carried a piped shell command inside a backtick span and were therefore read
by markdown as extra columns -- their Status landed under the Evidence heading. Another section declared
a three-column header while ten of its rows carried a Priority column. Both were invisible to every gate
that existed, because the register is a text surface and nothing parsed it as a table.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts" / "ci"))

import verify_register_table_shape as shape  # noqa: E402

REGISTER = REPO / "taskpacks/current/OPEN-TASK-REGISTER.md"
# The pre-cutover ledger, kept tracked byte-for-byte (404,985 B, 8 tables, 190 rows) by the 2026-10-09
# UI-priority cutover record. It is the positive control for the multi-table floors below.
ARCHIVE = REPO / ("taskpacks/history/UI-PRIORITY-CUTOVER-20261009/original-tree/"
                  "taskpacks/current/OPEN-TASK-REGISTER.md")


class RealRegister(unittest.TestCase):
    def test_the_live_register_is_rectangular(self) -> None:
        self.assertEqual(0, shape.main([]), "the register has rows that do not match their table header")

    def test_the_register_has_several_tables_and_many_rows(self) -> None:
        """The floors live on the ledger that has the shape; the live one is judged for what it declares.

        Measured across history rather than assumed: at d22d21eb^ OPEN-TASK-REGISTER.md held 8 tables /
        190 rows / 404,985 B, and at d22d21eb it holds 1 table / 25 rows / 123,260 B, because the 2026-10-09
        UI-priority cutover replaced the multi-ledger register with the single WUI table. The absolute floors
        were written against the old document, so they convicted the new one -- and deleting them would leave
        the parser with nothing that proves it still sees a multi-table ledger. The pre-cutover bytes survive
        TRACKED, byte-for-byte, at the archive path below, so the non-vacuity control runs on real repository
        content instead of a fixture, while the live file keeps its own measured floor: a row disappearing or
        a column drifting still goes red.
        """
        bad, tables, rows = shape.scan(ARCHIVE.read_text(encoding="utf-8"))
        self.assertGreaterEqual(len(tables), 3, tables)
        self.assertGreater(rows, 100, f"only {rows} rows judged; the parser lost a table")
        self.assertEqual([], bad)

        live_bad, live_tables, live_rows = shape.scan(REGISTER.read_text(encoding="utf-8"))
        self.assertEqual(1, len(live_tables),
                         f"the live register is the single WUI table; the parser saw {live_tables}")
        # 25 was the count on 2026-10-10; the 2026-10-11/12 cloud-audit batch appended WUI-21..WUI-24 and the
        # 2026-10-23 independent-closed-loop programme (source WL-REC-0107) appended CL-01..CL-12, taking the
        # ledger to 37. CL-13 and CL-14 (2026-10-25: "make the checks able to fail", then gate wiring and the
        # live loop closure) took it to 39; CL-15 (the WORK brand build) and CL-16 (the motion layer, registered
        # with its evidence and no code) make 41, and CL-17 (the seven P2 closures, 2026-10-26) makes 42 -- the
        # count the verifier itself prints: `REGISTER_TABLE_SHAPE_PASS ... tables=1 rows=42 wrong_width=0`.
        # The number is a tripwire for a *lost* row or a parser that stopped splitting them, not a claim
        # that the register never grows: adding a row must move this figure in the same commit that adds it,
        # otherwise a deleted row can hide behind a stale floor.
        #
        # Measured, not copied: exact-SHA CI run 40335931495 went red here with `41 != 42` because CL-17 was
        # registered in 20292c45 without moving this floor. The delta is one row and its origin is the diff --
        # `shape.scan` over `git show` bytes reads 41 at 99013978 and 42 at 20292c45.
        self.assertEqual(42, live_rows,
                         f"the live register carried 41 rows through CL-16 and CL-17 (2026-10-26) added the "
                         f"42nd; {live_rows} were judged, so a row was lost or the parser stopped splitting them")
        self.assertEqual([], live_bad)


class ScanJudgement(unittest.TestCase):
    def test_an_extra_column_is_caught(self) -> None:
        text = ("# T\n\n| ID | Status | Evidence |\n|---|---|---|\n"
                "| A | GREEN | ok |\n| B | P1 | DONE | note |\n")
        bad, tables, rows = shape.scan(text)
        self.assertEqual(1, len(bad), bad)
        self.assertEqual("B", bad[0][2])
        self.assertEqual(2, rows)

    def test_a_missing_column_is_caught_too(self) -> None:
        text = "| ID | Priority | Status |\n|---|---|---|\n| A | P0 | OK |\n| B | OK |\n"
        bad, _tables, _rows = shape.scan(text)
        self.assertEqual(1, len(bad), bad)

    def test_an_escaped_pipe_is_content_not_a_column(self) -> None:
        text = ("| ID | Priority | Status |\n|---|---|---|\n"
                "| A | P0 | grep -E 'a\\|b' = 0 |\n")
        bad, _tables, rows = shape.scan(text)
        self.assertEqual([], bad, f"the row is three cells; the backslash-pipe is inside the evidence: {bad}")
        self.assertEqual(1, rows)

    def test_a_separate_table_gets_its_own_width(self) -> None:
        text = ("| ID | Status |\n|---|---|\n| A | ok |\n\nprose\n\n"
                "| ID | Priority | Status |\n|---|---|---|\n| B | P1 | ok |\n")
        bad, tables, rows = shape.scan(text)
        self.assertEqual(2, len(tables), tables)
        self.assertEqual([], bad)
        self.assertEqual(2, rows)

    def test_a_file_with_no_table_fails_instead_of_passing(self) -> None:
        bad, tables, rows = shape.scan("# Notes\n\n- nothing tabular here\n")
        self.assertEqual([], tables)
        self.assertEqual(0, rows)
        self.assertEqual([], bad)


class FailClosedMain(unittest.TestCase):
    def test_a_planted_register_with_a_wide_row_is_red(self) -> None:
        import subprocess
        import tempfile
        root = REPO / ".project-local" / "runs"
        root.mkdir(parents=True, exist_ok=True)
        planted = Path(tempfile.mkdtemp(prefix="register-shape-", dir=str(root))) / "planted.md"
        planted.write_text("| ID | Status |\n|---|---|\n| A | ok |\n| B | P0 | extra |\n",
                           encoding="utf-8", newline="\n")
        try:
            proc = subprocess.run([sys.executable,
                                   str(REPO / "scripts" / "ci" / "verify_register_table_shape.py"),
                                   "--register", str(planted)],
                                  cwd=REPO, capture_output=True)
            out = (proc.stdout + proc.stderr).decode("utf-8", "replace")
            self.assertEqual(1, proc.returncode, out)
            self.assertIn("wrong_width=1", out)
        finally:
            import shutil
            shutil.rmtree(planted.parent, ignore_errors=True)

    def test_a_header_with_no_rows_is_called_out(self) -> None:
        import subprocess
        planted = REPO / ".project-local" / "runs" / "register-no-rows.md"
        planted.parent.mkdir(parents=True, exist_ok=True)
        planted.write_text("| ID | Status |\n|---|---|\n", encoding="utf-8", newline="\n")
        try:
            proc = subprocess.run([sys.executable,
                                   str(REPO / "scripts" / "ci" / "verify_register_table_shape.py"),
                                   "--register", str(planted)],
                                  cwd=REPO, capture_output=True)
            out = (proc.stdout + proc.stderr).decode("utf-8", "replace")
            self.assertEqual(1, proc.returncode, out)
            self.assertIn("rows=0", out)
        finally:
            planted.unlink()


if __name__ == "__main__":
    unittest.main()
