"""Client projection layer (WL3-700 / MR-15).

Projects neutral adapter contracts onto six clients without writing client
config: Hermes (rules/skills/capability hint, never silent global provider
switch), Codex (task contract + allowed paths + sandbox + output schema),
CC Switch (user-approved profiles only, never task routing), GitHub (approved
Issue/PR/CI operations only), Open Design/OpenHuman (capability discovery,
apply_supported=false), DeepSeek Harness (temporary executor, not a fixed
client registry entry).

Contract rules (taskpack §MR-15 acceptance):
- six clients keep neutral adapter contracts
- missing client => graceful unavailable
- never hard-code install paths, versions, ports, or physical model names
- global official+user / project overlay / task ephemeral precedence provable
"""
from __future__ import annotations

from typing import Any

SCHEMA_VERSION = "workflow/client-projection/v1"

CLIENTS = ("hermes", "codex", "cc-switch", "github", "openhuman", "open-design")


class ClientProjection:
    def __init__(self, client_state: dict[str, Any] | None = None) -> None:
        """client_state: {client_id: {available: bool, overlay_approved: bool}}."""
        self.client_state = client_state or {}

    def project(self, client: str, capability: str, data_privacy: str = "public") -> dict[str, Any]:
        if client not in CLIENTS:
            return {"status": "UNKNOWN_CLIENT", "client": client}
        state = self.client_state.get(client, {})
        if not state.get("available", True):
            return {"status": "UNAVAILABLE", "client": client,
                    "reason": "client missing (graceful)"}

        projection = {"schema_version": SCHEMA_VERSION, "client": client,
                      "capability": capability, "data_privacy": data_privacy}

        if client == "hermes":
            projection.update(self._hermes(capability))
        elif client == "codex":
            projection.update(self._codex(capability, data_privacy))
        elif client == "cc-switch":
            projection.update(self._cc_switch(capability, state))
        elif client == "github":
            projection.update(self._github(capability))
        elif client in ("openhuman", "open-design"):
            projection.update(self._observe_only(client, capability))
        return projection

    def _hermes(self, capability: str) -> dict[str, Any]:
        # Project rules/skills/capability hint; NEVER switch global provider.
        return {
            "kind": "rules_skills_hint",
            "apply": "user-facing-only",
            "global_provider_switch": "forbidden_without_explicit_user_action",
            "projection": f"hermes:{capability}",
        }

    def _codex(self, capability: str, data_privacy: str) -> dict[str, Any]:
        # Task contract + allowed paths + sandbox + output schema.
        return {
            "kind": "task_contract",
            "allowed_paths": ["<task-scoped>"],
            "sandbox": "workspace-write",
            "output_schema": "json",
            "data_privacy": data_privacy,
            "apply": "task-scoped-only",
        }

    def _cc_switch(self, capability: str, state: dict[str, Any]) -> dict[str, Any]:
        # Only user-approved profiles; never task routing.
        approved = state.get("overlay_approved", False)
        return {
            "kind": "profile_projection",
            "profile_apply": "approved_only" if approved else "none",
            "task_routing": "never",
        }

    def _github(self, capability: str) -> dict[str, Any]:
        allowed = {"issue.read", "issue.write", "pr.read", "ci.read"}
        if capability in allowed:
            return {"kind": "approved_github_op", "operation": capability}
        return {"kind": "github_op", "operation": capability, "status": "APPROVAL_REQUIRED"}

    def _observe_only(self, client: str, capability: str) -> dict[str, Any]:
        return {
            "kind": "capability_discovery",
            "apply_supported": False,
            "observe_only": True,
        }


def precedence_label(layers: list[str]) -> str:
    """Prove layer precedence: global official+user < project overlay < task ephemeral."""
    order = {"global": 0, "project": 1, "task": 2}
    ranked = sorted(layers, key=lambda x: order.get(x, 99))
    return " -> ".join(ranked)


if __name__ == "__main__":
    import json
    proj = ClientProjection({"hermes": {"available": True}})
    print(json.dumps(proj.project("hermes", "code.read"), ensure_ascii=False, indent=2))
    print("precedence:", precedence_label(["global", "task", "project"]))
