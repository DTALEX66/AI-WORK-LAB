# SPDX-License-Identifier: MIT
"""DL-CLOUD-2026-09-25 Prompt I: the Quality -> Jury -> Rights -> Preflight ->
Handoff readiness combiner (structural decision layer).

Composes the four *existing* contracts into one user-visible readiness
decision. It creates no parallel quality truth:

* the human/automated/deterministic gate is read from the sealed
  ``QualityRecord`` via :func:`design_lab.assurance.quality_record.
  final_gate_of` (the record is validated by the record module, so an
  automated judge can never reach the gate here either);
* the rights bands below are THIS module's classification of the state values that
  ``design-lab/config/rights-registry.json`` actually records, not a copy of a list the
  registry publishes: the file states values, and only a policy can say which of them block
  a handoff. ``design-lab/scripts/verify_rights_readiness_bands.py`` binds the classification
  to the file it claims to classify -- every value present in the registry must fall in one
  band, or the gate goes red instead of the combiner quietly reclassifying it;
* the preflight shape is ``preflight.schema.json`` (``result.status`` +
  ``required_checks[].severity`` + per-check status);
* the handoff shape is ``design-handoff.schema.json`` (artifacts, assets,
  approvals).

The combiner is a pure, fail-closed function of four documents and an
optional live-artifact digest: it never reads files, never downloads, and
never mutates. ``READY_FOR_HANDOFF`` is reachable only when there is not a
single blocker (human gate open, rights blocker, preflight blocker,
re-open failure, stale artifact, or an unapproved/rejected handoff approval).
The same source list feeds ``ui_signals`` (BLOCKER / WARNING / INFO), so the
user-visible UI and the backend decision cannot disagree.

This is the *backend decision contract* of Prompt I. Wiring the signals into
a Workbench UI surface is the owner-gated C/D/E product layer and is
deliberately out of scope here.
"""
from __future__ import annotations

from typing import Any, Mapping

from design_lab.assurance import quality_record

# -- rights state bands: see the module docstring, bound by
#    design-lab/scripts/verify_rights_readiness_bands.py ------------------
_RIGHTS_BLOCKING = ("FORBIDDEN", "NOT_ADJUDICATED")
_RIGHTS_RESTRICTING = (
    "PERSONAL_RESEARCH_NONCOMMERCIAL_ONLY",
    "NO_THIRD_PARTY_DISTRIBUTION",
)
_RIGHTS_CLEAN = ("ADJUDICATED",)
#: The four fields a subject's licence position is recorded in. `territory.state` is nested,
#: so it is named here as the read-back path rather than as a flat key.
RIGHTS_FIELDS = ("territory.state", "use_restriction", "output_restriction",
                 "redistribution")

# severities that a failing preflight check maps to
_BLOCKING_SEVERITY = "blocker"


class ReadinessError(ValueError):
    """A readiness input is malformed; the decision fails closed."""


def _quality_gates(quality: Mapping[str, Any]) -> tuple[list, list, list, Mapping[str, Any]]:
    """Validate the sealed QualityRecord and split its planes into the three
    signal bands. Reuses the record module -- no re-derivation of the gate."""
    blockers: list[str] = []
    warnings: list[str] = []
    info: list[str] = []
    # fail-closed: the document must be a well-formed sealed record
    document = quality_record.validate_quality_record(quality)
    gate = quality_record.final_gate_of(document)
    summary = quality_record.as_gate_summary(document)
    if gate == "PASS":
        info.append("human_jury: APPROVE (quality final_gate=PASS)")
    else:
        blockers.append(f"human_gate: quality final_gate={gate} (human gate open)")
    # the deterministic plane's blocking findings are surfaced as blockers
    for fid in summary.get("deterministic", {}).get("blocking", []):
        blockers.append(f"deterministic: {fid} hard-blocks")
    auto = summary.get("automated_judge", {})
    if auto.get("finding_count"):
        # advisory only -- a model score never blocks or vetoes, but it is
        # reported so the user sees it exists without it reaching the gate
        info.append(f"automated_judge: {auto['finding_count']} advisory finding(s) (never gate the decision)")
    return blockers, warnings, info, document


