"""CL-05: did the repair actually work? Re-read the store and answer, without believing the fixer.

`05_建议` puts 结果导入 → 独立验证 after the external repair, and the audit's closed-loop row 5 still says
「问题生命周期尚未接入」. This module is the independent half of that row:

* **An imported result is a claim, never an outcome.** `validate_external_result` checks that the document
  names the pack it answers, the target project, the target version the handoff was declared against, and a
  result id that has not been imported before. A result produced before the handoff existed is stale; a
  result for a closed record is late. None of these can become a decision -- the import stores them as
  `self` (or `none`, when it carries no reference) evidence in "待核验".

* **Verification reads the store, not the report.** `verify_repair_record` takes the issues projection
  WORK-LAB just re-read and asks one factual question: are the fingerprints this pack bound still being
  produced? The fixer's own claim is recorded in `receiptRecorded` and can never be upgraded into evidence
  (`receiptAcceptedAsVerification` is a const false).

* **UNVERIFIABLE is not RESOLVED.** If any source that produced the bound issues did not answer this round,
  or the read was truncated, a missing fingerprint means "we did not read it", never "it is fixed". The
  field that says which is named.

* **Evidence strength comes from who ran the check, not from how confident the text reads.** `evidenceLevel`
  reuses `services/task-governance/completion_authority.py`'s own vocabulary
  (none/self/reproducible/independent) rather than minting a fifth scale; a verdict from a re-read here is
  `independent`, and a verdict the store could not answer is `none` -- never `self`, because the fixer's
  words are not what this is measuring.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping

import issue_projection

VERIFICATION_SCHEMA_VERSION = "worklab/repair-verification/v1"
EXTERNAL_RESULT_SCHEMA_VERSION = "worklab/external-repair-result/v1"

OUTCOMES = ("RESOLVED", "UNRESOLVED", "UNVERIFIABLE")
# Same four values as completion_authority.EvidenceLevel, pinned by a guard test against that module so a
# rename there cannot quietly turn this into a parallel scale.
EVIDENCE_LEVELS = ("none", "self", "reproducible", "independent")
ANSWERED_SOURCE_STATES = ("read",)
CLAIMED_OUTCOMES = ("SUCCEEDED", "FAILED", "BLOCKED")
EXTERNAL_RESULT_TEXT_FIELDS = ("resultId", "packId", "projectId", "targetVersion", "producedAt",
                               "producer", "claimedOutcome")


def parse_instant(text: Any) -> datetime | None:
    """Parse an ISO instant; None means "not a time this module can compare"."""
    if not isinstance(text, str) or not text.strip():
        return None
    try:
        moment = datetime.fromisoformat(text.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    return moment if moment.tzinfo else moment.replace(tzinfo=timezone.utc)


def validate_external_result(result: Mapping[str, Any], *, pack_id: str, project_id: str,
                             handoff: Mapping[str, Any] | None,
                             existing_result_ids: list[str]) -> list[str]:
    """Problems with one imported result document. Empty means it binds to THIS record.

    Binding is checked against facts the record already holds, not against fields the document repeats:
    the pack id, the project id, the target version the handoff declaration named, and the handoff time.
    """
    if not isinstance(result, Mapping):
        return ["EXTERNAL_RESULT_INCOMPLETE document is not an object"]
    problems: list[str] = []
    if result.get("schemaVersion") != EXTERNAL_RESULT_SCHEMA_VERSION:
        problems.append(f"EXTERNAL_RESULT_SCHEMA schemaVersion must be {EXTERNAL_RESULT_SCHEMA_VERSION!r}")
    for field in EXTERNAL_RESULT_TEXT_FIELDS:
        if not str(result.get(field) or "").strip():
            problems.append(f"EXTERNAL_RESULT_INCOMPLETE {field} is required")
    references = result.get("evidenceRefs")
    if not isinstance(references, list) or any(not isinstance(ref, str) for ref in references):
        problems.append("EXTERNAL_RESULT_INCOMPLETE evidenceRefs must be a list of strings "
                        "(an empty list is a claim with no references, not a malformed document)")
    claimed = str(result.get("claimedOutcome") or "").strip().upper()
    if claimed and claimed not in CLAIMED_OUTCOMES:
        problems.append(f"EXTERNAL_RESULT_OUTCOME_UNKNOWN {claimed!r} is outside {list(CLAIMED_OUTCOMES)}")

    named_pack = str(result.get("packId") or "").strip()
    if named_pack and named_pack != str(pack_id):
        problems.append(f"EXTERNAL_RESULT_WRONG_PACK result names {named_pack!r}, this record is {pack_id!r}")
    named_project = str(result.get("projectId") or "").strip()
    if named_project and named_project != str(project_id):
        problems.append(f"EXTERNAL_RESULT_WRONG_PROJECT result names {named_project!r}, this record is "
                        f"{project_id!r}")

    if handoff is None:
        problems.append("EXTERNAL_RESULT_HANDOFF_MISSING no handoff has been declared; a result cannot "
                        "bind to a handoff that never happened")
    else:
        declared_version = str(handoff.get("targetVersion") or "").strip()
        named_version = str(result.get("targetVersion") or "").strip()
        if not declared_version:
            problems.append("EXTERNAL_RESULT_HANDOFF_UNBOUND the declared handoff names no target version; "
                            "re-declare it against the version this result must match")
        elif named_version and named_version != declared_version:
            problems.append(f"EXTERNAL_RESULT_WRONG_VERSION result names {named_version!r}, the handoff was "
                            f"declared against {declared_version!r}")
        produced = parse_instant(result.get("producedAt"))
        if produced is None and str(result.get("producedAt") or "").strip():
            problems.append("EXTERNAL_RESULT_PRODUCED_AT_INVALID producedAt is not an ISO instant that can "
                            "be compared with the handoff")
        declared_at = parse_instant(handoff.get("declaredAt"))
        if produced is not None and declared_at is not None and produced < declared_at:
            problems.append(f"EXTERNAL_RESULT_STALE result was produced at {produced.isoformat()} before "
                            f"the handoff was declared at {declared_at.isoformat()}; a stale result answers "
                            "an earlier handoff")

    result_id = str(result.get("resultId") or "").strip()
    if result_id and result_id in set(existing_result_ids):
        problems.append(f"EXTERNAL_RESULT_DUPLICATE result {result_id!r} was already imported; a second "
                        "submission is not a second result")
    return problems


def verify_repair_record(*, pack: Mapping[str, Any], issues_now: list[dict[str, Any]] | None,
                         summary_now: Mapping[str, Any] | None, absent_reason: str | None,
                         verified_at: str, receipt: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """One verdict row for one pack, derived only from what the store says right now.

    `pack` must be a repair pack (its `binds.issueFingerprints` / `binds.evidenceRefs` are the claim under
    test). Nothing here reads the receipt's outcome field as evidence; it is recorded so a later human can
    see what was claimed against what was observed.
    """
    binds = pack.get("binds") or {}
    bound = [str(fp) for fp in (binds.get("issueFingerprints") or [])]
    sources = sorted({issue_projection.source_of_evidence_ref(str(ref))
                      for ref in (binds.get("evidenceRefs") or []) if str(ref).strip()})

    if issues_now is None or summary_now is None:
        return {
            "schemaVersion": VERIFICATION_SCHEMA_VERSION,
            "packId": pack.get("packId"),
            "verifiedAt": verified_at,
            "outcome": "UNVERIFIABLE",
            "evidenceLevel": "none",
            "boundFingerprintCount": len(bound),
            "fingerprintsPresent": [],
            "fingerprintsAbsent": [],
            "sourcesUnderTest": sources,
            "sourcesUnanswered": ["<projection>"],
            "reason": f"issue-projection-absent:{absent_reason or 'unknown'}",
            "readPerformed": False,
            "receiptRecorded": bool(receipt),
            "receiptAcceptedAsVerification": False,
            "inferencePerformed": False,
            "contentIncluded": False,
        }

    now = {str(row.get("fingerprint") or "") for row in issues_now}
    present = [fp for fp in bound if fp in now]
    absent = [fp for fp in bound if fp not in now]

    states = {str(item.get("source")): str(item.get("state"))
              for item in (summary_now.get("sources") or []) if isinstance(item, Mapping)}
    unanswered = sorted(name for name in sources if states.get(name) not in ANSWERED_SOURCE_STATES)
    scan_truncated = summary_now.get("scanTruncated")
    truncated = bool(summary_now.get("truncated")) or (
        isinstance(scan_truncated, Mapping) and any(bool(value) for value in scan_truncated.values()))

    if unanswered:
        outcome, level, reason = ("UNVERIFIABLE", "none",
                                  "a source that produced these issues did not answer this round; "
                                  "an unconfirmed fault is not a confirmed fix")
    elif present:
        outcome, level, reason = ("UNRESOLVED", "independent",
                                  "the condition is still being produced by the store")
    elif truncated:
        outcome, level, reason = ("UNVERIFIABLE", "none",
                                  "the issue projection was truncated this round; a fingerprint missing "
                                  "from a capped read is not a fingerprint that stopped")
    elif not bound:
        outcome, level, reason = ("UNVERIFIABLE", "none", "the pack bound no fingerprint to re-check")
    else:
        outcome, level, reason = ("RESOLVED", "independent",
                                  "every bound fingerprint is absent from a re-read whose sources all answered")

    return {
        "schemaVersion": VERIFICATION_SCHEMA_VERSION,
        "packId": pack.get("packId"),
        "verifiedAt": verified_at,
        "outcome": outcome,
        "evidenceLevel": level,
        "boundFingerprintCount": len(bound),
        "fingerprintsPresent": present,
        "fingerprintsAbsent": absent,
        "sourcesUnderTest": sources,
        "sourcesUnanswered": unanswered,
        "reason": reason,
        "readPerformed": True,
        "receiptRecorded": bool(receipt),
        "receiptAcceptedAsVerification": False,
        "inferencePerformed": False,
        "contentIncluded": False,
    }


def validate_repair_verification(row: Mapping[str, Any]) -> list[str]:
    """Coherence checks on one verdict. Empty means clean."""
    problems: list[str] = []
    if row.get("schemaVersion") != VERIFICATION_SCHEMA_VERSION:
        problems.append("schemaVersion is not worklab/repair-verification/v1")
    if row.get("outcome") not in OUTCOMES:
        problems.append(f"outcome {row.get('outcome')!r} is outside {OUTCOMES}")
    if row.get("evidenceLevel") not in EVIDENCE_LEVELS:
        problems.append(f"evidenceLevel {row.get('evidenceLevel')!r} is outside the authority's scale")
    present = row.get("fingerprintsPresent") or []
    absent = row.get("fingerprintsAbsent") or []
    if row.get("readPerformed") is not True and row.get("readPerformed") is not False:
        problems.append("readPerformed must say whether the store was re-read at all")
    elif row.get("readPerformed") is False:
        if present or absent:
            problems.append("a verdict that performed no read cannot name fingerprints")
        if row.get("outcome") != "UNVERIFIABLE":
            problems.append("a verdict that performed no read cannot claim a resolved or unresolved outcome")
    elif int(row.get("boundFingerprintCount") or 0) != len(present) + len(absent):
        problems.append("boundFingerprintCount disagrees with present + absent")
    if row.get("outcome") == "RESOLVED" and present:
        problems.append("RESOLVED cannot carry a fingerprint that is still present")
    if row.get("outcome") == "RESOLVED" and (row.get("sourcesUnanswered") or []):
        problems.append("RESOLVED with an unanswered source: not reading the fault is not fixing it")
    if row.get("outcome") == "UNVERIFIABLE" and row.get("evidenceLevel") == "independent":
        problems.append("an unverifiable verdict may not claim independent strength")
    if row.get("outcome") == "UNRESOLVED" and not present:
        problems.append("UNRESOLVED must name what is still there")
    if row.get("receiptAcceptedAsVerification") is not False:
        problems.append("no receipt may be accepted as its own verification")
    for forbidden in ("content", "body", "payload", "text"):
        if forbidden in row:
            problems.append(f"a verdict must not carry {forbidden!r}")
    return problems
