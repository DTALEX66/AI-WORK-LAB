# SPDX-License-Identifier: MIT
"""A spill census is a claim about paths and rules; only its byte sums are about one disk.

Measured 2026-10-09 in two trees of `d6ba107f`: `deepseek_spill_census.py --check` compared
`repository_totals_bytes` against a sum over `.hermes` children. In the tree that generated the
record it matched (`{"UNKNOWN": 13638}`), and in a clean checkout of the same commit `.hermes/` is
absent, so the sum came back `{}` and the committed record printed `SPILL_CENSUS=DRIFT`. The same
comparison was blind in the other direction too: three of the agent-home entry counts the record
carries were already stale in the tree that wrote it (`.codex` 83 recorded against 91 live, `.dsh`
0 against 9, `.hermes` 3 against 0) and PASS said nothing about any of them, because totals were
the only field it looked at.

So the check now judges the record against the rules that produced it and against git -- the parts
that are true in every checkout -- and reports this disk's census as machine state.
"""
from __future__ import annotations

import copy
import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RECORD_REL = "reports/current/SPILL-CENSUS.json"
sys.path.insert(0, str(ROOT / "scripts"))

import deepseek_spill_census as census  # noqa: E402


def base_record() -> dict:
    """A record with one owned legacy object and one unproven agent file, both rule-correct."""
    owned_source = ".hermes/task-runtime/reconstruction"
    kind, reason = census.classify(owned_source)
    return {
        "schemaVersion": "design-lab/spill-census/v1",
        "scope": {
            "inspected": ["DESIGN-LAB repository"],
            "not_read": ["private chat content"],
            "never_touched": ["E:\\"],
        },
        "repository_legacy_objects": [
            {"owner": "DESIGN-LAB", "classification": kind, "reason": reason, "empty": False,
             "source_path": owned_source,
             "target_path": ".project-local/archive/hermes-legacy/runtime/reconstruction",
             "files": 3, "bytes": 1024, "digest": "sha256:" + "0" * 64, "recreatable": False,
             "delete_policy": census.implied_policy(kind, False)},
            {"owner": "UNPROVEN", "classification": "UNKNOWN",
             "reason": "not provably written by DESIGN-LAB; an agent-native artifact must not be "
                       "moved or deleted by this project",
             "empty": False, "source_path": ".hermes/skill-call-index.json", "target_path": None,
             "files": 1, "bytes": 512, "digest": None, "recreatable": False,
             "delete_policy": "DO_NOT_TOUCH"},
        ],
        "repository_totals_bytes": {kind: 1024, "UNKNOWN": 512},
        "repository_total_mib": round(1536 / 1048576, 2),
        "agent_homes": {".codex": {"path": "HOME/.codex", "exists": True, "product": "Codex",
                                   "content_read": False, "native_entries_seen": 91,
                                   "design_lab_owned": [],
                                   "scope_note": "native sessions unread"}},
        "verdict": "CENSUS_COMPLETE",
    }


class ControlsTests(unittest.TestCase):
    def test_a_rule_correct_record_produces_no_finding(self) -> None:
        self.assertEqual(census.record_findings(base_record()), [])

    def test_the_path_rules_are_still_the_ones_the_shipped_record_used(self) -> None:
        # An independent statement of the rule: if classify() changes, this test says so rather
        # than letting the gate quietly agree with whatever the new rule produces.
        self.assertEqual(census.classify(".hermes/task-runtime/reconstruction"),
                         ("RUNTIME_STATE", "runtime working data written by a DESIGN-LAB run"))
        self.assertEqual(census.classify(".hermes/task-artifacts/evidence"),
                         ("EVIDENCE", "evidence output written by a DESIGN-LAB run"))
        self.assertEqual(census.implied_policy("RUNTIME_STATE", False), "AUTO_WITH_MANIFEST")
        self.assertEqual(census.implied_policy("UNKNOWN", False), "OWNER_DELETE_APPROVAL_REQUIRED")
        self.assertEqual(census.implied_policy("CACHE", True), "REMOVE_EMPTY_LEGACY_DIRECTORY")

    def test_the_shipped_record_supports_itself(self) -> None:
        document = json.loads((ROOT / RECORD_REL).read_text(encoding="utf-8"))
        self.assertEqual(census.record_findings(document), [],
                         "the committed census disagrees with its own rules")


class PlantedRuleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.base = base_record()

    def codes(self, document: dict) -> list[str]:
        return census.record_findings(document)

    def find(self, document: dict, code: str) -> list[str]:
        return [line for line in self.codes(document) if line.startswith(code)]

    def test_a_misclassified_object_is_convicted(self) -> None:
        document = copy.deepcopy(self.base)
        document["repository_legacy_objects"][0]["classification"] = "EVIDENCE"
        self.assertTrue(self.find(document, "SPILL-RULE-CLASSIFICATION"))
        self.assertTrue(self.find(document, "SPILL-TOTALS-ARITHMETIC"),
                        "changing a classification without the totals must not go unnoticed")

    def test_a_reason_that_the_rule_never_wrote_is_convicted(self) -> None:
        document = copy.deepcopy(self.base)
        document["repository_legacy_objects"][0]["reason"] = "looks like cache to me"
        self.assertTrue(self.find(document, "SPILL-RULE-REASON"))

    def test_a_delete_policy_that_contradicts_the_rule_is_convicted(self) -> None:
        document = copy.deepcopy(self.base)
        document["repository_legacy_objects"][0]["delete_policy"] = "OWNER_DELETE_APPROVAL_REQUIRED"
        self.assertTrue(self.find(document, "SPILL-RULE-POLICY"))

    def test_a_recreatable_claim_that_the_rule_does_not_support_is_convicted(self) -> None:
        document = copy.deepcopy(self.base)
        document["repository_legacy_objects"][0]["recreatable"] = True
        self.assertTrue(self.find(document, "SPILL-RULE-RECREATABLE"))

    def test_a_repository_object_without_a_digest_is_convicted(self) -> None:
        document = copy.deepcopy(self.base)
        document["repository_legacy_objects"][0]["digest"] = None
        self.assertTrue(self.find(document, "SPILL-RULE-DIGEST"))

    def test_totals_that_do_not_add_up_are_convicted(self) -> None:
        document = copy.deepcopy(self.base)
        document["repository_totals_bytes"]["RUNTIME_STATE"] = 9999
        self.assertTrue(self.find(document, "SPILL-TOTALS-ARITHMETIC"))

    def test_the_mib_figure_is_checked_too(self) -> None:
        document = copy.deepcopy(self.base)
        document["repository_total_mib"] = 1.5
        self.assertTrue(self.find(document, "SPILL-TOTALS-MIB"))

    def test_two_objects_claiming_one_archive_target_are_convicted(self) -> None:
        document = copy.deepcopy(self.base)
        second = copy.deepcopy(document["repository_legacy_objects"][0])
        second["source_path"] = ".hermes/task-runtime/reconstruction-alt"
        second["reason"] = census.classify(second["source_path"])[1]
        document["repository_legacy_objects"].append(second)
        document["repository_totals_bytes"]["RUNTIME_STATE"] = 2048
        document["repository_total_mib"] = round(2560 / 1048576, 2)
        self.assertTrue(self.find(document, "SPILL-TARGET-COLLISION"))

    def test_an_object_that_git_versions_is_not_spill(self) -> None:
        document = copy.deepcopy(self.base)
        owned = document["repository_legacy_objects"][0]
        owned["source_path"] = "AGENTS.md"
        kind, reason = census.classify("AGENTS.md")
        owned["classification"], owned["reason"] = kind, reason
        owned["delete_policy"] = census.implied_policy(kind, False)
        owned["target_path"] = ".project-local/archive/hermes-legacy/runtime/AGENTS.md"
        findings = self.codes(document)
        self.assertTrue(any(line.startswith("SPILL-PREMISE-BROKEN") for line in findings), findings)

    def test_an_unproven_object_cannot_be_proposed_for_touch(self) -> None:
        for field, value, code in (
                ("delete_policy", "AUTO_WITH_MANIFEST", "SPILL-UNPROVEN-TOUCHABLE"),
                ("target_path", ".project-local/archive/hermes-legacy/x", "SPILL-UNPROVEN-TARGET"),
                ("source_path", ".openhuman/state", "SPILL-UNPROVEN-SCOPE"),
                ("recreatable", True, "SPILL-UNPROVEN-RECREATABLE")):
            document = copy.deepcopy(self.base)
            document["repository_legacy_objects"][1][field] = value
            self.assertTrue(self.find(document, code), (field, value, code))


