# SPDX-License-Identifier: MIT
"""The critical-set record must be judgeable by someone who does not own the run history.

Measured 2026-10-09 in two trees of `d6ba107f`: `deepseek_test_gate_report.py --check` compared
every field of the record against a re-derivation from
`.project-local/task-artifacts/test-run/history.jsonl`. That file is gitignored, so a clean checkout
found 0 matching runs, the re-derivation came back empty, and the committed PASS read as
`TEST_GATE=DRIFT results changed since generation`. The runs themselves cannot be reproduced from
the repository -- executing them is the authority chain's job -- so the check now judges what a
repository can answer: that the declared 16-module scope exists as versioned test files, and that
the verdict follows from the numbers the record itself publishes.

Two things this found on the way in. `executed_scope.tests_per_order` was the typed literal 220
while the runs the record reports (2026-10-06) recorded 225 in every order, so the scope figure had
never been derived from anything; and the check printed `DRIFT`, a word that made an unverifiable
machine read like a disagreement.
"""
from __future__ import annotations

import copy
import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RECORD_REL = "reports/current/DEEPSEEK-FINAL-TEST-GATE.json"
sys.path.insert(0, str(ROOT / "scripts"))

import deepseek_test_gate_report as gate  # noqa: E402


def record() -> dict:
    return json.loads((ROOT / RECORD_REL).read_text(encoding="utf-8"))


class ScopeIsVersionedTests(unittest.TestCase):
    def test_every_declared_module_exists_as_versioned_test_content(self) -> None:
        tracked = gate.tracked_paths()
        declared = record()["executed_scope"]["modules"]
        self.assertEqual(len(declared), 16, "the declared critical set changed size")
        for name in declared:
            self.assertIn(f"{gate.TESTS_DIR}/{name}.py", tracked,
                          f"{name} is declared as executed scope but no checkout contains it")

    def test_the_history_runner_is_versioned_and_named_by_the_record(self) -> None:
        self.assertIn(gate.BOUND_SUITE_RUNNER, gate.tracked_paths())
        self.assertIn(Path(gate.BOUND_SUITE_RUNNER).name, record()["source"])

    def test_the_scope_figure_is_the_number_the_runs_recorded(self) -> None:
        document = record()
        scope = document["executed_scope"]
        tests = [row["tests"] for key, row in document["requirements"].items()
                 if key in gate.ORDER_REQUIREMENT_KEYS and row]
        self.assertTrue(tests)
        self.assertEqual(set(tests), {scope["tests_per_order"]},
                         "executed_scope.tests_per_order is not the recorded per-order count")
        self.assertEqual(scope["tests_per_order_state"], "IDENTICAL_ACROSS_ORDERS")


