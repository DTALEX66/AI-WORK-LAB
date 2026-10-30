# SPDX-License-Identifier: MIT
"""DL-CLOUDAUDIT-B3 / G-3: the sealed per-artifact QualityRecord.

This is the *record* counterpart of the frozen QA policy that
:mod:`~design_lab.assurance.qa_plane` and :mod:`~design_lab.assurance.human_jury`
already own. Those two modules define the policy (which plane may produce which
outcome and its evidence ceiling) and the human-jury record structure. This
module composes them into one per-artifact document -- the ``QualityRecord`` --
whose ``quality.{deterministic, automated_judge, human_jury}`` triple is carried
as three **physically separated, non-overwriting** fields:

* ``deterministic``      -- the deterministic plane's findings (reproducible
  rules, rights/security). Allowed outcomes PASS / WARN / HARD_BLOCK.
* ``automated_judge``    -- the model-assisted plane's findings. Allowed
  outcomes PASS / WARN / REVIEW_REQUIRED; advisory only, never final.
* ``human_jury``         -- the human jury's signed verdict (APPROVE / REJECT),
  or ``null`` when the human gate has not been reached.

The physical guarantees each refused by name, not by configuration:

* **No automated plane fills the human field.** The ``human_jury`` field only
  accepts a record that passes :func:`human_jury.assert_not_agent_signed`; a
  model/agent judge document -- even one re-tagged as a verdict or still carrying
  proposal markers -- is refused, so an automated score can never masquerade as
  the human verdict.
* **No model score reaches the gate.** ``final_gate`` is computed exclusively
  from the deterministic and human planes (via :func:`qa_plane.aggregate`, which
  the tested qa-plane logic already keeps advisory for the model plane). The
  ``automated_judge`` findings never contribute to the gate, so a model score
  cannot be averaged or laundered into a final decision.
* **No field overwrites another.** Each field is a closed object and every
  embedded finding is re-validated through :func:`qa_plane.validate_finding` and
  checked to belong to the plane of its own field, so a finding smuggled into
  the wrong plane is refused by the frozen policy. All three planes are bound to
  the one ``artifact_sha256``; a record that mixes two artifacts fails closed.
* **PASS is structurally unreachable without a human verdict.** A record whose
  ``human_jury`` is ``null`` can only ever report ``NEEDS_HUMAN_VERDICT`` or
  ``BLOCKED``; only a signed human ``APPROVE`` reaches ``PASS``.

Boundary (held by every module in this package): structural validation and
composition only. Nothing here runs a check, calls a provider, reads an
artifact, opens a host or invents a human identity; a record that cannot be
validated fails closed with :class:`~design_lab.assurance.AssuranceError`.
"""
from __future__ import annotations

import json
from functools import lru_cache
from typing import Mapping

from ..runtime.paths import PROJECT_ROOT
from . import AssuranceError, require_digest, require_rfc3339, require_text, utc_now_rfc3339
from . import human_jury, qa_plane

SCHEMA_PATH = PROJECT_ROOT / "design-lab/schemas/assurance-quality-record.schema.json"

QUALITY_RECORD_VERSION = "design-lab/assurance-quality-record/v1"

#: The three physically separated plane fields of a QualityRecord.
FIELD_DETERMINISTIC = "deterministic"
FIELD_AUTOMATED_JUDGE = "automated_judge"
FIELD_HUMAN_JURY = "human_jury"
PLANE_FIELDS = (FIELD_DETERMINISTIC, FIELD_AUTOMATED_JUDGE, FIELD_HUMAN_JURY)

#: ``final_gate`` reuses the qa-plane gate vocabulary; a record never invents one.
GATES = qa_plane.GATES

_DETERMINISTIC_PLANE_IDS = tuple(
    layer.layer_id for layer in qa_plane.QA_PLANES if layer.kind == qa_plane.KIND_DETERMINISTIC
)
_MODEL_PLANE_IDS = tuple(
    layer.layer_id for layer in qa_plane.QA_PLANES if layer.kind == qa_plane.KIND_MODEL_ASSISTED
)
_HUMAN_PLANE_IDS = tuple(
    layer.layer_id for layer in qa_plane.QA_PLANES if layer.kind == qa_plane.KIND_HUMAN
)


