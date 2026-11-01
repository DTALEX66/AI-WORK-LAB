"""WLGM-040 tests: execution anchor / session lineage."""
from __future__ import annotations

import unittest

from execution_anchor import AnchorState, ExecutionAnchor, VisitedRepository


class ExecutionAnchorTests(unittest.TestCase):
    def test_transient_visit_does_not_migrate_anchor(self) -> None:
        anchor = ExecutionAnchor(execution_id="e1")
        anchor.anchor("work-lab", evidence="task-contract")
        anchor.record_visit("os-project", visited_at="t1")
        self.assertEqual(anchor.anchor_project_id, "work-lab")
        self.assertEqual(anchor.anchor_state, AnchorState.ANCHORED)
        self.assertEqual(len(anchor.visited_repositories), 1)

    def test_weak_evidence_never_switches_project(self) -> None:
        anchor = ExecutionAnchor(execution_id="e1")
        anchor.anchor("work-lab", evidence="task-contract")
        switched = anchor.switch_project("os-project", evidence="visited-cwd", strong=False)
        self.assertFalse(switched)
        self.assertEqual(anchor.anchor_project_id, "work-lab")

    def test_strong_evidence_switches_and_clears_visits(self) -> None:
        anchor = ExecutionAnchor(execution_id="e1")
        anchor.anchor("work-lab", evidence="task-contract")
        anchor.record_visit("os-project", visited_at="t1")
        switched = anchor.switch_project("os-project", evidence="new-execution", strong=True)
        self.assertTrue(switched)
        self.assertEqual(anchor.anchor_project_id, "os-project")
        self.assertEqual(anchor.visited_repositories, [])

    def test_same_project_switch_is_noop(self) -> None:
        anchor = ExecutionAnchor(execution_id="e1")
        anchor.anchor("p", evidence="e")
        self.assertFalse(anchor.switch_project("p", evidence="e2", strong=True))

    def test_conflict_marker(self) -> None:
        anchor = ExecutionAnchor(execution_id="e1")
        anchor.mark_conflict("conflicting-strong-evidence")
        self.assertEqual(anchor.anchor_state, AnchorState.CONFLICT)

    def test_compression_degrades_quality_not_anchor(self) -> None:
        anchor = ExecutionAnchor(execution_id="e1")
        anchor.anchor("p", evidence="e")
        anchor.current_working_area = "/p/sub"
        anchor.degrade_path_quality()
        self.assertEqual(anchor.current_working_area, None)
        self.assertEqual(anchor.anchor_project_id, "p")

    def test_json_shape(self) -> None:
        anchor = ExecutionAnchor(execution_id="e1", lineage=["parent-exec"])
        anchor.anchor("p", evidence="e")
        data = anchor.to_json()
        self.assertEqual(data["executionId"], "e1")
        self.assertEqual(data["anchorState"], "ANCHORED")
        self.assertEqual(data["lineage"], ["parent-exec"])


if __name__ == "__main__":
    unittest.main()
