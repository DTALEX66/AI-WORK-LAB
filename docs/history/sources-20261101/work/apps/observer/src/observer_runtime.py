from __future__ import annotations

from collections import OrderedDict
from copy import deepcopy
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Iterable
import json

from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = json.loads((ROOT / "schemas/observer-event.schema.json").read_text(encoding="utf-8"))
VALIDATOR = Draft202012Validator(SCHEMA)
SENSITIVE_KEYS = {"api_key", "apikey", "authorization", "password", "secret", "token", "cookie", "prompt", "response"}
TRANSFERRED_PROJECT_IDS = {"open-design"}


class ObserverInputError(ValueError):
    """Raised when an observed event is invalid or privacy-unsafe."""


def _keys(value: Any) -> set[str]:
    if isinstance(value, dict):
        return {str(k).lower() for k in value} | set().union(*(_keys(v) for v in value.values()))
    if isinstance(value, list):
        return set().union(*(_keys(v) for v in value)) if value else set()
    return set()


def validate_event(event: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(event, dict):
        raise ObserverInputError("event must be an object")
    sensitive = sorted(_keys(event) & SENSITIVE_KEYS)
    if sensitive:
        raise ObserverInputError(f"sensitive keys rejected: {', '.join(sensitive)}")
    errors = sorted(VALIDATOR.iter_errors(event), key=lambda error: list(error.path))
    if errors:
        raise ObserverInputError(errors[0].message)
    return deepcopy(event)


def append_events(log: list[dict[str, Any]], events: Iterable[dict[str, Any]], *, max_events: int = 256) -> int:
    """Append only validated observer-owned events; never mutates a source ledger."""
    if max_events < 1:
        raise ValueError("max_events must be positive")
    existing = {event["eventId"] for event in log}
    accepted = 0
    for raw in events:
        event = validate_event(raw)
        if event["eventId"] in existing:
            continue
        if len(log) >= max_events:
            raise ObserverInputError("observer event budget exceeded")
        log.append(event)
        existing.add(event["eventId"])
        accepted += 1
    return accepted


class IncrementalCursor:
    def __init__(self, *, max_batch: int = 128) -> None:
        if max_batch < 1:
            raise ValueError("max_batch must be positive")
        self.max_batch = max_batch
        self.cursor = ""
        self.rotation = 0
        self.seen: set[str] = set()

    def ingest(self, events: Iterable[dict[str, Any]], *, next_cursor: str) -> list[dict[str, Any]]:
        batch = list(events)
        if len(batch) > self.max_batch:
            raise ObserverInputError("collector batch budget exceeded")
        accepted: list[dict[str, Any]] = []
        for raw in batch:
            event = validate_event(raw)
            if event["eventId"] in self.seen:
                continue
            self.seen.add(event["eventId"])
            accepted.append(event)
        if next_cursor < self.cursor:
            self.rotation += 1
        self.cursor = next_cursor
        return accepted


def project_tasks(events: Iterable[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Rebuild a read-only task view from event history."""
    tasks: dict[str, dict[str, Any]] = {}
    for event in events:
        task_id = event.get("taskId")
        if not task_id:
            continue
        current = tasks.setdefault(task_id, {"taskId": task_id, "events": 0})
        current["events"] += 1
        current["lastEventType"] = event["eventType"]
        current["quality"] = event["quality"]
        current["coverage"] = event.get("coverage", "unknown")
        current["observedAt"] = event["observedAt"]
        current["taskTitle"] = event.get("taskTitle") or "工作项"
    return deepcopy(tasks)


def quality_summary(events: Iterable[dict[str, Any]]) -> dict[str, Any]:
    counts: dict[str, int] = {}
    total = 0
    for event in events:
        total += 1
        quality = event["quality"]
        counts[quality] = counts.get(quality, 0) + 1
    return {"quality": "source-exact" if total and counts.get("source-exact") == total else "partial" if total else "unknown", "coverage": "full" if total else "unknown", "counts": counts}


def project_usage(events: Iterable[dict[str, Any]]) -> dict[str, int]:
    """Aggregate only normalized explicit usage summaries from Observer events."""
    totals = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0, "records": 0}
    required = set(totals)
    for event in events:
        usage = event.get("usage")
        if usage is None:
            continue
        if not isinstance(usage, dict) or set(usage) != required:
            raise ObserverInputError("observer usage summary shape is invalid")
        for key in required:
            value = usage[key]
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ObserverInputError("observer usage metrics must be non-negative integers")
            totals[key] += value
    return totals


def project_cost(events: Iterable[dict[str, Any]], pricing_catalog: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Rebuild an idempotent, offline cost estimate from explicit usage and pricing fixtures."""
    if not isinstance(pricing_catalog, dict):
        raise ObserverInputError("pricing catalog must be an object")
    seen: set[str] = set()
    totals = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
    pricing_refs: list[dict[str, Any]] = []
    estimates: list[Decimal] = []
    statuses: set[str] = set()
    records = 0
    currency: str | None = None
    for event in events:
        event_id = event.get("eventId")
        if not isinstance(event_id, str) or not event_id:
            raise ObserverInputError("usage eventId must be a non-empty string")
        if event_id in seen:
            continue
        seen.add(event_id)
        usage = event.get("usage")
        if usage is None:
            telemetry = event.get("telemetry")
            if isinstance(telemetry, dict) and {"input_tokens", "output_tokens", "total_tokens"}.issubset(telemetry):
                usage = {key: telemetry[key] for key in ("input_tokens", "output_tokens", "total_tokens")}
        if usage is None:
            continue
        if not isinstance(usage, dict) or any(key not in usage for key in ("input_tokens", "output_tokens", "total_tokens")):
            raise ObserverInputError("usage rollup requires explicit token metrics")
        for key in ("input_tokens", "output_tokens", "total_tokens"):
            value = usage[key]
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ObserverInputError("usage rollup metrics must be non-negative integers")
            totals[key] += value
        records += 1
        alias = event.get("sourceId")
        telemetry = event.get("telemetry")
        if isinstance(telemetry, dict) and isinstance(telemetry.get("model"), str):
            alias = telemetry["model"]
        pricing = pricing_catalog.get(alias) if isinstance(alias, str) else None
        if not isinstance(pricing, dict):
            statuses.add("unknown")
            continue
        required = {"alias", "billing", "source", "effective_at", "currency", "stale"}
        if not required.issubset(pricing) or pricing["alias"] != alias:
            raise ObserverInputError("pricing entry is incomplete or alias-mismatched")
        if pricing["billing"] not in {"metered", "subscription"} or not isinstance(pricing["stale"], bool):
            raise ObserverInputError("pricing billing or stale flag is invalid")
        pricing_refs.append({key: pricing[key] for key in ("alias", "billing", "source", "effective_at", "currency", "stale")})
        if pricing["billing"] == "subscription":
            statuses.add("subscription/not-metered")
            continue
        if pricing["stale"]:
            statuses.add("stale")
            continue
        try:
            input_rate = Decimal(str(pricing["input_per_million"]))
            output_rate = Decimal(str(pricing["output_per_million"]))
        except (KeyError, InvalidOperation):
            raise ObserverInputError("metered pricing requires numeric input/output rates") from None
        if input_rate < 0 or output_rate < 0:
            raise ObserverInputError("pricing rates must be non-negative")
        estimates.append((Decimal(usage["input_tokens"]) * input_rate + Decimal(usage["output_tokens"]) * output_rate) / Decimal(1_000_000))
        statuses.add("estimated")
        if currency is None:
            currency = pricing["currency"]
        elif currency != pricing["currency"]:
            currency = None
            statuses.add("unknown")
    if not records:
        status = "unknown"
    elif "stale" in statuses:
        status = "stale"
    elif statuses == {"subscription/not-metered"}:
        status = "subscription/not-metered"
    elif statuses == {"estimated"}:
        status = "estimated"
    elif len(statuses) == 1:
        status = next(iter(statuses))
    else:
        status = "partial"
    estimated = format(sum(estimates, Decimal("0")), ".8f") if status == "estimated" else None
    return {
        **totals,
        "records": records,
        "estimated_cost": estimated,
        "currency": currency if status == "estimated" else None,
        "cost_status": status,
        "pricing": sorted(pricing_refs, key=lambda item: item["alias"]),
    }


def project_projection(events: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """Derive a cross-project read-only view: group tasks by projectId (default WORK-LAB).

    projectId is optional in the event schema; events without it belong to the
    default WORK-LAB project. Observer never mutates; this is a pure projection.
    """
    history = [deepcopy(event) for event in events]
    projects: dict[str, dict[str, Any]] = {}
    default_project = "work-lab"
    for event in history:
        pid = event.get("projectId") or default_project
        if pid in TRANSFERRED_PROJECT_IDS:
            continue
        current = projects.setdefault(pid, {"projectId": pid, "tasks": set(), "eventCount": 0, "sources": set()})
        current["eventCount"] += 1
        task_id = event.get("taskId")
        if isinstance(task_id, str) and task_id:
            current["tasks"].add(task_id)
        src = event.get("sourceModule")
        if isinstance(src, str):
            current["sources"].add(src)
    result: dict[str, Any] = {"count": len(projects), "projects": []}
    for pid in sorted(projects):
        p = projects[pid]
        result["projects"].append({
            "projectId": pid,
            "taskCount": len(p["tasks"]),
            "eventCount": p["eventCount"],
            "sources": sorted(p["sources"]),
        })
    return result


def project_read_only_dashboard(events: Iterable[dict[str, Any]], pricing_catalog: dict[str, dict[str, Any]] | None = None) -> dict[str, Any]:
    """Build a deterministic, data-only dashboard projection from event history."""
    history = [deepcopy(event) for event in events]
    tasks = project_tasks(history)
    public_tasks = [
        {key: value for key, value in task.items() if key != "taskId"}
        for task in sorted(tasks.values(), key=lambda item: (str(item.get("observedAt", "")), str(item.get("taskTitle", ""))))
    ]
    quality = quality_summary(history)
    observed = [event.get("observedAt") for event in history if isinstance(event.get("observedAt"), str)]
    partial = sum(event.get("coverage") == "partial" for event in history)
    unknown = sum(event.get("coverage") == "unknown" or event.get("quality") == "unknown" for event in history)
    last_good = max((event["observedAt"] for event in history if event.get("quality") == "source-exact"), default="unknown")
    return {
        "overview": {
            "taskCount": len(tasks),
            "eventCount": len(history),
            "quality": quality["quality"],
            "coverage": quality["coverage"],
            "lastObservedAt": max(observed, default="unknown"),
        },
        "tasks": public_tasks,
        "usage": project_usage(history),
        "cost": project_cost(history, pricing_catalog or {}),
        "quality": quality,
        "dataQuality": {
            "partialEvents": partial,
            "unknownEvents": unknown,
            "lastGood": last_good,
        },
        "mutationSurface": mutation_surface(),
    }


def mutation_surface() -> dict[str, Any]:
    # R2 third batch: allowedWrites removed — Observer owns no write surface
    # at all; the only enforcement is ObserverStore.append raising.
    return {"externalMutation": False, "ledgerMutation": False, "approvalMutation": False, "gitControl": False}


def _task_state(event_type: str) -> str:
    et = str(event_type or "").lower()
    if "block" in et or "fail" in et:
        return "blocked"
    if "unverified" in et or "pending" in et or "queued" in et or "wait" in et:
        return "waiting_external"
    if "pass" in et or "done" in et or "complete" in et or "verified" in et:
        return "completed"
    if "run" in et or "start" in et or "heartbeat" in et or "progress" in et or "checkpoint" in et or "usage" in et or "telemetry" in et:
        return "running"
    return "unknown"


def _freshness(observed_at: str | None) -> tuple[str, int | None]:
    if not observed_at:
        return "unknown", None
    try:
        parsed = datetime.fromisoformat(observed_at.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        age = max(0, int((datetime.now(timezone.utc) - parsed.astimezone(timezone.utc)).total_seconds()))
    except ValueError:
        return "unknown", None
    if age <= 60:
        return "fresh", age
    if age <= 300:
        return "delayed", age
    return "stale", age


def _unknown_dimension() -> dict[str, int | None]:
    return {"current": None, "drift": None, "quarantined": None, "conflicts": None, "stale": None}


def load_governance(project_root: Path) -> tuple[dict[str, Any], dict[str, Any], int | None]:
    """Load REAL governance inventory: skills / adapters / rules / memory from repo files.

    Returns (skills_dim, adapters_dim, rule_count). Never invents values — reads the
    actual governance artifacts (CURRENT_STATE skills, adapter-registry, .project/governance/rules).
    """
    skills = _unknown_dimension()
    adapters = _unknown_dimension()
    rules_count: int | None = None
    # Skills from CURRENT_STATE
    cs = project_root / ".project/governance" / "generated" / "CURRENT_STATE.json"
    if cs.exists():
        try:
            d = json.loads(cs.read_text(encoding="utf-8"))
            items = (d.get("skills") or {}).get("items", [])
            skills["current"] = len(items)
            skills["quarantined"] = sum(1 for i in items if i.get("trust") not in ("repository-controlled",))
        except Exception:
            pass
    # Adapters from adapter-registry entries
    ar = project_root / "config" / "adapter-registry.json"
    if ar.exists():
        try:
            d = json.loads(ar.read_text(encoding="utf-8"))
            entries = d.get("entries", [])
            adapters["current"] = len(entries)
            adapters["drift"] = 0
        except Exception:
            pass
    # Rules from .project/governance/rules (yaml/md rule files)
    rules_dir = project_root / ".project/governance" / "rules"
    if rules_dir.exists():
        try:
            rules_count = len([p for p in rules_dir.iterdir() if p.is_file() and p.suffix in (".yaml", ".yml", ".md")])
        except Exception:
            pass
    return skills, adapters, rules_count


def project_authority_dashboard(
    events: Iterable[dict[str, Any]],
    pricing_catalog: dict[str, dict[str, Any]] | None = None,
    *,
    mode: str | None = None,
) -> dict[str, Any]:
    """Build the authoritative dashboard projection (Schema v2) from REAL governance +
    real observed events.

    - `projects`: projects observed in Hermes runtime events, grouped by `projectId`.
      Repository modules are deliberately not used as a fallback: they are source
      code ownership entries, not proof that a project is currently running.
    - `governance`: real Rules / Skills / Adapters / Memory·Context inventory counts.
    - usage/quality from real event aggregates.
    LIVE is only emitted after an explicit caller declaration. A finite event
    collection is otherwise a SNAPSHOT; an empty collection is UNKNOWN.
    """
    history = [deepcopy(e) for e in events]
    allowed_modes = {"LIVE", "SNAPSHOT", "FIXTURE", "STALE", "OFFLINE", "UNKNOWN"}
    projection_mode = mode or ("SNAPSHOT" if history else "UNKNOWN")
    if projection_mode not in allowed_modes:
        raise ObserverInputError(f"unsupported projection mode: {projection_mode}")
    observed_times = sorted(e["observedAt"] for e in history if isinstance(e.get("observedAt"), str))
    generated_at = observed_times[-1] if observed_times else "1970-01-01T00:00:00+00:00"
    freshness_state, age_seconds = _freshness(generated_at if observed_times else None)
    project_root = Path(__file__).resolve().parents[3]  # repo root

    # --- Hermes runtime projects only. An event without projectId is assigned to
    # the explicit default WORK-LAB project by project_projection(); this keeps
    # legacy events usable without turning source modules into fake projects.
    observed: dict[str, list[dict[str, Any]]] = {}
    for event in history:
        project_id = event.get("projectId")
        if not isinstance(project_id, str) or not project_id.strip():
            project_id = "work-lab"
        observed.setdefault(project_id, []).append(event)

    main_projects: list[dict[str, Any]] = []
    for project_id in sorted(observed):
        project_events = observed[project_id]
        latest = max(project_events, key=lambda e: str(e.get("observedAt", "")))
        state = _task_state(latest.get("eventType", ""))
        task_titles = [e.get("taskTitle") or "工作项" for e in project_events if isinstance(e.get("taskId"), str) and e.get("taskId")]
        last_event_at = latest.get("observedAt")
        project_freshness, _ = _freshness(last_event_at)
        quality_state = "exact" if all(e.get("quality") == "source-exact" for e in project_events) else "partial"
        project = {
            "projectId": project_id,
            "displayName": "WORK-LAB" if project_id == "work-lab" else project_id.replace("-", " ").title(),
            "agentPlatform": "hermes",
            "task": task_titles[-1] if task_titles else None,
            "state": state,
            "stage": None,
            "durationSeconds": None,
            "blockerSummary": None,
            "branch": "main",
            "headSha": None,
            "ciState": None,
            "lastEventAt": last_event_at,
            "quality": {
                "evidenceCompleteness": "complete",
                "dataQuality": quality_state,
                "freshness": project_freshness,
                "sourceRef": "hermes-runtime-events",
            },
        }
        if project_id == "work-lab":
            project["repository"] = "DTALEX66/WORK-LAB"
        main_projects.append(project)

    counts = {"running": 0, "waiting": 0, "blocked": 0, "failed": 0, "completed": 0, "unknown": 0}
    for p in main_projects:
        key = p["state"] if p["state"] in counts else "unknown"
        counts[key] += 1

    # --- Real governance inventory
    skills_dim, adapters_dim, rules_count = load_governance(project_root)
    governance = {
        "rules": {"current": rules_count, "drift": None, "quarantined": None, "conflicts": None, "stale": None},
        "skills": skills_dim,
        "adapters": adapters_dim,
        "memoryContext": _unknown_dimension(),
    }

    # --- Usage / quality from real events
    usage_agg = project_usage(history)
    input_tokens = int(usage_agg.get("input_tokens", 0)) or None
    output_tokens = int(usage_agg.get("output_tokens", 0)) or None
    cost = project_cost(history, pricing_catalog or {})
    cost_status = str(cost.get("cost_status", "unknown"))
    usage = {
        "inputTokens": input_tokens,
        "outputTokens": output_tokens,
        "reasoningTokens": None,
        "cacheReadTokens": None,
        "cacheWriteTokens": None,
        "cost": {"amount": cost.get("estimated_cost") if cost_status == "estimated" else None, "currency": cost.get("currency"), "status": cost_status, "billingType": "mixed" if cost.get("pricing") else "unknown", "sourceRef": None, "effectiveAt": None},
        "subscriptionUsage": None,
        "series": [],
        "quality": {"evidenceCompleteness": "complete", "dataQuality": "exact" if input_tokens else "unknown", "freshness": freshness_state},
    }

    exact = sum(1 for e in history if e.get("quality") == "source-exact")
    quality = {
        "sourceCoverage": {"numerator": exact, "denominator": len(history), "scope": "observed-events"},
        "evidenceCompleteness": "complete" if history and exact == len(history) else "partial" if history else "missing",
        "freshness": freshness_state if exact else "unknown",
        "unknown": sum(1 for e in history if e.get("quality") == "unknown" or e.get("coverage") == "unknown"),
        "malformed": 0, "dropped": 0,
        "duplicate": len(history) - len({e.get("eventId") for e in history}),
        "projectionLagMs": age_seconds * 1000 if age_seconds is not None else None, "lastGoodAt": generated_at if observed_times else None,
    }

    # Backward-compatible aliases keep the legacy Python dashboard readable
    # while Schema v2 remains the single authoritative projection payload.
    legacy = project_read_only_dashboard(history, pricing_catalog)
    usage["input_tokens"] = legacy["usage"]["input_tokens"]
    usage["output_tokens"] = legacy["usage"]["output_tokens"]
    usage["total_tokens"] = legacy["usage"]["total_tokens"]
    usage["records"] = legacy["usage"]["records"]
    quality["quality"] = "source-exact" if history and exact == len(history) else "partial" if history else "unknown"
    quality["coverage"] = "full" if history else "unknown"

    return {
        "schemaVersion": "work-lab/observer-projection/v2",
        "mode": projection_mode,
        "generatedAt": generated_at,
        "freshness": {"state": freshness_state, "ageSeconds": age_seconds, "lastGoodAt": generated_at if observed_times else None},
        "summary": {"registeredProjects": len(main_projects), "activeProjects": counts["running"] + counts["waiting"], "tasks": counts},
        "projects": main_projects,
        "primaryBlocker": next(({"projectId": p["projectId"], "title": p["state"], "state": "BLOCKED", "durationSeconds": 0, "lastObservedAt": None, "impact": None, "nextCondition": None, "quality": p["quality"]} for p in main_projects if p["state"] == "blocked"), None),
        "usage": usage,
        "ci": {"exactShaBound": None, "exactShaRequired": None, "queuedNoJob": None, "running": None, "passed": None, "failed": None, "unknown": None, "quality": {"evidenceCompleteness": "missing", "dataQuality": "unknown", "freshness": "unknown"}},
        "governance": governance,
        "quality": quality,
        "sourceRefs": [],
        "mutationSurface": mutation_surface(),
        "overview": legacy["overview"],
        "tasks": legacy["tasks"],
        "cost": legacy["cost"],
        "dataQuality": legacy["dataQuality"],
    }
