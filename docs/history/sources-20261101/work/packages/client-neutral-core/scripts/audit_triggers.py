"""WLG-070: full-audit trigger dedup contract.

A full repository audit runs ONLY when one of the declared triggers fires.
The same SHA/fact must not produce a second audit report; ordinary project
fixes get targeted verification only.
"""

from __future__ import annotations

AUDIT_TRIGGERS = (
    "schema_or_authority_boundary_changed",
    "new_client_or_adapter",
    "new_risk_category",
    "unexplained_incident",
    "owner_explicit_request",
)

TARGETED_ONLY = "ordinary project fix — targeted verification only"


def should_run_full_audit(trigger: str | None) -> bool:
    return trigger in AUDIT_TRIGGERS


def audit_already_recorded(seen_digests: set[str], fact_digest: str) -> bool:
    """Same fact digest must not generate a second audit report."""
    return fact_digest in seen_digests
