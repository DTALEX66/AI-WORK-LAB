# SPDX-License-Identifier: MIT
"""DL D1: design action language tests."""
from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"


class DesignActionTests(unittest.TestCase):
    def test_actions_verifier_passes(self):
        r = subprocess.run([sys.executable, str(SCRIPTS / "verify_design_actions.py")], capture_output=True, text=True, encoding="utf-8", errors="replace")
        self.assertIn("DESIGN_ACTIONS=PASS", r.stdout, r.stdout + r.stderr)

    def test_vocabulary_is_tool_neutral(self):
        import json
        reg = json.loads((SCRIPTS.parent / "config/design-actions.json").read_text(encoding="utf-8"))
        banned = ["photoshop", "figma", "blender", "comfyui", "minimax", "deepseek"]
        for a in reg["actions"]:
            self.assertFalse(any(b in a["verb"].lower() for b in banned), a["verb"])


if __name__ == "__main__":
    unittest.main()
