"""Contract tests for tiered future-agent onboarding (WL3-710)."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tiered_adapters import MANIFEST_ONLY, probe_level, tier_matrix


class TieredAdaptersTests(unittest.TestCase):
    def test_core_platforms_are_l4_real_conformance(self) -> None:
        matrix = tier_matrix()
        for platform in ("hermes", "codex", "cc-switch", "github"):
            self.assertEqual(matrix["rows"][platform]["level"], "L4")
            self.assertEqual(matrix["rows"][platform]["basis"], "real-conformance")

    def test_uninstalled_future_platform_is_l0_and_never_fails_core(self) -> None:
        result = probe_level("cursor", executable="cursor-nonexistent", manifest={"name": "cursor"})
        self.assertEqual(result["level"], "L0")
        self.assertFalse(result["installed"])
        self.assertFalse(result["apply_allowed"])

    def test_manifest_only_platform_without_probe_stays_l0(self) -> None:
        result = probe_level("workbuddy", executable=None, manifest={"name": "workbuddy"})
        self.assertEqual(result["level"], "L0")
        self.assertEqual(result["basis"], "manifest-only")

    def test_probe_with_config_root_raises_to_l1(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            config_root = Path(temporary)
            result = probe_level(
                "claude-code",
                executable="claude-nonexistent",
                config_root=config_root,
                manifest={"name": "claude-code"},
            )
            self.assertEqual(result["level"], "L0")  # not installed -> L0 regardless

    def test_detection_never_grants_apply(self) -> None:
        result = probe_level("qwen-code", executable=None, manifest={"name": "qwen-code"})
        self.assertFalse(result["apply_allowed"])

    def test_manifest_only_platforms_registered(self) -> None:
        self.assertEqual(MANIFEST_ONLY, {"cursor", "claude-code", "workbuddy", "qwen-code"})


if __name__ == "__main__":
    unittest.main()
