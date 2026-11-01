# SPDX-License-Identifier: MIT
"""Unit tests for DL-EVD-001 / DL-REL-001 helper tools:
- update_evidence_binding.py (boundTree freshness/ancestry logic)
- score_artifact.py (weighted scoring + ACCEPT/REVISE/REJECT)
- verify_sbom.py (SPDX integrity + vendored coverage)
"""
from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"


def load(name: str):
    path = SCRIPTS / name
    spec = importlib.util.spec_from_file_location(name.replace(".py", ""), path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class UpdateEvidenceBindingTests(unittest.TestCase):
    """DL-EVD-003: state machine CURRENT_EXACT / HISTORICAL_VALID / STALE / UNRESOLVABLE.

    Only CURRENT_EXACT supports the current release; a committed index must
    never self-claim the current tree (DL-EVD-002); ancestor bindings are
    HISTORICAL_VALID with requiresRequalification=true.
    """

    def setUp(self):
        self.m = load("update_evidence_binding.py")
        self.head = self.m.git_head()
        self.assertTrue(self.head, "git HEAD must resolve")
        self.head_tree = self.m.git_tree(self.head)
        self.assertTrue(self.head_tree, "git HEAD tree must resolve")

    def test_current_exact_is_distinct_from_ancestor(self):
        self.assertEqual(self.m.compute_state(self.head_tree, self.head, self.head_tree), "CURRENT_EXACT")
        parent = self.m.git(["rev-parse", self.head + "^"])
        if parent:
            parent_tree = self.m.git_tree(parent)
            self.assertEqual(self.m.compute_state(parent_tree, self.head, self.head_tree), "HISTORICAL_VALID")

    def test_foreign_sha_is_stale(self):
        self.assertEqual(self.m.compute_state("0" * 40, self.head, self.head_tree), "STALE")

    def test_malformed_is_unresolvable(self):
        self.assertEqual(self.m.compute_state("abc", self.head, self.head_tree), "UNRESOLVABLE")
        self.assertEqual(self.m.compute_state("", self.head, self.head_tree), "UNRESOLVABLE")

    def test_committed_index_must_not_self_claim_current_tree(self):
        state, msg = self.m.check()
        # the committed lastVerifiedTree must never be CURRENT_EXACT
        self.assertNotEqual(state, "CURRENT_EXACT", msg)





class CapabilityEvidenceConsistencyTests(unittest.TestCase):
    def test_record_cannot_exceed_current_capability_evidence(self):
        m = load("verify_capability_evidence_v4.py")
        record = {
            "capability_id": "visual-quality",
            "evidence_level": "E3",
            "tree_sha": "0" * 40,
            "artifacts": ["runtime_id", "task_id", "artifact_provenance"],
        }
        errors = m.validate_record(record, {"visual-quality": "E1"})
        self.assertTrue(any("exceeds capability actualEvidence" in error for error in errors))

    def test_invalid_evidence_level_fails_closed_without_traceback(self):
        m = load("verify_capability_evidence_v4.py")
        record = {
            "capability_id": "visual-quality",
            "evidence_level": "E9",
            "artifacts": ["declaration_doc"],
        }
        errors = m.validate_record(record, {"visual-quality": "E1"})
        self.assertTrue(any("invalid evidence_level" in error for error in errors))


class ScoreArtifactTests(unittest.TestCase):
    RUBRIC = ROOT / "evals" / "rubrics" / "3d.rubric.json"

    def _sheet(self, scores: dict) -> Path:
        fd, name = tempfile.mkstemp(suffix=".json")
        with open(fd, "w", encoding="utf-8") as f:
            json.dump({"artifact": "test/x.blend", "reviewer": "tester", "scores": scores}, f)
        return Path(name)

    def test_accept(self):
        m = load("score_artifact.py")
        rubric = json.loads(self.RUBRIC.read_text(encoding="utf-8"))
        scores = {ax["id"]: 9.0 for ax in rubric["axes"]}
        sheet = self._sheet(scores)
        try:
            result, code = m.score(self.RUBRIC, sheet)
            self.assertEqual(code, 0)
            self.assertEqual(result["verdict"], "ACCEPT")
            self.assertEqual(result["weighted_score"], 9.0)
        finally:
            sheet.unlink(missing_ok=True)

    def test_reject(self):
        m = load("score_artifact.py")
        rubric = json.loads(self.RUBRIC.read_text(encoding="utf-8"))
        scores = {ax["id"]: 5.0 for ax in rubric["axes"]}
        sheet = self._sheet(scores)
        try:
            result, code = m.score(self.RUBRIC, sheet)
            self.assertEqual(code, 0)
            self.assertEqual(result["verdict"], "REJECT")
        finally:
            sheet.unlink(missing_ok=True)

    def test_missing_axis_fails_closed(self):
        m = load("score_artifact.py")
        rubric = json.loads(self.RUBRIC.read_text(encoding="utf-8"))
        scores = {ax["id"]: 9.0 for ax in rubric["axes"][:5]}
        sheet = self._sheet(scores)
        try:
            result, code = m.score(self.RUBRIC, sheet)
            self.assertEqual(code, 1)
            self.assertIn("missing", result.get("error", ""))
        finally:
            sheet.unlink(missing_ok=True)

    def test_out_of_range_fails_closed(self):
        m = load("score_artifact.py")
        rubric = json.loads(self.RUBRIC.read_text(encoding="utf-8"))
        scores = {ax["id"]: 11.0 for ax in rubric["axes"]}
        sheet = self._sheet(scores)
        try:
            result, code = m.score(self.RUBRIC, sheet)
            self.assertEqual(code, 1)
            self.assertIn("out of range", result.get("error", ""))
        finally:
            sheet.unlink(missing_ok=True)


class VerifySbomTests(unittest.TestCase):
    def test_sbom_valid(self):
        m = load("verify_sbom.py")
        findings = m.check()
        self.assertEqual(findings, [], f"expected SBOM OK: {findings}")


if __name__ == "__main__":
    unittest.main()
