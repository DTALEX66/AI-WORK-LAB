"""P0-07 / §42: software-update-postflight gate — negative controls.

One test per recurrence scenario from the DSH 2026-09-20 evidence. Each
drives the PURE ``software_update_postflight`` gate with fixtures only:
no real install, no C-drive read, no auto-deletion, no second updater —
§40 compliant. Every case must come out overall=FAIL with the exact
reason(s) asserted (fail-closed: no violation may surface as PASS or a
silent PENDING).

Recurrence scenarios guarded:
    (a) launcher pinning — NSIS silent install reset the desktop .lnk to
        LOCALAPPDATA instead of the D: install root,
    (b) body integrity — the update loop emptied resources\\app (45k -> 0),
    (c) data root / C residue — frozen DSH_HOME[HKCU] made the process
        fall back to the C:\\Users\\ALEX\\.dsh default root.
"""
from __future__ import annotations

import os
import sys
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "packages", "client-neutral-core", "scripts"))

import software_update_postflight as sup  # noqa: E402

DSH_INSTALL_ROOT = r"D:\All projects\DSH"
DSH_EXE = r"D:\All projects\DSH\DSH Desktop.exe"
DSH_DATA_ROOT = r"D:\All projects\DSH\.dsh"
DSH_LAUNCHER = r"D:\All projects\DSH\launch-dsh.cmd"
C_RESIDUE_DATA = r"C:\Users\ALEX\.dsh"
C_LOCALAPPDATA = r"C:\Users\ALEX\AppData\Local\DSH"


def _before() -> dict:
    return {
        "install_root": DSH_INSTALL_ROOT,
        "executable_realpath": DSH_EXE,
        "version": "2.0.12",
        "launcher_targets": [DSH_LAUNCHER],
        "data_root": DSH_DATA_ROOT,
    }


