# SPDX-License-Identifier: MIT
"""DL-P1-180 knowledge feedback candidate: the only outbound knowledge projection.

This module extends the existing ``candidate-knowledge.schema.json`` (V1, the
"compiled knowledge unit" contract) into
``assurance-knowledge-candidate-v2.schema.json`` by carrying the whole feedback
loop the V1 document left implicit: the DESIGN-LAB revision, job/operation and
evidence digests the candidate came from, its rights gate state and license, an
explicit revocation entrypoint, and a human review that must be signed before
anything leaves this project.

.. warning::
   An AI agent may never approve an export to ArcheAxis. ``build_candidate`` has
   no review argument at all, so it can only ever produce
   ``PENDING_HUMAN_APPROVAL``; ``approve`` demands ``reviewer_kind="human"``
   with a named reviewer and an RFC3339 timestamp, and the schema itself makes
   an ``APPROVED`` review without a human reviewer invalid. ``export_payload``
   is the only outbound projection and refuses anything not approved by a
   named human, anything revoked, and any payload carrying private material.

Boundary: structural contracts and validation only. No network, no host, no
model call, no database and no filesystem write; an unverifiable candidate fails
closed with :class:`~design_lab.assurance.AssuranceError`.

Honesty limit: this module binds an approval to a claimed human identity and
timestamp and refuses every automated actor. It cannot verify that the named
person exists or really reviewed the candidate; that needs the out-of-band
attestation record of the Human Gate, which is out of scope here.
"""
from __future__ import annotations

from functools import lru_cache
import json
import re
from typing import Mapping

from ..runtime.attempt_contract import request_hash
from ..runtime.state_resources import repo_resource
from . import AssuranceError, require_digest, require_rfc3339, require_text, utc_now_rfc3339

SCHEMA_PATH = repo_resource('schemas/assurance-knowledge-candidate-v2.schema.json')
V1_SCHEMA_PATH = repo_resource('schemas/candidate-knowledge.schema.json')

CANDIDATE_VERSION = "design-lab/assurance-knowledge-candidate/v2"
EXPORT_VERSION = "design-lab/assurance-knowledge-candidate-export/v1"
REVOCATION_VERSION = "design-lab/assurance-knowledge-candidate-revocation/v1"
V1_VERSION = "design-lab/candidate-knowledge/v1"

CANDIDATE_TYPES = ("METHOD", "JURY_CORRECTION", "PRODUCTION_LESSON")
RIGHTS_GATE_STATES = ("UNCHECKED", "CHECKED", "BLOCKED")
REVIEW_STATES = ("PENDING_HUMAN_APPROVAL", "APPROVED", "REJECTED")
REVIEWER_KIND_HUMAN = "human"
V1_KNOWLEDGE_TYPES = {
    "METHOD": "method",
    "JURY_CORRECTION": "rubric",
    "PRODUCTION_LESSON": "rule",
}
DEFAULT_REVOCATION_ENTRYPOINT = "design-lab/knowledge/revoke"

#: Owner ruling 2026-10-20: 「编号问题留出可填写位置，用户自行填写或者选择用没用」. The literal is
#: the explicit "not used" choice. A blank or absent id stays a refusal, because "the operator
#: declared there is no job id" and "nobody answered" are different facts and a provenance record
#: must not have to guess between them. Nothing here ever substitutes a value.
PROVENANCE_UNUSED = "UNUSED"


def provenance_state(value) -> str:
    """How a reader should describe what an id field holds: a supplied id, or a declared non-use."""
    if isinstance(value, str) and value.strip() == PROVENANCE_UNUSED:
        return "EXPLICITLY_UNUSED"
    return "USER_SUPPLIED"


def require_provenance_id(value, field: str) -> str:
    """``require_text`` plus the one accepted exception: the literal ``UNUSED``."""
    if isinstance(value, str) and value.strip() == PROVENANCE_UNUSED:
        return PROVENANCE_UNUSED
    return require_text(value, field)

