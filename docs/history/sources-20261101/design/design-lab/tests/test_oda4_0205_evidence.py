# SPDX-License-Identifier: MIT
"""ODA4-0205: capability evidence promotion + provenance roundtrip tests."""
from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "design-lab" / "scripts" / "verify_capability_evidence_v4.py"


def load_mod():
    spec = importlib.util.spec_from_file_location("vce4", SCRIPT)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


class CapabilityEvidenceV4Test(unittest.TestCase):
    def test_e2_needs_readback_artifact(self):
        mod = load_mod()
        rec = {"capability_id": "c1", "evidence_level": "E2", "artifacts": ["command_output"]}
        errs = mod.validate_record(rec)
        self.assertTrue(any("readback_artifact" in e for e in errs), f"errs: {errs}")

    def test_e2_with_readback_passes(self):
        mod = load_mod()
        rec = {"capability_id": "c1", "evidence_level": "E2", "artifacts": ["declaration_doc", "command_output", "readback_artifact"]}
        self.assertEqual(mod.validate_record(rec), [])

    def test_e3_requires_exact_tree(self):
        mod = load_mod()
        rec = {"capability_id": "c2", "evidence_level": "E3",
               "artifacts": ["runtime_id", "task_id", "artifact_provenance"]}
        errs = mod.validate_record(rec)
        self.assertTrue(any("exact tree_sha" in e for e in errs))

    def test_e3_static_only_rejected(self):
        mod = load_mod()
        rec = {"capability_id": "c3", "evidence_level": "E3",
               "tree_sha": "a" * 40,
               "artifacts": ["schema.json", "manifest.json"]}
        errs = mod.validate_record(rec)
        self.assertTrue(any("static files only" in e for e in errs), f"errs: {errs}")

    def test_e3_with_live_evidence_passes(self):
        mod = load_mod()
        rec = {"capability_id": "c4", "evidence_level": "E3",
               "tree_sha": "a" * 40,
               "artifacts": [
                   "declaration_doc", "command_output", "readback_artifact",
                   "runtime_id", "task_id", "artifact_provenance",
               ]}
        self.assertEqual(mod.validate_record(rec), [])

    def test_e4_requires_frozen_tree_and_review(self):
        mod = load_mod()
        rec = {"capability_id": "c5", "evidence_level": "E4",
               "tree_sha": "b" * 40,
               "artifacts": [
                   "declaration_doc", "command_output", "readback_artifact",
                   "runtime_id", "task_id", "artifact_provenance",
                   "frozen_tree", "exact_sha_ci",
               ]}  # missing independent_review
        errs = mod.validate_record(rec)
        self.assertTrue(any("independent_review" in e for e in errs), f"errs: {errs}")

    def test_illegal_skip_e1_to_e3_rejected(self):
        # E3 always requires the full artifact chain; a record claiming E3 without
        # E2's readback is structurally impossible because readback is not in artifacts.
        mod = load_mod()
        rec = {"capability_id": "c6", "evidence_level": "E3",
               "tree_sha": "c" * 40,
               "artifacts": ["declaration_doc", "runtime_id", "task_id", "artifact_provenance"]}
        errs = mod.validate_record(rec)
        self.assertTrue(any("readback_artifact" in e for e in errs), f"errs: {errs}")
        levels = [f for f, t, _ in mod.PROMOTION]
        self.assertEqual(levels, ["E0", "E1", "E2", "E3", "E4"])

    def test_e5_requires_the_complete_same_capability_chain(self):
        mod = load_mod()
        rec = {
            "capability_id": "c7",
            "evidence_level": "E5",
            "tree_sha": "d" * 40,
            "artifacts": ["external_acceptance"],
        }
        errs = mod.validate_record(rec)
        self.assertTrue(any("declaration_doc" in e for e in errs), f"errs: {errs}")
        self.assertTrue(any("exact_sha_ci" in e for e in errs), f"errs: {errs}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
