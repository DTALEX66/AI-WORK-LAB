#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""DL-V2 P1-A: DesignProject state machine (authoritative single state).

设计过程保存为显式 DesignState；stage transitions 严格校验（fail-closed）。
Kernel 只依赖 contracts/abstractions，不依赖具体模型或工具。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

STAGES = [
    "draft", "research", "direction", "system", "variant", "critique",
    "revision", "approved", "render", "preflight", "packaged", "delivered", "archived",
]

# 合法 transition（单向主链 + 回退边）
TRANSITIONS: dict[str, set[str]] = {
    "draft": {"research"},
    "research": {"direction"},
    "direction": {"system", "critique"},
    "system": {"variant"},
    "variant": {"critique"},
    "critique": {"revision", "approved"},
    "revision": {"critique", "variant"},
    "approved": {"render", "revision"},
    "render": {"preflight", "revision"},
    "preflight": {"packaged", "revision"},
    "packaged": {"delivered"},
    "delivered": {"archived"},
    "archived": set(),
}

VALID_QUALITY = {"pending", "passed", "failed", "blocked"}
VALID_MODES = {"guided", "copilot", "director", "method", "production"}


@dataclass
class ProjectTransitionError(Exception):
    message: str


@dataclass
class DesignProject:
    project_id: str
    domain: str = ""
    user_mode: str = "director"
    stage: str = "draft"
    quality_status: str = "pending"
    revision: int = 1
    objects: dict[str, str] = field(default_factory=dict)
    history: list[dict] = field(default_factory=list)

    def validate(self) -> list[str]:
        errs: list[str] = []
        if self.stage not in STAGES:
            errs.append(f"invalid stage: {self.stage}")
        if self.quality_status not in VALID_QUALITY:
            errs.append(f"invalid quality_status: {self.quality_status}")
        if self.user_mode not in VALID_MODES:
            errs.append(f"invalid user_mode: {self.user_mode}")
        if self.revision < 1:
            errs.append("revision must be >= 1")
        return errs

    def transition(self, to_stage: str, reason: str, by: str = "kernel") -> None:
        errs = self.validate()
        if errs:
            raise ProjectTransitionError("; ".join(errs))
        allowed = TRANSITIONS.get(self.stage, set())
        if to_stage not in allowed:
            raise ProjectTransitionError(
                f"transition {self.stage} -> {to_stage} not allowed "
                f"(allowed: {sorted(allowed)})"
            )
        self.history.append({
            "at": datetime.now(timezone.utc).isoformat(),
            "from_stage": self.stage,
            "to_stage": to_stage,
            "reason": reason,
            "by": by,
        })
        self.stage = to_stage

    def attach(self, object_key: str, ref: str) -> None:
        self.objects[object_key] = ref
        self.revision += 1

    def to_dict(self) -> dict[str, Any]:
        return {
            "project_id": self.project_id,
            "schemaVersion": "design-lab/design-project-state/v2",
            "stage": self.stage,
            "quality_status": self.quality_status,
            "revision": self.revision,
            "user_mode": self.user_mode,
            "domain": self.domain,
            "objects": self.objects,
            "history": self.history,
        }


def load_project(data: dict) -> DesignProject:
    p = DesignProject(
        project_id=data.get("project_id", ""),
        domain=data.get("domain", ""),
        user_mode=data.get("user_mode", "director"),
        stage=data.get("stage", "draft"),
        quality_status=data.get("quality_status", "pending"),
        revision=data.get("revision", 1),
        objects=data.get("objects", {}),
        history=data.get("history", []),
    )
    return p
