"""NX-700 offline pilot tests."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "ci"))

from offline_pilot import run_pilots  # noqa: E402


class OfflinePilotTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.report = run_pilots()
        cls.pilots = {pilot["branch"]: pilot for pilot in cls.report["pilots"]}

    def test_two_branches_are_offline_verified(self) -> None:
        self.assertEqual(self.report["mode"], "OFFLINE_FIXTURES_ONLY")
        self.assertTrue(self.report["allOfflineVerified"])
        self.assertEqual(set(self.pilots), {"workflow-agent", "observer"})

    def test_workflow_capability_usage_and_replay(self) -> None:
        workflow = self.pilots["workflow-agent"]
        self.assertFalse(workflow["credentialsRead"])
        self.assertFalse(workflow["promptResponseRead"])
        self.assertEqual(workflow["usageEventSchema"], "work-lab/observer-event/v2")
        self.assertEqual(workflow["taskReplay"]["outcome"], "PASS")
        self.assertEqual(workflow["qwenFixture"]["status"], "UNAVAILABLE")

    def test_observer_rebuild_duplicate_corrupt_and_read_only(self) -> None:
        observer = self.pilots["observer"]
        self.assertTrue(observer["restartRebuildEqual"])
        self.assertTrue(observer["duplicateIngestIdempotent"])
        self.assertEqual(observer["corruptEventsIsolated"], 1)
        self.assertEqual(observer["mutationSurface"], [])

    def test_no_external_side_effects_or_live_claims(self) -> None:
        self.assertFalse(self.report["externalWrites"])
        self.assertFalse(self.report["credentialsAccessed"])
        self.assertEqual(self.report["liveClaims"], "NONE")


if __name__ == "__main__":
    unittest.main()
