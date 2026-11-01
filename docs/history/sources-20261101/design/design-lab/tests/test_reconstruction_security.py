# SPDX-License-Identifier: MIT
"""Adversarial reconstruction inputs must fail before rendering or host launch."""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "design-lab" / "scripts"))
MANIFEST = PROJECT_ROOT / "design-lab" / "tests" / "fixtures" / "reconstruction" / "adversarial" / "manifest.json"


class ReconstructionSecurityTests(unittest.TestCase):
    def test_every_registered_attack_is_pre_render_rejected(self) -> None:
        from verify_reconstruction_security import run_attack

        attacks = json.loads(MANIFEST.read_text(encoding="utf-8"))["attacks"]
        for name in attacks:
            with self.subTest(name=name):
                self.assertEqual(run_attack(name).phase, "PRE_RENDER_REJECTED")


if __name__ == "__main__":
    unittest.main()
