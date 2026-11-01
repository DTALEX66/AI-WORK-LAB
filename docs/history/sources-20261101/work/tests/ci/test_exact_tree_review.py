"""NX-720 exact-tree review unit tests."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "ci"))

from exact_tree_review import review_tree  # noqa: E402


class ExactTreeReviewTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.report = review_tree()

    def test_head_and_origin_are_equal_and_clean(self) -> None:
        self.assertEqual(self.report["head"], self.report["originMain"])
        self.assertTrue(self.report["worktreeClean"])

    def test_only_two_active_modules_and_transferred_scope_absent(self) -> None:
        self.assertEqual(set(self.report["activeModulePresence"]), {
            "packages/client-neutral-core", "apps/observer",
        })
        self.assertTrue(all(self.report["activeModulePresence"].values()))
        self.assertEqual(self.report["transferredScopeTracked"], [])

    def test_no_forbidden_tracked_paths(self) -> None:
        self.assertEqual(self.report["forbiddenTrackedPaths"], [])

    def test_task_handoff_verifier_and_ci_evidence_present(self) -> None:
        self.assertTrue(all(status == "COMPLETED" for status in self.report["taskStatus"].values()))
        self.assertTrue(all(self.report["requiredHandoffsPresent"]))
        self.assertTrue(all(self.report["requiredVerifiersPresent"].values()))
        self.assertTrue(self.report["ciWorkflowPresent"])

    def test_release_boundaries_are_explicit(self) -> None:
        self.assertEqual(self.report["reviewerMode"], "READ_ONLY")
        self.assertFalse(self.report["credentialContentsRead"])
        self.assertFalse(self.report["externalWrites"])
        self.assertEqual(self.report["liveExecution"], "UNKNOWN_NOT_RUN")
        self.assertEqual(self.report["humanCalibration"], "PENDING")
        self.assertEqual(self.report["releaseApproval"], "PENDING_HUMAN_APPROVAL")


if __name__ == "__main__":
    unittest.main()
