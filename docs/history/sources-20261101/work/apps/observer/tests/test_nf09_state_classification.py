"""NF-09 Observer read-only state classification contract tests.

Locks the five-way split NF-09 demands (LIVE / ACTUAL_ZERO / STALE / UNKNOWN /
UNAUTHORIZED), the three evidence chains (real metadata chain, broken chain,
unauthorized client), the read-only guarantee (the classifier and the
projection's mutation surface never change execution state), and that every
result carries its source time + scope.  Pure, deterministic, no network /
credentials / paid calls; the state classifier is loaded by file path.
"""
from __future__ import annotations

import importlib.util
import os
import sys
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
MOD = os.path.join(ROOT, "apps", "observer", "src", "observer_state_classification.py")


def _load():
    spec = importlib.util.spec_from_file_location("nf09_state", MOD)
    m = importlib.util.module_from_spec(spec)
    sys.modules["nf09_state"] = m
    spec.loader.exec_module(m)
    return m


def _live_ev(active=2):
    return {"authorized": True, "freshness": "fresh", "quality": "exact",
            "active_tasks": active, "source_time": "2026-09-16T00:00:00Z", "scope": "work-lab"}


class StateClassificationTests(unittest.TestCase):
    def setUp(self):
        self.m = _load()

    def test_five_states_are_distinct(self):
        m = self.m
        self.assertEqual(m.state_enum(), (m.LIVE, m.ACTUAL_ZERO, m.STALE, m.UNKNOWN, m.UNAUTHORIZED))
        self.assertEqual(len(m.state_enum()), 5)
        # each representative evidence lands in a different bucket
        self.assertEqual(m.classify_client_state(_live_ev(3))["state"], m.LIVE)
        self.assertEqual(m.classify_client_state(_live_ev(0))["state"], m.ACTUAL_ZERO)
        stale = dict(_live_ev(1), freshness="stale")
        self.assertEqual(m.classify_client_state(stale)["state"], m.STALE)
        unknown = dict(_live_ev(1), quality="unknown")
        self.assertEqual(m.classify_client_state(unknown)["state"], m.UNKNOWN)
        unauth = dict(_live_ev(1), authorized=False)
        self.assertEqual(m.classify_client_state(unauth)["state"], m.UNAUTHORIZED)

    def test_real_metadata_chain_is_live(self):
        r = self.m.classify_client_state(_live_ev(4))
        self.assertEqual(r["state"], self.m.LIVE)
        self.assertTrue(r["counted_in_active"])
        self.assertEqual(r["contributes_active"], 4)
        self.assertEqual(r["source_time"], "2026-09-16T00:00:00Z")
        self.assertEqual(r["scope"], "work-lab")

    def test_broken_chain_is_stale_not_live(self):
        r = self.m.classify_client_state(dict(_live_ev(1), freshness="delayed"))
        self.assertEqual(r["state"], self.m.STALE)
        self.assertFalse(r["counted_in_active"])

    def test_unauthorized_client_excluded_from_active(self):
        r = self.m.classify_client_state(dict(_live_ev(9), authorized=False))
        self.assertEqual(r["state"], self.m.UNAUTHORIZED)
        self.assertFalse(r["counted_in_active"])
        self.assertEqual(r["contributes_active"], 0)

    def test_actual_zero_is_not_unknown(self):
        r = self.m.classify_client_state(_live_ev(0))
        self.assertEqual(r["state"], self.m.ACTUAL_ZERO)
        self.assertEqual(r["contributes_active"], 0)
        self.assertTrue(r["counted_in_active"] is False)  # zero active, not live-counted

    def test_tally_counts_only_live(self):
        m = self.m
        data = {
            "hermes": _live_ev(3),
            "codex": dict(_live_ev(0), authorized=True),          # actual zero
            "dsh": dict(_live_ev(5), authorized=False),           # unauthorized
            "ccswitch": dict(_live_ev(2), quality="unknown"),     # unknown
        }
        out = m.classify_all(data)
        self.assertEqual(out["tally"]["clients"], 4)
        self.assertEqual(out["tally"]["active_tasks"], 3)  # only LIVE contributes
        self.assertEqual(out["tally"]["by_state"].get("UNAUTHORIZED"), 1)
        self.assertEqual(out["tally"]["by_state"].get("UNKNOWN"), 1)

    def test_classifier_is_read_only(self):
        m = self.m
        r = m.classify_client_state(_live_ev(2))
        self.assertFalse(r["mutates_execution_state"])
        projection = {"mutationSurface": {"externalMutation": False, "ledgerMutation": False,
                                           "approvalMutation": False, "gitControl": False}}
        surface = m.assert_read_only(projection)
        self.assertTrue(surface["read_only"])
        # a projection that claims a write surface must fail closed
        bad = {"mutationSurface": {"externalMutation": True, "ledgerMutation": False,
                                   "approvalMutation": False, "gitControl": False}}
        with self.assertRaises(ValueError):
            m.assert_read_only(bad)


if __name__ == "__main__":
    unittest.main(verbosity=2)
