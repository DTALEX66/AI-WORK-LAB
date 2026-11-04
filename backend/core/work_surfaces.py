# SPDX-License-Identifier: MIT
"""WORK Observer / Control surfaces mounted on the one unified kernel (audit F09).

The audit's finding was twofold: a clean process could not import the sidecar at
all, and the unified service mounted none of the WORK consumer surface, so the
repair loop could not be read as "the old interfaces survived". Both are fixed
here without creating a second control plane or a second task ledger.

How the second-state risk is avoided: every read model is called through the
**same** ``CanonicalStore`` the ``WorkPacks`` adapter already owns
(``api.work.store``), and ``ControlPlane`` is constructed with that store injected.
``WorkflowSidecar`` and ``build_plane`` each open their own
``runtime_root/canonical.sqlite`` — instantiating either here would have created a
second durable truth, which is exactly what the project rules forbid.

Honest degradation: if the migrated machinery cannot answer, the route returns a
typed ``BLOCKED``/``SOURCE_ABSENT`` with the exception's name rather than an empty
list or a 200 that reads as "everything is fine". A 200 is not evidence that a
projection is correct, so each response carries the subject it read.
"""
from __future__ import annotations

import ipaddress
import json
from datetime import datetime, timezone
from pathlib import Path

#: Old WORK consumer path -> what serves it now. Published over HTTP so a
#: downstream reader does not have to guess the mapping.
COMPATIBILITY_MAP = {
    "/healthz": "/api/work/observer/health",
    "/api/projection": "/api/work/observer/projection",
    "/api/v1/snapshot": "/api/work/observer/snapshot",
    "/api/v1/repair-packs": "/api/work/observer/repair-packs",
    "/api/v1/solutions": "/api/work/observer/solutions",
    "/api/v1/evidence-range": "/api/work/observer/evidence-range",
    "/api/control/descriptor": "/api/work/control/descriptor",
    "/api/control/receipts/<task_id>": "/api/work/control/receipts/<task_id>",
    "/api/control/operations": "/api/work/control/operations",
    "/api/v1/events": "/api/work/observer/events?frames=N (bounded snapshot frames; the continuous watcher stream stays with the standalone sidecar)",
}

OBSERVER_WRITE_REFUSALS = "/api/work/observer/refusals"

#: A bounded stream by default. An unbounded one here would be a watcher thread the
#: unified kernel does not run, so the route says what it is instead.
MAX_EVENT_FRAMES = 5


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def handler_qs(handler) -> dict:
    from urllib.parse import parse_qs, urlsplit
    return parse_qs(urlsplit(handler.path).query, keep_blank_values=True)


def _blocked(handler, code: str, detail: str, *, subject: str) -> None:
    return handler.send_json(503, {"status": "BLOCKED", "code": code, "detail": detail,
                                   "subject": subject, "observed_at": _now(),
                                   "note": "a migrated read model that cannot answer is reported "
                                           "as unable, never as an empty success"})


def _sidecar_available():
    try:
        from domains.work.control import sidecar  # noqa: F401
        from domains.work.control import composition_root  # noqa: F401
        return True
    except Exception as exc:  # noqa: BLE001 - the import gap is the finding to report
        return type(exc).__name__ + ": " + str(exc)[:200]


def observer_health(api, handler):
    return handler.send_json(200, {"status": "ok", "readOnlyControl": True,
                                   "ledgerOwner": "workflow-assistance", "observerMutation": False,
                                   "served_by": "backend.core.work_surfaces (unified kernel)",
                                   "store": str(getattr(api.work.store, "path", "canonical"))})


