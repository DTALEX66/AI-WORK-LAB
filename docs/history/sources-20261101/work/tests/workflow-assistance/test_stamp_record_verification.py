"""Gate the verification stamper: it writes traceability fields, so its refusals are the product.

A `verifiedCommit` is the strongest claim in the ledger — that CI looked at this exact head and the
record was inside it. The tool must therefore fail closed on every ambiguity, and the tests below
each hand it an ambiguous case and require a refusal. The ancestry check has its own test because the
first version compared a captured stdout against zero and refused everything: an ancestry test prints
nothing, so only the return code answers the question.

Every control that runs the CLI hands it a fixture ledger with `--ledger`. Without that, a control's
ability to fail depends on whether the shipped record happens to be stamped yet - which is how two of
them went red the moment their own record was legitimately verified.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "audit" / "stamp_record_verification.py"
LEDGER = ROOT / "taskpacks/current/error-ledger.json"

spec = importlib.util.spec_from_file_location("stamp_record_verification", SCRIPT)
stamper = importlib.util.module_from_spec(spec)
spec.loader.exec_module(stamper)  # type: ignore[attr-defined]


def row(error_id: str, fixed: str, verified: str | None = None) -> dict:
    return {"error_id": error_id, "lifecycle": {"fixedCommit": fixed, "verifiedCommit": verified}}


class HeadResolutionTests(unittest.TestCase):
    def test_an_unresolvable_short_name_is_not_a_commit(self) -> None:
        self.assertEqual("", stamper.head_of("deadbee"))
        self.assertEqual(40, len(stamper.head_of("HEAD")))


class AncestryTests(unittest.TestCase):
    def test_the_real_check_accepts_a_known_descendant_pair(self) -> None:
        # Measured on this repository rather than asserted in the abstract: the stamp that this
        # tool's first version wrongly refused, because it compared captured stdout to zero and an
        # ancestry test prints nothing.
        doc = json.loads(LEDGER.read_text(encoding="utf-8"))
        row148 = next(e for e in doc["errors"] if e["error_id"] == "ERR-148")
        sha = stamper.head_of("07082ed")
        rc = subprocess.run(["git", "merge-base", "--is-ancestor",
                             row148["lifecycle"]["fixedCommit"], sha],
                            cwd=ROOT, capture_output=True).returncode
        self.assertEqual(0, rc, "the stamper must not refuse a genuine descendant")

class RefusalsRunAgainstAFixtureLedger(unittest.TestCase):
    """A refusal can only be proven by handing the tool a record it has no stamp for.

    These controls used to invoke the shipped ledger by error id. That worked while ERR-149 was unstamped
    and silently stopped working the moment ERR-149 was legitimately verified: the tool short-circuits on
    an existing verifiedCommit, exits 0, and the check that is supposed to prove it refuses anything
    ambiguous had nothing left to refuse. The fixture ledger is what makes the control independent of how
    much of the real debt has since been closed.
    """

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.ledger = Path(self.tmp.name) / "error-ledger.json"
        self.real_before = hashlib.sha256(LEDGER.read_bytes()).hexdigest()
        shipped = json.loads(LEDGER.read_text(encoding="utf-8"))
        self.row = next(e for e in shipped["errors"] if e["error_id"] == "ERR-149")

    def tearDown(self) -> None:
        self.assertEqual(self.real_before, hashlib.sha256(LEDGER.read_bytes()).hexdigest(),
                         "a negative control must never write the shipped ledger")
        self.tmp.cleanup()

    def fixture(self, verified: str | None) -> None:
        row = json.loads(json.dumps(self.row))
        row["lifecycle"]["verifiedCommit"] = verified
        self.ledger.write_text(json.dumps({"errors": [row]}, ensure_ascii=False, indent=2),
                               encoding="utf-8")

    def cli(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run([sys.executable, str(SCRIPT), "--ledger", str(self.ledger), *args],
                              cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
                              errors="replace")

    def test_an_unresolvable_head_is_refused(self) -> None:
        self.fixture(None)
        proc = self.cli("ERR-149", "deadbee")
        self.assertEqual(1, proc.returncode, proc.stdout + proc.stderr)
        self.assertIn("REFUSED ERR-149", proc.stdout)
        self.assertIn("does not resolve", proc.stdout)

    def test_a_head_without_the_record_is_refused_even_though_ancestry_holds(self) -> None:
        # 5143726 is ERR-149's own fix commit, so ancestry passes trivially, but the record is written in
        # the commit after it — a stamp there would claim a readback of a tree that lacks the record.
        self.fixture(None)
        proc = self.cli("ERR-149", "5143726")
        self.assertEqual(1, proc.returncode, proc.stdout + proc.stderr)
        self.assertIn("REFUSED ERR-149", proc.stdout)
        self.assertIn("does not contain the record", proc.stdout)

    def test_an_existing_verifiedCommit_survives_untouched(self) -> None:
        self.fixture("17eb5b6" + "0" * 33)
        proc = self.cli("ERR-149", "deadbee")
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
        self.assertIn("already stamped", proc.stdout)
        after = json.loads(self.ledger.read_text(encoding="utf-8"))
        self.assertEqual("17eb5b6" + "0" * 33, after["errors"][0]["lifecycle"]["verifiedCommit"])

    def test_the_tool_reads_the_ledger_it_was_handed(self) -> None:
        # If --ledger were ignored, every refusal above would turn into a success on the shipped record,
        # so this is the control that keeps the three controls above honest.
        self.fixture(None)
        self.ledger.write_text("{ not json", encoding="utf-8")
        proc = self.cli("ERR-149", "deadbee")
        self.assertEqual(2, proc.returncode, proc.stdout + proc.stderr)
        self.assertIn("STAMP_LEDGER_UNREADABLE", proc.stdout)


class CiVerdictTests(unittest.TestCase):
    def test_no_run_for_the_head_is_reported_as_unknown_not_green(self) -> None:
        payload = json.dumps([])
        with mock.patch.object(stamper.subprocess, "run",
                               return_value=subprocess.CompletedProcess([], 0, payload, "")):
            verdict = stamper.ci_verdict("f" * 40)
        self.assertFalse(verdict["known"])
        self.assertIn("NO_RUN_FOR_THIS_HEAD", verdict["reason"])

    def test_a_still_running_workflow_is_unknown_rather_than_a_pass(self) -> None:
        rows = [{"databaseId": 1, "headSha": "a" * 40, "workflowName": "work-lab-gate",
                 "status": "in_progress", "conclusion": None}]
        with mock.patch.object(stamper.subprocess, "run",
                               return_value=subprocess.CompletedProcess([], 0, json.dumps(rows), "")):
            verdict = stamper.ci_verdict("a" * 40)
        self.assertFalse(verdict["known"])
        self.assertIn("still in_progress", verdict["reason"])

    def test_a_failing_workflow_is_reported_and_never_upgraded(self) -> None:
        rows = [{"headSha": "b" * 40, "workflowName": "work-lab-gate", "status": "completed",
                 "conclusion": "failure"},
                {"headSha": "b" * 40, "workflowName": "wlr-060-production-gates",
                 "status": "completed", "conclusion": "success"}]
        with mock.patch.object(stamper.subprocess, "run",
                               return_value=subprocess.CompletedProcess([], 0, json.dumps(rows), "")):
            verdict = stamper.ci_verdict("b" * 40)
        self.assertTrue(verdict["known"])
        self.assertEqual("failure", verdict["verdict"])

    def test_a_gh_query_failure_is_unknown(self) -> None:
        with mock.patch.object(stamper.subprocess, "run",
                               return_value=subprocess.CompletedProcess([], 1, "", "boom")):
            verdict = stamper.ci_verdict("c" * 40)
        self.assertFalse(verdict["known"])
        self.assertIn("GH_QUERY_FAILED", verdict["reason"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
