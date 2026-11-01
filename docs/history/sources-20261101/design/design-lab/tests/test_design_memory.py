# SPDX-License-Identifier: MIT
"""DL-V2 P1-D: design memory tests."""
from __future__ import annotations

import unittest
from pathlib import Path

_CORE = Path(__file__).resolve().parents[1] / "core"


def _load(name):
    import importlib.util
    import sys
    p = _CORE / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"dl_mem_{name}", p)
    m = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = m
    spec.loader.exec_module(m)
    return m


_mem = _load("memory")


class MemoryIngestTests(unittest.TestCase):
    def _good(self):
        return {"id": "mem_u_1", "schemaVersion": "design-lab/design-memory/v1", "type": "semantic",
                "domain": "test", "title": "x", "statement": "a test rule statement", "confidence": 0.5,
                "created_by": "t", "created_at": "2026-08-16T00:00:00Z", "status": "candidate"}

    def test_valid_candidate_accepted(self):
        st, msg = _mem.ingest(self._good(), [])
        self.assertEqual(st, "validated", msg)
        self.assertEqual(msg, "accepted")

    def test_high_confidence_requires_evidence(self):
        rec = self._good()
        rec["confidence"] = 0.95
        st, msg = _mem.ingest(rec, [])
        self.assertEqual(st, "rejected")
        self.assertIn("evidence", msg)

    def test_duplicate_rejected(self):
        st, _ = _mem.ingest(self._good(), [self._good()])
        self.assertEqual(st, "rejected")

    def test_non_candidate_rejected(self):
        rec = self._good()
        rec["status"] = "active"
        st, _ = _mem.ingest(rec, [])
        self.assertEqual(st, "rejected")


if __name__ == "__main__":
    unittest.main()