def observer_projection(api, handler):
    try:
        canonical = api.work.store.projection()
    except Exception as exc:  # noqa: BLE001
        return _blocked(handler, "WORK_STORE_UNREADABLE", str(exc)[:200],
                        subject=str(getattr(api.work.store, "path", "canonical")))
    statuses = canonical.get("tasks_by_status") or {}
    return handler.send_json(200, {
        "schema_version": "workflow/sidecar-projection/v1",
        # The unified process runs no watcher thread, so the transport mode is a
        # stated fact, not a guess: reads are on-demand, nothing is pushed.
        "mode": "ON_DEMAND_READ",
        "health": {"status": "ok", "readOnlyControl": True, "observerMutation": False},
        "integrity": canonical.get("integrity"),
        "telemetry": {"count": canonical.get("telemetry_events")},
        "tasks": {"count": sum(statuses.values()), "by_status": statuses},
        "usage": canonical.get("usage_summary"),
        "ci": canonical.get("ci_summary"),
        "observed_at": canonical.get("observed_at"),
        "store": str(getattr(api.work.store, "path", "canonical")),
    })


def observer_snapshot(api, handler):
    from domains.work.control import composition_root
    try:
        store = api.work.store
        index = composition_root.load_approved_index(store)
        revision = store.seed_revision()
        snapshot = composition_root.build_v3_snapshot(
            store, index, revision=revision, events_url=None,
            transport_state="ON_DEMAND_READ", freshness_state="NOT_PROBED",
            generated_at=_now(), workspace_evidence=None,
            register_root=api.workspace_root)
    except Exception as exc:  # noqa: BLE001
        return _blocked(handler, "WORK_SNAPSHOT_UNAVAILABLE",
                        type(exc).__name__ + ": " + str(exc)[:300],
                        subject="domains.work.control.composition_root.build_v3_snapshot")
    return handler.send_json(200, snapshot)


def observer_solutions(api, handler, *, query="", software_id=None, limit=20):
    from domains.work.control import solution_library
    try:
        view = solution_library.store_view(api.work.store, query=query or "",
                                          software_id=software_id or None, limit=limit)
    except Exception as exc:  # noqa: BLE001
        return _blocked(handler, "WORK_SOLUTION_STORE_UNREADABLE", str(exc)[:200],
                        subject=str(getattr(api.work.store, "path", "canonical")))
    return handler.send_json(200, view)


def observer_repair_packs(api, handler):
    from domains.work.workflow_core import repair_pack_projection
    from domains.work.workflow_core import issue_projection
    try:
        issues, summary, absent_reason = issue_projection.load_issues(api.work.store)
    except Exception as exc:  # noqa: BLE001
        return _blocked(handler, "WORK_ISSUE_PROJECTION_UNAVAILABLE", str(exc)[:200],
                        subject="issue_projection.load_issues")
    if issues is None:
        return handler.send_json(200, {"schemaVersion": repair_pack_projection.PACKS_VIEW_SCHEMA_VERSION
                                       if hasattr(repair_pack_projection, "PACKS_VIEW_SCHEMA_VERSION")
                                       else "worklab/repair-packs-view/v1",
                                       "status": "SOURCE_ABSENT",
                                       "reason": repr(absent_reason), "packs": [],
                                       "note": "no source answered; this is not 'nothing to hand off'"})
    return handler.send_json(200, {"schemaVersion": "worklab/repair-packs-view/v1",
                                   "status": "OK", "issues": issues, "summary": summary,
                                   "generated_at": _now()})


def observer_evidence_range(api, handler, *, handle, offset, limit, expected_digest=None):
    from domains.work.control import evidence_range_reader
    address = getattr(handler, "client_address", None)
    peer = str(address[0]) if address else ""
    if not peer:
        # The old fallback was the literal "127.0.0.1": a handler that carried no peer
        # information was trusted as loopback by default, which is this gate failing open.
        return handler.send_json(403, {"schema_version": evidence_range_reader.SCHEMA_VERSION,
                                       "status": "REFUSED", "reason_code": "PEER_UNKNOWN",
                                       "reason": "没有对端地址信息，环回判定无从做起。", "content": None})
    try:
        loopback = ipaddress.ip_address(peer).is_loopback
    except ValueError:
        loopback = False
    if not loopback:
        return handler.send_json(403, {"schema_version": evidence_range_reader.SCHEMA_VERSION,
                                       "status": "REFUSED", "reason_code": "PEER_NOT_LOOPBACK",
                                       "reason": "证据区间只从环回地址提供。", "content": None})
    document = evidence_range_reader.read_range(
        handle=handle, root=api.workspace_root, offset=offset, limit=limit,
        expected_digest=expected_digest,
        evidence_roots=evidence_range_reader.declared_evidence_roots(api.workspace_root))
    return handler.send_json(200, document)


