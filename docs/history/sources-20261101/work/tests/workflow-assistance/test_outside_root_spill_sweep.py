"""Gate: the outside-root spill sweep must name what it measured, and must not flatter itself.

Three properties, in order of how they would have been lied about:

1. no machine-local absolute path may reach the tracked summary — `.project/governance/
   project-data-boundary.json` keeps those in the ignored detail report;
2. the summary must be internally consistent: its class totals must equal its hit total, and the
   verdict must follow from the counters instead of from prose ("SPILL_TO_EXPLAIN" used to be printed
   over the owner's own handover material, which made a clean-looking dirty verdict and a dirty-looking
   clean one equally unverifiable);
3. the adjudication must be able to refuse: a hit no rule matches stays UNADJUDICATED and fails the
   run, so adding a rule can never be a way to bury a finding. The rules themselves carry a `basis`
   naming the tracked record that justifies the class, and an empty basis is the lie this catches.

Discovered dynamically by `run_quality_gate.py governance`.
"""
from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "audit" / "outside_root_spill_sweep.py"
SUMMARY = ROOT / "docs" / "audits" / "OUTSIDE_ROOT_SPILL_SWEEP_2026-10-07.json"

spec = importlib.util.spec_from_file_location("orss", SCRIPT)
orss = importlib.util.module_from_spec(spec)
spec.loader.exec_module(orss)


class SweepModuleBehaviourTests(unittest.TestCase):
    def test_protected_volumes_are_refused_and_clean_paths_are_not(self) -> None:
        self.assertTrue(orss.forbidden_hit(r"E:\private\WORK-LAB"))
        self.assertTrue(orss.forbidden_hit("F:/models/x.gguf"))
        self.assertFalse(orss.forbidden_hit(r"D:\All projects\WORK-LAB\README.md"))
        self.assertFalse(orss.forbidden_hit("relative/path"))

    def test_boundaries_json_and_the_probe_list_agree_on_the_forbidden_roots(self) -> None:
        declared = set(json.loads((ROOT / ".project/governance/project-data-boundary.json")
                                  .read_text(encoding="utf-8"))["forbiddenExternalRoots"])
        self.assertTrue(declared <= set(orss.FORBIDDEN_PREFIXES),
                        "the sweep's prefix list drifted from the declared forbidden roots")
        for label, root, _why in orss.probe_roots():
            self.assertFalse(orss.forbidden_hit(root), f"{label} resolves into a forbidden volume")

    def test_an_unknown_hit_is_not_adjudicated_by_default(self) -> None:
        self.assertIsNone(orss.classify_hit("toolCache", "uv-cache", "work-lab-wheel.whl"))
        self.assertIsNone(orss.classify_hit("siblingProject", "SomeOtherProject", "WORK-LAB-note.md"))
        self.assertIsNone(orss.classify_hit("runtimeScratch", "brand-new-prefix",
                                            "WORK-LAB-AUTHORITY.md"))
        self.assertIsNone(orss.classify_hit("declaredSharedRoot", "docs", "unrelated-file.md"))

    def test_the_rules_that_exist_do_classify_their_own_shapes(self) -> None:
        self.assertEqual(orss.classify_hit("siblingProject", "Record", "02_WORK-LAB_x.docx")["cls"],
                         "inboundOwnerMaterial")
        self.assertEqual(orss.classify_hit("runtimeScratch", "auth-ref-abc123",
                                           "WORK-LAB-AUTHORITY.md")["cls"],
                         "projectAuthoredTempResidue")
        self.assertEqual(orss.classify_hit("declaredSharedRoot", "docs",
                                           "WORK-LAB-SHARED-DEPENDENCIES-2026-08-15.md")["cls"],
                         "projectAuthoredPreLedgerOriginal")

    def test_every_rule_carries_a_basis_a_disposition_and_a_stated_ownership(self) -> None:
        for r in orss.ADJUDICATION_RULES:
            self.assertGreaterEqual(len(r["basis"].strip()), 40,
                                    f"{r['rule']}: a one-line 'it is fine' is not a basis")
            self.assertTrue(r["disposition"].strip(), f"{r['rule']} states no disposition")
            self.assertIsInstance(r["projectAuthored"], (bool, type(None)),
                                  f"{r['rule']} does not say whether this project wrote it")
            self.assertIn(r["category"], {"declaredSharedRoot", "runtimeScratch", "siblingProject",
                                         "toolCache"}, f"{r['rule']} targets an unknown category")
        ids = [r["rule"] for r in orss.ADJUDICATION_RULES]
        self.assertEqual(len(ids), len(set(ids)), "duplicate adjudication rule id")

    def test_the_temp_residue_rule_declares_its_hits_as_project_authored_so_recurrence_fails(self) -> None:
        rule = orss.classify_hit("runtimeScratch", "auth-ref-zzz", "WORK-LAB-AUTHORITY.md")
        self.assertIs(rule["projectAuthored"], True)
        self.assertIs(rule["recoveredIn"], False)


class ShippedSweepRecordTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        assert SUMMARY.is_file(), f"missing {SUMMARY}"
        cls.doc = json.loads(SUMMARY.read_text(encoding="utf-8"))

    def test_the_record_publishes_no_user_profile_path_and_no_probe_root_field(self) -> None:
        """What the boundary declaration actually forbids, stated precisely.

        The record does quote `D:\\All projects\\Record` inside a rule basis: that root is named by
        tracked governance already (`blueprint-coverage.json`, register rows AG-19b/AG-20b), so the
        reference is project-level, not machine-local. What may not appear is a probe's resolved root
        (which is `%TEMP%`, `%APPDATA%` or a user profile on this box) or a user-directory path.
        """
        blob = json.dumps(self.doc, ensure_ascii=False)
        for marker in (r"C:\Users", "C:/Users", "/home/", "%APPDATA%", "%LOCALAPPDATA%",
                       "AppData"):
            self.assertNotIn(marker, blob, f"the tracked summary leaks a profile path via {marker}")
        for probe in self.doc["probes"]:
            self.assertNotIn("root", probe, "a probe published its resolved root")
            self.assertTrue(probe["probe"], "a probe row without a label")
        for hit in self.doc["hits"]:
            self.assertNotRegex(hit["under"], r"auth-ref-[A-Za-z0-9_]{6,}",
                                "a random temp directory name reached the tracked record")

    def test_class_totals_account_for_every_hit_and_the_verdict_follows_the_counters(self) -> None:
        counts = self.doc["counts"]
        self.assertEqual(sum(counts["hitsByClass"].values()), counts["hitsTotal"],
                         "the class table does not account for the hits the probes counted")
        self.assertEqual(counts["unadjudicatedHits"], counts["hitsByClass"].get("UNADJUDICATED", 0))
        verdict = self.doc["verdict"]
        if verdict == "NAMED_OUTSIDE_ROOT_ADJUDICATED_AND_RECOVERED":
            self.assertEqual(counts["unadjudicatedHits"], 0)
            self.assertEqual(counts["projectAuthoredUnrecovered"], 0)
            self.assertEqual(counts["ledgerViolations"], 0)
        else:
            self.assertTrue(counts["unadjudicatedHits"] or counts["projectAuthoredUnrecovered"]
                            or counts["ledgerViolations"] or counts["hitsTotal"] == 0,
                            f"verdict {verdict} is cleaner than the data behind it")

    def test_the_recorded_hits_are_all_present_in_the_rule_table(self) -> None:
        rules = {r["rule"] for r in self.doc["adjudicationRules"]}
        for hit in self.doc["hits"]:
            if hit["rule"] is not None:
                self.assertIn(hit["rule"], rules, "a hit cites a rule the record does not publish")
        self.assertEqual(len(rules), len(orss.ADJUDICATION_RULES),
                         "the shipped record publishes a different rule set than the tool")

    def test_the_record_is_not_vacuous_on_the_machine_that_ran_it(self) -> None:
        self.assertGreaterEqual(self.doc["counts"]["probes"], 10)
        self.assertGreaterEqual(self.doc["counts"]["probesPresent"], 5,
                                "a sweep that found no root at all is not a clean sweep")
        self.assertTrue(self.doc["scopeStatement"].strip())
        self.assertTrue(self.doc["disclosure"].strip())

    def test_the_authority_residue_found_by_the_sweep_is_the_one_the_release_tool_removed(self) -> None:
        """The class the release tool exists for must not be back on this machine."""
        import glob
        import os
        import tempfile
        left = glob.glob(os.path.join(tempfile.gettempdir(), "auth-ref-*"))
        recorded = self.doc["counts"]["hitsByClass"].get("projectAuthoredTempResidue", 0)
        self.assertEqual(len(left), recorded,
                         f"{len(left)} auth-ref-* dirs in %TEMP% but the record says {recorded}; "
                         "re-run scripts/audit/outside_root_spill_sweep.py, then release the "
                         "residue with scripts/maintenance/release_authority_reference_temp_residue.py")


if __name__ == "__main__":
    unittest.main()