class PlantedRecordTests(unittest.TestCase):
    """Each plant requires one named finding, so no guard below can be decoration."""

    def setUp(self) -> None:
        self.base = record()

    def codes(self, document: dict) -> str:
        return "\n".join(gate.record_findings(document))

    def test_the_shipped_record_supports_its_own_verdict(self) -> None:
        self.assertEqual(gate.record_findings(self.base), [])

    def test_a_module_that_no_checkout_contains_is_convicted(self) -> None:
        document = copy.deepcopy(self.base)
        document["executed_scope"]["modules"].append("test_the_module_that_was_renamed")
        self.assertIn("TESTGATE-SCOPE-MODULE-UNTRACKED", self.codes(document))

    def test_an_empty_scope_covers_nothing(self) -> None:
        document = copy.deepcopy(self.base)
        document["executed_scope"]["modules"] = []
        self.assertIn("TESTGATE-SCOPE-EMPTY", self.codes(document))

    def test_a_module_count_that_does_not_match_the_list_is_convicted(self) -> None:
        document = copy.deepcopy(self.base)
        document["executed_scope"]["module_count"] = 99
        self.assertIn("TESTGATE-SCOPE-COUNT", self.codes(document))

    def test_a_typed_scope_figure_is_convicted(self) -> None:
        document = copy.deepcopy(self.base)
        document["executed_scope"]["tests_per_order"] = 220
        self.assertIn("TESTGATE-TESTS-PER-ORDER", self.codes(document))

    def test_a_record_that_hides_a_failure_is_convicted(self) -> None:
        document = copy.deepcopy(self.base)
        document["requirements"]["reverse"]["failures"] = 3
        codes = self.codes(document)
        self.assertIn("TESTGATE-FAILURE-CLAIM", codes)
        self.assertIn("TESTGATE-VERDICT-NOT-DERIVED", codes)

    def test_a_missing_order_is_convicted(self) -> None:
        document = copy.deepcopy(self.base)
        document["requirements"]["reverse"] = None
        codes = self.codes(document)
        self.assertIn("TESTGATE-ORDERS-MISMATCH", codes)
        self.assertIn("TESTGATE-VERDICT-NOT-DERIVED", codes)

    def test_a_record_cannot_promote_itself_to_pass_without_repetition(self) -> None:
        document = copy.deepcopy(self.base)
        document["requirements"]["critical_module_repetition"] = None
        self.assertIn("TESTGATE-VERDICT-NOT-DERIVED", self.codes(document))

    def test_a_silently_dropped_deferral_is_convicted(self) -> None:
        document = copy.deepcopy(self.base)
        document["deferred"]["state"] = "COMPLETE"
        self.assertIn("TESTGATE-DEFERRAL-LOST", self.codes(document))
        document = copy.deepcopy(self.base)
        document["deferred"]["not_a_claim"] = ""
        self.assertIn("TESTGATE-DEFERRAL-INCOMPLETE", self.codes(document))

    def test_a_record_that_no_longer_names_where_its_numbers_came_from_is_convicted(self) -> None:
        document = copy.deepcopy(self.base)
        document["source"] = "typed in by hand"
        self.assertIn("TESTGATE-SOURCE-CLAIM", self.codes(document))


class MachineStateTests(unittest.TestCase):
    def test_absent_history_changes_the_report_not_the_judgement(self) -> None:
        real = gate.HISTORY
        try:
            gate.HISTORY = ROOT / ".project-local" / "no-such-history.jsonl"
            document = record()
            self.assertEqual(gate.history_agreement(document), ("HISTORY_ABSENT", 0))
            # The judgement half never touches the history file at all.
            self.assertEqual(gate.record_findings(document), [])
        finally:
            gate.HISTORY = real

    def test_the_writer_refuses_to_invent_a_pass_without_history(self) -> None:
        real = gate.HISTORY
        try:
            gate.HISTORY = ROOT / ".project-local" / "no-such-history.jsonl"
            self.assertEqual(gate.build_document()["verdict"], "FAIL",
                             "a gate with no runs on this machine must say FAIL, not PASS")
        finally:
            gate.HISTORY = real


class RuntimeTests(unittest.TestCase):
    def test_the_check_passes_reports_machine_state_and_writes_nothing(self) -> None:
        def porcelain() -> str:
            return subprocess.run(["git", "status", "--porcelain"], cwd=str(ROOT),
                                  capture_output=True, text=True, encoding="utf-8",
                                  errors="replace").stdout

        before = porcelain()
        result = subprocess.run([sys.executable, "-X", "utf8", "-B",
                                 str(ROOT / "scripts" / "deepseek_test_gate_report.py"), "--check"],
                                cwd=str(ROOT), capture_output=True, text=True,
                                encoding="utf-8", errors="replace", timeout=900)
        output = (result.stdout or "") + (result.stderr or "")
        self.assertEqual(result.returncode, 0, output[-900:])
        self.assertIn("TEST_GATE=PASS", output)
        self.assertIn("findings=0", output)
        self.assertIn("local_history=", output,
                      "the machine-dependent half must be reported, not hidden")
        self.assertEqual(before, porcelain(), "the read-only form wrote a tracked file")


if __name__ == "__main__":
    unittest.main()
