# SPDX-License-Identifier: MIT
"""Batch F-1: the release gate compares *effective* capability evidence.

P1-B (DL-EVD-002/003) split the recorded evidence level -- a historical
observation bound to the tree that produced it -- from the effective level a
capability may claim on the current tree. The release gate must compare the
effective level, so a capability that keeps a runtime recording from another
tree (requiresRequalification, or a subject SHA other than HEAD) can no longer
satisfy ``minimumRequiredEvidence`` on this checkout.

Covers:
- a requalified capability (recorded E3, floor E3) is reported as below the
  floor with actual=effective=E1, plus the distinguishable
  EVIDENCE-REQUALIFICATION-REQUIRED line;
- a clean capability (at/above its floor, no requalification, subject SHA ==
  current) produces no finding -- the gate must not over-block;
- unknown or missing levels stay fail-closed (a finding, never a pass);
- the committed index and the real script both behave this way end to end.

Stdlib only; runnable directly:

    python design-lab/tests/test_release_gate_effective.py
"""
from __future__ import annotations

import importlib.util
import json
import re
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[2]
SCRIPTS = REPO / "design-lab" / "scripts"
INDEX = REPO / "design-lab" / "config" / "capability-evidence-index.json"
RUNTIME = Path(__file__).resolve().parents[1] / ".project-local" / "task-runtime"
# Deterministic stand-in for "the current tree SHA": no capability in the
# committed index binds it, so it only exercises the comparison logic.
CURRENT_SHA = "1" * 40
FOREIGN_SHA = "2" * 40


def load(name: str):
    path = SCRIPTS / name
    spec = importlib.util.spec_from_file_location(name.replace(".py", ""), path)
    assert spec and spec.loader, f"cannot load {path}"
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ReleaseGateEffectiveEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.gate = load("verify_release_gate.py")
        self.effective = self.gate.load_effective_evidence_module()

    def findings(self, *capabilities) -> list[str]:
        """Run the gate's floor check over a synthetic index."""
        RUNTIME.mkdir(parents=True, exist_ok=True)
        path = RUNTIME / "f1-capability-evidence-index.json"
        path.write_text(json.dumps({"capabilities": list(capabilities)}), encoding="utf-8")
        try:
            return self.gate.capability_floor_findings(path, CURRENT_SHA, self.effective)
        finally:
            path.unlink()

    # --- the F-1 fix: the floor is measured against the effective level -----

    def test_requalified_capability_is_below_floor_by_effective_level(self):
        findings = self.findings(
            {
                "id": "creative-toolchain",
                "minimumRequiredEvidence": "E3",
                "actualEvidence": "E3",
                "requiresRequalification": True,
            }
        )
        self.assertEqual(
            sorted(findings),
            sorted(
                [
                    "EVIDENCE-BELOW-MINIMUM creative-toolchain actual=E1 minimum=E3 "
                    "recorded=E3 effective=E1",
                    "EVIDENCE-REQUALIFICATION-REQUIRED creative-toolchain "
                    "recorded=E3 effective=E1",
                ]
            ),
        )

    def test_requalified_capability_that_still_meets_its_floor_is_not_flagged(self):
        # style-master-method shape: recorded E1 against an E1 floor. Nothing was
        # downgraded (no runtime level was ever claimed), so the structural floor
        # is met and the gate must not over-block it.
        self.assertEqual(
            self.findings(
                {
                    "id": "style-master-method",
                    "minimumRequiredEvidence": "E1",
                    "actualEvidence": "E1",
                    "requiresRequalification": True,
                }
            ),
            [],
        )

    def test_clean_capability_produces_no_finding(self):
        self.assertEqual(
            self.findings(
                {
                    "id": "release-evidence",
                    "minimumRequiredEvidence": "E1",
                    "actualEvidence": "E1",
                    "subjectSha": CURRENT_SHA,
                }
            ),
            [],
        )
        self.assertEqual(
            self.findings(
                {"id": "research-evidence", "minimumRequiredEvidence": "E1", "actualEvidence": "E2"}
            ),
            [],
        )

    def test_foreign_subject_sha_is_downgraded_to_structural_and_flagged(self):
        findings = self.findings(
            {
                "id": "stale-runtime",
                "minimumRequiredEvidence": "E3",
                "actualEvidence": "E3",
                "subjectSha": FOREIGN_SHA,
            }
        )
        self.assertEqual(
            sorted(findings),
            sorted(
                [
                    "EVIDENCE-BELOW-MINIMUM stale-runtime actual=E1 minimum=E3 "
                    "recorded=E3 effective=E1",
                    "EVIDENCE-REQUALIFICATION-REQUIRED stale-runtime recorded=E3 effective=E1",
                ]
            ),
        )

    def test_requalified_capability_without_structural_pass_falls_to_e0(self):
        findings = self.findings(
            {
                "id": "no-structural",
                "minimumRequiredEvidence": "E1",
                "actualEvidence": "E0",
                "requiresRequalification": True,
            }
        )
        # recorded E0 == effective E0: no downgrade to report, but the E1 floor
        # is still missed on this tree.
        self.assertEqual(
            findings,
            ["EVIDENCE-BELOW-MINIMUM no-structural actual=E0 minimum=E1 recorded=E0 effective=E0"],
        )

    def test_below_minimum_line_carries_recorded_and_effective(self):
        # recorded == effective here; both are still named so a reader can tell
        # "never reached the floor" from "stale runtime recording".
        self.assertEqual(
            self.findings(
                {"id": "design-intelligence", "minimumRequiredEvidence": "E2", "actualEvidence": "E1"}
            ),
            [
                "EVIDENCE-BELOW-MINIMUM design-intelligence actual=E1 minimum=E2 "
                "recorded=E1 effective=E1"
            ],
        )

    def test_silently_stale_claim_is_still_a_hard_finding(self):
        # No requiresRequalification marker, but the subject SHA is foreign: the
        # effective level drops anyway, and the floor finding uses it.
        findings = self.findings(
            {
                "id": "silent-stale",
                "minimumRequiredEvidence": "E4",
                "actualEvidence": "E4",
                "subjectSha": FOREIGN_SHA,
            }
        )
        self.assertIn(
            "EVIDENCE-BELOW-MINIMUM silent-stale actual=E1 minimum=E4 recorded=E4 effective=E1",
            findings,
        )

    # --- fail-closed -------------------------------------------------------

    def test_unknown_floor_fails_closed(self):
        self.assertEqual(
            self.findings({"id": "x", "minimumRequiredEvidence": "E9", "actualEvidence": "E1"}),
            ["CAPABILITY-EVIDENCE-INVALID x minimum='E9' actual='E1'"],
        )

    def test_missing_recorded_level_fails_closed(self):
        self.assertEqual(
            self.findings({"id": "y", "minimumRequiredEvidence": "E1"}),
            ["CAPABILITY-EVIDENCE-INVALID y minimum='E1' actual=None"],
        )

    def test_missing_index_fails_closed(self):
        findings = self.gate.capability_floor_findings(
            RUNTIME / "f1-does-not-exist.json", CURRENT_SHA, self.effective
        )
        self.assertTrue(findings[0].startswith("CAPABILITY-EVIDENCE-INDEX-UNREADABLE"), findings)

    def test_capabilities_not_a_list_fails_closed(self):
        RUNTIME.mkdir(parents=True, exist_ok=True)
        path = RUNTIME / "f1-invalid-shape.json"
        path.write_text('{"capabilities": "nope"}', encoding="utf-8")
        try:
            self.assertEqual(
                self.gate.capability_floor_findings(path, CURRENT_SHA, self.effective),
                ["CAPABILITY-EVIDENCE-INDEX-INVALID (capabilities must be a list)"],
            )
        finally:
            path.unlink()

    def test_unavailable_effective_module_blocks_instead_of_falling_back(self):
        responses = iter([(0, ""), (0, CURRENT_SHA), (0, CURRENT_SHA)])
        with patch.object(self.gate, "git", side_effect=lambda *args: next(responses)):
            with patch.object(
                self.gate, "load_effective_evidence_module", side_effect=ImportError("no module")
            ):
                findings = self.gate.check()
        self.assertTrue(
            any(item.startswith("EFFECTIVE-EVIDENCE-MODULE-UNAVAILABLE") for item in findings),
            findings,
        )


