"""WLGM-130 tests: multi-evidence state aggregator."""
from __future__ import annotations

import unittest

from evidence_aggregator import (
    ActivityState,
    AttentionState,
    EvidenceAggregator,
    ExecutionState,
    IllegalTransitionError,
)


class EvidenceAggregatorTests(unittest.TestCase):
    def _now(self, offset_seconds: int = 0) -> str:
        from datetime import datetime, timedelta, timezone

        return (datetime.now(timezone.utc) + timedelta(seconds=offset_seconds)).isoformat().replace("+00:00", "Z")

    def test_one_waiting_does_not_mark_project_waiting(self) -> None:
        agg = EvidenceAggregator()
        agg.apply_event(execution_id="e1", event_type="execution_running", occurred_at=self._now(), evidence_level="A", anchor_project_id="p")
        agg.apply_event(execution_id="e2", event_type="execution_waiting_user", occurred_at=self._now(1), evidence_level="A", anchor_project_id="p")
        projection = agg.projection("p")
        self.assertEqual(projection["activityState"], ActivityState.ACTIVE.value)
        self.assertEqual(projection["activeExecutionCount"], 2)

    def test_one_failure_does_not_override_running(self) -> None:
        agg = EvidenceAggregator()
        agg.apply_event(execution_id="e1", event_type="execution_running", occurred_at=self._now(), evidence_level="A", anchor_project_id="p")
        agg.apply_event(execution_id="e2", event_type="execution_failed", occurred_at=self._now(1), evidence_level="A", anchor_project_id="p")
        projection = agg.projection("p")
        self.assertEqual(projection["activityState"], ActivityState.ACTIVE.value)
        self.assertEqual(projection["activeExecutionCount"], 1)

    def test_all_expired_becomes_partial_not_completed(self) -> None:
        agg = EvidenceAggregator(lost_seconds=1)
        agg.apply_event(execution_id="e1", event_type="execution_running", occurred_at="2000-01-01T00:00:00Z", evidence_level="A", anchor_project_id="p")
        projection = agg.projection("p", now=self._now())
        self.assertEqual(projection["activityState"], ActivityState.UNKNOWN.value)

    def test_weak_evidence_alone_never_running(self) -> None:
        agg = EvidenceAggregator()
        status = agg.apply_event(execution_id="e1", event_type="execution_running", occurred_at=self._now(), evidence_level="E", anchor_project_id="p")
        self.assertNotEqual(status.state, ExecutionState.RUNNING)
        self.assertTrue(any("weak-evidence-running" in item for item in status.conflict_evidence))

    def test_no_terminal_state_no_auto_complete(self) -> None:
        agg = EvidenceAggregator()
        agg.apply_event(execution_id="e1", event_type="execution_running", occurred_at=self._now(), evidence_level="A", anchor_project_id="p")
        agg.apply_event(execution_id="e1", event_type="execution_heartbeat", occurred_at=self._now(1), evidence_level="A", anchor_project_id="p")
        status = agg.executions["e1"]
        self.assertNotIn(status.state, {ExecutionState.COMPLETED, ExecutionState.FAILED, ExecutionState.CANCELLED})

    def test_waiting_states_are_distinct(self) -> None:
        agg = EvidenceAggregator()
        agg.apply_event(execution_id="e1", event_type="execution_waiting_approval", occurred_at=self._now(), evidence_level="A", anchor_project_id="p")
        projection = agg.projection("p")
        self.assertEqual(projection["attentionState"], AttentionState.WAITING_APPROVAL_PRESENT.value)

    def test_multi_agent_counts(self) -> None:
        agg = EvidenceAggregator()
        agg.register_execution("e1", agent="hermes", anchor_project_id="p")
        agg.apply_event(execution_id="e1", event_type="execution_running", occurred_at="t0", evidence_level="A")
        agg.register_execution("e2", agent="codex", anchor_project_id="p")
        agg.apply_event(execution_id="e2", event_type="execution_running", occurred_at="t1", evidence_level="A")
        projection = agg.projection("p")
        self.assertEqual(projection["agentCounts"], {"hermes": 1, "codex": 1})

    def test_conflict_lowers_quality(self) -> None:
        agg = EvidenceAggregator()
        agg.register_execution("e1", agent="hermes", anchor_project_id="p")
        status = agg.apply_event(execution_id="e1", event_type="execution_running", occurred_at="t0", evidence_level="E")
        projection = agg.projection("p")
        self.assertEqual(projection["quality"], "CORRELATED")


class IllegalTransitionTests(unittest.TestCase):
    def test_no_illegal_transitions(self) -> None:
        agg = EvidenceAggregator()
        agg.apply_event(execution_id="e1", event_type="execution_completed", occurred_at="t0", evidence_level="A")
        with self.assertRaises(IllegalTransitionError):
            agg.executions["e1"].transition(ExecutionState.RUNNING)

    def test_terminal_states_are_final(self) -> None:
        for terminal in (ExecutionState.COMPLETED, ExecutionState.FAILED, ExecutionState.CANCELLED, ExecutionState.LOST):
            agg = EvidenceAggregator()
            status = agg.apply_event(
                execution_id="e1", event_type="execution_running", occurred_at="t0",
                evidence_level="A", anchor_project_id="p",
            )
            status.transition(terminal)
            with self.assertRaises(IllegalTransitionError):
                agg.executions["e1"].transition(ExecutionState.RUNNING)


if __name__ == "__main__":
    unittest.main()
