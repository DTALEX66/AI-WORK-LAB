"""Execution anchor / session lineage model (WLGM-040).

A session's *anchor project* must not drift just because the agent briefly
reads another repository. This module models:

- ``ExecutionAnchor``: the stable project an execution belongs to;
- ``currentWorkingArea``: where the agent is working right now;
- ``visitedRepositories``: repositories touched transiently (never migrates the
  anchor);
- lineage: ``sessionLineage`` keeps the chain across compression/resume/fork so
  a lost cwd degrades path quality instead of reassigning the project.

Pure data model + switch policy: no IO.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from product_project import ResolutionState


class AnchorState(str, Enum):
    ANCHORED = "ANCHORED"
    UNANCHORED = "UNANCHORED"
    CONFLICT = "PROJECT_IDENTITY_CONFLICT"


@dataclass
class VisitedRepository:
    repository_id: str
    visited_at: str
    evidence_ref: str = ""


@dataclass
class ExecutionAnchor:
    """Stable project anchor for one agent execution."""

    execution_id: str
    anchor_project_id: str | None = None
    anchor_state: AnchorState = AnchorState.UNANCHORED
    current_working_area: str | None = None
    lineage: list[str] = field(default_factory=list)  # ancestor session/execution ids
    visited_repositories: list[VisitedRepository] = field(default_factory=list)
    last_switch_evidence: str = ""

    def anchor(self, project_id: str, evidence: str) -> None:
        self.anchor_project_id = project_id
        self.anchor_state = AnchorState.ANCHORED
        self.last_switch_evidence = evidence

    def record_visit(self, repository_id: str, visited_at: str, evidence_ref: str = "") -> None:
        """A transient read only updates visited; it never migrates the anchor."""
        for visit in self.visited_repositories:
            if visit.repository_id == repository_id:
                visit.visited_at = visited_at
                return
        self.visited_repositories.append(VisitedRepository(repository_id, visited_at, evidence_ref))

    def switch_project(self, project_id: str, evidence: str, strong: bool) -> bool:
        """Switch the anchor ONLY on strong evidence (new task contract, agent
        native switch, explicit user action, or a new execution).

        Returns True when the anchor changed.
        """
        if not strong:
            return False
        if self.anchor_project_id == project_id:
            return False
        self.anchor_project_id = project_id
        self.anchor_state = AnchorState.ANCHORED
        self.last_switch_evidence = evidence
        self.visited_repositories.clear()
        return True

    def mark_conflict(self, evidence: str) -> None:
        self.anchor_state = AnchorState.CONFLICT
        self.last_switch_evidence = evidence

    def degrade_path_quality(self) -> None:
        """Compression/resume with a lost cwd must not unanchor the project;
        only the working area becomes unknown."""
        self.current_working_area = None

    def to_json(self) -> dict[str, Any]:
        return {
            "executionId": self.execution_id,
            "anchorProjectId": self.anchor_project_id,
            "anchorState": self.anchor_state.value,
            "currentWorkingArea": self.current_working_area,
            "lineage": list(self.lineage),
            "visitedRepositories": [
                {"repositoryId": v.repository_id, "visitedAt": v.visited_at, "evidenceRef": v.evidence_ref}
                for v in self.visited_repositories
            ],
            "lastSwitchEvidence": self.last_switch_evidence,
        }
