"""Permission Policy Gate (WL-190): executor can never be the final authority.

Ch 18 mandates the chain::

    Executor  ->  WORK-LAB Policy  ->  Risk  ->  Human Gate (if required)
            ->  allow / deny

and the one hard rule: *the executor itself is never the final authorising
source*.  This module encodes that as a pure decision function:

* classify the requested *action kind* (filesystem / shell / network /
  credential / destructive / external mutation) and its *risk*;
* apply the WORK-LAB policy (scope allow-lists, risk thresholds);
* return a typed verdict ``Decision`` that says either ``ALLOWED`` (auto) or
  ``NEEDS_HUMAN`` (a human gate must sign off) — never a bare executor "yes".

The gate is policy-driven: the caller supplies a :class:`Policy` describing
what is in-scope and which risk tiers require a human.  The same gate that
protects a filesystem write protects a credential read; the distinction is
the *policy*, not the executor.

Loading convention mirrors the rest of services/: no package ``__init__.py``;
the Task Protocol base is loaded through a stable ``sys.modules`` name.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Iterable, Mapping

import importlib.util as _ilu

__all__ = [
    "ActionKind", "RiskTier", "Decision", "DecisionStatus", "Policy",
    "PermissionGate",
]


class ActionKind(str, Enum):
    FILESYSTEM = "filesystem"
    SHELL = "shell"
    NETWORK = "network"
    CREDENTIAL = "credential"
    DESTRUCTIVE = "destructive"
    EXTERNAL_MUTATION = "external_mutation"


class RiskTier(int, Enum):
    """Ordered risk levels.  Higher = more likely to need a human gate."""
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4


class DecisionStatus(str, Enum):
    ALLOWED = "allowed"              # auto-approved by policy
    NEEDS_HUMAN = "needs_human"     # a human gate must sign off
    DENIED = "denied"               # out of policy scope outright


@dataclass
class Policy:
    """The WORK-LAB policy a gate enforces (caller-supplied, not the executor).

    ``scope`` — action kinds this authority is allowed to gate at all.  A
    kind not in scope is DENIED outright (the executor cannot self-authorise
    it).
    ``human_gate_from`` — risk tier at and above which a human gate is
    required even though the action is in scope.  Below it, policy auto-
    allows.
    ``forbidden_paths`` / ``forbidden_hosts`` — explicit denials that
    override any tier.
    """
    scope: frozenset[ActionKind] = frozenset(ActionKind)
    human_gate_from: RiskTier = RiskTier.HIGH
    forbidden_paths: tuple[str, ...] = ()
    forbidden_hosts: tuple[str, ...] = ()


@dataclass
class Decision:
    kind: ActionKind
    risk: RiskTier
    status: DecisionStatus
    reason: str
    executor: str = ""
    target: str = ""
    gate_required: bool = False
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind.value,
            "risk": self.risk.name,
            "status": self.status.value,
            "reason": self.reason,
            "executor": self.executor,
            "target": self.target,
            "gate_required": self.gate_required,
            "details": dict(self.details),
        }


class PermissionGate:
    """Evaluates one requested action against a WORK-LAB policy.

    The executor names what it wants to do; the *policy* decides.  The
    resulting :class:`Decision` is what any downstream step may rely on —
    and only ``DecisionStatus.ALLOWED`` with ``gate_required`` False is
    auto-proceedable.  Everything else either needs a human signature or is
    denied.
    """

    def __init__(self, policy: Policy | None = None) -> None:
        self.policy = policy or Policy()

    # -- risk inference --------------------------------------------------
    def assess_risk(self, kind: ActionKind | str, *, target: str = "",
                    scope: str | None = None) -> RiskTier:
        """Heuristic risk for a *kind* of action in the given *scope*.

        The scope string narrows the kind: e.g. a filesystem write under the
        work-lab root is LOW, but a write to a protected path is CRITICAL.
        Deletion / destructive kinds are never LOW.
        """
        k = ActionKind(kind) if not isinstance(kind, ActionKind) else kind
        base = {
            ActionKind.FILESYSTEM: RiskTier.LOW,
            ActionKind.SHELL: RiskTier.MEDIUM,
            ActionKind.NETWORK: RiskTier.MEDIUM,
            ActionKind.CREDENTIAL: RiskTier.HIGH,
            ActionKind.DESTRUCTIVE: RiskTier.HIGH,
            ActionKind.EXTERNAL_MUTATION: RiskTier.HIGH,
        }[k]
        # a destructive/external-mutation that also touches something
        # irreversible escalates to CRITICAL
        if k in (ActionKind.DESTRUCTIVE, ActionKind.EXTERNAL_MUTATION):
            if scope and ("delete" in scope.lower() or "drop" in scope.lower()
                           or "rm" in scope.lower()):
                return RiskTier.CRITICAL
            return RiskTier.HIGH
        # filesystem: a protected target escalates
        if k is ActionKind.FILESYSTEM and target:
            low = target.lower()
            if any(f in low for f in (".env", "credential", "secret", "auth")):
                return RiskTier.CRITICAL
        return base

    # -- the decision ----------------------------------------------------
    def evaluate(
        self,
        kind: ActionKind | str,
        *,
        target: str = "",
        scope: str | None = None,
        executor: str = "",
    ) -> Decision:
        k = ActionKind(kind) if not isinstance(kind, ActionKind) else kind
        risk = self.assess_risk(k, target=target, scope=scope)
        p = self.policy

        # 1. kind must be in policy scope at all, else the executor cannot
        #    self-authorise it (hard rule of ch 18).
        if k not in p.scope:
            return Decision(k, risk, DecisionStatus.DENIED,
                            reason="action kind outside WORK-LAB policy scope",
                            executor=executor, target=target, gate_required=False,
                            details={"in_scope": False})
        # 2. explicit forbids override everything.
        if target and (target in p.forbidden_paths
                       or any(target.startswith(f) for f in p.forbidden_paths)):
            return Decision(k, risk, DecisionStatus.DENIED,
                            reason="target is on the forbidden list",
                            executor=executor, target=target, gate_required=False,
                            details={"forbidden": target})
        if scope and scope in p.forbidden_hosts:
            return Decision(k, risk, DecisionStatus.DENIED,
                            reason="host is on the forbidden list",
                            executor=executor, target=target,
                            gate_required=False, details={"forbidden_host": scope})
        # 3. risk at/above the human threshold -> a human gate is required.
        if risk.value >= p.human_gate_from.value:
            return Decision(k, risk, DecisionStatus.NEEDS_HUMAN,
                            reason=f"risk {risk.name} >= policy threshold {p.human_gate_from.name}",
                            executor=executor, target=target, gate_required=True,
                            details={"auto_allow_threshold": p.human_gate_from.name})
        # 4. otherwise the policy auto-allows.
        return Decision(k, risk, DecisionStatus.ALLOWED,
                        reason=f"risk {risk.name} below human-gate threshold",
                        executor=executor, target=target, gate_required=False,
                        details={"auto_allowed": True})

    # -- convenience -----------------------------------------------------
    def allow_all(self, kinds: Iterable[ActionKind | str]) -> Policy:
        """A permissive scope (useful for trusted local dev sandboxes)."""
        return Policy(
            scope=frozenset(ActionKind(k) if not isinstance(k, ActionKind) else k
                            for k in kinds),
            human_gate_from=RiskTier.CRITICAL,
        )

    def readonly(self) -> Policy:
        """Filesystem-only authority: ordinary targets auto-allow, sensitive
        targets (secret/.env/auth) require a human gate, everything outside
        the filesystem class is denied.  (Read-vs-write is not modelled on
        the target string yet; a plain filesystem action is LOW-risk, so with
        the MEDIUM threshold it auto-passes while escalated targets need a
        signature.)"""
        return Policy(
            scope=frozenset({ActionKind.FILESYSTEM}),
            human_gate_from=RiskTier.MEDIUM,  # LOW auto, MEDIUM+ human-gated
        )


def gate_for_policy(policy: Mapping[str, Any]) -> PermissionGate:
    """Build a gate from a plain mapping (config files, JSON task contracts)."""
    scope = frozenset(
        ActionKind(k) if not isinstance(k, ActionKind) else k
        for k in policy.get("scope", [a.value for a in ActionKind])
    )
    hgf = policy.get("human_gate_from", RiskTier.HIGH)
    human_gate_from = _resolve_risk_tier(hgf)
    return PermissionGate(Policy(
        scope=scope,
        human_gate_from=human_gate_from,
        forbidden_paths=tuple(policy.get("forbidden_paths", ())),
        forbidden_hosts=tuple(policy.get("forbidden_hosts", ())),
    ))


def _resolve_risk_tier(value: Any) -> RiskTier:
    """Accept a RiskTier member, its int value, or its upper-case name."""
    if isinstance(value, RiskTier):
        return value
    if isinstance(value, int):
        return RiskTier(value)
    name = str(value).strip().upper()
    try:
        return RiskTier[name]
    except KeyError:
        return RiskTier(int(value))
