# SPDX-License-Identifier: MIT
"""DL-P0-070: Adobe host capability matrix (claimed vs recorded, never inferred).

Module boundary: this module owns the *reading, schema validation, and gap
accounting* of `design-lab/readiness/adobe-host-matrix.json`. It never launches,
attaches to, or queries a host, so it cannot and does not turn a `declared` API
into a `verified` one. Every entry must carry an explicit evidence level and an
explicit "verified by whom / when" state; the only machine facts permitted to
enter the document are ones already recorded in this repository, and they are
cited by path in each entry's `evidence_refs`.

Fail-closed rules added here (not present elsewhere in the repository):
  * a `declared` API may not set `verified: true` unless the host's
    `verification.state` is `VERIFIED_LIVE` *and* a non-empty
    `verification.evidence_ref` exists;
  * a host with `present: false` may not declare any verified API;
  * every host claiming `editable_delivery: true` must declare at least one
    `FILE_FORMAT`/`COM`/`UXP` API *and* a non-empty `readback_method`;
  * `install_alias` must be an alias key, never an absolute user path.

There is deliberately no writer: this build has no live host evidence, so a
"promotion" path would be a fabrication path.
"""
from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator

from ..runtime.state_resources import repo_resource
from . import ReadinessError

TASK_ID = "DL-P0-070"
SCHEMA_VERSION = "design-lab/readiness-host-matrix/v1"
SCHEMA_PATH = repo_resource('schemas/readiness-host-matrix.schema.json')
MATRIX_PATH = repo_resource('readiness/adobe-host-matrix.json')

API_KINDS = ("UXP", "COM", "CLI", "FILE_FORMAT", "PLUGIN")
VERIFICATION_STATES = ("NOT_VERIFIED", "VERIFIED_STRUCTURAL", "VERIFIED_LIVE")
LIVE = "VERIFIED_LIVE"
NOT_VERIFIED = "NOT_VERIFIED"
#: API kinds that can carry an editable delivery path.
DELIVERY_KINDS = ("FILE_FORMAT", "COM", "UXP")
#: Explicit, honest marker used when the whole matrix contains no live evidence.
NO_LIVE_EVIDENCE = "NONE_RECORDED"


def _json_text(text: str, source: str):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ReadinessError(f"{source}: duplicate JSON key {key!r}")
            result[key] = value
        return result

    try:
        return json.loads(text, object_pairs_hook=unique,
                          parse_constant=lambda value: (_ for _ in ()).throw(
                              ReadinessError(f"{source}: non-finite JSON constant {value}")))
    except ReadinessError:
        raise
    except ValueError as exc:
        raise ReadinessError(f"{source}: invalid JSON: {exc}") from exc


def load_document(path) -> dict:
    """Read one JSON document from an explicit path; fail closed on any problem."""
    path = Path(path)
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ReadinessError(f"readiness document unreadable: {path}: {exc}") from exc
    return _json_text(text, str(path))


def _schema(path) -> dict:
    return load_document(path)


def _schema_errors(document, schema, source: str) -> list:
    errors = sorted(Draft202012Validator(schema).iter_errors(document),
                    key=lambda error: list(error.absolute_path))
    return [f"{source}: {'/'.join(str(part) for part in error.absolute_path) or '<root>'}: "
            f"{error.message}" for error in errors]


