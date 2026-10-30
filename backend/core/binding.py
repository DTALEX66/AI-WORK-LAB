# SPDX-License-Identifier: MIT
"""Result binding and verification contract, shared by both domains (audit F02, F03, F04).

Why one module: the audit's design-side findings all came from the same hole —
the work pack path ran a validator and the design path ran none, so a design
result could name any project, any task, any attempt, any version, an all-zero
digest and a traversing attachment and still be stored with 201. The fix is not
a second validator; it is one binding contract both domains go through.

Three principles the code enforces:

1. **Server facts win.** The task, attempt, pack and pinned revision are read
   out of the store. A field in the document is never taken as the truth; it is
   only ever compared against the server's own value, and a contradiction is a
   refusal. Adding a self-reported field therefore cannot launder a binding.
2. **One digest vocabulary.** A pack pins a *canonical binding document* (the
   identity fields, nothing else) and stores its digest. Verification recomputes
   the same document from a re-read of the pinned rows. The old code compared a
   digest of the whole rendered pack body with a digest of the plan detail — two
   different objects — and returned PASS on both branches.
3. **A refusal leaves nothing behind.** Every problem is collected before any
   write, and the handler raises; there is no path where a rejected result is
   half-stored or the attempt has already moved to RESULT_RECEIVED.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone

from backend.core import refs as ref_rules
from backend.core import origins

BINDING_SCHEMA_VERSION = "ai-work-lab/result-binding/v1"
DESIGN_RESULT_SCHEMA_VERSION = "ai-work-lab/design-result/v1"
WORK_RESULT_SCHEMA_VERSION = "worklab/external-repair-result/v1"
RESULT_SCHEMA_VERSIONS = (DESIGN_RESULT_SCHEMA_VERSION, WORK_RESULT_SCHEMA_VERSION)

#: How a design task treats a plan revision that moved after the pack was made.
#: LATEST_AT_PACK  — the pack answers the revision current when it was built; if
#:                   the plan has moved on, the pinned readback is still true but
#:                   the task is not *currently* satisfied, so validity is SUPERSEDED.
#: IMMUTABLE_PIN   — the task explicitly answers that one stored revision; reading
#:                   those exact bytes back is the acceptance, and the plan moving
#:                   on afterwards is recorded, not punished.
REVISION_POLICIES = ("LATEST_AT_PACK", "IMMUTABLE_PIN")

#: Whether a verdict still says something about *now*. A PASS whose validity is
#: SUPERSEDED/STALE/UNVERIFIABLE stays a historical fact but never supports a
#: current readiness claim (audit F04). Verdicts that are not a PASS answer
#: NOT_APPLICABLE — "not yet true" is not the same as "no longer true".
CURRENT_VALIDITY = ("CURRENT", "SUPERSEDED", "STALE", "UNVERIFIABLE", "NOT_APPLICABLE")

_ID_RE = re.compile(r"^[0-9a-f]{32}$")
_DIGEST_RE = re.compile(r"^[0-9a-f]{64}$")


def canonical_json(document) -> str:
    return json.dumps(document, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def canonical_digest(document) -> str:
    return hashlib.sha256(canonical_json(document).encode("utf-8")).hexdigest()


def parse_instant(text):
    if not isinstance(text, str) or not text.strip():
        return None
    try:
        moment = datetime.fromisoformat(text.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    return moment if moment.tzinfo else moment.replace(tzinfo=timezone.utc)


def design_binding_document(*, task_id: str, project_id: str, attempt_id: str,
                            design_project_id: str, plan_id: str, plan_revision,
                            plan_content_sha256: str, target_bindings: list,
                            revision_policy: str, acceptance_ref_digest: str,
                            candidate_version: str) -> dict:
    """The identity of one design attempt — the bytes both sides digest.

    Bookkeeping (timestamps, authors, the rendered handoff text) stays out, so
    re-rendering the pack body cannot change the binding.
    """
    return {
        "schemaVersion": BINDING_SCHEMA_VERSION,
        "flavor": "design_task_pack",
        "taskId": task_id,
        "projectId": project_id,
        "attemptId": attempt_id,
        "designProjectId": design_project_id,
        "planId": plan_id,
        "planRevision": plan_revision,
        "planContentSha256": plan_content_sha256,
        "targetBindings": sorted((canonical_json(row) for row in target_bindings)),
        "revisionPolicy": revision_policy,
        "acceptanceRefDigest": acceptance_ref_digest,
        "candidateVersion": candidate_version,
    }


def work_binding_document(*, task_id: str, project_id: str, attempt_id: str, pack_id: str,
                          pack_record_version: int, issue_fingerprints: list,
                          target_version: str, candidate_version: str) -> dict:
    return {
        "schemaVersion": BINDING_SCHEMA_VERSION,
        "flavor": "work_repair_pack",
        "taskId": task_id,
        "projectId": project_id,
        "attemptId": attempt_id,
        "packId": pack_id,
        "packRecordVersion": pack_record_version,
        "issueFingerprints": sorted(str(fp) for fp in issue_fingerprints),
        "targetVersion": target_version,
        "candidateVersion": candidate_version,
    }


def _problem(code: str, detail: str) -> str:
    return code + " " + detail


def _digest_forms(digest) -> tuple[str, ...]:
    """A digest and the ``sha256:``-prefixed spelling the design store publishes.

    assistance_plan and target_profile publish a revision's content digest as
    ``sha256:<64 hex>``; a client may state either spelling, and both mean the
    same bytes. Normalising here is a comparison detail, not a re-derivation: the
    value pinned at pack time is stored exactly as the design store published it.
    """
    text = str(digest or "").strip().lower()
    if not text:
        return ()
    if text.startswith("sha256:"):
        return (text, text[len("sha256:"):])
    return (text, "sha256:" + text)


def _check_text(document, field, code, problems, *, max_len: int = 400):
    value = document.get(field)
    if not isinstance(value, str) or not value.strip():
        problems.append(_problem(code, field + " must be a non-empty string"))
        return None
    if len(value) > max_len:
        problems.append(_problem(code, field + " exceeds " + repr(max_len) + " characters"))
        return None
    return value.strip()


def _check_ids_match(document, facts, fields, problems):
    """A self-reported id is only ever a claim; compare it to the server's fact."""
    for document_field, fact_key, label in fields:
        stated = document.get(document_field)
        if stated is None:
            continue
        stated = str(stated).strip()
        if not stated:
            continue
        if stated != str(facts[fact_key]):
            problems.append(_problem("RESULT_BINDING_WRONG_" + label.upper(),
                                     "document names " + repr(stated) + " but this attempt is "
                                     + repr(str(facts[fact_key])) + " (the store is the authority;"
                                       " a self-reported id cannot rebind a result)"))


