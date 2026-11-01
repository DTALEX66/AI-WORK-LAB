# SPDX-License-Identifier: MIT
"""A projection that can be re-checked must agree with its own record -- on someone else's clone.

Two defects came out of building `verify_projection_freshness.py`. The first:
`deepseek_language_inventory.py --check` compared the committed per-language file counts against
the live tree, so it had been red for weeks while nothing ran it -- no workflow step, no aggregate
entry, no test, and no reachability pattern match. The second: three other read-only forms pass on
the machine that generated their record and report DRIFT in a clean checkout of the same commit, so
their green describes a disk rather than a repository. Those were named exclusions with reasons, not
dropped entries; one of them (RECOVERY-SAFETY) has since been fixed by archiving the receipts it
audits, and the two left are still named in `test_exclusions_are_named_with_a_reason_and_a_real_script`.

The falsification that matters here is the writer form: an entry invoked with no arguments is the
bug this gate exists to catch, so a test plants exactly that and requires the gate to refuse.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "design-lab" / "scripts" / "verify_projection_freshness.py"

sys.path.insert(0, str(ROOT / "design-lab" / "scripts"))

import verify_projection_freshness as v  # noqa: E402


class EntryTableTests(unittest.TestCase):
    def test_every_entry_is_a_read_only_invocation(self) -> None:
        for record, generator, argv in v.ENTRIES:
            self.assertTrue(argv, f"{generator} would be invoked bare, which is its writer form")
            self.assertIn(argv[0], v.READ_ONLY_FLAGS,
                          f"{generator} {argv} is not a read-only form")

    def test_every_receipt_check_is_read_only_and_actually_declared(self) -> None:
        for generator, argv in v.RECEIPT_CHECKS:
            self.assertTrue(argv, f"{generator} would be invoked bare, which is its writer form")
            self.assertIn(argv[0], v.READ_ONLY_FLAGS, f"{generator} {argv} is not a read-only form")
            self.assertTrue((ROOT / generator).is_file(), generator)
            # Quote-agnostic: the flags are declared with single quotes in some scripts and double
            # in others, and a quote-style assumption here would convict a working entry.
            self.assertIsNotNone(
                re.search(r"[\"']" + re.escape(argv[0]) + r"[\"']",
                          (ROOT / generator).read_text(encoding="utf-8")),
                f"{generator} does not declare {argv[0]}, so the entry names a mode that does "
                "not exist")

    def test_every_entry_record_and_generator_exist(self) -> None:
        for record, generator, _argv in v.ENTRIES:
            self.assertTrue((ROOT / record).is_file(), f"{record} is declared but absent")
            self.assertTrue((ROOT / generator).is_file(), f"{generator} is declared but absent")
            self.assertIn("--check", (ROOT / generator).read_text(encoding="utf-8"),
                          f"{generator} has no --check, so its record cannot be re-verified")

    def test_entries_the_chain_also_runs_are_checked_in_both_places_as_read_only(self) -> None:
        """`verify_contract_graph` and `verify_language_boundary` run in the authority chain too.

        That is fine -- both are read-only there and here -- but it must be a stated fact rather
        than an accident, because two runners over one record is exactly where a writer form would
        hide. So: every shared entry must appear in the chain with a read-only flag as well.
        """
        chain = (ROOT / "scripts" / "verify_authority_gates.py").read_text(encoding="utf-8")
        shared = [(record, generator, argv) for record, generator, argv in v.ENTRIES
                  if Path(generator).name in chain]
        self.assertTrue(shared, "expected the chain and this gate to overlap on at least one "
                                "record; if they no longer do, delete this test with a reason")
        for _record, _generator, argv in shared:
            self.assertIn(argv[0], v.READ_ONLY_FLAGS)
        # The chain's own entries are guarded in test_language_boundary_check_mode.py, which
        # parses that list rather than grepping it -- one guard, one shape, no duplicated rule here.

    def test_exclusions_are_named_with_a_reason_and_a_real_script(self) -> None:
        # A shrinking register: the set is named because a row may only leave by fixing the
        # check, and a new row must be a deliberate edit here as well.
        # RECOVERY-SAFETY left on 2026-10-09: its three destructive-operation receipts were
        # audited from their single tracked copy in the preserved evidence bundle, so a clean
        # checkout reaches the same verdict as this disk.
        # DEEPSEEK-FINAL-TEST-GATE left the same day: its --check judges the record against
        # versioned test files and its own rows rather than re-deriving runs from a gitignored
        # bound-test history. SPILL-CENSUS left last: it judges the record against the path rules,
        # git and its own arithmetic, and reports the live byte census as machine state.
        self.assertEqual(v.EXCLUDED, {},
                         "an exclusion came back; it must name its measured cause here and in "
                         "the gate, and the cause has to be a real machine dependency")
        for record, reason in v.EXCLUDED.items():
            self.assertTrue((ROOT / record).is_file(), record)
            self.assertGreater(len(reason), 60, f"{record}'s exclusion reason is a placeholder")
            self.assertNotIn(str(Path(record)), json.dumps([e[0] for e in v.ENTRIES]))


class FindingTests(unittest.TestCase):
    def setUp(self) -> None:
        self._entries = list(v.ENTRIES)

    def tearDown(self) -> None:
        v.ENTRIES[:] = self._entries

    def test_the_shipped_state_produces_no_finding(self) -> None:
        failures, exclusions, checked, missing = v.check()
        self.assertEqual(failures, [], "a tracked projection disagrees with its own record")
        self.assertEqual(missing, [])
        self.assertEqual((len(checked), len(exclusions)),
                         (len(v.ENTRIES) + len(v.RECEIPT_CHECKS), len(v.EXCLUDED)))

    def test_the_gate_still_reports_an_exclusion_it_is_given(self) -> None:
        """The register is empty, which must not be allowed to make its reporting untested.

        One cheap entry plus a planted exclusion: an exclusion is a declared limitation, so it
        has to surface as a NOTICE and must never be counted as a finding.
        """
        entries, excluded = list(v.ENTRIES), dict(v.EXCLUDED)
        kept = next(entry for entry in entries if entry[0] == "reports/current/CONTRACT-GRAPH.json")
        try:
            v.ENTRIES[:] = [kept]
            v.EXCLUDED.clear()
            v.EXCLUDED["reports/current/SPILL-CENSUS.json"] = "planted: not re-checkable on a clone"
            failures, exclusions, checked, missing = v.check()
            self.assertEqual(exclusions, ["reports/current/SPILL-CENSUS.json: planted: "
                                          "not re-checkable on a clone"])
            self.assertEqual(checked, [kept[0]] + [script for script, _argv in v.RECEIPT_CHECKS],
                             "the receipts table ran outside the declared order, so its results "
                             "cannot be attributed")
            self.assertEqual(failures, [], "a declared exclusion was counted as a defect")
            self.assertEqual(missing, [])
        finally:
            v.ENTRIES[:] = entries
            v.EXCLUDED.clear()
            v.EXCLUDED.update(excluded)

    def test_a_writer_entry_is_refused(self) -> None:
        v.ENTRIES[0] = (v.ENTRIES[0][0], v.ENTRIES[0][1], [])
        failures = v.check()[0]
        self.assertTrue(any("FRESHNESS-WRITER-INVOKED" in f for f in failures), failures)

    def test_a_writer_receipt_is_refused_by_the_same_rule(self) -> None:
        """The receipt table is a second loop over the same guard, so it needs its own plant."""
        original = list(v.RECEIPT_CHECKS)
        try:
            v.RECEIPT_CHECKS[:] = [(original[0][0], [])]
            failures = v.check()[0]
            self.assertTrue(any("FRESHNESS-WRITER-INVOKED" in f for f in failures), failures)
        finally:
            v.RECEIPT_CHECKS[:] = original

    def test_a_failing_receipt_is_named_with_its_own_code(self) -> None:
        """A read-only form that exits non-zero must surface as FRESHNESS-RECEIPT-DRIFT.

        The plant is a declared-looking flag the tool does not implement (--self-test on the
        migration tool), so argparse exits 2. An argv that is not a read-only flag at all is
        refused earlier, by test_a_writer_receipt_is_refused_by_the_same_rule.
        """
        original = list(v.RECEIPT_CHECKS)
        try:
            v.RECEIPT_CHECKS[:] = [("scripts/deepseek_hermes_migration.py", ["--self-test"])]
            failures = v.check()[0]
            self.assertTrue(any("FRESHNESS-RECEIPT-DRIFT" in f for f in failures), failures)
        finally:
            v.RECEIPT_CHECKS[:] = original

    def test_a_missing_record_is_convicted(self) -> None:
        v.ENTRIES[0] = ("reports/current/not-a-real-projection.json", v.ENTRIES[0][1], ["--check"])
        failures, _exclusions, _checked, missing = v.check()
        self.assertTrue(any(f.startswith("FRESHNESS-RECORD-MISSING") for f in failures), failures)
        self.assertEqual(missing, ["reports/current/not-a-real-projection.json"])

    def test_a_drifting_child_is_named_with_its_verdict_line(self) -> None:
        original = v.run_entry_read_only
        try:
            # run_entry_read_only returns (code, tail, moved, scan_error); a 3-tuple stub left these
            # two cases raising ValueError instead of exercising the assertion. The fourth value
            # is the write-DETECTOR error, and "" means the detector ran fine.
            v.run_entry_read_only = lambda generator, argv: (1, "SOMETHING=DRIFT", [], "")
            failures = v.check()[0]
        finally:
            v.run_entry_read_only = original
        self.assertTrue(any("FRESHNESS-DRIFT" in f and "SOMETHING=DRIFT" in f
                            for f in failures), failures)

    def test_a_check_that_writes_is_refused_even_when_it_passes(self) -> None:
        """A checker that rewrites its own record cannot disagree with it, so it proves nothing."""
        original = v.run_entry_read_only
        try:
            v.run_entry_read_only = lambda generator, argv: (
                0, "SOMETHING=PASS", ["reports/current/FOUNDATION-AUDIT.json"], "")
            failures = v.check()[0]
        finally:
            v.run_entry_read_only = original
        self.assertTrue(any(f.startswith("FRESHNESS-CHECK-WROTE")
                            and "FOUNDATION-AUDIT" in f for f in failures), failures)

    def test_a_record_with_an_empty_subject_still_passes_its_own_check(self) -> None:
        """Subject debt is `report-subject-debt.json`'s business; this gate must not double-voice."""
        entries = {record: generator for record, generator, _a in v.ENTRIES}
        register = json.loads((ROOT / "design-lab" / "config" / "report-subject-debt.json")
                              .read_text(encoding="utf-8"))
        declared = [row["path"] for row in register["records"] if row["path"] in entries]
        self.assertTrue(declared, "expected at least one entry whose record carries a declared "
                                  "empty subject, so this assertion means something")
        for record in declared:
            document = json.loads((ROOT / record).read_text(encoding="utf-8"))
            self.assertIn("subject_sha", document)
            self.assertEqual(document["subject_sha"], "", record)
            code, tail = v.run_entry(entries[record], ["--check"])
            self.assertEqual(code, 0, f"{record} is red because of its subject, which belongs to "
                                      f"the debt register: {tail}")


