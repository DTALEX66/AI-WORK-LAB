# SPDX-License-Identifier: MIT
"""DL-P0-171 / DLDS-F070 human jury structure: a human verdict and an agent proposal are different types.

This module owns the jury record of DESIGN-LAB's Human Gate and extends the
existing ``jury-record.schema.json`` (V1) into
``assurance-jury-record-v2.schema.json`` with an explicit actor, a weighted
criterion breakdown, a bound artifact digest and an append-only ``supersedes``
edge. It does not replace the V1 contract or the ``JuryRecord`` template in
``packages/capabilities/quality/jury/``.

The verdict vocabulary is the frozen QA policy of DLDS-F070: the human jury's
final outcomes are ``APPROVE`` and ``REJECT``, and nothing else. The non-final
``REVISE`` this module previously carried was dropped with that policy: a human
who wants a revision states ``REJECT`` with evidence, which keeps exactly one
final vocabulary per plane and leaves no third state that a summary or a
downstream reader could mistake for acceptance. The values a proposal may
suggest are drawn from the same two outcomes, and a proposal is still never a
verdict.

The one structural guarantee: an AI agent can never sign a jury verdict. A
verdict is signed by a ``HUMAN`` or ``PANEL`` juror with an attestation, and an
agent may only produce a :class:`JuryProposal`, which is a different type with a
different ``kind`` marker; the schema roots differ in ``kind`` and in their
closed property sets, so a proposal document is *unrepresentable* as a verdict,
and it is additionally rejected by name by every function that accepts a
verdict. A record that carries proposal markers is refused even when it is
re-tagged ``JURY_VERDICT``, so an agent-produced document cannot be laundered
into a verdict by relabelling. There is no code path in this module that
converts a proposal into a verdict, and no function here invents a juror, an
attestation or a timestamp.

Boundary: structural validation only. No host access, no model call, no network,
no persistence; a record that cannot be validated fails closed with
:class:`~design_lab.assurance.AssuranceError`.

Honesty limit: this module proves that a record *claims* no automation and is
internally complete. It cannot prove that a human actually looked at the
artifact -- that requires an out-of-band attestation (the E4 evidence card of
the Human Gate) and is deliberately out of scope here.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from functools import lru_cache
import json
from typing import Mapping

from ..runtime.state_resources import repo_resource
from . import AssuranceError, require_digest, require_rfc3339, require_text

SCHEMA_PATH = repo_resource('schemas/assurance-jury-record-v2.schema.json')

KIND_VERDICT = "JURY_VERDICT"
KIND_PROPOSAL = "JURY_PROPOSAL"

HUMAN_JUROR_KINDS = ("HUMAN", "PANEL")
# Actor kinds that identify automation. Declaring one of these on a verdict is
# refused outright rather than reinterpreted.
AGENT_ACTOR_KINDS = (
    "AGENT", "AI", "ASSISTANT", "AUTOMATED", "BOT", "LLM", "MACHINE", "MODEL",
    "PIPELINE", "SCRIPT", "SERVICE", "SYSTEM", "TOOL",
)
#: The frozen final vocabulary (DLDS-F070). There is no third verdict: a wanted
#: revision is expressed as REJECT plus evidence, not as a non-final REVISE.
APPROVE = "APPROVE"
REJECT = "REJECT"
VERDICTS = (APPROVE, REJECT)
#: Alias used by the QA plane, which declares the same two values as the final
#: outcomes: one vocabulary, two modules.
FINAL_OUTCOMES = VERDICTS
#: Fields that mark a document as agent-produced. A verdict may never carry one,
#: whatever its ``kind`` says, so a proposal cannot be re-tagged into a verdict.
PROPOSAL_MARKERS = ("proposal_id", "proposer", "suggested_verdict", "is_verdict")
SCORE_FLOOR = 0.0
SCORE_CEILING = 5.0
WEIGHT_TOLERANCE = 1e-6
REVIEW_VERSION = "design-lab/assurance-jury-record/v2"


@dataclass(frozen=True)
class Juror:
    """The human actor accountable for a verdict; ``members`` names a panel."""

    juror_id: str
    kind: str
    attestation: str
    members: tuple = ()

    def as_dict(self) -> dict:
        return {
            "juror_id": self.juror_id,
            "kind": self.kind,
            "attestation": self.attestation,
            "members": list(self.members),
        }


@dataclass(frozen=True)
class Criterion:
    """One weighted axis of the judgement, mirroring the V1 five-axis model."""

    criterion_id: str
    weight: float
    score: float
    note: str | None = None

    def as_dict(self) -> dict:
        return {
            "criterion_id": self.criterion_id,
            "weight": self.weight,
            "score": self.score,
            "note": self.note,
        }


@dataclass(frozen=True)
class JuryVerdict:
    """A human-signed verdict bound to one exact artifact digest."""

    jury_record_id: str
    subject_ref: str
    artifact_sha256: str
    juror: Juror
    criteria: tuple
    verdict: str
    decided_at: str
    supersedes: str | None = None
    evidence_refs: tuple = ()
    kind: str = KIND_VERDICT

    def as_dict(self) -> dict:
        return {
            "schemaVersion": REVIEW_VERSION,
            "kind": self.kind,
            "jury_record_id": self.jury_record_id,
            "subject_ref": self.subject_ref,
            "artifact_sha256": self.artifact_sha256,
            "juror": self.juror.as_dict() if isinstance(self.juror, Juror) else self.juror,
            "criteria": [item.as_dict() if isinstance(item, Criterion) else item
                         for item in self.criteria],
            "verdict": self.verdict,
            "decided_at": self.decided_at,
            "supersedes": self.supersedes,
            "evidence_refs": list(self.evidence_refs),
        }


@dataclass(frozen=True)
class JuryProposal:
    """An agent's suggestion. Explicitly NOT a verdict and never accepted as one."""

    proposal_id: str
    subject_ref: str
    artifact_sha256: str
    proposer: str
    criteria: tuple
    suggested_verdict: str
    rationale: str
    created_at: str
    kind: str = KIND_PROPOSAL
    is_verdict: bool = False

    def as_dict(self) -> dict:
        return {
            "schemaVersion": REVIEW_VERSION,
            "kind": self.kind,
            "proposal_id": self.proposal_id,
            "subject_ref": self.subject_ref,
            "artifact_sha256": self.artifact_sha256,
            "proposer": self.proposer,
            "criteria": [item.as_dict() if isinstance(item, Criterion) else item
                         for item in self.criteria],
            "suggested_verdict": self.suggested_verdict,
            "rationale": self.rationale,
            "created_at": self.created_at,
            "is_verdict": self.is_verdict,
        }


