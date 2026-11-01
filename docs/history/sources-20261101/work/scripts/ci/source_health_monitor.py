"""Offline source health, vulnerability and upstream-change monitor (NX-600).

This module is deliberately read-only and deterministic:
- OSV-style vulnerability input is consumed locally; no network and no auto-fix.
- Scorecard is a health signal, never a sole absorption decision.
- Upstream changes that affect license, postinstall/network behavior, API,
  archive state, or package ownership produce UPSTREAM_CHANGED and BLOCK_UPDATE.
- New candidates are DISCOVERED/QUARANTINED only.
- Existing approved versions retain rollback evidence.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class SourceSnapshot:
    source_id: str
    reviewed_commit: str
    license_id: str
    has_postinstall: bool
    api_surface: tuple[str, ...]
    archived: bool
    package_owner: str
    package_name: str
    version: str


@dataclass(frozen=True)
class RollbackEvidence:
    source_id: str
    approved_commit: str
    approved_version: str
    rollback_ref: str


@dataclass
class HealthResult:
    source_id: str
    status: str
    update_decision: str
    reasons: list[str] = field(default_factory=list)
    rollback: RollbackEvidence | None = None


def compare_upstream(
    approved: SourceSnapshot,
    candidate: SourceSnapshot,
    rollback: RollbackEvidence,
) -> HealthResult:
    """Compare a candidate snapshot with the approved version, offline."""
    if approved.source_id != candidate.source_id:
        raise ValueError("source_id mismatch")
    reasons: list[str] = []
    if approved.license_id != candidate.license_id:
        reasons.append("LICENSE_CHANGED")
    if not approved.has_postinstall and candidate.has_postinstall:
        reasons.append("POSTINSTALL_ADDED")
    if set(approved.api_surface) - set(candidate.api_surface):
        reasons.append("API_REMOVED")
    if not approved.archived and candidate.archived:
        reasons.append("REPOSITORY_ARCHIVED")
    if approved.package_owner != candidate.package_owner:
        reasons.append("PACKAGE_OWNERSHIP_CHANGED")

    if reasons:
        return HealthResult(
            source_id=approved.source_id,
            status="UPSTREAM_CHANGED",
            update_decision="BLOCK_UPDATE",
            reasons=reasons,
            rollback=rollback,
        )
    return HealthResult(
        source_id=approved.source_id,
        status="UNCHANGED",
        update_decision="NO_CHANGE",
        rollback=rollback,
    )


def discover_candidate(source_id: str, package_name: str) -> dict[str, str]:
    """Register a new source without installing, vendoring, or enabling it."""
    if not source_id or not package_name:
        raise ValueError("candidate requires source_id and package_name")
    return {
        "source_id": source_id,
        "package_name": package_name,
        "status": "DISCOVERED",
        "decision": "QUARANTINED",
        "installation": "FORBIDDEN",
        "auto_enable": "FORBIDDEN",
    }


def offline_osv_scan(
    packages: list[dict[str, str]],
    local_advisories: dict[str, list[str]],
) -> dict[str, Any]:
    """Read local OSV-style advisories; no network and no automatic fix."""
    findings = []
    for package in packages:
        ids = local_advisories.get(package.get("name", ""), [])
        findings.append({
            "name": package.get("name", ""),
            "version": package.get("version", ""),
            "advisories": list(ids),
            "fix": "MANUAL_REVIEW_ONLY" if ids else "NONE",
        })
    return {"mode": "OFFLINE_READ_ONLY", "auto_fix": False, "findings": findings}


def scorecard_signal(
    source_id: str,
    score: float | None,
    critical_checks_failed: list[str] | None = None,
) -> dict[str, Any]:
    """Return OpenSSF Scorecard as a signal, not an absorption verdict."""
    failed = list(critical_checks_failed or [])
    return {
        "source_id": source_id,
        "score": score,
        "critical_checks_failed": failed,
        "decision_role": "SIGNAL_ONLY",
        "requires_review": score is None or bool(failed) or (score is not None and score < 7.0),
    }
