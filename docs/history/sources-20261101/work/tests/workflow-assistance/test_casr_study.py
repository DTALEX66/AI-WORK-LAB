"""Tests for the CASR architecture study (WL-P1-100 / ch 14).

ch 14 is REFERENCE_ONLY by design: the upstream cross_agent_session_resumer
carries a license rider, so WORK-LAB must not port its core.  This module
only maps the six ch 14 capability dimensions onto WORK-LAB's own
session-federation components and reaches the structural REFERENCE_ONLY
verdict.  Tests lock that shape in.
"""
from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SF = ROOT / "services" / "session-federation"


def _load(name: str, module_name: str):
    spec = importlib.util.spec_from_file_location(module_name, SF / name)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


class CasrStudyTests(unittest.TestCase):

    def _study(self, **kw):
        cs = _load("casr_study.py", "sf_cs")
        return cs, cs.CasrStudyBuilder().build(**kw)

    def test_status_is_reference_only(self):
        cs, study = self._study()
        self.assertEqual(study.status, "REFERENCE_ONLY")
        self.assertEqual(study.target, "cross_agent_session_resumer")
        self.assertTrue("rider" in study.license_rider)

    def test_six_dimensions_all_reference_only(self):
        cs, study = self._study()
        self.assertEqual(len(study.dimensions), 6)
        for d in study.dimensions:
            self.assertTrue(d.reference_only)          # ch 14 hard rule
            self.assertIn(d.dimension, cs.CapabilityDimension.ALL)

    def test_worklab_coverage_maps_every_dimension(self):
        cs, study = self._study()
        for d in study.dimensions:
            # every dimension is mapped to a real WORK-LAB component
            self.assertNotEqual(d.worklab_coverage, "no direct component")

    def test_verdict_never_ports_the_upstream_core(self):
        cs, study = self._study()
        v = cs.CasrStudyBuilder.verdict(study)
        self.assertIs(v["port_upstream_core"], False)
        self.assertEqual(v["status"], "REFERENCE_ONLY")
        # the majority of the capability is already on WORK-LAB's own plane
        self.assertGreater(len(v["worklab_already_covers"]), 0)

    def test_custom_assessment_must_be_valid(self):
        cs, study = self._study()
        with self.assertRaises(ValueError):
            cs.CasrStudyBuilder().build(
                assessments={cs.CapabilityDimension.CANONICAL_IR: "made_up"})
        # a valid GAP assessment is accepted and reflected
        _, s2 = self._study(
            assessments={cs.CapabilityDimension.NATIVE_WRITER: "gap"})
        nd = next(d for d in s2.dimensions if d.dimension == "native_writer")
        self.assertEqual(nd.assessment, "gap")

    def test_full_study_receipt_is_deterministic(self):
        cs = _load("casr_study.py", "sf_cs")
        r1 = cs.full_study_receipt(cs.CasrStudyBuilder().build())
        r2 = cs.full_study_receipt(cs.CasrStudyBuilder().build())
        self.assertEqual(r1["receipt_sha256"], r2["receipt_sha256"])
        int(r1["receipt_sha256"], 16)


if __name__ == "__main__":
    unittest.main(verbosity=2)
