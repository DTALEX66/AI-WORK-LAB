"""Gate: a check-run that never started is not a code red.

Measured 2026-10-08 at 6c500d66: 19 check-runs, 0 success, 9 failure, 10 skipped, and every one of the
nine failures carries the annotation "The job was not started because recent account payments have
failed or your spending limit needs to be increased." A reader who only sees conclusion=failure starts
hunting a defect that does not exist; the runner was unavailable, so the head has no CI verdict at all.
"""
from __future__ import annotations

import importlib.util
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "ci" / "verify_register_ci_claims_live.py"

spec = importlib.util.spec_from_file_location("ci_claims_live", SCRIPT)
live = importlib.util.module_from_spec(spec)
spec.loader.exec_module(live)  # type: ignore[attr-defined]

BILLING = ("The job was not started because recent account payments have failed or your spending "
           "limit needs to be increased. Please check the 'Billing & plans' section in your settings")


def runs_payload(runs: list[dict]) -> str:
    return "\n".join(json.dumps({"status": r.get("status"), "conclusion": r.get("conclusion"),
                                 "name": r.get("name"), "id": r.get("id")}) for r in runs)


class NeverStartedTests(unittest.TestCase):
    def test_only_a_run_whose_annotation_says_never_started_is_counted(self) -> None:
        runs = [{"conclusion": "failure", "id": 1}, {"conclusion": "failure", "id": 2},
                {"conclusion": "success", "id": 3}]
        texts = {1: BILLING, 2: "AssertionError: expected 3 got 4"}

        def fake_gh(*args: str) -> tuple[int, str, str]:
            path = " ".join(args)
            for rid, body in texts.items():
                if f"check-runs/{rid}/annotations" in path:
                    return 0, body, ""
            return 0, "", ""

        with mock.patch.object(live, "gh", fake_gh):
            self.assertEqual(live.never_started(runs), 1)

    def test_an_api_error_while_asking_is_never_counted_as_started(self) -> None:
        # A missing annotation must not silently become "the code is red" either: unknown stays unknown.
        with mock.patch.object(live, "gh", return_value=(1, "", "HTTP 403")):
            self.assertEqual(live.never_started([{"conclusion": "failure", "id": 9}]), 0)


class CheckRunsTests(unittest.TestCase):
    def _gh(self, payload: str, calls: list):
        def fake(*args: str) -> tuple[int, str, str]:
            joined = " ".join(args)
            calls.append(joined)
            if "commits/" in joined and "annotations" not in joined:
                return 0, payload, ""
            if BILLING in joined or "annotations" in joined:
                return 0, BILLING, ""
            return 0, "", ""
        return fake

    def test_a_head_where_nothing_ran_reports_every_failure_as_not_started(self) -> None:
        payload = runs_payload([{"status": "completed", "conclusion": "failure", "name": "a", "id": 1},
                                {"status": "completed", "conclusion": "failure", "name": "b", "id": 2},
                                {"status": "completed", "conclusion": "skipped", "name": "c", "id": 3}])
        calls: list[str] = []
        with mock.patch.object(live, "gh", self._gh(payload, calls)):
            verdict = live.check_runs("a" * 40)
        self.assertEqual(verdict["runs"], 3)
        self.assertEqual(verdict["success"], 0)
        self.assertEqual(verdict["failure"], 2)
        self.assertEqual(verdict["notStarted"], 2)

    def test_a_partial_red_does_not_pay_for_annotation_calls(self) -> None:
        # One success proves runners exist, so the reds are real and the API budget stays untouched.
        payload = runs_payload([{"status": "completed", "conclusion": "success", "name": "a", "id": 1},
                                {"status": "completed", "conclusion": "failure", "name": "b", "id": 2}])
        calls: list[str] = []
        with mock.patch.object(live, "gh", self._gh(payload, calls)):
            verdict = live.check_runs("a" * 40)
        self.assertEqual(verdict["notStarted"], 0)
        self.assertFalse([c for c in calls if "annotations" in c],
                         "annotation lookups were spent on a head that clearly executed")


class MainVerdictTests(unittest.TestCase):
    """The outage branch must return before anything is published, and a real red must not reach it."""

    def rows(self) -> list[dict]:
        return [{"pins": [("deadbeef", "green")], "line": 7, "rowId": "SOME-ROW-20261008"}]

    def run_main(self, verdict: dict, out: Path) -> tuple[int, str]:
        buffer = io.StringIO()
        with mock.patch.object(live, "claim_rows", return_value=self.rows()), \
             mock.patch.object(live, "resolve", return_value="a" * 40), \
             mock.patch.object(live, "check_runs", return_value=verdict), \
             mock.patch.object(live, "gh", return_value=(0, "ok", "")), \
             mock.patch.object(live.time, "sleep", lambda _s: None), \
             redirect_stdout(buffer):
            code = live.main(["--out", str(out)])
        return code, buffer.getvalue()

    def test_an_outage_is_its_own_exit_code_not_a_failed_claim(self) -> None:
        verdict = {"runs": 19, "success": 0, "failure": 9, "notStarted": 9, "pending": 0, "byName": []}
        with tempfile.TemporaryDirectory() as tmp:
            code, out = self.run_main(verdict, Path(tmp) / "unused.json")
            self.assertFalse((Path(tmp) / "unused.json").exists(),
                             "an unmeasurable head must not be published as a measurement")
        self.assertEqual(code, 4, out)
        self.assertIn("CI_BILLING_BLOCKED", out)
        self.assertIn("neither green nor red", out)

    def test_a_real_partial_red_is_a_contradicted_claim_not_an_outage(self) -> None:
        verdict = {"runs": 19, "success": 10, "failure": 9, "notStarted": 0, "pending": 0, "byName": []}
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "measurement.json"
            code, out = self.run_main(verdict, path)
            self.assertTrue(path.exists(), "a genuine measurement is still published")
        self.assertEqual(code, 1, out)
        self.assertNotIn("CI_BILLING_BLOCKED", out)
        self.assertIn("LIVE_CI_CONTRADICTION", out)


if __name__ == "__main__":
    unittest.main(verbosity=2)
