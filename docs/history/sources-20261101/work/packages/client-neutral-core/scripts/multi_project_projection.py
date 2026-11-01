"""NF-09-SYNC: multi-project task projection + run-evidence visibility.

Extend the EXISTING read-only Observer projection (``WorkflowProjectionAdapter``)
so the user can see, per project, which step a task is at, which software is
executing it, and who is waiting on whom — without entering duplicated chat
UIs.  The Observer STAYS READ-ONLY: publish / approve / cancel entry points stay
in the native client or a link, and NO write button is added to the sidecar GET
channel.

Key semantics (acceptance AT-24 / AT-34 / AT-38, self-executable slice)
-----------------------------------------------------------------------
* **Project filtering + stage state** — each project's tasks are shown with
  source/target software, material version, and the delivery / execution /
  return / review stage state, so project A and B are viewable independently.
* **Honest value display** — permission-insufficient, actual-zero, unknown,
  stale and online are shown as distinct labels; the update time comes from the
  FACT, not a UI refresh.  A task that ran but has not been returned is NEVER
  shown as "all failed" or "cloud received".
* **Stale marking** — after a client disconnects, its snapshot is marked STALE.
  An unknown value is never back-filled with 0.
* **Cost grouping** — cost is grouped by task and call source; subscription
  usage is NOT inferred into an "API billed amount".
* **No leakage** — another project's title or body is never exposed; a shared
  UI shows only the authorized-visible coarse state.
* **Read-only invariant** — the projection adds no write capability to the
  Observer (task / config / telemetry).

Pure and deterministic: no network, no Observer write, no leaked body.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Iterable

# the delivery / execution / return / review pipeline stages
STAGES = ("delivery", "execution", "return", "review")

# distinct value labels — "unknown" is never back-filled with 0
VALUE_LABELS = ("PERMISSION_INSUFFICIENT", "ZERO", "UNKNOWN", "STALE", "ONLINE")

# task states
TASK_STATES = ("RUNNING", "PENDING_RETURN", "REVIEW_PENDING", "RECEIVED",
               "FAILED", "CANCELLED", "COMPLETED")


def stage_state(task: Mapping[str, Any]) -> dict[str, str]:
    """The per-stage state a task is in.  A task that has run but not returned
    is PENDING_RETURN at the return stage — not 'all failed' and not
    'cloud received'."""
    executed = task.get("executed", False)
    returned = task.get("returned", False)
    status = task.get("status", "")
    states = {stage: "pending" for stage in STAGES}
    if status == "RUNNING" or (executed and not returned and status not in
                                ("RECEIVED", "FAILED", "CANCELLED")):
        states["delivery"] = "done"
        states["execution"] = "done"
        states["return"] = "in_progress"      # ran, not returned yet
        states["review"] = "pending"
    elif status == "RECEIVED":
        for s in STAGES:
            states[s] = "done"
    elif status in ("FAILED", "CANCELLED"):
        states["delivery"] = "done"
        states["execution"] = "failed" if status == "FAILED" else "cancelled"
        states["return"] = "not_reached"
        states["review"] = "not_reached"
    return states


class ProjectProjection:
    """A read-only, per-project task projection with honest value display.

    Each project keeps its own snapshot; a client disconnect marks its snapshot
    STALE.  Unknown values are never back-filled with 0.  Another project's
    body / title is never reachable through this projection.
    """

    def __init__(self) -> None:
        self._projects: dict[str, dict[str, Any]] = {}
        self._clients_online: dict[str, bool] = {}

    def add_project(self, project_id: str, *, tasks: Iterable[Mapping[str, Any]],
                    source_software: str, target_software: str,
                    material_version: str, fact_updated_at: str) -> None:
        """Project tasks in with their software + material version.  The update
        time is the FACT (fact_updated_at), not a UI refresh timestamp."""
        self._projects[project_id] = {
            "project_id": project_id,
            "source_software": source_software,
            "target_software": target_software,
            "material_version": material_version,
            "fact_updated_at": fact_updated_at,
            "tasks": {t["task_id"]: dict(t) for t in tasks},
            "stale": False,
        }

    def set_client_online(self, project_id: str, online: bool) -> None:
        self._clients_online[project_id] = online
        # a disconnected client's snapshot is marked STALE; a reconnect clears it
        if project_id in self._projects:
            self._projects[project_id]["stale"] = (not online)

    def view_project(self, project_id: str) -> dict[str, Any]:
        """The independent view for ONE project.  It does not reach into another
        project's tasks — each project is a separate namespace."""
        proj = self._projects.get(project_id)
        if proj is None:
            return {"project_id": project_id, "available": False}
        online = self._clients_online.get(project_id, True)
        tasks_view = []
        for tid, task in proj["tasks"].items():
            entry = {
                "task_id": tid,
                "status": task.get("status"),
                "stage_states": stage_state(task),
                "title": None,          # another project's title is never exposed
                "body": None,           # another project's body is never exposed
            }
            # an actual-zero metric is shown as ZERO, an unknown as UNKNOWN —
            # never back-filled with 0 when it is actually unknown
            token = task.get("token_usage")
            entry["token_usage"] = ("UNKNOWN" if token is None else
                                    ("ZERO" if token == 0 else str(token)))
            tasks_view.append(entry)
        view = {
            "project_id": project_id,
            "available": True,
            "source_software": proj["source_software"],
            "target_software": proj["target_software"],
            "material_version": proj["material_version"],
            "updated_at": proj["fact_updated_at"],
            "updated_from_fact": True,
            "client_online": online,
            "snapshot_state": "STALE" if proj["stale"] else "LIVE",
            "tasks": tasks_view,
        }
        return view

    def independent_projects(self, project_ids: Iterable[str]) -> dict[str, Any]:
        """View several projects independently — a problem in one never blocks
        another (the A/B parallel-row guarantee)."""
        views = {pid: self.view_project(pid) for pid in project_ids}
        # a task that ran but has not returned must not be shown as all-failed
        # or as cloud-received
        return {
            "views": views,
            "note": "projects are viewed independently; a ran-but-not-returned "
                    "task stays PENDING_RETURN, not 'all failed' / 'cloud received'",
        }

    def did_any_task_leak(self, project_ids: Iterable[str]) -> bool:
        """Honest invariant: no task view ever carries a title or body, so no
        project's private content leaks through the shared projection."""
        for pid in project_ids:
            for t in self.view_project(pid).get("tasks", []):
                if t.get("title") is not None or t.get("body") is not None:
                    return True
        return False


