# SPDX-License-Identifier: MIT
"""ODA4-0203: three public entrypoints + plugin convergence tests."""
from __future__ import annotations

import json
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
BUNDLES = REPO / "packages" / "capabilities" / "bundles"
PLUGINS = REPO / "packages" / "capabilities" / "plugins"
CONFIG = REPO / "design-lab" / "config" / "entrypoint-convergence.json"

EXPECTED_BUNDLES = ["commercial-design-core", "visual-quality-core", "production-handoff"]


class EntrypointConvergenceTest(unittest.TestCase):
    def test_exactly_three_public_bundles(self):
        found = sorted(p.name for p in BUNDLES.iterdir() if p.is_dir())
        self.assertEqual(found, sorted(EXPECTED_BUNDLES))

    def test_each_bundle_has_manifest(self):
        for b in EXPECTED_BUNDLES:
            self.assertTrue((BUNDLES / b / "open-design.json").exists(), f"{b} missing manifest")
            self.assertTrue((BUNDLES / b / "SKILL.md").exists(), f"{b} missing SKILL.md")

    def test_production_handoff_has_preflight_atoms(self):
        # V42-0303 (live daemon discovery): context.atoms must reference
        # daemon built-in atoms; local professional atoms are declared via
        # context.assets (SKILL.md paths).
        m = json.loads((BUNDLES / "production-handoff" / "open-design.json").read_text(encoding="utf-8"))
        ctx = m["od"]["context"]
        atoms = ctx["atoms"]
        self.assertIn("handoff", atoms)
        assets = " ".join(ctx.get("assets", []))
        self.assertIn("commercial-preflight", assets)
        self.assertIn("delivery-packager", assets)

    def test_convergence_map_covers_plugins(self):
        conv = json.loads(CONFIG.read_text(encoding="utf-8"))
        mapped = {p["plugin"] for p in conv["plugin_convergence_map"]}
        plugins = {p.name for p in PLUGINS.iterdir() if p.is_dir() and p.name != "INDEX.md"}
        # All plugins except INDEX must be mapped (minigame-ui, etc.)
        unmapped = plugins - mapped
        self.assertEqual(unmapped, set(), f"unmapped plugins: {unmapped}")
        self.assertEqual(set(conv["public_entrypoints"]), set(EXPECTED_BUNDLES))


if __name__ == "__main__":
    unittest.main(verbosity=2)
