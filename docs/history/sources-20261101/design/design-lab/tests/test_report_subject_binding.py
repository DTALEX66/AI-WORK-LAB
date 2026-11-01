# SPDX-License-Identifier: MIT
"""A projection that claims a subject must name a commit, or the gap is a booked row.

`git("rev-parse HEAD")` -- one argv element -- is rejected by git, the helper returns empty
stdout, and `subject_sha` is written as `""`. Nine tracked records were in that state on
2026-10-09 and no gate noticed, because a field that names nothing looks identical to a field
nobody filled in. `verify_report_subject_binding.py` grades every `subject_sha`/`subjectSha`
under `reports/current/` and `design-lab/config/`, and refuses the call shape itself so a tenth
cannot appear.

Each finding is fed a planted defect, and the two that matter most are pinned: a record that
becomes bound while still declared is red (the register may only shrink), and a joined call in a
script nobody declared is red (the register may not grow).
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "design-lab" / "scripts" / "verify_report_subject_binding.py"
DEBT_REL = "design-lab/config/report-subject-debt.json"
SHA_A = "a" * 40
SHA_B = "b" * 40

sys.path.insert(0, str(ROOT / "design-lab" / "scripts"))

import verify_report_subject_binding as v  # noqa: E402


class Tree:
    """A repository-shaped tmp dir the gate can be pointed at."""

    def __init__(self, ctx: tempfile.TemporaryDirectory) -> None:
        self.root = Path(ctx.name)
        (self.root / "reports" / "current").mkdir(parents=True, exist_ok=True)
        (self.root / "design-lab" / "config").mkdir(parents=True, exist_ok=True)
        (self.root / "scripts").mkdir(parents=True, exist_ok=True)

    def record(self, name: str, document: dict, directory: str = "reports/current") -> str:
        rel = f"{directory}/{name}"
        (self.root / rel).parent.mkdir(parents=True, exist_ok=True)
        (self.root / rel).write_text(json.dumps(document, indent=2) + "\n",
                                     encoding="utf-8", newline="\n")
        return rel

    def generator(self, name: str, body: str) -> str:
        rel = f"scripts/{name}"
        (self.root / rel).write_text(body, encoding="utf-8", newline="\n")
        return rel

    def debt(self, records: list[dict], call_sites: list[dict] | None = None,
             schema: str = v.SCHEMA_VERSION) -> None:
        document = {"schemaVersion": schema, "records": records,
                    "callSites": call_sites or []}
        (self.root / DEBT_REL).write_text(json.dumps(document, indent=2) + "\n",
                                          encoding="utf-8", newline="\n")

    def problems(self) -> list[str]:
        return v.check(self.root)[0]

    def result(self):
        return v.check(self.root)


def row(rel: str, key: str = "subject_sha", producer: str = "scripts/writer.py",
        fixed_on: str | None = "2026-10-09") -> dict:
    """A valid declaration: who writes it, why it is empty, and what would close it."""
    return {"path": rel, "key": key, "producer": producer,
            "reason": "the generator joined the git arguments",
            "whatWouldCloseIt": "one intentional run at a recorded head, then delete this row",
            "declaredOn": "2026-10-09", "producerFixedOn": fixed_on}


class ReportSubjectBindingTests(unittest.TestCase):
    def setUp(self) -> None:
        self._stack: list[tempfile.TemporaryDirectory] = []

    def tree(self) -> Tree:
        ctx = tempfile.TemporaryDirectory()
        self._stack.append(ctx)
        return Tree(ctx)

    def tearDown(self) -> None:
        for ctx in self._stack:
            ctx.cleanup()
        self._stack.clear()

    # ---- the data rule ----

    def test_a_bound_record_passes_with_no_register_at_all(self) -> None:
        tree = self.tree()
        tree.record("BOUND.json", {"schemaVersion": "x/v1", "subject_sha": SHA_A})
        self.assertEqual(tree.problems(), [])
        self.assertEqual(tree.result()[1:3], (1, 0))

    def test_an_empty_subject_that_is_not_declared_is_convicted(self) -> None:
        tree = self.tree()
        rel = tree.record("EMPTY.json", {"schemaVersion": "x/v1", "subject_sha": ""})
        findings = tree.problems()
        self.assertTrue(any(f.startswith("REPORT-SUBJECT-UNBOUND") and rel in f
                            for f in findings), findings)

    def test_the_same_gap_declared_is_counted_instead_of_failed(self) -> None:
        tree = self.tree()
        rel = tree.record("EMPTY.json", {"schemaVersion": "x/v1", "subject_sha": ""})
        tree.generator("writer.py", "def git(*a): pass\n")
        tree.debt([row(rel)])
        self.assertEqual(tree.problems(), [])
        problems, records, declared, _joined = tree.result()
        self.assertEqual((records, declared), (1, 1))

    def test_a_record_that_becomes_bound_must_leave_the_register(self) -> None:
        """The register only shrinks. A row kept after the fix is its own finding."""
        tree = self.tree()
        rel = tree.record("FIXED.json", {"schemaVersion": "x/v1", "subject_sha": SHA_A})
        tree.generator("writer.py", "def git(*a): pass\n")
        tree.debt([row(rel)])
        self.assertTrue(any("REPORT-DEBT-CLOSED-NOT-REMOVED" in f for f in tree.problems()))

    def test_a_half_written_value_is_convicted_as_shape_not_as_empty(self) -> None:
        tree = self.tree()
        rel = tree.record("TRUNC.json", {"schemaVersion": "x/v1", "subject_sha": SHA_A[:39]})
        tree.generator("writer.py", "def git(*a): pass\n")
        tree.debt([row(rel)])
        self.assertTrue(any("REPORT-SUBJECT-SHAPE" in f for f in tree.problems()))

    def test_a_declared_producer_that_is_gone_is_convicted(self) -> None:
        tree = self.tree()
        rel = tree.record("EMPTY.json", {"schemaVersion": "x/v1", "subject_sha": ""})
        tree.debt([row(rel, producer="scripts/dead.py")])
        self.assertTrue(any("REPORT-DEBT-PRODUCER-MISSING" in f for f in tree.problems()))

    def test_a_declared_row_for_a_field_that_is_not_read_is_convicted(self) -> None:
        tree = self.tree()
        tree.record("OTHER.json", {"schemaVersion": "x/v1", "subject_sha": SHA_A})
        tree.generator("writer.py", "def git(*a): pass\n")
        tree.debt([row("reports/current/GONE.json")])
        findings = tree.problems()
        self.assertTrue(any("REPORT-DEBT-UNSCANNED" in f for f in findings), findings)

    def test_one_corrupt_register_yields_exactly_one_finding(self) -> None:
        """The register is parsed once; a doubled finding teaches consumers to ignore it."""
        tree = self.tree()
        tree.record("EMPTY.json", {"schemaVersion": "x/v1", "subject_sha": ""})
        (tree.root / DEBT_REL).write_text("{not json", encoding="utf-8")
        unreadable = [f for f in tree.problems() if f.startswith("REPORT-DEBT-UNREADABLE")]
        self.assertEqual(len(unreadable), 1, unreadable)

    def test_a_row_without_a_reason_is_not_a_declaration(self) -> None:
        tree = self.tree()
        rel = tree.record("EMPTY.json", {"schemaVersion": "x/v1", "subject_sha": ""})
        tree.generator("writer.py", "def git(*a): pass\n")
        tree.debt([{"path": rel, "key": "subject_sha", "producer": "scripts/writer.py"}])
        self.assertTrue(any("REPORT-DEBT-ROW-INCOMPLETE" in f for f in tree.problems()))

    def test_a_duplicated_row_is_convicted(self) -> None:
        tree = self.tree()
        rel = tree.record("EMPTY.json", {"schemaVersion": "x/v1", "subject_sha": ""})
        tree.generator("writer.py", "def git(*a): pass\n")
        tree.debt([row(rel), row(rel)])
        self.assertTrue(any("REPORT-DEBT-DUPLICATE" in f for f in tree.problems()))

    def test_a_foreign_schema_version_is_convicted(self) -> None:
        tree = self.tree()
        rel = tree.record("EMPTY.json", {"schemaVersion": "x/v1", "subject_sha": ""})
        tree.generator("writer.py", "def git(*a): pass\n")
        tree.debt([row(rel)], schema="design-lab/report-subject-debt/v0")
        self.assertTrue(any("REPORT-DEBT-SCHEMA" in f for f in tree.problems()))

    def test_a_missing_register_still_convicts_an_undeclared_gap(self) -> None:
        """Absence of the register is not absence of debt: the record itself is graded."""
        tree = self.tree()
        rel = tree.record("EMPTY.json", {"schemaVersion": "x/v1", "subject_sha": ""})
        findings = tree.problems()
        self.assertTrue(any(f.startswith("REPORT-SUBJECT-UNBOUND") and rel in f
                            for f in findings), findings)
        self.assertEqual([f for f in findings if "UNREADABLE" in f], [],
                         "no register is the normal state of a debt-free repository")

    def test_both_spellings_are_graded_and_a_bound_sibling_is_named(self) -> None:
        """One key can be empty while the other holds a commit; a reader gets only what it asks."""
        tree = self.tree()
        rel = tree.record("TWIN.json", {"subject_sha": "", "subjectSha": SHA_B})
        findings = tree.problems()
        self.assertTrue(any("REPORT-SUBJECT-UNBOUND" in f and "under the other spelling" in f
                            for f in findings), findings)
        tree.debt([row(rel)])
        self.assertEqual([f for f in tree.problems() if "SUBJECT" in f], [])
        self.assertEqual(tree.result()[2], 1)

    def test_the_key_is_part_of_the_row_identity(self) -> None:
        tree = self.tree()
        rel = tree.record("TWIN.json", {"subject_sha": "", "subjectSha": ""})
        tree.generator("writer.py", "def git(*a): pass\n")
        tree.debt([row(rel)])
        self.assertTrue(any("REPORT-SUBJECT-UNBOUND" in f and "subjectSha" in f
                            for f in tree.problems()))

    def test_unparseable_and_oversized_records_are_skipped_not_guessed(self) -> None:
        tree = self.tree()
        (tree.root / "reports" / "current" / "broken.json").write_text("{not json",
                                                                       encoding="utf-8")
        big = tree.record("big.json", {"subject_sha": ""})
        path = tree.root / big
        path.write_text(json.dumps({"subject_sha": "", "pad": "x" * 4_000_000}),
                        encoding="utf-8", newline="\n")
        self.assertEqual([rel for rel, _k, _v in v.subject_records(tree.root)], [])

    # ---- the code rule ----

    def test_a_joined_git_call_is_refused(self) -> None:
        tree = self.tree()
        tree.record("BOUND.json", {"subject_sha": SHA_A})
        tree.generator("maker.py", 'def git(*args):\n    pass\n\n\ngit("rev-parse HEAD")\n')
        tree.debt([])
        findings = tree.problems()
        self.assertTrue(any(f.startswith("GIT-ARG-JOINED") for f in findings), findings)

    def test_a_declared_call_site_is_booked_rather_than_failed(self) -> None:
        tree = self.tree()
        tree.record("BOUND.json", {"subject_sha": SHA_A})
        tree.generator("maker.py", 'def git(*args):\n    pass\n\n\ngit("rev-parse HEAD")\n')
        tree.debt([], [{"script": "scripts/maker.py", "joinedArgument": "rev-parse HEAD",
                        "writesRecord": "reports/current/BOUND.json",
                        "reason": "booked", "declaredOn": "2026-10-09"}])
        self.assertEqual(tree.problems(), [])
        self.assertEqual(tree.result()[3], 1)

    def test_a_separated_call_that_stays_declared_is_convicted(self) -> None:
        tree = self.tree()
        tree.record("BOUND.json", {"subject_sha": SHA_A})
        tree.generator("maker.py", 'def git(*args):\n    pass\n\n\ngit("rev-parse", "HEAD")\n')
        tree.debt([], [{"script": "scripts/maker.py", "joinedArgument": "rev-parse HEAD",
                        "writesRecord": "reports/current/BOUND.json",
                        "reason": "booked", "declaredOn": "2026-10-09"}])
        self.assertTrue(any("CALL-DEBT-CLOSED-NOT-REMOVED" in f for f in tree.problems()))

    def test_a_call_site_declared_for_the_wrong_argument_is_convicted(self) -> None:
        tree = self.tree()
        tree.record("BOUND.json", {"subject_sha": SHA_A})
        tree.generator("maker.py", 'def git(*args):\n    pass\n\n\ngit("status --porcelain")\n')
        tree.debt([], [{"script": "scripts/maker.py", "joinedArgument": "rev-parse HEAD",
                        "writesRecord": "reports/current/BOUND.json",
                        "reason": "booked", "declaredOn": "2026-10-09"}])
        self.assertTrue(any("CALL-DEBT-ARG-MISMATCH" in f for f in tree.problems()))

    def test_a_declared_call_site_whose_script_is_gone_is_convicted(self) -> None:
        tree = self.tree()
        tree.record("BOUND.json", {"subject_sha": SHA_A})
        tree.debt([], [{"script": "scripts/dead.py", "joinedArgument": "rev-parse HEAD",
                        "writesRecord": "reports/current/BOUND.json",
                        "reason": "booked", "declaredOn": "2026-10-09"}])
        self.assertTrue(any("CALL-DEBT-PRODUCER-MISSING" in f for f in tree.problems()))

    def test_only_the_git_helper_is_scanned(self) -> None:
        """A different function legitimately takes one spaced string; it is not this bug."""
        tree = self.tree()
        tree.record("BOUND.json", {"subject_sha": SHA_A})
        tree.generator("other.py",
                       'def run(*args):\n    pass\n\n\nrun("rev-parse HEAD")\n')
        tree.debt([])
        self.assertEqual(tree.problems(), [])

    def test_a_row_must_say_what_would_close_it(self) -> None:
        tree = self.tree()
        rel = tree.record("EMPTY.json", {"schemaVersion": "x/v1", "subject_sha": ""})
        tree.generator("writer.py", "def git(*a): pass\n")
        naked = {k: value for k, value in row(rel).items() if k != "whatWouldCloseIt"}
        tree.debt([naked])
        self.assertTrue(any("whatWouldCloseIt" in f for f in tree.problems()))

    def test_a_row_must_say_whether_its_producer_is_still_broken(self) -> None:
        tree = self.tree()
        rel = tree.record("EMPTY.json", {"schemaVersion": "x/v1", "subject_sha": ""})
        tree.generator("writer.py", "def git(*a): pass\n")
        naked = {k: value for k, value in row(rel).items() if k != "producerFixedOn"}
        tree.debt([naked])
        self.assertTrue(any("producerFixedOn" in f for f in tree.problems()))

    def test_a_row_claiming_a_fix_that_is_not_in_the_source_is_convicted(self) -> None:
        tree = self.tree()
        rel = tree.record("EMPTY.json", {"schemaVersion": "x/v1", "subject_sha": ""})
        tree.generator("writer.py", 'def git(*a):\n    pass\n\n\ngit("rev-parse HEAD")\n')
        tree.debt([row(rel)], )
        # The joined call still exists, so the row needs a callSites entry as well; without it
        # the site is undeclared, and with a fix date the row contradicts the file either way.
        tree.debt([row(rel)], [{"script": "scripts/writer.py", "joinedArgument": "rev-parse HEAD",
                                "writesRecord": rel, "reason": "booked",
                                "declaredOn": "2026-10-09"}])
        self.assertTrue(any("RECORD-PRODUCER-STILL-BROKEN" in f for f in tree.problems()),
                        tree.problems())

    def test_a_row_that_still_blames_a_repaired_producer_is_convicted(self) -> None:
        """The defect description may not outlive the defect without saying so."""
        tree = self.tree()
        rel = tree.record("EMPTY.json", {"schemaVersion": "x/v1", "subject_sha": ""})
        tree.generator("writer.py", 'def git(*a):\n    pass\n\n\ngit("rev-parse", "HEAD")\n')
        tree.debt([row(rel, fixed_on=None)])
        self.assertTrue(any("RECORD-DEFECT-STILL-CLAIMED" in f for f in tree.problems()),
                        tree.problems())

    # ---- shipped state ----

    def test_the_shipped_repository_passes_the_gate(self) -> None:
        r = subprocess.run([sys.executable, str(SCRIPT)], capture_output=True, text=True,
                           encoding="utf-8", errors="replace", cwd=str(ROOT))
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("VERIFY_REPORT_SUBJECT_BINDING=OK", r.stdout)

    def test_the_shipped_register_declares_exactly_the_measured_debt(self) -> None:
        document = json.loads((ROOT / DEBT_REL).read_text(encoding="utf-8"))
        records, calls = document["records"], document["callSites"]
        # Pinned as a set: a row may leave only by the record being re-run at a recorded head,
        # and a new one may not join silently. RECOVERY-SAFETY left on 2026-10-09 when
        # scripts/verify_recovery_safety.py changed its own verdict shape and had to be rebound;
        # the register's `thisRound.rebasedOn` records that run and what it did not decide.
        self.assertEqual(sorted(row["path"] for row in records),
                         ["design-lab/config/rights-registry.json",
                          # Two rows left this set on 2026-10-19, each by the mechanism its own row
                          # demanded -- an intentional producer run at a recorded head, then the row
                          # deleted in that same pass and preserved under resolved_2026_10_19 (which is
                          # now a list of the two). CONTRACT-GRAPH left when T16/U09 added the knowledge
                          # read-back tables and the graph was re-run at 15ec42a4; CLEAN-TREE left when
                          # the archive/removal wave ran its producer at e9ff0717 and committed the
                          # output, so subject_sha stopped being empty. DLDS-I020's cited record is
                          # re-based along with that run, and the register says so rather than hiding it.
                          # Neither departure is silent: this pin is exact on purpose, and the gate that
                          # reports REPORT-DEBT-CLOSED-NOT-REMOVED is what forces the bookkeeping to
                          # follow the fact instead of the other way round.
                          # FOUNDATION-AUDIT / POST-CLEANUP-AUDIT / SPILL-CENSUS / rights-registry stay:
                          # their rows still name work that has not been done.
                          "reports/current/FOUNDATION-AUDIT.json",
                          # LANGUAGE-BOUNDARY-SCAN.json left this set on 2026-10-13: its
                          # row required "one intentional run at a recorded head, then
                          # delete the row in the same commit", and both happened. The
                          # removal is declared in report-subject-debt.json
                          # closureNote_2026_12_12 -- this pin is what catches a SILENT one.
                          "reports/current/POST-CLEANUP-AUDIT.json",
                          # REPOSITORY-SIZE.json left this set on 2026-10-18: its row required
                          # "re-running the generator rewrites the whole record", and the 2026-10-18
                          # repo cleanup re-ran the size-audit generator (deliberately not named with
                          # its filename here: test_gate_reachability treats a script named inside a
                          # test module as *invoked* by it, so writing the filename would flip that
                          # script from "exempt manual gate" to "reachable" and fail the stale-exemption
                          # check -- a comment must not be able to claim a call site), which now writes
                          # a real subject_sha. The row was removed from records[] in the same commit
                          # and kept under resolved_2026_10_18; verify_report_subject_binding is what
                          # refused to let it leave silently (REPORT-DEBT-CLOSED-NOT-REMOVED).
                          # This pin is exact on purpose: it catches a silent removal, not a recorded one.
                          "reports/current/SPILL-CENSUS.json"],
                         "the unbound set only moves when a record is re-run")
        # Pinned with the reason. On 2026-10-09 all nine producers were repaired, so the code
        # debt is closed and only the data debt is left; a new joined call is refused outright
        # by GIT-ARG-JOINED instead of landing here as a row.
        self.assertEqual(calls, [], "a joined git call appeared after the class was closed -- "
                                    "fix the call, do not declare the shape")
        self.assertEqual(document["thisRound"]["joinedGitCallSitesFixed"], 9)
        self.assertEqual(document["thisRound"]["recordsRegenerated"], 0)

    def test_no_joined_git_call_survives_anywhere_in_the_repository(self) -> None:
        self.assertEqual(v.joined_git_call_sites(), [])

    def test_every_declared_producer_carries_the_repaired_call(self) -> None:
        """The shipped bytes prove the fix, not the register's prose about it."""
        document = json.loads((ROOT / DEBT_REL).read_text(encoding="utf-8"))
        for declared in document["records"]:
            script = (ROOT / declared["producer"]).read_text(encoding="utf-8")
            self.assertIn('git("rev-parse", "HEAD")', script,
                          f"{declared['producer']} does not contain the separated call its row "
                          "claims")
            self.assertNotIn('git("rev-parse HEAD")', script,
                             f"{declared['producer']} still contains the broken shape")

    def test_every_declared_gap_names_the_evidence_it_would_re_base(self) -> None:
        """Why these rows were not simply re-run: each record is cited by a closed ledger task."""
        document = json.loads((ROOT / DEBT_REL).read_text(encoding="utf-8"))
        for declared in document["records"]:
            tasks = declared["citedByLedgerTasks"]
            self.assertGreaterEqual(len(tasks), 1,
                                    f"{declared['path']} cites no ledger task, so nothing "
                                    "explains why the record was left alone")
            for task in tasks:
                self.assertRegex(task, r"^DLDS-[A-Z]\d{3}",
                                 f"{declared['path']} cites {task!r}, which is not a task_key "
                                 "read from the ledger")
            self.assertTrue(str(declared["whatWouldCloseIt"]).strip())
            self.assertEqual(declared["producerFixedOn"], "2026-10-09")

    def test_no_declared_record_is_already_bound(self) -> None:
        document = json.loads((ROOT / DEBT_REL).read_text(encoding="utf-8"))
        values = {(rel, key): value for rel, key, value in v.subject_records()}
        for row_ in document["records"]:
            value = str(values.get((row_["path"], row_["key"])) or "")
            self.assertFalse(v.SHA40.match(value),
                             f"{row_['path']}#{row_['key']} is bound but still declared")

    def test_the_three_fixed_gates_are_no_longer_in_the_debt(self) -> None:
        """The fix in the same round must show up as a smaller register, not a quieter gate."""
        document = json.loads((ROOT / DEBT_REL).read_text(encoding="utf-8"))
        paths = {r["path"] for r in document["records"]} | {c["script"] for c in document["callSites"]}
        for fixed in ("SUPPLY-CHAIN-REPORT.json", "EVIDENCE-LEVEL-AUDIT.json",
                      "NO-OVERCLAIM-AUDIT.json", "verify_supply_chain.py",
                      "verify_evidence_levels.py", "verify_no_overclaim.py"):
            self.assertNotIn(fixed, " ".join(sorted(paths)),
                             f"{fixed} was fixed in this round and must not stay declared")

    def test_the_gate_is_registered_in_the_aggregate(self) -> None:
        scripts = (ROOT / "design-lab" / "scripts" / "verify_design_lab.py").read_text(
            encoding="utf-8")
        self.assertIn("verify_report_subject_binding.py", scripts,
                      "a gate nobody invokes is documentation")


if __name__ == "__main__":
    unittest.main()
