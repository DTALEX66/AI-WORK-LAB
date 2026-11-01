# SPDX-License-Identifier: MIT
"""Static safety contracts for Photoshop UXP reconstruction layer preparation."""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "design-lab" / "scripts"))
ROOT = PROJECT_ROOT / "integrations" / "hosts" / "adobe" / "photoshop-reconstruction"
MANIFEST = ROOT / "manifest.json"
INDEX = ROOT / "index.js"


class PhotoshopAdapterTests(unittest.TestCase):
    def test_manifest_has_no_unrestricted_network_permission(self) -> None:
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))

        self.assertNotIn("https://*", json.dumps(manifest, sort_keys=True))
        self.assertEqual(manifest["manifestVersion"], 5)

    def test_all_document_mutations_are_modal_and_static_verifier_passes(self) -> None:
        from verify_photoshop_reconstruction_adapter import verify_structural

        source = INDEX.read_text(encoding="utf-8")
        self.assertIn("executeAsModal", source)
        self.assertIn("executionContext.isCancelled", source)
        self.assertTrue(verify_structural(ROOT).ok)


if __name__ == "__main__":
    unittest.main()
