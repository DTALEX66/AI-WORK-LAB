# SPDX-License-Identifier: MIT
"""DL C1: Design IR tests."""
from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"


class DesignIRTests(unittest.TestCase):
    def test_ir_verifier_passes(self):
        r = subprocess.run([sys.executable, str(SCRIPTS / "verify_design_ir.py")], capture_output=True, text=True, encoding="utf-8", errors="replace")
        self.assertIn("DESIGN_IR=PASS", r.stdout, r.stdout + r.stderr)

    def test_ir_sample_has_artifact_refs(self):
        import json
        d = json.loads((SCRIPTS.parent / "evals/design-ir/sample-hero.json").read_text(encoding="utf-8"))
        imgs = [l for l in d["layers"] if l["type"] == "image"]
        self.assertTrue(imgs)
        self.assertTrue(all(l["image"]["src_ref"].startswith("artifact://") for l in imgs))


if __name__ == "__main__":
    unittest.main()