def _after(**overrides) -> dict:
    base = {
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
    base.update(overrides)
    return base


def _run(**overrides) -> dict:
    kwargs = dict(
        software_id="deepseek-harness",
        target_version="2.0.13",
        before=_before(),
        after=_after(),
        expected_install_root=DSH_INSTALL_ROOT,
        expected_data_root=DSH_DATA_ROOT,
        residue_watchlist=[C_RESIDUE_DATA, C_LOCALAPPDATA],
        expected_code_tree_files_min=40000,
        asar_expected=False,
        uninstaller_expected=True,
    )
    kwargs.update(overrides)
    return sup.run_postflight_checks(**kwargs)


def _status(record: dict, name: str) -> str:
    for c in record["checks"]:
        if c["name"] == name:
            return c["status"]
    raise AssertionError(f"check {name!r} missing from record")


class NegativeVersionReadbackTests(unittest.TestCase):
    def test_version_mismatch_fails_with_exact_reason(self):
        # Scenario (b): update loop rewrote the body; the readback still
        # reports the OLD version -> VERSION_READBACK_FAIL.
        record = _run(after=_after(version="2.0.12"))
        self.assertEqual(record["overall"], "FAIL")
        self.assertIn("VERSION_READBACK_FAIL", record["reasons"])
        self.assertIn("POSTFLIGHT_INCOMPLETE", record["reasons"])
        self.assertEqual(_status(record, "version_readback"), "FAIL")


class NegativeBodyIntegrityTests(unittest.TestCase):
    def test_code_tree_below_min_fails_with_exact_reason(self):
        # Scenario (b): resources\app emptied 45k -> 0 below the floor.
        record = _run(after=_after(code_tree_files=0))
        self.assertEqual(record["overall"], "FAIL")
        self.assertIn("BODY_INTEGRITY_FAIL", record["reasons"])
        self.assertEqual(_status(record, "body_integrity"), "FAIL")
        self.assertNotIn("VERSION_READBACK_FAIL", record["reasons"])

    def test_asar_residue_fails_when_unexpected(self):
        record = _run(after=_after(asar_residue=True))
        self.assertEqual(record["overall"], "FAIL")
        self.assertIn("BODY_INTEGRITY_FAIL", record["reasons"])
        self.assertEqual(_status(record, "body_integrity"), "FAIL")

    def test_missing_uninstaller_fails(self):
        record = _run(after=_after(uninstaller=None))
        self.assertEqual(record["overall"], "FAIL")
        self.assertIn("BODY_INTEGRITY_FAIL", record["reasons"])


class NegativeLauncherPinningTests(unittest.TestCase):
    def test_launcher_pointing_back_to_c_fails_with_exact_reason(self):
        # Scenario (a): NSIS silent install reset the .lnk to LOCALAPPDATA.
        record = _run(after=_after(launcher_targets=[C_LOCALAPPDATA]))
        self.assertEqual(record["overall"], "FAIL")
        self.assertIn("LAUNCHER_PINNING_FAIL", record["reasons"])
        self.assertEqual(_status(record, "launcher_pinning"), "FAIL")
        self.assertNotIn("DATA_ROOT_PINNING_FAIL", record["reasons"])

    def test_launcher_sibling_path_outside_root_fails(self):
        # A sibling of the install root ("d:/all projects/dsh2") is NOT
        # under the root — naive prefix matching must not pass it.
        record = _run(after=_after(launcher_targets=[r"D:\All projects\DSH2\launch.cmd"]))
        self.assertEqual(record["overall"], "FAIL")
        self.assertIn("LAUNCHER_PINNING_FAIL", record["reasons"])


class NegativeDataRootPinningTests(unittest.TestCase):
    def test_data_root_fallback_to_c_default_fails_with_exact_reason(self):
        # Scenario (c): frozen DSH_HOME[HKCU] -> process fell back to the
        # C: default data root.
        record = _run(after=_after(data_root=C_RESIDUE_DATA))
        self.assertEqual(record["overall"], "FAIL")
        self.assertIn("DATA_ROOT_PINNING_FAIL", record["reasons"])
        self.assertEqual(_status(record, "data_root_pinning"), "FAIL")
        self.assertNotIn("C_RESIDUE_DETECTED", record["reasons"])


class NegativeCResidueTests(unittest.TestCase):
    def test_c_residue_resurrection_fails_with_exact_reason(self):
        # Scenario (c) residue: a watched C-drive default path re-appeared
        # after the update.
        record = _run(after=_after(c_drive_residue=[C_RESIDUE_DATA]))
        self.assertEqual(record["overall"], "FAIL")
        self.assertIn("C_RESIDUE_DETECTED", record["reasons"])
        self.assertEqual(_status(record, "c_residue"), "FAIL")

    def test_unwatched_c_path_does_not_trigger_residue_reason(self):
        record = _run(
            after=_after(c_drive_residue=[r"C:\Users\ALEX\OneDrive\Notes\note.txt"]),
        )
        self.assertEqual(record["overall"], "PASS")
        self.assertEqual(record["reasons"], ["POSTFLIGHT_ALL_CHECKS_PASS"])
        self.assertEqual(_status(record, "c_residue"), "PASS")


class NegativeRuntimeHealthTests(unittest.TestCase):
    def test_runtime_health_fail_sets_overall_fail(self):
        record = _run(after=_after(runtime_health="FAIL"))
        self.assertEqual(record["overall"], "FAIL")
        self.assertIn("RUNTIME_HEALTH_FAIL", record["reasons"])
        self.assertEqual(_status(record, "runtime_health"), "FAIL")


class NegativeLocationReadbackTests(unittest.TestCase):
    def test_install_root_moved_after_update_fails_with_exact_reason(self):
        # §42: after a plain UPDATE the real install root must be re-read
        # and unchanged; a move to a sibling path is LOCATION_READBACK_FAIL.
        record = _run(after=_after(install_root=r"D:\All projects\DSH-NEW"))
        self.assertEqual(record["overall"], "FAIL")
        self.assertIn("LOCATION_READBACK_FAIL", record["reasons"])
        self.assertEqual(_status(record, "location_readback"), "FAIL")
        self.assertFalse(record["location_readback_passed"])

    def test_missing_after_root_is_unverified_not_pass(self):
        record = _run(after=_after(install_root=None))
        # Missing after root cannot be fabricated as a readback PASS.
        self.assertEqual(_status(record, "location_readback"), "UNVERIFIED")
        self.assertFalse(record["location_readback_passed"])
        self.assertEqual(record["overall"], "PENDING")


if __name__ == "__main__":
    unittest.main()
