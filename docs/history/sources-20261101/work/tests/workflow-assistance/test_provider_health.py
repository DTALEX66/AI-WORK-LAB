from __future__ import annotations

import json
import tempfile
from pathlib import Path
import sys
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "workflow"))

from provider_health import build_report, configured_models, main  # noqa: E402


class ProviderHealthTests(unittest.TestCase):
    def test_default_config_without_provider_is_fail_closed(self) -> None:
        config = {"model": {}, "model_picker": {"custom_lanes": {"lanes": []}}}
        self.assertEqual(configured_models(config), {})
        report = build_report(config, live=False)
        self.assertEqual(report["overall_status"], "UNVERIFIED")
        self.assertEqual(report["models"], {})

    def test_build_report_marks_unverified_without_live(self) -> None:
        config = {"model_picker": {"custom_lanes": {"lanes": [{"provider": "deepseek", "models": ["m1"]}]}}}
        report = build_report(config, live=False)
        key = "deepseek/m1"
        self.assertIn(key, report["models"])
        self.assertEqual(report["models"][key]["status"], "UNVERIFIED")
        self.assertEqual(report["overall_status"], "UNVERIFIED")

    def test_build_report_live_propagates_ok(self) -> None:
        config = {"model_picker": {"custom_lanes": {"lanes": [{"provider": "deepseek", "models": ["m1"]}]}}}
        with mock.patch("provider_health.live_check", return_value="LIVE_OK"):
            report = build_report(config, live=True)
        self.assertEqual(report["overall_status"], "LIVE_OK")
        self.assertEqual(report["models"]["deepseek/m1"]["status"], "LIVE_OK")

    def test_main_explicit_lane_requires_live(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            config = Path(raw) / "config.yaml"
            config.write_text("model: {}\n", encoding="utf-8")
            out = Path(raw) / "out.json"
            with self.assertRaises(SystemExit) as ctx:
                main(["--config", str(config), "--output", str(out), "--provider", "deepseek", "--model", "m1"])
            self.assertEqual(ctx.exception.code, 2)

    def test_main_explicit_lane_report_shape(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            config = Path(raw) / "config.yaml"
            config.write_text("model: {}\n", encoding="utf-8")
            out = Path(raw) / "out.json"
            with mock.patch("provider_health.live_check", return_value="LIVE_OK"):
                rc = main(["--config", str(config), "--output", str(out), "--live", "--provider", "deepseek", "--model", "m1"])
            self.assertEqual(rc, 0)
            report = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(report["overall_status"], "LIVE_OK")
            self.assertEqual(report["explicit"], True)
            self.assertTrue(report["secret_free"])
            self.assertIn("deepseek/m1", report["models"])


if __name__ == "__main__":
    unittest.main()
