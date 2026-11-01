"""NF-08 cross-software handoff gap-set contract tests.

Carries the existing 8 single-writer replay scenarios as acceptance evidence
(NF-08 explicitly keeps them) and proves the *gap set* the 8 do not cover in a
two-execution-entry handoff: response-lost redelivery, restart duplicate,
produce-after-cancel, and external-effect-unknown reconciliation.  No native
private database is read and no real network / paid call is made.  Loaded by
file path per the NF-02 convention (no `from services`).
"""
from __future__ import annotations

import importlib.util
import os
import sys
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
HANDOFF = os.path.join(ROOT, "packages", "client-neutral-core", "scripts", "handoff.py")
REPLAY = os.path.join(ROOT, "packages", "client-neutral-core", "scripts", "task_ledger_replay.py")
LEDGER = os.path.join(ROOT, "packages", "client-neutral-core", "scripts", "task_ledger.py")


def _load(name: str, path: str):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


HANDOFF_MOD = _load("nf08_handoff", HANDOFF)
REPLAY_MOD = _load("nf08_replay", REPLAY)


class HandoffGapSetTests(unittest.TestCase):
    def test_payload_is_desensitized(self):
        raw = {
            "repo": "D/All projects/WORK-LAB",
            "head": "efbde9e",
            "task_id": "T-1",
            "goal": "closeout",
            "verified": ["tests/green"],
            "next_step": "push + CI",
            "permission_scope": "read-only preview",
            "api_key": "SECRET-MUST-NOT-TRAVEL",
            "conversation": "raw chat must not travel",
        }
        p = HANDOFF_MOD.sanitize_payload(raw)
        self.assertNotIn("api_key", p)
        self.assertNotIn("conversation", p)
        self.assertIn("repo", p)
        self.assertIn("permission_scope", p)
        # digest is stable over the desensitized payload
        self.assertEqual(HANDOFF_MOD.payload_digest(p), HANDOFF_MOD.payload_digest(p))

    def test_response_lost_redelivery_is_idempotent(self):
        relay = HANDOFF_MOD.HandoffRelay()
        out = relay.response_lost_redelivery({"task_id": "T-2", "repo": "r", "head": "h"}, "dlv-2")
        self.assertEqual(out["first"], "DELIVERED")
        self.assertEqual(out["second"], "ALREADY_DELIVERED")
        self.assertEqual(out["side_effects"], 1)  # lost ack re-sent: no duplicate effect

    def test_restart_duplicate_single_real_effect(self):
        relay = HANDOFF_MOD.HandoffRelay()
        out = relay.restart_duplicate({"task_id": "T-3", "repo": "r"}, "dlv-3")
        self.assertEqual(out["first"], "DELIVERED")
        self.assertEqual(out["second"], "ALREADY_DELIVERED")
        self.assertEqual(out["side_effects_this_delivery"], 1)
        self.assertTrue(out["redundant_is_noop"])

    def test_produce_after_cancel_refused(self):
        for term in ("CANCELLED", "COMPLETED", "FAILED"):
            r = HANDOFF_MOD.produce_after_cancel(term, "eff-x", "push")
            self.assertEqual(r["status"], "REFUSED", term)
            self.assertFalse(r["side_effect_executed"])
        # a non-terminal task still may produce
        ok = HANDOFF_MOD.produce_after_cancel("RUNNING", "eff-x", "push")
        self.assertEqual(ok["status"], "ALLOWED")
        self.assertTrue(ok["side_effect_executed"])

    def test_external_effect_unknown_reconciled_not_blind_retried(self):
        for observed in ("CONFIRMED", "ABSENT", "CONFLICT"):
            r = HANDOFF_MOD.external_effect_unknown("eff-u", "push", observed)
            self.assertFalse(r["blind_retry"], observed)
        with self.assertRaises(ValueError):
            HANDOFF_MOD.external_effect_unknown("eff-u", "push", "MAYBE")

    def test_delivery_id_payload_conflict_not_silent(self):
        relay = HANDOFF_MOD.HandoffRelay()
        relay.deliver({"task_id": "A", "repo": "r"}, "dlv-c")
        # same delivery id, DIFFERENT payload -> explicit conflict, not silent
        out = relay.deliver({"task_id": "B", "repo": "r"}, "dlv-c")
        self.assertEqual(out["status"], "CONFLICT")
        self.assertFalse(out["side_effect_executed"])

    def test_existing_8_scenarios_carried_as_evidence(self):
        results = REPLAY_MOD.run_all_scenarios()["scenarios"]
        self.assertEqual(len(results), 8)
        for r in results:
            self.assertIn(r["outcome"], ("PASS", "FAIL_CLOSED"))
            if r["outcome"] == "PASS":
                self.assertFalse(r["duplicate_side_effect"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
