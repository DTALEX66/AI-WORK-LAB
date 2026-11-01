"""WORK-LAB Work Unit Engine — 工程任务统一实体（调研报告 Module03 最重要实体）。

标准状态机（报告）：CREATED → PLANNED → ASSIGNED → RUNNING → WAITING →
VERIFYING → COMPLETED；异常：FAILED / BLOCKED / NEED_APPROVAL / QUARANTINE。

字段（报告）：id、project、goal、agents、workspace、status、verification、
evidence、cost。事件化：每次状态迁移生成标准化事件（Event Bus 概念）。

本地优先：JSON ledger（对齐 TaskLedger 模式），无外部依赖。
"""
from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class WorkUnitState(str, Enum):
    CREATED = "CREATED"
    PLANNED = "PLANNED"
    ASSIGNED = "ASSIGNED"
    RUNNING = "RUNNING"
    WAITING = "WAITING"
    VERIFYING = "VERIFYING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    BLOCKED = "BLOCKED"
    NEED_APPROVAL = "NEED_APPROVAL"
    QUARANTINE = "QUARANTINE"

    @classmethod
    def parse(cls, value: str) -> "WorkUnitState":
        return cls(str(value).upper())


# 合法状态迁移表（确定性控制：非法迁移直接拒绝，不静默）。
_TRANSITIONS: dict[WorkUnitState, set[WorkUnitState]] = {
    WorkUnitState.CREATED: {WorkUnitState.PLANNED, WorkUnitState.FAILED, WorkUnitState.QUARANTINE},
    WorkUnitState.PLANNED: {WorkUnitState.ASSIGNED, WorkUnitState.BLOCKED, WorkUnitState.FAILED},
    WorkUnitState.ASSIGNED: {WorkUnitState.RUNNING, WorkUnitState.BLOCKED, WorkUnitState.NEED_APPROVAL},
    WorkUnitState.RUNNING: {WorkUnitState.WAITING, WorkUnitState.VERIFYING, WorkUnitState.FAILED, WorkUnitState.BLOCKED, WorkUnitState.NEED_APPROVAL},
    WorkUnitState.WAITING: {WorkUnitState.RUNNING, WorkUnitState.FAILED, WorkUnitState.BLOCKED},
    WorkUnitState.VERIFYING: {WorkUnitState.COMPLETED, WorkUnitState.FAILED, WorkUnitState.NEED_APPROVAL},
    WorkUnitState.COMPLETED: set(),
    WorkUnitState.FAILED: {WorkUnitState.PLANNED, WorkUnitState.ASSIGNED, WorkUnitState.QUARANTINE},
    WorkUnitState.BLOCKED: {WorkUnitState.ASSIGNED, WorkUnitState.RUNNING},
    WorkUnitState.NEED_APPROVAL: {WorkUnitState.ASSIGNED, WorkUnitState.RUNNING, WorkUnitState.QUARANTINE},
    WorkUnitState.QUARANTINE: {WorkUnitState.ASSIGNED},
}


@dataclass
class WorkUnit:
    """一个工程工作单元（报告字段全集）。"""
    id: str
    project: str
    goal: str
    agents: list[str] = field(default_factory=list)
    workspace: str | None = None
    status: WorkUnitState = WorkUnitState.CREATED
    verification: dict[str, Any] = field(default_factory=dict)
    evidence: list[str] = field(default_factory=list)
    cost: dict[str, Any] = field(default_factory=dict)
    # WLR-410: routing result (lane/modelRef from model_router; best-effort, may be None)
    model_lane: str | None = None
    model_ref: str | None = None
    events: list[dict[str, Any]] = field(default_factory=list)
    created_at: str = field(default_factory=_now)
    updated_at: str = field(default_factory=_now)

    def transition(self, target: WorkUnitState, *, actor: str = "system", reason: str = "") -> None:
        allowed = _TRANSITIONS[self.status]
        if target not in allowed:
            raise ValueError(f"invalid WorkUnit transition {self.status.value} -> {target.value}")
        prev = self.status
        self.status = target
        self.updated_at = _now()
        self.events.append({
            "type": "workunit/state",
            "workUnitId": self.id,
            "from": prev.value,
            "to": target.value,
            "actor": actor,
            "at": _now(),
            "reason": reason,
        })

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "project": self.project,
            "goal": self.goal,
            "agents": self.agents,
            "workspace": self.workspace,
            "status": self.status.value,
            "verification": self.verification,
            "evidence": self.evidence,
            "cost": self.cost,
            "events": self.events,
            "createdAt": self.created_at,
            "updatedAt": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "WorkUnit":
        return cls(
            id=str(data.get("id", "")),
            project=str(data.get("project", "")),
            goal=str(data.get("goal", "")),
            agents=list(data.get("agents", []) or []),
            workspace=data.get("workspace"),
            status=WorkUnitState.parse(str(data.get("status", "CREATED"))),
            verification=dict(data.get("verification", {}) or {}),
            evidence=list(data.get("evidence", []) or []),
            cost=dict(data.get("cost", {}) or {}),
            events=list(data.get("events", []) or []),
            created_at=str(data.get("createdAt", "")),
            updated_at=str(data.get("updatedAt", "")),
        )