@lru_cache(maxsize=1)
def schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def _validate_schema(document: dict) -> None:
    from jsonschema import Draft202012Validator

    validator = Draft202012Validator(schema())
    errors = sorted(validator.iter_errors(document), key=lambda error: list(error.path))
    if errors:
        first = errors[0]
        where = "/".join(str(part) for part in first.path)
        raise AssuranceError(
            f"jury record violates assurance-jury-record-v2.schema.json"
            f"{('/' + where) if where else ''}: {first.message}"
        )


def _kind_of(record) -> object:
    if isinstance(record, Mapping):
        return record.get("kind")
    return getattr(record, "kind", None)


def _require_verdict(record, *, function: str):
    """Refuse anything that is not a human/panel signed verdict.

    The explicit ``kind`` check comes first so a proposal, a model suggestion or
    a bare document is rejected by name rather than silently coerced. A record
    that carries proposal markers is refused next, even when its ``kind`` claims
    to be a verdict: relabelling an agent-produced document must not launder it
    into a human signature.
    """
    kind = _kind_of(record)
    if isinstance(record, JuryProposal) or kind == KIND_PROPOSAL:
        raise AssuranceError(
            f"{function} refuses a record of kind {KIND_PROPOSAL!r}: a jury proposal is a "
            "recommendation, not a verdict, and only a HUMAN or PANEL juror signs a verdict"
        )
    if kind != KIND_VERDICT:
        raise AssuranceError(
            f"{function} requires a record of kind {KIND_VERDICT!r}; got {kind!r} "
            f"({type(record).__name__})"
        )
    if not isinstance(record, (JuryVerdict, Mapping)):
        raise AssuranceError(
            f"{function} requires a JuryVerdict or a jury record document; "
            f"got {type(record).__name__}"
        )
    if isinstance(record, Mapping):
        markers = [name for name in PROPOSAL_MARKERS if name in record]
        if markers:
            raise AssuranceError(
                f"{function} refuses a record carrying the proposal marker(s) "
                f"{', '.join(markers)}: a {KIND_PROPOSAL} re-tagged as {KIND_VERDICT} is "
                "still an agent suggestion, and no agent may sign a human gate"
            )
    return record


