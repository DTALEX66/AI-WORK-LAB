"""WLG-060: hash/idempotency budget tests."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts/workflow"))

from hash_budget import (
    FORBIDDEN_DIGEST_INPUTS,
    REAL_TIME_DIGESTS,
    RELEASE_ONLY_DIGESTS,
    STAGE_DIGESTS,
    validate_budget,
)


class HashBudgetTests(unittest.TestCase):
    def test_real_time_layer_is_persisted_in_ledger(self):
        self.assertIn("task_id", REAL_TIME_DIGESTS)
        self.assertIn("idempotency_key", REAL_TIME_DIGESTS)
        self.assertIn("ledger_event_digest", REAL_TIME_DIGESTS)
        self.assertIn("desired_state_digest", REAL_TIME_DIGESTS)
        self.assertIn("evidence_envelope_digest", REAL_TIME_DIGESTS)

    def test_stage_layer_covers_frozen_tree_and_gate_plan(self):
        self.assertIn("frozen_tree_sha", STAGE_DIGESTS)
        self.assertIn("gate_plan_digest", STAGE_DIGESTS)
        self.assertIn("stage_qualification_evidence", STAGE_DIGESTS)

    def test_release_layer_is_exact_sha_and_packaging(self):
        self.assertIn("exact_sha_attestation", RELEASE_ONLY_DIGESTS)
        self.assertIn("installer_checksum", RELEASE_ONLY_DIGESTS)
        self.assertIn("sbom", RELEASE_ONLY_DIGESTS)
        self.assertIn("download_readback", RELEASE_ONLY_DIGESTS)

    def test_forbidden_inputs_are_explicit(self):
        for forbidden in ("secrets", "raw_memory", "sessions", "prompt_bodies", "response_bodies"):
            self.assertIn(forbidden, FORBIDDEN_DIGEST_INPUTS)

    def test_budget_validation_is_stable(self):
        budget = validate_budget()
        self.assertEqual(budget["real_time"], 5)
        self.assertEqual(budget["stage"], 3)
        self.assertEqual(budget["release_only"], 6)
        self.assertEqual(budget["forbidden_inputs"], 5)

    def test_ledger_uses_real_time_digests(self):
        ledger_source = (ROOT / "packages/client-neutral-core/scripts/task_ledger.py").read_text(encoding="utf-8")
        self.assertIn("idempotency_key", ledger_source)
        self.assertIn("intent_digest", ledger_source)


if __name__ == "__main__":
    unittest.main()
