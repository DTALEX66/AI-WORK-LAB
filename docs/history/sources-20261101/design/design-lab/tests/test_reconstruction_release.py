# SPDX-License-Identifier: MIT
"""Fail-closed lifecycle and exact-SHA contracts for reconstruction release claims."""
from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "design-lab"))
sys.path.insert(0, str(PROJECT_ROOT / "packages" / "capabilities"))

from reconstruction.release import EvidenceError, current_projection, validate_release  # noqa: E402


SHA = "a" * 40


def evidence() -> dict[str, object]:
    return {
        "schemaVersion": "design-lab/reconstruction-evidence/v1",
        "releaseSha": SHA,
        "lifecycle": {
            "implementedLocal": True,
            "testedLocal": True,
            "ciVerifiedExactSha": True,
            "mergedMain": True,
            "installedRuntimeVerified": True,
        },
        "ci": {"headSha": SHA, "conclusion": "success"},
        "goldenCases": [{"caseId": f"case-{number}", "status": "PASS"} for number in range(6)],
        "illustrator": {"status": "PASS"},
        "liveRuns": [{"host": "illustrator", "sha": SHA, "status": "PASS"}],
    }


class ReconstructionReleaseTests(unittest.TestCase):
    def test_local_tests_cannot_fill_runtime_field(self) -> None:
        record = evidence()
        record["liveRuns"] = []

        with self.assertRaises(EvidenceError):
            validate_release(record, SHA)

    def test_ci_sha_must_equal_requested_release_sha(self) -> None:
        record = evidence()
        record["ci"] = {"headSha": "b" * 40, "conclusion": "success"}

        with self.assertRaises(EvidenceError):
            validate_release(record, SHA)

    def test_projection_is_noncurrent_when_bound_sha_differs(self) -> None:
        projection = current_projection(evidence(), "b" * 40)

        self.assertFalse(projection["current"])
        self.assertEqual(projection["status"], "NONCURRENT")

    def test_nonpassing_golden_case_blocks_release(self) -> None:
        record = copy.deepcopy(evidence())
        record["goldenCases"][2]["status"] = "PARTIAL"

        with self.assertRaises(EvidenceError):
            validate_release(record, SHA)


if __name__ == "__main__":
    unittest.main()
