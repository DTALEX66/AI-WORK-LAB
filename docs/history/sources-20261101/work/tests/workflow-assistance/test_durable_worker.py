"""Contract tests for the durable worker loop (WL3-400/410)."""

from __future__ import annotations

import tempfile
import unittest
import json
import subprocess
import sys
import threading
import time
from pathlib import Path

from canonical_store import CanonicalStore
from durable_worker import CollectorError, CollectorResult, DurableWorker, fingerprint
import project_temp


def _quality_collector(store: CanonicalStore, project_id: str) -> CollectorResult:
    return CollectorResult(
        kind="quality",
        ok=True,
        records=[
            {
                "project_id": project_id,
                "scope": "workflow",
                "quality": "EXACT_SOURCE",
                "coverage": "PARTIAL",
                "freshness": "STALE",
                "observed_at": "2026-08-10T00:00:00Z",
                "last_good_at": None,
            }
        ],
    )


def _usage_collector(store: CanonicalStore, project_id: str) -> CollectorResult:
    return CollectorResult(
        kind="usage",
        ok=True,
        records=[
            {
                "project_id": project_id,
                "provider": "deepseek",
                "model": "deepseek-v4-flash",
                "input_tokens": 100,
                "output_tokens": 20,
                "total_tokens": 120,
                "quality": "EXACT_SOURCE",
            }
        ],
    )


def _failing_collector(store: CanonicalStore, project_id: str) -> CollectorResult:
    raise CollectorError("source unavailable")


def _unexpected_failing_collector(store: CanonicalStore, project_id: str) -> CollectorResult:
    raise RuntimeError("unexpected source failure")


def _ok_handler(store: CanonicalStore, task: dict[str, Any]) -> None:
    store.append_telemetry(
        {
            "event_id": f"task-done-{task['task_id']}",
            "project_id": task.get("project_id", "work-lab"),
            "producer": "durable-worker",
            "occurred_at": "2026-08-10T00:00:00Z",
        }
    )


def _failing_handler(store: CanonicalStore, task: dict[str, Any]) -> None:
    raise RuntimeError("handler boom")


class DurableWorkerTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temporary = tempfile.TemporaryDirectory()
        self.store = CanonicalStore(Path(self._temporary.name) / "canonical.sqlite")

    def tearDown(self) -> None:
        self.store.close()
        self._temporary.cleanup()

    def test_worker_runs_collectors_and_writes_canonical_facts(self) -> None:
        worker = DurableWorker(
            self.store,
            collectors=[_quality_collector, _usage_collector],
            task_handler=None,
        )
        result = worker.run_once()
        self.assertEqual(result["zombie_reclaimed"], [])
        outcomes = {item["kind"]: item for item in result["collectors"]}
        self.assertEqual(outcomes["quality"]["ok"], True)
        self.assertEqual(outcomes["usage"]["records"], 1)
        projection = self.store.projection()
        self.assertEqual(projection["tables"]["source_quality"], 1)
        self.assertEqual(projection["usage_summary"][0]["tokens"], 120)

    def test_failing_collector_degrades_without_killing_worker(self) -> None:
        worker = DurableWorker(self.store, collectors=[_failing_collector])
        result = worker.run_once()
        self.assertEqual(result["collectors"][0]["ok"], False)
        self.assertIn("source unavailable", result["collectors"][0]["error"])

    def test_worker_persists_collector_health_for_success_and_failure(self) -> None:
        worker = DurableWorker(
            self.store,
            collectors=[_quality_collector, _unexpected_failing_collector],
        )
        first = worker.run_once()
        self.assertEqual(len(first["collectors"]), 2)
        health = {row["name"]: row for row in self.store.list_collector_health()}
        self.assertEqual(health["_quality_collector"]["total_runs"], 1)
        self.assertIsNotNone(health["_quality_collector"]["last_success_at"])
        self.assertEqual(health["_quality_collector"]["consecutive_failures"], 0)
        self.assertEqual(health["_unexpected_failing_collector"]["total_runs"], 1)
        self.assertEqual(health["_unexpected_failing_collector"]["consecutive_failures"], 1)

        worker.run_once()
        health = {row["name"]: row for row in self.store.list_collector_health()}
        self.assertEqual(health["_quality_collector"]["total_runs"], 2)
        self.assertEqual(health["_unexpected_failing_collector"]["total_runs"], 2)
        self.assertEqual(health["_unexpected_failing_collector"]["consecutive_failures"], 2)

    def test_supervisor_loop_recovers_after_unhandled_tick_failure_and_stops(self) -> None:
        worker = DurableWorker(self.store, tick_seconds=0.01)
        calls = 0

        def flaky_tick() -> dict[str, object]:
            nonlocal calls
            calls += 1
            if calls == 1:
                raise RuntimeError("transient store failure")
            return {"ok": True}

        worker.run_once = flaky_tick  # type: ignore[method-assign]
        thread = threading.Thread(target=worker.run_forever)
        thread.start()
        deadline = time.time() + 2.0
        while calls < 2 and time.time() < deadline:
            time.sleep(0.01)
        worker.stop()
        thread.join(timeout=1.0)

        self.assertGreaterEqual(calls, 2)
        self.assertFalse(thread.is_alive())
        health = {row["name"]: row for row in self.store.list_collector_health()}
        self.assertGreaterEqual(health["worker_loop"]["total_runs"], 2)
        self.assertEqual(health["worker_loop"]["consecutive_failures"], 0)

    def test_task_loop_completes_healthy_task(self) -> None:
        self.store.upsert_task(
            {"task_id": "WL3-410-task", "project_id": "work-lab", "status": "PENDING"}
        )
        worker = DurableWorker(self.store, task_handler=_ok_handler)
        result = worker.run_once()
        self.assertEqual(result["task"]["status"], "completed")
        tasks = self.store.list_tasks()
        self.assertEqual(tasks[0]["status"], "COMPLETED_LOCAL")
        self.assertIsNone(tasks[0]["lease_holder"])

    def test_task_loop_retries_then_blocks_on_repeated_failure(self) -> None:
        self.store.upsert_task(
            {"task_id": "WL3-410-boom", "project_id": "work-lab", "status": "PENDING"}
        )
        worker = DurableWorker(self.store, task_handler=_failing_handler)
        first = worker.run_once()
        self.assertEqual(first["task"]["status"], "FAILED_RECOVERABLE")
        self.assertEqual(first["task"]["attempts"], 1)
        # Same fingerprint: second run increments and eventually blocks.
        second = worker.run_once()
        self.assertEqual(second["task"]["attempts"], 2)
        self.assertEqual(second["task"]["status"], "FAILED_RECOVERABLE")
        third = worker.run_once()
        self.assertEqual(third["task"]["attempts"], 3)
        fourth = worker.run_once()
        self.assertEqual(fourth["task"]["status"], "BLOCKED_POLICY")
        self.assertEqual(fourth["task"]["attempts"], 4)

    def test_fingerprint_is_stable(self) -> None:
        self.assertEqual(fingerprint("a:boom"), fingerprint("a:boom"))
        self.assertNotEqual(fingerprint("a:boom"), fingerprint("b:boom"))

    def test_cli_once_registers_project_and_runs_standard_collectors(self) -> None:
        # The runtime root must stay inside the project: the worker CLI now refuses an outside root, because
        # a canonical store in %TEMP% is invisible to the boundary sweep and outlives the checkout.
        root = project_temp.fixture_dir(prefix="durable-worker-cli-")
        try:
            project = root / "project"
            runtime = root / "runtime"
            project.mkdir()
            result = subprocess.run(
                [
                    sys.executable,
                    str(Path(__file__).resolve().parents[2] / "services/orchestration" / "durable_worker.py"),
                    "--runtime-root",
                    str(runtime),
                    "--project-root",
                    str(project),
                    "--project-id",
                    "cli-project",
                    "--once",
                ],
                text=True, encoding="utf-8", errors="replace",
                capture_output=True,
                check=False,
                timeout=30,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            outcome = json.loads(result.stdout)
            self.assertEqual(len(outcome["collectors"]), 6)
            readback = CanonicalStore(runtime / "canonical.sqlite")
            try:
                self.assertEqual(readback.list_projects()[0]["project_id"], "cli-project")
                projection = readback.projection()
                self.assertGreaterEqual(projection["telemetry_events"], 1)
                self.assertGreaterEqual(projection["tables"]["source_quality"], 1)
            finally:
                readback.close()
        finally:
            self.assertTrue(project_temp.force_release(root) or not root.exists(),
                            f"the CLI fixture root was left behind: {root}")


if __name__ == "__main__":
    unittest.main()