def _document(record) -> dict:
    if isinstance(record, JuryVerdict):
        return record.as_dict()
    if isinstance(record, Mapping):
        return json.loads(json.dumps(record, allow_nan=False))
    raise AssuranceError(
        f"a jury record must be a JuryVerdict or a JSON object; got {type(record).__name__}"
    )


def assert_not_agent_signed(record) -> dict:
    """Refuse any record whose actor is automation rather than a human.

    Accepts a verdict, a verdict document or a foreign record and fails closed
    when the actor kind is missing, unknown or an agent kind. Returns the
    normalized document so a caller can bind the checked identity.
    """
    if isinstance(record, JuryProposal) or _kind_of(record) == KIND_PROPOSAL:
        raise AssuranceError(
            "a jury proposal is not a signed record: an agent may propose, never subscribe "
            "a human gate"
        )
    if isinstance(record, Mapping):
        markers = [name for name in PROPOSAL_MARKERS if name in record]
        if markers:
            raise AssuranceError(
                "the record carries the proposal marker(s) "
                f"{', '.join(markers)}: an agent-produced document is not a signed human "
                "record, whatever its kind marker says"
            )
    if isinstance(record, JuryVerdict):
        document = record.as_dict()
    elif isinstance(record, Mapping):
        document = _document(record)
    else:
        raise AssuranceError(
            f"cannot establish the signing actor of {type(record).__name__}; failing closed"
        )
    juror = document.get("juror")
    if not isinstance(juror, Mapping):
        raise AssuranceError(
            "the record declares no juror, so no human actor is established; failing closed"
        )
    kind = juror.get("kind")
    if kind in AGENT_ACTOR_KINDS:
        raise AssuranceError(
            f"an agent-signed verdict is refused: juror kind {kind!r} is automation, and no "
            "agent may sign a human gate"
        )
    if kind not in HUMAN_JUROR_KINDS:
        raise AssuranceError(
            f"the signing actor kind {kind!r} is not one of {', '.join(HUMAN_JUROR_KINDS)}; "
            "failing closed rather than assuming a human"
        )
    require_text(juror.get("juror_id"), "juror.juror_id")
    require_text(juror.get("attestation"), "juror.attestation")
    return document


def agent_may_propose(*, proposal_id, subject_ref, artifact_sha256, proposer, criteria,
                      suggested_verdict, rationale, created_at) -> JuryProposal:
    """Build an agent proposal. It is not a verdict and no function will treat it as one."""
    require_text(proposal_id, "proposal_id")
    require_text(subject_ref, "subject_ref")
    digest = require_digest(artifact_sha256, "artifact_sha256")
    require_text(proposer, "proposer")
    require_text(rationale, "rationale")
    require_rfc3339(created_at, "created_at")
    if suggested_verdict not in VERDICTS:
        raise AssuranceError(
            f"suggested_verdict must be one of {', '.join(VERDICTS)}; "
            f"got {suggested_verdict!r}"
        )
    proposal = JuryProposal(
        proposal_id=proposal_id,
        subject_ref=subject_ref,
        artifact_sha256=digest,
        proposer=proposer,
        criteria=tuple(_criteria(criteria)),
        suggested_verdict=suggested_verdict,
        rationale=rationale,
        created_at=created_at,
        kind=KIND_PROPOSAL,
        is_verdict=False,
    )
    _validate_proposal_schema(proposal.as_dict())
    return proposal


