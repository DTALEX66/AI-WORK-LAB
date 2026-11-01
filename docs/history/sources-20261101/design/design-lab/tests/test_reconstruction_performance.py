# SPDX-License-Identifier: MIT
"""Performance-routing contracts for bounded 8GB reconstruction execution."""
from __future__ import annotations

import sys
import json
import subprocess
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "design-lab"))
sys.path.insert(0, str(PROJECT_ROOT / "packages" / "capabilities"))


class ReconstructionPerformanceTests(unittest.TestCase):
    def test_eight_gb_profile_never_requires_large_models(self) -> None:
        from reconstruction.performance import HardwareProfile, select_runtime_plan

        plan = select_runtime_plan(HardwareProfile(vram_mib=8151), "mixed")

        self.assertIn("vtracer", plan.required_providers)
        self.assertEqual(plan.tile_size, 1024)
        self.assertEqual(plan.resolution_scale, 1.0)
        self.assertNotIn("omnisvg-4b", plan.required_providers)
        self.assertNotIn("qwen-image-layered", plan.required_providers)

    def test_timing_event_requires_observed_positive_duration(self) -> None:
        from reconstruction.performance import TimingEvent, validate_event

        event = validate_event(TimingEvent("render", 12.5, "cold"))

        self.assertEqual(event.duration_ms, 12.5)
        with self.assertRaises(ValueError):
            validate_event(TimingEvent("render", 0.0, "cold"))

    def test_low_vram_plan_is_explicitly_cpu_fallback_without_downscaling(self) -> None:
        from reconstruction.performance import HardwareProfile, select_runtime_plan

        plan = select_runtime_plan(HardwareProfile(vram_mib=4096), "poster")

        self.assertEqual(plan.optional_providers, ("sam2-cpu",))
        self.assertEqual(plan.tile_size, 1024)
        self.assertEqual(plan.resolution_scale, 1.0)

    def test_benchmark_cli_writes_validated_ndjson_event(self) -> None:
        script = PROJECT_ROOT / "design-lab" / "scripts" / "benchmark_reconstruction.py"
        with tempfile.TemporaryDirectory() as raw_dir:
            output = Path(raw_dir) / "events.ndjson"
            result = subprocess.run(
                [
                    sys.executable,
                    str(script),
                    "--stage", "inference",
                    "--temperature", "cold",
                    "--duration-ms", "12.5",
                    "--output",
                    str(output),
                ],
                check=False,
                capture_output=True,
                text=True, encoding="utf-8", errors="replace",
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(output.read_text(encoding="utf-8").strip())
            self.assertEqual(payload["stage"], "inference")
            self.assertEqual(payload["durationMs"], 12.5)
            self.assertEqual(payload["temperature"], "cold")


if __name__ == "__main__":
    unittest.main()
