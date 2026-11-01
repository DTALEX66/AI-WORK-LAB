"""NX-510: design production & quality evidence tests.

RED-GREEN coverage:
- Tool capability probes report available/unavailable honestly (no fake).
- SVG preflight rejects malicious inline scripts, passes safe SVG.
- SPDX/REUSE manifest is reuse-compliant.
- Fixture closures exist and stay WAITING_HUMAN_CALIBRATION until human calibrates.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WF_SCRIPTS = ROOT / "packages" / "client-neutral-core" / "scripts"
sys.path.insert(0, str(WF_SCRIPTS))

from production_evidence import (  # noqa: E402
    probe_tools, svg_preflight, spdx_manifest, SpdxEntry,
    run_fixture_closures, evaluate_fixture, VisualFixture,
)


class ProductionEvidenceTest(unittest.TestCase):
    def test_tool_probes_honest(self) -> None:
        probes = probe_tools()
        self.assertEqual(len(probes), 5)
        for status in probes.values():
            self.assertIn(status, ("available", "unavailable"))

    def test_svg_preflight_rejects_malicious(self) -> None:
        bad = '<svg><script>alert(1)</script></svg>'
        self.assertTrue(svg_preflight(bad))

    def test_svg_preflight_passes_safe(self) -> None:
        safe = '<svg xmlns="http://www.w3.org/2000/svg"><rect width="10" height="10"/></svg>'
        self.assertEqual(svg_preflight(safe), [])

    def test_svg_preflight_rejects_empty(self) -> None:
        self.assertTrue(svg_preflight(""))

    def test_spdx_manifest_reuse_compliant(self) -> None:
        m = spdx_manifest([SpdxEntry("a", "https://x", "MIT", "MIT", "1.0", "workflow")])
        self.assertTrue(m["reuseCompliant"])
        self.assertEqual(m["count"], 1)

    def test_fixture_stays_waiting_human_calibration(self) -> None:
        r = evaluate_fixture(VisualFixture("brand", "brand", checks_passed=5, checks_total=5))
        self.assertEqual(r.calibration_status, "WAITING_HUMAN_CALIBRATION")

    def test_fixture_calibrated_after_human(self) -> None:
        r = evaluate_fixture(VisualFixture("brand", "brand", checks_passed=5, checks_total=5, human_calibrated=True))
        self.assertEqual(r.calibration_status, "CALIBRATED")

    def test_auto_score_in_range(self) -> None:
        for fx in run_fixture_closures():
            self.assertIsNotNone(fx.auto_score)
            self.assertTrue(0 <= fx.auto_score <= 1)

    def test_at_least_two_fixture_categories(self) -> None:
        results = run_fixture_closures()
        self.assertGreaterEqual(len(results), 2)


if __name__ == "__main__":
    unittest.main()