def _validate_proposal_schema(document: dict) -> None:
    from jsonschema import Draft202012Validator

    subschema = dict(schema()["$defs"]["proposal"])
    subschema["$defs"] = schema()["$defs"]
    errors = sorted(
        Draft202012Validator(subschema).iter_errors(document),
        key=lambda error: list(error.path),
    )
    if errors:
        first = errors[0]
        where = "/".join(str(part) for part in first.path)
        raise AssuranceError(
            f"jury proposal violates the declared proposal contract"
            f"{('/' + where) if where else ''}: {first.message}"
        )


def _criteria(criteria) -> list:
    if criteria is None or isinstance(criteria, (str, bytes, Mapping)):
        raise AssuranceError("criteria must be a sequence of criterion objects")
    collected = []
    for index, item in enumerate(criteria):
        if isinstance(item, Criterion):
            collected.append(item)
        elif isinstance(item, Mapping):
            collected.append(Criterion(
                criterion_id=item.get("criterion_id"),
                weight=item.get("weight"),
                score=item.get("score"),
                note=item.get("note"),
            ))
        else:
            raise AssuranceError(f"criteria/{index} must be a criterion object")
    if not collected:
        raise AssuranceError("a jury record needs at least one criterion")
    return collected


def _check_criteria(criteria: list, *, source: str) -> None:
    seen = set()
    total = 0.0
    for index, item in enumerate(criteria):
        require_text(item.criterion_id, f"criteria/{index}/criterion_id")
        if item.criterion_id in seen:
            raise AssuranceError(
                f"duplicate criterion_id {item.criterion_id!r} in {source}"
            )
        seen.add(item.criterion_id)
        if isinstance(item.weight, bool) or not isinstance(item.weight, (int, float)):
            raise AssuranceError(f"criteria/{index}/weight must be a number")
        if isinstance(item.score, bool) or not isinstance(item.score, (int, float)):
            raise AssuranceError(f"criteria/{index}/score must be a number")
        if item.weight < 0:
            raise AssuranceError(f"criteria/{index}/weight must not be negative")
        if not SCORE_FLOOR <= item.score <= SCORE_CEILING:
            raise AssuranceError(
                f"criteria/{index}/score {item.score!r} is outside "
                f"[{SCORE_FLOOR}, {SCORE_CEILING}]"
            )
        # A judgement at either extreme must say why: an unexplained 0 or 5 is
        # indistinguishable from a default value.
        if item.score <= SCORE_FLOOR or item.score >= SCORE_CEILING:
            if not isinstance(item.note, str) or not item.note.strip():
                raise AssuranceError(
                    f"criteria/{index} scores the extreme {item.score!r} without a note; "
                    "an extreme score must be explained by the human who gave it"
                )
        elif item.note is not None:
            require_text(item.note, f"criteria/{index}/note")
        total += float(item.weight)
    if abs(total - 1.0) > WEIGHT_TOLERANCE:
        raise AssuranceError(
            f"criterion weights of {source} must sum to 1.0 (tolerance {WEIGHT_TOLERANCE}); "
            f"got {total!r}"
        )