def _state_of(entry: Mapping[str, Any], field: str) -> Any:
    """The recorded value of one rights field, reading `territory.state` through its path."""
    if field == "territory.state":
        return (entry.get("territory") or {}).get("state")
    return entry.get(field)


def rights_band(state: Any) -> str:
    """Which band a recorded rights state falls in: BLOCKER / WARNING / ABSENT / UNCLASSIFIED.

    One function owns the classification so a caller, a route and this combiner cannot each
    answer "does this licence state block a handoff" with a different rule.
    """
    if state is None:
        return "ABSENT"
    if state in _RIGHTS_BLOCKING:
        return "BLOCKER"
    if state in _RIGHTS_RESTRICTING:
        return "WARNING"
    if state in _RIGHTS_CLEAN:
        return "CLEAN"
    return "UNCLASSIFIED"


def _rights_gates(rights_entries: list[Mapping[str, Any]]) -> tuple[list, list, list]:
    blockers, warnings, info = [], [], []
    for entry in rights_entries:
        subject = str(entry.get("subject_id", "<unspecified>"))
        states = {field: _state_of(entry, field) for field in RIGHTS_FIELDS}
        for field, state in states.items():
            band = rights_band(state)
            if band == "ABSENT":
                # a rights field the registry did not record -- the registry
                # never guesses a legal position, so an absence is not clean
                warnings.append(f"rights:{subject}:{field}=ABSENT (registry recorded no value)")
            elif band == "BLOCKER":
                blockers.append(f"rights:{subject}:{field}={state}")
            elif band == "WARNING":
                warnings.append(f"rights:{subject}:{field}={state}")
            elif band == "CLEAN":
                info.append(f"rights:{subject}:{field}=ADJUDICATED")
            else:
                # Fail closed. A state this module does not classify is a licence position
                # nobody has ruled on, and `READY_FOR_HANDOFF` means "not a single blocker".
                # A warning would let a new registry value -- `LITIGATION_HOLD`, a typo of
                # `FORBIDEN`, a value added under another taskpack -- pass straight through,
                # because the unclassified band was never a place a blocker could come from.
                blockers.append(
                    f"rights:{subject}:{field}={state!r} UNCLASSIFIED (not in any rights "
                    'band; blocking rather than letting an unruled licence state reach '
                    'READY_FOR_HANDOFF)')
    return blockers, warnings, info


def _preflight_gates(preflight: Mapping[str, Any] | None) -> tuple[list, list, list, list]:
    """result.status + per-check severity. Returns (blockers, warnings, info,
    blocking_check_ids)."""
    blockers, warnings, info = [], [], []
    blocking_check_ids: list[str] = []
    if preflight is None:
        # no preflight report supplied: the production gate has not been run.
        # A READY handoff requires a passing preflight, so absence blocks.
        blockers.append("preflight: no report supplied (production preflight not run)")
        return blockers, warnings, info, blocking_check_ids
    result = preflight.get("result") or {}
    status = result.get("status")
    if status == "fail":
        blockers.append("preflight: result.status=fail")
    elif status == "pass":
        info.append("preflight: result.status=pass")
    else:
        warnings.append(f"preflight: result.status={status!r} (not pass)")
    # map each check to the severity of the matching required_check
    required = {c.get("id"): c.get("severity") for c in preflight.get("required_checks", []) if isinstance(c, Mapping)}
    for chk in result.get("checks", []):
        if not isinstance(chk, Mapping):
            continue
        cid = str(chk.get("id", "<unspecified>"))
        cstat = chk.get("status")
        sev = required.get(cid)
        if cstat == "fail":
            if sev == _BLOCKING_SEVERITY:
                blockers.append(f"preflight:{cid}=fail (severity={sev})")
                blocking_check_ids.append(cid)
            else:
                warnings.append(f"preflight:{cid}=fail (severity={sev or 'unspecified'})")
        elif cstat == "warning":
            warnings.append(f"preflight:{cid}=warning")
    return blockers, warnings, info, blocking_check_ids