def refuse_observer_write(api, handler, match):
    """An Observer write is refused *and recorded*, so the refusal is auditable."""
    method = getattr(handler, "command", "") or getattr(handler, "requestline", "").split(" ")[0]
    record = {"refused_at": _now(), "method": method, "path": handler.path,
              "reason_code": "OBSERVER_IS_READ_ONLY",
              "reason": "Observer 面只读；写请求被拒绝并且本条拒绝记录已落盘",
              "store": str(getattr(api.work.store, "path", "canonical"))}
    _append_refusal(api, record)
    return handler.send_json(405, record)


def observer_events(api, handler, match):
    """A bounded SSE snapshot stream, encoded by the migrated renderer.

    The old sidecar route ``/api/v1/events`` was a long-lived watcher socket: an
    initial ``snapshot`` frame, then deltas pushed by ``SseRevisionHub`` while a
    background watcher kept re-reading the store. Mounting *that* here would mean
    starting a second watcher thread with its own idea of freshness, on a process
    whose transport state is honestly ``ON_DEMAND_READ``.

    So this route gives the SSE contract the consumer actually parses — the frame
    format comes from the migrated ``render_sse_frames``, ids come from the store's
    own monotonic revision, and every frame is a fresh read — and keeps it bounded
    (``?frames=``, default 1, capped) instead of pretending to a push stream it is
    not running. A client that wants the continuous watcher still has the standalone
    sidecar, and that difference is stated in the response rather than hidden.
    """
    from domains.work.control import sse_hub
    try:
        frames = int(handler_qs(handler).get("frames", ["1"])[0])
    except (ValueError, IndexError):
        return handler.send_json(400, {"status": "REFUSED", "code": "EVENT_FRAMES_MALFORMED"})
    frames = max(1, min(frames, MAX_EVENT_FRAMES))
    revision = api.work.store.seed_revision()
    messages = []
    for index in range(frames):
        try:
            canonical = api.work.store.projection()
        except Exception as exc:  # noqa: BLE001 - a failed read is reported, not swallowed
            return _blocked(handler, "WORK_STORE_UNREADABLE", type(exc).__name__ + ": "
                            + str(exc)[:200], subject=str(getattr(api.work.store, "path", "")))
        messages.append(sse_hub.SSEMessage(
            event_id=str(revision + index), event_type=sse_hub.SNAPSHOT.lower(),
            data={"schema": "ai-work-lab/observer-events/v1", "observed_at": _now(),
                  "transport_state": "ON_DEMAND_READ", "frames": frames, "frame": index,
                  "integrity": canonical.get("integrity"),
                  "tasks_by_status": canonical.get("tasks_by_status"),
                  "continuous_stream": False,
                  "note": "本路由按帧现读现发；持续推送的 watcher 仍属独立 sidecar，未接入统一内核"}))
    body = sse_hub.render_sse_frames(messages, include_retry=True, include_heartbeat=False)
    handler.send_response(200)
    handler.send_header("Content-Type", "text/event-stream; charset=utf-8")
    handler.send_header("Cache-Control", "no-store")
    handler.send_header("X-Accel-Buffering", "no")
    handler.send_header("Content-Length", str(len(body.encode("utf-8"))))
    handler.end_headers()
    try:
        handler.wfile.write(body.encode("utf-8"))
        handler.wfile.flush()
    except OSError:
        pass
    return None


