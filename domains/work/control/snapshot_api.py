"""Unique read-only Snapshot API (WLGM-150).

Eliminates the dual projection (``/api/dashboard`` vs ``/api/v1/snapshot``).
The canonical -> Observer projection is implemented ONCE here, in the
Workflow-owned module. The snapshot:

- carries revision, generatedAt, source watermark, transport/quality/coverage;
- strictly distinguishes null from 0;
- separates projects, tasks and executions;
- splits token columns with exact/estimated/unknown cost marking;
- separates git local/remote/CI SHAs with match state;
- carries ``artifactHandles`` (identity-only evidence rows for the byte-range route) only when the caller
  supplies them, alongside the ``artifactHandlesSummary`` that states that list's enumeration scope;
- every core field is traceable to sourceRef where applicable.

Null vs zero: unknown values are null; counters that were observed are 0 or
positive integers. Nothing is padded to zero.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from typing import Any

SNAPSHOT_SCHEMA_VERSION = "workflow/snapshot/v3"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def build_snapshot(
    *,
    revision: int,
    store_projection: dict[str, Any] | None = None,
    executions: list[dict[str, Any]] | None = None,
    ci_runs: list[dict[str, Any]] | None = None,
    usage: list[dict[str, Any]] | None = None,
    projects: list[dict[str, Any]] | None = None,
    git_state: dict[str, Any] | None = None,
    transport: dict[str, Any] | None = None,
    governance: dict[str, Any] | None = None,
    workspace: dict[str, Any] | None = None,
    source_watermark: str | None = None,
    generated_at: str | None = None,
    platform_map: dict[str, str] | None = None,
    git_map: dict[str, dict[str, Any]] | None = None,
    agent_map: dict[str, str] | None = None,
    software: list[dict[str, Any]] | None = None,
    task_records: list[dict[str, Any]] | None = None,
    adapter_capabilities: list[dict[str, Any]] | None = None,
    artifact_handles: list[dict[str, Any]] | None = None,
    artifact_handles_summary: dict[str, Any] | None = None,
    collector_delivery: list[dict[str, Any]] | None = None,
    operation_progress: list[dict[str, Any]] | None = None,
    isolated_trials: list[dict[str, Any]] | None = None,
    issues: list[dict[str, Any]] | None = None,
    issues_summary: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the v3 snapshot from canonical facts (all fields optional for tests)."""
    generated_at = generated_at or _now()
    executions = executions or []
    ci_runs = ci_runs or []
    usage = usage or []
    projects = projects or []

    usage_by_project = _rollup_usage(usage)

    return {
        "schemaVersion": SNAPSHOT_SCHEMA_VERSION,
        "revision": revision,
        "generatedAt": generated_at,
        "sourceWatermark": source_watermark,
        "transport": {
            "transportState": (transport or {}).get("transportState") or "UNKNOWN",
            "freshnessState": (transport or {}).get("freshnessState") or "UNKNOWN",
            "connectedSince": (transport or {}).get("connectedSince"),
            "eventsUrl": (transport or {}).get("eventsUrl"),
        },
        "coverage": {
            "numerator": (transport or {}).get("coverageNumerator"),
            "denominator": (transport or {}).get("coverageDenominator"),
            "scope": (transport or {}).get("coverageScope"),
        },
        "governance": _governance_projection(governance),
        "workspace": workspace or {},
        "projects": [_project_projection(p, executions, usage_by_project, git_state, ci_runs, platform_map, git_map, agent_map) for p in projects],
        "executions": executions,
        "tasks": (store_projection or {}).get("tasks_by_status", {}),
        "tokenSummary": _token_summary(usage),
        "git": {
            "localSha": (git_state or {}).get("localSha"),
            "remoteSha": (git_state or {}).get("remoteSha"),
            "ciSha": (git_state or {}).get("ciSha"),
            "matchState": _git_match_state(git_state or {}),
        },
        "ci": [
            {
                "runId": run.get("runId"),
                "workflow": run.get("workflow"),
                "headSha": run.get("headSha"),
                "status": run.get("status"),
                "conclusion": run.get("conclusion"),
                "sourceRef": run.get("sourceRef"),
            }
            for run in ci_runs
        ],
        "sourceRefs": [e.get("sourceRef") for e in executions if e.get("sourceRef")],
        **({"software": software} if software is not None else {}),
        **({"taskRecords": task_records} if task_records is not None else {}),
        **({"adapterCapabilities": adapter_capabilities} if adapter_capabilities is not None else {}),
        # REQ-RANGE-20261007: the evidence artifact list the range route reads from. Absent stays absent for
        # the same reason taskRecords does — an empty list tells a reader "this project owns no evidence",
        # which is a different lie from saying nothing. The summary travels with the list or with neither:
        # it is the enumeration scope (cap, truncation, refusals) of that exact list, and a scope report for
        # an unprojected list would be a claim about a snapshot the reader is not looking at.
        **({"artifactHandles": artifact_handles,
            **({"artifactHandlesSummary": artifact_handles_summary}
               if artifact_handles_summary is not None else {})}
           if artifact_handles is not None else {}),
        # Per-collector delivery and refusal counts (ERR-256 made them durable). Same absent-never-empty rule
        # as the sections above: the presence of the key is the statement that health was read at all.
        **({"collectors": collector_delivery} if collector_delivery is not None else {}),
        # WUI-21: the two read models the isolated-trial pages need. Each item is a CONTRACT DOCUMENT
        # verbatim — `worklab/operation-progress/v1` / `worklab/isolated-trial/v1` — so the shape is owned by
        # one place (the schema file) instead of being restated here and drifting. Absent stays absent: a
        # reader must be able to tell "the producer was never wired" from "there is nothing to report".
        **({"operationProgress": operation_progress} if operation_progress is not None else {}),
        **({"isolatedTrials": isolated_trials} if isolated_trials is not None else {}),
        # The read side of the problem centre (audit 2026-10-22, 闭环距离 row 2). Paired exactly like
        # artifactHandles: the scope report travels with the list or with neither, and an absent pair means
        # "no source answered" — an empty pair would have claimed "every source was read and nothing is
        # wrong", which is a different statement and the one this repo refuses to let a projection make.
        **({"issues": issues,
            **({"issuesSummary": issues_summary} if issues_summary is not None else {})}
           if issues is not None else {}),
    }


