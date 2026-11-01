"""WORK-LAB Agent Registry（调研报告 Module02 核心）。

统一 Agent 注册：id、type、runtime、provider、capabilities、permissions、status。
对接 runtime_registry 发现的运行时（codex/hermes/deepseek-harness/...）。
本地优先 JSON ledger；确定性、无外部依赖。
"""
from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


AGENT_TYPES = {"coding", "orchestrator", "automation", "knowledge", "design", "custom"}
RUNTIMES = {"codex", "hermes", "deepseek-harness", "claude-code", "opencode", "aider", "custom"}
STATUSES = {"REGISTERED", "ACTIVE", "PAUSED", "QUARANTINED", "RETIRED"}


@dataclass
class AgentRecord:
    """一个注册 Agent（报告字段）。"""
    agent_id: str
    name: str
    agent_type: str = "custom"
    runtime: str = "custom"
    provider: str | None = None
    capabilities: list[str] = field(default_factory=list)
    permissions: list[str] = field(default_factory=list)
    status: str = "REGISTERED"
    registered_at: str = field(default_factory=_now)
    updated_at: str = field(default_factory=_now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "agentId": self.agent_id,
            "name": self.name,
            "agentType": self.agent_type,
            "runtime": self.runtime,
            "provider": self.provider,
            "capabilities": self.capabilities,
            "permissions": self.permissions,
            "status": self.status,
            "registeredAt": self.registered_at,
            "updatedAt": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AgentRecord":
        return cls(
            agent_id=str(data.get("agentId", "")),
            name=str(data.get("name", "")),
            agent_type=str(data.get("agentType", "custom")),
            runtime=str(data.get("runtime", "custom")),
            provider=data.get("provider"),
            capabilities=list(data.get("capabilities", []) or []),
            permissions=list(data.get("permissions", []) or []),
            status=str(data.get("status", "REGISTERED")),
            registered_at=str(data.get("registeredAt", "")),
            updated_at=str(data.get("updatedAt", "")),
        )


class AgentRegistry:
    """本地 JSON ledger（对齐 TaskLedger/WorkUnitStore 模式）。"""

    def __init__(self, root: Path) -> None:
        self.path = (root / "agent_registry.json").resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure()

    def _ensure(self) -> None:
        if not self.path.exists():
            self._write({"agents": {}, "revision": 0})

    def _read(self) -> dict[str, Any]:
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, FileNotFoundError):
            return {"agents": {}, "revision": 0}

    def _write(self, data: dict[str, Any]) -> None:
        self.path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def register(self, *, name: str, agent_type: str = "custom", runtime: str = "custom",
                 provider: str | None = None, capabilities: list[str] | None = None,
                 permissions: list[str] | None = None, agent_id: str | None = None) -> AgentRecord:
        if agent_type not in AGENT_TYPES:
            raise ValueError(f"unknown agent type: {agent_type}")
        if runtime not in RUNTIMES:
            raise ValueError(f"unknown runtime: {runtime}")
        rec = AgentRecord(
            agent_id=agent_id or uuid.uuid4().hex[:12],
            name=name,
            agent_type=agent_type,
            runtime=runtime,
            provider=provider,
            capabilities=list(capabilities or []),
            permissions=list(permissions or []),
        )
        data = self._read()
        data["agents"][rec.agent_id] = rec.to_dict()
        data["revision"] = int(data.get("revision", 0)) + 1
        self._write(data)
        return rec

    def get(self, agent_id: str) -> AgentRecord | None:
        raw = self._read()["agents"].get(agent_id)
        return AgentRecord.from_dict(raw) if raw else None

    def set_status(self, agent_id: str, status: str) -> AgentRecord:
        if status not in STATUSES:
            raise ValueError(f"unknown status: {status}")
        data = self._read()
        raw = data["agents"].get(agent_id)
        if not raw:
            raise KeyError(f"agent not found: {agent_id}")
        raw["status"] = status
        raw["updatedAt"] = _now()
        data["revision"] = int(data.get("revision", 0)) + 1
        self._write(data)
        return AgentRecord.from_dict(raw)

    def list(self, status: str | None = None) -> list[AgentRecord]:
        agents = [AgentRecord.from_dict(raw) for raw in self._read()["agents"].values()]
        if status:
            agents = [a for a in agents if a.status == status]
        return sorted(agents, key=lambda a: a.registered_at, reverse=True)

    def sync_runtime_agents(self, runtime_agents: list[dict[str, Any]]) -> int:
        """对接 runtime_registry 发现的运行时 Agent，自动注册缺失项。"""
        added = 0
        for ra in runtime_agents:
            agent_id = str(ra.get("id") or ra.get("agentId") or "")
            if not agent_id:
                continue
            if self.get(agent_id):
                continue
            self.register(
                agent_id=agent_id,
                name=str(ra.get("name") or agent_id),
                agent_type=str(ra.get("agentType") or "custom"),
                runtime=str(ra.get("runtime") or "custom"),
                provider=ra.get("provider"),
                capabilities=list(ra.get("capabilities", []) or []),
                permissions=list(ra.get("permissions", []) or []),
            )
            added += 1
        return added

    def status_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for raw in self._read()["agents"].values():
            st = str(raw.get("status", "REGISTERED"))
            counts[st] = counts.get(st, 0) + 1
        return counts
