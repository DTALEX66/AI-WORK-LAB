"""ACP compatibility layer (NX-200).

Adds ACP protocol/capability mapping on top of the existing Adapter SDK without
creating a second execution platform.

- init: returns protocol version + supported versions.
- capabilities: exposes the unified capability model for the adapter.
- negotiate: given a requested feature set, returns supported / unsupported with
  graceful degradation (never hard-fails on unknown protocol version).
- detect/observe: read-only ACP operations (safe).
- plan/apply/invoke/rollback: respect existing permission/approval boundaries
  (read-only by default; mutations require explicit approval).
- Qwen Code is a fixture/pilot; if not installed it returns `unavailable` without
  failing the project.
"""
from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from typing import Any

ACP_PROTOCOL_VERSION = "0.1.0"
SUPPORTED_PROTOCOL_VERSIONS = ("0.1.0",)

READ_ONLY_OPERATIONS = ("detect", "capabilities", "observe")
MUTATION_OPERATIONS = ("plan", "apply", "invoke", "rollback")

# Unified capability model mapping for known clients.
# "native-acp": speaks ACP; "internal-bridge": mapped via bridge, never claimed native.
CLIENT_CAPABILITIES: dict[str, dict[str, Any]] = {
    "hermes": {
        "transport": "internal-bridge",
        "operations": ["detect", "capabilities", "plan", "apply", "invoke", "observe", "rollback"],
        "read_only": ["detect", "capabilities", "observe"],
        "note": "mapped via internal bridge; does not claim native ACP",
    },
    "codex": {
        "transport": "internal-bridge",
        "operations": ["detect", "capabilities", "plan", "apply", "invoke", "observe", "rollback"],
        "read_only": ["detect", "capabilities", "observe"],
        "note": "mapped via internal bridge",
    },
    "cursor": {
        "transport": "internal-bridge",
        "operations": ["detect", "capabilities", "observe"],
        "read_only": ["detect", "capabilities", "observe"],
        "note": "read-only observation only",
    },
    "claude-code": {
        "transport": "internal-bridge",
        "operations": ["detect", "capabilities", "observe"],
        "read_only": ["detect", "capabilities", "observe"],
        "note": "read-only observation only",
    },
    "workbuddy": {
        "transport": "internal-bridge",
        "operations": ["detect", "capabilities", "observe"],
        "read_only": ["detect", "capabilities", "observe"],
        "note": "read-only observation only",
    },
    "qwen-code": {
        "transport": "native-acp-pilot",
        "operations": ["detect", "capabilities", "observe"],
        "read_only": ["detect", "capabilities", "observe"],
        "note": "ACP fixture/pilot; returns unavailable if not installed",
    },
}


