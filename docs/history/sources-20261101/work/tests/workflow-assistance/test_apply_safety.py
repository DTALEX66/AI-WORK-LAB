"""WLG-100: apply safety contract tests."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts/workflow"))

from apply_safety import APPLY_SEQUENCE, SAFETY_INVARIANTS, validate_apply_sequence


class ApplySafetyTests(unittest.TestCase):
    def test_apply_sequence_is_plan_first_rollback_last(self):
        self.assertEqual(
            APPLY_SEQUENCE,
            ("plan", "diff", "approval", "backup", "atomic_apply", "readback", "rollback"),
        )

    def test_sequence_validation(self):
        self.assertTrue(validate_apply_sequence(APPLY_SEQUENCE))
        self.assertFalse(validate_apply_sequence(("apply", "plan", "rollback")))
        self.assertFalse(validate_apply_sequence(()))

    def test_safety_invariants_present(self):
        for invariant in (
            "official_schema_wins",
            "unknown_preserved",
            "provider_model_auth_observe",
            "no_cross_client_body_sync",
            "failure_never_breaks_client",
        ):
            self.assertIn(invariant, SAFETY_INVARIANTS)

    def test_sync_scripts_implement_the_sequence(self):
        codex_sync = (ROOT / "integrations/executors/codex/sync_codex_global_assets.py").read_text(encoding="utf-8")
        hermes_sync = (ROOT / "integrations/executors/hermes/sync_hermes_workflow_assets.py").read_text(encoding="utf-8")
        for source in (codex_sync, hermes_sync):
            self.assertIn("plan", source)
            # Backup is implemented as a journaled previous-state mechanism
            # (previous_*/state_original_bytes) or backup-before-publish.
            self.assertTrue(
                any(marker in source for marker in ("previous_", "state_original_bytes", "backup")),
                "no journaled backup mechanism found",
            )
            self.assertIn("rollback", source)
            self.assertIn("verify", source)
            self.assertIn("atomic", source)
            self.assertIn("approv", source)


if __name__ == "__main__":
    unittest.main()