# Field names that must never leave this project, whatever plane put them there.
PRIVATE_FIELD_NAMES = frozenset({
    "client_asset", "client_assets", "client_brief", "client_briefs", "brief_body",
    "brief_text", "raw_brief", "asset_bytes", "raw_bytes", "binary", "blob",
    "base64", "data_uri", "data_url", "transcript", "raw_transcript", "chat_log",
    "chat_history", "messages", "conversation", "dialogue", "prompt", "prompts",
    "raw_prompt", "system_prompt", "file_path", "filepath", "local_path",
    "source_path", "absolute_path", "path", "secrets", "credentials", "api_key",
    "access_token", "token",
})
_PRIVATE_FLAGS = ("private", "confidential", "internal_only", "restricted")
_TRANSCRIPT_MARKER = re.compile(
    r'"(?:role|speaker)"\s*:\s*"(?:user|assistant|system|human|ai|model)"', re.I)
_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+")
_URL_CREDENTIALS = re.compile(r"[A-Za-z][A-Za-z0-9+.-]*://[^/\s@]+@")
_DATA_URI = re.compile(r"^data:[^,]*;base64,", re.I)
_BOUNDARY = r"(?:^|[\s\"'(\[=,:;])"
_PATTERNS = (
    # Paths are matched wherever they appear in prose, not only as a whole value.
    (re.compile(_BOUNDARY + r"[A-Za-z]:[\\/]"), "a Windows drive path"),
    (re.compile(_BOUNDARY + r"\\\\[^\\]"), "a UNC network path"),
    (re.compile(_BOUNDARY + r"/(?!/)"), "a POSIX absolute path"),
    (re.compile(_BOUNDARY + r"~/"), "a home-relative path"),
    (re.compile(r"file://", re.I), "a file:// URL"),
    (re.compile(_BOUNDARY + r"\.\.[\\/]"), "a parent-directory traversal"),
    (re.compile(_BOUNDARY + r"(?:[A-Za-z0-9_.-]+[\\/])+[A-Za-z0-9_.-]+\.[A-Za-z0-9]{1,6}"),
     "a relative path naming a file"),
)
_SHA256_PREFIX = "sha256:"


@lru_cache(maxsize=1)
def schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def v1_schema() -> dict:
    return json.loads(V1_SCHEMA_PATH.read_text(encoding="utf-8"))


def _validate(document: dict, *, subdef: str | None = None, schema_path=None) -> None:
    from jsonschema import Draft202012Validator

    loaded = schema() if schema_path is None else schema_path
    if subdef is not None:
        subschema = dict(loaded["$defs"][subdef])
        subschema["$defs"] = loaded["$defs"]
        validator = Draft202012Validator(subschema)
        label = f"#/$defs/{subdef}"
        name = SCHEMA_PATH.name
    else:
        validator = Draft202012Validator(loaded)
        label = "#"
        name = SCHEMA_PATH.name if schema_path is None else V1_SCHEMA_PATH.name
    errors = sorted(validator.iter_errors(document), key=lambda error: list(error.path))
    if errors:
        first = errors[0]
        where = "/".join(str(part) for part in first.path)
        raise AssuranceError(
            f"document violates {name}{('/' + where) if where else ''} ({label}): "
            f"{first.message}"
        )


def _document(candidate, function: str) -> dict:
    if not isinstance(candidate, Mapping):
        raise AssuranceError(
            f"{function} requires a knowledge candidate document; "
            f"got {type(candidate).__name__}"
        )
    try:
        return json.loads(json.dumps(candidate, allow_nan=False))
    except (TypeError, ValueError) as exc:
        raise AssuranceError(
            f"{function} requires a JSON-serializable knowledge candidate document: {exc}"
        ) from exc


def require_design_lab_sha(value, field: str = "source.design_lab_sha") -> str:
    """A nonzero lowercase DESIGN-LAB revision (accepts a bare or sha256: -prefixed hex)."""
    text = require_text(value, field)
    body = text[len(_SHA256_PREFIX):] if text.lower().startswith(_SHA256_PREFIX) else text
    if not re.fullmatch(r"[0-9a-f]{7,64}", body) or set(body) == {"0"}:
        raise AssuranceError(
            f"{field} must be a nonzero lowercase hexadecimal DESIGN-LAB revision "
            f"(7-64 hex characters); got {text!r}"
        )
    return body


