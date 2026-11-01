"""WLG-070: audit trigger dedup tests."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts/workflow"))

from audit_triggers import AUDIT_TRIGGERS, audit_already_recorded, should_run_full_audit


class AuditTriggerTests(unittest.TestCase):
    def test_full_audit_runs_only_on_declared_triggers(self):
        for trigger in AUDIT_TRIGGERS:
            self.assertTrue(should_run_full_audit(trigger), trigger)
        self.assertFalse(should_run_full_audit("fix a typo"))
        self.assertFalse(should_run_full_audit("update a test"))
        self.assertFalse(should_run_full_audit(None))

    def test_same_fact_does_not_generate_second_audit(self):
        seen = {"sha-abc"}
        self.assertTrue(audit_already_recorded(seen, "sha-abc"))
        self.assertFalse(audit_already_recorded(seen, "sha-def"))

    def test_trigger_set_is_exactly_five(self):
        self.assertEqual(
            set(AUDIT_TRIGGERS),
            {
                "schema_or_authority_boundary_changed",
                "new_client_or_adapter",
                "new_risk_category",
                "unexplained_incident",
                "owner_explicit_request",
            },
        )


if __name__ == "__main__":
    unittest.main()