def validate_matrix(document, *, schema_path=None) -> dict:
    """Schema-validate a matrix document and enforce the readiness rules.

    Returns the document unchanged on success; raises `ReadinessError` listing
    every violation on failure. Never repairs, defaults, or drops a bad entry.
    """
    if not isinstance(document, dict):
        raise ReadinessError("host matrix must be a JSON object")
    source = "adobe-host-matrix"
    schema = _schema(SCHEMA_PATH if schema_path is None else schema_path)
    issues = _schema_errors(document, schema, source)
    if issues:
        raise ReadinessError("host matrix schema violation: " + "; ".join(issues[:8]))
    if document.get("schema_version") != SCHEMA_VERSION:
        raise ReadinessError(f"host matrix schema_version must be {SCHEMA_VERSION}")
    if not document.get("inventory_observed_at"):
        raise ReadinessError("host matrix must cite inventory_observed_at from the recorded inventory")
    if not document.get("inventory_ref"):
        raise ReadinessError("host matrix must cite the recorded inventory by repository-relative path")

    seen: set = set()
    for entry in document["entries"]:
        host_id = entry["host_id"]
        label = f"{host_id}@{entry['host_version']}"
        key = (host_id, entry["host_version"])
        if key in seen:
            raise ReadinessError(f"duplicate host entry: {label}")
        seen.add(key)

        alias = entry["install_alias"]
        if "/" in alias or "\\" in alias or ":" in alias:
            raise ReadinessError(f"{label}: install_alias must be an alias key, not a path: {alias!r}")
        if not entry.get("evidence_refs"):
            raise ReadinessError(f"{label}: every host entry must cite at least one evidence_ref")

        verification = entry["verification"]
        state = verification["state"]
        if state not in VERIFICATION_STATES:
            raise ReadinessError(f"{label}: unknown verification state {state!r}")
        if state == LIVE and not (verification.get("evidence_ref") or "").strip():
            raise ReadinessError(f"{label}: VERIFIED_LIVE requires a non-empty verification.evidence_ref")
        if state == LIVE and not verification.get("by", "").strip():
            raise ReadinessError(f"{label}: VERIFIED_LIVE requires verification.by (who verified)")

        declared = [api for api in entry["apis"] if api["declared"]]
        verified = [api for api in entry["apis"] if api["verified"]]
        for api in entry["apis"]:
            if api["verified"] and not api["declared"]:
                raise ReadinessError(
                    f"{label}: api {api['api_id']} is verified but not declared; verification without a claim")
            if api["verified"] and api["evidence_level"] not in ("E2", "E3", "E4", "E5"):
                raise ReadinessError(
                    f"{label}: api {api['api_id']} verified at {api['evidence_level']}; "
                    "verification requires runtime-or-better evidence, not a declaration")
        if verified and state != LIVE:
            api_ids = ", ".join(api["api_id"] for api in verified)
            raise ReadinessError(
                f"{label}: APIs marked verified ({api_ids}) require verification.state == {LIVE}, "
                f"found {state!r}")
        if not entry["present"] and verified:
            api_ids = ", ".join(api["api_id"] for api in verified)
            raise ReadinessError(
                f"{label}: host is absent from the recorded inventory and may not declare a verified API ({api_ids})")
        if entry["editable_delivery"]:
            if not any(api["kind"] in DELIVERY_KINDS for api in declared):
                raise ReadinessError(
                    f"{label}: editable_delivery requires a declared {'/'.join(DELIVERY_KINDS)} API")
            if not (entry.get("readback_method") or "").strip():
                raise ReadinessError(f"{label}: editable_delivery requires a readback_method")
        elif (entry.get("readback_method") or "").strip():
            raise ReadinessError(f"{label}: readback_method declared without editable_delivery")
    return document


def load_matrix(path=None) -> dict:
    """Load and validate the repository matrix; fail closed on either step."""
    return validate_matrix(load_document(MATRIX_PATH if path is None else path))


def capability_gap(matrix: dict) -> list:
    """Per host: declared-but-unverified APIs and the delivery capability at risk.

    One record per host entry, in document order:
      host_id, host_version, present, unverified_apis (declared and not
      verified), unproven (the delivery capability that remains unproven), and
      the explicit `evidence_gap` sentence a reviewer can quote.
    """
    gaps = []
    for entry in matrix["entries"]:
        label = f"{entry['host_id']}@{entry['host_version']}"
        unverified = [
            {"api_id": api["api_id"], "kind": api["kind"], "evidence_level": api["evidence_level"],
             "note": api.get("note", "")}
            for api in entry["apis"] if api["declared"] and not api["verified"]
        ]
        if entry["editable_delivery"]:
            unproven = ("editable delivery via " + entry["readback_method"]
                        if entry["present"] else
                        "editable delivery claimed but host absent from the recorded inventory")
        else:
            unproven = "no editable delivery claimed for this host"
        if unverified:
            evidence_gap = (f"{label}: {len(unverified)} declared API(s) with no recorded verification; "
                            f"state={entry['verification']['state']}; "
                            f"readback={entry['readback_method'] or 'none'}")
        else:
            evidence_gap = f"{label}: no declared API remains unverified"
        gaps.append({
            "host_id": entry["host_id"],
            "host_version": entry["host_version"],
            "present": entry["present"],
            "unverified_apis": unverified,
            "unproven": unproven,
            "evidence_gap": evidence_gap,
        })
    return gaps


def summary(matrix: dict) -> dict:
    """Counts plus an explicit live-evidence line; `NONE_RECORDED` means none."""
    entries = matrix["entries"]
    apis = [api for entry in entries for api in entry["apis"]]
    hosts_verified = [entry for entry in entries if entry["verification"]["state"] == LIVE]
    apis_verified = [api for api in apis if api["verified"]]
    structural = [entry for entry in entries if entry["verification"]["state"] == "VERIFIED_STRUCTURAL"]
    return {
        "task_id": TASK_ID,
        "hosts_total": len(entries),
        "hosts_present": sum(1 for entry in entries if entry["present"]),
        "hosts_absent": sum(1 for entry in entries if not entry["present"]),
        "hosts_editable_delivery": sum(1 for entry in entries if entry["editable_delivery"]),
        "hosts_structurally_verified": len(structural),
        "hosts_live_verified": len(hosts_verified),
        "apis_declared": sum(1 for api in apis if api["declared"]),
        "apis_verified": len(apis_verified),
        "inventory_observed_at": matrix.get("inventory_observed_at"),
        "live_host_evidence": NO_LIVE_EVIDENCE if not apis_verified else "RECORDED",
    }
