#!/usr/bin/env python3
"""Fail-closed lifecycle operations for local growth-candidate contracts."""

from __future__ import annotations

import copy
import hashlib
import json
import re
from typing import Any

SCHEMA_VERSION = "workflow/growth-candidate/v1"
CLASSIFICATIONS = {"curator", "learn", "manual", "hub", "upstream", "deployment"}
RISKS = {"low", "medium", "high", "critical"}
STATES = {"discovered", "isolated", "scanned", "evaluated", "candidate", "approved", "approved_project", "approved_global", "blocked", "retired", "expired", "conflict"}
REQUIRED = {"schema_version", "candidateId", "origin", "classification", "status", "risk"}
ALLOWED = REQUIRED | {"sourceDigest", "scope", "ttl_days", "supersedes", "conflictsWith"}
TRANSITIONS = {
    "discovered": {"isolated", "blocked", "conflict", "expired"},
    "isolated": {"scanned", "blocked", "conflict", "expired"},
    "scanned": {"evaluated", "blocked", "conflict", "expired"},
    "evaluated": {"candidate", "blocked", "conflict", "expired"},
    "candidate": {"approved", "approved_project", "approved_global", "blocked", "conflict", "expired"},
    "approved": {"retired"},
    "approved_project": {"approved_global", "retired"},
    "approved_global": {"retired"},
    "blocked": set(),
    "retired": set(),
    "expired": set(),
    "conflict": set(),
}
DIGEST = re.compile(r"^[a-f0-9]{64}$")


def validate_candidate(candidate: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(candidate, dict):
        raise ValueError("candidate must be an object")
    unexpected = set(candidate) - ALLOWED
    if unexpected:
        raise ValueError(f"additional candidate properties: {sorted(unexpected)}")
    missing = REQUIRED - set(candidate)
    if missing:
        raise ValueError(f"candidate missing required properties: {sorted(missing)}")
    if candidate["schema_version"] != SCHEMA_VERSION:
        raise ValueError("candidate schema version mismatch")
    for key in ("candidateId", "origin"):
        if not isinstance(candidate[key], str) or not candidate[key]:
            raise ValueError(f"candidate {key} must be non-empty")
    if candidate["classification"] not in CLASSIFICATIONS:
        raise ValueError("invalid candidate classification")
    if candidate["status"] not in STATES:
        raise ValueError("invalid candidate status")
    if candidate["risk"] not in RISKS:
        raise ValueError("invalid candidate risk")
    if candidate["status"] not in {"discovered", "blocked"} and "sourceDigest" not in candidate:
        raise ValueError("source digest is required for this candidate status")
    if "sourceDigest" in candidate and not isinstance(candidate["sourceDigest"], str):
        raise ValueError("candidate digest must be a string")
    if "sourceDigest" in candidate and not DIGEST.fullmatch(candidate["sourceDigest"]):
        raise ValueError("candidate digest must be 64 lowercase hexadecimal characters")
    return candidate


def discover(candidate_id: str, origin: str, classification: str, risk: str) -> dict[str, Any]:
    candidate = {
        "schema_version": SCHEMA_VERSION,
        "candidateId": candidate_id,
        "origin": origin,
        "classification": classification,
        "status": "discovered",
        "risk": risk,
    }
    return validate_candidate(candidate)


def source_digest(source: Any) -> str:
    """Return the stable digest used to bind a candidate to its intake source."""
    canonical = json.dumps(source, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def intake(
    candidate_id: str,
    origin: str,
    classification: str,
    risk: str,
    source: Any,
) -> dict[str, Any]:
    """Create a discovered candidate while retaining only a source digest."""
    candidate = discover(candidate_id, origin, classification, risk)
    candidate["sourceDigest"] = source_digest(source)
    return validate_candidate(candidate)


def readback(candidate: dict[str, Any], persisted: dict[str, Any]) -> dict[str, Any]:
    """Validate that a persisted candidate is an exact contract readback."""
    expected = validate_candidate(copy.deepcopy(candidate))
    actual = validate_candidate(copy.deepcopy(persisted))
    if actual != expected:
        raise ValueError("candidate readback mismatch")
    return actual


def transition(candidate: dict[str, Any], target: str, *, source_digest: str | None = None) -> dict[str, Any]:
    validate_candidate(candidate)
    current = candidate["status"]
    if target not in STATES or target not in TRANSITIONS[current]:
        raise ValueError(f"invalid candidate transition {current} -> {target}")
    updated = copy.deepcopy(candidate)
    if target != "blocked" and "sourceDigest" not in updated:
        if source_digest is None or not DIGEST.fullmatch(source_digest):
            raise ValueError("source digest is required before lifecycle promotion")
        updated["sourceDigest"] = source_digest
    updated["status"] = target
    return validate_candidate(updated)


def promote(candidate: dict[str, Any], *, approval: bool = False, scope: str = "project") -> dict[str, Any]:
    """Project approval promotes to approved_project; global always requires a
    separate explicit approval."""
    if approval is not True:
        raise ValueError("explicit approval is required before promotion")
    target = "approved_global" if scope == "global" else "approved_project"
    return transition(candidate, target)


def approve_global(candidate: dict[str, Any], *, approval: bool = False) -> dict[str, Any]:
    """Separate, explicit gate before a project-approved candidate may go global."""
    if approval is not True:
        raise ValueError("separate explicit approval is required before global promotion")
    return transition(candidate, "approved_global")


def quarantine(candidate: dict[str, Any]) -> dict[str, Any]:
    return transition(candidate, "blocked")


def expire(candidate: dict[str, Any]) -> dict[str, Any]:
    return transition(candidate, "expired")


def mark_conflict(candidate: dict[str, Any]) -> dict[str, Any]:
    return transition(candidate, "conflict")


def rollback(candidate: dict[str, Any]) -> dict[str, Any]:
    return transition(candidate, "retired")