class PrivacyAndScopeTests(unittest.TestCase):
    def test_content_read_is_never_allowed(self) -> None:
        document = base_record()
        document["agent_homes"][".codex"]["content_read"] = True
        self.assertTrue(any(line.startswith("SPILL-PRIVACY")
                            for line in census.record_findings(document)))

    def test_a_home_without_a_scope_note_is_convicted(self) -> None:
        document = base_record()
        document["agent_homes"][".codex"]["scope_note"] = ""
        self.assertTrue(any(line.startswith("SPILL-PRIVACY")
                            for line in census.record_findings(document)))

    def test_the_record_must_still_declare_the_roots_it_refuses_to_read(self) -> None:
        document = base_record()
        document["scope"]["never_touched"] = []
        self.assertTrue(any(line.startswith("SPILL-SCOPE-E-DRIVE")
                            for line in census.record_findings(document)))
        document = base_record()
        document["scope"]["not_read"] = []
        self.assertTrue(any(line.startswith("SPILL-SCOPE-NOT-READ")
                            for line in census.record_findings(document)))

    def test_no_agent_homes_at_all_is_not_a_census(self) -> None:
        document = base_record()
        document["agent_homes"] = {}
        self.assertTrue(any(line.startswith("SPILL-SCOPE-HOMES")
                            for line in census.record_findings(document)))

    def test_a_changed_verdict_is_named(self) -> None:
        document = base_record()
        document["verdict"] = "CENSUS_PROBABLY_COMPLETE"
        self.assertTrue(any(line.startswith("SPILL-VERDICT")
                            for line in census.record_findings(document)))


class MachineStateTests(unittest.TestCase):
    def test_the_judgement_never_walks_the_disk(self) -> None:
        """The point of the rewrite: a clean checkout must reach the same verdict.

        Patching the census walker to explode proves `record_findings` never calls it.
        """
        real = census.repo_legacy_census
        try:
            def boom() -> list:
                raise AssertionError("the record judgement must not depend on this disk")

            census.repo_legacy_census = boom
            self.assertEqual(census.record_findings(base_record()), [])
            document = json.loads((ROOT / RECORD_REL).read_text(encoding="utf-8"))
            self.assertEqual(census.record_findings(document), [])
        finally:
            census.repo_legacy_census = real

    def test_the_live_census_is_reported_in_named_states_only(self) -> None:
        document = json.loads((ROOT / RECORD_REL).read_text(encoding="utf-8"))
        self.assertIn(census.local_state(document),
                      {"MATCHES_RECORDED_TOTALS", "DIFFERS_FROM_RECORDED_TOTALS",
                       "NOTHING_ON_THIS_MACHINE"})
        tampered = copy.deepcopy(document)
        tampered["repository_totals_bytes"] = {"UNKNOWN": 1}
        if (census.REPO / ".hermes").is_dir():
            self.assertEqual(census.local_state(tampered), "DIFFERS_FROM_RECORDED_TOTALS")

    def test_a_tree_without_the_legacy_root_says_so_instead_of_disagreeing(self) -> None:
        real = census.REPO
        try:
            census.REPO = ROOT / ".project-local" / "task-runtime" / "no-such-tree"
            self.assertEqual(census.local_state(base_record()), "NOTHING_ON_THIS_MACHINE")
        finally:
            census.REPO = real


class RuntimeTests(unittest.TestCase):
    def test_the_check_passes_reports_machine_state_and_writes_nothing(self) -> None:
        def porcelain() -> str:
            return subprocess.run(["git", "status", "--porcelain"], cwd=str(ROOT),
                                  capture_output=True, text=True, encoding="utf-8",
                                  errors="replace").stdout

        before = porcelain()
        result = subprocess.run([sys.executable, "-X", "utf8", "-B",
                                 str(ROOT / "scripts" / "deepseek_spill_census.py"), "--check"],
                                cwd=str(ROOT), capture_output=True, text=True,
                                encoding="utf-8", errors="replace", timeout=900)
        output = (result.stdout or "") + (result.stderr or "")
        self.assertEqual(result.returncode, 0, output[-900:])
        self.assertIn("SPILL_CENSUS=PASS", output)
        self.assertIn("local_state=", output,
                      "the disk facts must be said out loud, not used to decide")
        self.assertNotIn("DRIFT", output,
                         "the word DRIFT must not survive where nothing can be compared")
        self.assertEqual(before, porcelain(), "the read-only form wrote a tracked file")


if __name__ == "__main__":
    unittest.main()