@lru_cache(maxsize=1)
def schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def _check_schema(document: dict) -> None:
    from jsonschema import Draft202012Validator

    validator = Draft202012Validator(schema())
    errors = sorted(validator.iter_errors(document), key=lambda error: list(error.path))
    if errors:
        first = errors[0]
        where = "/".join(str(part) for part in first.path)
        raise AssuranceError(
            "quality record violates assurance-quality-record.schema.json"
            f"{('/' + where) if where else ''}: {first.message}"
        )


def _finding_from_doc(doc: Mapping, field: str) -> qa_plane.QaFinding:
    """Rebuild one embedded finding and re-validate it through the frozen policy.

    Every finding carried in any plane field is run through
    ``qa_plane.validate_finding``, so a finding placed in the wrong plane, with a
    disallowed outcome, a verdict on an automated plane, or an unsigned human
    outcome is refused by the policy itself -- the record cannot relax it.
    """
    if not isinstance(doc, Mapping):
        raise AssuranceError(f"finding in {field!r} must be an object; got {type(doc).__name__}")
    try:
        finding = qa_plane.QaFinding(
            finding_id=doc.get("finding_id"),
            layer_id=doc.get("layer_id"),
            check_id=doc.get("check_id"),
            subject_ref=doc.get("subject_ref"),
            outcome=doc.get("outcome"),
            severity=doc.get("severity"),
            evidence=doc.get("evidence") or {},
            recommendation=doc.get("recommendation"),
            verdict=doc.get("verdict"),
        )
    except (TypeError, ValueError) as exc:
        raise AssuranceError(f"finding in {field!r} is malformed: {exc}") from exc
    return qa_plane.validate_finding(finding)


def _normalize_finding(finding, field: str) -> qa_plane.QaFinding:
    """Accept a finding document or a :class:`qa_plane.QaFinding` instance."""
    if isinstance(finding, qa_plane.QaFinding):
        return qa_plane.validate_finding(finding)
    return _finding_from_doc(finding, field)


def _plane_of(finding: qa_plane.QaFinding) -> qa_plane.QaLayer:
    return qa_plane.plane_for(finding.layer_id)


def _check_plane_field(field: str, findings: list[qa_plane.QaFinding], expected_ids: tuple,
                       artifact_sha256: str) -> None:
    """Every finding in ``field`` must belong to a plane of that field's kind."""
    for finding in findings:
        layer = _plane_of(finding)
        if layer.layer_id not in expected_ids:
            raise AssuranceError(
                f"finding {finding.finding_id!r} belongs to plane {layer.layer_id!r} but was "
                f"placed in the {field!r} field; a finding may only appear in the field of the "
                "plane that produced it, and a finding in another plane does not overwrite it"
            )
        digest = (finding.evidence or {}).get("artifact_sha256")
        if digest != artifact_sha256:
            raise AssuranceError(
                f"finding {finding.finding_id!r} in {field!r} is bound to artifact {digest!r}, "
                f"but the record is about {artifact_sha256!r}; one record describes one artifact"
            )


def _human_finding(jury: Mapping, subject_ref: str) -> qa_plane.QaFinding:
    """Bridge a signed human verdict into the qa-plane finding vocabulary.

    The gate is always computed through the tested ``qa_plane.aggregate``: the
    human verdict becomes a HUMAN-plane finding (``APPROVE`` / ``REJECT``; a
    ``REJECT`` is the blocking act). No automated plane is passed in, so the
    model judge structurally cannot influence the gate.
    """
    verdict = jury.get("verdict")
    severity = "BLOCKER" if verdict == qa_plane.REJECT else "INFO"
    return qa_plane.QaFinding(
        finding_id=f"human-{jury.get('jury_record_id', 'verdict')}",
        layer_id="qa-human",
        check_id="human-jury",
        subject_ref=subject_ref,
        outcome=verdict,
        severity=severity,
        evidence={"artifact_sha256": jury.get("artifact_sha256")},
        verdict=verdict,
    )


