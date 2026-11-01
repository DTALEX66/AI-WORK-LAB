"""Mutation policy (WL-350 / ch 31): the M1..M5 mutation-level gate.

ch 31 classifies every self-modification by how dangerous it is and
maps each class to a disposition::

    M1 Prompt          -> auto-experiment allowed
    M2 Skill           -> auto-experiment allowed
    M3 Workflow        -> must run inside a sandbox
    M4 Tool / Runtime  -> Security + Eval + Approval
    M5 Governance      -> the agent may NOT modify it AND self-accept it

The last row is the strongest: governance is the layer that decides who
may promote; an agent that could rewrite it and then sign off on that
rewrite would defeat the entire ch 29 independent gate.  M5 therefore
requires an authority OTHER than the modifying agent to accept it.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


class MutationLevel:
    M1_PROMPT = "M1"
    M2_SKILL = "M2"
    M3_WORKFLOW = "M3"
    M4_TOOL_RUNTIME = "M4"
    M5_GOVERNANCE = "M5"

    ALL = (M1_PROMPT, M2_SKILL, M3_WORKFLOW, M4_TOOL_RUNTIME, M5_GOVERNANCE)
    _MEMBERS = frozenset(ALL)

    @classmethod
    def is_valid(cls, lv: str) -> bool:
        return lv in cls._MEMBERS


class Disposition:
    AUTO_EXPERIMENT = "auto_experiment"
    SANDBOX = "sandbox"
    SECURITY_EVAL_APPROVAL = "security_eval_approval"
    INDEPENDENT_APPROVAL = "independent_approval"

    # ch 31's fixed mapping — this IS the policy, tested for drift.
    POLICY: Dict[str, str] = {
        MutationLevel.M1_PROMPT: AUTO_EXPERIMENT,
        MutationLevel.M2_SKILL: AUTO_EXPERIMENT,
        MutationLevel.M3_WORKFLOW: SANDBOX,
        MutationLevel.M4_TOOL_RUNTIME: SECURITY_EVAL_APPROVAL,
        MutationLevel.M5_GOVERNANCE: INDEPENDENT_APPROVAL,
    }


@dataclass
class MutationDecision:
    level: str
    disposition: str
    allowed: bool
    reasons: List[str] = field(default_factory=list)

    def receipt_sha256(self) -> str:
        import hashlib
        payload = json.dumps(
            {"level": self.level, "d": self.disposition,
             "allowed": self.allowed, "reasons": self.reasons},
            sort_keys=True, ensure_ascii=False).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()

    def to_dict(self) -> Dict[str, Any]:
        return {"level": self.level, "disposition": self.disposition,
                "allowed": self.allowed, "reasons": self.reasons,
                "receipt_sha256": self.receipt_sha256()}


class MutationGate:
    """Decides whether a mutation at a given level may proceed, given the
    context the caller supplies.  Deterministic and receipt-hashed."""

    SCHEMA = "work-lab/mutation-policy/v1"

    def __init__(self, modifier: str = "agent",
                 independent_acceptor: str = "work-lab-governance") -> None:
        # who made the change vs. who may accept an M5 change
        self.modifier = modifier
        self.independent_acceptor = independent_acceptor

    def decide(self, level: str,
               in_sandbox: bool = False,
               security_passed: bool = False,
               eval_passed: bool = False,
               approval: Optional[Dict[str, Any]] = None,
               accepted_by: Optional[str] = None) -> MutationDecision:
        if not MutationLevel.is_valid(level):
            return MutationDecision(level, Disposition.INDEPENDENT_APPROVAL,
                                    False, [f"unknown level {level!r}"])
        disposition = Disposition.POLICY[level]
        reasons: List[str] = []
        allowed = True

        if disposition == Disposition.AUTO_EXPERIMENT:
            reasons.append("M1/M2 auto-experiment is permitted")
        elif disposition == Disposition.SANDBOX:
            if in_sandbox:
                reasons.append("M3 workflow mutation ran in a sandbox")
            else:
                allowed = False
                reasons.append("M3 workflow mutation must run in a sandbox")
        elif disposition == Disposition.SECURITY_EVAL_APPROVAL:
            if not security_passed:
                allowed = False
                reasons.append("M4 needs a passing Security check")
            if not eval_passed:
                allowed = False
                reasons.append("M4 needs a passing Eval check")
            if not (approval and approval.get("granted")):
                allowed = False
                reasons.append("M4 needs an explicit approval record")
            if allowed:
                reasons.append("M4 tool/runtime mutation cleared "
                               "Security+Eval+Approval")
        elif disposition == Disposition.INDEPENDENT_APPROVAL:
            # ch 31's strongest rule: the agent may not self-accept M5.
            if accepted_by is None:
                allowed = False
                reasons.append("M5 governance change needs an acceptor")
            elif accepted_by == self.modifier:
                allowed = False
                reasons.append("M5: the modifying agent may not self-accept "
                               "a governance change (ch 31)")
            elif accepted_by != self.independent_acceptor:
                allowed = False
                reasons.append(f"M5: acceptor {accepted_by!r} is not the "
                               f"independent authority {self.independent_acceptor!r}")
            else:
                reasons.append("M5 governance change accepted by the "
                               "independent authority")

        return MutationDecision(level, disposition, allowed, reasons)
