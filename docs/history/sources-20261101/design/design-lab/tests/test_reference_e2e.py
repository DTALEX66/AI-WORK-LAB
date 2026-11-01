# SPDX-License-Identifier: MIT
"""DL-V2 P1-F: reference E2E tests."""
from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"


class ReferenceE2ETests(unittest.TestCase):
    def test_reference_e2e_passes(self):
        r = subprocess.run([sys.executable, str(SCRIPTS / "verify_reference_e2e.py")], capture_output=True, text=True, encoding="utf-8", errors="replace")
        self.assertIn("REFERENCE_E2E=PASS", r.stdout, r.stdout + r.stderr)

    def test_sample_is_honest_e1(self):
        import json
        data = json.loads((SCRIPTS.parent / "evals/e2e-reference/ecommerce-hero-v1.json").read_text(encoding="utf-8"))
        self.assertEqual(data["evidence_level"], "E1")
        self.assertNotIn("H3", data["claim"])
        self.assertNotIn("ComfyUI", data["claim"])


if __name__ == "__main__":
    unittest.main()