_CHECKPOINT_KEY_NAME = re.compile(r"[A-Za-z0-9_.:/@+#=-]{1,64}")


_CHECKPOINT_KEY_NAME = re.compile(r"[A-Za-z0-9_.:/@+#=-]{1,64}")


def project_task_record(row: dict[str, Any]) -> dict[str, Any]:
    """Project one canonical-store task row into the Observer snapshot.

    The checkpoint column is workflow state that can quote a user's own text, so its VALUES never enter
    a read-only projection (AGENTS.md: no prompt bodies). What a reader needs to locate and trust a task
    is projected instead: the identifier, its owning project, the real status, the lease and fencing
    identity, whether a checkpoint exists at all, its key names, and a digest that changes when the
    checkpoint changes. A digest is an identity, not content.

    Absent means absent: no field is padded to a zero or an empty string.
    """
    checkpoint = row.get("checkpoint")
    parse_state = str(row.get("checkpointParseState") or "").upper()
    # Present is present, even when it will not parse: an unreadable checkpoint used to become `{}` in the
    # store and then `checkpointPresent: false` here, which asserts "this task has no checkpoint" about a
    # checkpoint that exists (ERR follow-up to the read-surface review).
    has_checkpoint = checkpoint is not None or parse_state == "UNPARSEABLE"
    keys: list[str] = []
    digest = row.get("checkpointDigest") if has_checkpoint else None
    if isinstance(checkpoint, dict):
        # Only a mapping's KEY NAMES are workflow field names. A checkpoint stored as a list would iterate
        # values and one stored as a bare string would iterate single characters -- both put user text into
        # a read-only projection while looking like a key list, so a non-mapping payload yields no keys.
        keys = sorted(name for name in (str(key) for key in checkpoint)
                      if _CHECKPOINT_KEY_NAME.fullmatch(name))
        if digest is None:
            canonical = json.dumps(checkpoint, ensure_ascii=False, sort_keys=True,
                                   separators=(",", ":")).encode("utf-8")
            digest = hashlib.sha256(canonical).hexdigest()
    fencing = row.get("fencing_token")
    return {
        "taskId": row.get("task_id"),
        "projectId": row.get("project_id"),
        "status": row.get("status"),
        "createdAt": row.get("created_at"),
        "updatedAt": row.get("updated_at"),
        "leaseHolder": row.get("lease_holder"),
        "leaseExpiresAt": row.get("lease_expires_at"),
        "fencingToken": fencing if isinstance(fencing, int) and not isinstance(fencing, bool) else None,
        "checkpointPresent": has_checkpoint,
        "checkpointKeys": keys,
        "checkpointDigest": digest,
    }


