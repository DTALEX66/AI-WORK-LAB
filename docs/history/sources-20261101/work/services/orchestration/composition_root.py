"""唯一运行组合根：approved ProductProject → canonical → v3 Snapshot → SSE → Observer。

WLGM P0-1/P0-2 收口：sidecar 与 durable_worker 通过本模块组装新链路，旧
collectors/EventHub/v1 投影保留兼容。本模块不修改任何既有模块。

- ``load_approved_index`` 从 canonical 读 approved ProductProject 定义；
- ``build_v3_snapshot`` 组装 snapshot_api.build_snapshot 的全部入参，transport
  由调用方传入的 live-gate verdict 决定（LIVE 只能来自 live gate）。
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any

from canonical_store import CanonicalStore
from open_task_register_projection import (load_register_task_records, merge_task_rows, register_path,
                                           unreadable_marker)
from product_project import ProductProject, ProjectRootBinding
from project_identity_resolver import ApprovedProjectIndex
from snapshot_api import build_snapshot

# ---------------------------------------------------------------------------
# WS-2 / spec-3: software[] wiring into build_v3_snapshot
#
# The canonical software registry (config/software-registry.json) is the single
# source of truth for managed software ids. Real discovery (platform_discovery.
# discover_software_installations) probes the declared install roots and
# classifies each software via the shared resolver (software_installation_identity).
# Any probe failure degrades to software=[] + discoverySource="unavailable" —
# the snapshot build NEVER crashes on discovery.
#
# Cross-package import convention (matches durable_worker.py / canary_runner.py):
# the module roots live under packages/client-neutral-core/scripts after the
# directory convergence. Inject the path once; guard so tests that already
# include that path on sys.path are unaffected.
# ---------------------------------------------------------------------------
_ROOT = Path(__file__).resolve().parents[2]
_CNC_SCRIPTS = _ROOT / "packages" / "client-neutral-core" / "scripts"
if str(_CNC_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_CNC_SCRIPTS))

try:
    import platform_discovery as _platform_discovery
    import software_installation_identity as _sii
except Exception:  # pragma: no cover - import failure degrades to unavailable
    _platform_discovery = None  # type: ignore[assignment]
    _sii = None  # type: ignore[assignment]

# Bounded in-memory cache for discovery results (spec: TTL-based, single entry).
# The cache survives across /api/v1/snapshot calls within its TTL so repeated
# discovery probes (subprocess execs of --version, etc.) are not run on every
# SSE publish tick. The TTL is intentionally conservative (60 s) so a user who
# installs software gets a fresh observation within one minute without waiting
# for a full sidecar restart.
_SOFTWARE_DISCOVERY_TTL_SECONDS = 60.0
_software_discovery_cache: dict[str, Any] = {}


def _load_software_registry() -> list[dict[str, Any]]:
    """Read the canonical software registry. Returns [] on any failure."""
    try:
        path = _ROOT / "config" / "software-registry.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        return data.get("software", [])
    except Exception:
        return []


def _build_software_projection() -> list[dict[str, Any]]:
    """Build the software[] snapshot projection (registry × discovery × resolver).

    Field alignment (frontend SoftwareIdentity, spec step 1/4):
      softwareId, displayName, installRoot, executableRealpath,
      discoveredVersion, releaseChannel, updateAvailable,
      duplicateInstallation, expectedLocation, observedLocation,
      locationStatus, lastVerified, discoverySource

    Truth discipline: when discovery is unavailable, locationStatus stays
    "UNKNOWN" and discoverySource becomes "unavailable" — we never fabricate
    a value. Each entry reflects only the actual probed facts.
    """
    if _platform_discovery is None or _sii is None:
        return []

    # --- Bounded TTL cache (key: revision-independent; value: {at, items}) ---
    now = time.time()
    cached = _software_discovery_cache.get("items")
    if cached is not None and (now - _software_discovery_cache.get("at", 0.0)) < _SOFTWARE_DISCOVERY_TTL_SECONDS:
        return cached

    try:
        registry = _load_software_registry()
        observations = _platform_discovery.discover_software_installations()
        obs_by_id = {str(o.get("software_id") or ""): o for o in observations}

        items: list[dict[str, Any]] = []
        for entry in registry:
            software_id = str(entry.get("softwareId") or "")
            if not software_id:
                continue
            display_name = entry.get("displayName")
            # Canonical registry -> discovery inventory matching.
            # The SOFTWARE_CANDIDATE_INVENTORY in platform_discovery uses
            # "package_identity" keys that mirror "softwareId" in the registry.
            obs = obs_by_id.get(software_id)

            if obs is None:
                # Registry entry with no discovery observation: UNKNOWN.
                items.append(
                    {
                        "softwareId": software_id,
                        "displayName": display_name,
                        "installRoot": None,
                        "executableRealpath": None,
                        "discoveredVersion": None,
                        "releaseChannel": None,
                        "updateAvailable": None,
                        "duplicateInstallation": False,
                        "expectedLocation": None,
                        "observedLocation": None,
                        "locationStatus": "UNKNOWN",
                        "lastVerified": None,
                        "discoverySource": "unavailable",
                    }
                )
                continue

            # Discovery observation present — extract real fields.
            location_status = str(obs.get("location_status") or "UNKNOWN")
            # DUAL_INSTALLATION from the resolver means more than one real root.
            duplicate = location_status == "DUAL_INSTALLATION"
            observed_location = obs.get("observed_existing_location") or obs.get("install_root")

            items.append(
                {
                    "softwareId": software_id,
                    "displayName": display_name,
                    "installRoot": obs.get("install_root"),
                    "executableRealpath": obs.get("executable_realpath") or None,
                    "discoveredVersion": obs.get("discovered_version"),
                    "releaseChannel": obs.get("release_channel"),  # usually None from resolver
                    "updateAvailable": None,  # NOT in resolver; not probed -> never fabricate
                    "duplicateInstallation": duplicate,
                    "expectedLocation": obs.get("expected_existing_location") or obs.get("expected_existing"),
                    "observedLocation": observed_location,
                    "locationStatus": location_status,
                    "lastVerified": obs.get("verified_at"),
                    "discoverySource": obs.get("discovery_source") or "real-platform-probe",
                }
            )

        _software_discovery_cache["items"] = items
        _software_discovery_cache["at"] = now
        return items
    except Exception:
        # Discovery failure → empty projection + unavailable flag (degrade, don't crash).
        _software_discovery_cache.clear()
        return []


def clear_software_discovery_cache() -> None:
    """Public reset for tests / callers that need to force a fresh probe."""
    _software_discovery_cache.clear()


# ---------------------------------------------------------------------------
# REQ-RANGE-20261007: artifactHandles[] wiring
#
# The evidence-range route could already read an exact byte interval of one artifact; what the UI was
# missing was the list of handles it may ask about, so the record was parked at
# UI_LANDING_BLOCKED_ON_HANDLE_PROJECTION. `artifact_handle_projection` enumerates the declared evidence
# surfaces and projects identity-only rows (path, surface, size, mtime, kind, and a digest ONLY where a
# project record already states one).
#
# Same TTL shape as software discovery, and for the same reason: the walk costs ~130 ms on this machine
# and build_v3_snapshot runs twice per snapshot (the live-gate skeleton and the snapshot itself), so an
# uncapped per-call enumeration would put ~260 ms of directory syscalls into every read.
#
# Absent-vs-empty is the contract, not a detail: no declared surface on this machine means the KEY IS NOT
# EMITTED (an empty list would claim the project owns no evidence), while a surface that exists and holds
# nothing emits [].
# ---------------------------------------------------------------------------
_ARTIFACT_HANDLES_TTL_SECONDS = 60.0
_artifact_handles_cache: dict[str, Any] = {}


def _build_artifact_handles_projection(*, force: bool = False) -> tuple[list[dict[str, Any]] | None,
                                                                       dict[str, Any] | None,
                                                                       str | None]:
    """(handles, summary, absentReason) from this machine's declared evidence surfaces, TTL-cached."""
    now = time.time()
    if not force and _artifact_handles_cache and (
            now - _artifact_handles_cache.get("at", 0.0)) < _ARTIFACT_HANDLES_TTL_SECONDS:
        return (_artifact_handles_cache["handles"], _artifact_handles_cache["summary"],
                _artifact_handles_cache["reason"])
    handles: list[dict[str, Any]] | None = None
    summary: dict[str, Any] | None = None
    reason: str | None = None
    try:
        from artifact_handle_projection import load_artifact_handles
        handles, summary, reason = load_artifact_handles(_ROOT, generated_at=_snapshot_timestamp(now))
    except Exception as error:  # noqa: BLE001 - a listing fault is a reported gap, never a crashed read
        handles = summary = None
        reason = f"projection-unavailable:{type(error).__name__}"
    _artifact_handles_cache.clear()
    _artifact_handles_cache.update({"at": now, "handles": handles, "summary": summary, "reason": reason})
    return handles, summary, reason


