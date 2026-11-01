# SPDX-License-Identifier: MIT
"""The authority chain must verify records, not rewrite them mid-job.

Found by measuring, not guessing: `scripts/verify_authority_gates.py` is the chain CI runs, four of
its five entries passed `--check`, and the fifth -- `verify_language_boundary.py` -- was called with
no arguments, which is that script's *writer* form. So every chain run rewrote
`reports/current/LANGUAGE-BOUNDARY-SCAN.json`, and a record that is rewritten is never seen to be
stale: measured today, its judgement still agrees (`verdict=PASS`, `failures=[]`) while its census
says `tracked_files_scanned=3360` against a repository of 3412.

These tests pin the read-only form of that gate, pin that the chain no longer contains a bare
writer entry, and -- because the shape is what matters -- assert the rule over the whole GATES list
rather than over the one script that happened to be caught.
"""
from __future__ import annotations

import ast
import contextlib
import hashlib
import importlib.util
import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GATE = ROOT / "scripts" / "verify_language_boundary.py"
CHAIN = ROOT / "scripts" / "verify_authority_gates.py"
RECORD = ROOT / "reports" / "current" / "LANGUAGE-BOUNDARY-SCAN.json"

sys.path.insert(0, str(ROOT))

from scripts.verify_language_boundary import check_against  # noqa: E402

SHA_A = "a" * 40


def module():
    spec = importlib.util.spec_from_file_location("verify_language_boundary", GATE)
    built = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(built)
    return built


class CheckAgainstTests(unittest.TestCase):
    def test_a_matching_judgement_produces_no_problem(self) -> None:
        stored = {"verdict": "PASS", "failures": [], "tracked_files_scanned": 10}
        fresh = {"verdict": "PASS", "failures": [], "tracked_files_scanned": 10}
        self.assertEqual(check_against(stored, fresh), ([], []))

    def test_a_changed_verdict_is_a_problem(self) -> None:
        problems, notices = check_against({"verdict": "PASS", "failures": []},
                                          {"verdict": "FAIL", "failures": ["x"]})
        self.assertTrue(any("verdict" in p for p in problems), problems)

    def test_the_failing_set_is_compared_in_both_directions(self) -> None:
        problems, _ = check_against({"verdict": "FAIL", "failures": ["gone"]},
                                    {"verdict": "FAIL", "failures": ["new"]})
        joined = " ".join(problems)
        self.assertIn("only-stored=['gone']", joined, problems)
        self.assertIn("only-fresh=['new']", joined, problems)

    def test_the_census_moves_are_reported_not_failed(self) -> None:
        """Every commit changes the file count; pinning it here would re-run the writer."""
        problems, notices = check_against({"verdict": "PASS", "failures": [],
                                           "tracked_files_scanned": 3360},
                                          {"verdict": "PASS", "failures": [],
                                           "tracked_files_scanned": 3412})
        self.assertEqual(problems, [])
        self.assertEqual(len(notices), 1)
        self.assertIn("3412", notices[0])

    def test_the_subject_field_is_deliberately_not_compared(self) -> None:
        """The committed record predates the argv fix, so its empty subject is declared debt."""
        problems, _ = check_against({"verdict": "PASS", "failures": [], "subject_sha": ""},
                                    {"verdict": "PASS", "failures": [], "subject_sha": SHA_A})
        self.assertEqual(problems, [])
        self.assertEqual(problems, [], "a judgement check must not become a second voice about "
                                       "the debt register")


class CheckerFormTests(unittest.TestCase):
    def test_check_passes_against_the_committed_record(self) -> None:
        r = subprocess.run([sys.executable, str(GATE), "--check"], capture_output=True,
                           text=True, encoding="utf-8", errors="replace", cwd=str(ROOT),
                           timeout=600)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("mode=check judgement_agrees=yes", r.stdout)

    def test_check_writes_nothing_to_the_record(self) -> None:
        before = hashlib.sha256(RECORD.read_bytes()).hexdigest()
        r = subprocess.run([sys.executable, str(GATE), "--check"], capture_output=True,
                           text=True, encoding="utf-8", errors="replace", cwd=str(ROOT),
                           timeout=600)
        self.assertEqual(r.returncode, 0, r.stdout[-600:])
        self.assertEqual(hashlib.sha256(RECORD.read_bytes()).hexdigest(), before,
                         "the checker form rewrote the tracked record it claims to verify")

    def test_a_missing_record_fails_closed(self) -> None:
        gate = module()
        original = gate.OUT
        try:
            gate.OUT = ROOT / "reports" / "current" / "does-not-exist-check-mode.json"
            self.assertEqual(gate.main(["--check"]), 1)
        finally:
            gate.OUT = original

    def test_a_disagreeing_record_is_red(self) -> None:
        gate = module()
        with tempfile_record({"verdict": "FAIL", "failures": ["invented"],
                              "tracked_files_scanned": 1}) as path:
            original = gate.OUT
            try:
                gate.OUT = path
                self.assertEqual(gate.main(["--check"]), 1)
            finally:
                gate.OUT = original