def observer_refusals(api, handler):
    path = Path(api.local_root) / "observer-write-refusals.jsonl"
    rows = []
    if path.is_file():
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                rows.append(json.loads(line))
            except ValueError:
                rows.append({"unparsed_line": line[:200]})
    return handler.send_json(200, {"schema": "ai-work-lab/observer-write-refusal/v1",
                                   "path": str(path), "count": len(rows), "refusals": rows[-50:]})


def _append_refusal(api, record: dict) -> None:
    path = Path(api.local_root) / "observer-write-refusals.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def control_plane(api):
    """One ControlPlane over the store the rest of the service already owns."""
    cached = getattr(api, "_control_plane", None)
    if cached is not None:
        return cached
    from domains.work.control import control_service
    from domains.work.workflow_core.canonical_store import CanonicalStore
    plane = control_service.ControlPlane(
        api.work.store if isinstance(api.work.store, CanonicalStore) else
        CanonicalStore(api.work.store.path),
        project_root=api.repo_root,
        evidence_ceiling="SYNTHETIC",
        receipts_path=Path(api.local_root) / control_service.RECEIPTS_PATH,
        grants_path=Path(api.local_root) / control_service.TRUSTED_GRANTS_PATH)
    api._control_plane = plane
    return plane


def control_descriptor(api, handler):
    try:
        plane = control_plane(api)
    except Exception as exc:  # noqa: BLE001
        return _blocked(handler, "CONTROL_PLANE_UNAVAILABLE",
                        type(exc).__name__ + ": " + str(exc)[:300],
                        subject="domains.work.control.control_service.ControlPlane")
    descriptor = plane.descriptor()
    descriptor["served_by"] = "backend.core.work_surfaces (unified kernel)"
    descriptor["evidence_ceiling"] = plane.evidence_ceiling
    descriptor["project_root"] = str(plane.project_root)
    return handler.send_json(200, descriptor)


def control_receipts(api, handler, match):
    try:
        plane = control_plane(api)
    except Exception as exc:  # noqa: BLE001
        return _blocked(handler, "CONTROL_PLANE_UNAVAILABLE", str(exc)[:300], subject="control plane")
    return handler.send_json(200, {"task_id": match[1],
                                   "receipts": plane.receipts_for(match[1], limit=20)})


def control_execute(api, handler):
    """The single CONTROL write entry, with the migrated gate intact.

    The plane itself runs the jsonschema contract, the OPERATIONS allowlist,
    scope/boundary checks and the PermissionGate; a HIGH-risk target needs a human
    and a grant that resolves. This mount adds the kernel guard (already applied),
    the loopback peer rule the standalone server enforced, and a data-origin stamp
    so a control receipt written by this build can never be read as live evidence
    without a resolved grant.
    """
    try:
        plane = control_plane(api)
    except Exception as exc:  # noqa: BLE001
        return _blocked(handler, "CONTROL_PLANE_UNAVAILABLE",
                        type(exc).__name__ + ": " + str(exc)[:300], subject="control plane")
    address = getattr(handler, "client_address", None)
    peer = str(address[0]) if address else ""
    if not peer:
        # Same fail-open default as the evidence-range gate: no peer information used to answer
        # "127.0.0.1", so the check that exists to keep the control plane loopback-only was
        # skipped by the connections that said least about where they came from.
        return handler.send_json(403, {"status": "REFUSED", "code": "PEER_UNKNOWN",
                                       "reason": "控制面缺少对端地址，无法判定环回来源"})
    try:
        if not ipaddress.ip_address(peer).is_loopback:
            return handler.send_json(403, {"status": "REFUSED", "code": "PEER_NOT_LOOPBACK",
                                           "reason": "控制面只接受环回对端"})
    except ValueError:
        return handler.send_json(403, {"status": "REFUSED", "code": "PEER_UNPARSEABLE"})
    body = handler.body(fields={}, optional={}, limit=65536)
    if not isinstance(body, dict):
        return handler.send_json(400, {"status": "REFUSED", "code": "CONTROL_REQUEST_MALFORMED"})
    result = plane.execute(body)
    status = 200 if str(result.get("status") or "").upper() not in (
        "REFUSED", "DENIED", "FAILED") else 409
    return handler.send_json(status, result)