class RuntimeTests(unittest.TestCase):
    """One subprocess run, both assertions: the gate itself costs ~30s of child checks."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.porcelain_before = subprocess.run(
            ["git", "status", "--porcelain"], cwd=str(ROOT), capture_output=True, text=True,
            encoding="utf-8", errors="replace").stdout
        # Not `cls.run`: TestCase.run is the runner itself, and shadowing it turns every
        # test in the class into a TypeError on a CompletedProcess.
        cls.gate_run = subprocess.run([sys.executable, "-B", str(SCRIPT)], capture_output=True,
                                      text=True, encoding="utf-8", errors="replace",
                                      cwd=str(ROOT), timeout=1800)
        cls.porcelain_after = subprocess.run(
            ["git", "status", "--porcelain"], cwd=str(ROOT), capture_output=True, text=True,
            encoding="utf-8", errors="replace").stdout

    def test_the_gate_passes_and_prints_its_verdict_last(self) -> None:
        self.assertEqual(self.gate_run.returncode, 0,
                         (self.gate_run.stdout or "")[-1200:] + (self.gate_run.stderr or "")[-600:])
        lines = [line for line in self.gate_run.stdout.splitlines() if line.strip()]
        self.assertTrue(lines[-1].startswith("VERIFY_PROJECTION_FRESHNESS=OK"), lines[-1])
        # Derived from the gate's own tables rather than a literal: a pinned number here went
        # stale the moment an exclusion was fixed, which is the opposite of what it should catch.
        self.assertIn(f"records={len(v.ENTRIES)}", lines[-1])
        self.assertIn(f"receipts={len(v.RECEIPT_CHECKS)}", lines[-1])
        self.assertIn(f"verified={len(v.ENTRIES) + len(v.RECEIPT_CHECKS)}", lines[-1],
                      "a declared read-only form did not actually run")
        self.assertIn(f"excluded={len(v.EXCLUDED)}", lines[-1])
        self.assertLess(len(v.EXCLUDED), len(v.ENTRIES),
                        "the gate excludes as many records as it holds, so it verifies nothing")

    def test_it_writes_no_tracked_file(self) -> None:
        self.assertEqual(self.porcelain_before, self.porcelain_after,
                         "a freshness check rewrote a tracked projection")

    def test_the_gate_is_registered_in_the_aggregate(self) -> None:
        scripts = (ROOT / "design-lab" / "scripts" / "verify_design_lab.py").read_text(
            encoding="utf-8")
        self.assertIn("verify_projection_freshness.py", scripts,
                      "a gate nobody invokes is documentation")


class InventorySnapshotTests(unittest.TestCase):
    """The check that had been silently red for weeks, now asserting what a snapshot can."""

    def setUp(self) -> None:
        sys.path.insert(0, str(ROOT / "scripts"))
        import importlib
        self.module = importlib.import_module("deepseek_language_inventory")

    def record(self) -> dict:
        return json.loads((ROOT / "reports" / "current" / "LANGUAGE-INVENTORY.json")
                          .read_text(encoding="utf-8"))

    def test_the_shipped_snapshot_is_self_consistent(self) -> None:
        self.assertEqual(self.module.snapshot_findings(self.record()), [])

    def test_the_census_no_longer_has_to_match_the_live_tree(self) -> None:
        r = subprocess.run([sys.executable, "-B", str(ROOT / "scripts" /
                                                      "deepseek_language_inventory.py"),
                            "--check"], capture_output=True, text=True, encoding="utf-8",
                           errors="replace", cwd=str(ROOT), timeout=600)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("LANGUAGE_INVENTORY=NOTICE", r.stdout,
                      "the check must say how far the tree has moved, not fail because of it")

    def test_a_census_that_no_longer_adds_up_is_convicted(self) -> None:
        record = self.record()
        record["languages"][0]["file_count"] += 5
        findings = self.module.snapshot_findings(record)
        self.assertTrue(any("TOTAL-DOES-NOT-ACCOUNT" in f for f in findings), findings)

    def test_an_emptied_policy_field_is_convicted(self) -> None:
        record = self.record()
        record["policy"]["forbidden_without_adr"] = []
        self.assertTrue(any("POLICY-EMPTY" in f
                            for f in self.module.snapshot_findings(record)))

    def test_a_language_row_without_a_role_is_convicted(self) -> None:
        record = self.record()
        record["languages"][0]["runtime_role"] = " "
        self.assertTrue(any("MISSING-FIELD" in f and "runtime_role" in f
                            for f in self.module.snapshot_findings(record)))

    def test_a_line_count_disagreeing_with_its_row_is_convicted(self) -> None:
        record = self.record()
        language = record["code_languages"][0]
        record["code_nonblank_lines"][language] += 1
        self.assertTrue(any("CODE-LINES-MISMATCH" in f
                            for f in self.module.snapshot_findings(record)))

    def test_a_subject_that_names_no_commit_is_convicted(self) -> None:
        record = self.record()
        record["subject_sha"] = ""
        findings = self.module.snapshot_findings(record)
        self.assertTrue(any(f.startswith("SUBJECT-NOT-A-COMMIT") for f in findings), findings)

    def test_duplicated_and_empty_rows_are_convicted(self) -> None:
        record = self.record()
        record["languages"].append(dict(record["languages"][1]))
        findings = self.module.snapshot_findings(record)
        self.assertTrue(any("DUPLICATE-LANGUAGE-ROW" in f for f in findings), findings)


if __name__ == "__main__":
    unittest.main()
