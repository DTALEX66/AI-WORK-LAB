"""NX-410: Task Ledger replay + side-effect consistency tests.

RED-GREEN coverage:
- All 8 failure scenarios present.
- Duplicate side effects are never executed (idempotency by intent).
- Old-writer revival and corrupt events fail closed (never silently mis-run).
- Replay of the same history is deterministic (same state each time).
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WF_SCRIPTS = ROOT / "packages" / "client-neutral-core" / "scripts"
sys.path.insert(0, str(WF_SCRIPTS))

from task_ledger_replay import (  # noqa: E402
    ReplayHarness, run_scenario, run_all_scenarios, build_ops,
)


class TaskLedgerReplayTest(unittest.TestCase):
    def test_all_8_scenarios_present(self) -> None:
        results = run_all_scenarios()["scenarios"]
        self.assertEqual(len(results), 8)

    def test_crash_mid_run_no_duplicate_side_effect(self) -> None:
        r = run_scenario("crash-mid-run")
        self.assertEqual(r["outcome"], "PASS")
        self.assertFalse(r["duplicate_side_effect"])

    def test_push_unknown_idempotent(self) -> None:
        r = run_scenario("push-unknown")
        self.assertEqual(r["outcome"], "PASS")
        self.assertEqual(r["effects_executed"], 1)  # 3 ops, 1 unique effect

    def test_old_writer_revival_fail_closed(self) -> None:
        r = run_scenario("old-writer-revival")
        self.assertEqual(r["outcome"], "FAIL_CLOSED")

    def test_duplicate_webhook_idempotent(self) -> None:
        r = run_scenario("duplicate-webhook")
        self.assertEqual(r["outcome"], "PASS")
        self.assertEqual(r["effects_executed"], 1)

    def test_corrupt_event_fail_closed(self) -> None:
        r = run_scenario("corrupt-event")
        self.assertEqual(r["outcome"], "FAIL_CLOSED")

    def test_replay_deterministic(self) -> None:
        ops = build_ops("crash-mid-run")
        h1 = ReplayHarness()
        h2 = ReplayHarness()
        s1 = h1.replay(ops)
        s2 = h2.replay(ops)
        self.assertEqual(s1.side_effects, s2.side_effects)
        self.assertEqual(s1.cursor, s2.cursor)

    def test_task_upgrade_readable(self) -> None:
        # Version upgrade: events replay; no silent mis-run.
        r = run_scenario("task-upgrade")
        self.assertIn(r["outcome"], ("PASS", "FAIL_CLOSED"))


if __name__ == "__main__":
    unittest.main()
