# SPDX-License-Identifier: MIT
"""Static safety contracts for the Illustrator reconstruction JSX adapter."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "design-lab"))
sys.path.insert(0, str(PROJECT_ROOT / "design-lab" / "scripts"))
JSX = PROJECT_ROOT / "integrations" / "hosts" / "adobe" / "illustrator" / "reconstruction-assemble.jsx"


class IllustratorAdapterTests(unittest.TestCase):
    def test_jsx_has_no_arbitrary_menu_or_shell_execution(self) -> None:
        source = JSX.read_text(encoding="utf-8")

        self.assertNotIn("executeMenu" + "Command", source)
        self.assertNotIn("system.call" + "System", source)
        self.assertIn("function assertInside", source)
        self.assertIn("app.documents.add", source)

    def test_static_verifier_requires_reopen_readback_and_preview_export(self) -> None:
        from verify_illustrator_reconstruction_adapter import verify_structural

        result = verify_structural(JSX)

        self.assertEqual(result.required_operations[-3:], ("reopen", "readback", "exportPNG"))
        self.assertTrue(result.ok)


if __name__ == "__main__":
    unittest.main()
