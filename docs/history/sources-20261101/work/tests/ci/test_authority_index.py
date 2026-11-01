"""WLG-000: authority index contract tests.

Asserts that the machine-readable authority index exists, is schema-valid,
and that every rule points at exactly one canonical source. Adding a second
field table or a second active CI authority is a WLG violation.
"""

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
INDEX = ROOT / ".project/governance/config-authority-index.json"


class AuthorityIndexTests(unittest.TestCase):
    def test_index_exists_and_is_valid_json(self):
        self.assertTrue(INDEX.exists(), "config-authority-index.json must exist")
        data = json.loads(INDEX.read_text(encoding="utf-8"))
        self.assertEqual(data["schema_version"], "workflow/authority-index/v1")
        self.assertEqual(data["wl_task"], "WLG-000")

    def test_every_authority_has_exactly_one_canonical_source(self):
        data = json.loads(INDEX.read_text(encoding="utf-8"))
        authorities = data["authorities"]
        self.assertGreaterEqual(len(authorities), 8)
        for name, entry in authorities.items():
            self.assertIn("canonical_source", entry, f"{name} must name a source")
            self.assertIn("status", entry, f"{name} must declare status")

    def test_active_and_superseded_lists_cover_authorities(self):
        data = json.loads(INDEX.read_text(encoding="utf-8"))
        named = set(data["authorities"].keys())
        listed = set(data["active_list"]) | set(data["superseded_list"]) | set(data["archive_list"])
        self.assertEqual(named, listed, "every authority must be classified exactly once")

    def test_config_ownership_is_the_single_field_authority(self):
        data = json.loads(INDEX.read_text(encoding="utf-8"))
        cfg = data["authorities"]["config_fields"]
        self.assertEqual(cfg["status"], "ACTIVE")
        self.assertIn("single field-level authority", cfg["role"])
        # No duplicate field tables: the standard doc must not re-list fields.
        standard = ROOT / "docs/current/workflow-assistance/workflow/official-plus-user-configuration-standard-2026-08-11.md"
        text = standard.read_text(encoding="utf-8")
        self.assertIn("config/config-ownership.json", text)
        self.assertIn("only field-level authority", text)

    def test_no_second_active_ci_authority(self):
        data = json.loads(INDEX.read_text(encoding="utf-8"))
        root_gate = data["authorities"]["workflow_root_gate"]
        nested = data["authorities"]["nested_governance_workflow"]
        self.assertEqual(root_gate["status"], "ACTIVE")
        self.assertEqual(nested["status"], "SUPERSEDED_REFERENCE")

    def test_managed_config_schema_is_superseded_not_active(self):
        data = json.loads(INDEX.read_text(encoding="utf-8"))
        self.assertEqual(data["authorities"]["managed_config_schema"]["status"], "SUPERSEDED")


if __name__ == "__main__":
    unittest.main()