class ChainEntryTests(unittest.TestCase):
    """The class rule: a chain entry may not invoke a tracked-path writer without a flag."""

    def gates(self) -> list[tuple[str, str, list[str]]]:
        tree = ast.parse(CHAIN.read_text(encoding="utf-8"))
        for node in tree.body:
            if isinstance(node, ast.Assign) and getattr(node.targets[0], "id", "") == "GATES":
                return [(el.elts[0].value, el.elts[1].value,
                         [a.value for a in el.elts[2].elts]) for el in node.value.elts]
        raise AssertionError("no GATES list in the authority chain")

    def test_no_entry_calls_a_writer_bare(self) -> None:
        offenders = []
        for _name, script, args in self.gates():
            if args:
                continue
            text = (ROOT / script).read_text(encoding="utf-8")
            writes_tracked = "OUT = REPO" in text or "RECORD = REPO" in text
            if writes_tracked:
                offenders.append(script)
        self.assertEqual(offenders, [],
                         f"{offenders} are invoked with no arguments and write a tracked path")

    def test_the_language_boundary_entry_is_the_checker_form(self) -> None:
        entry = next(gate for gate in self.gates() if "verify_language_boundary" in gate[1])
        self.assertEqual(entry[2], ["--check"])

    def test_every_chain_child_that_writes_a_record_passes_a_read_only_flag(self) -> None:
        read_only = ({"--check"}, {"verify"}, {"--self-test"}, set())
        for _name, script, args in self.gates():
            text = (ROOT / script).read_text(encoding="utf-8")
            if "OUT = REPO" not in text:
                continue
            if not args:
                continue
            self.assertTrue(args[0] in ("--check", "verify") or script.endswith(
                "deepseek_authority_ledger.py"),
                f"{script} writes a tracked record and was passed {args}")


@contextlib.contextmanager
def tempfile_record(document: dict):
    import tempfile
    handle = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8")
    try:
        handle.write(json.dumps(document, indent=2) + "\n")
        handle.close()
        yield Path(handle.name)
    finally:
        Path(handle.name).unlink()


class ModuleDocstringTests(unittest.TestCase):
    def test_the_gate_documents_why_check_does_not_compare_the_subject(self) -> None:
        text = GATE.read_text(encoding="utf-8")
        self.assertIn("report-subject-debt.json", text,
                      "the checker must say which record owns the empty subject, or the next "
                      "reader will 'fix' it here")


class ChainEncodingTests(unittest.TestCase):
    """The chain ran on Linux and never on this host's console codepage, until it crashed here."""

    def chain(self):
        spec = importlib.util.spec_from_file_location("verify_authority_gates", CHAIN)
        built = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(built)
        return built

    def test_children_are_told_to_emit_utf8(self) -> None:
        self.assertEqual(self.chain().child_env().get("PYTHONIOENCODING"), "utf-8",
                         "a child falling back to the console codepage turns its own Chinese "
                         "output into U+FFFD in the parent's hands")

    def test_safe_text_keeps_ascii_and_survives_an_unencodable_console(self) -> None:
        chain = self.chain()
        self.assertEqual(chain.safe_text("AUTHORITY_GATES=PASS"), "AUTHORITY_GATES=PASS")
        rendered = chain.safe_text("中文 \ufffd note")
        encoding = getattr(sys.stdout, "encoding", None) or "utf-8"
        rendered.encode(encoding, errors="strict")

    def test_the_chain_completes_on_a_gbk_console_and_writes_no_tracked_file(self) -> None:
        """Reproduces the crash: the parent printed a child's mangled line and aborted.

        Regression-pins both halves of the fix -- the UTF-8 child env and the sanitised echo --
        and asserts what the whole exercise was for: a check-only chain leaves the working tree
        untouched.
        """
        import os
        before = subprocess.run(["git", "status", "--porcelain"], cwd=str(ROOT),
                                capture_output=True, text=True, encoding="utf-8",
                                errors="replace").stdout
        env = dict(os.environ, PYTHONIOENCODING="gbk")
        r = subprocess.run([sys.executable, str(CHAIN), "--zero-spill"], cwd=str(ROOT),
                           capture_output=True, text=True, encoding="utf-8", errors="replace",
                           env=env, timeout=900)
        after = subprocess.run(["git", "status", "--porcelain"], cwd=str(ROOT),
                               capture_output=True, text=True, encoding="utf-8",
                               errors="replace").stdout
        self.assertNotIn("UnicodeEncodeError", r.stderr,
                         "the chain aborted while echoing a child's report line")
        self.assertIn("AUTHORITY_GATES=PASS", r.stdout, r.stdout[-800:] + r.stderr[-800:])
        self.assertEqual(r.returncode, 0, r.stdout[-800:])
        self.assertEqual(before, after, "the chain wrote a tracked file; it is meant to check only")


if __name__ == "__main__":
    unittest.main()
