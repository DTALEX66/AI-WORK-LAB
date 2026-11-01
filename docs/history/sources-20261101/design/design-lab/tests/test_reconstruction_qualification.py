# SPDX-License-Identifier: MIT
"""Qualification aggregation contracts for repeated reconstruction runs."""
from __future__ import annotations

import sys
import json
import subprocess
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "design-lab"))
sys.path.insert(0, str(PROJECT_ROOT / "packages" / "capabilities"))


class ReconstructionQualificationTests(unittest.TestCase):
    def test_two_successes_do_not_qualify(self) -> None:
        from reconstruction.qualification import QualificationRun, aggregate

        run = QualificationRun("PASS", "a" * 64, "b" * 64, ())

        self.assertEqual(aggregate((run, run)).status, "PARTIAL")

    def test_three_identical_clean_runs_qualify_but_residue_does_not(self) -> None:
        from reconstruction.qualification import QualificationRun, aggregate

        clean = QualificationRun("PASS", "a" * 64, "b" * 64, ())
        dirty = QualificationRun("PASS", "a" * 64, "b" * 64, ("leftover.tmp",))

        self.assertEqual(aggregate((clean, clean, clean)).status, "PASS")
        self.assertEqual(aggregate((clean, clean, dirty)).status, "PARTIAL")

    def test_qualification_cli_accepts_only_three_clean_identical_host_records(self) -> None:
        script = PROJECT_ROOT / "design-lab" / "scripts" / "qualify_reconstruction_runtime.py"
        record = {
            "schemaVersion": "design-lab/reconstruction-qualification-runs/v1",
            "caseId": "logo-orbit-001",
            "runs": [
                {"status": "PASS", "deterministicPreviewSha256": "a" * 64, "readbackSha256": "b" * 64, "residue": []}
                for _ in range(3)
            ],
        }
        with tempfile.TemporaryDirectory() as raw_dir:
            input_path = Path(raw_dir) / "runs.json"
            input_path.write_text(json.dumps(record), encoding="utf-8")
            result = subprocess.run([sys.executable, str(script), str(input_path)], check=False, capture_output=True, text=True, encoding="utf-8", errors="replace")

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("RECONSTRUCTION_QUALIFICATION=PASS case=logo-orbit-001", result.stdout)


if __name__ == "__main__":
    unittest.main()
