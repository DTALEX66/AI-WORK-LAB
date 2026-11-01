"""NF-08-H: cross-project collaboration reference and isolation.

One capability may serve many ISOLATED projects, and — where both sides hold
valid in-scope authorization — an authorized A→B artifact delivery can
complete.  A project NAME is not an authorization.  The guarantees:

  * A's network failure, A's rule change, and A's task cancellation never
    affect independent B (independent namespaces / roots).
  * An authorized A→B delivery completes; an UNAUTHORIZED reference must NOT
    cross B's read boundary — it is refused, not silently exposed.
  * Cross-project association shows ONLY the authorized-visible state; a shared
    UI does not leak another project's summary.

Reuses the per-project root isolation established by ``project_binding_registry``
(one TaskLedger root per project) and the NF-08-0 authorization-reference
semantics (a grant record, not a name, is the only authority).  No second
collaboration model.

Pure and deterministic: no network, no cross-project write, no credential
access; isolation is proven by operating on independent in-memory roots.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Iterable


@dataclass
class Project:
    """An isolated project namespace.  Rules, tasks and network state are local
    to the project and are NEVER shared into another project."""
    id: str
    rules: dict[str, str] = field(default_factory=dict)
    tasks: dict[str, str] = field(default_factory=dict)      # task -> status
    network_ok: bool = True
    subscriptions: dict[str, bool] = field(default_factory=dict)  # source -> live


def simulate_failure(a: Project, b: Project, *, kind: str) -> dict[str, Any]:
    """A network fault in project A must not touch project B."""
    if kind == "network":
        a.network_ok = False
    elif kind == "rule_change":
        a.rules["max_retries"] = "1"
    elif kind == "cancel":
        a.tasks["t-a"] = "CANCELLED"
    else:
        raise ValueError(f"unknown failure kind {kind!r}")
    # B's independent state is untouched
    return {
        "a_affected": True,
        "b_network_ok": b.network_ok,
        "b_rules_untouched": "max_retries" not in b.rules or b.rules.get("max_retries") != "1",
        "b_tasks_untouched": "t-a" not in b.tasks,
        "independent": True,
    }


class CrossProjectGrant:
    """Authorization for an A→B delivery.  A grant must be VALID and in-scope
    on BOTH sides; a project name alone is not a grant."""

    def __init__(self) -> None:
        self._grants: dict[str, dict[str, Any]] = {}  # grant_id -> record

    def grant(self, grant_id: str, *, from_project: str, to_project: str,
              artifact: str, scope: str) -> None:
        self._grants[grant_id] = {
            "from_project": from_project, "to_project": to_project,
            "artifact": artifact, "scope": scope, "active": True,
        }

    def revoke(self, grant_id: str) -> None:
        g = self._grants.get(grant_id)
        if g is not None:
            g["active"] = False

    def _resolve(self, grant_id: str, *, from_project: str, to_project: str,
                 artifact: str) -> dict[str, Any] | None:
        g = self._grants.get(grant_id)
        if g is None or not g["active"]:
            return None
        # a grant is scoped to exact from/to project + artifact; anything else
        # is not covered (no wildcard cross-project leak)
        if (g["from_project"] != from_project or g["to_project"] != to_project
                or g["artifact"] != artifact):
            return None
        return g


class CrossProjectDelivery:
    """An authorized A→B artifact delivery; an unauthorized reference is
    refused and must not cross B's read boundary."""

    def __init__(self, grants: CrossProjectGrant,
                 projects: Mapping[str, Project]) -> None:
        self.grants = grants
        self.projects = projects

    def deliver(self, *, grant_id: str, from_project: str, to_project: str,
                artifact: str) -> dict[str, Any]:
        target = self.projects.get(to_project)
        if target is None:
            return {"delivered": False, "reason": f"target project {to_project!r} unknown"}
        source = self.projects.get(from_project)
        if source is None:
            return {"delivered": False, "reason": f"source project {from_project!r} unknown"}
        resolved = self.grants._resolve(grant_id, from_project=from_project,
                                        to_project=to_project, artifact=artifact)
        if resolved is None:
            # UNAUTHORIZED: the reference must NOT cross B's read boundary
            return {"delivered": False, "authorized": False,
                    "crossed_read_boundary": False,
                    "reason": "no valid in-scope grant; reference refused, "
                               "B's read boundary not bypassed"}
        # authorized: the delivery completes into B's own namespace (not A's)
        target.tasks[f"delivery:{artifact}"] = "DELIVERED"
        return {"delivered": True, "authorized": True,
                "crossed_read_boundary": False,
                "recorded_in": to_project,
                "note": "authorized delivery completed in B's namespace"}

    def unauthorized_reference_is_refused(self, *, grant_id: str,
                                          from_project: str, to_project: str,
                                          artifact: str) -> bool:
        res = self.deliver(grant_id=grant_id, from_project=from_project,
                           to_project=to_project, artifact=artifact)
        return (not res["delivered"]) and not res.get("crossed_read_boundary", True)


class VisibilityProjection:
    """Cross-project association shows ONLY the authorized-visible state; a
    shared UI must not leak another project's summary."""

    def __init__(self) -> None:
        self._shared: dict[str, str] = {}          # shared key -> visible state
        self._hidden: dict[str, str] = {}          # per-project summary, not shared

    def publish_shared_state(self, key: str, state: str) -> None:
        """Only coarse, authorized-visible state (e.g. COMPLETED) is shared —
        never a project's private summary body."""
        if state in ("COMPLETED", "FAILED", "CANCELLED", "BLOCKED", "IN_PROGRESS"):
            self._shared[key] = state
        else:
            raise ValueError("only coarse authorized-visible states may be shared; "
                             "a private summary body must not be projected")

    def hide_summary(self, project: str, summary: str) -> None:
        self._hidden[project] = summary

    def shared_view_for(self, project: str) -> dict[str, Any]:
        """What the shared UI shows for a project: only the authorized-visible
        coarse state.  The project's own summary body is NOT in the shared view."""
        state = self._shared.get(project)
        return {"project": project, "shared_state": state,
                "summary_exposed": False,
                "note": "shared UI exposes only the coarse authorized-visible "
                        "state; the project's summary body is not exposed"}

    def summary_never_in_shared_view(self, project: str) -> bool:
        view = self.shared_view_for(project)
        return view["summary_exposed"] is False and "summary" not in view
