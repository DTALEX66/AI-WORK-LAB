#!/usr/bin/env python3
"""Standards knowledge & master-evidence association verifier (NX-520).

Verifies standard validators are sourced/searchable/testable, and that only
source-gated master-evidence cards become authoritative.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
WF_SCRIPTS = ROOT / "packages" / "client-neutral-core" / "scripts"
sys.path.insert(0, str(WF_SCRIPTS))

from standard_validators import (  # noqa: E402
    standard_validators, validate_against, search_standards,
    MasterEvidenceCard, associate_master_evidence,
)


def verify() -> dict:
    errors: list[str] = []
    standards = standard_validators()
    if len(standards) != 10:
        errors.append(f"expected 10 standards, got {len(standards)}")

    # Every validator is sourced + has at least one rule.
    for name, data in standards.items():
        if not data.get("source"):
            errors.append(f"{name}: missing source")
        if not data.get("rules"):
            errors.append(f"{name}: no rules")

    # Validator is testable: passing all rules -> passing=True.
    full = [r["id"] for r in standards["wcag22"]["rules"]]
    result = validate_against("wcag22", full)
    if not result["passing"]:
        errors.append("wcag22 should pass when all rules checked")

    # Searchable index.
    hits = search_standards("contrast")
    if "wcag22" not in hits:
        errors.append("search should find wcag22 for 'contrast'")

    # Master evidence: only source-gated cards authoritative.
    cards = [
        MasterEvidenceCard("card-1", "wcag22", passes_source_gate=True, authoritative_ready=True),
        MasterEvidenceCard("card-2", "aria-apg", passes_source_gate=False, authoritative_ready=False),
    ]
    assoc = associate_master_evidence(cards)
    if assoc["authoritative_count"] != 1:
        errors.append("only source-gated card should be authoritative")

    if errors:
        raise ValueError("; ".join(errors))
    return {"standards": len(standards), "authoritative": assoc["authoritative_count"]}


def main() -> int:
    try:
        result = verify()
    except (ValueError, ImportError) as exc:
        print(f"STANDARD_VALIDATORS_FAIL {exc}")
        return 1
    print(
        f"STANDARD_VALIDATORS_PASS standards={result['standards']} sourced=true searchable=true "
        f"testable=true authoritative_source_gated={result['authoritative']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