@dataclass
class AcpAdapter:
    """ACP compatibility layer for a single client adapter."""

    adapter_id: str
    installed: bool = True
    protocol_version: str = ACP_PROTOCOL_VERSION
    approvals: dict[str, Any] = field(default_factory=dict)

    def init(self, requested_version: str | None = None) -> dict[str, Any]:
        """Return protocol identity; negotiate gracefully on unknown versions."""
        if requested_version is None or requested_version in SUPPORTED_PROTOCOL_VERSIONS:
            chosen = self.protocol_version
            degraded = False
        else:
            # Unknown/newer protocol version: fail closed to the supported base.
            chosen = SUPPORTED_PROTOCOL_VERSIONS[0]
            degraded = True
        return {
            "status": "OK",
            "adapter_id": self.adapter_id,
            "protocol_version": chosen,
            "supported_versions": list(SUPPORTED_PROTOCOL_VERSIONS),
            "degraded": degraded,
        }

    def _availability(self) -> dict[str, Any]:
        if not self.installed:
            return {"status": "UNAVAILABLE", "adapter_id": self.adapter_id, "reason": "not-installed"}
        return {"status": "OK", "adapter_id": self.adapter_id}

    def capabilities(self) -> dict[str, Any]:
        base = self._availability()
        if base["status"] == "UNAVAILABLE":
            return base
        cap = CLIENT_CAPABILITIES.get(self.adapter_id, {
            "transport": "internal-bridge",
            "operations": READ_ONLY_OPERATIONS,
            "read_only": READ_ONLY_OPERATIONS,
        })
        return {
            "status": "OK",
            "adapter_id": self.adapter_id,
            "protocol_version": self.protocol_version,
            "transport": cap["transport"],
            "operations": list(cap["operations"]),
            "read_only": list(cap["read_only"]),
            "mutation_requires_approval": True,
        }

    def negotiate(self, requested_features: list[str]) -> dict[str, Any]:
        """Negotiate requested features -> supported / unsupported (graceful)."""
        cap = self.capabilities()
        if cap["status"] == "UNAVAILABLE":
            return {**cap, "requested": requested_features, "unsupported": requested_features}
        supported = set(cap["operations"])
        unsupported = [f for f in requested_features if f not in supported]
        return {
            "status": "OK",
            "adapter_id": self.adapter_id,
            "requested": requested_features,
            "supported": [f for f in requested_features if f in supported],
            "unsupported": unsupported,
            "degraded": bool(unsupported),
        }

    def detect(self, request: dict[str, Any]) -> dict[str, Any]:
        return {**self._availability(), "operation": "detect"}

    def observe(self, request: dict[str, Any]) -> dict[str, Any]:
        base = self._availability()
        if base["status"] == "UNAVAILABLE":
            return {**base, "operation": "observe"}
        return {**base, "operation": "observe", "read_only": True, "events": []}

    def plan(self, request: dict[str, Any]) -> dict[str, Any]:
        """Read-only by default; a mutation plan requires explicit approval."""
        if request.get("external_mutation"):
            return {
                "status": "WAITING_APPROVAL",
                "plan_id": f"acp-plan-{request.get('run_id', 'x')}",
                "approval": {"required": True, "status": "PENDING"},
                "external_mutation": True,
            }
        return {"status": "READ_ONLY", "plan_id": f"acp-plan-{request.get('run_id', 'x')}", "external_mutation": False}

    def apply(self, plan: dict[str, Any]) -> dict[str, Any]:
        approval = plan.get("approval", {})
        if plan.get("external_mutation") and (approval.get("status") != "APPROVED"):
            raise PermissionError("ACP apply requires explicit approval for mutation")
        return {"status": "APPLIED", "plan_id": plan.get("plan_id"), "external_mutation": plan.get("external_mutation", False)}

    def invoke(self, request: dict[str, Any]) -> dict[str, Any]:
        if request.get("external_mutation"):
            raise PermissionError("ACP invoke of a mutation requires explicit approval")
        return {"status": "INVOKED", "run_id": request.get("run_id")}

    def rollback(self, plan: dict[str, Any]) -> dict[str, Any]:
        return {"status": "ROLLED_BACK", "plan_id": plan.get("plan_id"), "external_mutation": plan.get("external_mutation", False)}

    # --- Harness Adapter 统一接口（对齐调研报告 Module04；ACP 协议层映射） ---
    def start(self, *, workspace: str | None = None, task: str | None = None) -> dict[str, Any]:
        return {"status": "WAITING_APPROVAL", "adapter_id": self.adapter_id,
                "reason": "ACP runtime start is approval-gated (external mutation)", "workspace": workspace, "task": task}

    def stop(self, session_id: str | None = None) -> dict[str, Any]:
        return {"status": "WAITING_APPROVAL", "adapter_id": self.adapter_id,
                "reason": "ACP runtime stop is approval-gated", "session_id": session_id}

    def send(self, session_id: str | None, message: str) -> dict[str, Any]:
        return {"status": "UNSUPPORTED", "adapter_id": self.adapter_id,
                "reason": "ACP send requires an approved interaction contract", "session_id": session_id}

    def get_logs(self, session_id: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
        return []  # ACP session logs via export_trace metadata only

    def export_trace(self, session_id: str | None = None) -> dict[str, Any]:
        return {"adapter_id": self.adapter_id, "kind": "acp",
                "trace": [{"session": session_id, "log": None}],
                "schema": "dsh/adapter-trace/v1", "privacy": "metadata-only",
                "protocol": self.protocol_version}


def make_qwen_code_pilot() -> AcpAdapter:
    """Qwen Code ACP pilot. Returns unavailable if the CLI is not installed."""
    installed = shutil.which("qwen-code") is not None or shutil.which("qwen") is not None
    return AcpAdapter(adapter_id="qwen-code", installed=installed)


def build_adapter(client_id: str) -> AcpAdapter:
    """Build the ACP adapter for a known client id."""
    if client_id not in CLIENT_CAPABILITIES:
        raise ValueError(f"unknown client id: {client_id}")
    if client_id == "qwen-code":
        return make_qwen_code_pilot()
    return AcpAdapter(adapter_id=client_id)
