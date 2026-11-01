"""Local-first Workflow Assistance sidecar with read-only health/projection routes."""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import ipaddress
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import os
from pathlib import Path
import queue
import sys
import threading
import time
from typing import Any
from urllib.parse import parse_qs, urlsplit
import uuid

# Module roots, derived from this file, so the documented entry works as documented:
# `python services/orchestration/sidecar.py --project-root . ...` (apps/observer/README.md)
# and `apps/observer/start-observer.cmd` both run it with nothing on PYTHONPATH, and running a
# script puts only ITS directory on sys.path. The other roots were supplied by
# `tests/conftest.py` alone -- which is exactly why the gap survived: every green CI run came
# through the pytest bootstrap, and the shipped launcher came through none of it. Measured
# 2026-10-18: the documented command died at `from canonical_store import CanonicalStore`
# with `ModuleNotFoundError` in a clean shell.
for _relative in (
    "../../packages/client-neutral-core/scripts",
    "../receipts",
    "../policy",
    "../authority",
):
    _candidate = (Path(__file__).resolve().parent / _relative).resolve()
    if _candidate.is_dir() and str(_candidate) not in sys.path:
        sys.path.insert(0, str(_candidate))

from sidecar_lock import SingleInstanceLock
from canonical_store import CanonicalStore
import evidence_range_reader
from sse_hub import HEARTBEAT_SECONDS, LIVE, LiveProjection, SNAPSHOT, STALE, render_sse_frames
from composition_root import build_v3_snapshot, load_approved_index
import repair_pack_projection
import solution_library
from live_gate import evaluate_live
from sse_revision import SseRevisionHub
from snapshot_validator import validate_snapshot
from workspace_evidence import load_workspace_evidence

COLLECTOR_FRESHNESS_SECONDS = 60.0
CANONICAL_READBACK_FRESHNESS_SECONDS = 60.0
REPAIR_PACKS_VIEW_SCHEMA_VERSION = "worklab/repair-packs-view/v1"
SOLUTION_SEARCH_SCHEMA_VERSION = solution_library.SEARCH_SCHEMA_VERSION


