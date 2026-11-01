"""P0-1/P0-2 tests: composition root + sidecar v3 snapshot wiring."""
from __future__ import annotations

import json
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "packages" / "client-neutral-core" / "scripts"))
sys.path.insert(0, str(ROOT / "services" / "orchestration"))

from canonical_store import CanonicalStore
from composition_root import build_v3_snapshot, load_approved_index
from durable_worker import CollectorResult
from sidecar import WorkflowSidecar, create_server
from sse_hub import HEARTBEAT_SECONDS, STALE
from snapshot_validator import validate_snapshot
from workspace_evidence import (CURRENT_STATE_PATH, ERROR_LEDGER_PATH, PLAN_PATH,
                                load_workspace_evidence)


def _write_fixture(root: Path, rel: Path, text: str) -> None:
    """Write each operand at the path the product actually reads.

    Hard-coding the fixture's directory is what let this test keep passing while the shipped
    constant pointed elsewhere, and then go red on CI on 2026-10-19; a moved constant must move
    the fixture with it, so the fixture is written from the constant.
    """
    target = root / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")
import project_temp
import socket
import urllib.request

PROJECT_ROOT = ROOT


def make_sidecar(runtime_root: Path) -> WorkflowSidecar:
    return WorkflowSidecar(PROJECT_ROOT, runtime_root)


