"""NX-710 regression report tests."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "ci"))

from regression_report import run_report  # noqa: E402


class RegressionReportTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.report = run_report()

    def test_report_has_current_tree_and_baseline_metadata(self) -> None:
        self.assertEqual(self.report["schemaVersion"], "work-lab/regression-report/v1")
        self.assertGreater(self.report["tree"]["trackedFiles"], 0)
        self.assertGreater(self.report["tree"]["trackedBytes"], 0)
        self.assertIn(self.report["baseline"]["baselineStatus"], ("COMPARABLE_TO_PARENT_COMMIT", "NOT_AVAILABLE"))

    def test_performance_has_p50_p95_and_bounded_latency(self) -> None:
        self.assertEqual(set(self.report["performance"]), {"usageRollup", "designContract", "offlinePilot"})
        for metric in self.report["performance"].values():
            self.assertEqual(metric["samples"], 25)
            self.assertGreaterEqual(metric["p50Ms"], 0)
            self.assertLess(metric["p50Ms"], 5000)
            self.assertLess(metric["p95Ms"], 5000)

    def test_dedup_and_unknown_cost_semantics(self) -> None:
        quality = self.report["quality"]
        self.assertEqual(quality["tokenDedupCount"], quality["tokenDedupExpected"])
        self.assertEqual(quality["unknownModelCostStatus"], "unknown")

    def test_boundary_semantics(self) -> None:
        self.assertEqual(self.report["quality"]["contaminationControls"], 7)
        self.assertEqual(self.report["quality"]["observerMutationSurface"], [])
        self.assertFalse(self.report["boundaries"]["network"])
        self.assertFalse(self.report["boundaries"]["credentials"])
        self.assertFalse(self.report["boundaries"]["externalWrites"])


if __name__ == "__main__":
    unittest.main()