class WorkflowSidecar:
    def __init__(self, project_root: Path, runtime_root: Path) -> None:
        self.project_root = project_root.resolve()
        self.runtime_root = runtime_root.resolve()
        self.store = CanonicalStore(self.runtime_root / "canonical.sqlite")
        self.store.register_project("work-lab", str(self.project_root), display_name=self.project_root.name)
        self.live = LiveProjection(self.store)
        # WLGM composition root: approved index + persistent SSE revision hub.
        self.index = load_approved_index(self.store)  # 失败时降级空索引，不 raise
        # Bounded, tracked repository evidence is loaded once per sidecar
        # lifetime. It is typed as PLAN/STATIC_BASELINE/HISTORY and never
        # promoted to LIVE telemetry.
        self.workspace_evidence = load_workspace_evidence(self.project_root)
        self._revision = self.store.seed_revision()
        # Seed the hub from the persisted revision so a restart never rolls
        # Last-Event-ID cursors back; publishes stay monotonic across the
        # worker's own projection revisions and this sidecar's delta stream.
        self.revision_hub = SseRevisionHub(seed_revision=self._revision)
        self._last_heartbeat_at: float | None = None
        self._last_write_at: float | None = None
        # Last successful canonical readback (watcher). LIVE requires a fresh
        # readback, not merely a live watcher thread.
        self._last_canonical_ok_at: float | None = None
        self._sse_connection_count = 0
        self._sse_connected_since: float | None = None
        self._sse_connection_lock = threading.Lock()
        self._events_url: str | None = None
        self._watch_stop = threading.Event()
        self._watch_thread: threading.Thread | None = None
        self._worker: Any | None = None
        self._worker_supervisor: Any | None = None
        self._worker_thread: threading.Thread | None = None
        self._expected_collector_names: frozenset[str] = frozenset()

    def _canonical_fingerprint(self) -> str:
        canonical = self.store.projection()
        stable = {
            "integrity": canonical["integrity"],
            "tables": canonical["tables"],
            "newest": self.store.newest_changes(),
            "tasks_by_status": canonical["tasks_by_status"],
            "telemetry_events": canonical["telemetry_events"],
            "usage_summary": canonical["usage_summary"],
            "ci_summary": canonical["ci_summary"],
            "collector_health": [
                {
                    "name": row.get("name"),
                    "total_runs": row.get("total_runs"),
                    "last_run_at": row.get("last_run_at"),
                    "last_success_at": row.get("last_success_at"),
                    "consecutive_failures": row.get("consecutive_failures"),
                    "circuit_open_until": row.get("circuit_open_until"),
                }
                for row in self.store.list_collector_health()
            ],
        }
        return json.dumps(stable, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

    def start_live_updates(self, interval_seconds: float = 0.25) -> None:
        """Publish canonical deltas written by the separate Workflow worker."""
        if interval_seconds <= 0:
            raise ValueError("live update interval must be positive")
        if self._watch_thread and self._watch_thread.is_alive():
            return
        self._watch_stop.clear()
        last_fingerprint = self._canonical_fingerprint()
        self._last_canonical_ok_at = time.time()
        # P0-4: LIVE only comes from the live gate; the watcher must not
        # declare LIVE by itself.
        self.live.set_mode(SNAPSHOT)

        def _watch() -> None:
            nonlocal last_fingerprint
            while not self._watch_stop.wait(interval_seconds):
                try:
                    current = self._canonical_fingerprint()
                except Exception:  # fail closed if canonical readback is unavailable
                    self._last_canonical_ok_at = None
                    if self.live.mode() != STALE:
                        self.live.set_mode(STALE)
                    continue
                self._last_canonical_ok_at = time.time()
                if current != last_fingerprint:
                    previous_write_at = self._last_write_at
                    self._last_write_at = time.time()
                    try:
                        self.publish_observed()
                    except Exception:  # fail closed and retry the same fingerprint
                        self._last_write_at = previous_write_at
                        if self.live.mode() != STALE:
                            self.live.set_mode(STALE)
                        continue
                    last_fingerprint = current

        thread = threading.Thread(
            target=_watch,
            daemon=True,
            name="workflow-sidecar-canonical-watch",
        )
        self._watch_thread = thread
        try:
            thread.start()
        except Exception:
            self._watch_stop.set()
            self._watch_thread = None
            raise

    def stop_live_updates(self) -> None:
        self._watch_stop.set()
        thread = self._watch_thread
        if thread and thread is not threading.current_thread():
            thread.join(timeout=2.0)
        if thread is not None and thread.is_alive():
            # Keep the store open while an in-flight projection read still owns
            # it. A later close retry can finish once the watcher returns.
            raise RuntimeError("live_update_shutdown_timeout")
        self._watch_thread = None

    def start_worker(self, tick_seconds: float = 30.0, collectors: list[Any] | None = None) -> None:
        """Run the Workflow-owned producer under the sidecar lifecycle."""
        if self.worker_running():
            return
        from collectors import build_standard_collectors
        from durable_worker import WorkerSupervisor, make_worker

        selected_collectors = build_standard_collectors(self.project_root) if collectors is None else collectors
        expected_names = frozenset(
            [*(getattr(collector, "__name__", collector.__class__.__name__) for collector in selected_collectors), "worker_loop"]
        )
        if len(expected_names) != len(selected_collectors) + 1:
            raise ValueError("collector names must be unique")
        worker = make_worker(
            self.store,
            project_id="work-lab",
            tick_seconds=tick_seconds,
            collectors=selected_collectors,
        )
        supervisor = WorkerSupervisor(self.runtime_root, worker)
        supervisor.start()
        thread = threading.Thread(target=worker.run_forever, daemon=True, name="workflow-sidecar-worker")
        self._worker = worker
        self._worker_supervisor = supervisor
        self._worker_thread = thread
        self._expected_collector_names = expected_names
        try:
            thread.start()
        except Exception:
            self._worker = None
            self._worker_supervisor = None
            self._worker_thread = None
            self._expected_collector_names = frozenset()
            supervisor.stop()
            raise

    def stop_worker(self) -> None:
        worker = self._worker
        thread = self._worker_thread
        supervisor = self._worker_supervisor
        if worker is not None:
            worker.stop()
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=2.0)
        if thread is not None and thread.is_alive():
            # The collector may still be using SQLite. Retain the worker
            # references and single-writer lock; releasing either would allow
            # a duplicate writer or close the database underneath this thread.
            raise RuntimeError("worker_shutdown_timeout")
        if supervisor is not None:
            supervisor.stop()
        self._worker = None
        self._worker_thread = None
        self._worker_supervisor = None
        self._expected_collector_names = frozenset()

    def worker_running(self) -> bool:
        return bool(self._worker_thread and self._worker_thread.is_alive())

    def live_updates_running(self) -> bool:
        return bool(self._watch_thread and self._watch_thread.is_alive())

    def health(self) -> dict[str, Any]:
        return {"status": "ok", "readOnlyControl": True, "ledgerOwner": "workflow-assistance", "observerMutation": False}

    def projection(self) -> dict[str, Any]:
        canonical = self.store.projection()
        statuses = canonical["tasks_by_status"]
        return {
            "schema_version": "workflow/sidecar-projection/v1",
            "mode": self.live.mode(),
            "health": self.health(),
            "integrity": canonical["integrity"],
            "telemetry": {"count": canonical["telemetry_events"]},
            "tasks": {"count": sum(statuses.values()), "by_status": statuses},
            "usage": canonical["usage_summary"],
            "ci": canonical["ci_summary"],
            "observed_at": canonical["observed_at"],
        }

    def publish_observed(self) -> str:
        legacy_id = self.live.hub.publish("observed", self.projection())
        # 新链路双写：persistent revision hub（sidecar.v3_snapshot 由 live gate
        # 提供 transport verdict；watch 触发时数据已变化）。
        snapshot = self.v3_snapshot()
        self._revision = self.revision_hub.publish("observed", snapshot)
        # Persist the new revision so a restarted sidecar seeds its hub from
        # here, keeping Last-Event-ID cursors monotonic across restarts.
        self.store.record_revision(self._revision)
        return legacy_id

    def _collector_coverage(self) -> dict[str, Any] | None:
        if not self.worker_running() or not self._expected_collector_names:
            return None
        rows = self.store.list_collector_health()
        rows_by_name = {str(row.get("name")): row for row in rows}
        now = time.time()

        def fresh_success(row: dict[str, Any]) -> bool:
            raw = row.get("last_success_at")
            if not isinstance(raw, str) or not raw:
                return False
            try:
                observed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
                if observed.tzinfo is None:
                    return False
                age = now - observed.timestamp()
            except (TypeError, ValueError, OverflowError):
                return False
            return (
                0.0 <= age <= COLLECTOR_FRESHNESS_SECONDS
                and int(row.get("consecutive_failures") or 0) == 0
                and not row.get("circuit_open_until")
            )

        fresh = sum(
            1
            for name in self._expected_collector_names
            if (row := rows_by_name.get(name)) is not None
            if fresh_success(row)
        )
        return {
            "numerator": fresh,
            "denominator": len(self._expected_collector_names),
            "scope": "collector_health",
        }

    def v3_snapshot(self) -> dict:
        """P0-2: /api/v1/snapshot returns the v3 snapshot; transport verdict
        comes exclusively from the live gate (never fabricated LIVE)."""
        coverage = self._collector_coverage()
        now = time.time()
        connected, connected_since = self.sse_connection_state()
        verdict = evaluate_live(
            snapshot_valid=bool(validate_snapshot(self.live_projection_skeleton())["valid"]),
            sse_connected=connected,
            heartbeat_age_seconds=(now - self._last_heartbeat_at) if self._last_heartbeat_at is not None else float("inf"),
            heartbeat_threshold_seconds=HEARTBEAT_SECONDS,
            cursor_valid=(
                self._revision > 0
                and self.live_updates_running()
                and self._last_canonical_ok_at is not None
                and (now - self._last_canonical_ok_at) <= CANONICAL_READBACK_FRESHNESS_SECONDS
            ),
            writer_watermark_age_seconds=(now - self._last_write_at) if self._last_write_at is not None else float("inf"),
            writer_watermark_threshold_seconds=60.0,
            coverage=coverage,
        )
        freshness_state = (
            "UNKNOWN"
            if self._last_write_at is None
            else "FRESH"
            if now - self._last_write_at <= 60.0
            else "STALE"
        )
        snapshot = build_v3_snapshot(
            self.store,
            self.index,
            revision=self._revision,
            events_url=self._events_url,
            transport_state=verdict.state,
            freshness_state=freshness_state,
            workspace_evidence=self.workspace_evidence,
        )
        # The generic composition root can only project persisted health rows.
        # The supervising sidecar additionally knows the complete expected set
        # and whether its worker is still alive; expose that authoritative
        # coverage instead of a misleading partial-row N/N.
        snapshot["coverage"] = coverage or {
            "numerator": None,
            "denominator": None,
            "scope": "collector_health",
        }
        snapshot["transport"].update(
            {
                "eventStreamConnected": connected,
                "connectedSince": self._timestamp(connected_since),
                "lastHeartbeatAt": self._timestamp(self._last_heartbeat_at),
                "writerWatermarkAt": self._timestamp(self._last_write_at),
            }
        )
        return snapshot

    def repair_packs_view(self) -> dict[str, Any]:
        """CL-07: the copyable handoff material behind the problem rows.

        The text is rendered by the same `repair_pack_projection.render_handoff_text` the CLI uses, so the
        browser copies the projection's own sentences instead of a second implementation that could drift.
        `manual=True` names no adapter: a human copies the material to whatever tool they choose, and this
        route never asserts that any adapter can invoke anything.

        Absent issues and no issues are different statements. `issues` absent from the snapshot means no
        source answered, so this route returns SOURCE_ABSENT with no packs rather than an empty list that
        would read as "every source was read and there is nothing to hand off".
        """
        snapshot = self.v3_snapshot()
        issues = snapshot.get("issues")
        issues_summary = snapshot.get("issuesSummary")
        generated_at = self._timestamp(time.time()) or ""
        if issues is None:
            return {
                "schemaVersion": REPAIR_PACKS_VIEW_SCHEMA_VERSION,
                "status": "SOURCE_ABSENT",
                "reason": "问题投影缺席：没有来源作答，无法判断是否存在可交接的问题。",
                "generatedAt": generated_at,
                "issuesSummary": issues_summary,
                "packs": [],
                "summary": None,
            }
        projection = repair_pack_projection.project_repair_packs(
            issues=issues,
            projects=self.store.list_projects(),
            registry=None,
            adapters=[],
            generated_at=generated_at,
            manual=True,
        )
        packs, pack_summary = projection["packs"], projection["summary"]
        for pack in packs:
            pack["handoffText"] = repair_pack_projection.render_handoff_text(pack)
        open_count = pack_summary.get("openIssueCount")
        if open_count == 0:
            status, reason = "NO_OPEN_ISSUES", "已读取问题投影：当前没有待交接的问题。"
        elif not packs:
            status, reason = "NO_PACK", "存在问题，但没有形成可交接的包；原因见 summary.refusals。"
        else:
            status, reason = "OK", "已生成人工交接材料：复制不等于发送，WORK-LAB 不执行任何操作。"
        return {
            "schemaVersion": REPAIR_PACKS_VIEW_SCHEMA_VERSION,
            "status": status,
            "reason": reason,
            "generatedAt": generated_at,
            "issuesSummary": issues_summary,
            "packs": packs,
            "summary": pack_summary,
        }

    def solutions_view(self, *, query: str = "", software_id: str | None = None,
                       current_version: str | None = None, fingerprints: Any = (),
                       limit: int = solution_library.MAX_RESULTS) -> dict[str, Any]:
        """CL-06: local solution search. Read-only; no model and no AAOS are consulted.

        A store that cannot be read is SOURCE_ABSENT, never an empty list: "the library has no
        solutions" and "the library could not be read" are different statements, and only the first
        one licenses a reader to conclude there is nothing to apply.
        """
        return solution_library.store_view(
            self.store, query=query, software_id=software_id,
            current_version=current_version, fingerprints=fingerprints, limit=limit,
        )

    def live_projection_skeleton(self) -> dict:
        """Minimal valid snapshot skeleton for live-gate schema validation."""
        return build_v3_snapshot(
            self.store,
            self.index,
            revision=self._revision,
            events_url=self._events_url,
            transport_state="UNKNOWN",
            workspace_evidence=self.workspace_evidence,
        )

    def close(self) -> None:
        self.stop_worker()
        self.stop_live_updates()
        self.store.close()

    def mark_sse_connected(self) -> None:
        with self._sse_connection_lock:
            if self._sse_connection_count == 0:
                self._sse_connected_since = time.time()
            self._sse_connection_count += 1

    def mark_sse_disconnected(self) -> None:
        with self._sse_connection_lock:
            self._sse_connection_count = max(0, self._sse_connection_count - 1)
            if self._sse_connection_count == 0:
                self._sse_connected_since = None

    def has_sse_connections(self) -> bool:
        connected, _ = self.sse_connection_state()
        return connected

    def sse_connection_state(self) -> tuple[bool, float | None]:
        with self._sse_connection_lock:
            return self._sse_connection_count > 0, self._sse_connected_since

    @staticmethod
    def _timestamp(value: float | None) -> str | None:
        if value is None:
            return None
        return datetime.fromtimestamp(value, timezone.utc).isoformat().replace("+00:00", "Z")

    @contextmanager
    def sse_connection(self):
        self.mark_sse_connected()
        try:
            yield
        finally:
            self.mark_sse_disconnected()


