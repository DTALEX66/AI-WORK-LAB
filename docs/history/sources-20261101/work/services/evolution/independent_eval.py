"""Independent evolution gate (WL-340 / ch 29): the ch 29 acceptance path.

ch 29 FORBIDS the self-reinforcing loop::

    Penguin modifies -> Penguin evaluates -> Penguin promotes itself

and REQUIRES the full independent path::

    Baseline -> Candidate -> Independent benchmark -> Holdout ->
    Regression -> Security -> Cost -> Latency -> Evaluator ->
    WORK-LAB Promotion Gate

This module owns the verdict.  Two invariants are structural, not
discouraged-by-convention:

* the Evaluator that scores a candidate MUST be a different authority
  from the producer of that candidate (ch 29's whole point);
* promotion is the last stage and only WORK-LAB's promotion gate
  grants it — never the evaluator or the producer.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


class Axis:
    """The eight scored stages between Candidate and Evaluator."""

    INDEPENDENT_BENCHMARK = "independent_benchmark"
    HOLDOUT = "holdout"
    REGRESSION = "regression"
    SECURITY = "security"
    COST = "cost"
    LATENCY = "latency"

    ORDER = [INDEPENDENT_BENCHMARK, HOLDOUT, REGRESSION,
             SECURITY, COST, LATENCY]


class Verdict:
    PASS = "PASS"
    REJECT = "REJECT"
    PENDING = "PENDING"


class SelfEvaluationError(Exception):
    """Raised when the evaluator is the candidate's own producer."""


class PromotionAuthorityError(Exception):
    """Raised when a promotion is attempted by a non-WORK-LAB authority."""


@dataclass
class ScoredAxis:
    axis: str
    score: float                  # 0..1
    status: str                   # "ok" | "fail" | "unavailable"
    evidence: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {"axis": self.axis, "score": self.score, "status": self.status,
                "evidence": self.evidence}


@dataclass
class EvaluationReceipt:
    candidate_id: str
    evaluator: str
    producer: str
    axes: List[ScoredAxis] = field(default_factory=list)
    overall: str = Verdict.PENDING

    def to_dict(self) -> Dict[str, Any]:
        return {"candidate_id": self.candidate_id, "evaluator": self.evaluator,
                "producer": self.producer, "overall": self.overall,
                "axes": [a.to_dict() for a in self.axes]}

    def receipt_sha256(self) -> str:
        import hashlib
        payload = json.dumps(self.to_dict(), sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class IndependentEvaluator:
    """An authority that scores candidates.  Its name identifies it so the
    gate can enforce independence from the producer."""

    def __init__(self, name: str) -> None:
        self.name = name

    def score(self, candidate: Any, axis: str,
              baseline: Optional[Dict[str, Any]] = None) -> ScoredAxis:
        raise NotImplementedError


class Evaluator:
    """Deterministic baseline evaluator used when a live scorer is not
    provided.  Scores an axis from evidence the caller supplies so the
    pipeline stays end-to-end verifiable without a live model.

    Score of an axis is the caller-provided value when the evidence marks
    it available, else the axis is ``unavailable`` (honest) — the receipt
    then stays PENDING until every required axis has a number.
    """

    def __init__(self, name: str, evidence: Optional[Dict[str, Dict[str, Any]]] = None) -> None:
        self.name = name
        self._evidence = evidence or {}

    def score(self, candidate: Any, axis: str,
              baseline: Optional[Dict[str, Any]] = None) -> ScoredAxis:
        ev = self._evidence.get(axis)
        if ev is None:
            return ScoredAxis(axis, 0.0, "unavailable")
        return ScoredAxis(axis, float(ev.get("score", 0.0)),
                          ev.get("status", "ok"),
                          {k: v for k, v in ev.items() if k not in ("score", "status")})


class EvolutionGate:
    """Runs the ch 29 pipeline and owns the promotion verdict."""

    SCHEMA = "work-lab/evolution-gate/v1"

    def __init__(self,
                 evaluator: Optional[IndependentEvaluator] = None,
                 promotion_authority: str = "work-lab-evolution-gate") -> None:
        # the gate's own promotion authority is WORK-LAB, always
        self.promotion_authority = promotion_authority

    def _evaluator(self, evaluator: Optional[IndependentEvaluator]) -> IndependentEvaluator:
        if evaluator is not None:
            return evaluator
        return Evaluator("deterministic-baseline")

    def evaluate(self, candidate: Any,
                 baseline: Optional[Dict[str, Any]] = None,
                 evaluator: Optional[IndependentEvaluator] = None) -> EvaluationReceipt:
        ev = self._evaluator(evaluator)
        producer = getattr(candidate, "produced_by", "unknown")
        # ch 29: the evaluator must NOT be the candidate's own producer.
        if ev.name == producer:
            raise SelfEvaluationError(
                f"evaluator {ev.name!r} is the candidate's producer; "
                "ch 29 forbids self-evaluation")

        axes: List[ScoredAxis] = [ev.score(candidate, a, baseline)
                                  for a in Axis.ORDER]
        receipt = EvaluationReceipt(candidate.candidate_id, ev.name, producer,
                                    axes=axes)
        # evaluate() stops at the Evaluator stage: it records PASS when every
        # axis is available and at/above the pass bar, PENDING otherwise.
        # Promotion is a SEPARATE final stage (promote()) owned by the
        # WORK-LAB authority — the evaluator never promotes on its own.
        receipt.overall = Verdict.PASS if self._all_ok(axes) else Verdict.PENDING
        return receipt

    def promote(self, candidate: Any, receipt: EvaluationReceipt,
                by: str, allow_worklab: bool = False) -> str:
        """The final stage.  Only the WORK-LAB promotion authority may
        promote, and only when every axis is available and passing.

        A call whose ``by`` is not the WORK-LAB authority is rejected
        structurally — this is the last defence against the forbidden
        self-promotion loop.
        """
        if not allow_worklab:
            raise PromotionAuthorityError(
                "promotion is a WORK-LAB gate stage; direct "
                f"promotion by {by!r} is forbidden")
        if by != self.promotion_authority:
            raise PromotionAuthorityError(
                f"promotion by {by!r} is not the WORK-LAB authority "
                f"({self.promotion_authority!r})")
        # the evaluator may have recorded PENDING (some axis still
        # unavailable); only a fully-passing receipt may be promoted.
        return Verdict.PASS if self._all_ok(receipt.axes) else Verdict.REJECT

    @staticmethod
    def _all_ok(axes: List[ScoredAxis]) -> bool:
        """Every axis must be available (scored) and at or above its pass
        bar.  An unavailable axis keeps the receipt PENDING — it can never
        silently pass."""
        return all(a.status in ("ok",) for a in axes) and \
            all(a.score >= 0.5 for a in axes)