def validate_design_result(document, facts, *, allowed_roots) -> list[str]:
    """Problems with one design result. Empty means it binds to this attempt.

    `facts` are server-side: task_id, project_id, attempt_id, design_project_id,
    plan_id, plan_revision, plan_content_sha256, binding_sha256,
    handoff_target_version, handoff_declared_at, existing_result_ids.
    """
    if not isinstance(document, dict):
        return [_problem("RESULT_DOCUMENT_MALFORMED", "result must be a JSON object")]
    problems: list[str] = []
    schema = str(document.get("schemaVersion") or "").strip()
    if schema != DESIGN_RESULT_SCHEMA_VERSION:
        problems.append(_problem("RESULT_SCHEMA_UNKNOWN",
                                 "design results must declare schemaVersion "
                                 + repr(DESIGN_RESULT_SCHEMA_VERSION) + ", found " + repr(schema)))
    result_id = _check_text(document, "resultId", "RESULT_ID_REQUIRED", problems)
    _check_text(document, "summary", "RESULT_SUMMARY_REQUIRED", problems, max_len=4000)
    _check_ids_match(document, facts, (
        ("taskId", "task_id", "task"),
        ("task_id", "task_id", "task"),
        ("attemptId", "attempt_id", "attempt"),
        ("attempt_id", "attempt_id", "attempt"),
        ("projectId", "project_id", "project"),
        ("project_id", "project_id", "project"),
        ("designProjectId", "design_project_id", "design_project"),
        ("design_project_id", "design_project_id", "design_project"),
        ("planId", "plan_id", "plan"),
        ("plan_id", "plan_id", "plan"),
    ), problems)

    stated_revision = document.get("planRevision", document.get("plan_revision"))
    if stated_revision is not None:
        if isinstance(stated_revision, bool) or not isinstance(stated_revision, int):
            problems.append(_problem("RESULT_PLAN_REVISION_MALFORMED",
                                     "planRevision must be a positive integer when stated"))
        elif stated_revision != facts["plan_revision"]:
            problems.append(_problem("RESULT_PLAN_REVISION_WRONG", "document claims revision "
                                    + repr(stated_revision) + " but the pack pinned revision "
                                    + repr(facts["plan_revision"])))

    stated_digest = document.get("contentSha256", document.get("body_sha256"))
    if stated_digest is not None:
        text = str(stated_digest).strip().lower()
        bare = text[len("sha256:"):] if text.startswith("sha256:") else text
        if not _DIGEST_RE.match(bare):
            problems.append(_problem("RESULT_DIGEST_MALFORMED",
                                     "a stated digest must be 64 hex characters, with or without "
                                     "the store's own sha256: prefix"))
        elif _ZERO_HEX_RE.match(bare):
            problems.append(_problem("RESULT_DIGEST_ZERO", "an all-zero digest is a placeholder, "
                                     "not a claim about bytes"))
        elif text not in _digest_forms(facts["plan_content_sha256"]) + _digest_forms(
                facts["binding_sha256"]):
            problems.append(_problem("RESULT_DIGEST_UNBOUND", "the stated digest matches neither the "
                                     "pinned plan revision nor the pinned binding document; a digest "
                                     "the server cannot re-derive is not evidence"))

    produced = parse_instant(document.get("producedAt", document.get("produced_at")))
    if produced is None and str(document.get("producedAt", "") or "").strip():
        problems.append(_problem("RESULT_PRODUCED_AT_INVALID", "producedAt is not an ISO instant"))
    declared_at = parse_instant(facts.get("handoff_declared_at"))
    if produced is not None and declared_at is not None and produced < declared_at:
        problems.append(_problem("RESULT_STALE", "result was produced at " + produced.isoformat()
                                 + " before the handoff was declared at " + declared_at.isoformat()
                                 + "; it answers an earlier handoff"))

    target_version = document.get("targetVersion")
    if target_version is not None:
        stated = str(target_version).strip()
        expected = str(facts.get("handoff_target_version") or "").strip()
        if not expected:
            problems.append(_problem("RESULT_HANDOFF_UNBOUND", "the declared handoff names no "
                                     "target version; re-declare it before importing"))
        elif stated != expected:
            problems.append(_problem("RESULT_WRONG_VERSION", "document names " + repr(stated)
                                     + ", the handoff was declared against " + repr(expected)))

    references = document.get("evidenceRefs", document.get("evidence_refs"))
    if references is None or not isinstance(references, list):
        problems.append(_problem("RESULT_EVIDENCE_LIST_REQUIRED",
                                 "evidenceRefs must be a list of references"))
    else:
        for reference in references:
            try:
                ref_rules.validate(reference, allowed_roots=allowed_roots)
            except ref_rules.RefError as exc:
                problems.append(str(exc))

    if result_id and result_id in set(facts.get("existing_result_ids") or ()):
        problems.append(_problem("RESULT_DUPLICATE", "result " + repr(result_id)
                                 + " was already imported for this pack; a second submission "
                                 "is not a second result"))
    return problems


