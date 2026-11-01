# SPDX-License-Identifier: MIT
"""Behavioral contracts for bounded diff-guided reconstruction repair."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "design-lab"))
sys.path.insert(0, str(PROJECT_ROOT / "packages" / "capabilities"))


class ReconstructionRepairTests(unittest.TestCase):
    def setUp(self) -> None:
        self.rir = {
            "schemaVersion": "design-lab/reconstruction-ir/v1",
            "canvas": {"width": 10, "height": 10, "colorSpace": "srgb"},
            "layers": [],
        }

    def test_regressing_repair_is_discarded_without_mutating_input(self) -> None:
        """A lower-quality proposal cannot replace an editable scene even when its patch is valid."""
        from reconstruction.repair import RepairMetrics, RepairPlan, hash_rir, repair_once

        before = RepairMetrics(0.997, 0.997, 0.01, ())
        regressing = RepairMetrics(0.996, 0.999, 0.001, ())
        result = repair_once(
            self.rir,
            before,
            lambda _rir, _metrics: RepairPlan("set-canvas-background", {"color": "#ffffff"}),
            lambda _candidate: regressing,
        )

        self.assertFalse(result.accepted)
        self.assertEqual(result.rir_hash, hash_rir(self.rir))
        self.assertNotIn("background", self.rir["canvas"])

    def test_iteration_budget_returns_partial_not_pass(self) -> None:
        """Exhausting a global repair budget is partial work, never verification evidence."""
        from reconstruction.repair import RepairMetrics, RepairPlan, optimize

        before = RepairMetrics(0.9, 0.9, 0.2, ())
        result = optimize(
            self.rir,
            before,
            lambda _rir, _metrics: RepairPlan("set-canvas-background", {"color": "#000000"}),
            lambda _candidate: RepairMetrics(0.91, 0.91, 0.19, ()),
            global_budget=1,
        )

        self.assertEqual(result.state, "PARTIAL")
        self.assertEqual(result.iterations, 1)


if __name__ == "__main__":
    unittest.main()
