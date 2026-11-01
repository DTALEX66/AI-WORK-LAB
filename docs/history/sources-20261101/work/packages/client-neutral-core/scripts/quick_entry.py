"""Quick Entry: the thin unified entry's request handling, per blueprint §15.2.

Coverage item OD05 in `.project/governance/blueprint-coverage.json` said, verbatim: "SOURCE_GAP: Lite, tray
HUD and Quick Entry have no field or permission spec anywhere in the source ... must not be presented as
implemented modes". This module plus `packages/contracts/schemas/workflow/quick-entry-request.schema.json`
is the field and permission spec, and §15.2's five release conditions are the outcomes below -- each one is
judged from the request, never from a caller's assertion about the world.

It is also the first non-test consumer of `context_bundle.ContextBundle`: an accepted entry assembles the
bundle the executors are meant to receive, so the assembly path is exercised by a real caller rather than
only by its own tests.

No authentication, token, or credential surface exists here and none may be added: `permission.mode` is the
operation's declared capability (observe / propose / execute), the same vocabulary the ownership contracts
already use, and a refusal is a normal returned outcome rather than an exception.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from context_bundle import ContextBundle

REPO_ROOT = Path(__file__).resolve().parents[3]
SCHEMA_PATH = REPO_ROOT / "packages" / "contracts" / "schemas" / "workflow" / "quick-entry-request.schema.json"
SCHEMA_ID = "work-lab/quick-entry-request/v1"

# §15.2: 放行条件为覆盖 输入修订、权限拒绝、客户端不可用、失败恢复与取消.
OUTCOME_ACCEPTED = "ACCEPTED"
OUTCOME_INPUT_REVISED = "INPUT_REVISED"
OUTCOME_PERMISSION_REFUSED = "PERMISSION_REFUSED"
OUTCOME_CLIENT_UNAVAILABLE = "CLIENT_UNAVAILABLE"
OUTCOME_CANCELLED = "CANCELLED"
OUTCOME_RECOVERED = "RECOVERED"
OUTCOME_INVALID = "INVALID_REQUEST"
OUTCOME_PROJECT_UNAPPROVED = "PROJECT_UNAPPROVED"

# Cancellation first: a cancelled request must not be re-interpreted as any other verdict, and a
# permission refusal before availability, because "we could not reach the client" is a misleading reason
# for an operation that was never allowed to run.
PRECEDENCE = (
    OUTCOME_CANCELLED,
    OUTCOME_PERMISSION_REFUSED,
    OUTCOME_CLIENT_UNAVAILABLE,
    OUTCOME_INPUT_REVISED,
)


@dataclass(frozen=True)
class EntryDecision:
    """What the entry decided, with the reason stated in the outcome and never in prose alone."""

    outcome: str
    request_id: str
    reason: str
    bundle: dict[str, Any] | None = None
    details: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "schemaVersion": "work-lab/quick-entry-decision/v1",
            "outcome": self.outcome,
            "requestId": self.request_id,
            "reason": self.reason,
            "bundle": self.bundle,
            "details": self.details or {},
        }


def validate(request: Mapping[str, Any]) -> list[str]:
    """Contract violations as messages. Empty means the request is well-formed.

    `jsonschema` is resolved from the repository's own schema file rather than by $id, so nothing here can
    reach the network while validating a local desktop operation.
    """
    import jsonschema

    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    validator = jsonschema.Draft202012Validator(schema)
    return [
        f"{error.json_path}: {error.message}"
        for error in sorted(validator.iter_errors(dict(request)), key=lambda e: str(e.json_path))
    ]


def _cancelled(request: Mapping[str, Any]) -> bool:
    return bool((request.get("cancellation") or {}).get("requested"))


def _permission_refused(request: Mapping[str, Any], allowed_modes: tuple[str, ...]) -> str | None:
    mode = (request.get("permission") or {}).get("mode")
    if mode not in allowed_modes:
        return f"mode {mode!r} is not in the entry's allowed set {list(allowed_modes)}"
    return None


def _client_unavailable(request: Mapping[str, Any], live_hosts: Mapping[str, bool]) -> str | None:
    host_id = (request.get("client") or {}).get("hostId") or ""
    declared = (request.get("client") or {}).get("declaredAvailable")
    live = live_hosts.get(host_id)
    if live is None:
        return f"host {host_id!r} is not registered with the entry"
    if not live:
        return f"host {host_id!r} is not available now (caller declared {declared!r})"
    return None


def _input_revised(request: Mapping[str, Any]) -> str | None:
    base = (request.get("input") or {}).get("baseRevision")
    current = (request.get("input") or {}).get("currentRevision")
    if base == "UNKNOWN" or current == "UNKNOWN":
        # UNKNOWN is not a mismatch and not a match: the entry says so rather than guessing either way.
        return f"input revision is UNKNOWN on at least one side (base={base!r} current={current!r})"
    if base != current:
        return f"input moved since the caller built it (base={base!r} current={current!r})"
    return None


def submit(request: Mapping[str, Any], *,
           live_hosts: Mapping[str, bool],
           allowed_modes: tuple[str, ...] = ("observe", "propose", "execute"),
           approved_project_ids: tuple[str, ...] = (),
           bundle_facts: Mapping[str, Any] | None = None) -> EntryDecision:
    """Judge one Quick Entry request and, when accepted, assemble its context bundle."""
    problems = validate(request)
    request_id = str(request.get("requestId") or "")
    if problems:
        return EntryDecision(OUTCOME_INVALID, request_id,
                             "request does not satisfy " + SCHEMA_ID, details={"problems": problems})

    if _cancelled(request):
        already = bool((request.get("cancellation") or {}).get("sideEffectsAlreadyMade"))
        return EntryDecision(
            OUTCOME_CANCELLED, request_id,
            "cancelled before any side effect" if not already
            else "cancelled after a side effect was already made; this is not a rollback",
            details={"sideEffectsAlreadyMade": already})

    refusal = _permission_refused(request, allowed_modes)
    if refusal:
        return EntryDecision(OUTCOME_PERMISSION_REFUSED, request_id, refusal)

    unavailable = _client_unavailable(request, live_hosts)
    if unavailable:
        return EntryDecision(OUTCOME_CLIENT_UNAVAILABLE, request_id, unavailable)

    revised = _input_revised(request)
    if revised:
        return EntryDecision(OUTCOME_INPUT_REVISED, request_id, revised,
                             details={"base": request["input"]["baseRevision"],
                                      "current": request["input"]["currentRevision"]})

    project_id = str(request["project"]["projectId"])
    if project_id not in approved_project_ids:
        # The approved index is the only authority here; a path from the request text is never resolved.
        return EntryDecision(OUTCOME_PROJECT_UNAPPROVED, request_id,
                             f"project {project_id!r} is not in the approved index",
                             details={"approvedCount": len(approved_project_ids)})

    if bundle_facts is None:
        return EntryDecision(OUTCOME_ACCEPTED, request_id, "accepted; no bundle facts supplied, "
                                                           "so nothing was assembled",
                             details={"bundleAssembled": False})

    facts = dict(bundle_facts)
    preserve = facts.pop("preserve", None) or {}
    blocks = facts.pop("blocks", None) or {}
    bundle = ContextBundle(project_id,
                           facts.pop("rulesRevision", "unversioned"),
                           facts.pop("globalRulesRevision", "global-1")).build(
        blocks=blocks,
        boundary=facts.pop("boundary", ""),
        acceptance=facts.pop("acceptance", ""),
        base_tree=facts.pop("baseTree", None),
        evidence_selectors=facts.pop("evidenceSelectors", None),
        data_classification=facts.pop("dataClassification", "public"),
        redaction_result=facts.pop("redactionResult", "none-required"),
        volatile=facts.pop("volatile", None),
        preserve=preserve,
    )

    recovery = request.get("recovery") or {}
    outcome = OUTCOME_RECOVERED if int(recovery.get("attempt") or 0) > 1 else OUTCOME_ACCEPTED
    reason = ("accepted on recovery attempt " + str(recovery.get("attempt"))
              if outcome == OUTCOME_RECOVERED else "accepted on the first attempt")
    carried = list(recovery.get("carriedForward") or []) if outcome == OUTCOME_RECOVERED else []
    lost = [key for key in preserve if key not in carried] if carried else []
    return EntryDecision(
        outcome, request_id, reason, bundle=bundle,
        details={"projectId": project_id, "verb": request["verb"], "permissionMode": request["permission"]["mode"],
                 "carriedForward": carried, "driftFactsNotMarkedCarried": lost})