# Live platform: agent name -> platform display (execution evidence driven, not locked).
# Unknown agents keep their agent name; config map is only a fallback.
AGENT_TO_PLATFORM: dict[str, str] = {
    "deepseek-harness": "DSH",
    "hermes": "HERMES",
    "codex": "CODEX",
    "cc-switch": "CC_SWITCH",
    "github": "GITHUB",
    "openhuman": "OPENHUMAN",
    "open-design": "OPEN_DESIGN",
}

ACTIVE_EXECUTION_STATES = {"RUNNING", "STARTING", "WAITING_USER", "WAITING_APPROVAL", "BLOCKED"}


def _platform_for_agent(agent: Any, merged: dict[str, str]) -> str:
    """Map an agent to its platform display; unknown agents show their name as-is."""
    key = str(agent).lower()
    return merged.get(key, str(agent))


def _live_agent_platform(
    project_executions: list[dict[str, Any]],
    agent_map: dict[str, str] | None = None,
) -> str | None:
    """Real platform = the agent actually driving this project's executions.

    Any project run by any agent software is shown truthfully: active
    execution preferred, otherwise the most recent execution's agent. Unknown
    agents are displayed by their own name — never fabricated and never locked
    to a static config. None only when the project has no execution at all.
    """
    merged = dict(AGENT_TO_PLATFORM)
    if agent_map:
        merged.update(agent_map)
    # 1. active execution agent (whoever is running right now)
    for e in project_executions:
        if e.get("state") in ACTIVE_EXECUTION_STATES and e.get("agent"):
            return _platform_for_agent(e.get("agent"), merged)
    # 2. most recent execution's agent (last in list order)
    for e in reversed(project_executions):
        if e.get("agent"):
            return _platform_for_agent(e.get("agent"), merged)
    return None