def validate_work_envelope(document, facts, *, allowed_roots) -> list[str]:
    """The envelope checks the migrated WORK validator does not make itself.

    `repair_verification.validate_external_result` already binds pack, project,
    version, staleness and duplicates against the WORK record; this adds the
    shared half — the attempt this HTTP call is answering, the pinned binding
    digest, and reference scoping.
    """
    if not isinstance(document, dict):
        return [_problem("RESULT_DOCUMENT_MALFORMED", "result must be a JSON object")]
    problems: list[str] = []
    _check_ids_match(document, facts, (
        ("taskId", "task_id", "task"),
        ("task_id", "task_id", "task"),
        ("attemptId", "attempt_id", "attempt"),
        ("attempt_id", "attempt_id", "attempt"),
    ), problems)
    references = document.get("evidenceRefs")
    if references is not None and isinstance(references, list):
        for reference in references:
            try:
                ref_rules.validate(reference, allowed_roots=allowed_roots)
            except ref_rules.RefError as exc:
                problems.append(str(exc))
    elif references is not None:
        problems.append(_problem("RESULT_EVIDENCE_LIST_REQUIRED", "evidenceRefs must be a list"))
    return problems


def origin_for_write(declared, facts) -> str:
    """The chain origin a new row must carry, refusing a promotion to live."""
    chain = origins.combine(facts.get("project_origin"), facts.get("task_origin"),
                            facts.get("attempt_origin"), facts.get("handoff_origin"),
                            facts.get("pack_origin"))
    return origins.refuse_promotion(declared, chain, where="RESULT")


def current_validity(*, pinned_matches: bool, superseded: bool, readable: bool,
                     revision_policy: str) -> str:
    """Whether a verdict still says something about *now* (audit F04)."""
    if not readable:
        return "UNVERIFIABLE"
    if not pinned_matches:
        return "STALE"
    if superseded and revision_policy != "IMMUTABLE_PIN":
        return "SUPERSEDED"
    return "CURRENT"


_ZERO_HEX_RE = re.compile(r"^0{64}$")
