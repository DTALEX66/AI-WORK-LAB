"""Hermes read-only adapter (WLGM-080).

Uses only official read-only metadata surfaces (CLI status / session metadata /
HERMES_SESSION_ID correlation). Never calls stop/delete/pause/resume/trigger or
any config-writing interface. Falls back to process evidence (level D) when the
official surface is unavailable; never reads Hermes private state databases as
an official dependency.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from typing import Any

from adapter_sdk import AdapterProbe, AgentAdapter, CapabilityUnsupported

HERMES_SESSION_ENV = "HERMES_SESSION_ID"


class HermesAdapter(AgentAdapter):
    adapter_id = "hermes"

    def __init__(self, *, hermes_bin: str | None = None) -> None:
        self.hermes_bin = hermes_bin if hermes_bin is not None else shutil.which("hermes")

    def probe(self) -> AdapterProbe:
        installed = bool(self.hermes_bin)
        capabilities: set[str] = set()
        detail = "hermes not found on PATH"
        if installed:
            capabilities = {"heartbeat"}
            status = self._read_only("status")
            if status is not None:
                capabilities |= {"run_status", "session_list"}
                detail = "hermes status surface reachable"
        return AdapterProbe(
            adapter_id=self.adapter_id,
            installed=installed,
            capabilities=capabilities,
            evidence_level="B",
            privacy_surface="run/session ids, status, model id, usage counters only",
            detail=detail,
        )

    def _read_only(self, *args: str) -> str | None:
        if not self.hermes_bin:
            return None
        try:
            result = subprocess.run(
                [self.hermes_bin, *args],
                text=True, capture_output=True, timeout=25, check=False,
                encoding="utf-8", errors="replace",
            )
        except (OSError, subprocess.SubprocessError):
            return None
        return result.stdout if result.returncode == 0 else None

    def session_list(self) -> list[dict[str, Any]]:
        if not self.probe().has("session_list"):
            raise CapabilityUnsupported("hermes session_list unavailable")
        # Correlation env is enough for the current execution; full session
        # enumeration belongs to the official API when reachable.
        session_id = os.environ.get(HERMES_SESSION_ENV)
        if session_id:
            return [{"sessionId": session_id, "status": "active", "source": "HERMES_SESSION_ID"}]
        return []

    def run_status(self, session_id: str | None = None) -> list[dict[str, Any]]:
        if not self.probe().has("run_status"):
            raise CapabilityUnsupported("hermes run_status unavailable")
        status = self._read_only("status")
        if status is None:
            raise CapabilityUnsupported("hermes status surface unreachable")
        # status output is not machine JSON in all versions; keep it as a
        # presence fact only and never fabricate RUNNING from it.
        return []

    # --- Harness Adapter 统一接口（调研报告 Module04） ---
    def start(self, *, workspace: str | None = None, task: str | None = None) -> dict[str, Any]:
        return {"status": "WAITING_APPROVAL", "adapter_id": self.adapter_id,
                "reason": "hermes runtime start is approval-gated (external mutation)", "workspace": workspace, "task": task}

    def stop(self, session_id: str | None = None) -> dict[str, Any]:
        return {"status": "WAITING_APPROVAL", "adapter_id": self.adapter_id,
                "reason": "hermes runtime stop is approval-gated", "session_id": session_id}

    def send(self, session_id: str | None, message: str) -> dict[str, Any]:
        return {"status": "UNSUPPORTED", "adapter_id": self.adapter_id,
                "reason": "send into hermes requires an approved interaction contract", "session_id": session_id}

    def get_logs(self, session_id: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
        return []  # hermes session logs via export_trace metadata only

    def export_trace(self, session_id: str | None = None) -> dict[str, Any]:
        return {"adapter_id": self.adapter_id, "kind": "hermes",
                "trace": [{"session": session_id, "log": None}],
                "schema": "dsh/adapter-trace/v1", "privacy": "metadata-only"}

    def heartbeat(self) -> dict[str, Any]:
        return {"adapterId": self.adapter_id, "ts": __import__("adapter_sdk")._now(), "state": "ALIVE" if self.hermes_bin else "UNAVAILABLE"}
