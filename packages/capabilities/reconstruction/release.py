# SPDX-License-Identifier: MIT
"""Fail-closed release-evidence checks for reconstruction capability claims."""
from __future__ import annotations

import re
from typing import Any, Mapping


_SHA = re.compile(r"^[0-9a-f]{40}$")
_LIFECYCLE = (
    "implementedLocal",
    "testedLocal",
    "ciVerifiedExactSha",
    "mergedMain",
    "installedRuntimeVerified",
)


class EvidenceError(ValueError):
    """Raised when a release claim lacks the layer of evidence it asserts."""


def _mapping(record: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    value = record.get(key)
    if not isinstance(value, Mapping):
        raise EvidenceError(f"{key} must be an object")
    return value


def validate_release(evidence: Mapping[str, Any], expected_sha: str) -> None:
    """Accept only a complete, exact-SHA CI and installed-host release claim."""

    if not _SHA.fullmatch(expected_sha):
        raise EvidenceError("expected release SHA must be a lowercase 40-hex SHA")
    if evidence.get("schemaVersion") != "design-lab/reconstruction-evidence/v1":
        raise EvidenceError("unsupported reconstruction evidence schema")
    release_sha = evidence.get("releaseSha")
    if release_sha != expected_sha:
        raise EvidenceError("release SHA does not equal requested SHA")
    lifecycle = _mapping(evidence, "lifecycle")
    for field in _LIFECYCLE:
        if lifecycle.get(field) is not True:
            raise EvidenceError(f"lifecycle field is not verified: {field}")
    ci = _mapping(evidence, "ci")
    if ci.get("headSha") != expected_sha or ci.get("conclusion") != "success":
        raise EvidenceError("CI is not a successful exact-SHA verification")
    cases = evidence.get("goldenCases")
    if not isinstance(cases, list) or len(cases) != 6:
        raise EvidenceError("all six golden cases are required")
    if any(not isinstance(case, Mapping) or case.get("status") != "PASS" for case in cases):
        raise EvidenceError("golden corpus is incomplete")
    illustrator = _mapping(evidence, "illustrator")
    if illustrator.get("status") != "PASS":
        raise EvidenceError("Illustrator runtime is not qualified")
    live_runs = evidence.get("liveRuns")
    if not isinstance(live_runs, list) or not live_runs:
        raise EvidenceError("installed runtime requires at least one live run")
    if any(not isinstance(run, Mapping) or run.get("status") != "PASS" or run.get("sha") != expected_sha for run in live_runs):
        raise EvidenceError("live host evidence is missing, failed, or bound to another SHA")


def current_projection(evidence: Mapping[str, Any], checked_out_sha: str) -> dict[str, object]:
    """Project validated evidence without letting a stale SHA look current."""

    try:
        validate_release(evidence, str(evidence.get("releaseSha", "")))
        valid = True
    except EvidenceError:
        valid = False
    bound_sha = evidence.get("releaseSha")
    current = bool(valid and bound_sha == checked_out_sha)
    return {
        "schemaVersion": "design-lab/reconstruction-capability-projection/v1",
        "boundSha": bound_sha,
        "current": current,
        "status": "PASS" if current else "NONCURRENT",
        "lifecycle": evidence.get("lifecycle", {}),
    }