def assert_no_private_payload(payload, *, where: str = "payload",
                              allow_contact_email: bool = False) -> None:
    """Refuse payload material that must not leave this project.

    Rejects private-flagged fields, absolute/UNC/drive/traversal paths, relative
    paths naming a file, e-mail addresses, URLs carrying credentials, embedded
    base64 data URIs and transcript shapes. ``allow_contact_email`` exists only
    for the reviewer identity of an already approved export record; the exported
    payload itself is always scanned strictly.
    """
    _scan(payload, "$", where, allow_contact_email)


def _fail(where: str, path: str, reason: str) -> None:
    raise AssuranceError(
        f"{where}{path} must not leave this project: it is {reason}"
    )


def _scan(node, path: str, where: str, allow_contact_email: bool) -> None:
    if isinstance(node, Mapping):
        for key, value in node.items():
            name = str(key)
            folded = name.casefold()
            if folded in PRIVATE_FIELD_NAMES:
                _fail(where, f"{path}/{name}", f"a private field name ({name!r})")
            if folded.endswith("_private") or folded.startswith("private_"):
                _fail(where, f"{path}/{name}", "a field flagged private by its name")
            if folded in _PRIVATE_FLAGS and value is True:
                _fail(where, f"{path}/{name}", f"a field flagged {name!r}")
            _scan(value, f"{path}/{name}", where, allow_contact_email)
        return
    if isinstance(node, (list, tuple)):
        for index, value in enumerate(node):
            _scan(value, f"{path}/{index}", where, allow_contact_email)
        return
    if not isinstance(node, str):
        return
    if _DATA_URI.match(node):
        _fail(where, path, "an embedded base64 data URI (a raw asset)")
    for pattern, reason in _PATTERNS:
        if pattern.search(node):
            _fail(where, path, reason)
    if _URL_CREDENTIALS.search(node):
        _fail(where, path, "a URL carrying credentials")
    if not allow_contact_email and _EMAIL.search(node):
        _fail(where, path, "an e-mail address")
    if _TRANSCRIPT_MARKER.search(node):
        _fail(where, path, "a raw transcript")


def build_candidate(*, candidate_id, candidate_type, source, rights, payload,
                    supersedes=None, created_at=None,
                    revocation_entrypoint=DEFAULT_REVOCATION_ENTRYPOINT) -> dict:
    """Build a candidate that is always ``PENDING_HUMAN_APPROVAL``.

    There is deliberately no ``review`` parameter: no argument to this function
    can produce an APPROVED candidate, so approval can only come from
    :func:`approve` with a named human reviewer and a timestamp. ``created_at``
    defaults to the current UTC time; pass it explicitly for a reproducible
    document.
    """
    require_text(candidate_id, "candidate_id")
    if candidate_type not in CANDIDATE_TYPES:
        raise AssuranceError(
            f"candidate_type must be one of {', '.join(CANDIDATE_TYPES)}; "
            f"got {candidate_type!r}"
        )
    if not isinstance(source, Mapping):
        raise AssuranceError("source must be an object with provenance digests")
    if not isinstance(rights, Mapping):
        raise AssuranceError("rights must be an object describing the rights gate")
    if not isinstance(payload, Mapping):
        raise AssuranceError("payload must be the lesson/method/correction content object")

    design_lab_sha = require_design_lab_sha(source.get("design_lab_sha"))
    job_id = require_provenance_id(source.get("job_id"), "source.job_id")
    operation_id = require_provenance_id(source.get("operation_id"), "source.operation_id")
    evidence_sha256 = require_digest(source.get("evidence_sha256"), "source.evidence_sha256")

    rights_gate_state = rights.get("rights_gate_state")
    if rights_gate_state not in RIGHTS_GATE_STATES:
        raise AssuranceError(
            f"rights.rights_gate_state must be one of {', '.join(RIGHTS_GATE_STATES)}; "
            f"got {rights_gate_state!r}"
        )
    require_text(rights.get("license_id"), "rights.license_id")
    for field in ("contains_client_asset", "contains_third_party_asset"):
        if not isinstance(rights.get(field), bool):
            raise AssuranceError(f"rights.{field} must be a boolean")
    redaction_note = rights.get("redaction_note")
    if rights["contains_client_asset"]:
        if not isinstance(redaction_note, str) or not redaction_note.strip():
            raise AssuranceError(
                "rights.contains_client_asset is true without a redaction_note; a candidate "
                "built from client material must record how it was redacted"
            )
        assert_no_private_payload(redaction_note, where="rights.redaction_note")
    elif redaction_note is not None:
        require_text(redaction_note, "rights.redaction_note")

    require_text(payload.get("title"), "payload.title")
    require_text(payload.get("statement"), "payload.statement")
    if not isinstance(payload.get("applies_to"), list) or not payload["applies_to"]:
        raise AssuranceError("payload.applies_to must be a non-empty list of design domains")
    assert_no_private_payload(payload, where="payload")
    try:
        payload_sha256 = request_hash(dict(payload))
    except (TypeError, ValueError) as exc:
        raise AssuranceError(f"payload must be JSON-serializable and finite: {exc}") from exc

    if supersedes is not None:
        require_text(supersedes, "supersedes")
        if supersedes == candidate_id:
            raise AssuranceError("a candidate may not supersede itself")
    require_text(revocation_entrypoint, "revocation.entrypoint")

    document = {
        "schemaVersion": CANDIDATE_VERSION,
        "candidate_id": candidate_id,
        "candidate_type": candidate_type,
        "source": {
            "design_lab_sha": design_lab_sha,
            "job_id": job_id,
            "operation_id": operation_id,
            "evidence_sha256": evidence_sha256,
        },
        "rights": {
            "license_id": rights["license_id"],
            "rights_gate_state": rights_gate_state,
            "contains_client_asset": rights["contains_client_asset"],
            "contains_third_party_asset": rights["contains_third_party_asset"],
            "redaction_note": redaction_note,
        },
        "payload": dict(payload),
        "payload_sha256": payload_sha256,
        "supersedes": supersedes,
        "revocation": {
            "revocable": True,
            "entrypoint": revocation_entrypoint,
            "state": "ACTIVE",
            "reason": None,
            "revoked_by": None,
            "revoked_at": None,
        },
        "review": {
            "state": "PENDING_HUMAN_APPROVAL",
            "reviewer_id": None,
            "reviewer_kind": None,
            "reviewed_at": None,
            "note": None,
        },
        "created_at": require_rfc3339(created_at or utc_now_rfc3339(), "created_at"),
    }
    _validate(document)
    return document


