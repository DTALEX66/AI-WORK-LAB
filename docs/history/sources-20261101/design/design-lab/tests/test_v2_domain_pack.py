# SPDX-License-Identifier: MIT
from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACK = ROOT / "domain-packs/minigame-design"


class DomainPackTests(unittest.TestCase):
    def test_manifest_is_fixture_design_only(self):
        manifest = json.loads((PACK / "manifest.json").read_text(encoding="utf-8"))
        self.assertIn("cctv-primary-visual", manifest["capabilities"])
        self.assertNotIn("advertising", manifest["capabilities"])
        self.assertIn("advertising", manifest["excluded_capabilities"])

    def test_required_handoff_material_exists(self):
        for name in ("README.md", "rules.md", "qa.md", "handoff.md", "schemas/brief.schema.json"):
            with self.subTest(name=name):
                self.assertTrue((PACK / name).is_file())

    def test_brief_schema_parses(self):
        schema = json.loads((PACK / "schemas/brief.schema.json").read_text(encoding="utf-8"))
        self.assertEqual(schema["$id"], "design-lab/minigame-design-brief/v1")


if __name__ == "__main__":
    unittest.main()
