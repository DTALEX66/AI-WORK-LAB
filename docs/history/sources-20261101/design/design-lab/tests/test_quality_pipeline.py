# SPDX-License-Identifier: MIT
"""DL D2: quality pipeline tests."""
from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"


class QualityPipelineTests(unittest.TestCase):
    def test_pipeline_verifier_passes(self):
        r = subprocess.run([sys.executable, str(SCRIPTS / "verify_quality_pipeline.py")], capture_output=True, text=True, encoding="utf-8", errors="replace")
        self.assertIn("QUALITY_PIPELINE=PASS", r.stdout, r.stdout + r.stderr)

    def test_human_feedback_is_last_and_e4(self):
        import json
        reg = json.loads((SCRIPTS.parent.parent / "packages/capabilities/quality/pipeline-layers.json").read_text(encoding="utf-8"))
        last = reg["layers"][-1]
        self.assertEqual(last["id"], "human-feedback")
        self.assertEqual(last["evidence_level"], "E4")


if __name__ == "__main__":
    unittest.main()
