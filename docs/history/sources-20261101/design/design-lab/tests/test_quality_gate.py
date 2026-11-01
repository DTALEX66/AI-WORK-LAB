# SPDX-License-Identifier: MIT
"""DL-V2 P1-E: quality gate tests."""
from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

_CORE = Path(__file__).resolve().parents[1] / "core"


def _load(name):
    import sys
    p = _CORE / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"dl_qg_{name}", p)
    m = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = m
    spec.loader.exec_module(m)
    return m


_qg = _load("quality_gate")
GATE = {
    "schemaVersion": "packages/capabilities/quality-gate/v1", "gate_id": "test",
    "minimum_total": 82,
    "minimum_dimensions": {"production_readiness": 95},
    "blocking_rules": ["insufficient_bleed"],
    "dimensions": [{"id": "production_readiness", "title": "p", "weight": 100}],
}


class QualityGateTests(unittest.TestCase):
    def test_blocker_fails_high_score(self):
        res = _qg.evaluate({"production_readiness": 100}, GATE, ["insufficient_bleed"])
        self.assertEqual(res["decision"], "fail")

    def test_below_minimum_fails(self):
        res = _qg.evaluate({"production_readiness": 68}, GATE, [])
        self.assertEqual(res["decision"], "fail")
        self.assertTrue(any("below_minimum" in b for b in res["blocking_issues"]))

    def test_clean_passes(self):
        res = _qg.evaluate({"production_readiness": 96}, GATE, [])
        self.assertEqual(res["decision"], "pass")


if __name__ == "__main__":
    unittest.main()