def _is_loopback_host(host: str | None) -> bool:
    if not host:
        return False
    candidate = host.strip().strip("[]").lower()
    if candidate == "localhost" or candidate.endswith(".localhost"):
        # .localhost 是 RFC 6761 保留 TLD：Tauri 2 (Windows WebView2) 前端
        # Origin 为 http://tauri.localhost —— 必须放行否则 fetch 403 → 前端 OFFLINE。
        return True
    try:
        return ipaddress.ip_address(candidate).is_loopback
    except ValueError:
        return False


def _allowed_origin(origin: str) -> bool:
    try:
        parsed = urlsplit(origin)
        _ = parsed.port
    except ValueError:
        return False
    return (
        parsed.scheme in {"http", "https"}
        and _is_loopback_host(parsed.hostname)
        and parsed.username is None
        and parsed.password is None
        and parsed.path in {"", "/"}
        and not parsed.query
        and not parsed.fragment
    )


def _url_host(host: str) -> str:
    return f"[{host}]" if ":" in host and not host.startswith("[") else host


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)


class _WorkflowHTTPServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address: tuple[str, int], handler: type[BaseHTTPRequestHandler], sidecar: WorkflowSidecar) -> None:
        self._sidecar_lock = SingleInstanceLock(sidecar.runtime_root / "sidecar.lock")
        self.sidecar = sidecar
        self._sidecar_lock.acquire()
        self._endpoint_path = sidecar.runtime_root / "sidecar-endpoint.json"
        self._closed = False
        try:
            super().__init__(address, handler)
            host = str(self.server_address[0])
            url_host = _url_host(host)
            port = int(self.server_address[1])
            _atomic_json(
                self._endpoint_path,
                {
                    "schemaVersion": "workflow/sidecar-endpoint/v1",
                    "pid": os.getpid(),
                    "host": host,
                    "port": port,
                    "startedAt": __import__("time").time(),
                    "projectionUrl": f"http://{url_host}:{port}/api/v1/snapshot",
                    "eventsUrl": f"http://{url_host}:{port}/api/v1/events",
                },
            )
        except Exception:
            self._sidecar_lock.release()
            raise

    def server_close(self) -> None:
        if self._closed:
            return
        self._closed = True
        try:
            try:
                endpoint = json.loads(self._endpoint_path.read_text(encoding="utf-8"))
            except (FileNotFoundError, UnicodeError, json.JSONDecodeError):
                endpoint = {}
            if endpoint.get("pid") == os.getpid() and endpoint.get("port") == self.server_port:
                self._endpoint_path.unlink(missing_ok=True)
        finally:
            try:
                super().server_close()
            finally:
                try:
                    self.sidecar.close()
                finally:
                    self._sidecar_lock.release()


