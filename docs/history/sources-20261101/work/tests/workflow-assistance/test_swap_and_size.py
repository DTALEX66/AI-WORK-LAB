"""Contract tests for swap drills and repo size audit (WL3-720/810)."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from repo_size_audit import audit_working_tree, savings_proposal
from swap_drills import DRILLS, run_all_drills, run_drill


class SwapDrillsTests(unittest.TestCase):
    def test_six_drills_registered(self) -> None:
        self.assertEqual(len(DRILLS), 6)
        for drill in (
            "hermes-codex-github",
            "cursor-replaces-hermes",
            "provider-model-swap",
            "platform-update-path-change",
            "client-absent",
            "cc-switch-unavailable",
        ):
            self.assertIn(drill, DRILLS)

    def test_each_drill_keeps_core_identical(self) -> None:
        report = run_all_drills()
        self.assertTrue(report["passed"])
        for result in report["drills"].values():
            self.assertTrue(result["core_identical"])
            self.assertFalse(result["core_forked"])

    def test_unknown_drill_rejected(self) -> None:
        with self.assertRaises(ValueError):
            run_drill("not-a-drill")

    def test_cc_switch_unavailable_is_explicit_degradation(self) -> None:
        result = run_drill("cc-switch-unavailable")
        self.assertTrue(result["pass"])
        self.assertEqual(result["degraded_entry"], ["cc-switch-unavailable"])


class RepoSizeAuditTests(unittest.TestCase):
    def test_audit_is_read_only_and_returns_counts(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "a.txt").write_text("x" * 100, encoding="utf-8")
            (root / "b.bin").write_bytes(b"y" * 200)
            subprocess = __import__("subprocess")
            subprocess.run(["git", "init", "-q"], cwd=root, check=True)
            subprocess.run(["git", "add", "-A"], cwd=root, check=True)
            audit = audit_working_tree(root)
            self.assertEqual(audit["tracked_files"], 2)
            self.assertEqual(audit["total_bytes"], 300)
            self.assertFalse(audit["rewrite_required"])

    def test_proposal_is_proposal_not_action(self) -> None:
        proposal = savings_proposal({"top_blobs": [], "duplicate_groups": 0})
        self.assertEqual(proposal["status"], "PROPOSAL_READY")
        self.assertFalse(proposal["rewrite_required"])


if __name__ == "__main__":
    unittest.main()
