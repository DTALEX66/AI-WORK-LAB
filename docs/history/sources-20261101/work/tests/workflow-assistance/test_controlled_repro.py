"""Contract tests for controlled repro of launcher/config drift (WL3-120)."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from controlled_repro import controlled_repro, fingerprint_metadata


class ControlledReproTests(unittest.TestCase):
    def test_no_metadata_change_classifies_clean(self) -> None:
        result = controlled_repro(
            [{"layer": "official_config", "before": {"d": "a"}, "after": {"d": "a"}}]
        )
        self.assertEqual(result["classification"], "NO_METADATA_CHANGE")

    def test_official_config_change_classifies_config_layer(self) -> None:
        result = controlled_repro(
            [
                {"layer": "official_config", "before": {"digest": "x"}, "after": {"digest": "y"}},
                {"layer": "project_overlay", "before": 1, "after": 1},
            ]
        )
        self.assertEqual(result["classification"], "CONFIG_LAYER_CHANGED")

    def test_desktop_internal_change_classifies_platform_state(self) -> None:
        result = controlled_repro(
            [{"layer": "desktop_internal", "before": {"size": 1}, "after": {"size": 2}}]
        )
        self.assertEqual(result["classification"], "PLATFORM_INTERNAL_STATE_CHANGED")

    def test_fingerprint_never_reads_private_body(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / ".codex-global-state.json"
            path.write_text('{"secret": "should-not-leak"}', encoding="utf-8")
            meta = fingerprint_metadata(path)
            self.assertTrue(meta["exists"])
            self.assertNotIn("secret", str(meta))
            self.assertEqual(len(meta["digest"]), 64)

    def test_missing_path_reports_unavailable(self) -> None:
        meta = fingerprint_metadata(Path("C:/definitely/not/here.json"))
        self.assertFalse(meta["exists"])


if __name__ == "__main__":
    unittest.main()
