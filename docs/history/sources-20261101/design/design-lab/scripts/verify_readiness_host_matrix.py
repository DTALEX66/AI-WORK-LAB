#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""GD-1: fail-closed consumer for the Adobe readiness host matrix (DL-P0-070).

The matrix ``design-lab/readiness/adobe-host-matrix.json`` (schema
``design-lab/schemas/readiness-host-matrix.schema.json``) records *claimed
versus recorded* host capability at E1 STRUCTURAL. This gate is its
fail-closed consumer: the document exists but nothing in CI enforced its
internal consistency. It never promotes evidence (E3 live legs stay
owner-gated, DECLARED not EXECUTED); it only prevents a recorded matrix
from drifting into false claims.

Invariants (all fail-closed; any violation makes the exit code 1):

1.  the matrix parses and is schema-valid against
    ``readiness-host-matrix.schema.json`` (draft 2020-12 via ``jsonschema``
    when importable; otherwise a built-in subset validator runs, so the
    gate still works in a bare-stdlib environment);
2.  the whole-document ``evidence_level`` is exactly ``E1`` — the matrix is
    structural by construction and must never round itself up to a live
    claim;
3.  ``inventory_ref`` resolves to a tracked file, and when that inventory
    carries ``observed_at`` it equals the matrix ``inventory_observed_at``
    (an observation date is not a test timestamp; a re-observed inventory
    with a stale matrix is drift);
4.  per api: a ``verified=true`` claim above E1 requires
    ``verification.state == VERIFIED_LIVE`` with a non-null
    ``verification.evidence_ref`` that resolves in the tree (live evidence
    pointer); no E2+ api may carry ``verified=true`` without that leg;
5.  per entry: ``editable_delivery=true`` requires a non-null
    ``readback_method``; a recorded ``readback_method`` implies
    ``editable_delivery`` (recording a readback path without claiming the
    editable delivery is incoherent);
6.  per entry: a host recorded ``present=false`` may never carry
    ``editable_delivery=true`` (nothing may be delivered or read back
    for an absent host);
7.  every repo-relative reference in ``evidence_refs`` and in any
    ``verification.evidence_ref`` resolves to a file on disk — an
    unresolvable reference is path drift and fails the gate (absolute or
    drive-letter external references are skipped, matching the shared-
    root policy: machine-specific paths live outside the repo).

Usage:
    python design-lab/scripts/verify_readiness_host_matrix.py
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SCHEMA = REPO / "design-lab" / "schemas" / "readiness-host-matrix.schema.json"
MATRIX = REPO / "design-lab" / "readiness" / "adobe-host-matrix.json"

E_LEVELS = ("E0", "E1", "E2", "E3", "E4", "E5")


def _load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _resolve_ref(repo: Path, ref: str) -> bool | None:
    """True/False for repo-relative refs; None for external (skipped)."""
    if ref.startswith("http://") or ref.startswith("https://"):
        return None
    if len(ref) >= 2 and ref[1] == ":":  # drive-letter / absolute external
        return None
    return (repo / ref).is_file()


def _fallback_validate(matrix: dict, schema: dict) -> list[str]:
    """Built-in subset of the schema for bare-stdlib environments.

    Checks the required top-level fields, the const fields, the entry/api
    required-key set and the enums. Not a full draft 2020-12 validator —
    it only narrows the surface enough to keep the gate fail-closed when
    ``jsonschema`` is absent.
    """
    errors: list[str] = []
    for key in schema.get("required", []):
        if key not in matrix:
            errors.append(f"matrix missing required key: {key}")
    if matrix.get("schema_version") != schema["properties"]["schema_version"]["const"]:
        errors.append("matrix schema_version mismatch")
    if matrix.get("task_id") != schema["properties"]["task_id"]["const"]:
        errors.append("matrix task_id mismatch")
    if matrix.get("evidence_level") not in ("E0", "E1"):
        errors.append(f"evidence_level must be E0/E1, got {matrix.get('evidence_level')!r}")
    entries = matrix.get("entries", [])
    if not isinstance(entries, list) or not entries:
        errors.append("entries must be a non-empty array")
    entry_schema = schema["properties"]["entries"]["items"]
    for i, entry in enumerate(entries if isinstance(entries, list) else []):
        for key in entry_schema.get("required", []):
            if key not in entry:
                errors.append(f"entry[{i}] missing required key: {key}")
        for j, api in enumerate(entry.get("apis", [])):
            for key in entry_schema["properties"]["apis"]["items"]["required"]:
                if key not in api:
                    errors.append(f"entry[{i}].apis[{j}] missing required key: {key}")
        if entry.get("verification", {}).get("state") not in ("NOT_VERIFIED", "VERIFIED_STRUCTURAL", "VERIFIED_LIVE"):
            errors.append(f"entry[{i}] verification.state invalid")
    return errors


