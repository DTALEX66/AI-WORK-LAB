# SPDX-License-Identifier: MIT
"""DL-P0-161: DeliveryReceipt V2 -- deterministic, evidence-honest delivery record.

What a receipt is
-----------------
A receipt binds one *job* to its deliverables and records, per deliverable: the
artifact digest, the byte size, the editable flag, the host readback (or ``null``),
the digest of the C2PA-shaped provenance structure (never the structure itself),
the caller-declared requirements and the rollback record for that artifact. The
receipt is deterministic: it never reads the wall clock, ``created_at`` must be
supplied by the caller, and its identity is derived from its own canonical JSON.

Evidence honesty is enforced, not documented away
-------------------------------------------------
``axes.delivery`` is ``PARTIAL`` unless *every* deliverable has a host readback;
:func:`verify_receipt` recomputes the receipt hash, rejects any digest that is not
a nonzero ``sha256:`` value, and fails closed when the delivery axis claims more
than the evidence supports. :func:`unsupported_claims` states exactly what the
receipt does not prove -- read it before quoting this receipt anywhere.

Boundary: JSON in, JSON out; no clock, no filesystem, no host, no signature. No
part of this module performs a host readback; it records one that a caller
supplies. All evidence reachable from this module is E1 (STRUCTURAL).
"""
from __future__ import annotations

import json
from datetime import datetime

from ..runtime.attempt_contract import canonical_hash, request_hash
from ..runtime.state_resources import repo_resource
from . import InteropError, load_schema, schema_errors
from .provenance import (SIGNING_STATUS, build_manifest, manifest_digest,
                         validate_manifest)

SCHEMA_VERSION = "design-lab/delivery-receipt/v2"
TASK_ID = "DL-P0-161"
SCHEMA_PATH = repo_resource('schemas/interop-delivery-receipt-v2.schema.json')
SCHEMA_REPOSITORY_PATH = 'design-lab/schemas/interop-delivery-receipt-v2.schema.json'

DELIVERY_AXES = ("PASS", "PARTIAL")
#: Requirement statuses reused from the repository's provenance record vocabulary.
REQUIREMENT_STATUSES = (
    "NOT_RUN", "PASS", "FAIL", "BLOCKED", "UNVERIFIED", "SKIPPED_OPTIONAL",
)
IDENTITY_FIELDS = ("receipt_id", "receipt_sha256")


def _fail(message: str) -> "InteropError":
    return InteropError(message)