# D1 (Lite visible delivery): MIME types for the read-only static frontend.
# A closed, explicit map — no dynamic content negotiation, no exec. Only the
# asset classes a Vite React build emits.
_STATIC_MIME = {
    ".html": "text/html; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".mjs": "text/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".ico": "image/x-icon",
    ".woff": "font/woff",
    ".woff2": "font/woff2",
    ".txt": "text/plain; charset=utf-8",
    ".map": "application/json; charset=utf-8",
    ".webmanifest": "application/manifest+json",
}


def create_server(
    sidecar: WorkflowSidecar,
    host: str = "127.0.0.1",
    port: int = 0,
    *,
    live_updates: bool = False,
    frontend_root: Path | None = None,
) -> ThreadingHTTPServer:
    if not _is_loopback_host(host):
        raise ValueError("sidecar host must be loopback-only")

    # D1: optional read-only static root (a Vite React build's `dist/`). When
    # provided, the sidecar serves it to the browser at `http://<host>:<port>/`
    # so the SAME production artifact that Tauri ships is also reachable via
    # an authorized local browser read-only entry — no second page, no fake
    # data. API routes always take precedence over static files; every
    # non-GET method stays 405 (read-only contract unchanged). `frontend_root`
    # is None by default, so existing callers see zero behavior change.
    static_root = None
    if frontend_root is not None:
        static_root = frontend_root.resolve()
        if not static_root.is_dir():
            raise ValueError("frontend_root is not a directory: " + str(frontend_root))

    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"
        def _cors_origin(self) -> str | None:
            origin = self.headers.get("Origin")
            return origin if origin and _allowed_origin(origin) else None

        def send_json(self, status: int, payload: dict[str, Any]) -> None:
            body = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            cors_origin = self._cors_origin()
            if cors_origin:
                self.send_header("Access-Control-Allow-Origin", cors_origin)
                self.send_header("Vary", "Origin")
            self.end_headers()
            try:
                self.wfile.write(body)
            except (ConnectionResetError, BrokenPipeError, OSError):
                # a browser that navigates away is normal; it is not a service failure
                self.close_connection = True

        def _drain_request_body(self) -> int:
            """Read and discard a request body, returning how many bytes went unread.

            This server speaks HTTP/1.1, so the connection stays open after a response. A refused write
            that left its body in the buffer made the NEXT response on that connection begin with the
            caller's JSON -- a client then sees a broken status line where the read-only contract says
            405. The 405 is the promise the UI and the delivery proofs rely on, so it has to arrive whole.
            """
            try:
                length = int(self.headers.get("Content-Length") or 0)
            except (TypeError, ValueError):
                length = 0
            if length <= 0:
                return 0
            try:
                self.rfile.read(length)
            except OSError:
                self.close_connection = True
            return length

        def refuse_write(self) -> None:
            """Drain then deny. The denial is spelled out in each `do_<verb>` on purpose.

            `verify_observer_readonly_boundary.py` reads the body of every write handler and fails if the
            405 is not stated there, so routing the refusal through this helper alone would launder the
            guard's own evidence. A guard that reads source shape is a deliberate anti-indirection device:
            when it fires on a refactor, the call site changes, not the check.
            """
            self._drain_request_body()

        def _serve_static(self, path: str) -> bool:
            """D1: serve a file from the read-only static root (if enabled).

            Returns True when a static file was served, False when the path is
            not a static asset (caller falls through to the API 404). Every
            mapping is content-neutral (no template substitution, no eval),
            the root is a Vite `dist/` directory, and path traversal is
            rejected so the sidecar can never read outside the artifact.
            """
            if static_root is None:
                return False
            rel = path.lstrip("/")
            candidate = (static_root / rel).resolve() if rel else (static_root / "index.html").resolve()
            try:
                candidate.relative_to(static_root)
            except ValueError:
                self.send_json(403, {"status": "static_path_escape"})
                return True
            if not candidate.is_file():
                # SPA fallback: any unknown non-asset GET -> index.html, so the
                # React router can own client-side routes. index.html missing
                # means the static root has no frontend -> not a static asset.
                index = (static_root / "index.html").resolve()
                if index.is_file() and index != candidate:
                    candidate = index
                else:
                    return False
            mime = _STATIC_MIME.get(candidate.suffix.lower(), "application/octet-stream")
            data = candidate.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", mime)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)
            return True

        def do_GET(self) -> None:  # noqa: N802
            origin = self.headers.get("Origin")
            if origin and not _allowed_origin(origin):
                self.send_json(403, {"status": "origin_not_allowed"})
                return
            path = urlsplit(self.path).path
            if path == "/healthz":
                self.send_json(200, sidecar.health())
            elif path == "/api/projection":
                self.send_json(200, sidecar.projection())  # 旧 v1 兼容，保留
            elif path == "/api/v1/snapshot":
                self.send_json(200, sidecar.v3_snapshot())  # P0-2: 真 v3
            elif path == "/api/v1/repair-packs":
                # CL-07: the problem rows' copyable handoff, rendered server-side by the same projection
                # the CLI writes. GET-only like every other read; no adapter is named or invoked.
                self.send_json(200, sidecar.repair_packs_view())
            elif path == "/api/v1/solutions":
                # CL-06: local search over solidified solutions. GET-only; the response carries its own
                # typed status because a 200 with status EMPTY/NO_MATCH/SOURCE_ABSENT is not "found".
                query = parse_qs(urlsplit(self.path).query)
                try:
                    limit = int((query.get("limit") or [str(solution_library.MAX_RESULTS)])[0])
                except ValueError:
                    self.send_json(400, {
                        "schemaVersion": SOLUTION_SEARCH_SCHEMA_VERSION,
                        "status": "REFUSED", "reason": "limit 必须是整数。",
                        "query": "", "results": [], "summary": None,
                    })
                    return
                self.send_json(200, sidecar.solutions_view(
                    query=(query.get("q") or [""])[0],
                    software_id=(query.get("softwareId") or [None])[0],
                    current_version=(query.get("version") or [None])[0],
                    fingerprints=query.get("fingerprint") or [],
                    limit=limit,
                ))
            elif path == "/api/v1/evidence-range":
                # REQ-RANGE: a read-only slice of a large artifact, addressed by an exact byte interval.
                # The typed verdict lives in the body (HTTP 200 never means the read succeeded). Two things
                # narrow it beyond "inside the repository": the handle must sit on an evidence surface the
                # boundary declaration names, and the peer must be a literal loopback address — a name that
                # resolves to loopback today can be redirected by a HOSTS entry tomorrow.
                query = parse_qs(urlsplit(self.path).query)
                if not ipaddress.ip_address(str(self.client_address[0])).is_loopback:
                    self.send_json(403, {
                        "schema_version": evidence_range_reader.SCHEMA_VERSION,
                        "status": "REFUSED", "reason_code": "PEER_NOT_LOOPBACK",
                        "reason": "证据区间只从环回地址提供。", "content": None,
                    })
                    return
                try:
                    offset = int((query.get("offset") or ["0"])[0])
                    limit = int((query.get("limit") or [str(evidence_range_reader.DEFAULT_LIMIT)])[0])
                except ValueError:
                    self.send_json(400, {
                        "schema_version": evidence_range_reader.SCHEMA_VERSION,
                        "status": "REFUSED", "reason_code": "BAD_QUERY",
                        "reason": "offset 与 limit 必须是整数。",
                        "content": None,
                    })
                    return
                self.send_json(200, evidence_range_reader.read_range(
                    handle=(query.get("handle") or [""])[0],
                    root=sidecar.project_root,
                    offset=offset,
                    limit=limit,
                    expected_digest=(query.get("expectedDigest") or [None])[0],
                    evidence_roots=evidence_range_reader.declared_evidence_roots(sidecar.project_root),
                ))
            elif path == "/api/v1/events":
                if server._closed:
                    self.send_json(503, {"status": "server_closed"})
                    return
                last_id = self.headers.get("Last-Event-ID")
                client = sidecar.revision_hub.connect(uuid.uuid4().hex, last_event_id=last_id)
                if client is None:
                    self.send_json(503, {"status": "too_many_connections"})
                    return
                with sidecar.sse_connection():
                    try:
                        self.send_response(200)
                        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
                        self.send_header("Cache-Control", "no-store")
                        self.send_header("X-Accel-Buffering", "no")
                        self.send_header("Connection", "keep-alive")
                        cors_origin = self._cors_origin()
                        if cors_origin:
                            self.send_header("Access-Control-Allow-Origin", cors_origin)
                            self.send_header("Vary", "Origin")
                        self.end_headers()
                        frames = sidecar.revision_hub.frames_for(client)
                        if not frames:  # 新连接：先推一帧 snapshot 事件
                            frames = [SseRevisionHub._frame("snapshot", sidecar.v3_snapshot(), sidecar._revision)]
                        self.wfile.write("".join(frames).encode("utf-8"))
                        self.wfile.flush()
                        while True:
                            time.sleep(HEARTBEAT_SECONDS / 2)
                            if server._closed:
                                break
                            sidecar._last_heartbeat_at = time.time()
                            frames = sidecar.revision_hub.frames_for(client)
                            if not frames:
                                frames = [sidecar.revision_hub.heartbeat_frame()]
                            self.wfile.write("".join(frames).encode("utf-8"))
                            self.wfile.flush()
                    except (BrokenPipeError, ConnectionResetError, OSError):
                        return
                    finally:
                        sidecar.revision_hub.disconnect(client.client_id)
            else:
                if self._serve_static(path):
                    return
                self.send_json(404, {"status": "not_found"})

        def do_POST(self) -> None:  # noqa: N802
            self.refuse_write()
            self.send_json(405, {"status": "method_not_allowed"})

        def do_PUT(self) -> None:  # noqa: N802
            self.refuse_write()
            self.send_json(405, {"status": "method_not_allowed"})

        def do_PATCH(self) -> None:  # noqa: N802
            self.refuse_write()
            self.send_json(405, {"status": "method_not_allowed"})

        def do_DELETE(self) -> None:  # noqa: N802
            self.refuse_write()
            self.send_json(405, {"status": "method_not_allowed"})

        def log_message(self, format: str, *args: Any) -> None:
            return

    server: _WorkflowHTTPServer | None = None
    try:
        server = _WorkflowHTTPServer((host, port), Handler, sidecar)
        # P0-4: backfill eventsUrl once the real port is known (frontend reads
        # transport.eventsUrl to subscribe).
        url_host = _url_host(str(server.server_address[0]))
        sidecar._events_url = f"http://{url_host}:{int(server.server_address[1])}/api/v1/events"
        if live_updates:
            sidecar.start_live_updates()
        return server
    except Exception:
        if server is not None:
            server.server_close()
        else:
            sidecar.close()
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description="Serve the Workflow Assistance loopback-only sidecar")
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--runtime-root", type=Path)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument("--worker-tick", type=float, default=30.0)
    parser.add_argument("--no-worker", action="store_true")
    parser.add_argument(
        "--frontend-root", type=Path, default=None,
        help="D1: read-only Vite `dist/` directory to serve at `/` (browser read-only entry). "
             "Optional; when omitted the sidecar is API-only (unchanged behavior).",
    )
    args = parser.parse_args()
    project_root = args.project_root.resolve()
    runtime_root = (args.runtime_root or project_root / ".hermes" / "task-runtime" / "workflow").resolve()
    sidecar = WorkflowSidecar(project_root, runtime_root)
    server = create_server(
        sidecar,
        args.host,
        args.port,
        live_updates=True,
        frontend_root=args.frontend_root,
    )
    try:
        if not args.no_worker:
            sidecar.start_worker(tick_seconds=args.worker_tick)
    except Exception:
        server.server_close()
        raise
    print(
        f"WORKFLOW_SIDECAR_READY url=http://{args.host}:{server.server_port} "
        f"ledger_owner=workflow-assistance worker={'disabled' if args.no_worker else 'supervised'}",
        flush=True,
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        return 0
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