class CommittedIndexEffectiveEvidenceTests(unittest.TestCase):
    """The real index and the real script, not just the helper."""

    def setUp(self):
        self.gate = load("verify_release_gate.py")

    def test_committed_index_reports_creative_toolchain_by_effective_level(self):
        findings = self.gate.capability_floor_findings(
            INDEX, CURRENT_SHA, self.gate.load_effective_evidence_module()
        )
        self.assertIn(
            "EVIDENCE-BELOW-MINIMUM creative-toolchain actual=E1 minimum=E3 "
            "recorded=E3 effective=E1",
            findings,
        )
        self.assertIn(
            "EVIDENCE-REQUALIFICATION-REQUIRED creative-toolchain recorded=E3 effective=E1",
            findings,
        )

    def test_recorded_only_comparison_would_have_missed_it(self):
        """Regression guard for the bug F-1 fixes: on the committed index the
        recorded level (E3) already met the E3 floor, so a recorded-based gate
        reported nothing for creative-toolchain."""
        data = json.loads(INDEX.read_text(encoding="utf-8"))
        capability = next(c for c in data["capabilities"] if c.get("id") == "creative-toolchain")
        recorded = capability["actualEvidence"]
        floor = capability["minimumRequiredEvidence"]
        self.assertGreaterEqual(self.gate.LEVEL_ORDER[recorded], self.gate.LEVEL_ORDER[floor])
        self.assertIn(
            "EVIDENCE-BELOW-MINIMUM creative-toolchain actual=E1 minimum=E3 recorded=E3 effective=E1",
            self.gate.capability_floor_findings(
                INDEX, CURRENT_SHA, self.gate.load_effective_evidence_module()
            ),
        )

    def test_script_output_contract_and_effective_lines(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPTS / "verify_release_gate.py")],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=REPO,
        )
        out = result.stdout
        self.assertIn(
            "EVIDENCE-BELOW-MINIMUM creative-toolchain actual=E1 minimum=E3 "
            "recorded=E3 effective=E1",
            out,
        )
        self.assertIn(
            "EVIDENCE-REQUALIFICATION-REQUIRED creative-toolchain recorded=E3 effective=E1", out
        )
        tail = re.search(r"RELEASE_GATE=(\w+)(?: findings=(\d+))?", out)
        self.assertIsNotNone(tail, out)
        verdict, count = tail.group(1), tail.group(2)
        if verdict == "BLOCKED":
            self.assertEqual(result.returncode, 1, out)
            self.assertIsNotNone(count, out)
            self.assertGreaterEqual(int(count), 2)
        else:
            self.assertEqual(verdict, "READY", out)
            self.assertEqual(result.returncode, 0, out)


if __name__ == "__main__":
    unittest.main(verbosity=2)
