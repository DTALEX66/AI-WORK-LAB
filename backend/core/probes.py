# SPDX-License-Identifier: MIT
"""Controlled local probes — the only thing that can earn a qualification.

Two kinds, and the difference matters (audit F10):

* a **live read probe** asks the real subject this service is actually serving:
  the unified store file, the design runtime database, the WORK canonical store.
  It reads; it never writes, never starts a collector, never probes a model,
  never touches a user software directory and never opens a remote connection.
  Its evidence is the row count and digest it observed, with the store path.
* a **scratch probe** performs an operation against a temporary fixture. That
  proves the machinery runs, and it is stamped ``data_origin=test``, so it can
  never grant a live qualification. Recording it at all is useful: it is the
  counter-example that keeps a `test` record from being read as `VERIFIED`.

`loopback_http` probes the port this process really listens on, from a *separate*
child process, so "the HTTP surface works" is an observation of the socket
rather than a function that returned a dict.

Nothing here probes Photoshop, Illustrator, ComfyUI, a model, or an external
executor. Those stay NOT_PROBED behind the Human Gate, and no local success
propagates into them.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from backend.core.qualifications import (loopback_http_probe, probe_record,
                                         scratch_roundtrip_probe)

#: A probe query is a probe, not a user request. It must not be able to write.
KNOWLEDGE_PROBE_QUERY = "规范"
PLAN_PROBE_LIMIT = 200


def _observed(detail: str, **counts) -> tuple[bool, str]:
    return True, detail + " " + json.dumps(counts, ensure_ascii=False, sort_keys=True)


def run_read_probes(api) -> list[dict]:
    """Append one live read probe per capability whose subject exists locally."""
    version = api.candidate()
    ledger = api.qualifications
    written: list[dict] = []

    def record(capability_id, operation, subject, ok, detail, *, evidence=None,
                origin="live", dependency="SATISFIED", authorization="NOT_REQUIRED",
                connection="NOT_REQUIRED", **observation):
        if observation:
            detail = detail + " observed " + json.dumps(observation, ensure_ascii=False,
                                                        sort_keys=True)
        row = probe_record(capability_id=capability_id, operation=operation,
                           scope="local_read", subject=subject, version=version,
                           outcome="VERIFIED" if ok else "FAILED",
                           evidence_refs=list(evidence or ["probe:" + capability_id]),
                           detail=detail, data_origin=origin, dependency=dependency,
                           authorization=authorization, connection=connection,
                           command="backend.core.probes.run_read_probes (read-only)")
        ledger.append(row)
        written.append(row)
        return row

    # -- unified store: the rows this service actually serves -----------------
    try:
        counts = {table: api.unified.conn.execute(
            "SELECT COUNT(*) AS n FROM " + table).fetchone()["n"]
            for table in ("projects", "tasks", "attempts", "results", "verifications")}
        record("core.projects", "projects.read_write", str(api.unified.path), True,
               "live project rows read back", evidence=["probe:core.projects/count"], **counts)
        record("core.tasks", "tasks.attempts.results.verifications", str(api.unified.path), True,
               "live task/attempt/result/verification rows read back",
               evidence=["probe:core.tasks/count"], **counts)
    except sqlite3.Error as exc:
        for capability_id, operation in (("core.projects", "projects.read_write"),
                                         ("core.tasks", "tasks.attempts.results.verifications")):
            record(capability_id, operation, str(api.unified.path), False,
                   "store unreadable: " + type(exc).__name__, dependency="UNKNOWN")

    # -- design runtime: real searches against the migrated stores -------------
    try:
        knowledge = api._knowledge_factory(api.design_service).search(
            query=KNOWLEDGE_PROBE_QUERY, offset=0, limit=1)
        record("design.knowledge.search", "knowledge.search",
               str(api.design_service.db_path if hasattr(api.design_service, "db_path")
                   else api.workspace_root),
               "total" in knowledge,
               "probe query " + repr(KNOWLEDGE_PROBE_QUERY) + " answered through the migrated "
               "knowledge search",
               evidence=["probe:design.knowledge.search/total"],
               total=knowledge.get("total"), indexed=(knowledge.get("index") or {}).get("rows"),
               strategy=knowledge.get("strategy"))
    except (ValueError, sqlite3.Error, OSError) as exc:
        record("design.knowledge.search", "knowledge.search", "design runtime", False,
               "knowledge search did not answer: " + type(exc).__name__, dependency="UNKNOWN")

    try:
        design_projects = [row for row in api.unified.list_projects() if row["source"] == "design"]
        plans = api._plans_factory(api.design_service)
        counted = 0
        for project in design_projects:
            listed = plans.list(project["root_path"], offset=0, limit=PLAN_PROBE_LIMIT)
            counted += int(listed.get("total") or 0)
        record("design.plans", "plans.read", str(api.workspace_root), True,
               "plan inventory read for every registered design project",
               evidence=["probe:design.plans/count"], projects=len(design_projects), plans=counted)
    except (ValueError, sqlite3.Error, OSError) as exc:
        record("design.plans", "plans.read", str(api.workspace_root), False,
               "plan read did not answer: " + type(exc).__name__, dependency="UNKNOWN")

    try:
        profiles = api._profiles_factory(api.design_service).list(offset=0, limit=1)
        record("design.target_profiles", "target_profiles.read", str(api.workspace_root),
               "total" in profiles, "target profile inventory read back",
               evidence=["probe:design.target_profiles/count"], total=profiles.get("total"))
    except (ValueError, sqlite3.Error, OSError) as exc:
        record("design.target_profiles", "target_profiles.read", str(api.workspace_root), False,
               "target profile read did not answer: " + type(exc).__name__, dependency="UNKNOWN")

    # -- WORK solution library: the read model F05 now serves -----------------
    try:
        from domains.work.control import solution_library
        view = solution_library.store_view(api.work.store, query="")
        record("work.solution_library.search", "solutions.search",
               str(getattr(api.work.store, "path", "canonical")),
               view.get("status") in ("OK", "EMPTY", "NO_MATCH"),
               "solution read model answered with its typed status",
               evidence=["probe:work.solution_library.search/status"],
               status=view.get("status"),
               solutions_read=(view.get("summary") or {}).get("solutionsRead"))
    except Exception as exc:  # noqa: BLE001 - a failed probe is recorded as FAILED, not hidden
        record("work.solution_library.search", "solutions.search", "work store", False,
               "solution read model did not answer: " + type(exc).__name__, dependency="UNKNOWN")

    # -- WORK observer snapshot surface ---------------------------------------
    try:
        from backend.core.work_surfaces import observer_probe
        snapshot = observer_probe(api)
        record("work.observer.read_surface", "observer.snapshot_reads",
               str(snapshot.get("subject")), bool(snapshot.get("ok")),
               str(snapshot.get("detail")), evidence=["probe:work.observer.read_surface"],
               dependency=snapshot.get("dependency", "UNKNOWN"))
    except Exception as exc:  # noqa: BLE001
        record("work.observer.read_surface", "observer.snapshot_reads", "work control plane",
               False, "observer surface unavailable: " + type(exc).__name__,
               dependency="UNKNOWN")

    # -- a scratch roundtrip is recorded as test, on purpose -------------------
    def runner(path: Path) -> tuple[bool, str]:
        from backend.core.unified_store import UnifiedStore
        store = UnifiedStore(path)
        project = store.register_project(source="design", display_name="probe-fixture")
        task = store.create_task(project_id=project["project_id"], kind="design",
                                 title="probe task", input_refs=[], acceptance={})
        store.close()
        return (bool(task["task_id"]), "scratch envelope wrote and read back one task")

    ledger.append(scratch_roundtrip_probe(capability_id="data.migration",
                                          operation="business_data.migrate_verify",
                                          version=version, runner=runner))
    return written


def run_http_probe(api, *, base_url: str, port: int, token: str) -> dict:
    """Probe the loopback port from a child process; record what it observed.

    The token is handed to the child on stdin, exactly as the launcher received it:
    recording this evidence must not put the service credential into argv, a URL or
    a file on disk.
    """
    row = loopback_http_probe(capability_id="backend.http_surface",
                              operation="http.loopback_api", version=api.candidate(),
                              base_url=base_url, path="/api/v1/health", command=[str(port)],
                              token=token)
    api.qualifications.append(row)
    return row