def _snapshot_timestamp(now: float) -> str:
    from datetime import datetime, timezone
    return datetime.fromtimestamp(now, timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def clear_artifact_handles_cache() -> None:
    """Public reset for tests / callers that need a fresh enumeration."""
    _artifact_handles_cache.clear()


# ---------------------------------------------------------------------------
# taskRecords from the live open-task register (owner readback 2026-10-27)
#
# `open_task_register_projection` reads and parses `taskpacks/current/OPEN-TASK-REGISTER.md`. The file is
# 345,684 B and one read+parse costs ~3 ms measured on this machine, but `build_v3_snapshot` runs twice per
# snapshot (the live-gate skeleton and the snapshot itself) and the sidecar re-serves it on every poll, so
# the parse is cached.
#
# Cached on the file's own (mtime, size), NOT on the 60 s TTL the other projections here use, and the
# difference is deliberate: this file is the artifact the owner edits by hand and expects to see. A timer
# would show them their own registration late and call that "the current register", which is exactly the
# class of stale-but-green answer this round exists to remove. A stat() costs microseconds; the read only
# happens when the file actually changed.
# ---------------------------------------------------------------------------
_register_cache: dict[str, Any] = {}


def _build_register_task_rows(*, root: Path | None = None) -> list[dict[str, Any]]:
    """taskRecords derived from a repository's live register, re-parsed only when the file changed."""
    search_root = Path(root) if root is not None else _ROOT
    key = search_root.as_posix()
    path = register_path(search_root)
    try:
        stat = path.stat()
        signature: tuple[int, int] | None = (int(stat.st_mtime_ns), int(stat.st_size))
    except OSError:
        signature = None  # absent or unstatable: fall through to the read, which reports it
    entry = _register_cache.get(key)
    if entry is not None and signature is not None and entry.get("signature") == signature:
        return entry["rows"]
    try:
        rows, state, reason = load_register_task_records(search_root)
    except Exception as error:  # noqa: BLE001 - a register read fault is a reported gap, never a dead read
        reason = f"projection-unavailable:{type(error).__name__}"
        rows, state = [unreadable_marker(reason, evidence_ref=path.as_posix())], "UNREADABLE"
    _register_cache[key] = {"signature": signature, "rows": rows, "state": state, "reason": reason,
                            "path": path.as_posix()}
    return rows


def register_status(*, root: Path | None = None) -> dict[str, Any]:
    """How the register reached the last snapshot — read from the same cache the build used."""
    search_root = Path(root) if root is not None else _ROOT
    entry = _register_cache.get(search_root.as_posix()) or {}
    return {"projectedCount": len(entry.get("rows") or []),
            "state": entry.get("state"),
            "reason": entry.get("reason"),
            "path": entry.get("path"),
            "watchedSignature": entry.get("signature")}


def clear_register_projection_cache() -> None:
    """Public reset for tests / callers that need a fresh parse."""
    _register_cache.clear()


def artifact_handles_status() -> dict[str, Any]:
    """Why artifactHandles is or is not in the last snapshot — read from the same cache the build used.

    The snapshot itself only ever says "here are the handles" or says nothing (absent must stay absent), so
    without this accessor an absent key would be unexplainable to an operator: no surface on this machine
    and an enumeration that threw look identical from the outside.
    """
    return {"enumerated": bool(_artifact_handles_cache.get("handles") is not None),
            "absentReason": _artifact_handles_cache.get("reason"),
            "projectedCount": len(_artifact_handles_cache.get("handles") or []),
            "cachedAt": _artifact_handles_cache.get("at"),
            "ttlSeconds": _ARTIFACT_HANDLES_TTL_SECONDS}


# ---------------------------------------------------------------------------
# Issue centre (audit 2026-10-22, 闭环距离 row 2): problems derived from facts the store already holds.
# ---------------------------------------------------------------------------
_ISSUES_TTL_SECONDS = 30.0
_issues_cache: dict[str, Any] = {}


def _build_issues_projection(store: CanonicalStore, software_rows: list[dict[str, Any]] | None,
                             *, force: bool = False
                             ) -> tuple[list[dict[str, Any]] | None, dict[str, Any] | None, str | None]:
    """(issues, summary, absentReason), TTL-cached like the handle enumeration.

    The identity signature is part of the cache key: rows attributed to `softwareId`s from one tick must not
    be served next to a software list from another, or the attribution counts and the identity section would
    disagree inside one snapshot. The derivation itself is pure over store rows; this wrapper exists so the
    read path can never die on a bad column, and so an operator can ask why the key is absent.
    """
    now = time.time()
    signature = tuple(sorted({str(row.get("softwareId") or "") for row in (software_rows or [])}))
    if (not force and _issues_cache and _issues_cache.get("softwareSignature") == signature
            and (now - _issues_cache.get("at", 0.0)) < _ISSUES_TTL_SECONDS):
        return _issues_cache["issues"], _issues_cache["summary"], _issues_cache["reason"]
    try:
        from issue_projection import load_issues
        issues, summary, reason = load_issues(store, generated_at=_snapshot_timestamp(now),
                                             software_rows=software_rows)
    except Exception as error:  # noqa: BLE001 - a projection fault is a reported gap, not a dead snapshot
        issues = summary = None
        reason = f"projection-unavailable:{type(error).__name__}"
    _issues_cache.clear()
    _issues_cache.update({"at": now, "issues": issues, "summary": summary, "reason": reason,
                          "softwareSignature": signature})
    return issues, summary, reason


def issues_status() -> dict[str, Any]:
    """Why `issues` is or is not in the last snapshot, read from the same cache the build used."""
    return {"derived": bool(_issues_cache.get("issues") is not None),
            "absentReason": _issues_cache.get("reason"),
            "identityRowsKnown": len(_issues_cache.get("softwareSignature") or ()),
            "emittedCount": len(_issues_cache.get("issues") or []),
            "sourcesRead": (_issues_cache.get("summary") or {}).get("sourcesRead"),
            "sourcesAbsent": (_issues_cache.get("summary") or {}).get("sourcesAbsent"),
            "cachedAt": _issues_cache.get("at"),
            "ttlSeconds": _ISSUES_TTL_SECONDS}


def clear_issues_cache() -> None:
    _issues_cache.clear()


# ---------------------------------------------------------------------------
# End WS-2 / spec-3 software[] wiring
# ---------------------------------------------------------------------------

# 显式批准白名单：默认仅 WORK-LAB 自身；其余项目需经 upsert_project_definition
# 持久化 approved=True 后才收集（未批准 → 绝不自动收集）。
EXPLICIT_APPROVED: set[str] = {"work-lab", "design-lab", "archeaxis-knowledge-os", "obsidian-assistance"}


def load_approved_index(store: CanonicalStore) -> ApprovedProjectIndex:
    """从 canonical 构造 ApprovedProjectIndex；未批准 registry 行不得进入投影。"""
    projects: list[ProductProject] = []
    machine_roots: dict[str, str] = {}
    for row in store.list_projects():
        project_id = str(row.get("project_id") or row.get("projectId") or "")
        if not project_id:
            continue
        definition = store.get_project_definition(project_id)
        if definition:
            project = ProductProject.from_definition(definition)
        else:
            project = ProductProject(
                project_id=project_id,
                display_name=str(row.get("display_name") or project_id),
                approved=project_id in EXPLICIT_APPROVED,
            )
        approved = project_id in EXPLICIT_APPROVED or project.approved
        if not approved or project.deny_listed or project.never_scan:
            continue
        root = str(row.get("root_path") or "")
        if root:
            project.add_root_binding(
                ProjectRootBinding(
                    binding_id=f"{project_id}-root",
                    project_id=project_id,
                    root=root,
                )
            )
            machine_roots[project_id] = root
        projects.append(project)
    return ApprovedProjectIndex(projects=projects, machine_roots=machine_roots)


def _project_rows(store: CanonicalStore, index: ApprovedProjectIndex) -> list[dict[str, Any]]:
    """projects 表行 → v3 project projection（identityState 由 index 判定）。"""
    projections: list[dict[str, Any]] = []
    strong_evidence = _strong_evidence_map(store)
    for row in store.list_projects():
        project_id = str(row.get("project_id") or "")
        if not project_id or project_id not in index.projects:
            continue
        root = str(row.get("root_path") or "")
        project = index.by_root(root) if root else None
        projections.append(
            {
                "projectId": project_id,
                "displayName": str(row.get("display_name") or project_id),
                "activityState": str(row.get("status") or "UNKNOWN"),
                "identityState": "RESOLVED" if project is not None else "UNRESOLVED",
                # The card's 最近变化 / 更新 was 待确认 / UNKNOWN forever because this key was never
                # produced here, while `snapshot_api._project_projection` read it and the front fell back
                # to 待确认. Null is still the answer when the project owns no strong observation.
                "lastStrongEvidenceAt": strong_evidence.get(project_id),
            }
        )
    return projections


# ---------------------------------------------------------------------------
# projects[].lastStrongEvidenceAt (owner readback 2026-10-27)
#
# `snapshot_api._project_projection` has always copied this key out of the project row, and
# `apps/observer/frontend/src/daily/dailyData.ts::projectCardOf` has always read it — with
# 「最近变化 待确认 / 更新：UNKNOWN」 as the fallback when it is null. Nothing upstream ever produced it, so
# the card could not have been anything but 待确认.
#
# The one per-project, per-timestamp observation the canonical store actually carries is the
# `source_quality` table: `collectors.py` writes `quality = "EXACT_SOURCE" if head else "UNKNOWN"` (and
# the same label for a source it read exactly), and every row states `observed_at` plus `project_id`.
# Measured against the live store on 2026-10-27: 2 rows, both `work-lab`, both `EXACT_SOURCE`
# (scopes `git` and `source`), newest `observed_at` = 2026-10-27T14:53:24.153046Z.
#
# `artifactHandles` is NOT used here even though its rows carry `modifiedAt`: a handle is enumerated from
# this repository's declared evidence surfaces (`artifact_handle_projection.enumerate_surfaces(root)`) and
# has no project attribution on the row. Printing WORK-LAB's newest file mtime under another project's
# name is WL-L01 with a different field, so handles stay out of this decision until a handle states which
# project it belongs to.
#
# Hard rule: no strong row → no value (null). Never 0, never "刚刚", never the snapshot's own
# `generatedAt` — a timestamp the projection manufactured would tell the owner "this is when the source
# last said something" when it means "this is when we woke up".
# ---------------------------------------------------------------------------
STRONG_SOURCE_QUALITIES: frozenset[str] = frozenset({"EXACT_SOURCE"})


def _strong_evidence_map(store: CanonicalStore) -> dict[str, str]:
    """project_id -> newest `observed_at` among that project's strong `source_quality` rows.

    A project with no strong row is simply absent from the map, so the caller answers null. `observed_at`
    is passed through verbatim; the ordering comparison is string ordering over the collector's own
    ISO-8601 `Z` stamps, which is what `_git_states` above already uses for the same column.
    """
    newest: dict[str, str] = {}
    try:
        rows = store.list_source_quality()
    except Exception:  # noqa: BLE001 - an unreadable evidence table is "no evidence", never a guessed time
        return {}
    for row in rows:
        project_id = str(row.get("project_id") or "")
        observed_at = row.get("observed_at")
        if not project_id or not observed_at:
            continue
        if str(row.get("quality") or "") not in STRONG_SOURCE_QUALITIES:
            continue
        candidate = str(observed_at)
        current = newest.get(project_id)
        if current is None or candidate >= current:
            newest[project_id] = candidate
    return newest


def _execution_rows(store: CanonicalStore) -> list[dict[str, Any]]:
    """execution_instances 行 → v3 execution projection (snake_case → camelCase)。"""
    executions: list[dict[str, Any]] = []
    for row in store.list_executions():
        executions.append(
            {
                "executionId": str(row.get("execution_id") or ""),
                "anchorProjectId": row.get("anchor_project_id"),
                "workingArea": row.get("working_area"),
                "state": str(row.get("state") or "UNKNOWN"),
                "stateQuality": str(row.get("state_quality") or "UNKNOWN"),
                "agent": row.get("agent"),
                "sessionId": row.get("session_id"),
                "sourceRef": row.get("source_ref"),
            }
        )
    return executions


def _usage_rows(store: CanonicalStore) -> list[dict[str, Any]]:
    """usage_samples 行 → v3 usage sample（snake_case → camelCase）。"""
    samples: list[dict[str, Any]] = []
    for row in store.list_usage_samples():
        samples.append(
            {
                "projectId": row.get("project_id"),
                "provider": row.get("provider"),
                "model": row.get("model"),
                "inputTokens": row.get("input_tokens"),
                "outputTokens": row.get("output_tokens"),
                "totalTokens": row.get("total_tokens"),
                "costQuality": str(row.get("quality") or "UNKNOWN"),
            }
        )
    return samples


def _ci_rows(store: CanonicalStore) -> list[dict[str, Any]]:
    """ci_runs 行 → v3 ci projection。

    WL-L02 (2026-10-11): ``projectId`` used to be dropped here. Downstream, snapshot_api filters
    per-project with ``[r for r in ci_runs if r.get("projectId") == project_id]``, so a dropped key made
    the predicate false for every row and every project's ``ci`` list came out empty — which a reader
    takes as "this project has no CI", not as "the predicate never held". The column exists in the store
    (``ci_runs.project_id``), so the fix is to carry it.
    """
    runs: list[dict[str, Any]] = []
    for row in store.list_ci_runs():
        runs.append(
            {
                "runId": row.get("run_id"),
                "projectId": row.get("project_id"),
                "workflow": row.get("workflow"),
                "headSha": row.get("head_sha"),
                "status": row.get("status"),
                "conclusion": row.get("conclusion"),
                "sourceRef": row.get("source_ref"),
            }
        )
    return runs


def _agent_platform_map() -> dict[str, str]:
    """Map agent id -> platform display name from the adapter registry.

    Kept dynamic (reads registry, never hard-locks). Unknown agents fall back
    to snapshot_api.AGENT_TO_PLATFORM defaults.
    """
    import json
    from pathlib import Path
    registry_path = Path(__file__).resolve().parents[2] / "config" / "adapter-registry.json"
    mapping: dict[str, str] = {}
    try:
        data = json.loads(registry_path.read_text(encoding="utf-8"))
        for entry in data.get("entries", []):
            aid = entry.get("id")
            display = entry.get("display_name") or entry.get("displayName")
            if aid and display:
                mapping[aid.lower()] = str(display).upper()
    except Exception:
        pass
    return mapping


def _collector_is_fresh(row: dict[str, Any]) -> bool:
    """One predicate for "this collector is currently delivering", shared by coverage and the delivery rows.

    Two surfaces that each decide freshness on their own drift apart the first time one of them is tightened,
    and then the same collector reads healthy in one lane and stale in another.
    """
    return bool(row.get("last_success_at")) \
        and int(row.get("consecutive_failures") or 0) == 0 \
        and not row.get("circuit_open_until")


def _collector_coverage(store: CanonicalStore) -> dict[str, Any]:
    """collector_health 行 → coverage；无运行记录时保持空覆盖。"""
    rows = store.list_collector_health()
    if not rows:
        return {"numerator": None, "denominator": None, "scope": None}
    fresh = sum(1 for row in rows if _collector_is_fresh(row))
    return {"numerator": fresh, "denominator": len(rows), "scope": "collector_health"}


def _collector_delivery_rows(store: CanonicalStore) -> list[dict[str, Any]] | None:
    """Per collector: how many rows it delivered, how many it refused, and why the refusals happened.

    ERR-256 made these facts durable (`collector_health.refused_rows` / `last_refusal_reason`, migration 4);
    this makes them reachable. Coverage alone cannot carry the statement: a source that refused half its rows
    still reads fresh under the liveness predicate, and "the collector is green" over a stream of refusals is
    the silent-filtering lie in a new costume.

    Absent, never empty, on the same rule as `adapterCapabilities`: if the health table cannot be read the key
    is not emitted at all, because `[]` would tell the surface "every source was read and there are none".

    `circuit_open_until` is deliberately NOT projected. It is a `time.monotonic()` value from another process,
    so it means nothing to a reader and would be re-derived wrong; the boolean is the fact.
    """
    try:
        rows = store.list_collector_health()
    except Exception:  # noqa: BLE001 - unreadable source is a gap, not a claim of "no collectors"
        return None
    return [
        {
            "collector": str(row.get("name") or "unknown"),
            "totalRuns": int(row.get("total_runs") or 0),
            "lastRunAt": row.get("last_run_at"),
            "lastSuccessAt": row.get("last_success_at"),
            "consecutiveFailures": int(row.get("consecutive_failures") or 0),
            "circuitOpen": bool(row.get("circuit_open_until")),
            "droppedEvents": int(row.get("dropped_count") or 0),
            "refusedRows": int(row.get("refused_rows") or 0),
            "deliveredRows": int(row.get("delivered_rows") or 0),
            "lastRefusalReason": row.get("last_refusal_reason"),
            "fresh": _collector_is_fresh(row),
        }
        for row in rows
    ]


def _git_states(store: CanonicalStore) -> dict[str, dict[str, Any]]:
    """Return the newest Git observation per approved project.

    The previous implementation returned the first ``scope=git`` row and
    passed it to every project.  That made a cross-project dashboard display
    WORK-LAB's branch/SHA on unrelated projects.  Keep the projection
    project-scoped and choose by observed timestamp (the collector writes one
    row per project).
    """
    latest: dict[str, dict[str, Any]] = {}
    for row in store.list_source_quality():
        if str(row.get("scope") or "") != "git":
            continue
        project_id = str(row.get("project_id") or "")
        payload = row.get("payload") or {}
        if isinstance(payload, str):
            try:
                import json
                payload = json.loads(payload)
            except (TypeError, ValueError):
                payload = {}
        if not project_id or not isinstance(payload, dict) or not payload.get("head_sha"):
            continue
        candidate = {
            "localSha": payload.get("head_sha"),
            "remoteSha": payload.get("remote_sha"),
            "ciSha": payload.get("ci_sha"),
            "branch": payload.get("branch"),
            "dirtyCount": payload.get("dirty_count"),
            "observedAt": row.get("observed_at"),
            "quality": row.get("quality"),
            "freshness": row.get("freshness"),
            "sourceRef": payload.get("sourceRef"),
        }
        current = latest.get(project_id)
        if current is None or str(candidate.get("observedAt") or "") >= str(current.get("observedAt") or ""):
            latest[project_id] = candidate
    return latest


def _git_state(store: CanonicalStore) -> dict[str, Any] | None:
    """Backward-compatible single-project helper (WORK-LAB only).

    WL-L01 (2026-10-11): the second half of the old ``or next(iter(...))`` returned *some* other
    approved project's Git observation and the caller published it under WORK-LAB's name at the top
    level of the snapshot. WORK-LAB either has its own observation or the answer is None — the
    top-level "git" block then reads as nulls/NO_LOCAL_CLAIM, which is unknown, not someone else's.
    """
    return _git_states(store).get("work-lab")


def _task_ledger_read_models(
    store: CanonicalStore,
    *,
    transport_state: str | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """WUI-21: the isolated-trial read models, built from the real Task Ledger or honestly absent.

    The ledger lives in a project-local file (`<project>/.hermes/task-runtime/task-ledger/ledger.json`).
    If it is not there, this returns two lists whose every item answers UNKNOWN / NO_PRODUCER — it does
    NOT create an empty ledger to make the section look populated, and it does not omit the sections
    either: an absent key would read as "the producer was never wired", which is a different claim.
    """
    from pathlib import Path

    from operation_progress import build_isolated_trial, build_operation_progress
    from task_ledger import TaskLedger

    # The ledger path is the one the ledger's own CLI documents (task_ledger.py:585), not a guessed one.
    repo_root = Path(__file__).resolve().parents[2]
    ledger_dir = repo_root / ".hermes" / "task-runtime" / "task-ledger"
    ledger_path = ledger_dir if (ledger_dir / "ledger.json").is_file() else None

    class _Unreadable:
        """A ledger that cannot answer. Every question becomes an UNKNOWN record, not a crash."""

        def get(self, *_a: Any, **_k: Any) -> Any:
            raise OSError("task ledger is not readable from here")

        def detect_zombie(self, *_a: Any, **_k: Any) -> Any:
            raise OSError("task ledger is not readable from here")

    try:
        ledger: Any = TaskLedger(ledger_path) if ledger_path is not None else _Unreadable()
    except Exception:  # noqa: BLE001
        ledger = _Unreadable()

    task_ids: list[str] = []
    try:
        for row in store.list_tasks():
            tid = str(row.get("task_id") or "")
            if tid:
                task_ids.append(tid)
    except Exception:  # noqa: BLE001
        task_ids = []

    # With no ledger there is no task list to answer for; carry one honest placeholder record so the
    # page can say "本仓没有可核对的账本记录" instead of rendering an empty success panel.
    if not task_ids:
        task_ids = ["UNRESOLVED"]

    progress = [build_operation_progress(ledger, tid, transport_state=transport_state) for tid in task_ids]
    trials = [build_isolated_trial(ledger, tid) for tid in task_ids]
    return progress, trials


def build_v3_snapshot(
    store: CanonicalStore,
    index: ApprovedProjectIndex,
    *,
    revision: int,
    events_url: str | None = None,
    transport_state: str = "UNKNOWN",
    freshness_state: str = "UNKNOWN",
    generated_at: str | None = None,
    workspace_evidence: dict[str, Any] | None = None,
    register_root: Path | None = None,
) -> dict[str, Any]:
    """组装 v3 snapshot（transport 由 live-gate verdict 决定，绝不伪造 LIVE）。"""
    coverage = _collector_coverage(store)
    # Observer cross-project view: map project_id -> primary platform from
    # platform_observations (recorded by the platform collector). Null when
    # no observation exists; never fabricated.
    platform_map = {}
    try:
        for row in store.query_platform_observations():
            platform_map.setdefault(row["project_id"], row["platform"])
    except Exception:
        platform_map = {}
    git_states = _git_states(store)
    software_rows = _build_software_projection()
    artifact_handle_rows, artifact_handles_summary, _artifact_handles_reason = (
        _build_artifact_handles_projection())
    operation_progress_rows, isolated_trial_rows = _task_ledger_read_models(
        store, transport_state=transport_state)
    issues_rows, issues_summary, _issues_reason = _build_issues_projection(store, software_rows)
    return build_snapshot(
        revision=revision,
        generated_at=generated_at,
        source_watermark=store.max_watermark(),
        store_projection=store.projection(),
        projects=_project_rows(store, index),
        executions=_execution_rows(store),
        usage=_usage_rows(store),
        ci_runs=_ci_rows(store),
        transport={
            "transportState": transport_state,
            "freshnessState": freshness_state,
            "eventsUrl": events_url,
            "coverageNumerator": coverage["numerator"],
            "coverageDenominator": coverage["denominator"],
            "coverageScope": coverage["scope"],
        },
        # Keep the top-level Git summary for legacy consumers, but pass the
        # project map so each card is sourced from its own repository. The summary is WORK-LAB's own
        # observation or nothing (WL-L01): borrowing another project's row here put a foreign SHA under
        # our name, and per-project cards now never fall back either.
        git_state=git_states.get("work-lab"),
        git_map=git_states,
        workspace=workspace_evidence,
        platform_map=platform_map,
        agent_map=_agent_platform_map(),
        software=software_rows,
        task_records=_task_rows(store, root=register_root),
        adapter_capabilities=_adapter_capability_rows(software_rows),
        artifact_handles=artifact_handle_rows,
        artifact_handles_summary=artifact_handles_summary,
        collector_delivery=_collector_delivery_rows(store),
        operation_progress=operation_progress_rows,
        isolated_trials=isolated_trial_rows,
        issues=issues_rows,
        issues_summary=issues_summary,
    )


def _adapter_capability_rows(software_rows: list[dict[str, Any]]) -> list[dict[str, Any]] | None:
    """P1-03: one capability card per managed client, seven layers each, plus the per-verb dimension.

    The projection lives in ``adapter_capability_projection`` (the single place that decides a layer's
    state) so the read side cannot promote a declared capability into an observed one. If either declared
    source is missing the card set is simply absent from the snapshot — the Agents lane then reports the
    source gap instead of inventing a ladder.

    Absent, never empty: returning [] when the load failed told the UI "the sources were read and nothing
    is declared", which is the opposite claim from "I could not look" and made the honest gap branch
    unreachable in production.

    The verb dimension is loaded alongside the entry probe and is additive and optional in exactly the
    same way: a client with rows gets ``verbEvidence``, a client the probe record says nothing about keeps
    no key at all. An absent file yields ``({}, None)`` from ``load_verb_probe``, and a record that exists
    but cannot be read or whose verb vocabulary disagrees with the contract is degraded HERE to "no verb
    rows for anyone" rather than being laundered into an empty list (which a renderer would read as
    "declares nothing" instead of "I did not look") and rather than removing the seven layers that were
    read successfully. The contract verb list is taken from the projection's own discovery helper, never
    restated here, so the cards and the probe adjudicate verbs against the same closed vocabulary.
    """
    try:
        from adapter_capability_projection import (load_inputs, load_live_probe,
                                                  project_adapter_capabilities)
        from snapshot_api import _now as _snapshot_now
        registry, conformance, matrix = load_inputs(_ROOT)
        probe_rows, probe_at = load_live_probe(_ROOT)
    except Exception:  # noqa: BLE001 - a failed read is a source gap, not an empty capability set
        return None
    # Everything the seven layers need, without the additive verb dimension. Reused by both the verb-on and
    # the degraded-to-verbless calls so the ladder is byte-identical whichever way the verb record reads.
    layers_only = {
        "registry": registry,
        "conformance": conformance,
        "matrix": matrix,
        "software_rows": software_rows,
        "live_probe_rows": probe_rows,
        "live_probe_at": probe_at,
        "observed_at": _snapshot_now(),
    }
    try:
        from adapter_capability_projection import load_verb_probe, contract_verb_vocabulary
        verb_rows, verb_at = load_verb_probe(_ROOT)
        contract_verbs = contract_verb_vocabulary(_ROOT)
    except Exception:  # noqa: BLE001 - an unreadable or disagreeing verb record is "did not look", no verbEvidence
        return project_adapter_capabilities(**layers_only)
    try:
        return project_adapter_capabilities(
            **layers_only, verb_rows=verb_rows, verb_probe_at=verb_at, contract_verbs=contract_verbs)
    except Exception:  # noqa: BLE001 - a malformed verb row must not remove the honest seven-layer ladder
        return project_adapter_capabilities(**layers_only)


def _task_rows(store: CanonicalStore, *, root: Path | None = None) -> list[dict[str, Any]]:
    """Task detail records for the Work lane, projected by the unique Snapshot API.

    ``list_tasks()`` is the canonical store's own read; the projection lives in
    ``snapshot_api.project_task_record`` so there is exactly one place that decides what a task looks
    like on the read side. The checkpoint VALUES stay in the store — a read-only projection carries the
    key names and a digest, never the workflow text.

    The live open-task register is appended after the store rows and each of its records carries its own
    provenance (``register.source == "OPEN_TASK_REGISTER"``), because the two answer different questions:
    the tasks table is machine-written execution state (measured 0 rows on this machine, 2026-10-27), the
    register is what the owner wrote down by hand (measured 42 rows). The merge, the id-conflict marker and
    the unreadable marker all live in ``open_task_register_projection`` so this file holds no second
    opinion about the register's shape.
    """
    from snapshot_api import project_task_record

    rows = [project_task_record(row) for row in store.list_tasks()]
    return merge_task_rows(rows, _build_register_task_rows(root=root))
