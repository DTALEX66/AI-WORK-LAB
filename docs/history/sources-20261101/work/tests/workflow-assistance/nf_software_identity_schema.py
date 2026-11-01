"""P0-07 / TaskPack §36 DoD: builder outputs must conform to the contracts.

Validates the pure ``preflight_identity_record`` and ``build_update_preflight``
builders against the two registered JSON Schemas
(``workflow/software-installation-identity/v1`` and
``workflow/software-update-preflight/v1``), covering the reason/after/readback
edge cases. Pure + fixture-driven; no filesystem writes, no credentials, and
no auto relocation/deletion (§40).
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
sys.path.insert(0, os.path.join(ROOT, "tests"))

import software_installation_identity as sii  # noqa: E402

D = "D:\\All projects\\DSH"
C = "C:\\Users\\ALEX\\AppData\\Local\\DSH"


def _schema(name: str) -> dict:
    p = os.path.join(ROOT, "packages", "contracts", "schemas", "workflow", name)
    with open(p, encoding="utf-8") as handle:
        return json.load(handle)


class BuilderConformanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if jsonschema is None:
            raise unittest.SkipTest("jsonschema not available")
        cls.ident = _schema("software-installation-identity.schema.json")
        cls.pref = _schema("software-update-preflight.schema.json")

    def _valid(self, schema, record):
        jsonschema.validate(instance=record, schema=schema)

    def test_dsh_identity_record_conforms(self):
        rec = sii.preflight_identity_record(
            software_id="deepseek-harness",
            expected_existing=D, observed=[D], verified=True,
        )
        self._valid(self.ident, rec)
        self.assertEqual(rec["location_status"], "SINGLE_VERIFIED")
        self.assertTrue(rec["installed"])

    def test_in_place_preflight_conforms_with_after(self):
        rec = sii.build_update_preflight(
            software_id="deepseek-harness",
            location_status="SINGLE_VERIFIED",
            install_root=D, proposed_install_root=D, verified=True,
        )
        self._valid(self.pref, rec)
        self.assertEqual(rec["update_mode"], "IN_PLACE_ONLY")
        self.assertTrue(rec["location_readback_required"])
        self.assertIn("after", rec)
        self.assertEqual(rec["overall"], "PENDING")

    def test_blocked_dual_preflight_conforms_without_after(self):
        rec = sii.build_update_preflight(
            software_id="deepseek-harness",
            location_status="DUAL_INSTALLATION",
            install_root=D,
        )
        self._valid(self.pref, rec)
        self.assertEqual(rec["update_mode"], "BLOCKED")
        self.assertFalse(rec["location_readback_required"])
        self.assertNotIn("after", rec)
        self.assertEqual(rec["overall"], "FAIL")
        self.assertIn("DUAL_INSTALLATION_UPDATE_BLOCKED", rec["reasons"])

    def test_fresh_install_preflight_conforms_without_after(self):
        rec = sii.build_update_preflight(
            software_id="openai-codex",
            location_status="NOT_INSTALLED",
            user_declared=C,
        )
        self._valid(self.pref, rec)
        self.assertEqual(rec["update_mode"], "FRESH_INSTALL")
        self.assertNotIn("after", rec)

    def test_approved_relocation_preflight_conforms_with_after(self):
        rec = sii.build_update_preflight(
            software_id="deepseek-harness",
            location_status="SINGLE_VERIFIED",
            install_root=D, proposed_install_root=C, verified=True,
            relocation_requested=True, relocation_approved=True,
        )
        self._valid(self.pref, rec)
        self.assertEqual(rec["update_mode"], "RELOCATION")
        self.assertTrue(rec["relocation_approved"])
        self.assertIn("after", rec)
        self.assertEqual(rec["approved_operation"], "RELOCATION")

    def test_reasons_stay_within_closed_enum(self):
        enum = set(self.pref["properties"]["reasons"]["items"]["enum"])
        for status in ("SINGLE_VERIFIED", "SINGLE_UNVERIFIED", "LOCATION_DRIFT",
                       "DUAL_INSTALLATION", "MISSING_EXPECTED_INSTALL",
                       "NOT_INSTALLED", "OS_MANAGED", "RELOCATION_REQUESTED"):
            rec = sii.build_update_preflight(software_id="x", location_status=status,
                                             install_root=D, proposed_install_root=C,
                                             relocation_requested=(status == "RELOCATION_REQUESTED"))
            for reason in rec["reasons"]:
                self.assertIn(reason, enum)


if __name__ == "__main__":
    unittest.main()