def _handoff_gates(handoff: Mapping[str, Any], quality_artifact_sha: str | None, live_artifact_sha: str | None) -> tuple[list, list, list]:
    blockers, warnings, info = [], [], []
    for ap in handoff.get("approvals", []):
        role = str(ap.get("role", "<unspecified>"))
        st = ap.get("status")
        if st in ("rejected", "pending"):
            blockers.append(f"handoff.approval:{role}={st}")
        elif st in ("approved", "approved-with-notes"):
            info.append(f"handoff.approval:{role}={st}")
        else:
            warnings.append(f"handoff.approval:{role}={st!r} (unrecognised)")
    # stale-artifact: every handoff artifact the caller asserts is the
    # quality-authenticated one must carry the record's artifact digest (or a
    # live digest the caller re-observed); a mismatch is a stale artifact.
    for art in handoff.get("artifacts", []):
        ahash = art.get("hash")
        if not ahash:
            warnings.append(f"handoff.artifact:{art.get('path','?')}=hash-missing")
            continue
        if quality_artifact_sha is not None and ahash != quality_artifact_sha:
            blockers.append(f"stale_artifact: handoff {art.get('path','?')} hash != quality record artifact_sha256")
        if live_artifact_sha is not None and ahash != live_artifact_sha:
            blockers.append(f"stale_artifact: handoff {art.get('path','?')} hash != live re-observed digest")
    # missing fonts / rollback / provenance are completion signals, not hard
    # blockers by themselves -- but the editable source is required to hand off
    if not any(art.get("editable") for art in handoff.get("artifacts", [])):
        warnings.append("handoff: no editable source artifact declared")
    return blockers, warnings, info


def decide(*, quality_record_doc: Mapping[str, Any],
           rights_entries: list[Mapping[str, Any]],
           preflight: Mapping[str, Any] | None,
           handoff: Mapping[str, Any],
           live_artifact_sha: str | None = None) -> Mapping[str, Any]:
    """Combine the four contracts into one readiness decision.

    Pure and fail-closed. ``READY_FOR_HANDOFF`` iff the BLOCKER band is empty
    and the quality record's final gate is PASS (a signed human APPROVE).
    The same source list feeds ``ui_signals`` so the UI and backend agree.
    """
    blockers: list[str] = []
    warnings: list[str] = []
    info: list[str] = []

    q_blk, q_wrn, q_inf, document = _quality_gates(quality_record_doc)
    r_blk, r_wrn, r_inf = _rights_gates(rights_entries)
    p_blk, p_wrn, p_inf, _blk_ids = _preflight_gates(preflight)
    h_blk, h_wrn, h_inf = _handoff_gates(handoff, document.get("artifact_sha256"), live_artifact_sha)

    blockers = q_blk + r_blk + p_blk + h_blk
    warnings = q_wrn + r_wrn + p_wrn + h_wrn
    info = q_inf + r_inf + p_inf + h_inf

    gate = quality_record.final_gate_of(document)
    ready = not blockers and gate == "PASS"
    return {
        "schemaVersion": "design-lab/handoff-readiness/v1",
        "readiness": "READY_FOR_HANDOFF" if ready else "BLOCKED",
        "quality_final_gate": gate,
        "blockers": blockers,
        "ui_signals": {"BLOCKER": blockers, "WARNING": warnings, "INFO": info},
        "warnings": warnings,
        "info": info,
    }


__all__ = [
    "decide", "ReadinessError", "RIGHTS_FIELDS", "rights_band",
]
