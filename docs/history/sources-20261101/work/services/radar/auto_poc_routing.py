"""Auto POC routing (WL-390): route a scored candidate to its disposition.

Given the ch 33 tiers this module maps each scored candidate to a
disposition and — for the ones that warrant hands-on work — the exact
next gate that must run before anything lands.  The routing is the seam
between the Radar Plane and the Security / Evolution planes:

* P0_AUDIT  (85+)   -> run the full audit (skill / extension pipeline)
                       before any install; WORK-LAB holds the verdict.
* P1_POC    (70-84) -> build a POC behind its provider interface; the
                       external artifact stays register-and-recipe.
* REFERENCE (55-69) -> record it as a reference; no active work.
* ARCHIVE   (<55)   -> archive; revisit only on a future radar sweep.

Two load-bearing guards:

* a P0_AUDIT candidate CANNOT skip the audit and be installed directly —
  routing to "install" for an unaudited candidate is a structural error
  (ch 41: the acceptance authority is WORK-LAB's gate, not the radar).
* routing is deterministic + receipt-hashed, and it never invents a
  candidate's capability the metadata did not carry.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set


class Disposition:
    AUDIT = "audit"
    POC = "poc"
    REFERENCE = "reference"
    ARCHIVE = "archive"

    # ch 33 tier -> disposition (this mapping IS the routing policy).
    TIER_TO_DISPOSITION = {
        "P0_AUDIT": AUDIT,
        "P1_POC": POC,
        "REFERENCE": REFERENCE,
        "ARCHIVE": ARCHIVE,
    }


class RoutingError(Exception):
    """Raised when a routing action would bypass a required gate."""


@dataclass
class RouteDecision:
    candidate_key: str
    tier: str
    disposition: str
    next_gate: str                  # the gate to run next (or "none")
    requires_work_lab: bool          # True when a WORK-LAB gate must pass
    reasons: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {"candidate_key": self.candidate_key, "tier": self.tier,
                "disposition": self.disposition, "next_gate": self.next_gate,
                "requires_work_lab": self.requires_work_lab,
                "reasons": self.reasons}

    def receipt_sha256(self) -> str:
        import hashlib
        payload = json.dumps(self.to_dict(), sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class POCRouter:
    """Routes a scored candidate (or a receipt) to its disposition."""

    SCHEMA = "work-lab/auto-poc-routing/v1"

    def __init__(self, auto_poc_allowlist: Optional[Set[str]] = None) -> None:
        # even a P0_AUDIT candidate lands only after its audit gate; the
        # allowlist is for POCs that WORK-LAB has already cleared to build.
        self.auto_poc_allowlist = set(auto_poc_allowlist or set())

    def route(self, receipt: Any) -> RouteDecision:
        """Route from a scoring receipt (total / tier / candidate_key)."""
        tier = receipt.tier
        key = receipt.candidate_key
        disposition = Disposition.TIER_TO_DISPOSITION.get(tier)
        if disposition is None:
            raise RoutingError(f"unknown tier {tier!r} cannot be routed")
        return self._decide(key, tier, disposition)

    def route_candidate(self, total: float, key: str) -> RouteDecision:
        """Route from a raw total score.  The ch 33 tier thresholds are
        mirrored HERE (85/70/55) rather than imported: services/ modules
        are loaded by spec without an __init__.py, so a hard
        `from services.radar.radar_scoring import Tier` would resolve only
        when that sibling is pre-registered.  Mirroring keeps the router
        self-contained and the threshold drift is asserted in the tests.
        """
        if total >= 85:
            tier = "P0_AUDIT"
        elif total >= 70:
            tier = "P1_POC"
        elif total >= 55:
            tier = "REFERENCE"
        else:
            tier = "ARCHIVE"
        disposition = Disposition.TIER_TO_DISPOSITION.get(tier)
        if disposition is None:
            raise RoutingError(f"unknown tier {tier!r}")
        return self._decide(key, tier, disposition)

    def _decide(self, key: str, tier: str,
                disposition: str) -> RouteDecision:
        if disposition == Disposition.AUDIT:
            # ch 41: an unaudited P0 candidate must NOT be installed.
            # the next gate is the audit; WORK-LAB holds the verdict.
            return RouteDecision(key, tier, disposition,
                                 next_gate="skillspector-gate",
                                 requires_work_lab=True,
                                 reasons=["P0_AUDIT: run the audit gate "
                                          "before any install"])
        if disposition == Disposition.POC:
            # build a POC behind its provider interface; cleared POCs are
            # allowed to proceed, others still stop at the POC gate.
            cleared = key in self.auto_poc_allowlist
            return RouteDecision(key, tier, disposition,
                                 next_gate="poc-provider-gate" if not cleared
                                 else "register-and-recipe",
                                 requires_work_lab=not cleared,
                                 reasons=([f"P1_POC build cleared for {key}"]
                                          if cleared
                                          else ["P1_POC: build behind the "
                                               "provider interface"]))
        if disposition == Disposition.REFERENCE:
            return RouteDecision(key, tier, disposition,
                                 next_gate="none", requires_work_lab=False,
                                 reasons=["REFERENCE: record, no active work"])
        return RouteDecision(key, tier, disposition,
                             next_gate="none", requires_work_lab=False,
                             reasons=["ARCHIVE: revisit on a future sweep"])

    def assert_no_install_bypass(self, receipt: Any,
                                 audited: bool = False) -> None:
        """The structural guard: a P0_AUDIT candidate that has NOT been
        audited must not be marked installable.  Raises RoutingError.
        """
        decision = self.route(receipt)
        if decision.disposition == Disposition.AUDIT and not audited:
            raise RoutingError(
                f"{receipt.candidate_key} is a P0_AUDIT candidate and "
                "has not been audited; install is forbidden (ch 41)")