def check_matrix(matrix: dict, schema: dict, repo: Path, use_jsonschema: bool = True) -> list[str]:
    errors: list[str] = []

    # (1) schema validity
    if use_jsonschema:
        try:
            from jsonschema import validate  # type: ignore
            try:
                validate(instance=matrix, schema=schema)
            except Exception as exc:  # fail-closed on any schema violation
                errors.append(f"schema: {exc}")
        except ImportError:
            errors.extend(_fallback_validate(matrix, schema))
    else:
        errors.extend(_fallback_validate(matrix, schema))

    # (2) whole-document evidence level is structural
    if matrix.get("evidence_level") not in ("E0", "E1"):
        errors.append(f"evidence_level {matrix.get('evidence_level')!r} exceeds structural E1")

    # (3) inventory reference + observed-date consistency
    inv_ref = str(matrix.get("inventory_ref", ""))
    inv_path = repo / inv_ref if inv_ref else None
    if not inv_ref:
        errors.append("inventory_ref is empty")
    elif not (inv_path and inv_path.is_file()):
        errors.append(f"inventory_ref does not resolve: {inv_ref}")
    else:
        try:
            inventory = _load_json(inv_path)
            inv_observed = inventory.get("observed_at")
            if inv_observed and matrix.get("inventory_observed_at") != inv_observed:
                errors.append(
                    "inventory_observed_at "
                    f"{matrix.get('inventory_observed_at')!r} != inventory observed_at {inv_observed!r} (stale matrix)"
                )
        except (json.JSONDecodeError, OSError) as exc:
            errors.append(f"inventory unreadable: {exc}")

    level_rank = {level: i for i, level in enumerate(E_LEVELS)}

    for entry in matrix.get("entries", []):
        label = f"{entry.get('host_id')} v{entry.get('host_version')}"
        apis = entry.get("apis", [])
        verification = entry.get("verification", {})
        state = verification.get("state")
        evidence_ref = verification.get("evidence_ref")

        # (4) live claims above E1 need a resolving live-evidence pointer
        for api in apis:
            if api.get("verified") and level_rank.get(str(api.get("evidence_level", "E0")), 0) > 1:
                if state != "VERIFIED_LIVE":
                    errors.append(f"{label}: {api.get('api_id')} verified at {api.get('evidence_level')} without VERIFIED_LIVE state")
                elif not evidence_ref:
                    errors.append(f"{label}: {api.get('api_id')} verified at {api.get('evidence_level')} with null evidence_ref")
                elif _resolve_ref(repo, str(evidence_ref)) is False:
                    errors.append(f"{label}: {api.get('api_id')} evidence_ref does not resolve: {evidence_ref}")

        # VERIFIED_LIVE coherence (state alone is a false claim without ref)
        if state == "VERIFIED_LIVE" and not evidence_ref:
            errors.append(f"{label}: VERIFIED_LIVE with null evidence_ref")

        # (5) editable delivery <-> readback method
        editable = bool(entry.get("editable_delivery"))
        readback = entry.get("readback_method")
        if editable and not (isinstance(readback, str) and readback.strip()):
            errors.append(f"{label}: editable_delivery=true requires a non-null readback_method")
        if readback is not None and not editable:
            errors.append(f"{label}: recorded readback_method without editable_delivery claim")

        # (6) absent hosts may not claim editable delivery
        if entry.get("present") is False and editable:
            errors.append(f"{label}: absent host claims editable delivery")

        # (7) repo-relative evidence refs must resolve (path drift)
        for ref in entry.get("evidence_refs", []):
            hit = _resolve_ref(repo, str(ref))
            if hit is False:
                errors.append(f"{label}: evidence_ref does not resolve: {ref}")
        if evidence_ref:
            hit = _resolve_ref(repo, str(evidence_ref))
            if hit is False:
                errors.append(f"{label}: verification.evidence_ref does not resolve: {evidence_ref}")

    return errors


def main(repo: Path = REPO) -> int:
    if not MATRIX.is_file():
        print(f"READINESS_HOST_MATRIX=FAIL matrix missing: {MATRIX.name}")
        return 1
    try:
        matrix = _load_json(MATRIX)
        schema = _load_json(SCHEMA)
    except (json.JSONDecodeError, OSError) as exc:
        print(f"READINESS_HOST_MATRIX=FAIL unreadable: {exc}")
        return 1

    force_fallback = os.environ.get("DL_HOST_MATRIX_FORCE_FALLBACK") == "1"
    try:
        import jsonschema  # noqa: F401
        have_js = not force_fallback
    except ImportError:
        have_js = False
    errors = check_matrix(matrix, schema, repo, use_jsonschema=have_js)

    entries = matrix.get("entries", [])
    live = [e for e in entries if e.get("verification", {}).get("state") == "VERIFIED_LIVE"]
    validator = "jsonschema" if have_js else "built-in-fallback"
    for e in errors:
        print(f"FAIL {e}")
    print(
        f"READINESS_HOST_MATRIX={'PASS' if not errors else 'FAIL'} "
        f"entries={len(entries)} live={len(live)} validator={validator} failed={len(errors)}"
    )
    return 0 if not errors else 1


if __name__ == "__main__":
    sys.exit(main())