def _project_projection(
    project: dict[str, Any],
    executions: list[dict[str, Any]],
    usage_by_project: dict[str, dict[str, Any]],
    git_state: dict[str, Any] | None,
    ci_runs: list[dict[str, Any]],
    platform_map: dict[str, str] | None = None,
    git_map: dict[str, dict[str, Any]] | None = None,
    agent_map: dict[str, str] | None = None,
) -> dict[str, Any]:
    # ``git_state`` is the top-level legacy single-project summary (see build_snapshot's "git" block).
    # It is deliberately NOT consumed here: reading it as a per-project fallback was WL-L01, which put
    # one repository's SHA under another project's name whenever that project had no Git row of its own.
    del git_state  # documented non-use, not a forgotten argument
    project_id = project.get("projectId")
    # WL-L01 (2026-10-11): this line used to read ``(git_map or {}).get(project_id) or git_state``.
    # The ``or git_state`` half meant a project with no Git observation of its own was printed with
    # somebody else's SHA/branch — and composition_root built that fallback with
    # ``next(iter(git_states.values()))``, so the borrower was whichever project happened to be first.
    # A missing observation is now UNKNOWN, and ``sourceProjectId`` names whose observation a row is
    # showing (null = nobody's), so a reader can tell "this project has no Git row" from "Git says X".
    effective_git = (git_map or {}).get(project_id)
    git_source_project_id = project_id if effective_git is not None else None
    project_executions = [e for e in executions if e.get("anchorProjectId") == project_id]
    active = sum(
        1 for e in project_executions if e.get("state") in {"RUNNING", "STARTING", "WAITING_USER", "WAITING_APPROVAL", "BLOCKED"}
    )
    raw_activity = str(project.get("activityState") or "UNKNOWN").upper()
    # A registry row is not evidence that a project is running.  Conversely,
    # once an execution instance is present, the project-level surface must
    # expose that activity instead of leaving every project REGISTERED.
    if active > 0 and raw_activity in {"REGISTERED", "UNKNOWN", "IDLE"}:
        activity_state = "ACTIVE"
    elif active == 0 and raw_activity == "UNKNOWN":
        activity_state = "UNKNOWN"
    else:
        activity_state = raw_activity
    usage = usage_by_project.get(project_id, {})
    project_ci = [r for r in ci_runs if r.get("projectId") == project_id]
    # WLGM-180: aggregate working areas from executions (never duplicated).
    working_areas: list[str] = []
    for e in project_executions:
        area = e.get("workingArea")
        if area and area not in working_areas:
            working_areas.append(area)
    live_platform = _live_agent_platform(project_executions, agent_map)
    return {
        "projectId": project_id,
        "agentPlatform": live_platform or (platform_map or {}).get(project_id) or project.get("agentPlatform"),
        "displayName": project.get("displayName"),
        "identityState": project.get("identityState") or "UNRESOLVED",
        "activityState": activity_state,
        "attentionState": project.get("attentionState") or "NONE",
        "activeExecutionCount": active,
        "workingAreas": working_areas,
        "visibility": project.get("visibility") or "UNKNOWN",
        "quality": project.get("quality") or "UNKNOWN",
        "lastStrongEvidenceAt": project.get("lastStrongEvidenceAt"),
        "repositories": project.get("repositories", []),
        "git": {
            "localSha": (effective_git or {}).get("localSha"),
            "remoteSha": (effective_git or {}).get("remoteSha"),
            "matchState": _git_match_state(effective_git or {}),
            "branch": (effective_git or {}).get("branch"),
            "dirtyCount": (effective_git or {}).get("dirtyCount"),
            "observedAt": (effective_git or {}).get("observedAt"),
            "quality": (effective_git or {}).get("quality"),
            "freshness": (effective_git or {}).get("freshness"),
            "sourceRef": (effective_git or {}).get("sourceRef"),
            # Whose Git observation these values are. Equal to this row's projectId for an own
            # observation, null when this project has none — never another project's id, because
            # borrowing one was WL-L01.
            "sourceProjectId": git_source_project_id,
        },
        "token": {
            "inputTokens": usage.get("inputTokens"),
            "outputTokens": usage.get("outputTokens"),
            "totalTokens": usage.get("totalTokens"),
            "costQuality": usage.get("costQuality") or "UNKNOWN",
        },
        "ci": project_ci,
        # The line below this one filtered; this one did not, so a row built from an execution with no id
        # emitted null inside a list the front model declares string[] — the join announced an identifier
        # it did not have. An id-less execution is still visible in `executions[]`, where executionId is
        # required, so dropping it here hides no fact.
        "executionIds": [eid for eid in (e.get("executionId") for e in project_executions) if eid],
        "sourceRefs": [e.get("sourceRef") for e in project_executions if e.get("sourceRef")],
    }


