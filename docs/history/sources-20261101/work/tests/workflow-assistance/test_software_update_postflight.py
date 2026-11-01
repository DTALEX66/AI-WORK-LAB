"""P0-07 / §42: software-update-postflight gate — positive behavior tests.

Covers the DSH golden PASS case (in-place update 2.0.12 -> 2.0.13, install
root stays on D:, data root pinned, launchers pinned, official code tree
intact, no C-drive residue re-seeded, runtime healthy), the PENDING case
(runtime health UNKNOWN is never fabricated as PASS), and record conformance
against the registered ``workflow/software-update-postflight/v1`` schema.
Fixture-driven and pure: no real filesystem access, no C-drive reads, no
auto-deletion or second updater (§40).
"""
from __future__ import annotations

import json
import os
import sys
import unittest

try:
    import jsonschema
except ImportError:  # pragma: no cover
    jsonschema = None

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "packages", "client-neutral-core", "scripts"))

import software_update_postflight as sup  # noqa: E402

DSH_INSTALL_ROOT = r"D:\All projects\DSH"
DSH_EXE = r"D:\All projects\DSH\DSH Desktop.exe"
DSH_DATA_ROOT = r"D:\All projects\DSH\.dsh"
DSH_LAUNCHER = r"D:\All projects\DSH\launch-dsh.cmd"


def _schema() -> dict:
    p = os.path.join(
        ROOT, "packages", "contracts", "schemas", "workflow",
        "software-update-postflight.schema.json",
    )
    with open(p, encoding="utf-8") as handle:
        return json.load(handle)


def _before() -> dict:
    return {
        "install_root": DSH_INSTALL_ROOT,
        "executable_realpath": DSH_EXE,
        "version": "2.0.12",
        "launcher_targets": [DSH_LAUNCHER],
        "data_root": DSH_DATA_ROOT,
    }


def _after() -> dict:
    """A fully-verified in-place DSH update: everything pinned, healthy."""
    return {
        "install_root": DSH_INSTALL_ROOT,
        "executable_realpath": DSH_EXE,
        "version": "2.0.13",
        "launcher_targets": [DSH_LAUNCHER],
        "data_root": DSH_DATA_ROOT,
        "c_drive_residue": [],
        "code_tree_files": 45000,
        "asar_residue": False,
        "uninstaller": r"D:\All projects\DSH\Uninstaller.exe",
        "runtime_health": "PASS",
    }


class DshGoldenPostflightTests(unittest.TestCase):
    def test_dsh_in_place_update_passes_every_check(self):
        record = sup.run_postflight_checks(
            software_id="deepseek-harness",
            target_version="2.0.13",
            before=_before(),
            after=_after(),
            expected_install_root=DSH_INSTALL_ROOT,
            expected_data_root=DSH_DATA_ROOT,
            residue_watchlist=[
                r"C:\Users\ALEX\.dsh",
                r"C:\Users\ALEX\AppData\Local\DSH",
            ],
            expected_code_tree_files_min=40000,
            asar_expected=False,
            uninstaller_expected=True,
        )
        self.assertEqual(record["overall"], "PASS")
        self.assertEqual(record["reasons"], ["POSTFLIGHT_ALL_CHECKS_PASS"])
        self.assertTrue(record["location_readback_passed"])
        statuses = {c["name"]: c["status"] for c in record["checks"]}
        self.assertEqual(
            statuses,
            {
                "version_readback": "PASS",
                "body_integrity": "PASS",
                "launcher_pinning": "PASS",
                "data_root_pinning": "PASS",
                "c_residue": "PASS",
                "runtime_health": "PASS",
                "location_readback": "PASS",
            },
        )

    def test_pending_when_runtime_health_unknown(self):
        after = _after()
        after["runtime_health"] = "UNKNOWN"
        record = sup.run_postflight_checks(
            software_id="deepseek-harness",
            target_version="2.0.13",
            before=_before(),
            after=after,
            expected_install_root=DSH_INSTALL_ROOT,
            expected_data_root=DSH_DATA_ROOT,
            expected_code_tree_files_min=40000,
        )
        self.assertEqual(record["overall"], "PENDING")
        self.assertIn("RUNTIME_HEALTH_UNVERIFIED", record["reasons"])
        self.assertIn("POSTFLIGHT_INCOMPLETE", record["reasons"])
        # Unknown runtime health must NOT be fabricated as PASS anywhere.
        self.assertNotIn("POSTFLIGHT_ALL_CHECKS_PASS", record["reasons"])

    def test_missing_version_is_unverified_not_pass(self):
        after = _after()
        del after["version"]
        record = sup.run_postflight_checks(
            software_id="deepseek-harness",
            target_version="2.0.13",
            before=_before(),
            after=after,
            expected_install_root=DSH_INSTALL_ROOT,
            expected_data_root=DSH_DATA_ROOT,
        )
        self.assertEqual(record["overall"], "PENDING")
        self.assertIn("POSTFLIGHT_INCOMPLETE", record["reasons"])
        statuses = {c["name"]: c["status"] for c in record["checks"]}
        self.assertEqual(statuses["version_readback"], "UNVERIFIED")


class PostflightSchemaConformanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if jsonschema is None:
            raise unittest.SkipTest("jsonschema not available")
        cls.schema = _schema()
        cls.validator = jsonschema.Draft202012Validator(cls.schema)

    def _valid(self, record: dict) -> None:
        errors = list(self.validator.iter_errors(record))
        self.assertEqual(errors, [], "expected VALID but got: " + "; ".join(e.message for e in errors))

    def _invalid(self, record: dict) -> None:
        errors = list(self.validator.iter_errors(record))
        self.assertNotEqual(errors, [], "expected INVALID but the instance passed the schema")

    def test_golden_pass_record_conforms(self):
        record = sup.run_postflight_checks(
            software_id="deepseek-harness",
            target_version="2.0.13",
            before=_before(),
            after=_after(),
            expected_install_root=DSH_INSTALL_ROOT,
            expected_data_root=DSH_DATA_ROOT,
            expected_code_tree_files_min=40000,
        )
        self._valid(record)
        self.assertEqual(record["schema_version"], "workflow/software-update-postflight/v1")

    def test_pending_record_conforms(self):
        after = _after()
        after["runtime_health"] = "UNKNOWN"
        record = sup.run_postflight_checks(
            software_id="deepseek-harness",
            target_version="2.0.13",
            before=_before(),
            after=after,
            expected_install_root=DSH_INSTALL_ROOT,
            expected_data_root=DSH_DATA_ROOT,
        )
        self._valid(record)

    def test_schema_reason_enum_matches_module_closed_set(self):
        schema_enum = self.schema["properties"]["reasons"]["items"]["enum"]
        self.assertEqual(schema_enum, list(sup.POSTFLIGHT_REASONS))

    def test_unknown_check_name_is_rejected(self):
        record = sup.run_postflight_checks(
            software_id="deepseek-harness",
            target_version="2.0.13",
            before=_before(),
            after=_after(),
            expected_install_root=DSH_INSTALL_ROOT,
            expected_data_root=DSH_DATA_ROOT,
        )
        record["checks"].append(
            {"name": "made_up_check", "status": "PASS", "expected": None, "observed": None}
        )
        self._invalid(record)

    def test_unknown_status_is_rejected(self):
        record = sup.run_postflight_checks(
            software_id="deepseek-harness",
            target_version="2.0.13",
            before=_before(),
            after=_after(),
            expected_install_root=DSH_INSTALL_ROOT,
            expected_data_root=DSH_DATA_ROOT,
        )
        record["checks"][0]["status"] = "MAYBE"
        self._invalid(record)

    def test_extra_top_level_field_is_rejected(self):
        record = sup.run_postflight_checks(
            software_id="deepseek-harness",
            target_version="2.0.13",
            before=_before(),
            after=_after(),
            expected_install_root=DSH_INSTALL_ROOT,
            expected_data_root=DSH_DATA_ROOT,
        )
        record["extra"] = "boom"
        self._invalid(record)


if __name__ == "__main__":
    unittest.main()
