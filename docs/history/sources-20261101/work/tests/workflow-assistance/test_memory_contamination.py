"""NX-400: memory contamination negative controls.

RED-GREEN coverage of the 7 contamination cases.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WF_SCRIPTS = ROOT / "packages" / "client-neutral-core" / "scripts"
sys.path.insert(0, str(WF_SCRIPTS))

from memory_contamination import MemoryGuard, MemoryRecord  # noqa: E402


class MemoryContaminationTest(unittest.TestCase):
    def setUp(self) -> None:
        self.g = MemoryGuard()

    def test_cross_project_contamination_fail_closed(self) -> None:
        r = self.g.cross_project_contamination("projA", "projB")
        self.assertEqual(r.outcome, "fail-closed")

    def test_same_project_pass(self) -> None:
        r = self.g.cross_project_contamination("projA", "projA")
        self.assertEqual(r.outcome, "pass")

    def test_new_instruction_supersedes_old_preference(self) -> None:
        old = MemoryRecord(project_id="p", fact="old", source="user", version="1.0")
        new = MemoryRecord(project_id="p", fact="new", source="user", version="2.0")
        r = self.g.old_preference_overrides_new_instruction(old, new)
        self.assertTrue(old.superseded)

    def test_expired_version_quarantined(self) -> None:
        rec = MemoryRecord(project_id="p", fact="old", source="user", version="1.0", expiry="2026-01-01")
        r = self.g.expired_injection(rec, now_version="2.0")
        self.assertEqual(r.outcome, "fail-closed")
        self.assertTrue(rec.quarantined)

    def test_malicious_skill_no_global_promotion(self) -> None:
        rec = MemoryRecord(project_id="p", fact="claim", source="skill")
        r = self.g.malicious_skill_promotion(rec)
        self.assertEqual(r.outcome, "quarantine")
        self.assertTrue(rec.quarantined)

    def test_weight_inflation_capped(self) -> None:
        rec = MemoryRecord(project_id="p", fact="f", source="user")
        r = self.g.weight_inflation(rec, summaries=5)
        self.assertEqual(rec.weight, 1)

    def test_compression_loses_safety_fail_closed(self) -> None:
        rec = MemoryRecord(project_id="p", fact="f", source="user", safety_boundary=None)
        r = self.g.compression_loses_safety(rec, compressed=True)
        self.assertEqual(r.outcome, "fail-closed")
        self.assertTrue(rec.quarantined)

    def test_unsourced_inference_quarantined(self) -> None:
        rec = MemoryRecord(project_id="p", fact="guess", source="inference")
        r = self.g.unsourced_inference(rec)
        self.assertEqual(r.outcome, "quarantine")
        self.assertTrue(rec.quarantined)

    def test_seven_negative_controls_present(self) -> None:
        from memory_contamination import run_all_negative_controls
        results = run_all_negative_controls()
        self.assertEqual(len(results), 7)


if __name__ == "__main__":
    unittest.main()
