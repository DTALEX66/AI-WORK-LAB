"""NX-600 source health monitor tests."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "ci"))

from source_health_monitor import (  # noqa: E402
    RollbackEvidence,
    SourceSnapshot,
    compare_upstream,
    discover_candidate,
    offline_osv_scan,
    scorecard_signal,
)


class SourceHealthMonitorTest(unittest.TestCase):
    def setUp(self) -> None:
        self.approved = SourceSnapshot(
            "source", "commit-a", "MIT", False, ("parse", "render"),
            False, "owner-a", "pkg", "1.0.0",
        )
        self.rollback = RollbackEvidence("source", "commit-a", "1.0.0", "git:commit-a")

    def test_unchanged_source_does_not_block(self) -> None:
        result = compare_upstream(self.approved, self.approved, self.rollback)
        self.assertEqual(result.status, "UNCHANGED")
        self.assertEqual(result.update_decision, "NO_CHANGE")
        self.assertEqual(result.rollback, self.rollback)

    def test_license_change_blocks_and_preserves_rollback(self) -> None:
        candidate = SourceSnapshot("source", "commit-b", "GPL-3.0", False, ("parse", "render"), False, "owner-a", "pkg", "1.1.0")
        result = compare_upstream(self.approved, candidate, self.rollback)
        self.assertEqual(result.status, "UPSTREAM_CHANGED")
        self.assertEqual(result.update_decision, "BLOCK_UPDATE")
        self.assertIn("LICENSE_CHANGED", result.reasons)
        self.assertEqual(result.rollback.approved_commit, "commit-a")

    def test_postinstall_api_archive_and_takeover_are_blocked(self) -> None:
        cases = [
            ("POSTINSTALL_ADDED", dict(has_postinstall=True)),
            ("API_REMOVED", dict(api_surface=("parse",))),
            ("REPOSITORY_ARCHIVED", dict(archived=True)),
            ("PACKAGE_OWNERSHIP_CHANGED", dict(package_owner="owner-b")),
        ]
        for reason, change in cases:
            with self.subTest(reason=reason):
                values = dict(self.approved.__dict__)
                values.update(change)
                result = compare_upstream(self.approved, SourceSnapshot(**values), self.rollback)
                self.assertEqual(result.update_decision, "BLOCK_UPDATE")
                self.assertIn(reason, result.reasons)

    def test_candidate_is_quarantined_and_not_installed(self) -> None:
        result = discover_candidate("new", "new-package")
        self.assertEqual(result["status"], "DISCOVERED")
        self.assertEqual(result["decision"], "QUARANTINED")
        self.assertEqual(result["installation"], "FORBIDDEN")
        self.assertEqual(result["auto_enable"], "FORBIDDEN")

    def test_offline_osv_scan_never_auto_fixes(self) -> None:
        result = offline_osv_scan(
            [{"name": "pkg", "version": "1.0.0"}],
            {"pkg": ["OSV-1"]},
        )
        self.assertEqual(result["mode"], "OFFLINE_READ_ONLY")
        self.assertFalse(result["auto_fix"])
        self.assertEqual(result["findings"][0]["fix"], "MANUAL_REVIEW_ONLY")

    def test_scorecard_is_signal_only(self) -> None:
        high = scorecard_signal("source", 9.0)
        low = scorecard_signal("source", 5.0)
        self.assertEqual(high["decision_role"], "SIGNAL_ONLY")
        self.assertFalse(high["requires_review"])
        self.assertTrue(low["requires_review"])

    def test_source_id_mismatch_fails_closed(self) -> None:
        candidate = SourceSnapshot("other", "commit-b", "MIT", False, (), False, "owner-a", "pkg", "1.1.0")
        with self.assertRaises(ValueError):
            compare_upstream(self.approved, candidate, self.rollback)


if __name__ == "__main__":
    unittest.main()
