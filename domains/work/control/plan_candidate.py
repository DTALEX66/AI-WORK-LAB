"""Super-entry planning handback contract (AG-16).

The super-entry architecture (`WORK-LAB_SUPER_ENTRY_ARCHITECTURE_RECONCILIATION`,
and the Context handoff / Planning / Audit rows of the layer table) is:

    ContextEnvelope -> PlanningCandidate -> check / authorize
                    -> user-selected executor -> Receipt

Two links already exist in this repository and are REUSED, not duplicated:

* the context side — ``context_control_plane`` / ``context-capsule.schema.json``
  (canonical stable prefix, cache truth, digest);
* the message + authorization side — ``handoff_envelope.py`` v2, whose
  ``check_authorization`` already refuses to let payload text confer a grant.

The missing link is the middle one: what a **planning end** (a web GPT, a cloud
client, a second model) hands BACK. That is what this module defines.

Hard rules, each fail-closed
---------------------------
1. **Planning output never authorizes execution.** A candidate carries no
   authority of its own. It may only *reference* a grant id that must resolve in
   a trusted local record (the same rule ``handoff_envelope.check_authorization``
   applies to envelopes). Any self-claim in the candidate text
   (``approved`` / ``scope`` / ``permission_scope``) is ignored and reported as
   ignored — never honoured.
2. **A candidate with unresolved blocking items cannot be accepted.** It comes
   back as NEEDS_INPUT naming exactly what is missing, so the planning end
   answers instead of the executor guessing.
3. **Planning is not execution.** Even a fully authorized candidate returns
   ``execution_status = NOT_EXECUTED``. This module never runs anything, never
   writes, never calls the network, and never touches a model.
4. **Deduplication is content-addressed.** Two returns that normalize to the
   same content share one digest, so a re-delivered plan cannot be applied twice
   under a fresh id.
5. **Capability and scope are checked against the real registry.** A candidate
   targeting a capability no registered executor advertises is refused with the
   capability named, rather than discovered at execution time.

Pure and deterministic: no network, no filesystem, no paid call, no native
private store, no credentials.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any, Iterable, Mapping

SCHEMA_VERSION = "workflow/planning-candidate/v1"

# Return states. Deliberately distinct so no caller can collapse
# "authorized" into "executed" — the single most dangerous conflation here.
R_DRAFT_INVALID = "DRAFT_INVALID"
R_NEEDS_INPUT = "NEEDS_INPUT"
R_AWAITING_AUTHORIZATION = "AWAITING_AUTHORIZATION"
R_AUTHORIZED = "AUTHORIZED_NOT_EXECUTED"
R_REFUSED_CAPABILITY = "REFUSED_CAPABILITY_UNAVAILABLE"
R_DUPLICATE = "DUPLICATE_CONTENT"

EXECUTION_STATUS = "NOT_EXECUTED"

# Fields a planning end might emit to try to authorize itself. Never honoured.
SELF_CONFER_FIELDS = ("approved", "authorized", "scope", "permission_scope",
                      "permission", "granted")

# A returned plan must state these; absence is a refusal, not a guess.
REQUIRED_DRAFT_FIELDS = (
    "planningSoftware",   # which client/model produced the plan
    "workUnitId",
    "taskRevision",
    "baseline",           # code/workspace baseline the plan was reasoned against
    "contextRef",         # context capsule id the plan was given
    "contextDigest",      # digest of that exact context
    "changes",            # what the plan proposes to change (scope)
    "verification",       # how the result would be verified
)


def stable_digest(payload: Mapping[str, Any]) -> str:
    """Deterministic content digest (same convention as handoff_envelope)."""
    blob = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _normalize_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value] if value.strip() else []
    if isinstance(value, (list, tuple, set)):
        return [str(v) for v in value if str(v).strip()]
    return [str(value)]


def candidate_content(candidate: Mapping[str, Any]) -> dict[str, Any]:
    """The content that defines a candidate's identity.

    Excludes bookkeeping (id, messageId, createdAt, correlationId) so the same
    plan re-sent under a new id still dedupes, and excludes every self-confer
    field so a candidate cannot change its own authorization standing by editing
    text.
    """
    return {
        "workUnitId": candidate.get("workUnitId"),
        "taskRevision": candidate.get("taskRevision"),
        "baseline": candidate.get("baseline"),
        "contextDigest": candidate.get("contextDigest"),
        "planningSoftware": candidate.get("planningSoftware"),
        "assumptions": _normalize_list(candidate.get("assumptions")),
        "changes": candidate.get("changes") or [],
        "verification": candidate.get("verification") or [],
        "references": _normalize_list(candidate.get("references")),
        "unresolved": candidate.get("unresolved") or [],
        "openQuestions": _normalize_list(candidate.get("openQuestions")),
        "targetCapability": candidate.get("targetCapability", ""),
        "authorizationRef": candidate.get("authorizationRef", ""),
    }


def build_candidate(draft: Mapping[str, Any]) -> dict[str, Any]:
    """Normalize a returned plan into a PlanningCandidate. Raises on malformed input.

    Fail-closed: a missing required field raises rather than defaulting, because
    a plan that does not say what it was reasoned against (baseline + context
    digest) cannot be safely evaluated.
    """
    if not isinstance(draft, Mapping):
        raise ValueError("planning candidate must be a mapping")
    missing = [f for f in REQUIRED_DRAFT_FIELDS
               if draft.get(f) in (None, "", [], {})]
    if missing:
        raise ValueError(
            f"planning candidate is missing required field(s): {sorted(missing)}; "
            "refusing to infer them"
        )
    baseline = dict(draft.get("baseline") or {})
    if not (baseline.get("commit") or baseline.get("digest")):
        raise ValueError("baseline requires an exact commit or an immutable digest")
    revision = int(draft.get("taskRevision", 0))
    if revision < 1:
        raise ValueError("taskRevision must be >= 1")

    candidate = {
        "schemaVersion": SCHEMA_VERSION,
        "candidateId": draft.get("candidateId") or "",
        "planningSoftware": draft.get("planningSoftware"),
        "workUnitId": draft.get("workUnitId"),
        "taskRevision": revision,
        "baseline": baseline,
        "contextRef": draft.get("contextRef"),
        "contextDigest": draft.get("contextDigest"),
        "assumptions": _normalize_list(draft.get("assumptions")),
        "changes": list(draft.get("changes") or []),
        "verification": list(draft.get("verification") or []),
        "references": _normalize_list(draft.get("references")),
        "unresolved": list(draft.get("unresolved") or []),
        "openQuestions": _normalize_list(draft.get("openQuestions")),
        "targetCapability": draft.get("targetCapability", ""),
        "authorizationRef": draft.get("authorizationRef", ""),
        # Never carried forward as truth: kept only so the verdict can report
        # that a self-claim was seen and ignored.
        "_self_claims": {
            k: draft.get(k) for k in SELF_CONFER_FIELDS if draft.get(k)
        },
        "createdAt": draft.get("createdAt", ""),
    }
    if not candidate["candidateId"]:
        candidate["candidateId"] = f"pc-{stable_digest(candidate_content(candidate))[:16]}"
    candidate["contentDigest"] = stable_digest(candidate_content(candidate))
    return candidate


def blocking_items(candidate: Mapping[str, Any]) -> list[str]:
    """Unresolved items that must be answered before the plan can be evaluated.

    An entry counts as blocking unless it is explicitly marked non-blocking, so
    the default is safe: silence is not consent.
    """
    blocking: list[str] = []
    for item in candidate.get("unresolved") or []:
        if isinstance(item, Mapping):
            if item.get("blocking") is False:
                continue
            label = item.get("id") or item.get("title") or json.dumps(item, sort_keys=True)
            blocking.append(str(label))
        else:
            blocking.append(str(item))
    return blocking


def check_candidate(
    candidate: Mapping[str, Any],
    *,
    trusted_grants: Mapping[str, str] | None = None,
    capability_registry: Any | None = None,
    required_capability: str | None = None,
    already_seen_digests: Iterable[str] = (),
) -> dict[str, Any]:
    """Evaluate a candidate and return a verdict. NEVER executes anything.

    Order is deliberate: malformed/dedup first (cheapest, and a duplicate must
    not consume a grant), then the blocking-item gate, then capability, and only
    then authorization — so authorization is the LAST thing consulted and can
    never mask a missing answer or an unavailable capability.
    """
    if not isinstance(candidate, Mapping) or candidate.get("schemaVersion") != SCHEMA_VERSION:
        return _verdict(R_DRAFT_INVALID, candidate,
                        reason="not a planning-candidate/v1 document")
    digest = candidate.get("contentDigest") or stable_digest(candidate_content(candidate))
    if digest in set(already_seen_digests):
        return _verdict(R_DUPLICATE, candidate, digest=digest,
                        reason="identical plan content was already returned; "
                               "re-delivery under a new id does not re-apply")

    blocking = blocking_items(candidate)
    if blocking:
        return _verdict(R_NEEDS_INPUT, candidate, digest=digest,
                        reason="the plan leaves blocking items unresolved",
                        blocking=blocking)

    needed = required_capability or candidate.get("targetCapability") or ""
    if needed and capability_registry is not None:
        candidates = []
        if hasattr(capability_registry, "roles_with_capability"):
            try:
                candidates = list(capability_registry.roles_with_capability(needed))
            except Exception:  # noqa: BLE001 - a registry that cannot answer is not a pass
                candidates = []
        if not candidates:
            return _verdict(R_REFUSED_CAPABILITY, candidate, digest=digest,
                            reason=f"no registered executor advertises capability {needed!r}")

    grants = dict(trusted_grants or {})
    ref = candidate.get("authorizationRef") or ""
    self_claims = dict(candidate.get("_self_claims") or {})
    if not ref:
        return _verdict(R_AWAITING_AUTHORIZATION, candidate, digest=digest,
                        reason="no authorizationRef; a plan never authorizes itself",
                        ignored_self_claims=sorted(self_claims))
    scope = grants.get(ref)
    if scope is None:
        return _verdict(R_AWAITING_AUTHORIZATION, candidate, digest=digest,
                        reason=f"grant {ref!r} is not in the trusted local record",
                        ignored_self_claims=sorted(self_claims))
    return _verdict(R_AUTHORIZED, candidate, digest=digest,
                    reason="grant resolved in the trusted local record",
                    scope=scope,
                    ignored_self_claims=sorted(self_claims))


def _verdict(status: str, candidate: Any, *, reason: str,
             digest: str | None = None, scope: str | None = None,
             blocking: list[str] | None = None,
             ignored_self_claims: list[str] | None = None) -> dict[str, Any]:
    # A malformed return (None, a list, a string) must produce a VERDICT, not a
    # crash: a planning end is an untrusted boundary, so "could not read it" has
    # to be a fail-closed answer rather than an exception the caller may swallow.
    fields = candidate if isinstance(candidate, Mapping) else {}
    return {
        "schemaVersion": "workflow/planning-candidate-verdict/v1",
        "status": status,
        "reason": reason,
        "candidateId": fields.get("candidateId"),
        "workItemRevision": fields.get("taskRevision"),
        "contentDigest": digest,
        "authorizedScope": scope,
        "blocking": blocking or [],
        "ignoredSelfClaims": ignored_self_claims or [],
        # The whole point, stated in the payload itself: a verdict is not an
        # execution and never becomes one.
        "executionStatus": EXECUTION_STATUS,
        "executionNote": "the verdict authorizes nothing by itself; a separate "
                         "authorized step chooses the executor and runs it",
    }


class CandidateLedger:
    """Tracks returned plans by content digest so a re-delivery cannot re-apply."""

    def __init__(self) -> None:
        self._seen: dict[str, dict[str, Any]] = {}

    def record(self, candidate: Mapping[str, Any]) -> dict[str, Any]:
        digest = candidate.get("contentDigest")
        if not digest:
            raise ValueError("candidate has no contentDigest; build it first")
        if digest in self._seen:
            return {"status": R_DUPLICATE, "contentDigest": digest,
                    "recorded": False,
                    "firstSeenAs": self._seen[digest].get("candidateId")}
        self._seen[digest] = {
            "candidateId": candidate.get("candidateId"),
            "workUnitId": candidate.get("workUnitId"),
            "taskRevision": candidate.get("taskRevision"),
        }
        return {"status": "RECORDED", "contentDigest": digest, "recorded": True}

    def digests(self) -> list[str]:
        return sorted(self._seen)

    def for_work_unit(self, work_unit_id: str) -> list[dict[str, Any]]:
        return [
            {"contentDigest": digest, **meta}
            for digest, meta in sorted(self._seen.items())
            if meta.get("workUnitId") == work_unit_id
        ]


if __name__ == "__main__":
    demo = build_candidate({
        "planningSoftware": "web-gpt",
        "workUnitId": "WU-1",
        "taskRevision": 1,
        "baseline": {"commit": "0" * 40},
        "contextRef": "capsule-1",
        "contextDigest": "d" * 64,
        "changes": [{"path": "docs/x.md", "op": "edit"}],
        "verification": ["run the gate"],
        "unresolved": [{"id": "Q1", "blocking": True, "title": "which executor?"}],
    })
    print(json.dumps(check_candidate(demo), ensure_ascii=False, indent=2))
