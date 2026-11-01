# SPDX-License-Identifier: MIT
"""Topology, lineage, and hash contracts for reconstruction golden fixtures."""
from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "design-lab"))
sys.path.insert(0, str(PROJECT_ROOT / "packages" / "capabilities"))

from reconstruction.golden_corpus import load_corpus  # noqa: E402


CORPUS = PROJECT_ROOT / "design-lab" / "evals" / "reconstruction" / "golden-corpus.json"


class ReconstructionGoldenCorpusTests(unittest.TestCase):
    def test_exactly_six_required_profiles_exist(self) -> None:
        corpus = load_corpus(CORPUS)

        self.assertEqual(
            {case.kind for case in corpus.cases},
            {"logo", "ui", "poster", "flat-illustration", "complex-illustration", "mixed-media"},
        )
        self.assertEqual(len(corpus.cases), 6)

    def test_reference_cannot_be_registered_as_output_layer(self) -> None:
        for case in load_corpus(CORPUS).cases:
            self.assertNotIn(case.reference_sha256, case.allowed_output_asset_hashes)

    def test_references_are_rights_cleared_and_match_frozen_hashes(self) -> None:
        corpus = load_corpus(CORPUS)
        for case in corpus.cases:
            self.assertEqual(case.rights_status, "cleared")
            self.assertEqual(case.reference_sha256, case.actual_reference_sha256)

    def test_standalone_verifier_reports_six_cases(self) -> None:
        script = PROJECT_ROOT / "design-lab" / "scripts" / "verify_reconstruction_golden_corpus.py"
        result = subprocess.run([sys.executable, str(script)], check=False, capture_output=True, text=True, encoding="utf-8", errors="replace")

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("RECONSTRUCTION_GOLDEN=PASS cases=6", result.stdout)


if __name__ == "__main__":
    unittest.main()
