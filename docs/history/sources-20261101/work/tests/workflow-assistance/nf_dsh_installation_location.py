"""P0-07 / TaskPack §20 + §35: DSH golden location regression + negative tests.

All tests drive the PURE ``software_installation_identity`` resolver with
fixtures. No real install / move / delete / C->D or D->C is performed, no
C-drive DSH state is read, and no second install is auto-removed — the resolver
only classifies and returns fail-closed verdicts, which is exactly what §40
permits. The DSH canonical identity (§20) is:

    install_root:  D:\\All projects\\DSH
    entry:         D:\\All projects\\DSH\\DSH Desktop.exe
    deployment:    community desktop
"""
from __future__ import annotations

import os
import sys
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "packages", "client-neutral-core", "scripts"))

import software_installation_identity as sii  # noqa: E402

D = "D:\\All projects\\DSH"
C = "C:\\Users\\ALEX\\AppData\\Local\\DSH"


class DshGoldenRegressionTests(unittest.TestCase):
    """§20 Cases A-E against the DSH canonical identity."""

    def test_case_a_in_place_update_passes(self):
        # before D, proposed D, after D -> in place, PASS.
        plan = sii.plan_update(location_status="SINGLE_VERIFIED",
                               install_root=D, proposed_install_root=D, verified=True)
        self.assertEqual(plan["update_mode"], "IN_PLACE_ONLY")
        self.assertFalse(plan["blocked"])
        readback = sii.location_readback(
            {"install_root": D, "executable_realpath": f"{D}\\DSH Desktop.exe"},
            {"install_root": D, "executable_realpath": f"{D}\\DSH Desktop.exe"})
        self.assertTrue(readback["location_readback_passed"])
        self.assertEqual(sii.overall_result(version_verification="PASS",
                                             behavior_verification="PASS",
                                             location_verification="PASS"), "PASS")

    def test_case_b_updater_wants_c_blocked(self):
        # existing D, installer proposes C -> BLOCKED, must relocate explicitly.
        plan = sii.plan_update(location_status="SINGLE_VERIFIED",
                               install_root=D, proposed_install_root=C, verified=True)
        self.assertEqual(plan["update_mode"], "BLOCKED")
        self.assertTrue(plan["blocked"])
        self.assertIn("INSTALL_ROOT_CHANGE_REQUIRES_EXPLICIT_RELOCATION", plan["reasons"])

    def test_case_c_dual_installation_blocked(self):
        # D and C both present -> DUAL_INSTALLATION, update blocked, no auto-delete.
        cls = sii.classify_installation(expected_existing=D, observed=[D, C], verified=True)
        self.assertEqual(cls["location_status"], "DUAL_INSTALLATION")
        self.assertIsNone(cls["canonical_candidate"])
        plan = sii.plan_update(location_status="DUAL_INSTALLATION",
                               install_root=D, proposed_install_root=D)
        self.assertEqual(plan["update_mode"], "BLOCKED")
        self.assertIn("DUAL_INSTALLATION_UPDATE_BLOCKED", plan["reasons"])

    def test_case_d_expected_d_missing_no_vendor_fallback(self):
        # expected D, actual none -> MISSING_EXPECTED_INSTALL, never re-install to C.
        cls = sii.classify_installation(expected_existing=D, observed=[])
        self.assertEqual(cls["location_status"], "MISSING_EXPECTED_INSTALL")
        plan = sii.plan_update(location_status="MISSING_EXPECTED_INSTALL")
        self.assertEqual(plan["update_mode"], "BLOCKED")
        self.assertIn("MISSING_EXPECTED_INSTALL_NO_VENDOR_FALLBACK", plan["reasons"])

    def test_case_e_true_fresh_install_respects_user_fixed_location(self):
        # no DSH detected, user fixed config D -> fresh install goes to D.
        cls = sii.classify_installation(user_declared=D, observed=[])
        self.assertEqual(cls["location_status"], "NOT_INSTALLED")
        plan = sii.plan_update(location_status="NOT_INSTALLED", user_declared=D)
        self.assertEqual(plan["update_mode"], "FRESH_INSTALL")
        self.assertEqual(plan.get("fresh_target"), D)


