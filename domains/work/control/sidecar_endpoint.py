"""Sidecar endpoint descriptor validation (WLGM-210).

Tauri shells (and any other consumer) must only trust a Workflow-owned sidecar
endpoint descriptor that satisfies:

- loopback host (127.0.0.1 / localhost / ::1);
- the canonical projection path ``/api/v1/snapshot``;
- a live owning PID (not a stale descriptor);
- a plausible start epoch (not from the future, not impossibly old);
- a bounded, randomized port (ephemeral range) unless explicitly configured.

This is the reference implementation of the checks the Rust shell performs at
runtime; it is fully testable without a Rust toolchain. Tauri compile-time
verification remains PENDING until a Rust toolchain is available.
"""
from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

DESCRIPTOR_SCHEMA_VERSION = "workflow/sidecar-endpoint/v1"
CANONICAL_PROJECTION_PATH = "/api/v1/snapshot"
EPHEMERAL_PORT_MIN = 49152
EPHEMERAL_PORT_MAX = 65535
MAX_START_AGE_SECONDS = 24 * 3600  # a descriptor older than a day is suspicious


@dataclass
class EndpointValidation:
    valid: bool
    errors: list[str]
    descriptor: dict[str, Any] | None = None

    def as_dict(self) -> dict[str, Any]:
        return {"valid": self.valid, "errors": self.errors}


def read_descriptor(path: Path) -> dict[str, Any] | None:
    """Read and parse a sidecar endpoint descriptor; None on any failure."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, UnicodeError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def _is_loopback(host: str) -> bool:
    host = host.strip().lower()
    return host in {"127.0.0.1", "localhost", "::1", "[::1]"}


def validate_descriptor(
    descriptor: dict[str, Any] | None,
    *,
    now: float | None = None,
    require_pid_alive: bool = True,
    require_ephemeral_port: bool = False,
) -> EndpointValidation:
    """Validate a descriptor; errors are explicit and never silently patched."""
    errors: list[str] = []
    if not descriptor:
        return EndpointValidation(valid=False, errors=["descriptor missing or unparseable"])

    if descriptor.get("schemaVersion") != DESCRIPTOR_SCHEMA_VERSION:
        errors.append(f"schemaVersion must be {DESCRIPTOR_SCHEMA_VERSION}")

    host = str(descriptor.get("host", ""))
    if not _is_loopback(host):
        errors.append(f"host must be loopback, got {host!r}")

    projection_url = descriptor.get("projectionUrl")
    if not isinstance(projection_url, str):
        errors.append("projectionUrl required")
    else:
        parsed = urlparse(projection_url)
        if parsed.path != CANONICAL_PROJECTION_PATH:
            errors.append(f"projectionUrl path must be {CANONICAL_PROJECTION_PATH}")
        if not _is_loopback(str(parsed.hostname or "")):
            errors.append("projectionUrl host must be loopback")
        if parsed.query or parsed.fragment:
            errors.append("projectionUrl must not carry query or fragment")

    port = descriptor.get("port")
    if not isinstance(port, int) or not (0 < port < 65536):
        errors.append(f"port must be a valid port, got {port!r}")
    elif require_ephemeral_port and not (EPHEMERAL_PORT_MIN <= port <= EPHEMERAL_PORT_MAX):
        errors.append(f"port {port} outside ephemeral range")

    started_at = descriptor.get("startedAt")
    reference = now if now is not None else time.time()
    if not isinstance(started_at, (int, float)):
        errors.append("startedAt (epoch) required")
    else:
        if started_at > reference + 60:
            errors.append("startedAt is in the future (clock skew or forged descriptor)")
        if reference - started_at > MAX_START_AGE_SECONDS:
            errors.append(f"startedAt too old (> {MAX_START_AGE_SECONDS}s)")

    pid = descriptor.get("pid")
    if not isinstance(pid, int) or pid <= 0:
        errors.append("pid required")
    elif require_pid_alive and not _pid_alive(pid):
        errors.append(f"owning pid {pid} is not alive (stale descriptor)")

    return EndpointValidation(valid=not errors, errors=errors, descriptor=descriptor)


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if pid == os.getpid():
        return True
    if os.name == "nt":
        try:
            import ctypes
            from ctypes import wintypes

            PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
            STILL_ACTIVE = 259
            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            open_process = kernel32.OpenProcess
            open_process.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
            open_process.restype = wintypes.HANDLE
            get_exit_code = kernel32.GetExitCodeProcess
            get_exit_code.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
            get_exit_code.restype = wintypes.BOOL
            close_handle = kernel32.CloseHandle
            close_handle.argtypes = [wintypes.HANDLE]
            close_handle.restype = wintypes.BOOL
            handle = open_process(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
            if not handle:
                return False
            try:
                exit_code = wintypes.DWORD()
                if not get_exit_code(handle, ctypes.byref(exit_code)):
                    return False
                # Windows reports STILL_ACTIVE (259) only while the process
                # has not terminated.  A valid handle alone is insufficient:
                # exited processes can still be opened briefly and would make
                # a stale sidecar descriptor appear live.
                return exit_code.value == STILL_ACTIVE
            finally:
                close_handle(handle)
        except Exception:  # noqa: BLE001 - best-effort liveness check
            return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def capability_probe(descriptor: dict[str, Any] | None) -> dict[str, Any]:
    """WLGM-210: version capability probe — never fabricates support."""
    if not descriptor:
        return {"installed": False, "schemaVersion": None, "capabilities": []}
    version = str(descriptor.get("schemaVersion", ""))
    capabilities: list[str] = []
    if version == DESCRIPTOR_SCHEMA_VERSION:
        capabilities = ["snapshot_v3", "events_v1"]
    return {"installed": True, "schemaVersion": version, "capabilities": capabilities}