def _finding_docs(document: Mapping, field: str) -> list:
    """The finding documents of one plane block (``{"findings": [...]}``)."""
    block = document.get(field, {})
    if not isinstance(block, Mapping):
        return []
    return list(block.get("findings", []))


def final_gate_of(document: Mapping) -> str:
    """The gate a QualityRecord reports, derived ONLY from the non-advisory planes.

    The deterministic and human planes are aggregated (a hard block or a human
    ``REJECT`` outranks everything; ``PASS`` needs a human verdict); the
    ``automated_judge`` findings are deliberately excluded, so a model score can
    never be averaged or laundered into the final gate.
    """
    if not isinstance(document, Mapping):
        raise AssuranceError("final_gate_of requires a quality record document")
    det = [_finding_from_doc(f, FIELD_DETERMINISTIC) for f in _finding_docs(document, FIELD_DETERMINISTIC)]
    gating = list(det)
    jury = document.get(FIELD_HUMAN_JURY)
    if jury is not None:
        jury_doc = human_jury.assert_not_agent_signed(jury)
        gating.append(_human_finding(jury_doc, document.get("subject_ref", "")))
    summary = qa_plane.aggregate(gating)
    return summary["gate"]


def record_quality_record(*, quality_record_id, subject_ref, artifact_sha256,
                         deterministic=(), automated_judge=(), human_verdict=None,
                         created_at: str | None = None) -> dict:
    """Build and validate a sealed per-artifact QualityRecord document.

    ``deterministic`` / ``automated_judge`` are iterables of qa-plane finding
    documents (or :class:`qa_plane.QaFinding` instances); ``human_verdict`` is a
    signed jury verdict document (or a :class:`human_jury.JuryVerdict`) or
    ``None`` when the human gate has not yet been reached. ``created_at`` may be
    omitted, in which case the current UTC instant is used. The returned document
    is plain and schema-checked; its ``final_gate`` is derived, never supplied.
    """
    record_id = require_text(quality_record_id, "quality_record_id")
    subject = require_text(subject_ref, "subject_ref")
    digest = require_digest(artifact_sha256, "artifact_sha256")
    stamp = require_rfc3339(created_at, "created_at") if created_at else utc_now_rfc3339()

    det = [_normalize_finding(f, FIELD_DETERMINISTIC) for f in deterministic]
    judge = [_normalize_finding(f, FIELD_AUTOMATED_JUDGE) for f in automated_judge]
    _check_plane_field(FIELD_DETERMINISTIC, det, _DETERMINISTIC_PLANE_IDS, digest)
    _check_plane_field(FIELD_AUTOMATED_JUDGE, judge, _MODEL_PLANE_IDS, digest)

    jury_doc = None
    if human_verdict is not None:
        if isinstance(human_verdict, human_jury.JuryVerdict):
            jury_doc = human_jury.record_verdict(human_verdict)
        elif isinstance(human_verdict, Mapping):
            jury_doc = dict(human_verdict)
        else:
            raise AssuranceError(
                "human_verdict must be a jury verdict document or a JuryVerdict; "
                f"got {type(human_verdict).__name__}"
            )
        jury_doc = human_jury.assert_not_agent_signed(jury_doc)
        if jury_doc.get("artifact_sha256") != digest:
            raise AssuranceError(
                f"the human verdict is bound to artifact {jury_doc.get('artifact_sha256')!r}, "
                f"but the record is about {digest!r}; one record describes one artifact"
            )

    document = {
        "schemaVersion": QUALITY_RECORD_VERSION,
        "quality_record_id": record_id,
        "subject_ref": subject,
        "artifact_sha256": digest,
        FIELD_DETERMINISTIC: {"findings": [item.as_dict() for item in det]},
        FIELD_AUTOMATED_JUDGE: {"findings": [item.as_dict() for item in judge]},
        FIELD_HUMAN_JURY: jury_doc,
        "final_gate": "",
        "created_at": stamp,
    }
    document["final_gate"] = final_gate_of(document)
    _check_schema(document)
    return document


