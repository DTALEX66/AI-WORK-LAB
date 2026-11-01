# SPDX-License-Identifier: MIT
"""The bound run must name the cases it did not run.

`skipped=4` on its own is a count of one scanner's scope: it reads the same whether four
host probes found no host or four real checks stopped being collected. These tests pin the
identity + stated reason + honest truncation, and pin the loud failure for the one case
where the runner can count a skip but cannot say which one.
"""
from __future__ import annotations

import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(REPO / "src"))

import run_bound_test_suite as runner  # noqa: E402

REASON = "fixture: this case is declared not-runnable on purpose"


class _Fixture(unittest.TestCase):
    def test_runs(self) -> None:
        self.assertTrue(True)

    @unittest.skip(REASON)
    def test_skipped_case(self) -> None:
        raise AssertionError("never reaches this line")


def _result() -> unittest.TestResult:
    return unittest.TextTestRunner(verbosity=0, stream=io.StringIO()).run(
        unittest.TestSuite([_Fixture("test_runs"), _Fixture("test_skipped_case")]))


class SkipIdentityTests(unittest.TestCase):
    def test_every_skip_comes_back_as_case_plus_its_own_reason(self) -> None:
        details, truncated = runner.skip_details(_result())
        self.assertEqual(1, len(details), details)
        self.assertFalse(truncated)
        self.assertIn("test_skipped_case", details[0]["case"])
        # the reason is the decorator's own text, not a cause this runner invented
        self.assertEqual(REASON, details[0]["reason"])

    def test_no_skip_produces_no_identity_and_no_claim(self) -> None:
        result = unittest.TextTestRunner(verbosity=0, stream=io.StringIO()).run(
            unittest.TestSuite([_Fixture("test_runs")]))
        details, truncated = runner.skip_details(result)
        self.assertEqual([], details)
        self.assertFalse(truncated)

    def test_a_cut_list_admits_it_was_cut(self) -> None:
        # A bounded view must never read as the whole truth: the count lives in the
        # record's own `skipped` field, so the caller can still see what was hidden.
        details, truncated = runner.skip_details(_result(), limit=0)
        self.assertEqual([], details)
        self.assertTrue(truncated)


class BoundRunRecordsIdentities(unittest.TestCase):
    def test_the_written_record_and_stdout_both_name_the_skip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            stdout = io.StringIO()
            with patch.object(runner, "discover", return_value=[
                    _Fixture("test_runs"), _Fixture("test_skipped_case")]), \
                 patch.object(runner, "RECORD_DIR", root), \
                 patch.object(runner, "RECORD", root / "last-run.json"), \
                 patch.object(runner, "HISTORY", root / "history.jsonl"), \
                 redirect_stdout(stdout):
                code = runner.main([])

            text = stdout.getvalue()
            self.assertEqual(0, code, text)
            self.assertIn("skipped=1", text)
            self.assertIn(f"SKIP {_Fixture('test_skipped_case').id()} :: {REASON}", text)
            self.assertNotIn("BOUND_SKIP_IDENTITY=DEFECT", text)

            record = json.loads((root / "last-run.json").read_text(encoding="utf-8"))
            self.assertEqual(1, record["skipped"])
            self.assertEqual([{"case": str(_Fixture("test_skipped_case")),
                               "case_id": _Fixture("test_skipped_case").id(),
                               "reason": REASON}],
                             record["skipped_detail"])
            self.assertFalse(record["skipped_detail_truncated"])
            # readers of the older record keep working: the fields they know are untouched
            for key in ("schemaVersion", "run_id", "tests_run", "failures", "errors",
                        "skipped", "result", "exit_code", "subject", "test_manifest_sha256"):
                self.assertIn(key, record, key)

    def test_a_run_that_counts_skips_but_names_none_is_reported_broken(self) -> None:
        # The null case of this instrument: a result object that yields a skip count with
        # no readable identity must not be able to print a clean PASS line.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            stdout = io.StringIO()
            with patch.object(runner, "discover", return_value=[
                    _Fixture("test_runs"), _Fixture("test_skipped_case")]), \
                 patch.object(runner, "skip_details", return_value=([], False)), \
                 patch.object(runner, "RECORD_DIR", root), \
                 patch.object(runner, "RECORD", root / "last-run.json"), \
                 patch.object(runner, "HISTORY", root / "history.jsonl"), \
                 redirect_stdout(stdout):
                code = runner.main([])

            text = stdout.getvalue()
            self.assertEqual(3, code, text)
            self.assertIn("BOUND_SKIP_IDENTITY=DEFECT", text)
            self.assertIn("skipped=1", text)


if __name__ == "__main__":
    unittest.main()
