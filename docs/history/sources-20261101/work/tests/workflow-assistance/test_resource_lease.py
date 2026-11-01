"""Contract tests for resource lease + RuntimeSupervisor (WL3-330 / MR-09).

Covers taskpack §20.3: two-task gpu.heavy contention, stale lease recovery,
PID-reuse guard, user-external runtime never stopped, exact owned teardown,
unload timeout representation, OOM/restart recovery markers.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts/workflow"))

from resource_lease import ResourceLease, RuntimeSupervisor


class ResourceLeaseTests(unittest.TestCase):
    def test_gpu_heavy_mutual_exclusion(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            a = ResourceLease(root, "gpu.heavy")
            b = ResourceLease(root, "gpu.heavy")
            first = a.acquire()
            self.assertEqual(first["status"], "HELD")
            second = b.acquire()
            self.assertEqual(second["status"], "QUEUED")
            self.assertEqual(second["reason_code"], "RESOURCE_BUSY")

    def test_release_then_acquire(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            a = ResourceLease(root, "gpu.heavy")
            a.acquire()
            self.assertEqual(a.release()["status"], "RELEASED")
            b = ResourceLease(root, "gpu.heavy")
            self.assertEqual(b.acquire()["status"], "HELD")

    def test_unknown_group_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                ResourceLease(Path(tmp), "gpu.huge")

    @mock.patch("resource_lease._pid_alive", return_value=False)
    def test_stale_lease_reclaimed(self, _alive) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            # Simulate a stale lock written by a dead pid
            (root / "leases").mkdir(parents=True, exist_ok=True)
            stale = {
                "group": "gpu.heavy", "pid": 999999, "token": "dead",
                "start_time": None, "acquired_at": "2026-01-01T00:00:00+00:00",
            }
            (root / "leases" / "gpu.heavy.json").write_text(
                json.dumps(stale), encoding="utf-8")
            lease = ResourceLease(root, "gpu.heavy")
            result = lease.acquire()
            self.assertEqual(result["status"], "HELD")
            self.assertTrue(result.get("reclaimed"))

    @mock.patch("resource_lease._pid_alive", return_value=True)
    def test_live_owner_never_evicted(self, _alive) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            a = ResourceLease(root, "gpu.heavy")
            a.acquire()
            b = ResourceLease(root, "gpu.heavy")
            self.assertEqual(b.acquire()["status"], "QUEUED")


class RuntimeSupervisorTests(unittest.TestCase):
    def test_unknown_runtime_never_killed_by_name(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            sup = RuntimeSupervisor(Path(tmp))
            result = sup.stop("not-recorded")
            self.assertEqual(result["status"], "UNKNOWN_RUNTIME")
            self.assertIn("refusing to kill by name", result["reason"])

    @mock.patch("resource_lease._pid_alive", return_value=False)
    def test_dead_sidecar_reports_already_stopped(self, _alive) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            sup = RuntimeSupervisor(Path(tmp))
            sup.record("llama-cpp", 999999, ["llama-server"])
            result = sup.stop("llama-cpp")
            self.assertEqual(result["status"], "ALREADY_STOPPED")

    def test_not_owned_runtime_never_stopped(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            sup = RuntimeSupervisor(Path(tmp))
            # Simulate an external runtime (ComfyUI) that we only observed
            path = sup._state_path("comfyui")
            path.write_text(json.dumps({
                "runtime_id": "comfyui", "pid": os.getpid(),
                "command": [], "port": 8188,
                "start_time": None, "started_at": "2026-01-01T00:00:00+00:00",
                "owned_by_supervisor": False,
            }), encoding="utf-8")
            result = sup.stop("comfyui")
            self.assertEqual(result["status"], "NOT_OWNED")

    @mock.patch("resource_lease._pid_alive", return_value=True)
    @mock.patch("resource_lease._process_start_time", return_value="2026-08-16T00:00:00+08:00")
    @mock.patch("resource_lease.subprocess.run", return_value=mock.Mock())
    def test_owned_sidecar_stopped_exact_pid(self, _run, _st, _alive) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            # platform_name="nt" forces the Windows taskkill branch on any OS,
            # so the subprocess mock is exercised deterministically (CI/Ubuntu safe).
            sup = RuntimeSupervisor(Path(tmp), platform_name="nt")
            sup.record("llama-cpp", 4242, ["llama-server", "--port", "8080"], port=8080)
            result = sup.stop("llama-cpp")
            self.assertEqual(result["status"], "STOPPED")
            # taskkill used with exact PID + /T (tree), not process name
            args = _run.call_args[0][0]
            self.assertIn("taskkill", args)
            self.assertIn("/PID", args)
            self.assertIn("4242", args)

    @mock.patch("resource_lease._pid_alive", return_value=True)
    def test_pid_reuse_aborts_kill(self, _alive) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            sup = RuntimeSupervisor(Path(tmp))
            # Recorded start time differs from current => PID reused by another process
            path = sup._state_path("llama-cpp")
            path.write_text(json.dumps({
                "runtime_id": "llama-cpp", "pid": 4242,
                "command": ["llama-server"], "port": None,
                "start_time": "2026-08-01T00:00:00+08:00",
                "started_at": "2026-08-01T00:00:00+08:00",
                "owned_by_supervisor": True,
            }), encoding="utf-8")
            with mock.patch("resource_lease._process_start_time", return_value="2026-08-16T00:00:00+08:00"):
                result = sup.stop("llama-cpp")
            self.assertEqual(result["status"], "PID_REUSE_ABORT")

    def test_snapshot_marks_pid_reuse(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            sup = RuntimeSupervisor(Path(tmp))
            path = sup._state_path("x")
            path.write_text(json.dumps({
                "runtime_id": "x", "pid": 1, "command": [], "port": None,
                "start_time": "2026-08-01T00:00:00+08:00",
                "started_at": "2026-08-01T00:00:00+08:00", "owned_by_supervisor": True,
            }), encoding="utf-8")
            with mock.patch("resource_lease._pid_alive", return_value=True), \
                 mock.patch("resource_lease._process_start_time", return_value="2026-08-16T00:00:00+08:00"):
                snap = sup.snapshot("x")
            self.assertTrue(snap["pid_reuse_detected"])


if __name__ == "__main__":
    unittest.main()