def validate_candidate(document) -> dict:
    """Validate a stored candidate against the v2 contract; returns a JSON copy.

    The write functions below already validate what they build. This entry point
    exists for read paths: a row that was stored months ago is re-checked against
    today's contract instead of being printed as if a valid write had produced it.
    """
    checked = _document(document, "validate_candidate")
    _validate(checked)
    return checked


def _require_human_reviewer(reviewer_id, reviewer_kind, reviewed_at) -> tuple:
    if reviewer_kind != REVIEWER_KIND_HUMAN:
        raise AssuranceError(
            f"an agent cannot approve an export to ArcheAxis: reviewer_kind must be "
            f"{REVIEWER_KIND_HUMAN!r} with a named human reviewer, got {reviewer_kind!r}"
        )
    return (
        require_text(reviewer_id, "reviewer_id"),
        require_rfc3339(reviewed_at, "reviewed_at"),
    )


def _reviewable(document: dict, *, action: str) -> dict:
    _validate(document)
    state = document["review"]["state"]
    if state == "APPROVED":
        raise AssuranceError(
            f"candidate {document['candidate_id']!r} is already APPROVED by "
            f"{document['review']['reviewer_id']!r}; a decision is not re-signed or upgraded"
        )
    if state == "REJECTED":
        raise AssuranceError(
            f"{action} is refused: candidate {document['candidate_id']!r} was already REJECTED "
            "by a human, so it must be rebuilt rather than re-labelled"
        )
    rights = document["rights"]
    if rights["rights_gate_state"] != "CHECKED":
        raise AssuranceError(
            f"rights gate state is {rights['rights_gate_state']}; only CHECKED may be reviewed "
            "for export to ArcheAxis"
        )
    if rights["contains_client_asset"] and not (rights.get("redaction_note") or "").strip():
        raise AssuranceError(
            "contains_client_asset is true without a redaction_note; client material may not "
            "leave this project"
        )
    require_design_lab_sha(document["source"]["design_lab_sha"])
    require_digest(document["source"]["evidence_sha256"], "source.evidence_sha256")
    require_digest(document["payload_sha256"], "payload_sha256")
    return document


