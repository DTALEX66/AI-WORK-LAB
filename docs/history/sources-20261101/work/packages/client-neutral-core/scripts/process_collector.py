"""Windows agent-instance / process fallback collector (WLGM-110).

Low-trust, low-interference candidate evidence when native interfaces are
missing. Collects PID, parent PID, process start time, image name and a
sanitized argument hint. Never reads full environment variables; never injects,
debugs or opens process memory; never requires admin. Electron multi-session
shares a main process: only one agent *instance* is reported per image.
"""
from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from typing import Any

AGENT_IMAGE_PATTERNS = ("hermes", "codex", "claude", "opencode", "aider", "cursor")


@dataclass
class ProcessObservation:
    pid: int
    parent_pid: int | None
    image_name: str
    started_at: str | None = None
    sanitized_args: str = ""

    def to_record(self) -> dict[str, Any]:
        return {
            "pid": self.pid,
            "parentPid": self.parent_pid,
            "imageName": self.image_name,
            "startedAt": self.started_at,
            "sanitizedArgs": self.sanitized_args[:200],  # bounded, never full cmdline
        }


def _wmic_or_powershell() -> list[dict[str, str]]:
    """Best-effort process table via PowerShell (no admin)."""
    script = (
        "Get-CimInstance Win32_Process | "
        "Select-Object ProcessId,ParentProcessId,Name,CreationDate | "
        "ConvertTo-Json -Compress"
    )
    try:
        result = subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script],
            text=True, capture_output=True, timeout=30, check=False,
            encoding="utf-8", errors="replace",
        )
    except (OSError, subprocess.SubprocessError):
        return []
    if result.returncode != 0:
        return []
    try:
        import json

        data = json.loads(result.stdout.strip() or "[]")
    except (ValueError, json.JSONDecodeError):
        return []
    if isinstance(data, dict):
        data = [data]
    return data


def collect_agent_processes(patterns: tuple[str, ...] = AGENT_IMAGE_PATTERNS) -> list[ProcessObservation]:
    """Return one observation per agent instance image (deduped by image+parent)."""
    rows = _wmic_or_powershell()
    seen: dict[str, ProcessObservation] = {}
    for row in rows:
        name = str(row.get("Name", "")).lower()
        if not any(pattern in name for pattern in patterns):
            continue
        try:
            pid = int(row.get("ProcessId"))
        except (TypeError, ValueError):
            continue
        try:
            parent = int(row["ParentProcessId"]) if row.get("ParentProcessId") not in (None, "") else None
        except (TypeError, ValueError):
            parent = None
        # Electron multi-session: same image -> one instance (parent as key).
        key = f"{name}:{parent}"
        if key in seen:
            continue
        seen[key] = ProcessObservation(
            pid=pid,
            parent_pid=parent,
            image_name=name,
            started_at=str(row.get("CreationDate", ""))[:19],
        )
    return list(seen.values())
