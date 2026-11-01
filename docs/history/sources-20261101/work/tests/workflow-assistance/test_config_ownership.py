"""Contract tests for the config-ownership registry (WL3-200)."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

import jsonschema
import yaml

ROOT = Path(__file__).resolve().parents[2]
REGISTRY = ROOT / "config/config-ownership.json"
SCHEMA = ROOT / "packages/contracts/schemas/workflow/config-ownership.schema.json"
COMPATIBILITY_RECIPE = ROOT / "config/managed-config-schema.yaml"
EXPECTED_LAYERS = {
    "UPSTREAM_OFFICIAL", "USER_OVERLAY", "PROJECT_OVERLAY", "TASK_EPHEMERAL",
    "PLATFORM_INTERNAL", "RUNTIME_EPHEMERAL", "SECRET", "COSMETIC",
}


class ConfigOwnershipTests(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = json.loads(REGISTRY.read_text(encoding="utf-8"))

    def test_single_authority_v2(self) -> None:
        self.assertEqual(self.registry["schema_version"], "workflow/config-ownership/v2")
        self.assertTrue(self.registry["single_authority"])

    def test_registry_validates_against_v2_schema(self) -> None:
        schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
        jsonschema.Draft202012Validator(schema).validate(self.registry)

    def test_all_layers_and_modes_present(self) -> None:
        self.assertEqual(set(self.registry["layers"]), EXPECTED_LAYERS)
        self.assertEqual(set(self.registry["operation_modes"]), {"MANAGE", "OBSERVE", "IGNORE", "FORBIDDEN"})

    def test_unknown_fields_default_to_quarantine(self) -> None:
        default = self.registry["default_unknown"]
        self.assertEqual(default["mode"], "OBSERVE")
        self.assertTrue(default["quarantine"])

    def test_secret_fields_are_forbidden(self) -> None:
        secret_fields = [f for f in self.registry["fields"] if f["layer"] == "SECRET"]
        self.assertTrue(secret_fields)
        for field in secret_fields:
            self.assertEqual(field["mode"], "FORBIDDEN")

    def test_field_paths_are_unique_and_cover_all_layers(self) -> None:
        paths = [field["path"] for field in self.registry["fields"]]
        self.assertEqual(len(paths), len(set(paths)))
        used_layers = {field["layer"] for field in self.registry["fields"]}
        self.assertIn("USER_OVERLAY", used_layers)
        self.assertIn("SECRET", used_layers)
        self.assertIn("PLATFORM_INTERNAL", used_layers)

    def test_cross_client_and_external_actor_boundaries_are_explicit(self) -> None:
        rules = self.registry["rules"]
        self.assertTrue(rules["cc_switch_owns_supported_client_provider_routing_only"])
        self.assertTrue(rules["cross_client_prompt_skill_session_sync_forbidden"])
        self.assertTrue(rules["raw_memory_never_crosses_client_boundary"])
        fields = {field["path"]: field for field in self.registry["fields"]}
        self.assertEqual(fields["openhuman.runtime_memory"]["mode"], "IGNORE")
        self.assertEqual(fields["open-design.read_only_mcp"]["mode"], "OBSERVE")
        self.assertEqual(fields["cc_switch.provider.catalog"]["mode"], "OBSERVE")
        self.assertEqual(fields["cc_switch.provider.routing"]["mode"], "OBSERVE")
        self.assertEqual(fields["openhuman.global_configuration"]["mode"], "MANAGE")
        self.assertFalse(fields["openhuman.global_configuration"]["apply_supported"])
        self.assertEqual(fields["open-design.global_configuration"]["mode"], "MANAGE")
        self.assertFalse(fields["open-design.global_configuration"]["apply_supported"])
        self.assertEqual(fields["external_projects.design_lab.project_configuration"]["mode"], "OBSERVE")
        self.assertFalse(fields["external_projects.design_lab.project_configuration"]["apply_supported"])

    def test_project_local_rules_are_observed_not_globally_applied(self) -> None:
        fields = {field["path"]: field for field in self.registry["fields"]}
        for path in ("project.AGENTS", "project.rules", "project.skills"):
            self.assertEqual(fields[path]["layer"], "PROJECT_OVERLAY")
            self.assertEqual(fields[path]["mode"], "OBSERVE")
            self.assertIn("no global synchronizer may apply", fields[path]["scope"])

    def test_live_configuration_reconciliation_is_discovery_first_and_minimal(self) -> None:
        rules = self.registry["rules"]
        self.assertTrue(rules["live_config_discovery_required_before_apply"])
        self.assertTrue(rules["machine_scoped_action_plan_required"])
        self.assertTrue(rules["apply_only_actual_managed_drift"])
        self.assertTrue(rules["no_op_plan_never_writes"])
        self.assertTrue(rules["explicit_approval_after_plan_review"])
        self.assertTrue(rules["apply_readback_required"])

    def test_legacy_recipe_is_isolated_empty_home_only(self) -> None:
        recipe = yaml.safe_load(COMPATIBILITY_RECIPE.read_text(encoding="utf-8"))
        self.assertEqual(recipe["authority"], "config/config-ownership.json")
        self.assertEqual(recipe["compatibility_scope"], "isolated-empty-home")
        self.assertEqual(recipe["global_workflow"]["deployment"], "isolated-empty-home-only")
        self.assertNotIn("repo-to-live", COMPATIBILITY_RECIPE.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