class CompositionRootTests(unittest.TestCase):
    def test_workspace_evidence_loads_plan_governance_and_history_as_typed_sources(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "taskpacks/current").mkdir(parents=True)
            (root / ".project/governance" / "generated").mkdir(parents=True)
            _write_fixture(root, PLAN_PATH,
                "# Master\n> Status: `DELIVERED_PENDING_REMAINING_APPROVALS`\n"
                "28 个 WL3 任务:\n  VERIFIED_LOCAL: 24\n  BLOCKED(工具链):  1\n  RECONCILE_REQUIRED: 3\n"
                "| WL3-000 | VERIFIED_LOCAL | freshness |\n| WL3-620 | BLOCKED | portable |\n"
                "1. **Hermes/Codex global config live apply** — ✅ Codex 已完成；Hermes live 未动；\n"
            )
            _write_fixture(root, CURRENT_STATE_PATH,
                json.dumps({
                    "schema_version": "work-lab-current-state/v1",
                    "generated_at": "2026-08-14T12:58:47Z",
                    "modules": [{"id": "workflow-assistance"}, {"id": "work-lab-observer"}],
                    "contracts": {"count": 30},
                    "skills": {"count": 13},
                    "module_ownership": {"single_writer": True},
                    "stage3": {"taskpack_id": "WORK-LAB-FINAL-MASTER-CONTROL-PLANE", "task_count": 28},
                    "unverified_capabilities": ["commercial_release"],
                }),
            )
            _write_fixture(root, ERROR_LEDGER_PATH,
                json.dumps({
                    "schema_version": "work-lab/error-ledger/v1",
                    "generated_at": "2026-08-14T12:00:00Z",
                    "summary": {"total": 60, "by_classification": {"contract_drift": 27}},
                    "errors": [{"error_id": "ERR-060", "title": "fail closed", "status_after": "PASS"}],
                }),
            )

            evidence = load_workspace_evidence(root)
            self.assertEqual(evidence["plan"]["status"], "DELIVERED_PENDING_REMAINING_APPROVALS")
            self.assertEqual(evidence["plan"]["counts"]["verifiedLocal"], 24)
            self.assertEqual(evidence["plan"]["tasks"][-1]["taskId"], "WL3-620")
            self.assertEqual(evidence["plan"]["approvals"][0]["state"], "PARTIAL")
            self.assertEqual(evidence["governance"]["contracts"], 30)
            self.assertEqual(evidence["history"]["totalErrors"], 60)
            self.assertEqual(evidence["history"]["recentErrors"][0]["errorId"], "ERR-060")
            self.assertEqual({item["evidenceKind"] for item in evidence["sources"]}, {"PLAN", "STATIC_BASELINE", "HISTORY"})

    def test_load_approved_index_from_store(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = CanonicalStore(Path(tmp) / "c.sqlite")
            try:
                store.register_project("work-lab", str(PROJECT_ROOT))
                index = load_approved_index(store)
                self.assertIn("work-lab", set(index.projects.keys()))
                # machine root binding present so resolution can succeed.
                project = index.by_root(str(PROJECT_ROOT))
                self.assertIsNotNone(project)
            finally:
                store.close()

    def test_unapproved_registered_project_is_excluded_from_index_and_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = CanonicalStore(Path(tmp) / "c.sqlite")
            try:
                store.register_project("work-lab", str(PROJECT_ROOT), display_name="WORK-LAB")
                store.register_project("unapproved", str(Path(tmp) / "unapproved"))
                store.register_project("approved-external", str(Path(tmp) / "approved"))
                store.upsert_project_definition(
                    "approved-external",
                    {
                        "schema_version": "workflow/product-project/v1",
                        "project_id": "approved-external",
                        "display_name": "Approved External",
                        "approved": True,
                    },
                )

                index = load_approved_index(store)
                self.assertEqual(set(index.projects), {"work-lab", "approved-external"})

                snap = build_v3_snapshot(store, index, revision=0)
                self.assertEqual(
                    {project["projectId"] for project in snap["projects"]},
                    {"work-lab", "approved-external"},
                )
            finally:
                store.close()

    def test_build_v3_snapshot_flat_and_null(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = CanonicalStore(Path(tmp) / "c.sqlite")
            try:
                index = load_approved_index(store)
                snap = build_v3_snapshot(
                    store, index, revision=1,
                    events_url="http://127.0.0.1:9/api/v1/events",
                    transport_state="OFFLINE",
                    freshness_state="STALE",
                )
                self.assertEqual(snap["schemaVersion"], "workflow/snapshot/v3")
                self.assertIsInstance(snap["executions"], list)
                self.assertEqual(snap["tokenSummary"]["costQuality"], "UNKNOWN")
                self.assertIsNone(snap["tokenSummary"]["inputTokens"])
                self.assertEqual(snap["transport"]["eventsUrl"], "http://127.0.0.1:9/api/v1/events")
                self.assertEqual(snap["transport"]["transportState"], "OFFLINE")
                self.assertEqual(snap["transport"]["freshnessState"], "STALE")
                self.assertTrue(validate_snapshot(snap)["valid"])
            finally:
                store.close()

    def test_build_v3_snapshot_exposes_only_real_registry_task_and_local_git_facts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = CanonicalStore(Path(tmp) / "c.sqlite")
            try:
                store.register_project("work-lab", str(PROJECT_ROOT), display_name="WORK-LAB")
                store.upsert_task({"task_id": "t1", "project_id": "work-lab", "status": "PENDING"})
                store.append_quality(
                    {
                        "row_id": "git-work-lab-test",
                        "project_id": "work-lab",
                        "scope": "git",
                        "quality": "EXACT_SOURCE",
                        "coverage": "PARTIAL",
                        "freshness": "STALE",
                        "observed_at": "2026-08-14T14:59:30Z",
                        "last_good_at": "2026-08-14T14:59:30Z",
                        "head_sha": "769345d21fb9df9d0acafe13f953e41597658b80",
                        "branch": "main",
                        "dirty_count": 10,
                        "sourceRef": "git-rev-parse",
                    }
                )
                snap = build_v3_snapshot(store, load_approved_index(store), revision=0)
                project = snap["projects"][0]
                self.assertEqual(snap["tasks"], {"PENDING": 1})
                self.assertEqual(snap["sourceWatermark"], "2026-08-14T14:59:30Z")
                self.assertEqual(project["activityState"], "REGISTERED")
                self.assertEqual(project["git"]["localSha"], "769345d21fb9df9d0acafe13f953e41597658b80")
                self.assertEqual(project["git"]["branch"], "main")
                self.assertEqual(project["git"]["dirtyCount"], 10)
                self.assertEqual(project["git"]["matchState"], "UNVERIFIED")
                self.assertEqual(project["git"]["observedAt"], "2026-08-14T14:59:30Z")
                self.assertEqual(project["git"]["quality"], "EXACT_SOURCE")
                self.assertEqual(project["git"]["sourceRef"], "git-rev-parse")
                self.assertEqual(snap["executions"], [])
                self.assertEqual(snap["ci"], [])
            finally:
                store.close()

    def test_build_v3_snapshot_preserves_workspace_evidence_without_claiming_live(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = CanonicalStore(Path(tmp) / "c.sqlite")
            try:
                evidence = {"plan": {"status": "PLANNED"}, "history": {"totalErrors": 3}}
                snap = build_v3_snapshot(
                    store,
                    load_approved_index(store),
                    revision=0,
                    transport_state="OFFLINE",
                    workspace_evidence=evidence,
                )
                self.assertEqual(snap["workspace"], evidence)
                self.assertEqual(snap["transport"]["transportState"], "OFFLINE")
            finally:
                store.close()


class SidecarV3SnapshotTests(unittest.TestCase):
    def _start(self) -> tuple[WorkflowSidecar, object, Path]:
        runtime = project_temp.fixture_dir(prefix="sidecar-v3-")
        sidecar = make_sidecar(runtime)
        server = create_server(sidecar, port=0, live_updates=True)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()

        def stop_server() -> None:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

        def release_sidecar() -> None:
            # None of the three _start() tests ever closed the sidecar, so the CanonicalStore kept
            # a WAL handle on runtime/canonical.sqlite: on Windows the fixture directory then
            # cannot be removed (WinError 32). A watcher that will not stop is announced with the
            # token project_temp's sweeper uses, never hidden by an ignored teardown.
            try:
                sidecar.close()
            except RuntimeError as error:
                print(f"TEMP_RESIDUE_NOT_REMOVED {runtime} {type(error).__name__}: {error}")

        # addCleanup runs LIFO: the server stops touching the store, then the store is released.
        self.addCleanup(release_sidecar)
        self.addCleanup(stop_server)
        return sidecar, server, runtime

    def test_v1_snapshot_endpoint_returns_v3(self) -> None:
        import urllib.request

        sidecar, server, _ = self._start()
        port = int(server.server_address[1])
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/v1/snapshot", timeout=10) as response:
            data = json.loads(response.read().decode("utf-8"))
        self.assertEqual(data["schemaVersion"], "workflow/snapshot/v3")
        self.assertIsInstance(data["executions"], list)
        self.assertEqual(data["tokenSummary"]["costQuality"], "UNKNOWN")
        self.assertIn("eventsUrl", data["transport"])
        # transport verdict comes from the live gate; never fabricated LIVE.
        self.assertIn(data["transport"]["transportState"], {"OFFLINE", "DELAYED", "LIVE", "UNKNOWN", "CONNECTING"})

    def test_legacy_projection_still_served(self) -> None:
        import urllib.request

        _, server, _ = self._start()
        port = int(server.server_address[1])
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/projection", timeout=10) as response:
            data = json.loads(response.read().decode("utf-8"))
        self.assertEqual(data["schema_version"], "workflow/sidecar-projection/v1")

    def test_events_url_backfilled(self) -> None:
        sidecar, server, _ = self._start()
        port = int(server.server_address[1])
        self.assertEqual(sidecar._events_url, f"http://127.0.0.1:{port}/api/v1/events")

    def test_sse_connection_state_counts_concurrent_clients(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            sidecar = make_sidecar(Path(tmp))
            try:
                initial = sidecar.v3_snapshot()["transport"]
                self.assertFalse(initial["eventStreamConnected"])
                self.assertIsNone(initial["connectedSince"])
                sidecar.mark_sse_connected()
                sidecar.mark_sse_connected()
                self.assertTrue(sidecar.has_sse_connections())
                connected = sidecar.v3_snapshot()["transport"]
                self.assertTrue(connected["eventStreamConnected"])
                self.assertIsNotNone(connected["connectedSince"])
                sidecar.mark_sse_disconnected()
                self.assertTrue(sidecar.has_sse_connections(), "one disconnect must not hide the remaining client")
                sidecar.mark_sse_disconnected()
                self.assertFalse(sidecar.has_sse_connections())
                disconnected = sidecar.v3_snapshot()["transport"]
                self.assertFalse(disconnected["eventStreamConnected"])
                self.assertIsNone(disconnected["connectedSince"])
                sidecar.mark_sse_disconnected()
                self.assertFalse(sidecar.has_sse_connections(), "connection count never goes negative")
            finally:
                sidecar.close()

    def test_sidecar_startup_does_not_invent_heartbeat_or_writer_freshness(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            sidecar = make_sidecar(Path(tmp))
            try:
                transport = sidecar.v3_snapshot()["transport"]
                self.assertIsNone(transport["lastHeartbeatAt"])
                self.assertIsNone(transport["writerWatermarkAt"])
            finally:
                sidecar.close()

    def test_fresh_writer_and_complete_collector_health_can_reach_live(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            sidecar = make_sidecar(Path(tmp))
            def healthy_collector(store: CanonicalStore, project_id: str) -> CollectorResult:
                return CollectorResult(kind="quality", ok=True, records=[])
            try:
                sidecar.start_live_updates(interval_seconds=0.01)
                sidecar.start_worker(tick_seconds=30, collectors=[healthy_collector])
                deadline = time.time() + 2
                while len(sidecar.store.list_collector_health()) < 2 and time.time() < deadline:
                    time.sleep(0.02)
                now = time.time()
                sidecar._revision = 1
                sidecar._last_heartbeat_at = now
                sidecar._last_write_at = now
                sidecar.mark_sse_connected()
                transport = sidecar.v3_snapshot()["transport"]
                self.assertEqual(transport["transportState"], "LIVE")
                self.assertEqual(transport["freshnessState"], "FRESH")
                sidecar.stop_worker()
                self.assertNotEqual(sidecar.v3_snapshot()["transport"]["transportState"], "LIVE")
            finally:
                sidecar.close()

    def test_watcher_publish_failure_rolls_back_watermark_and_retries(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            sidecar = make_sidecar(Path(tmp))
            original_publish = sidecar.publish_observed
            calls = 0

            def flaky_publish() -> int:
                nonlocal calls
                calls += 1
                if calls == 1:
                    raise RuntimeError("synthetic publish failure")
                return original_publish()

            try:
                sidecar.publish_observed = flaky_publish  # type: ignore[method-assign]
                sidecar.start_live_updates(interval_seconds=0.01)
                sidecar.store.upsert_collector_health(
                    {
                        "name": "probe",
                        "totalRuns": 1,
                        "lastRunAt": "2026-08-15T00:00:00Z",
                        "lastSuccessAt": "2026-08-15T00:00:00Z",
                        "consecutiveFailures": 0,
                        "circuitOpenUntil": None,
                        "droppedCount": 0,
                    }
                )
                deadline = time.time() + 2
                # Wait on the condition this test actually asserts, not on a proxy
                # that advances at function entry. `calls` is incremented before the
                # publish body runs, so waiting only for `calls >= 2` let the main
                # thread assert while the worker was still inside the second publish:
                # `_revision` is assigned inside publish_observed, so it could still
                # read 0 and fail roughly one run in five. Waiting for both the retry
                # and its visible effect keeps the original intent (first call fails,
                # retry succeeds) without the race.
                while (calls < 2 or sidecar._revision <= 0) and time.time() < deadline:
                    time.sleep(0.02)
                self.assertGreaterEqual(calls, 2)
                self.assertTrue(sidecar.live_updates_running())
                self.assertGreater(sidecar._revision, 0)
                self.assertIsNotNone(sidecar._last_write_at)
            finally:
                sidecar.close()

    def test_stale_historical_collector_success_cannot_reach_live(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            sidecar = make_sidecar(Path(tmp))

            def healthy_collector(store: CanonicalStore, project_id: str) -> CollectorResult:
                return CollectorResult(kind="quality", ok=True, records=[])

            try:
                sidecar.start_worker(tick_seconds=30, collectors=[healthy_collector])
                deadline = time.time() + 2
                while len(sidecar.store.list_collector_health()) < 2 and time.time() < deadline:
                    time.sleep(0.02)
                stale = "2020-01-01T00:00:00Z"
                for name in ("healthy_collector", "worker_loop"):
                    sidecar.store.upsert_collector_health(
                        {
                            "name": name,
                            "totalRuns": 1,
                            "lastRunAt": stale,
                            "lastSuccessAt": stale,
                            "consecutiveFailures": 0,
                            "circuitOpenUntil": None,
                            "droppedCount": 0,
                        }
                    )
                now = time.time()
                sidecar._revision = 1
                sidecar._last_heartbeat_at = now
                sidecar._last_write_at = now
                sidecar.mark_sse_connected()
                snapshot = sidecar.v3_snapshot()
                self.assertEqual(snapshot["coverage"]["numerator"], 0)
                self.assertEqual(snapshot["coverage"]["denominator"], 2)
                self.assertNotEqual(snapshot["transport"]["transportState"], "LIVE")
            finally:
                sidecar.close()

    def test_dead_watcher_cannot_reach_live_with_historical_revision(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            sidecar = make_sidecar(Path(tmp))

            def healthy_collector(store: CanonicalStore, project_id: str) -> CollectorResult:
                return CollectorResult(kind="quality", ok=True, records=[])

            try:
                sidecar.start_worker(tick_seconds=30, collectors=[healthy_collector])
                deadline = time.time() + 2
                while len(sidecar.store.list_collector_health()) < 2 and time.time() < deadline:
                    time.sleep(0.02)
                now = time.time()
                sidecar._revision = 7
                sidecar._last_heartbeat_at = now
                sidecar._last_write_at = now
                sidecar.mark_sse_connected()
                self.assertFalse(sidecar.live_updates_running())
                self.assertNotEqual(sidecar.v3_snapshot()["transport"]["transportState"], "LIVE")
            finally:
                sidecar.close()

    def test_partial_expected_collector_set_cannot_reach_live(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            sidecar = make_sidecar(Path(tmp))
            entered = threading.Event()
            release = threading.Event()

            def first_collector(store: CanonicalStore, project_id: str) -> CollectorResult:
                return CollectorResult(kind="quality", ok=True, records=[])

            def second_collector(store: CanonicalStore, project_id: str) -> CollectorResult:
                entered.set()
                release.wait(timeout=10)
                return CollectorResult(kind="quality", ok=True, records=[])

            try:
                sidecar.start_worker(
                    tick_seconds=30,
                    collectors=[first_collector, second_collector],
                )
                self.assertTrue(entered.wait(timeout=2))
                now = time.time()
                sidecar._revision = 1
                sidecar._last_heartbeat_at = now
                sidecar._last_write_at = now
                sidecar.mark_sse_connected()
                # `entered` only proves the SECOND collector has started; the
                # first collector's health record is written asynchronously by
                # the worker thread, so reading the snapshot immediately raced
                # and intermittently observed numerator=0 (order-dependent flake
                # seen in the full governance batch on 2026-10-01, never in
                # isolation). Poll to the deadline the way the sibling test above
                # does, instead of asserting on an unsynchronized read.
                deadline = time.time() + 5
                snapshot = sidecar.v3_snapshot()
                while snapshot["coverage"]["numerator"] < 1 and time.time() < deadline:
                    time.sleep(0.02)
                    snapshot = sidecar.v3_snapshot()
                self.assertEqual(snapshot["coverage"]["numerator"], 1)
                self.assertEqual(snapshot["coverage"]["denominator"], 3)
                self.assertNotEqual(snapshot["transport"]["transportState"], "LIVE")
            finally:
                release.set()
                sidecar.close()

    def test_duplicate_collector_names_are_rejected_before_worker_start(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            sidecar = make_sidecar(Path(tmp))

            def duplicated(store: CanonicalStore, project_id: str) -> CollectorResult:
                return CollectorResult(kind="quality", ok=True, records=[])

            try:
                with self.assertRaisesRegex(ValueError, "collector names must be unique"):
                    sidecar.start_worker(collectors=[duplicated, duplicated])
                self.assertFalse(sidecar.worker_running())
            finally:
                sidecar.close()

    def test_embedded_worker_lifecycle_writes_health_and_stops_cleanly(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            sidecar = make_sidecar(Path(tmp))
            def healthy_collector(store: CanonicalStore, project_id: str) -> CollectorResult:
                return CollectorResult(kind="quality", ok=True, records=[])
            try:
                sidecar.start_worker(tick_seconds=0.05, collectors=[healthy_collector])
                # run_forever writes the collector rows inside run_once() and only stamps `worker_loop`
                # after that tick returns, so a health table with "something in it" is a legal intermediate
                # state, not a finished one. Wait for the set the sidecar itself declares as expected.
                deadline = time.time() + 5.0
                while time.time() < deadline:
                    names = {row["name"] for row in sidecar.store.list_collector_health()}
                    if names >= sidecar._expected_collector_names:
                        break
                    time.sleep(0.02)
                self.assertTrue(sidecar.worker_running())
                health_names = {row["name"] for row in sidecar.store.list_collector_health()}
                missing = sidecar._expected_collector_names - health_names
                self.assertFalse(missing,
                                 f"these collectors never reported health within 5s: {sorted(missing)}")
                self.assertIn("healthy_collector", health_names)
                self.assertIn("worker_loop", health_names)
                self.assertEqual(sidecar.store.list_projects()[0]["project_id"], "work-lab")
            finally:
                sidecar.close()
            self.assertFalse(sidecar.worker_running())

    def test_blocked_worker_shutdown_retains_writer_lock_and_open_store(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            runtime = Path(tmp)
            entered = threading.Event()
            release = threading.Event()

            def blocked_collector(store: CanonicalStore, project_id: str) -> CollectorResult:
                entered.set()
                release.wait(timeout=10)
                return CollectorResult(kind="quality", ok=True, records=[])

            sidecar = make_sidecar(runtime)
            contender = make_sidecar(runtime)
            try:
                sidecar.start_worker(tick_seconds=30, collectors=[blocked_collector])
                self.assertTrue(entered.wait(timeout=2), "collector did not enter its blocking section")
                with self.assertRaisesRegex(RuntimeError, "worker_shutdown_timeout"):
                    sidecar.close()
                self.assertTrue(sidecar.worker_running())
                self.assertEqual(sidecar.store.integrity_check(), "ok")
                with self.assertRaisesRegex(RuntimeError, "already_running"):
                    contender.start_worker(tick_seconds=30, collectors=[])
            finally:
                release.set()
                deadline = time.time() + 2
                while sidecar.worker_running() and time.time() < deadline:
                    time.sleep(0.02)
                sidecar.close()
                contender.close()

    def test_blocked_watcher_shutdown_retains_open_store(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            sidecar = make_sidecar(Path(tmp))
            entered = threading.Event()
            release = threading.Event()
            original_fingerprint = sidecar._canonical_fingerprint
            sidecar.start_live_updates(interval_seconds=0.01)

            def blocked_fingerprint() -> str:
                entered.set()
                release.wait(timeout=5)
                return original_fingerprint()

            sidecar._canonical_fingerprint = blocked_fingerprint
            self.assertTrue(entered.wait(timeout=1), "watcher did not enter its blocking read")
            with self.assertRaisesRegex(RuntimeError, "live_update_shutdown_timeout"):
                sidecar.close()
            self.assertEqual(sidecar.store.integrity_check(), "ok")

            release.set()
            sidecar.close()

    def test_worker_thread_start_failure_releases_supervisor_lock(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            runtime = Path(tmp)
            sidecar = make_sidecar(runtime)

            def collector(store: CanonicalStore, project_id: str) -> CollectorResult:
                return CollectorResult(kind="quality", ok=True, records=[])

            with mock.patch("sidecar.threading.Thread.start", side_effect=RuntimeError("thread start failed")):
                with self.assertRaisesRegex(RuntimeError, "thread start failed"):
                    sidecar.start_worker(tick_seconds=30, collectors=[collector])
            self.assertFalse(sidecar.worker_running())
            self.assertEqual(sidecar._expected_collector_names, frozenset())

            sidecar.start_worker(tick_seconds=30, collectors=[collector])
            self.assertTrue(sidecar.worker_running())
            sidecar.close()

    def test_watch_thread_start_failure_clears_thread_reference(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            sidecar = make_sidecar(Path(tmp))
            with mock.patch("sidecar.threading.Thread.start", side_effect=RuntimeError("thread start failed")):
                with self.assertRaisesRegex(RuntimeError, "thread start failed"):
                    sidecar.start_live_updates(interval_seconds=0.01)
            self.assertIsNone(sidecar._watch_thread)

            sidecar.start_live_updates(interval_seconds=0.01)
            self.assertIsNotNone(sidecar._watch_thread)
            sidecar.close()

    def test_sse_connection_scope_releases_count_after_handshake_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            sidecar = make_sidecar(Path(tmp))
            try:
                with self.assertRaisesRegex(RuntimeError, "handshake failed"):
                    with sidecar.sse_connection():
                        self.assertTrue(sidecar.has_sse_connections())
                        raise RuntimeError("handshake failed")
                self.assertFalse(sidecar.has_sse_connections())
            finally:
                sidecar.close()

    def test_failing_canonical_readback_removes_live(self) -> None:
        """P0: an alive watcher whose canonical readback keeps failing must
        fail closed to DELAYED/OFFLINE instead of staying LIVE on thread
        liveness alone."""
        with tempfile.TemporaryDirectory() as tmp:
            sidecar = make_sidecar(Path(tmp))

            def healthy_collector(store: CanonicalStore, project_id: str) -> CollectorResult:
                return CollectorResult(kind="quality", ok=True, records=[])

            try:
                sidecar.start_worker(tick_seconds=30, collectors=[healthy_collector])
                deadline = time.time() + 2
                while len(sidecar.store.list_collector_health()) < 2 and time.time() < deadline:
                    time.sleep(0.02)
                sidecar.start_live_updates(interval_seconds=0.01)
                now = time.time()
                sidecar._revision = 1
                sidecar._last_heartbeat_at = now
                sidecar._last_write_at = now
                sidecar.mark_sse_connected()
                self.assertEqual(sidecar.v3_snapshot()["transport"]["transportState"], "LIVE")

                def broken_fingerprint() -> str:
                    raise RuntimeError("canonical readback failed")

                sidecar._canonical_fingerprint = broken_fingerprint
                deadline = time.time() + 2
                while sidecar.live.mode() != STALE and time.time() < deadline:
                    time.sleep(0.02)
                self.assertEqual(sidecar.live.mode(), STALE)
                self.assertNotEqual(sidecar.v3_snapshot()["transport"]["transportState"], "LIVE")
            finally:
                sidecar.close()

    def test_sse_handler_loop_stops_after_server_close(self) -> None:
        """P0: a serving SSE connection must stop writing heartbeats once the
        server (and its store) is closed, so an old handler never refreshes a
        replaced sidecar's heartbeat timestamp."""
        with tempfile.TemporaryDirectory() as tmp:
            sidecar = make_sidecar(Path(tmp))
            server = create_server(sidecar, "127.0.0.1", 0, live_updates=True)
            serve_thread = threading.Thread(target=server.serve_forever, daemon=True)
            serve_thread.start()
            port = int(server.server_address[1])
            connection = urllib.request.urlopen(f"http://127.0.0.1:{port}/api/v1/events", timeout=5)
            try:
                self.assertTrue(sidecar.has_sse_connections())
                last_heartbeat_before_close = sidecar._last_heartbeat_at
                server.shutdown()  # stop the accept loop cleanly (avoids
                # Windows select-on-closed-socket noise from serve_forever)
                server.server_close()
                # The serving handler must observe the closed server and stop
                # refreshing the heartbeat; a short grace period proves it.
                time.sleep(HEARTBEAT_SECONDS / 2 + 0.2)
                self.assertEqual(sidecar._last_heartbeat_at, last_heartbeat_before_close)
            finally:
                try:
                    connection.close()
                except OSError:
                    pass
                try:
                    server.server_close()
                except Exception:
                    pass


if __name__ == "__main__":
    unittest.main()