def approve(candidate, *, reviewer_id, reviewer_kind, reviewed_at, note=None) -> dict:
    """Record a human approval. Returns a new document; never mutates the input."""
    document = _document(candidate, "approve")
    reviewer_id, reviewed_at = _require_human_reviewer(reviewer_id, reviewer_kind, reviewed_at)
    document = _reviewable(document, action="approve")
    if note is not None:
        require_text(note, "note")
    document["review"] = {
        "state": "APPROVED",
        "reviewer_id": reviewer_id,
        "reviewer_kind": REVIEWER_KIND_HUMAN,
        "reviewed_at": reviewed_at,
        "note": note,
    }
    _validate(document)
    return document


def reject(candidate, *, reviewer_id, reviewer_kind, reviewed_at, reason) -> dict:
    """Record a human rejection. Also a human gate: automation may not close it."""
    document = _document(candidate, "reject")
    reviewer_id, reviewed_at = _require_human_reviewer(reviewer_id, reviewer_kind, reviewed_at)
    document = _reviewable(document, action="reject")
    document["review"] = {
        "state": "REJECTED",
        "reviewer_id": reviewer_id,
        "reviewer_kind": REVIEWER_KIND_HUMAN,
        "reviewed_at": reviewed_at,
        "note": require_text(reason, "reason"),
    }
    _validate(document)
    return document


def revoke(candidate, *, reason, revoked_by, revoked_at=None) -> dict:
    """Return a revocation record for a candidate.

    Revocation may be requested by automation because it only removes privilege;
    approval may not. The record is applied with :func:`apply_revocation`.
    """
    document = _document(candidate, "revoke")
    _validate(document)
    revocation = document["revocation"]
    if revocation.get("revocable") is not True:
        raise AssuranceError(
            f"candidate {document['candidate_id']!r} is not revocable, so it may not be "
            "exported at all"
        )
    if revocation.get("state") == "REVOKED":
        raise AssuranceError(f"candidate {document['candidate_id']!r} is already revoked")
    record = {
        "schemaVersion": REVOCATION_VERSION,
        "candidate_id": document["candidate_id"],
        "entrypoint": require_text(revocation.get("entrypoint"), "revocation.entrypoint"),
        "reason": require_text(reason, "reason"),
        "revoked_by": require_text(revoked_by, "revoked_by"),
        "revoked_at": require_rfc3339(revoked_at or utc_now_rfc3339(), "revoked_at"),
        "export_blocked": True,
    }
    assert_no_private_payload(record, where="revocation_record")
    return record


def apply_revocation(candidate, revocation_record) -> dict:
    """Return a candidate marked REVOKED; never mutates the input."""
    document = _document(candidate, "apply_revocation")
    _validate(document)
    if not isinstance(revocation_record, Mapping):
        raise AssuranceError("apply_revocation requires a revocation record object")
    if revocation_record.get("schemaVersion") != REVOCATION_VERSION:
        raise AssuranceError(
            f"revocation record schemaVersion must be {REVOCATION_VERSION!r}; "
            f"got {revocation_record.get('schemaVersion')!r}"
        )
    if revocation_record.get("candidate_id") != document["candidate_id"]:
        raise AssuranceError(
            f"revocation record is for {revocation_record.get('candidate_id')!r} but the "
            f"candidate is {document['candidate_id']!r}; a revocation is never transferable"
        )
    if revocation_record.get("export_blocked") is not True:
        raise AssuranceError("a revocation record must set export_blocked to true")
    document["revocation"] = {
        "revocable": True,
        "entrypoint": document["revocation"]["entrypoint"],
        "state": "REVOKED",
        "reason": require_text(revocation_record.get("reason"), "revocation_record.reason"),
        "revoked_by": require_text(revocation_record.get("revoked_by"),
                                   "revocation_record.revoked_by"),
        "revoked_at": require_rfc3339(revocation_record.get("revoked_at"),
                                      "revocation_record.revoked_at"),
    }
    _validate(document)
    return document


