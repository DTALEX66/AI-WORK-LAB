"""Tests for the Beads Task Graph POC (WL-P0-180 / ch 22).

This is a *comparison* POC, so the tests pin the two things that make it
meaningful rather than a port:

* the SSOT verdict is always False (taskpack mandate) AND it is grounded in
  the actual capability map — not a hard-coded string;
* the report is deterministic and hashable, so the verdict is reproducible
  offline.

Repo convention (mirrors the other test files here): load the service file
by spec, pre-register in sys.modules.
"""
from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TG = ROOT / "services" / "task-graph"


def _load():
    spec = importlib.util.spec_from_file_location("tg_beads_poc", TG / "beads_poc.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class BeadsPocTests(unittest.TestCase):
    def test_ssot_is_false_and_mandated(self):
        m = _load()
        self.assertFalse(m.conclude_ssot())
        rep = m.assess()
        self.assertFalse(rep.beads_as_ssot)

    def test_coverage_is_grounded_in_capability_map(self):
        # The "covered" count must equal the number of COVERED rows in the
        # map — if someone edits the map, this catches the report drifting.
        m = _load()
        rep = m.assess()
        covered = sum(1 for c in rep.coverage.values() if c == "covered")
        self.assertEqual(rep.covered_count, covered)
        self.assertEqual(rep.total_count, len(m.BeadsCapability))

    def test_missing_dimensions_are_the_ssot_blockers(self):
        # Every dimension the report calls a blocker must be one that the
        # capability map marks ssot_blocker=True — the conclusion is the
        # map's, not a re-statement.
        m = _load()
        rep = m.assess()
        expected_blockers = {
            cap.value for cap in m.BeadsCapability
            if m.CAPABILITY_MAP[cap].ssot_blocker
        }
        self.assertEqual(set(rep.blockers), expected_blockers)
        # and each reason line comes from a MISSING assessment
        missing = {
            cap.value for cap in m.BeadsCapability
            if m.CAPABILITY_MAP[cap].coverage is m.Coverage.MISSING
        }
        self.assertEqual(missing, set(rep.blockers))

    def test_report_is_deterministic_and_hashed(self):
        m = _load()
        a, b = m.assess(), m.assess()
        self.assertEqual(a.to_json(), b.to_json())
        self.assertEqual(a.receipt_sha256, b.receipt_sha256)
        # the receipt is a real sha256 (64 hex chars)
        self.assertEqual(len(a.receipt_sha256), 64)
        int(a.receipt_sha256, 16)  # raises if not hex

    def test_every_map_row_names_a_real_api_or_gap(self):
        # No row may be empty: each has an API (or an explicit "(none)")
        # and non-empty evidence, so the report is inspection-ready.
        m = _load()
        for cap in m.BeadsCapability:
            row = m.CAPABILITY_MAP[cap]
            self.assertTrue(row.task_ledger_api.strip())
            self.assertTrue(row.evidence.strip())
            self.assertTrue(row.beads_note.strip())

    def test_recommendations_advise_against_dolt_adoption(self):
        m = _load()
        rep = m.assess()
        joined = " ".join(rep.recommendations)
        self.assertIn("Do not adopt Beads' Dolt backend", joined)
        self.assertIn("TaskLedger", joined)  # keeps TaskLedger as SSOT


if __name__ == "__main__":
    unittest.main(verbosity=2)
