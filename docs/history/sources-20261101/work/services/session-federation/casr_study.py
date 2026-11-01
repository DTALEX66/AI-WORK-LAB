"""CASR architecture study (WL-P1-100 / ch 14): REFERENCE_ONLY by design.

ch 14 names one research target — the external
``cross_agent_session_resumer`` — and six capability dimensions to study::

    Canonical IR / Reader-Writer / read-back verification /
    native writer / round trip / loss accounting

and one hard constraint that decides the deliverable's SHAPE: the
upstream project's license carries an extra rider, so its core code MUST
NOT be copied into the WORK-LAB core.  The status is REFERENCE_ONLY.

That makes this a STUDY, not an integration — the same shape as the
Beads POC (ch 22): assess a capability against what WORK-LAB already owns,
record the mapping, and reach a verdict without vendoring the other side's
code.  The conclusion a correct study must reach is structural, not
optimistic::

    REFERENCE_ONLY — keep the design as reference material; do NOT port
    the upstream core (license rider); reuse WORK-LAB's own
    session-federation plane for the same capability where it already
    covers it.

Each of the six dimensions is scored against WORK-LAB's existing
session-federation components (canonical session, portability levels,
L1 handoff, loss report, ACP facade), and the receipt carries a
deterministic hash so the study is reproducible and citable.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional


class CapabilityDimension:
    """The six ch 14 study dimensions."""

    CANONICAL_IR = "canonical_ir"
    READER_WRITER = "reader_writer"
    READ_BACK_VERIFICATION = "read_back_verification"
    NATIVE_WRITER = "native_writer"
    ROUND_TRIP = "round_trip"
    LOSS_ACCOUNTING = "loss_accounting"

    ALL = (CANONICAL_IR, READER_WRITER, READ_BACK_VERIFICATION,
           NATIVE_WRITER, ROUND_TRIP, LOSS_ACCOUNTING)
    _MEMBERS = frozenset(ALL)


# Which WORK-LAB session-federation component already covers a dimension.
# This is the reuse-mapping the study is for: it proves WORK-LAB does not
# need the upstream's code to have most of the capability already.
WORKLAB_COVERAGE: Dict[str, str] = {
    CapabilityDimension.CANONICAL_IR:
        "services/session-federation/canonical.py (CanonicalSession v1)",
    CapabilityDimension.READER_WRITER:
        "hermes/codex/dsh providers (L0/L1 discover + normalise)",
    CapabilityDimension.READ_BACK_VERIFICATION:
        "canonical.content_digest + gate integrity checks",
    CapabilityDimension.NATIVE_WRITER:
        "portability level L3 native-resume (NOT overclaimed)",
    CapabilityDimension.ROUND_TRIP:
        "continues.py build_capsule_doc (capsule round-trip)",
    CapabilityDimension.LOSS_ACCOUNTING:
        "canonical.LossReport + gate c-retention check",
}


class PortabilityAssessment:
    """How much of a dimension WORK-LAB already has.

    FULL      — WORK-LAB already has this capability on its own plane.
    PARTIAL   — WORK-LAB has a partial/level-limited form (e.g. L1 not L3).
    GAP       — WORK-LAB does not have it yet; reference only, do not port.
    """

    FULL = "full"
    PARTIAL = "partial"
    GAP = "gap"

    _MEMBERS = frozenset({FULL, PARTIAL, GAP})

    @classmethod
    def is_valid(cls, a: str) -> bool:
        return a in cls._MEMBERS


@dataclass
class DimensionStudy:
    dimension: str
    upstream_notes: str          # what the upstream project is reported to do
    worklab_coverage: str        # which WORK-LAB component covers it
    assessment: str             # FULL / PARTIAL / GAP
    reference_only: bool        # always True under ch 14's license rider

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class CasrStudy:
    target: str
    status: str                 # always REFERENCE_ONLY
    license_rider: str
    dimensions: List[DimensionStudy] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {"target": self.target, "status": self.status,
                "license_rider": self.license_rider,
                "dimensions": [d.to_dict() for d in self.dimensions]}

    def receipt_sha256(self) -> str:
        import hashlib
        payload = json.dumps(self.to_dict(), sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class CasrStudyBuilder:
    """Builds the REFERENCE_ONLY study.  It never imports, copies, or
    writes any upstream ``cross_agent_session_resumer`` source; it only
    records the design mapping and the license-rider verdict."""

    SCHEMA = "work-lab/casr-study/v1"
    TARGET = "cross_agent_session_resumer"
    STATUS = "REFERENCE_ONLY"
    LICENSE_RIDER = ("upstream license carries an extra rider; core code must "
                     "not be vendored into the WORK-LAB core (ch 14)")

    def __init__(self,
                 upstream_notes: Optional[Dict[str, str]] = None) -> None:
        # caller-supplied notes per dimension; default to a conservative
        # reference-only note so the study is complete without external data
        self._notes = upstream_notes or {}

    def build(self,
              assessments: Optional[Dict[str, str]] = None) -> CasrStudy:
        # default assessment: WORK-LAB owns its session plane, so most
        # dimensions are FULL or PARTIAL on our own components; we still
        # mark each dimension reference-only because we are not porting
        # the upstream code, only mapping our coverage to it.
        default_assess = {
            CapabilityDimension.CANONICAL_IR: PortabilityAssessment.FULL,
            CapabilityDimension.READER_WRITER: PortabilityAssessment.FULL,
            CapabilityDimension.READ_BACK_VERIFICATION: PortabilityAssessment.FULL,
            CapabilityDimension.NATIVE_WRITER: PortabilityAssessment.PARTIAL,
            CapabilityDimension.ROUND_TRIP: PortabilityAssessment.PARTIAL,
            CapabilityDimension.LOSS_ACCOUNTING: PortabilityAssessment.FULL,
        }
        assess = dict(default_assess)
        if assessments:
            for k, v in assessments.items():
                if not PortabilityAssessment.is_valid(v):
                    raise ValueError(f"invalid assessment {v!r} for {k!r}")
                assess[k] = v
        dims = [
            DimensionStudy(
                dimension=d,
                upstream_notes=self._notes.get(d, "reference-only; not ported"),
                worklab_coverage=WORKLAB_COVERAGE.get(d, "no direct component"),
                assessment=assess.get(d, PortabilityAssessment.GAP),
                reference_only=True,
            ) for d in CapabilityDimension.ALL
        ]
        return CasrStudy(self.TARGET, self.STATUS, self.LICENSE_RIDER, dims)

    # -- the verdict the study must reach ---------------------------------
    @staticmethod
    def verdict(study: CasrStudy) -> Dict[str, Any]:
        """The load-bearing conclusion: REFERENCE_ONLY, and the count of
        dimensions WORK-LAB already covers on its own plane (i.e. where
        porting the upstream code adds nothing)."""
        covered = [d.dimension for d in study.dimensions
                   if d.assessment in (PortabilityAssessment.FULL,
                                       PortabilityAssessment.PARTIAL)]
        gaps = [d.dimension for d in study.dimensions
                if d.assessment == PortabilityAssessment.GAP]
        return {
            "status": study.status,
            "port_upstream_core": False,
            "reason": study.license_rider,
            "worklab_already_covers": covered,
            "gaps_reference_only": gaps,
            "reuse": "WORK-LAB session-federation plane",
        }


def full_study_receipt(study: CasrStudy) -> Dict[str, Any]:
    """Study + verdict + deterministic receipt, serialisable."""
    v = CasrStudyBuilder.verdict(study)
    out = study.to_dict()
    out["verdict"] = v
    out["receipt_sha256"] = study.receipt_sha256()
    return out