def _governance_projection(governance: dict[str, Any] | None) -> dict[str, Any]:
    """WLGM-180 §7: Rules/Skills/Memory/Adapter drift surface.

    Unknown when no data source declares it; never fabricates counts. Each
    family carries current/drift and a quality label.
    """
    if not governance:
        return {
            "state": "UNKNOWN",
            "families": {
                "rules": {"state": "UNKNOWN", "current": None, "drift": None},
                "skills": {"state": "UNKNOWN", "current": None, "drift": None},
                "memory": {"state": "UNKNOWN", "current": None, "drift": None},
                "adapters": {"state": "UNKNOWN", "current": None, "drift": None},
            },
        }
    families = {}
    for name in ("rules", "skills", "memory", "adapters"):
        family = governance.get(name) or {}
        current = family.get("current")
        drift = family.get("drift")
        if current is None and drift is None:
            state = "UNKNOWN"
        elif (drift or 0) > 0:
            state = "DRIFT"
        else:
            state = "CLEAN"
        families[name] = {"state": state, "current": current, "drift": drift}
    return {"state": governance.get("state") or "UNKNOWN", "families": families}


def _merge_cost_quality(qualities: list[Any]) -> str:
    """One precision rule, used by both the per-project rollup and the global token summary.

    WL-L03 (2026-10-11): the rollup used to promote a project to EXACT as soon as *one* sample said
    EXACT, while the summary over the very same samples demanded *all* of them. The same data therefore
    read EXACT on the project card and ESTIMATED in the total, and the optimistic one was the one shown
    per project. Sharing this predicate (not the token lists — they are different aggregations) is what
    keeps the two surfaces from disagreeing again.

    Empty input is UNKNOWN, never EXACT: ``all([])`` is True, and "no samples declared a precision" is
    not the same claim as "every sample was exact".
    """
    if not qualities:
        return "UNKNOWN"
    if all(q == "EXACT" for q in qualities):
        return "EXACT"
    if any(q == "ESTIMATED" for q in qualities):
        return "ESTIMATED"
    return "UNKNOWN"


def _rollup_usage(usage: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    rolled: dict[str, dict[str, Any]] = {}
    for sample in usage:
        project_id = sample.get("projectId") or "unknown"
        entry = rolled.setdefault(project_id, {"inputTokens": None, "outputTokens": None, "totalTokens": None, "costQuality": "UNKNOWN"})
        for field in ("inputTokens", "outputTokens", "totalTokens"):
            value = sample.get(field)
            if isinstance(value, int) and not isinstance(value, bool):
                entry[field] = (entry[field] or 0) + value
        entry["_qualities"] = (entry.get("_qualities") or []) + [sample.get("costQuality")]
    for entry in rolled.values():
        entry["costQuality"] = _merge_cost_quality(entry.pop("_qualities"))
    return rolled


def _token_summary(usage: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate usage into tokenSummary with null-vs-zero discipline (P0-3).

    No usage -> every field null, costQuality UNKNOWN; a field missing from
    every sample stays null (never padded to 0); EXACT only when every sample
    declares EXACT, ESTIMATED when any does, else UNKNOWN.
    """
    if not usage:
        return {"inputTokens": None, "outputTokens": None, "totalTokens": None, "costQuality": "UNKNOWN"}

    def _sum(field: str) -> int | None:
        values = [u.get(field) for u in usage if isinstance(u.get(field), int) and not isinstance(u.get(field), bool)]
        return sum(values) if values else None

    # Same predicate as the per-project rollup (WL-L03); an empty usage list is answered above.
    cost_quality = _merge_cost_quality([u.get("costQuality") for u in usage])
    return {
        "inputTokens": _sum("inputTokens"),
        "outputTokens": _sum("outputTokens"),
        "totalTokens": _sum("totalTokens"),
        "costQuality": cost_quality,
    }


def _git_match_state(git_state: dict[str, Any]) -> str:
    local = git_state.get("localSha")
    remote = git_state.get("remoteSha")
    ci = git_state.get("ciSha")
    if local and remote and local == remote and ci == local:
        return "MATCH"
    if local and remote and local == remote:
        return "LOCAL_REMOTE_MATCH"
    if local and ci and local == ci:
        return "LOCAL_CI_MATCH"
    if not local:
        return "NO_LOCAL_CLAIM"
    if remote is None and ci is None:
        return "UNVERIFIED"
    return "MISMATCH"