def observer_probe(api) -> dict:
    """What the live probe asks: can the migrated read model actually answer?

    Returns ``{ok, subject, detail, dependency}`` for backend.core.probes — a
    failed read is ``dependency=MISSING`` and an un-importable module is
    ``dependency=UNKNOWN``, so the catalog reports a gap instead of a pass.
    """
    availability = _sidecar_available()
    if availability is not True:
        return {"ok": False, "subject": "domains.work.control",
                "detail": "observer modules did not import in this process: " + str(availability),
                "dependency": "UNKNOWN"}
    try:
        canonical = api.work.store.projection()
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "subject": str(getattr(api.work.store, "path", "canonical")),
                "detail": "canonical projection failed: " + type(exc).__name__,
                "dependency": "MISSING"}
    return {"ok": True, "subject": str(getattr(api.work.store, "path", "canonical")),
            "detail": "observer projection read through the shared canonical store",
            "dependency": "SATISFIED",
            "integrity": canonical.get("integrity")}


def surface_map(api, handler):
    availability = _sidecar_available()
    return handler.send_json(200, {
        "schema": "ai-work-lab/work-surface-map/v1",
        "compatibility_map": COMPATIBILITY_MAP,
        "observer_writes": "refused with a recorded 405; see GET /api/work/observer/refusals",
        "control_write_entry": "POST /api/work/control/operations",
        "single_state_owner": "domains/work/workflow_core/canonical_store via backend.core.workpacks",
        "sidecar_importable": availability is True,
        "import_blocker": None if availability is True else availability,
        "does_not_say": ["HTTP 200 on a projection is not evidence the projection is correct",
                         "this mount does not run collectors, watchers or an SSE stream; "
                         "transport state is reported as ON_DEMAND_READ / NOT_PROBED"],
    })


#: Route table entries appended to V1_ROUTES. Patterns are regex fragments the
#: kernel compiles, matching the migrated ``Route`` convention.
def build_routes():
    from design_lab.http_service import Route
    observer_read_paths = ("health", "projection", "snapshot", "repair-packs", "solutions",
                           "evidence-range", "events")
    table = [
        Route("GET", "/api/work/observer/health", "_work_observer_health", exact=True),
        Route("GET", "/api/work/observer/projection", "_work_observer_projection", exact=True),
        Route("GET", "/api/work/observer/snapshot", "_work_observer_snapshot", exact=True),
        Route("GET", "/api/work/observer/repair-packs", "_work_observer_repair_packs", exact=True),
        Route("GET", "/api/work/observer/solutions", "_work_observer_solutions", exact=True,
              path_only=True),
        Route("GET", "/api/work/observer/evidence-range", "_work_observer_evidence_range",
              exact=True, path_only=True),
        Route("GET", "/api/work/observer/events", "_work_observer_events", exact=True,
              path_only=True),
        Route("GET", OBSERVER_WRITE_REFUSALS, "_work_observer_refusals", exact=True),
        Route("GET", "/api/work/surface-map", "_work_surface_map", exact=True),
        Route("GET", "/api/work/control/descriptor", "_work_control_descriptor", exact=True),
        Route("GET", "/api/work/control/receipts/([0-9A-Za-z_-]{1,120})",
              "_work_control_receipts"),
        Route("POST", "/api/work/control/operations", "_work_control_execute", exact=True),
    ]
    for method in ("POST", "PUT", "PATCH", "DELETE"):
        for leaf in observer_read_paths:
            table.append(Route(method, "/api/work/observer/" + leaf,
                               "_work_observer_write_refused", exact=True))
        for leaf in ("descriptor", "receipts", "operations"):
            if method != "POST":
                table.append(Route(method, "/api/work/control/" + leaf,
                                   "_work_control_write_refused", exact=True))
    return table


WORK_SURFACE_ROUTES = build_routes()