def record_verdict(verdict) -> dict:
    """Validate a human verdict and return the record document; never mutates input."""
    _require_verdict(verdict, function="record_verdict")
    document = _document(verdict)
    # The actor guard runs before generic schema validation so that automation
    # trying to sign a human gate is refused by name, not by a field message.
    assert_not_agent_signed(document)
    _validate_schema(document)
    if document.get("kind") != KIND_VERDICT:  # pragma: no cover - schema already pins it
        raise AssuranceError("jury record kind must be JURY_VERDICT")
    require_text(document.get("subject_ref"), "subject_ref")
    require_digest(document.get("artifact_sha256"), "artifact_sha256")
    require_rfc3339(document.get("decided_at"), "decided_at")

    criteria = _criteria(document.get("criteria"))
    _check_criteria(criteria, source=f"jury record {document.get('jury_record_id')!r}")

    juror = document["juror"]
    require_text(juror.get("juror_id"), "juror.juror_id")
    if juror["kind"] == "PANEL":
        members = juror.get("members") or []
        if not members:
            raise AssuranceError(
                "a PANEL juror must name its members; an unnamed panel cannot be a human actor"
            )
        for index, member in enumerate(members):
            require_text(member, f"juror/members/{index}")
    verdict_value = document.get("verdict")
    if verdict_value not in VERDICTS:
        raise AssuranceError(
            f"verdict must be one of {', '.join(VERDICTS)}; got {verdict_value!r}"
        )
    if verdict_value == REJECT:
        refs = document.get("evidence_refs") or []
        if not refs:
            raise AssuranceError(
                "a REJECT verdict requires at least one evidence_ref; a rejection without "
                "evidence cannot be reviewed or appealed"
            )
    for index, ref in enumerate(document.get("evidence_refs") or []):
        require_text(ref, f"evidence_refs/{index}")
    supersedes = document.get("supersedes")
    if supersedes is not None:
        require_text(supersedes, "supersedes")
        if supersedes == document.get("jury_record_id"):
            raise AssuranceError("a jury record may not supersede itself")
    return document


def score_summary(verdict) -> dict:
    """Weighted total and per-criterion breakdown; confidence stays null for one human."""
    document = record_verdict(verdict)
    criteria = _criteria(document["criteria"])
    breakdown = []
    total = 0.0
    for item in criteria:
        weighted = float(item.weight) * float(item.score)
        total += weighted
        breakdown.append({
            "criterion_id": item.criterion_id,
            "weight": item.weight,
            "score": item.score,
            "weighted": weighted,
            "note": item.note,
        })
    juror = document["juror"]
    members = list(juror.get("members") or [])
    if juror["kind"] == "PANEL" and len(members) > 1:
        confidence = (
            f"NOT_COMPUTED: {len(members)} attested panel members "
            f"({', '.join(members)}); per-member scores are not part of this record, so "
            "inter-rater agreement cannot be derived here and no model may substitute for it"
        )
        basis = "PANEL_MULTI_MEMBER"
    elif juror["kind"] == "PANEL":
        confidence = None
        basis = "PANEL_SINGLE_MEMBER"
    else:
        confidence = None
        basis = "SINGLE_JUROR"
    return {
        "jury_record_id": document["jury_record_id"],
        "subject_ref": document["subject_ref"],
        "artifact_sha256": document["artifact_sha256"],
        "verdict": document["verdict"],
        "juror_kind": juror["kind"],
        "juror_count": len(members) if juror["kind"] == "PANEL" else 1,
        "weighted_total": total,
        "scale_ceiling": SCORE_CEILING,
        "criteria": breakdown,
        "confidence": confidence,
        "confidence_basis": basis,
    }


def validate_against_subject(verdict, subject) -> dict:
    """The verdict's artifact digest must equal the subject's digest exactly."""
    document = record_verdict(verdict)
    if isinstance(subject, Mapping):
        candidate = subject.get("artifact_sha256", subject.get("sha256"))
    else:
        candidate = subject
    if candidate is None:
        raise AssuranceError(
            "the subject declares no artifact_sha256, so the verdict cannot be bound to it; "
            "failing closed"
        )
    expected = require_digest(candidate, "subject.artifact_sha256")
    bound = document["artifact_sha256"]
    if bound != expected:
        raise AssuranceError(
            f"this verdict is bound to {bound} and cannot be reused for {expected}; a jury "
            "verdict is never transferable across artifacts, and 'same design, close enough' "
            "is not acceptance"
        )
    return document


def resign_kind(verdict, kind: str):
    """Test/audit helper: return a copy with a different ``kind`` marker."""
    if not isinstance(verdict, JuryVerdict):
        raise AssuranceError("resign_kind requires a JuryVerdict")
    return replace(verdict, kind=kind)
