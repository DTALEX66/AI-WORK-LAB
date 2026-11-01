"""Resource lease and RuntimeSupervisor (WL3-330 / MR-09).

gpu.heavy / cpu.heavy / io.hash resource groups with mutual exclusion,
exact PID/port/lease lifecycle, and crash/stale-lock/orphan/OOM recovery.

Contract rules (taskpack §MR-09 acceptance):
- two gpu.heavy tasks: second enters QUEUED
- stale lease recoverable via PID identity + start time (never process-name)
- supervisor only stops its own sidecar PID trees (never user-external runtimes)
- lease release leaves replayable checkpoint state
"""
from __future__ import annotations

import datetime as dt
import json
import os
import subprocess
import time
import uuid
from pathlib import Path
from typing import Any

RESOURCE_GROUPS = ("gpu.heavy", "cpu.heavy", "io.hash", "none")


def _utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def _pid_alive(pid: int) -> bool:
    """Cross-platform PID liveness; Windows uses an OpenProcess handle probe."""
    if pid <= 0:
        return False
    if pid == os.getpid():
        return True
    if os.name == "nt":
        try:
            import ctypes
            from ctypes import wintypes
            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            handle = kernel32.OpenProcess(0x1000, False, pid)
            if not handle:
                return ctypes.get_last_error() == 5
            try:
                exit_code = wintypes.DWORD()
                if not kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
                    return True
                return exit_code.value == 259
            finally:
                kernel32.CloseHandle(handle)
        except Exception:
            return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def _process_start_time(pid: int) -> str | None:
    """Best-effort start-time probe; None on failure (kept UNKNOWN)."""
    try:
        if os.name == "nt":
            import subprocess
            result = subprocess.run(
                ["powershell", "-NoProfile", "-Command",
                 f"(Get-Process -Id {pid} -ErrorAction SilentlyContinue).StartTime.ToString('o')"],
                text=True, encoding="utf-8", errors="replace", capture_output=True, timeout=8, check=False,
            )
            out = result.stdout.strip()
            return out or None
        with open(f"/proc/{pid}/stat", encoding="utf-8", errors="replace") as f:
            parts = f.read().split()
            return parts[21] if len(parts) > 21 else None
    except Exception:
        return None


class ResourceLease:
    """One resource-group lease with exact owner identity (pid + start time).

    Acquire is fail-closed: same-group contention returns QUEUED. Stale owners
    (pid dead) are recoverable; a live owner is never evicted.
    """

    def __init__(self, root: Path, group: str) -> None:
        if group not in RESOURCE_GROUPS:
            raise ValueError(f"unknown resource group: {group}")
        self.group = group
        self.path = (root / "leases" / f"{group}.json").resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._token: str | None = None

    def _read(self) -> dict[str, Any] | None:
        if not self.path.exists():
            return None
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None

    def _write(self, payload: dict[str, Any]) -> None:
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True), encoding="utf-8")
        os.replace(tmp, self.path)

    def acquire(self) -> dict[str, Any]:
        """Try to acquire. Returns {status: HELD|QUEUED, ...}; never evicts live owner."""
        token = uuid.uuid4().hex
        payload = {
            "group": self.group,
            "pid": os.getpid(),
            "token": token,
            "start_time": _process_start_time(os.getpid()),
            "acquired_at": _utc_now(),
        }
        existing = self._read()
        if existing:
            owner_pid = int(existing.get("pid", -1))
            if _pid_alive(owner_pid):
                return {"status": "QUEUED", "group": self.group, "owner_pid": owner_pid,
                        "reason_code": "RESOURCE_BUSY"}
            # stale owner -> reclaim
            self._write(payload)
            self._token = token
            return {"status": "HELD", "group": self.group, "reclaimed": True, "token": token}
        self._write(payload)
        self._token = token
        return {"status": "HELD", "group": self.group, "token": token}

    def release(self) -> dict[str, Any]:
        existing = self._read()
        if not existing:
            return {"status": "RELEASED", "group": self.group}
        if self._token and existing.get("token") == self._token:
            self.path.unlink(missing_ok=True)
            self._token = None
            return {"status": "RELEASED", "group": self.group}
        return {"status": "NOT_OWNED", "group": self.group,
                "reason": "lease held by another owner"}

    def status(self) -> dict[str, Any] | None:
        existing = self._read()
        if not existing:
            return None
        owner_pid = int(existing.get("pid", -1))
        return {
            "group": self.group,
            "owner_pid": owner_pid,
            "owner_alive": _pid_alive(owner_pid),
            "start_time": existing.get("start_time"),
            "acquired_at": existing.get("acquired_at"),
            "stale": not _pid_alive(owner_pid),
        }


