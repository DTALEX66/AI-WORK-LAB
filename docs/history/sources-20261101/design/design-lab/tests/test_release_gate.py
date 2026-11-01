#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

# Deterministic stand-in for "the current tree SHA": no capability in the
# committed index binds it, so it only exercises the comparison logic.
CURRENT_SHA = "1" * 40

from verify_release_gate import (  # noqa: E402
    capability_floor_findings,
    evidence_card_findings,
    load_effective_evidence_module,
)


class ReleaseGateHelpersTest(unittest.TestCase):
    def test_git_status_failure_is_fail_closed(self):
        import verify_release_gate

        responses = iter([
            (128, "git status failed"),
            (0, "head-sha"),
            (0, "head-sha"),
        ])
        with patch.object(verify_release_gate, "git", side_effect=lambda *args: next(responses)):
            findings = verify_release_gate.check()
        self.assertTrue(any(item.startswith("GIT-STATUS-FAILED") for item in findings))

    def test_capability_floor_rejects_underqualified_actual_evidence(self):
        data = {
            "capabilities": [
                {"id": "creative-toolchain", "minimumRequiredEvidence": "E3", "actualEvidence": "E1"},
                {"id": "release-evidence", "minimumRequiredEvidence": "E1", "actualEvidence": "E1"},
            ]
        }
        path = Path(self._tmp_file("capabilities.json"))
        path.write_text(json.dumps(data), encoding="utf-8")
        try:
            findings = capability_floor_findings(path, CURRENT_SHA, load_effective_evidence_module())
        finally:
            path.unlink()
        # Batch F-1: the line now reports the level the floor was measured
        # against (effective) next to the recording, so a stale runtime claim
        # stays distinguishable from a never-reached floor.
        self.assertEqual(
            findings,
            [
                "EVIDENCE-BELOW-MINIMUM creative-toolchain actual=E1 minimum=E3 "
                "recorded=E1 effective=E1"
            ],
        )

    def test_capability_floor_rejects_invalid_levels_without_traceback(self):
        path = Path(self._tmp_file("invalid-capabilities.json"))
        path.write_text(
            '{"capabilities": [{"id": "x", "minimumRequiredEvidence": "E9", "actualEvidence": "E1"}]}',
            encoding="utf-8",
        )
        try:
            findings = capability_floor_findings(path, CURRENT_SHA, load_effective_evidence_module())
        finally:
            path.unlink()
        self.assertIn("CAPABILITY-EVIDENCE-INVALID", findings[0])

    def test_evidence_cards_require_completed_human_calibration(self):
        path = Path(self._tmp_file("cards.json"))
        path.write_text(
            '{"cards": [{"card_status": "accepted", "human_calibration": {"status": "pending"}}]}',
            encoding="utf-8",
        )
        try:
            self.assertEqual(evidence_card_findings(path), ["EVIDENCE-CARDS-PENDING accepted=0/1"])
        finally:
            path.unlink()

    def test_evidence_cards_accept_only_completed_cards(self):
        path = Path(self._tmp_file("accepted-cards.json"))
        path.write_text(
            '{"cards": [{"card_status": "accepted", "human_calibration": {"status": "completed"}}]}',
            encoding="utf-8",
        )
        try:
            self.assertEqual(evidence_card_findings(path), [])
        finally:
            path.unlink()

    @staticmethod
    def _tmp_file(name: str) -> str:
        directory = Path(__file__).resolve().parents[1] / ".project-local" / "task-runtime"
        directory.mkdir(parents=True, exist_ok=True)
        return str(directory / name)


if __name__ == "__main__":
    unittest.main()