def export_payload(candidate) -> dict:
    """The only outbound projection: a human-approved, unrevoked, non-private candidate."""
    document = _document(candidate, "export_payload")
    _validate(document)
    review = document["review"]
    if review["state"] != "APPROVED":
        raise AssuranceError(
            f"candidate {document['candidate_id']!r} is {review['state']}; only a candidate "
            "approved by a named human may be exported to ArcheAxis"
        )
    if review["reviewer_kind"] != REVIEWER_KIND_HUMAN:
        raise AssuranceError(
            f"candidate {document['candidate_id']!r} claims an approval whose reviewer_kind is "
            f"{review['reviewer_kind']!r}; an agent approval is not an approval"
        )
    require_text(review["reviewer_id"], "review.reviewer_id")
    require_rfc3339(review["reviewed_at"], "review.reviewed_at")
    if document["rights"]["rights_gate_state"] != "CHECKED":
        raise AssuranceError(
            f"rights gate state is {document['rights']['rights_gate_state']}; a candidate may "
            "only leave this project with a CHECKED rights gate"
        )
    revocation = document["revocation"]
    if revocation.get("state") == "REVOKED":
        raise AssuranceError(
            f"candidate {document['candidate_id']!r} was revoked at "
            f"{revocation.get('revoked_at')!r} by {revocation.get('revoked_by')!r}; a revoked "
            "candidate can never be exported"
        )
    if revocation.get("revocable") is not True or not str(revocation.get("entrypoint") or ""):
        raise AssuranceError(
            f"candidate {document['candidate_id']!r} has no revocation path, so it must not "
            "leave this project"
        )

    assert_no_private_payload(document["payload"], where="payload")
    exported = {
        "schemaVersion": EXPORT_VERSION,
        "candidate_id": document["candidate_id"],
        "candidate_type": document["candidate_type"],
        "source": dict(document["source"]),
        "license_id": document["rights"]["license_id"],
        "payload": dict(document["payload"]),
        "payload_sha256": document["payload_sha256"],
        "supersedes": document["supersedes"],
        "revocation": {
            "revocable": True,
            "entrypoint": revocation["entrypoint"],
            "state": "ACTIVE",
        },
        "review": {
            "state": "APPROVED",
            "reviewer_id": review["reviewer_id"],
            "reviewer_kind": REVIEWER_KIND_HUMAN,
            "reviewed_at": review["reviewed_at"],
        },
    }
    # The reviewer identity may legitimately be a contact address; nothing else may.
    assert_no_private_payload(exported, where="export", allow_contact_email=True)
    _validate(exported, subdef="export")
    return exported


def to_v1_projection(candidate) -> dict:
    """Downward projection onto the existing ``candidate-knowledge.schema.json`` contract.

    Read-only: it never produces a v1 record that claims more than the v2
    candidate does. ``JURY_CORRECTION`` maps to ``rubric`` and
    ``PRODUCTION_LESSON`` to ``rule`` because the V1 enum has no exact
    counterpart; ``compiled_ref`` stays null because this module compiles
    nothing.
    """
    document = _document(candidate, "to_v1_projection")
    _validate(document)
    state = {
        "PENDING_HUMAN_APPROVAL": "review-required",
        "APPROVED": "compiled",
        "REJECTED": "quarantined",
    }[document["review"]["state"]]
    if document["revocation"].get("state") == "REVOKED":
        state = "quarantined"
    if document["rights"]["rights_gate_state"] != "CHECKED":
        state = "quarantined" if state == "compiled" else state
    source = document["source"]
    projection = {
        "candidate_id": document["candidate_id"],
        "schemaVersion": V1_VERSION,
        "source_id": f"{source['job_id']}:{source['operation_id']}",
        "knowledge_type": V1_KNOWLEDGE_TYPES[document["candidate_type"]],
        "content_hash": document["payload_sha256"],
        "state": state,
        "compiled_ref": None,
        "created_at": document["created_at"],
    }
    validate_v1_projection(projection)
    return projection


def validate_v1_projection(document) -> dict:
    """Check a projection against the existing V1 candidate-knowledge contract."""
    if not isinstance(document, Mapping):
        raise AssuranceError("a candidate-knowledge projection must be an object")
    errors_document = json.loads(json.dumps(document, allow_nan=False))
    _validate(errors_document, schema_path=v1_schema())
    return errors_document