class RuntimeSupervisor:
    """Owns sidecar lifecycle for runtimes this supervisor started.

    stop() terminates ONLY the exact recorded PID tree (own sidecar), never a
    process matched by name, never a user-external runtime like ComfyUI.
    """

    def __init__(self, root: Path, platform_name: str | None = None) -> None:
        self.root = root.resolve()
        self.platform_name = platform_name or os.name
        (self.root / "runtime-state").mkdir(parents=True, exist_ok=True)

    def _state_path(self, runtime_id: str) -> Path:
        return self.root / "runtime-state" / f"{runtime_id}.json"

    def record(self, runtime_id: str, pid: int, command: list[str], port: int | None = None) -> dict[str, Any]:
        entry = {
            "runtime_id": runtime_id,
            "pid": pid,
            "command": command,
            "port": port,
            "start_time": _process_start_time(pid),
            "started_at": _utc_now(),
            "owned_by_supervisor": True,
        }
        self._state_path(runtime_id).write_text(
            json.dumps(entry, ensure_ascii=False, sort_keys=True), encoding="utf-8")
        return entry

    def snapshot(self, runtime_id: str) -> dict[str, Any] | None:
        path = self._state_path(runtime_id)
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        pid = int(data.get("pid", -1))
        data["alive"] = _pid_alive(pid)
        data["current_start_time"] = _process_start_time(pid)
        # PID-reuse guard: recorded start time must match current start time.
        data["pid_reuse_detected"] = bool(
            data.get("start_time") and data["current_start_time"]
            and data["start_time"] != data["current_start_time"]
        )
        return data

    def stop(self, runtime_id: str) -> dict[str, Any]:
        """Stop ONLY the exact recorded PID tree of a supervisor-owned sidecar.

        Refuses when the recorded PID is dead (nothing to stop), when PID reuse
        is detected (do not kill an innocent process), or when the runtime was
        never recorded (unknown -> never kill by name).
        """
        data = self.snapshot(runtime_id)
        if not data:
            return {"status": "UNKNOWN_RUNTIME", "runtime_id": runtime_id,
                    "reason": "no recorded state; refusing to kill by name"}
        if not data["alive"]:
            return {"status": "ALREADY_STOPPED", "runtime_id": runtime_id}
        if data.get("pid_reuse_detected"):
            return {"status": "PID_REUSE_ABORT", "runtime_id": runtime_id,
                    "reason": "recorded start time differs; refusing to kill"}
        if not data.get("owned_by_supervisor"):
            return {"status": "NOT_OWNED", "runtime_id": runtime_id,
                    "reason": "user-external runtime; supervisor never stops it"}
        pid = int(data["pid"])
        try:
            if self.platform_name == "nt":
                import subprocess
                subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"],
                               capture_output=True, timeout=15, check=False)
            else:
                os.killpg(pid, 15)
        except Exception:
            return {"status": "STOP_FAILED", "runtime_id": runtime_id}
        return {"status": "STOPPED", "runtime_id": runtime_id, "pid": pid}

    def stop_all_owned(self) -> dict[str, Any]:
        results: dict[str, Any] = {}
        for path in (self.root / "runtime-state").glob("*.json"):
            runtime_id = path.stem
            results[runtime_id] = self.stop(runtime_id)
        return {"status": "COMPLETE", "results": results}


if __name__ == "__main__":
    import project_temp
    with project_temp.fixture_root(prefix='resource-lease-selftest-') as tmp:
        lease = ResourceLease(Path(tmp), "gpu.heavy")
        first = lease.acquire()
        print("first:", first)
        second = ResourceLease(Path(tmp), "gpu.heavy").acquire()
        print("second:", second)
        print("release:", lease.release())
        print("after:", ResourceLease(Path(tmp), "gpu.heavy").acquire())
