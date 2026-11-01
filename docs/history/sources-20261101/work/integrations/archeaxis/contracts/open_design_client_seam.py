"""Open Design client seam — WORK-LAB V2 three-project boundary.

Open Design is a CLIENT that WORK-LAB manages (the Open Design
USER_GLOBAL desired state): rules, skills, plugins, capability discovery,
workflow policy, adapter, software state.

DESIGN-LAB is a SEPARATE PROJECT that owns the design DOMAIN: design
knowledge, design prompt truth, design assets, generation strategy, design
quality system, Adobe domain logic. WORK-LAB neither collects nor manages
any of those (IGNORE), and it must not grow a design-capability owner.

This module is the single allowed surface for WORK-LAB's Open Design client
management. Anything that stores design prompt truth / assets / quality
inside WORK-LAB is a boundary violation caught by
scripts/ci/verify_three_project_boundary.py.

Authority: .project/governance/three-project-boundary.json
Field ownership: config/config-ownership.json (adapter "open-design",
  external project "design-lab-project").
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class OpenDesignClientState:
    """WORK-LAB-managed Open Design client desired state (MANAGE, apply_supported=false
    until a reviewed adapter + stable official interface exist)."""
    rules: List[str] = field(default_factory=list)
    skills: List[str] = field(default_factory=list)
    plugins: List[str] = field(default_factory=list)
    workflow_policy: Dict[str, Any] = field(default_factory=dict)
    capability_map: Dict[str, Any] = field(default_factory=dict)

    def applies_now(self) -> bool:
        # apply_supported=false today: managed, not yet applied.
        return False

    def design_capability_forbidden_here(self) -> bool:
        # design capability (models/tools/params/assets/specs/quality gates)
        # belongs to DESIGN-LAB — never stored in WORK-LAB.
        return True


__all__ = ["OpenDesignClientState"]