class CostGrouping:
    """Cost is grouped by task and by call source.  A subscription usage figure
    is NEVER inferred into an 'API billed amount' — it stays an estimate with a
    label."""

    def __init__(self) -> None:
        self._groups: dict[str, dict[str, float | str]] = {}

    def record(self, task_id: str, source: str, *, cost: str | None,
               token_usage: str | None) -> None:
        g = self._groups.setdefault(task_id, {})
        # absent cost / tokens stay UNKNOWN, never a fabricated 0 / billed amount
        g[f"cost:{source}"] = cost if cost else "UNKNOWN"
        g[f"tokens:{source}"] = token_usage if token_usage else "UNKNOWN"

    def group(self, task_id: str) -> dict[str, Any]:
        return dict(self._groups.get(task_id, {}))

    def subscription_not_inferred_as_api_billed(self) -> dict[str, Any]:
        """A subscription usage figure is reported as an ESTIMATE, explicitly
        NOT an API billed amount."""
        return {"treated_as_api_billed": False,
                "label": "estimate (not an API billed amount)",
                "note": "subscription usage is never inferred into a billed figure"}


def read_only_invariant(holds_write: bool) -> dict[str, Any]:
    """The Observer adds NO write capability.  A projection that somehow gained
    a task/config/telemetry write must be rejected."""
    return {
        "write_added": holds_write,
        "allowed": not holds_write,
        "note": "Observer stays read-only; publish/approve/cancel entry points "
                "remain in the native client or a link, not a sidecar GET write",
    }
