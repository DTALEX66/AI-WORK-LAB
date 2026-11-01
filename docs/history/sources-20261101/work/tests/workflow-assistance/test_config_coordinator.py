"""Contract tests for the three-way config coordinator (WL3-210)."""

from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("config_coordinator", ROOT / "services/policy/config_coordinator.py")
assert SPEC and SPEC.loader
MOD = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MOD
SPEC.loader.exec_module(MOD)

OWNERSHIP = json.loads((ROOT / "config/config-ownership.json").read_text(encoding="utf-8"))


class ConfigCoordinatorTests(unittest.TestCase):
    def test_existing_machine_managed_field_is_preserved_not_patchable(self) -> None:
        plan = MOD.three_way_compare(
            OWNERSHIP,
            previous_upstream={"display.language": "zh"},
            new_upstream={"display.language": "zh"},
            user_overlay={"display.language": "en"},
            identity_apply_allowed=True,
        )
        self.assertEqual(plan["status"], "NOOP")
        self.assertFalse(plan["approval_required"])
        self.assertFalse(plan["apply_allowed"])
        self.assertEqual(plan["write_set"], [])
        self.assertEqual(plan["preserved_fields"], ["display.language"])
        field = next(f for f in plan["fields"] if f["path"] == "display.language")
        self.assertEqual(field["change"], "USER_OVERLAY")
        self.assertEqual(field["action"], "PRESERVE")

    def test_existing_null_machine_value_is_preserved_not_patchable(self) -> None:
        plan = MOD.three_way_compare(
            OWNERSHIP,
            previous_upstream={"display.language": "zh"},
            new_upstream={"display.language": "en"},
            user_overlay={"display.language": None},
            identity_apply_allowed=True,
            machine_identity={"machine_id": "test-machine", "config_scope": "isolated-test-home"},
        )
        self.assertEqual(plan["status"], "NOOP")
        self.assertEqual(plan["write_set"], [])
        self.assertEqual(plan["preserved_fields"], ["display.language"])

    def test_actual_managed_drift_requires_discovered_machine_identity(self) -> None:
        without_identity = MOD.three_way_compare(
            OWNERSHIP,
            previous_upstream={"display.language": "zh"},
            new_upstream={"display.language": "en"},
            user_overlay={},
            identity_apply_allowed=True,
        )
        self.assertEqual(without_identity["status"], "WAITING_MACHINE_DISCOVERY")
        self.assertFalse(without_identity["apply_allowed"])
        self.assertEqual(without_identity["write_set"], ["display.language"])

        with_identity = MOD.three_way_compare(
            OWNERSHIP,
            previous_upstream={"display.language": "zh"},
            new_upstream={"display.language": "en"},
            user_overlay={},
            identity_apply_allowed=True,
            machine_identity={"machine_id": "test-machine", "config_scope": "isolated-test-home"},
        )
        self.assertEqual(with_identity["status"], "WAITING_APPROVAL")
        self.assertTrue(with_identity["approval_required"])
        self.assertTrue(with_identity["apply_allowed"])
        self.assertEqual(with_identity["write_set"], ["display.language"])

    def test_non_managed_values_are_redacted_from_machine_plan(self) -> None:
        plan = MOD.three_way_compare(
            OWNERSHIP,
            previous_upstream={"credentials": {"api_key": "old"}},
            new_upstream={"credentials": {"api_key": "new"}},
            user_overlay={},
            identity_apply_allowed=True,
            machine_identity={"machine_id": "test-machine", "config_scope": "isolated-test-home"},
        )
        field = next(f for f in plan["fields"] if f["path"] == "credentials")
        self.assertEqual(field["action"], "QUARANTINE")
        self.assertNotIn("previous_upstream", field)
        self.assertNotIn("new_upstream", field)
        self.assertNotIn("user_overlay", field)

    def test_secret_field_is_quarantined_even_with_unique_identity(self) -> None:
        plan = MOD.three_way_compare(
            OWNERSHIP,
            previous_upstream={},
            new_upstream={"credentials": {"api_key": "x"}},
            user_overlay={},
            identity_apply_allowed=True,
        )
        self.assertFalse(plan["apply_allowed"])
        self.assertIn("credentials", plan["quarantined_fields"])

    def test_unknown_field_defaults_to_quarantine(self) -> None:
        plan = MOD.three_way_compare(
            OWNERSHIP,
            previous_upstream={"mystery.key": 1},
            new_upstream={"mystery.key": 2},
            user_overlay={},
            identity_apply_allowed=True,
        )
        self.assertFalse(plan["apply_allowed"])
        self.assertIn("mystery.key", plan["quarantined_fields"])

    def test_project_local_rules_are_quarantined_from_global_write_set(self) -> None:
        plan = MOD.three_way_compare(
            OWNERSHIP,
            previous_upstream={"project.AGENTS": "old"},
            new_upstream={"project.AGENTS": "new"},
            user_overlay={},
            identity_apply_allowed=True,
            machine_identity={"machine_id": "test-machine", "config_scope": "isolated-test-home"},
        )
        self.assertEqual(plan["status"], "NOOP")
        self.assertEqual(plan["write_set"], [])
        self.assertIn("project.AGENTS", plan["quarantined_fields"])

    def test_declared_manage_field_without_reviewed_adapter_is_quarantined(self) -> None:
        plan = MOD.three_way_compare(
            OWNERSHIP,
            previous_upstream={"open-design.global_configuration": "old-pointer"},
            new_upstream={"open-design.global_configuration": "new-pointer"},
            user_overlay={},
            identity_apply_allowed=True,
            machine_identity={"machine_id": "test-machine", "config_scope": "isolated-test-home"},
        )
        self.assertEqual(plan["status"], "NOOP")
        self.assertEqual(plan["write_set"], [])
        self.assertIn("open-design.global_configuration", plan["quarantined_fields"])
        field = next(f for f in plan["fields"] if f["path"] == "open-design.global_configuration")
        self.assertEqual(field["action"], "QUARANTINE")
        self.assertFalse(field["apply_supported"])

    def test_upstream_change_with_user_overlay_is_rebase_candidate(self) -> None:
        plan = MOD.three_way_compare(
            OWNERSHIP,
            previous_upstream={"display.busy_input_mode": "queue"},
            new_upstream={"display.busy_input_mode": "drop"},
            user_overlay={"display.busy_input_mode": "queue"},
            identity_apply_allowed=True,
        )
        field = next(f for f in plan["fields"] if f["path"] == "display.busy_input_mode")
        self.assertEqual(field["change"], "UPSTREAM_CHANGED_WITH_OVERLAY")
        self.assertEqual(field["action"], "PRESERVE")

    def test_readback_and_rollback_are_hash_fenced(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "overlay.json"
            path.write_text(json.dumps({"display.language": "en"}), encoding="utf-8")
            digest = MOD.overlay_digest({"display.language": "en"})
            readback = MOD.readback_overlay(path, digest)
            self.assertEqual(readback["status"], "PASS")
            plan = MOD.three_way_compare(
                OWNERSHIP,
                previous_upstream={"display.language": "zh"},
                new_upstream={"display.language": "zh"},
                user_overlay={"display.language": "en"},
                identity_apply_allowed=True,
            )
            rollback = MOD.rollback_plan(plan, {"display.language": "zh"})
            self.assertEqual(rollback["status"], "NOOP")
            self.assertFalse(rollback["apply"])
            self.assertEqual(rollback["restore_fields"], [])

            patched_plan = MOD.three_way_compare(
                OWNERSHIP,
                previous_upstream={"display.language": "zh"},
                new_upstream={"display.language": "en"},
                user_overlay={},
                identity_apply_allowed=True,
                machine_identity={"machine_id": "test-machine", "config_scope": "isolated-test-home"},
            )
            patched_rollback = MOD.rollback_plan(patched_plan, {"display.language": "zh"})
            self.assertEqual(patched_rollback["status"], "READY")
            self.assertEqual(patched_rollback["restore_fields"], ["display.language"])


if __name__ == "__main__":
    unittest.main()
