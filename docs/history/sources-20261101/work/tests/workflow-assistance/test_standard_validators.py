"""NX-520: standards knowledge and master-evidence association tests.

Coverage:
- all required standards are sourced and searchable;
- validators return deterministic per-rule coverage;
- unknown standards/cards fail closed;
- only source-gated evidence can become authoritative.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WF_SCRIPTS = ROOT / "packages" / "client-neutral-core" / "scripts"
sys.path.insert(0, str(WF_SCRIPTS))

from standard_validators import (  # noqa: E402
    MasterEvidenceCard,
    associate_master_evidence,
    search_standards,
    standard_validators,
    validate_against,
)


class StandardValidatorsTest(unittest.TestCase):
    def test_required_standards_are_sourced(self) -> None:
        standards = standard_validators()
        self.assertEqual(len(standards), 10)
        required = {
            "wcag22", "aria-apg", "clreq", "jlreq", "ghent-print",
            "smithsonian-exhibit", "nps-access", "govuk", "18f-methods",
            "plain-language",
        }
        self.assertEqual(set(standards), required)
        for data in standards.values():
            self.assertTrue(data["source"])
            self.assertGreaterEqual(len(data["rules"]), 1)

    def test_search_is_case_insensitive_and_rule_aware(self) -> None:
        self.assertIn("wcag22", search_standards("CONTRAST"))
        self.assertIn("clreq", search_standards("punctuation"))
        self.assertIn("govuk", search_standards("user needs"))

    def test_validator_reports_partial_coverage(self) -> None:
        result = validate_against("wcag22", ["wcag-1.4.3"])
        self.assertEqual(result["coverage"], "1/3")
        self.assertFalse(result["passing"])
        self.assertEqual(sum(1 for rule in result["rules"] if rule["passed"]), 1)

    def test_validator_reports_full_coverage(self) -> None:
        rules = [rule["id"] for rule in standard_validators()["aria-apg"]["rules"]]
        result = validate_against("aria-apg", rules)
        self.assertTrue(result["passing"])
        self.assertEqual(result["coverage"], "2/2")

    def test_unknown_standard_fails_closed(self) -> None:
        with self.assertRaises(ValueError):
            validate_against("not-a-standard", [])

    def test_source_gate_controls_authoritative_status(self) -> None:
        result = associate_master_evidence([
            MasterEvidenceCard("approved", "wcag22", True, True),
            MasterEvidenceCard("ungated", "aria-apg", False, True),
            MasterEvidenceCard("not-ready", "clreq", True, False),
        ])
        self.assertEqual(result["authoritative_count"], 1)
        states = {item["card_id"]: item["authoritative_ready"] for item in result["associations"]}
        self.assertTrue(states["approved"])
        self.assertFalse(states["ungated"])
        self.assertFalse(states["not-ready"])

    def test_unknown_card_standard_fails_closed(self) -> None:
        with self.assertRaises(ValueError):
            associate_master_evidence([MasterEvidenceCard("bad", "missing")])

    def test_association_schema_is_versioned(self) -> None:
        result = associate_master_evidence([])
        self.assertEqual(result["schemaVersion"], "work-lab/master-evidence-association/v1")
        self.assertEqual(result["authoritative_count"], 0)


if __name__ == "__main__":
    unittest.main()