class NegativeLocationTests(unittest.TestCase):
    """§35 mandatory negative tests — every case must fail-closed as asserted."""

    def test_1_existing_d_updater_wants_c_must_fail(self):
        plan = sii.plan_update(location_status="SINGLE_VERIFIED",
                               install_root=D, proposed_install_root=C, verified=True)
        self.assertTrue(plan["blocked"])
        self.assertEqual(plan["update_mode"], "BLOCKED")

    def test_2_two_valid_installations_must_fail(self):
        cls = sii.classify_installation(observed=[D, C], verified=True)
        self.assertEqual(cls["location_status"], "DUAL_INSTALLATION")
        plan = sii.plan_update(location_status=cls["location_status"])
        self.assertEqual(plan["update_mode"], "BLOCKED")

    def test_3_missing_expected_install_must_not_fallback_to_vendor_default(self):
        cls = sii.classify_installation(expected_existing=D, observed=[])
        self.assertEqual(cls["location_status"], "MISSING_EXPECTED_INSTALL")
        # A plain update for a missing expected install is BLOCKED, not a fresh
        # install into the vendor default C:.
        plan = sii.plan_update(location_status=cls["location_status"])
        self.assertEqual(plan["update_mode"], "BLOCKED")

    def test_4_path_unchanged_version_upgrade_passes(self):
        plan = sii.plan_update(location_status="SINGLE_VERIFIED",
                               install_root=D, proposed_install_root=D, verified=True)
        self.assertEqual(plan["update_mode"], "IN_PLACE_ONLY")
        self.assertFalse(plan["blocked"])

    def test_5_relocation_explicitly_approved_may_change_root(self):
        plan = sii.plan_update(location_status="SINGLE_VERIFIED",
                               install_root=D, proposed_install_root=C,
                               verified=True, relocation_requested=True,
                               relocation_approved=True)
        self.assertEqual(plan["update_mode"], "RELOCATION")
        self.assertFalse(plan["blocked"])
        readback = sii.location_readback(
            {"install_root": D}, {"install_root": C}, is_relocation=True)
        self.assertTrue(readback["location_readback_passed"])

    def test_6_relocation_without_approval_fails(self):
        plan = sii.plan_update(location_status="SINGLE_VERIFIED",
                               install_root=D, proposed_install_root=C,
                               verified=True, relocation_requested=True,
                               relocation_approved=False)
        self.assertEqual(plan["update_mode"], "BLOCKED")
        self.assertTrue(plan["blocked"])

    def test_7_os_managed_stays_os_managed(self):
        cls = sii.classify_installation(expected_existing=D, observed=[D], os_managed=True)
        self.assertEqual(cls["location_status"], "OS_MANAGED")
        plan = sii.plan_update(location_status="OS_MANAGED")
        self.assertEqual(plan["update_mode"], "PRESERVE_OFFICIAL_CHANNEL")
        self.assertNotEqual(plan["update_mode"], "RELOCATION")

    def test_location_readback_fail_closes_overall(self):
        # §19: version+behavior PASS but location FAIL -> overall FAIL.
        readback = sii.location_readback({"install_root": D}, {"install_root": C})
        self.assertFalse(readback["location_readback_passed"])
        overall = sii.overall_result(version_verification="PASS",
                                     behavior_verification="PASS",
                                     location_verification="FAIL")
        self.assertEqual(overall, "FAIL")

    def test_single_unverified_requires_validation_first(self):
        plan = sii.plan_update(location_status="SINGLE_UNVERIFIED",
                               install_root=D, proposed_install_root=D)
        self.assertEqual(plan["update_mode"], "BLOCKED")
        self.assertIn("SINGLE_UNVERIFIED_IDENTITY_VALIDATION_FIRST", plan["reasons"])


if __name__ == "__main__":
    unittest.main()