class WorkUnitStore:
    """本地 JSON ledger（对齐 TaskLedger 模式；后续可迁移 canonical work_units 表）。"""

    def __init__(self, root: Path) -> None:
        self.path = (root / "work_units.json").resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure()

    def _ensure(self) -> None:
        if not self.path.exists():
            self._write({"workUnits": {}, "revision": 0})

    def _read(self) -> dict[str, Any]:
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, FileNotFoundError):
            return {"workUnits": {}, "revision": 0}

    def _write(self, data: dict[str, Any]) -> None:
        self.path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def create(self, *, project: str, goal: str, agents: list[str] | None = None,
               workspace: str | None = None, work_unit_id: str | None = None) -> WorkUnit:
        # WLR-410: route goal -> capability lane (zero model calls; deterministic rules).
        model_lane = None
        model_ref = None
        try:
            from model_router import TaskSignal, route
            plan = route(TaskSignal(task=goal, risk="low"))
            model_lane = plan.lane
            model_ref = plan.model_ref
        except Exception:
            model_lane, model_ref = None, None  # routing is best-effort, never blocks
        wu = WorkUnit(
            id=work_unit_id or uuid.uuid4().hex[:12],
            project=project,
            goal=goal,
            agents=list(agents or []),
            workspace=workspace,
            model_lane=model_lane,
            model_ref=model_ref,
        )
        data = self._read()
        data["workUnits"][wu.id] = wu.to_dict()
        data["revision"] = int(data.get("revision", 0)) + 1
        self._write(data)
        return wu

    def get(self, work_unit_id: str) -> WorkUnit | None:
        data = self._read()
        raw = data["workUnits"].get(work_unit_id)
        return WorkUnit.from_dict(raw) if raw else None

    def transition(self, work_unit_id: str, target: str, *, actor: str = "system", reason: str = "") -> WorkUnit:
        data = self._read()
        raw = data["workUnits"].get(work_unit_id)
        if not raw:
            raise KeyError(f"work unit not found: {work_unit_id}")
        wu = WorkUnit.from_dict(raw)
        wu.transition(WorkUnitState.parse(target), actor=actor, reason=reason)
        data["workUnits"][work_unit_id] = wu.to_dict()
        data["revision"] = int(data.get("revision", 0)) + 1
        self._write(data)
        return wu

    def attach_verification(self, work_unit_id: str, verification: dict[str, Any]) -> WorkUnit:
        data = self._read()
        raw = data["workUnits"].get(work_unit_id)
        if not raw:
            raise KeyError(f"work unit not found: {work_unit_id}")
        raw["verification"] = dict(verification)
        raw["updatedAt"] = _now()
        data["revision"] = int(data.get("revision", 0)) + 1
        self._write(data)
        return WorkUnit.from_dict(raw)

    def list(self, status: str | None = None) -> list[WorkUnit]:
        data = self._read()
        units = [WorkUnit.from_dict(raw) for raw in data["workUnits"].values()]
        if status:
            want = WorkUnitState.parse(status)
            units = [u for u in units if u.status == want]
        return sorted(units, key=lambda u: u.created_at, reverse=True)

    def events(self, work_unit_id: str) -> list[dict[str, Any]]:
        wu = self.get(work_unit_id)
        return wu.events if wu else []

    def status_counts(self) -> dict[str, int]:
        data = self._read()
        counts: dict[str, int] = {}
        for raw in data["workUnits"].values():
            st = str(raw.get("status", "CREATED"))
            counts[st] = counts.get(st, 0) + 1
        return counts