def validate_quality_record(document: Mapping) -> Mapping:
    """Re-validate a stored QualityRecord document (fail-closed).

    Re-checks every embedded finding through the frozen qa-plane policy, the
    human field through the jury signing rules, the single-artifact binding, the
    plane-field placement, and the derived ``final_gate``. A document that stops
    satisfying any of these -- for example after an automated judge is re-tagged
    as the human verdict, or two artifacts are mixed -- fails closed.
    """
    if not isinstance(document, Mapping):
        raise AssuranceError("a quality record must be a JSON object; failing closed")
    if document.get("schemaVersion") != QUALITY_RECORD_VERSION:
        raise AssuranceError(
            f"a quality record must declare schemaVersion {QUALITY_RECORD_VERSION!r}; "
            f"got {document.get('schemaVersion')!r}"
        )
    digest = require_digest(document.get("artifact_sha256"), "artifact_sha256")
    require_text(document.get("quality_record_id"), "quality_record_id")
    require_text(document.get("subject_ref"), "subject_ref")
    require_rfc3339(document.get("created_at"), "created_at")

    for field, expected in ((FIELD_DETERMINISTIC, _DETERMINISTIC_PLANE_IDS),
                            (FIELD_AUTOMATED_JUDGE, _MODEL_PLANE_IDS)):
        block = document.get(field, {})
        if not isinstance(block, Mapping):
            raise AssuranceError(f"the {field!r} field must be an object with a 'findings' list")
        findings = [_finding_from_doc(f, field) for f in block.get("findings", [])]
        _check_plane_field(field, findings, expected, digest)

    jury = document.get(FIELD_HUMAN_JURY)
    if jury is not None:
        jury_doc = human_jury.assert_not_agent_signed(jury)
        if jury_doc.get("artifact_sha256") != digest:
            raise AssuranceError(
                "the human_jury verdict is bound to a different artifact than the record; "
                "one record describes one artifact"
            )

    derived = final_gate_of(document)
    reported = document.get("final_gate")
    if reported != derived:
        raise AssuranceError(
            f"the record reports final_gate {reported!r} but the non-advisory planes derive "
            f"{derived!r}; the gate is computed from the deterministic and human planes only, "
            "and an automated judge may never supply it"
        )
    _check_schema(document)
    return document


def as_gate_summary(document: Mapping) -> dict:
    """A stable per-plane gate view: what each plane owes, which block, the gate.

    Structurally excludes the automated judge from ``blocking`` and from the
    gate, so a reader of the summary cannot mistake a model score for a
    decision.
    """
    validate_quality_record(document)
    det = [_finding_from_doc(f, FIELD_DETERMINISTIC) for f in _finding_docs(document, FIELD_DETERMINISTIC)]
    blocking_det = [f.finding_id for f in det if qa_plane.blocks(f)]
    jury = document.get(FIELD_HUMAN_JURY)
    blocking_human = ([f"human-{jury.get('jury_record_id', 'verdict')}"]
                      if jury is not None and jury.get("verdict") == qa_plane.REJECT else [])
    return {
        "quality_record_id": document["quality_record_id"],
        "final_gate": document["final_gate"],
        "deterministic": {"finding_count": len(det), "blocking": blocking_det},
        "automated_judge": {
            "finding_count": len(_finding_docs(document, FIELD_AUTOMATED_JUDGE)),
            "final": False,
            "note": "advisory only: a model-assisted finding never blocks, vetoes or signs",
        },
        "human_jury": {
            "present": jury is not None,
            "verdict": jury.get("verdict") if jury else None,
            "blocking": blocking_human,
        },
        "artifact_sha256": document["artifact_sha256"],
    }
