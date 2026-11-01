"""Standards knowledge & master-evidence association (NX-520).

Converts standard sources (WCAG/ARIA/CLREQ/JLREQ/Ghent/Smithsonian/NPS/
GOV.UK/18F/Plain Language) into sourced, searchable, testable validators —
not copied web pages.

Each standard is a validator with a source + a set of checkable rules.
Master evidence cards are kept, but only cards that pass the source gate may be
used for authoritative/commercial-ready conclusions. Final generation
instructions use transferable methods, never copied signature style/composition.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# Standard -> source + representative checkable rules (transferable methods).
STANDARDS: dict[str, dict[str, Any]] = {
    "wcag22": {
        "source": "W3C WCAG 2.2", "category": "accessibility",
        "rules": [
            {"id": "wcag-1.4.3", "check": "text contrast >= 4.5:1"},
            {"id": "wcag-2.4.7", "check": "focus visible"},
            {"id": "wcag-3.2.2", "check": "no unexpected context change on input"},
        ],
    },
    "aria-apg": {
        "source": "W3C ARIA Authoring Practices Guide", "category": "accessibility",
        "rules": [
            {"id": "aria-dialog", "check": "modal dialog has focus trap + aria-modal"},
            {"id": "aria-tabs", "check": "tab panel keyboard nav + aria-selected"},
        ],
    },
    "clreq": {
        "source": "W3C Chinese Layout Requirements", "category": "typography-cjk",
        "rules": [
            {"id": "clreq-punct", "check": "CJK punctuation line-breaking"},
            {"id": "clreq-vert", "check": "vertical writing-mode support"},
        ],
    },
    "jlreq": {
        "source": "W3C Japanese Layout Requirements", "category": "typography-cjk",
        "rules": [
            {"id": "jlreq-ruby", "check": "ruby annotation support"},
            {"id": "jlreq-punct", "check": "Japanese punctuation spacing"},
        ],
    },
    "ghent-print": {
        "source": "Ghent Workgroup PDF/X preflight", "category": "print",
        "rules": [
            {"id": "print-pdfx", "check": "PDF/X-Plus compliance"},
            {"id": "print-bleed", "check": "bleed + trim box set"},
        ],
    },
    "smithsonian-exhibit": {
        "source": "Smithsonian Guidelines for Accessible Exhibition Design", "category": "exhibition",
        "rules": [
            {"id": "exhibit-text", "check": "readable text size/contrast in exhibit"},
            {"id": "exhibit-light", "check": "lighting does not impair access"},
        ],
    },
    "nps-access": {
        "source": "NPS Exhibit Accessibility", "category": "exhibition",
        "rules": [
            {"id": "nps-path", "check": "accessible pathways"},
            {"id": "nps-media", "check": "audio description + captions"},
        ],
    },
    "govuk": {
        "source": "GOV.UK Service Manual", "category": "content",
        "rules": [
            {"id": "govuk-needs", "check": "start from user needs"},
            {"id": "govuk-simple", "check": "plain language"},
        ],
    },
    "18f-methods": {
        "source": "18F Methods", "category": "content",
        "rules": [
            {"id": "18f-discover", "check": "discover stage research"},
            {"id": "18f-make", "check": "make stage prototyping"},
        ],
    },
    "plain-language": {
        "source": "Plain Language Guidelines", "category": "content",
        "rules": [
            {"id": "plain-active", "check": "use active voice"},
            {"id": "plain-short", "check": "short sentences, user language"},
        ],
    },
}

VALIDATOR_NAMES = list(STANDARDS)


def standard_validators() -> dict[str, dict[str, Any]]:
    """Return all standard validators (sourced, searchable)."""
    return STANDARDS


def validate_against(standard: str, rules_checked: list[str]) -> dict[str, Any]:
    """Run a validator: given the rules actually checked, report coverage.

    A validator is testable: it returns pass/fail per rule and coverage.
    """
    if standard not in STANDARDS:
        raise ValueError(f"unknown standard: {standard}")
    rules = STANDARDS[standard]["rules"]
    result = []
    for rule in rules:
        checked = rule["id"] in rules_checked
        result.append({"id": rule["id"], "check": rule["check"], "passed": checked})
    passed = sum(1 for r in result if r["passed"])
    return {
        "standard": standard,
        "source": STANDARDS[standard]["source"],
        "category": STANDARDS[standard]["category"],
        "coverage": f"{passed}/{len(rules)}",
        "passing": passed == len(rules),
        "rules": result,
    }


def search_standards(query: str) -> list[str]:
    """Searchable knowledge index: return matching standard names."""
    q = query.lower()
    return [name for name, data in STANDARDS.items()
            if q in name.lower() or q in data["source"].lower()
            or q in data["category"].lower()
            or any(q in r["check"].lower() for r in data["rules"])]


@dataclass
class MasterEvidenceCard:
    """A predecessor master-evidence card."""

    id: str
    standard: str
    passes_source_gate: bool = False
    authoritative_ready: bool = False


def associate_master_evidence(cards: list[MasterEvidenceCard]) -> dict[str, Any]:
    """Associate standard validators with master evidence cards.

    Only cards that pass the source gate become authoritative/commercial-ready.
    """
    association = []
    for card in cards:
        if card.standard not in STANDARDS:
            raise ValueError(f"card {card.id} references unknown standard {card.standard}")
        source_gate = card.passes_source_gate
        authoritative = source_gate and card.authoritative_ready
        association.append({
            "card_id": card.id,
            "standard": card.standard,
            "source_gate_passed": source_gate,
            "authoritative_ready": authoritative,
        })
    return {
        "schemaVersion": "work-lab/master-evidence-association/v1",
        "associations": association,
        "authoritative_count": sum(1 for a in association if a["authoritative_ready"]),
    }
