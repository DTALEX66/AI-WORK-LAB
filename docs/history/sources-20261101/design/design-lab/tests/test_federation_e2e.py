# SPDX-License-Identifier: MIT
"""TP-20260819 E2E-002: federation E2E tests."""
from __future__ import annotations
import subprocess
import sys
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'

class FederationE2ETests(unittest.TestCase):
    def test_federation_e2e_passes(self):
        r = subprocess.run([sys.executable, str(SCRIPTS / 'verify_federation_e2e.py')], capture_output=True, text=True, encoding="utf-8", errors="replace")
        self.assertIn('FEDERATION_E2E=PASS', r.stdout, r.stdout + r.stderr)

if __name__ == '__main__':
    unittest.main()