def _text(value, where: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise _fail(f"{where} must be a nonempty string")
    return value


def _digest(value, where: str) -> str:
    try:
        return canonical_hash(value)
    except ValueError as exc:
        raise _fail(f"{where}: {exc}") from exc


def _integer(value, where: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise _fail(f"{where} must be a non-negative integer")
    return value


def _boolean(value, where: str) -> bool:
    if not isinstance(value, bool):
        raise _fail(f"{where} must be a boolean")
    return value


def _timestamp(value, where: str) -> str:
    text = _text(value, where)
    try:
        datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise _fail(f"{where} must be an ISO-8601 timestamp; got {text!r}") from exc
    return text


def _schema_errors(document) -> list[str]:
    return schema_errors(load_schema(SCHEMA_PATH), document)


# --------------------------------------------------------------------------- #
# hashing
# --------------------------------------------------------------------------- #

def _body(receipt: dict) -> dict:
    return {key: value for key, value in receipt.items() if key not in IDENTITY_FIELDS}


def _derive_id(body: dict) -> str:
    return "receipt-" + request_hash(body).removeprefix("sha256:")[:16]


def _derive_hash(body: dict, receipt_id: str) -> str:
    return request_hash({**body, "receipt_id": receipt_id})


def receipt_sha256(receipt) -> str:
    """The canonical hash of a receipt body plus its ``receipt_id``."""
    if not isinstance(receipt, dict):
        raise _fail("receipt must be an object")
    body = _body(receipt)
    receipt_id = receipt.get("receipt_id")
    if receipt_id is None:
        receipt_id = _derive_id(body)
    else:
        _text(receipt_id, "receipt.receipt_id")
    return _derive_hash(body, receipt_id)


def rebuild_identity(receipt) -> dict:
    """Recompute ``receipt_id`` and ``receipt_sha256`` for a receipt body.

    A receipt is not signed, so this is an integrity check against accidental
    edits, not protection against tampering. Call it after changing a body, then
    run :func:`verify_receipt` so the evidence rules are applied again.
    """
    if not isinstance(receipt, dict):
        raise _fail("receipt must be an object")
    body = _body(receipt)
    receipt_id = _derive_id(body)
    return {**body, "receipt_id": receipt_id, "receipt_sha256": _derive_hash(body, receipt_id)}


# --------------------------------------------------------------------------- #
# normalization
# --------------------------------------------------------------------------- #

def _normalize_requirements(value, where: str) -> list[dict]:
    if not isinstance(value, list):
        raise _fail(f"{where} must be an array of {{'req_id', 'status'}} records")
    if not value:
        raise _fail(f"{where} must not be empty; a delivery with no requirement record is undecided")
    seen: set[str] = set()
    normalized = []
    for index, entry in enumerate(value):
        entry_where = f"{where}[{index}]"
        if not isinstance(entry, dict):
            raise _fail(f"{entry_where} must be an object")
        req_id = _text(entry.get("req_id"), f"{entry_where}.req_id")
        status = entry.get("status")
        if status not in REQUIREMENT_STATUSES:
            raise _fail(
                f"{entry_where}.status must be one of {', '.join(REQUIREMENT_STATUSES)}; got {status!r}"
            )
        if req_id in seen:
            raise _fail(f"{entry_where}.req_id {req_id!r} is declared twice")
        seen.add(req_id)
        normalized.append({"req_id": req_id, "status": status})
    return sorted(normalized, key=lambda record: record["req_id"])


def _normalize_rollback(value, where: str) -> dict:
    if not isinstance(value, dict):
        raise _fail(f"{where} must be an object with 'backup_ref' and 'procedure'")
    return {
        "backup_ref": _text(value.get("backup_ref"), f"{where}.backup_ref"),
        "procedure": _text(value.get("procedure"), f"{where}.procedure"),
    }


def _normalize_readback(value, where: str) -> dict:
    if not isinstance(value, dict):
        raise _fail(f"{where} must be an object")
    return {
        "host_id": _text(value.get("host_id"), f"{where}.host_id"),
        "host_version": _text(value.get("host_version"), f"{where}.host_version"),
        "readback_sha256": _digest(value.get("readback_sha256"), f"{where}.readback_sha256"),
        "opened_at": _timestamp(value.get("opened_at"), f"{where}.opened_at"),
    }


def _readback_index(host_readback) -> dict[str, dict]:
    if host_readback is None:
        return {}
    if isinstance(host_readback, dict):
        entries = []
        for deliverable_id, record in host_readback.items():
            _text(deliverable_id, "host_readback key")
            if not isinstance(record, dict):
                raise _fail(f"host_readback[{deliverable_id!r}] must be an object")
            entries.append((deliverable_id, record))
    elif isinstance(host_readback, (list, tuple)):
        entries = []
        for index, record in enumerate(host_readback):
            if not isinstance(record, dict):
                raise _fail(f"host_readback[{index}] must be an object")
            entries.append((_text(record.get("deliverable_id"),
                                  f"host_readback[{index}].deliverable_id"), record))
    else:
        raise _fail("host_readback must be a mapping keyed by deliverable id, a list of records or None")
    index: dict[str, dict] = {}
    for deliverable_id, record in entries:
        if deliverable_id in index:
            raise _fail(f"host_readback declares deliverable {deliverable_id!r} more than once")
        index[deliverable_id] = _normalize_readback(record, f"host_readback[{deliverable_id!r}]")
    return index


def _provenance_digest(entry: dict, where: str) -> str:
    manifest = entry.get("provenance_manifest")
    digest = entry.get("provenance_sha256")
    if manifest is not None and digest is not None:
        raise _fail(
            f"{where} declares both provenance_manifest and provenance_sha256; the receipt records "
            "the structure digest, so supply exactly one"
        )
    if manifest is not None:
        if not isinstance(manifest, dict):
            raise _fail(f"{where}.provenance_manifest must be an object")
        validate_manifest(manifest)
        expected = manifest.get("design_lab", {}).get("deliverable_id")
        if expected != entry.get("deliverable_id"):
            raise _fail(
                f"{where}.provenance_manifest belongs to deliverable {expected!r}, not "
                f"{entry.get('deliverable_id')!r}"
            )
        return manifest_digest(manifest)
    if digest is not None:
        return _digest(digest, f"{where}.provenance_sha256")
    raise _fail(
        f"{where} needs a provenance_manifest (validated and digested here) or a provenance_sha256; "
        "a deliverable without provenance is not receiptable"
    )


# --------------------------------------------------------------------------- #
# build
# --------------------------------------------------------------------------- #
def build_receipt(delivery, *, host_readback=None) -> dict:
    """Build a deterministic DeliveryReceipt V2 for one job.

    ``delivery``::

        {"job_id": ..., "created_at": <optional ISO-8601>,
         "requirements": [{"req_id", "status"}],   # optional per-job default
         "rollback": {"backup_ref", "procedure"},  # optional per-job default
         "deliverables": [{"deliverable_id", "artifact_sha256", "byte_size", "editable",
                           "provenance_manifest" | "provenance_sha256",
                           "requirements"?, "rollback"?}]}

    ``host_readback`` is a mapping keyed by deliverable id (or a list of records
    carrying ``deliverable_id``) of ``{"host_id", "host_version",
    "readback_sha256", "opened_at"}``. A readback for an undeclared deliverable
    fails closed. Requirement and rollback records fall back to the per-job
    defaults when a deliverable does not state its own.

    ``axes.delivery`` is ``PASS`` only when every deliverable has a host readback
    and no requirement is ``FAIL``/``BLOCKED``; otherwise ``PARTIAL``.
    """
    if not isinstance(delivery, dict):
        raise _fail("delivery must be an object")
    job_id = _text(delivery.get("job_id"), "delivery.job_id")
    created_at = delivery.get("created_at")
    if created_at is not None:
        created_at = _timestamp(created_at, "delivery.created_at")
    default_requirements = delivery.get("requirements")
    default_rollback = delivery.get("rollback")
    entries = delivery.get("deliverables")
    if not isinstance(entries, list) or not entries:
        raise _fail("delivery.deliverables must be a nonempty array")

    readbacks = _readback_index(host_readback)
    deliverables = []
    for index, entry in enumerate(entries):
        where = f"delivery.deliverables[{index}]"
        if not isinstance(entry, dict):
            raise _fail(f"{where} must be an object")
        deliverable_id = _text(entry.get("deliverable_id"), f"{where}.deliverable_id")
        artifact = _digest(entry.get("artifact_sha256"), f"{where}.artifact_sha256")
        byte_size = _integer(entry.get("byte_size"), f"{where}.byte_size")
        editable = _boolean(entry.get("editable"), f"{where}.editable")
        requirements = entry.get("requirements", default_requirements)
        if requirements is None:
            raise _fail(
                f"{where} has no requirements and the delivery declares no default; requirement "
                "status must be stated by the caller"
            )
        rollback = entry.get("rollback", default_rollback)
        if rollback is None:
            raise _fail(
                f"{where} has no rollback record and the delivery declares no default; a delivery "
                "without a rollback reference is not receiptable"
            )
        readback = readbacks.pop(deliverable_id, None)
        deliverables.append({
            "deliverable_id": deliverable_id,
            "artifact_sha256": artifact,
            "byte_size": byte_size,
            "editable": editable,
            "host_readback": readback,
            "provenance": _provenance_digest(entry, where),
            "requirements": _normalize_requirements(requirements, f"{where}.requirements"),
            "rollback": _normalize_rollback(rollback, f"{where}.rollback"),
            "readback_matches_artifact": (None if readback is None
                                          else readback["readback_sha256"] == artifact),
        })
    if readbacks:
        raise _fail(
            "host_readback names deliverable(s) the delivery does not declare: "
            + ", ".join(sorted(readbacks))
        )
    deliverables.sort(key=lambda item: item["deliverable_id"])

    body = {
        "schemaVersion": SCHEMA_VERSION,
        "job_id": job_id,
        "deliverables": deliverables,
        "axes": {"delivery": _delivery_axis(deliverables)},
    }
    if created_at is not None:
        body["created_at"] = created_at
    receipt_id = _derive_id(body)
    receipt = {**body, "receipt_id": receipt_id}
    receipt["receipt_sha256"] = _derive_hash(body, receipt_id)
    return receipt


def _delivery_axis(deliverables) -> str:
    for entry in deliverables:
        if entry["host_readback"] is None:
            return "PARTIAL"
        for requirement in entry["requirements"]:
            if requirement["status"] in ("FAIL", "BLOCKED"):
                return "PARTIAL"
    return "PASS"


# --------------------------------------------------------------------------- #
# verify
# --------------------------------------------------------------------------- #

def _check_digests(receipt: dict) -> None:
    for index, entry in enumerate(receipt["deliverables"]):
        where = f"deliverables[{index}]"
        _digest(entry["artifact_sha256"], f"{where}.artifact_sha256")
        _digest(entry["provenance"], f"{where}.provenance")
        readback = entry["host_readback"]
        if readback is not None:
            _digest(readback["readback_sha256"], f"{where}.host_readback.readback_sha256")


def unsupported_claims(receipt) -> list[str]:
    """Everything this receipt does **not** prove, as explicit statements.

    Read this before quoting a receipt anywhere: a receipt is a delivery record,
    not an acceptance, not a signature and not proof that an artifact still exists.
    """
    if not isinstance(receipt, dict):
        raise _fail("receipt must be an object")
    deliverables = receipt.get("deliverables")
    if not isinstance(deliverables, list):
        raise _fail("receipt.deliverables must be an array")
    claims = [
        "the provenance digest records an unsigned C2PA-shaped structure "
        f"({SIGNING_STATUS}); no signature, no signing certificate and no trusted timestamp exist",
        "requirement statuses are caller-declared and are not independently verified by this receipt",
        "byte_size and the editable flag are caller-declared values, not read back from the artifact",
        "this receipt does not prove the artifact still exists, nor that its bytes are unchanged "
        "since the receipt was written",
        "no independent (E4) human acceptance is recorded, and no rollback has been executed: the "
        "rollback record is a plan, not a performed restore",
        "no E2+ host/runtime result is claimed anywhere in this receipt",
    ]
    for entry in deliverables:
        deliverable_id = entry.get("deliverable_id")
        if entry.get("host_readback") is None:
            claims.append(
                f"deliverable {deliverable_id!r}: no host readback was recorded, so opening, editing "
                "and re-saving it in a host is NOT proven"
            )
        elif entry.get("readback_matches_artifact") is False:
            claims.append(
                f"deliverable {deliverable_id!r}: the host readback digest differs from the artifact "
                "digest, so a byte-identical host round trip is NOT proven"
            )
        for requirement in entry.get("requirements", []):
            if requirement.get("status") in ("FAIL", "BLOCKED"):
                claims.append(
                    f"deliverable {deliverable_id!r}: requirement {requirement.get('req_id')!r} is "
                    f"{requirement.get('status')}"
                )
    if receipt.get("axes", {}).get("delivery") == "PARTIAL":
        claims.append(
            "axes.delivery is PARTIAL: at least one deliverable lacks a host readback or carries a "
            "failing/blocked requirement"
        )
    return claims


def verify_receipt(receipt) -> dict:
    """Recompute the receipt hash and refuse any claim the evidence does not support.

    Raises :class:`InteropError` when the receipt is structurally invalid, when a
    digest is not a nonzero ``sha256:`` value, when the receipt identity does not
    match its canonical body, or when ``axes.delivery`` claims ``PASS`` without a
    host readback for every deliverable.
    """
    if not isinstance(receipt, dict):
        raise _fail("receipt must be an object")
    problems = _schema_errors(receipt)
    if problems:
        raise InteropError(f"receipt violates {SCHEMA_PATH.name}: " + "; ".join(problems))

    expected_id = _derive_id(_body(receipt))
    if receipt["receipt_id"] != expected_id:
        raise _fail(
            f"receipt_id {receipt['receipt_id']!r} does not match the canonical body (expected "
            f"{expected_id!r}); the receipt was modified after it was built"
        )
    expected_hash = _derive_hash(_body(receipt), receipt["receipt_id"])
    if receipt["receipt_sha256"] != expected_hash:
        raise _fail(
            f"receipt_sha256 mismatch: recorded {receipt['receipt_sha256']!r}, recomputed "
            f"{expected_hash!r}"
        )
    _check_digests(receipt)

    axis = receipt["axes"]["delivery"]
    if axis not in DELIVERY_AXES:
        raise _fail(f"axes.delivery must be one of {', '.join(DELIVERY_AXES)}; got {axis!r}")
    derived = _delivery_axis(receipt["deliverables"])
    if axis != derived:
        raise _fail(
            f"axes.delivery claims {axis!r} but the recorded evidence supports {derived!r} "
            "(a receipt without a host readback for every deliverable must not claim PASS)"
        )
    for index, entry in enumerate(receipt["deliverables"]):
        expected_match = (None if entry["host_readback"] is None
                          else entry["host_readback"]["readback_sha256"] == entry["artifact_sha256"])
        if entry["readback_matches_artifact"] is not expected_match:
            raise _fail(
                f"deliverables[{index}].readback_matches_artifact is {entry['readback_matches_artifact']!r} "
                f"but the recorded digests imply {expected_match!r}"
            )
    return {
        "schemaVersion": SCHEMA_VERSION,
        "schema_path": SCHEMA_REPOSITORY_PATH,
        "receipt_id": receipt["receipt_id"],
        "receipt_sha256": receipt["receipt_sha256"],
        "job_id": receipt["job_id"],
        "deliverable_count": len(receipt["deliverables"]),
        "readback_count": sum(1 for entry in receipt["deliverables"]
                              if entry["host_readback"] is not None),
        "axes": dict(receipt["axes"]),
        "verified": True,
        "unsupported_claims": unsupported_claims(receipt),
    }


# --------------------------------------------------------------------------- #
# serialization
# --------------------------------------------------------------------------- #

def dumps(receipt) -> str:
    """Serialize a receipt as canonical JSON; ``loads`` reproduces the same hash."""
    if not isinstance(receipt, dict):
        raise _fail("receipt must be an object")
    try:
        return json.dumps(receipt, sort_keys=True, ensure_ascii=False,
                          separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise _fail(f"receipt is not canonical JSON: {exc}") from exc


def loads(text) -> dict:
    """Parse and verify a serialized receipt; the hash must survive the round trip."""
    if not isinstance(text, str) or not text.strip():
        raise _fail("serialized receipt must be a nonempty string")
    try:
        receipt = json.loads(text)
    except json.JSONDecodeError as exc:
        raise _fail(f"serialized receipt is not valid JSON: {exc}") from exc
    verify_receipt(receipt)
    if dumps(receipt) != text:
        raise _fail(
            "serialized receipt is not in canonical form; re-serialize with dumps() before signing "
            "or comparing hashes"
        )
    return receipt


# --------------------------------------------------------------------------- #
# a real bundle delivery -> receipt
# --------------------------------------------------------------------------- #
#
# Everything above this line is a contract: it takes a delivery record and records
# it. This section is the mapping the *product path* uses, and it is still pure --
# it reads no file and no database; the caller hands it the bundle manifest that
# ``runtime.bundle_store.verify_bundle`` already re-read from the published archive.
#
# What a real local delivery actually knows at bundle time, and nothing beyond it:
#
# * every member's digest and byte size, from the manifest whose member bytes were
#   just re-hashed by ``verify_bundle``;
# * which host produced the primary artifact and the host version string the
#   adapter parsed out of the host's own reply;
# * the native attempt id (the operation identity) and the job the attempt belongs
#   to, plus the moment the attempt was receipted (``attempt_state.ended_at``);
# * the state of every gate the bundle manifest records -- and every one of those
#   states is NOT_REVIEWED / NOT_VERIFIED, which is projected as NOT_RUN /
#   UNVERIFIED, never as a verdict;
# * the immutable source version the archive was exported from, as the rollback
#   reference.
#
# What it does not know, and therefore does not write: a host readback. No host
# opens the delivered artifact and re-saves it in this product (the Photoshop
# adapter saves, then closes the document with DONOTSAVECHANGES, and nothing
# re-opens the saved file), so every deliverable gets ``host_readback: null`` and
# ``axes.delivery`` stays ``PARTIAL``. A field this mapping cannot derive from a
# recorded value makes it refuse the whole receipt; it never fills a plausible one.

#: ``schemaVersion`` of the archive manifest this mapping consumes.
BUNDLE_SCHEMA_VERSION = "design-lab/asset-bundle/v1"
#: The hosts whose native execution this product can name as a producer.
BUNDLE_HOSTS = ("photoshop", "illustrator")
#: Member role -> the ``editable`` declaration the receipt may carry for it. Only
#: the host-native layered document is declared editable; a preview is a flattened
#: render. Role ``input`` is absent on purpose: those members are byte copies of the
#: caller's own source files, so stating their editability would be a claim about a
#: document DESIGN-LAB never produced. They ship as provenance ingredients of the
#: deliverables instead (see :func:`bundle_inputs`), not as deliverables.
BUNDLE_ROLE_EDITABLE = {"primary": True, "preview": False}
#: Member suffix -> DESIGN-LAB asset kind, which ``provenance`` carries as ``format``.
#: An unlisted suffix stops the receipt rather than guessing a kind.
BUNDLE_MEMBER_KINDS = {".psd": "psd", ".ai": "ai", ".png": "raster", ".svg": "vector"}
#: The rights profile a bundle declares: none. ``no-rights-declared`` is the C2PA
#: profile that asserts *nothing* about licensing (no creative-work, no training
#: assertion), which is exactly the state of an unreviewed delivery.
BUNDLE_RIGHTS_PROFILE = "no-rights-declared"
#: Requirement naming the one thing the delivery genuinely proves about its bytes.
BUNDLE_BYTES_REQUIREMENT = "req-native-bytes-verified"
#: ``(metadata key, req_id, {recorded state -> receipt status})``. A state outside
#: the inner mapping is not a status the receipt may invent, so it fails closed.
BUNDLE_GATE_REQUIREMENTS = (
    ("rights", "req-rights-review", {"NOT_REVIEWED": "NOT_RUN"}),
    ("quality", "req-quality-review", {"NOT_REVIEWED": "NOT_RUN"}),
    ("font_rights", "req-font-rights", {"NOT_REVIEWED": "NOT_RUN"}),
    ("link_relocation", "req-link-relocation", {"NOT_VERIFIED": "UNVERIFIED"}),
)


def _member_suffix(name: str) -> str:
    base = name.rsplit("/", 1)[-1]
    return "" if "." not in base else "." + base.rsplit(".", 1)[-1].lower()


def bundle_requirements(metadata, *, bundle_bytes_verified: bool,
                        where: str = "delivery.requirements") -> list:
    """Project the gate states a bundle manifest records into requirement records.

    ``bundle_bytes_verified`` must be ``True`` only when the manifest came back from
    :func:`design_lab.runtime.bundle_store.verify_bundle`, which re-reads every
    member and compares its digest and size to the manifest record; that is the
    evidence behind ``req-native-bytes-verified``. Nothing else in this projection is
    claimed as verified: an unreviewed rights gate stays ``NOT_RUN``.
    """
    if not isinstance(metadata, dict):
        raise _fail(f"{where} source must be an object")
    records = []
    for key, req_id, mapping in BUNDLE_GATE_REQUIREMENTS:
        state = metadata.get(key)
        if state not in mapping:
            raise _fail(
                f"bundle metadata {key} is {state!r}, which has no receipt projection; the receipt "
                f"records only {', '.join(f'{k} -> {v}' for k, v in sorted(mapping.items()))} and "
                "will not guess a status for an unlisted state"
            )
        records.append({"req_id": req_id, "status": mapping[state]})
    verified = _boolean(bundle_bytes_verified, "delivery.bundle_bytes_verified")
    records.append({"req_id": BUNDLE_BYTES_REQUIREMENT, "status": "PASS" if verified else "NOT_RUN"})
    return _normalize_requirements(records, where)


def bundle_inputs(manifest) -> list:
    """The source assets shipped inside the archive, as C2PA ingredient records.

    Identity is the DESIGN-LAB asset id the bundle metadata recorded; the digest is
    the member's own record in the same manifest, so an input the archive does not
    actually carry cannot be named here.
    """
    files = manifest["files"]
    entries = manifest.get("metadata", {}).get("input_assets", [])
    if not isinstance(entries, list):
        raise _fail("bundle.metadata.input_assets must be an array")
    inputs = []
    for index, entry in enumerate(entries):
        where = f"bundle.metadata.input_assets[{index}]"
        if not isinstance(entry, dict):
            raise _fail(f"{where} must be an object")
        version_id = _text(entry.get("id"), f"{where}.id")
        member = _text(entry.get("member"), f"{where}.member")
        record = files.get(member)
        if not isinstance(record, dict):
            raise _fail(
                f"{where} names bundle member {member!r}, which the archive manifest does not "
                "declare; an input the archive does not carry cannot be put in the provenance"
            )
        inputs.append({"version_id": version_id,
                       "sha256": _digest("sha256:" + str(record.get("sha256")),
                                         f"{where}.sha256"),
                       "relationship": "inputTo"})
    seen = {item["version_id"] for item in inputs}
    if len(seen) != len(inputs):
        raise _fail("bundle declares the same input asset id more than once")
    return sorted(inputs, key=lambda item: item["version_id"])


def bundle_provenance(*, name, record, metadata, host: str, inputs, when: str) -> dict:
    """Project one shipped member onto the unsigned C2PA structure it deserves.

    The producer is the native host that wrote the bytes (named by the execution
    record, with the host version string the adapter parsed from the host's reply),
    the action is ``c2pa.created`` at the moment DESIGN-LAB persisted that host's
    readback, and the rights profile is ``no-rights-declared`` because the delivery
    has no rights review to project. ``when`` is that persisted ledger time, never a
    claim about the host's own clock.
    """
    kind = BUNDLE_MEMBER_KINDS.get(_member_suffix(name))
    if kind is None:
        raise _fail(
            f"bundle member {name!r} has suffix {_member_suffix(name)!r}, which this product maps "
            f"to no DESIGN-LAB asset kind ({', '.join(sorted(BUNDLE_MEMBER_KINDS))}); the receipt "
            "would have to state a format it cannot derive"
        )
    artifact = _digest("sha256:" + str(record.get("sha256")), f"bundle.files[{name}].sha256")
    return build_manifest({
        "deliverable_id": name,
        "artifact_sha256": artifact,
        "asset_kind": kind,
        "producer": {"operation_id": _text(metadata.get("native_attempt_id"),
                                           "bundle.metadata.native_attempt_id"),
                     "provider_id": host, "model_id": None},
        "inputs": inputs,
        "actions": [{"action": "c2pa.created", "when": when,
                     "software_agent": f"{host} {metadata.get('host_version')}"}],
        "rights_profile": BUNDLE_RIGHTS_PROFILE,
        "created_at": when,
    })


def receipt_for_bundle(manifest, *, job_id: str, created_at: str, receipted_at: str,
                       rollback, bundle_bytes_verified: bool, host_readback=None) -> dict:
    """Build, validate and return the DeliveryReceipt V2 for one published bundle.

    ``manifest`` is the archive manifest returned by
    :func:`design_lab.runtime.bundle_store.verify_bundle` (so its member digests have
    just been re-read from the published bytes). ``created_at`` is the bundle version
    row's own persisted timestamp -- the receipt stays clock-free, the caller supplies
    it. ``receipted_at`` is the native attempt's persisted ``ended_at``, the moment
    DESIGN-LAB recorded the host's readback. ``rollback`` must reference an existing
    immutable version; :func:`verify_receipt` runs here, inside the product path, so a
    document that violates the schema or overclaims its evidence is never persisted.

    Only members with a ``primary`` or ``preview`` role become deliverables, and
    ``host_readback`` defaults to ``None``: this product does not open the delivered
    artifact in a host, so the receipt it emits is always ``PARTIAL``.
    """
    if not isinstance(manifest, dict) or set(manifest) != {"schemaVersion", "primary",
                                                           "files", "metadata"}:
        raise _fail("bundle manifest must carry schemaVersion, primary, files and metadata")
    if manifest["schemaVersion"] != BUNDLE_SCHEMA_VERSION:
        raise _fail(
            f"bundle manifest schemaVersion must be {BUNDLE_SCHEMA_VERSION!r}; got "
            f"{manifest['schemaVersion']!r}"
        )
    files = manifest["files"]
    metadata = manifest["metadata"]
    if not isinstance(files, dict) or not files or not isinstance(metadata, dict):
        raise _fail("bundle manifest needs nonempty files and metadata")
    host = metadata.get("host")
    if host not in BUNDLE_HOSTS:
        raise _fail(
            f"bundle metadata host is {host!r}, which this product cannot name as a producer; "
            f"known native hosts are {', '.join(BUNDLE_HOSTS)}"
        )
    _text(metadata.get("host_version"), "bundle.metadata.host_version")
    _text(metadata.get("source_asset_id"), "bundle.metadata.source_asset_id")
    job = _text(job_id, "delivery.job_id")
    stamp = _timestamp(created_at, "delivery.created_at")
    when = _timestamp(receipted_at, "delivery.receipted_at")
    rollback_record = _normalize_rollback(rollback, "delivery.rollback")
    requirements = bundle_requirements(metadata, bundle_bytes_verified=bundle_bytes_verified)
    inputs = bundle_inputs(manifest)

    deliverables = []
    for name, record in sorted(files.items()):
        if not isinstance(record, dict) or record.get("role") not in BUNDLE_ROLE_EDITABLE:
            continue
        deliverables.append({
            "deliverable_id": name,
            "artifact_sha256": _digest("sha256:" + str(record.get("sha256")),
                                       f"bundle.files[{name}].sha256"),
            "byte_size": _integer(record.get("byte_size"), f"bundle.files[{name}].byte_size"),
            "editable": BUNDLE_ROLE_EDITABLE[record["role"]],
            "provenance_manifest": bundle_provenance(name=name, record=record, metadata=metadata,
                                                     host=host, inputs=inputs, when=when),
            "requirements": requirements,
            "rollback": rollback_record,
        })
    if not deliverables:
        raise _fail(
            "bundle declares no member with role 'primary' or 'preview', so nothing in it is a "
            "deliverable; an archive of inputs alone is not receiptable"
        )
    receipt = build_receipt({"job_id": job, "created_at": stamp, "deliverables": deliverables},
                            host_readback=host_readback)
    verify_receipt(receipt)
    return receipt
