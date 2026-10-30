from __future__ import annotations

import datetime as _dt
import json
import os
from pathlib import Path
import uuid


def _utc_now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds")


def _windows_pid_alive(pid: int) -> bool:
    """Query a process handle without sending a console control event."""
    import ctypes
    from ctypes import wintypes

    process_query_limited_information = 0x1000
    still_active = 259
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.GetExitCodeProcess.argtypes = (wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD))
    kernel32.GetExitCodeProcess.restype = wintypes.BOOL
    kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
    kernel32.CloseHandle.restype = wintypes.BOOL

    handle = kernel32.OpenProcess(process_query_limited_information, False, pid)
    if not handle:
        return ctypes.get_last_error() == 5  # Access denied still proves existence.
    try:
        exit_code = wintypes.DWORD()
        if not kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
            return True
        return exit_code.value == still_active
    finally:
        kernel32.CloseHandle(handle)


class SingleInstanceLock:
    """PID-aware cross-process lock with stale-owner recovery.

    The lock never removes a live or unverifiable owner. Release is fenced by a
    per-acquisition token so one process cannot delete another process's lock.
    """

    def __init__(self, path: Path) -> None:
        self.path = path.resolve()
        self._owned = False
        self._token: str | None = None

    @staticmethod
    def _pid_alive(pid: int) -> bool:
        if pid <= 0:
            return False
        if pid == os.getpid():
            return True
        if os.name == "nt":
            return _windows_pid_alive(pid)
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return False
        except PermissionError:
            return True
        except OSError:
            # Windows reports an invalid-parameter OSError for a missing PID.
            return False
        return True

    def _read_owner(self) -> tuple[bytes, dict[str, object]]:
        raw = self.path.read_bytes()
        try:
            owner = json.loads(raw.decode("utf-8"))
        except (UnicodeError, json.JSONDecodeError) as exc:
            raise RuntimeError("sidecar_lock_unreadable") from exc
        if not isinstance(owner, dict) or not isinstance(owner.get("pid"), int) or not isinstance(owner.get("token"), str):
            raise RuntimeError("sidecar_lock_invalid")
        return raw, owner

    def acquire(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        token = uuid.uuid4().hex
        payload = (
            json.dumps(
                {"pid": os.getpid(), "token": token, "acquired_at": _utc_now()},
                sort_keys=True,
            )
            + "\n"
        ).encode("utf-8")
        for _ in range(2):
            try:
                fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            except FileExistsError as exc:
                raw, owner = self._read_owner()
                if self._pid_alive(int(owner["pid"])):
                    raise RuntimeError("sidecar_already_running") from exc
                try:
                    if self.path.read_bytes() != raw:
                        raise RuntimeError("sidecar_lock_changed")
                    self.path.unlink()
                except FileNotFoundError:
                    pass
                continue
            with os.fdopen(fd, "wb") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            self._owned = True
            self._token = token
            return
        raise RuntimeError("sidecar_lock_contention")

    def release(self) -> None:
        if self._owned:
            try:
                _, owner = self._read_owner()
                if owner.get("pid") == os.getpid() and owner.get("token") == self._token:
                    self.path.unlink(missing_ok=True)
            except (FileNotFoundError, RuntimeError):
                pass
            self._owned = False
            self._token = None

    def status(self) -> dict[str, object] | None:
        """Read-only lock status: owner pid, token, acquired_at, and staleness.

        Session-governance view (absorbed 2026-08-12): consumers can observe
        who holds the lock and for how long without touching it. Returns None
        when the lock is free; raises only for unreadable/invalid lock files.
        """
        if not self.path.exists():
            return None
        _, owner = self._read_owner()
        owner = dict(owner)
        owner["alive"] = self._pid_alive(int(owner["pid"]))
        return owner

    def __enter__(self) -> "SingleInstanceLock":
        self.acquire()
        return self

    def __exit__(self, *_: object) -> None:
        self.release()
