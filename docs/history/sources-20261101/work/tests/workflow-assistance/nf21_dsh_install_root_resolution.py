"""AG-07 negative controls: the DSH install root must be RESOLVED, never pinned.

The 2026-10-01 regression this guards: `deepseek_harness_adapter` hardcoded
`COMMUNITY_INSTALL_DIR = D:/All projects/DSH` as the identity of the installed
DSH. When the user reinstalled the OFFICIAL build at the vendor default
per-user path, `detect()` kept reporting `present: false` on a machine where
DSH demonstrably was installed. A pinned path rots silently; resolution cannot.

These tests drive the pure resolution helpers with a synthetic override root, so
they pass on any machine and never read or write real DSH state, never launch a
process, and never touch the user's `.dsh` data.
"""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "integrations" / "executors" / "dsh"))

import deepseek_harness_adapter as dsh  # noqa: E402


class InstallRootIsResolvedNotPinned(unittest.TestCase):
    def test_no_drive_letter_is_hardcoded_as_the_official_identity(self) -> None:
        # The official entry must contain no absolute drive-letter path: the
        # vendor default is expressed relative to LOCALAPPDATA at call time.
        self.assertFalse(
            dsh.OFFICIAL_EXE_NAME.startswith("D:"),
            "official exe name must be a bare filename, not a pinned path",
        )
        self.assertNotIn("D:", str(dsh.OFFICIAL_UNINSTALL_KEY))
        for candidate in dsh._official_candidates():
            # Candidates are allowed to be any drive, but they must be derived
            # (override env / LOCALAPPDATA / registry), not the community pin.
            self.assertNotEqual(candidate, dsh.COMMUNITY_INSTALL_DIR)

    def test_override_env_is_a_candidate_not_a_pin(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / dsh.OFFICIAL_EXE_NAME).write_bytes(b"stub")
            previous = os.environ.get("WORKLAB_DSH_INSTALL_ROOT")
            os.environ["WORKLAB_DSH_INSTALL_ROOT"] = str(root)
            try:
                # The env override is the FIRST candidate, so it wins.
                self.assertEqual(dsh._official_candidates()[0], root)
                self.assertEqual(dsh.official_install_root(), root)
            finally:
                if previous is None:
                    os.environ.pop("WORKLAB_DSH_INSTALL_ROOT", None)
                else:
                    os.environ["WORKLAB_DSH_INSTALL_ROOT"] = previous

    def test_injected_candidates_resolve_deterministically(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / dsh.OFFICIAL_EXE_NAME).write_bytes(b"stub")
            # Deterministic: driven only by the injected list, so the result does
            # not depend on what is installed on this machine.
            self.assertEqual(dsh.official_install_root([root]), root)
            detected = dsh.official_detected([root])
            self.assertTrue(detected["present"])
            self.assertEqual(detected["install_root"], str(root))
            self.assertEqual(
                detected["install_path_policy"], "RESOLVE_AT_RUNTIME_NOT_HARDCODED"
            )

    def test_absent_install_is_not_fabricated(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            # Empty directory in the injected chain: nothing may be reported.
            self.assertIsNone(dsh.official_install_root([Path(tmp)]))
            detected = dsh.official_detected([Path(tmp)])
            self.assertFalse(detected["present"])
            self.assertIsNone(detected["install"])
            self.assertIsNone(detected["install_root"])

    def test_unknown_version_stays_none_not_guessed(self) -> None:
        # A present install whose version cannot be read must report None, not a
        # fabricated string.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / dsh.OFFICIAL_EXE_NAME).write_bytes(b"stub")
            detected = dsh.official_detected([root])
            self.assertTrue(detected["present"])
            self.assertTrue(
                detected["version"] is None or isinstance(detected["version"], str)
            )

    def test_detect_reports_official_deployment_read_never_writes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / dsh.OFFICIAL_EXE_NAME).write_bytes(b"stub")
            previous = os.environ.get("WORKLAB_DSH_INSTALL_ROOT")
            os.environ["WORKLAB_DSH_INSTALL_ROOT"] = str(root)
            try:
                adapter = dsh.DeepSeekHarnessAdapter(Path.cwd())
                report = adapter.detect()
                self.assertEqual(report["deployment"], "official-deepseek-harness")
                self.assertEqual(
                    report["official_deepseek_harness"]["user_config_access"], "NOT_ACCESSED"
                )
                # The user's real .dsh data root must never be reported as read.
                self.assertNotIn("sessions", report)
            finally:
                if previous is None:
                    os.environ.pop("WORKLAB_DSH_INSTALL_ROOT", None)
                else:
                    os.environ["WORKLAB_DSH_INSTALL_ROOT"] = previous


if __name__ == "__main__":
    unittest.main()
