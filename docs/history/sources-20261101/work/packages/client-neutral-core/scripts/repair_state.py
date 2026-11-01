"""CL-04: the durable lifecycle of a repair pack -- record, approve, declare, close.

CL-03 produces material and exports it. This module is where that material gets an identity that survives
a restart, and where every later claim about it has to answer to a fact that already exists:

1. **Recording writes a draft, never a decision.** `record_pack` accepts the two statuses the projection can
   honestly produce (WAITING_APPROVAL / BLOCKED) and refuses anything else, so there is no code path from
   "export" to "approved". The stored row keeps the immutable pack snapshot and the mutable lifecycle apart:
   the snapshot is what the human copied; the lifecycle says what has actually happened since.

2. **Approval resolves a grant in the existing trusted record.** The reference is not a free-text note: it
   must exist in the same `control-trusted-grants.json` the Control plane reads, must not be expired, and
   must cover `work-unit:<packId>` (or `*`). This module reads that record; it never creates or edits it.
   Grants arrive as an explicit path, so no default file silently authorizes anything.

3. **Four handoff claims stay separate.** `declare_handoff` writes only the user's own statements
   (copiedByUser / userDeclaredHandoff). `externalReceipt` is not declarable here -- only an imported
   external document (CL-05) can fill it -- because "the user says they handed it over" and "the receiving
   system said it got it" are different facts with different remedies.

4. **Closing needs evidence of the right strength.** `record_outcome` only runs from APPROVED, and SUCCEEDED
   requires `reproducible` or `independent` evidence with at least one reference. A self-report can close
   nothing; it belongs in "待核验" until CL-05's independent verification reads the store facts.

Every mutation is a compare-and-swap: the caller passes the version it read, and a stale version is refused
rather than overwritten. Repeating an already-applied request is a no-op, so a retried CLI run does not mint
a second version.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

import issue_projection
import repair_pack_projection as projection
import repair_verification as verification

RECORD_SCHEMA_VERSION = "worklab/repair-record/v1"

# The statuses a stored row can hold. The projection may only record the first two; APPROVED is minted by
# `approve_pack` after a grant resolves, and the three terminal statuses only by `record_outcome`.
RECORDABLE_STATUSES = ("WAITING_APPROVAL", "BLOCKED")
OPEN_STATUSES = ("WAITING_APPROVAL", "APPROVED")
TERMINAL_STATUSES = ("SUCCEEDED", "FAILED", "BLOCKED")
OUTCOMES = ("SUCCEEDED", "FAILED", "BLOCKED")
LIFECYCLE_STATUSES = RECORDABLE_STATUSES + ("APPROVED",) + OUTCOMES

# `services/task-governance/completion_authority.py` owns this four-level scale; a fifth would be a second
# vocabulary for the same question.
EVIDENCE_LEVELS = ("none", "self", "reproducible", "independent")
CLOSING_EVIDENCE_LEVELS = ("reproducible", "independent")

HANDOFF_CLAIMS = ("copiedByUser", "userDeclaredHandoff")
EXTERNAL_ONLY_CLAIM = "externalReceipt"

# Same vocabulary as services/control/control_service.py; the reader below mirrors that one's semantics and
# the test suite pins both against the same fixture so the two copies cannot drift apart silently.
GRANT_SCOPE_ANY = "*"
GRANT_SCOPE_WORK_UNIT_PREFIX = "work-unit:"


def _now_string() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _empty_handoff_record() -> dict[str, Any]:
    return {
        "copiedByUser": {"declared": False, "declaredAt": None, "channel": None},
        "userDeclaredHandoff": {"declared": False, "declaredAt": None, "channel": None,
                                "claimedRecipient": None},
        "externalReceipt": {"received": False, "receivedAt": None, "externalId": None, "source": None},
    }


def _record_payload(pack: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schemaVersion": RECORD_SCHEMA_VERSION,
        "pack": dict(pack),
        "handoffRecord": _empty_handoff_record(),
        "approval": {"authorizationRef": None, "approvedAt": None},
        "outcome": None,
        # CL-05: imported result documents, the pending one awaiting a re-read, and the verdicts that re-read
        # produced. The imported claim lives apart from the outcome so a document can never close a row.
        "externalResults": [],
        "pendingVerification": None,
        "verifications": [],
        "history": [],
    }


def _read_payload(row: Mapping[str, Any]) -> dict[str, Any]:
    payload = row.get("payload")
    if not isinstance(payload, dict) or payload.get("schemaVersion") != RECORD_SCHEMA_VERSION:
        raise ValueError(f"REPAIR_RECORD_UNREADABLE plan {row.get('planId')} does not carry a "
                         f"{RECORD_SCHEMA_VERSION} payload; refusing to mutate a shape this module does "
                         "not own")
    return payload


def _write(store: Any, *, plan_id: str, project_id: str, status: str, payload: dict[str, Any],
           expected_version: int, approved_at: str | None) -> dict[str, Any]:
    return store.save_action_plan({"planId": plan_id, "projectId": project_id, "status": status,
                                   "approvedAt": approved_at, "payload": payload},
                                  expected_version=expected_version)


def record_pack(store: Any, pack: Mapping[str, Any]) -> dict[str, Any]:
    """Persist a generated pack as a draft. Idempotent for the same pack bytes.

    A pack that fails `validate_repair_pack` is refused before it can become a durable row: the store is
    the single runtime truth, and a row there is what a later result will be checked against.
    """
    problems = projection.validate_repair_pack(pack)
    status = str(pack.get("status") or "")
    if status not in RECORDABLE_STATUSES:
        raise ValueError(f"REPAIR_RECORD_NOT_A_DRAFT status {status!r} is outside {RECORDABLE_STATUSES}: the "
                         "export/projection path writes what it generated, and APPROVED is a grant-backed "
                         "decision made by approve_pack, never by an export")
    if problems:
        raise ValueError("REPAIR_RECORD_INVALID " + "; ".join(problems))
    plan_id = str(pack["packId"])
    project_id = str((pack.get("target") or {}).get("projectId") or "")
    return store.save_action_plan({"planId": plan_id, "projectId": project_id, "status": status,
                                   "payload": _record_payload(pack)})


def read_record(store: Any, plan_id: str) -> dict[str, Any] | None:
    return store.read_action_plan(plan_id)


def list_records(store: Any, project_id: str | None = None) -> list[dict[str, Any]]:
    return store.list_action_plans(project_id)


def load_grants(path: Path | str | None, *, now: str | None = None) -> tuple[dict[str, str], dict[str, Any]]:
    """Read the one local authorization record: grant id -> scope. Missing/expired/malformed fail closed.

    Mirrors `services/control/control_service.py::_trusted_grants` field by field. Kept as its own reader
    because that module pulls the whole Control plane (jsonschema, permission gate); the shared semantics
    are pinned by a test that feeds one fixture to both readers and compares the results.
    """
    state: dict[str, Any] = {"path": None, "readable": False, "grants": 0, "expired": 0,
                             "malformed": 0, "note": "没有配置授权记录路径，任何授权都解不开。"}
    if path is None:
        return {}, state
    grants_path = Path(path)
    state["path"] = grants_path.name
    if not grants_path.is_file():
        state["note"] = f"授权记录不存在：{grants_path.name}（缺记录＝没有授权，不是放行）"
        return {}, state
    try:
        document = json.loads(grants_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        state["note"] = f"授权记录读不开：{type(error).__name__}，按没有授权处理。"
        return {}, state
    entries = document.get("grants") if isinstance(document, dict) else None
    if not isinstance(entries, list):
        state["note"] = "授权记录形状不对（grants 不是数组），按没有授权处理。"
        return {}, state
    moment = now or _now_string()
    resolved: dict[str, str] = {}
    for entry in entries:
        if not isinstance(entry, dict):
            state["malformed"] += 1
            continue
        grant_id = str(entry.get("grant_id") or "").strip()
        scope = str(entry.get("scope") or "").strip()
        if not grant_id or not scope:
            state["malformed"] += 1
            continue
        expires_at = entry.get("expires_at")
        if isinstance(expires_at, str) and expires_at.strip() and expires_at.strip() <= moment:
            state["expired"] += 1
            continue
        resolved[grant_id] = scope
    state.update(readable=True, grants=len(resolved),
                 note=f"本地授权记录已读：{len(resolved)} 条有效（内容不对外投影）。")
    return resolved, state


def grant_covers(scope: str, work_unit_id: str) -> bool:
    """Same question Control asks: does this scope authorize THIS work unit?"""
    text = str(scope or "").strip()
    if text == GRANT_SCOPE_ANY:
        return True
    return text == f"{GRANT_SCOPE_WORK_UNIT_PREFIX}{str(work_unit_id).strip()}"


def approve_pack(store: Any, plan_id: str, *, authorization_ref: str, grants: Mapping[str, str],
                 expected_version: int, approved_at: str | None = None) -> dict[str, Any]:
    """WAITING_APPROVAL -> APPROVED, only when the named grant resolves and covers this pack."""
    row = store.read_action_plan(plan_id)
    if row is None:
        raise ValueError(f"REPAIR_RECORD_NOT_FOUND plan {plan_id}")
    payload = _read_payload(row)
    reference = str(authorization_ref or "").strip()
    if not reference:
        raise ValueError("REPAIR_GRANT_REQUIRED approval needs the grant id it resolves, not a boolean")
    current_approval = payload.get("approval") or {}
    if row["status"] == "APPROVED":
        if current_approval.get("authorizationRef") == reference:
            return {**row, "changed": False}
        raise ValueError(f"REPAIR_RECORD_ALREADY_APPROVED plan {plan_id} already holds grant "
                         f"{current_approval.get('authorizationRef')!r}")
    if row["status"] != "WAITING_APPROVAL":
        raise ValueError(f"REPAIR_RECORD_NOT_APPROVABLE plan {plan_id} is {row['status']}; only a ready "
                         "draft (WAITING_APPROVAL) can be approved -- a blocked pack has no verification "
                         "route to approve")
    scope = grants.get(reference)
    if scope is None:
        raise ValueError(f"REPAIR_GRANT_NOT_FOUND grant {reference!r} does not resolve in the trusted "
                         f"record ({len(grants)} valid grant(s)); approval without a grant is self-grant")
    if not grant_covers(scope, plan_id):
        raise ValueError(f"REPAIR_GRANT_SCOPE_MISMATCH grant {reference!r} covers {scope!r}, not "
                         f"{GRANT_SCOPE_WORK_UNIT_PREFIX}{plan_id}")
    moment = approved_at or _now_string()
    payload["approval"] = {"authorizationRef": reference, "approvedAt": moment}
    payload["history"] = list(payload.get("history") or []) + [
        {"at": moment, "event": "APPROVED", "authorizationRef": reference}]
    result = _write(store, plan_id=plan_id, project_id=str(row["projectId"]), status="APPROVED",
                    payload=payload, expected_version=expected_version, approved_at=moment)
    return {**result, "changed": True}


def declare_handoff(store: Any, plan_id: str, *, claim: str, declared_at: str | None = None,
                    channel: str | None = None, claimed_recipient: str | None = None,
                    target_version: str | None = None, expected_version: int) -> dict[str, Any]:
    """Record a user's own statement about the material. Never fills the external receipt.

    `target_version` is what a later imported result must match (CL-05). It is stated by the user at handoff
    time, not inferred from the result, or the result would be checking itself.
    """
    if claim == EXTERNAL_ONLY_CLAIM:
        raise ValueError("REPAIR_CLAIM_EXTERNAL_ONLY externalReceipt is filled by an imported external "
                         "document, not by a user statement; declare copiedByUser or userDeclaredHandoff")
    if claim not in HANDOFF_CLAIMS:
        raise ValueError(f"REPAIR_CLAIM_UNKNOWN {claim!r} is outside the declarable vocabulary "
                         f"{list(HANDOFF_CLAIMS)}")
    row = store.read_action_plan(plan_id)
    if row is None:
        raise ValueError(f"REPAIR_RECORD_NOT_FOUND plan {plan_id}")
    payload = _read_payload(row)
    if row["status"] in TERMINAL_STATUSES:
        raise ValueError(f"REPAIR_RECORD_TERMINAL plan {plan_id} is {row['status']}; a closed record is "
                         "history, and appending a claim to it would rewrite what was closed")
    moment = declared_at or _now_string()
    version = str(target_version).strip() if target_version is not None else ""
    desired: dict[str, Any] = {"declared": True, "declaredAt": moment, "channel": channel,
                               "targetVersion": version or None}
    if claim == "userDeclaredHandoff":
        desired["claimedRecipient"] = claimed_recipient
    handoff_record = dict(payload.get("handoffRecord") or {})
    current = handoff_record.get(claim) or {}
    # A retry is the same statement, not a new one: the first declaration time is the fact, so a second
    # invocation with the same channel/recipient/version does not bump the version or rewrite the timestamp.
    if current.get("declared") is True and current.get("channel") == channel and (
            current.get("targetVersion") or None) == (version or None) and (
            claim != "userDeclaredHandoff" or current.get("claimedRecipient") == claimed_recipient):
        return {**row, "changed": False}
    handoff_record[claim] = desired
    payload["handoffRecord"] = handoff_record
    payload["history"] = list(payload.get("history") or []) + [
        {"at": moment, "event": "HANDOFF_DECLARED", "claim": claim}]
    result = _write(store, plan_id=plan_id, project_id=str(row["projectId"]), status=row["status"],
                    payload=payload, expected_version=expected_version,
                    approved_at=row.get("approvedAt"))
    return {**result, "changed": True}


def record_outcome(store: Any, plan_id: str, *, outcome: str, evidence_level: str,
                   evidence_refs: list[str], expected_version: int,
                   recorded_at: str | None = None, detail: str | None = None) -> dict[str, Any]:
    """APPROVED -> SUCCEEDED / FAILED / BLOCKED, from evidence strong enough for the claim."""
    row = store.read_action_plan(plan_id)
    if row is None:
        raise ValueError(f"REPAIR_RECORD_NOT_FOUND plan {plan_id}")
    payload = _read_payload(row)
    if outcome not in OUTCOMES:
        raise ValueError(f"REPAIR_OUTCOME_UNKNOWN {outcome!r} is outside {list(OUTCOMES)}")
    if evidence_level not in EVIDENCE_LEVELS:
        raise ValueError(f"REPAIR_EVIDENCE_LEVEL_UNKNOWN {evidence_level!r} is outside "
                         f"{list(EVIDENCE_LEVELS)}")
    references = [str(ref).strip() for ref in (evidence_refs or []) if str(ref).strip()]
    if outcome == "SUCCEEDED":
        if evidence_level not in CLOSING_EVIDENCE_LEVELS:
            raise ValueError(f"REPAIR_OUTCOME_UNEVIDENCED a {evidence_level!r} claim cannot mark a problem "
                             "solved; a self-report stays unverified until a re-runnable or independent "
                             "check confirms it")
        if not references:
            raise ValueError("REPAIR_OUTCOME_UNEVIDENCED SUCCEEDED needs at least one evidence reference "
                             "that can be read back")
    if row["status"] == outcome:
        existing = payload.get("outcome") or {}
        if (existing.get("evidenceLevel") == evidence_level
                and list(existing.get("evidenceRefs") or []) == references
                and existing.get("detail") == detail):
            return {**row, "changed": False}
        raise ValueError(f"REPAIR_RECORD_TERMINAL plan {plan_id} already closed as {row['status']}; a "
                         "different verdict needs a new record, not a rewrite of a closed one")
    if row["status"] in TERMINAL_STATUSES:
        raise ValueError(f"REPAIR_RECORD_TERMINAL plan {plan_id} is {row['status']}; a closed record takes "
                         "no further outcome")
    if row["status"] != "APPROVED":
        raise ValueError(f"REPAIR_RECORD_NOT_APPROVED plan {plan_id} is {row['status']}; an outcome is "
                         "written against an approved repair, not against a draft")
    moment = recorded_at or _now_string()
    desired = {"status": outcome, "evidenceLevel": evidence_level, "evidenceRefs": references,
               "recordedAt": moment, "detail": detail}
    payload["outcome"] = desired
    payload["history"] = list(payload.get("history") or []) + [
        {"at": moment, "event": "OUTCOME_RECORDED", "outcome": outcome, "evidenceLevel": evidence_level}]
    result = _write(store, plan_id=plan_id, project_id=str(row["projectId"]), status=outcome,
                    payload=payload, expected_version=expected_version,
                    approved_at=row.get("approvedAt"))
    return {**result, "changed": True}


def _latest_handoff(payload: Mapping[str, Any]) -> dict[str, Any] | None:
    """The most recent handoff declaration -- the one an imported result has to answer."""
    handoff_record = payload.get("handoffRecord") or {}
    declared = [handoff_record.get(name) or {} for name in HANDOFF_CLAIMS
                if (handoff_record.get(name) or {}).get("declared") is True]
    if not declared:
        return None

    def order(claim: Mapping[str, Any]) -> float:
        moment = verification.parse_instant(claim.get("declaredAt"))
        return moment.timestamp() if moment else float("-inf")

    return max(declared, key=order)


def import_external_result(store: Any, plan_id: str, result: Mapping[str, Any], *,
                           accepted_at: str | None = None,
                           expected_version: int) -> dict[str, Any]:
    """Store an external result document as a claim awaiting WORK-LAB's own re-read.

    The only writer of `handoffRecord.externalReceipt`: the import is the moment another system's document
    entered this record, and the receipt records that fact without adopting what the document claims.
    """
    row = store.read_action_plan(plan_id)
    if row is None:
        raise ValueError(f"REPAIR_RECORD_NOT_FOUND plan {plan_id}")
    payload = _read_payload(row)
    if row["status"] in TERMINAL_STATUSES:
        raise ValueError(f"EXTERNAL_RESULT_RECORD_CLOSED plan {plan_id} is {row['status']}; a result that "
                         "arrives after the record closed is late, not a re-opening")
    if row["status"] != "APPROVED":
        raise ValueError(f"EXTERNAL_RESULT_RECORD_NOT_APPROVED plan {plan_id} is {row['status']}; an "
                         "imported result answers an approved repair, not a draft")
    handoff = _latest_handoff(payload)
    existing = [str(item.get("resultId") or "") for item in payload.get("externalResults") or []]
    problems = verification.validate_external_result(
        result, pack_id=plan_id, project_id=str(row["projectId"]), handoff=handoff,
        existing_result_ids=existing)
    if problems:
        raise ValueError("EXTERNAL_RESULT_REFUSED " + "; ".join(problems))
    moment = accepted_at or _now_string()
    references = [str(ref).strip() for ref in (result.get("evidenceRefs") or []) if str(ref).strip()]
    imported = {
        "resultId": str(result.get("resultId")).strip(),
        "producer": str(result.get("producer")).strip(),
        "claimedOutcome": str(result.get("claimedOutcome")).strip().upper(),
        "evidenceRefs": references,
        # The document's own references make it a self-report with material, never independent evidence.
        "evidenceLevel": "self" if references else "none",
        "producedAt": str(result.get("producedAt")).strip(),
        "targetVersion": str(result.get("targetVersion")).strip(),
        "importedAt": moment,
        "verification": None,
    }
    payload["externalResults"] = list(payload.get("externalResults") or []) + [imported]
    handoff_record = dict(payload.get("handoffRecord") or {})
    handoff_record["externalReceipt"] = {"received": True, "receivedAt": moment,
                                         "externalId": imported["resultId"],
                                         "source": imported["producer"]}
    payload["handoffRecord"] = handoff_record
    payload["pendingVerification"] = {"resultId": imported["resultId"], "importedAt": moment}
    payload["history"] = list(payload.get("history") or []) + [
        {"at": moment, "event": "EXTERNAL_RESULT_IMPORTED", "resultId": imported["resultId"],
         "claimedOutcome": imported["claimedOutcome"]}]
    written = _write(store, plan_id=plan_id, project_id=str(row["projectId"]), status=row["status"],
                     payload=payload, expected_version=expected_version,
                     approved_at=row.get("approvedAt"))
    return {**written, "changed": True, "importedResult": imported}


def _same_verdict(stored: Mapping[str, Any], verdict: Mapping[str, Any]) -> bool:
    return all(stored.get(field) == verdict.get(field) for field in
               ("outcome", "verifiedAt", "packId", "fingerprintsPresent", "fingerprintsAbsent",
                "sourcesUnanswered"))


def record_verification(store: Any, plan_id: str, verdict: Mapping[str, Any], *,
                        expected_version: int) -> dict[str, Any]:
    """Turn one already-computed re-read verdict into the record's answer.

    RESOLVED closes only when the imported result also claimed SUCCEEDED. A failing claim is never rewritten
    into a success, and an UNVERIFIABLE verdict closes nothing -- it stays pending so a later read can answer.
    """
    row = store.read_action_plan(plan_id)
    if row is None:
        raise ValueError(f"REPAIR_RECORD_NOT_FOUND plan {plan_id}")
    payload = _read_payload(row)
    verifications = list(payload.get("verifications") or [])
    if row["status"] in TERMINAL_STATUSES:
        if verifications and _same_verdict(verifications[-1], verdict):
            return {**row, "changed": False}
        raise ValueError(f"REPAIR_RECORD_TERMINAL plan {plan_id} is {row['status']}; a closed record takes "
                         "no further verification")
    if row["status"] != "APPROVED":
        raise ValueError(f"REPAIR_RECORD_NOT_APPROVED plan {plan_id} is {row['status']}; verification "
                         "answers an approved repair")
    problems = verification.validate_repair_verification(verdict)
    if problems:
        raise ValueError("REPAIR_VERIFICATION_INVALID " + "; ".join(problems))
    pack = payload.get("pack") or {}
    bound = {str(fp) for fp in (pack.get("binds") or {}).get("issueFingerprints") or []}
    if str(verdict.get("packId")) != plan_id:
        raise ValueError(f"REPAIR_VERIFICATION_WRONG_PACK verdict is for {verdict.get('packId')!r}, "
                         f"record is {plan_id!r}")
    checked = {str(fp) for fp in (verdict.get("fingerprintsPresent") or [])
               + (verdict.get("fingerprintsAbsent") or [])}
    if int(verdict.get("boundFingerprintCount") or 0) != len(bound) or (
            verdict.get("readPerformed") is not False and checked != bound):
        raise ValueError("REPAIR_VERIFICATION_WRONG_PACK the verdict re-checked a different fingerprint "
                         f"set than this pack bound ({len(checked)} checked, {len(bound)} bound)")
    pending = payload.get("pendingVerification") or {}
    result_id = str(pending.get("resultId") or "")
    imported = next((item for item in payload.get("externalResults") or []
                     if item.get("resultId") == result_id), None)
    if not result_id or imported is None:
        raise ValueError(f"REPAIR_VERIFICATION_NOT_PENDING plan {plan_id} has no imported result waiting "
                         "for a verdict; there is no claim for this re-read to answer")
    verification_id = f"v{len(verifications) + 1}"
    stored = {key: verdict.get(key) for key in (
        "schemaVersion", "packId", "verifiedAt", "outcome", "evidenceLevel", "boundFingerprintCount",
        "fingerprintsPresent", "fingerprintsAbsent", "sourcesUnderTest", "sourcesUnanswered", "reason",
        "readPerformed", "receiptRecorded", "receiptAcceptedAsVerification", "inferencePerformed",
        "contentIncluded")}
    stored["verificationId"] = verification_id
    stored["answeredResultId"] = result_id
    verifications.append(stored)
    payload["verifications"] = verifications
    imported["verification"] = {"verificationId": verification_id, "outcome": stored["outcome"]}

    claimed = str(imported.get("claimedOutcome") or "")
    outcome = str(stored["outcome"])
    moment = str(verdict.get("verifiedAt") or _now_string())
    evidence_ref = f"action_plan:{plan_id}#verification:{verification_id}"
    status = row["status"]
    outcome_row = payload.get("outcome")
    pending_after: dict[str, Any] | None = payload.get("pendingVerification")
    if outcome == "RESOLVED" and claimed == "SUCCEEDED":
        status = "SUCCEEDED"
        outcome_row = {"status": status, "evidenceLevel": "independent", "evidenceRefs": [evidence_ref],
                       "recordedAt": moment, "detail": stored["reason"]}
        pending_after = None
    elif outcome == "RESOLVED":
        status = "FAILED"
        outcome_row = {"status": status, "evidenceLevel": "independent", "evidenceRefs": [evidence_ref],
                       "recordedAt": moment,
                       "detail": f"imported result {result_id} claimed {claimed}; the re-read finds the "
                                 "bound fingerprints gone, and a failed claim is not rewritten into a success"}
        pending_after = None
    elif outcome == "UNRESOLVED":
        status = "FAILED"
        outcome_row = {"status": status, "evidenceLevel": "independent", "evidenceRefs": [evidence_ref],
                       "recordedAt": moment,
                       "detail": f"the re-read still produces the bound fingerprints; imported result "
                                 f"{result_id} claimed {claimed}"}
        pending_after = None
    payload["outcome"] = outcome_row
    payload["pendingVerification"] = pending_after
    payload["history"] = list(payload.get("history") or []) + [
        {"at": moment, "event": "VERIFICATION_RECORDED", "verificationId": verification_id,
         "outcome": outcome, "resultingStatus": status}]
    written = _write(store, plan_id=plan_id, project_id=str(row["projectId"]), status=status,
                     payload=payload, expected_version=expected_version,
                     approved_at=row.get("approvedAt"))
    return {**written, "changed": True, "verification": stored}


def verify_record(store: Any, plan_id: str, *, verified_at: str | None = None,
                  expected_version: int) -> dict[str, Any]:
    """Re-read the issue projection from the store and record what it says about this pack."""
    row = store.read_action_plan(plan_id)
    if row is None:
        raise ValueError(f"REPAIR_RECORD_NOT_FOUND plan {plan_id}")
    payload = _read_payload(row)
    moment = verified_at or _now_string()
    pending = payload.get("pendingVerification") or {}
    imported = next((item for item in payload.get("externalResults") or []
                     if item.get("resultId") == str(pending.get("resultId") or "")), None)
    issues_now, summary_now, absent_reason = issue_projection.load_issues(store, generated_at=moment)
    verdict = verification.verify_repair_record(
        pack=payload.get("pack") or {}, issues_now=issues_now, summary_now=summary_now,
        absent_reason=absent_reason, verified_at=moment, receipt=imported)
    return record_verification(store, plan_id, verdict, expected_version=expected_version)


def render_verification_line(verdict: Mapping[str, Any]) -> str:
    return (f"REPAIR_VERIFICATION pack={verdict.get('packId')} outcome={verdict.get('outcome')} "
            f"level={verdict.get('evidenceLevel')} "
            f"present={len(verdict.get('fingerprintsPresent') or [])} "
            f"absent={len(verdict.get('fingerprintsAbsent') or [])} "
            f"unanswered={len(verdict.get('sourcesUnanswered') or [])} reason={verdict.get('reason')}")


def render_record_line(record: Mapping[str, Any]) -> str:
    """One line a CLI or a log can carry; the fields the lifecycle actually has."""
    payload = record.get("payload") if isinstance(record.get("payload"), dict) else {}
    approval = payload.get("approval") or {}
    outcome = payload.get("outcome") or {}
    handoff_record = payload.get("handoffRecord") or {}
    copied = (handoff_record.get("copiedByUser") or {}).get("declared")
    declared = (handoff_record.get("userDeclaredHandoff") or {}).get("declared")
    receipt = (handoff_record.get("externalReceipt") or {}).get("received")
    changed = record.get("changed")
    return (f"REPAIR_RECORD plan={record.get('planId')} status={record.get('status')} "
            f"version={record.get('version')} grant={approval.get('authorizationRef')} "
            f"copied={copied} declared={declared} receipt={receipt} "
            f"outcome={outcome.get('status')} evidence={outcome.get('evidenceLevel')}"
            + ("" if changed is None else f" changed={changed}"))


def main(argv: list[str] | None = None) -> int:
    """CLI over one canonical store. The store is never created here: a typo'd path must not read as empty."""
    import argparse

    root = Path(__file__).resolve().parents[3]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("record", "approve", "declare", "outcome", "import-result",
                                            "verify", "show", "list"))
    parser.add_argument("--runtime-root", type=Path,
                        default=root / ".project-local" / "runs" / "issues-live-readback")
    parser.add_argument("--plan-id")
    parser.add_argument("--pack-file", type=Path)
    parser.add_argument("--grant-ref")
    parser.add_argument("--grants", type=Path,
                        help="defaults to <runtime-root>/control-trusted-grants.json; no file means no grant")
    parser.add_argument("--claim", choices=HANDOFF_CLAIMS)
    parser.add_argument("--channel")
    parser.add_argument("--claimed-recipient")
    parser.add_argument("--target-version")
    parser.add_argument("--result-file", type=Path)
    parser.add_argument("--outcome", choices=OUTCOMES)
    parser.add_argument("--evidence-level", choices=EVIDENCE_LEVELS)
    parser.add_argument("--evidence-ref", action="append", default=[])
    parser.add_argument("--detail")
    parser.add_argument("--expected-version", type=int)
    parser.add_argument("--project-id")
    args = parser.parse_args(argv)

    db = args.runtime_root / "canonical.sqlite"
    if not db.is_file():
        print(f"REPAIR_STATE_NO_STORE {db} -- refusing to create a store and report an empty lifecycle")
        return 3
    from canonical_store import CanonicalStore
    store = CanonicalStore(db)
    try:
        if args.command == "record":
            if not args.pack_file:
                parser.error("record requires --pack-file")
            pack = json.loads(args.pack_file.read_text(encoding="utf-8"))
            result = record_pack(store, pack)
        elif args.command == "approve":
            if not (args.plan_id and args.grant_ref and args.expected_version is not None):
                parser.error("approve requires --plan-id, --grant-ref and --expected-version")
            grants_path = args.grants or (args.runtime_root / "control-trusted-grants.json")
            grants, grant_state = load_grants(grants_path)
            print(f"GRANT_RECORD path={grant_state.get('path')} readable={grant_state.get('readable')} "
                  f"grants={grant_state.get('grants')} expired={grant_state.get('expired')} "
                  f"malformed={grant_state.get('malformed')}")
            result = approve_pack(store, args.plan_id, authorization_ref=args.grant_ref, grants=grants,
                                  expected_version=args.expected_version, approved_at=None)
        elif args.command == "declare":
            if not (args.plan_id and args.claim and args.expected_version is not None):
                parser.error("declare requires --plan-id, --claim and --expected-version")
            result = declare_handoff(store, args.plan_id, claim=args.claim, channel=args.channel,
                                     claimed_recipient=args.claimed_recipient,
                                     target_version=args.target_version,
                                     expected_version=args.expected_version)
        elif args.command == "import-result":
            if not (args.plan_id and args.result_file and args.expected_version is not None):
                parser.error("import-result requires --plan-id, --result-file and --expected-version")
            document = json.loads(args.result_file.read_text(encoding="utf-8"))
            result = import_external_result(store, args.plan_id, document,
                                            expected_version=args.expected_version)
        elif args.command == "verify":
            if not (args.plan_id and args.expected_version is not None):
                parser.error("verify requires --plan-id and --expected-version")
            result = verify_record(store, args.plan_id, expected_version=args.expected_version)
            verdict = result.get("verification") or {}
            if verdict:
                print(render_verification_line(verdict))
            print(render_record_line({**result, "changed": None}))
            return 0
        elif args.command == "outcome":
            if not (args.plan_id and args.outcome and args.evidence_level
                    and args.expected_version is not None):
                parser.error("outcome requires --plan-id, --outcome, --evidence-level and "
                             "--expected-version")
            result = record_outcome(store, args.plan_id, outcome=args.outcome,
                                    evidence_level=args.evidence_level,
                                    evidence_refs=args.evidence_ref,
                                    expected_version=args.expected_version, detail=args.detail)
        elif args.command == "show":
            if not args.plan_id:
                parser.error("show requires --plan-id")
            record = read_record(store, args.plan_id)
            if record is None:
                print(f"REPAIR_RECORD_ABSENT plan {args.plan_id}")
                return 1
            print(render_record_line(record))
            print(json.dumps(record, ensure_ascii=False, indent=2))
            return 0
        else:
            records = list_records(store, args.project_id)
            for record in records:
                print(render_record_line(record))
            print(f"REPAIR_RECORDS count={len(records)}")
            return 0
    except (ValueError, OSError) as error:
        print(f"REPAIR_STATE_REFUSED {error}")
        return 1
    finally:
        store.close()
    print(render_record_line(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
