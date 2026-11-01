"""WORK-LAB Sandbox Manager（控制平面执行治理，调研报告 Module06）。

按 Level0-3 分级治理 Agent 执行的沙箱边界（不实际执行，只做分级策略评估）：
- Level0：无限制（不推荐，仅显式用户批准）
- Level1：只读（工作区内只读，禁止写/执行）
- Level2：工作区写（仅允许在工作区 Git root 内写，禁止外部路径/网络）
- Level3：完全隔离（临时快照/受限，网络禁用）

本地优先：沙箱规则策略评估，不实际创建进程沙箱（实际沙箱由客户端宿主承担，
如 DSH 的 sandbox 模式）。规则定义阶段 2 逆向归档 ArcheAxis（Machine Knowledge）。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


LEVEL_NAMES = {0: "UNRESTRICTED", 1: "READ_ONLY", 2: "WORKSPACE_WRITE", 3: "ISOLATED"}


@dataclass
class SandboxDecision:
    level: int
    allowed: bool
    reason: str
    denied_paths: list[str] = field(default_factory=list)
    policy_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "level": self.level,
            "levelName": LEVEL_NAMES.get(self.level, "UNKNOWN"),
            "allowed": self.allowed,
            "reason": self.reason,
            "deniedPaths": self.denied_paths,
            "policyId": self.policy_id,
        }


def _norm(p: str) -> str:
    return Path(p).resolve().as_posix().lower()


class SandboxManager:
    """分级沙箱策略评估器。"""

    def __init__(self, workspace_root: str | Path) -> None:
        self.workspace = _norm(str(workspace_root))

    def evaluate(
        self,
        *,
        level: int,
        action: str,
        target_path: str | None = None,
        network: bool = False,
    ) -> SandboxDecision:
        level = int(level)
        if level not in LEVEL_NAMES:
            return SandboxDecision(level=level, allowed=False, reason=f"unknown level {level}")

        # Level0: explicit approval gate only
        if level == 0:
            return SandboxDecision(level=0, allowed=False, reason="level0 requires explicit user approval per action")

        # Level1: read-only — reject writes/execution/network
        if level == 1:
            if action in {"write", "delete", "execute"}:
                return SandboxDecision(level=1, allowed=False, reason="read-only sandbox rejects write/delete/execute")
            if network:
                return SandboxDecision(level=1, allowed=False, reason="read-only sandbox rejects network")
            return SandboxDecision(level=1, allowed=True, reason="read-only allowed")

        # Level2: workspace write — writes only inside workspace root
        if level == 2:
            if action in {"execute", "delete"}:
                return SandboxDecision(level=2, allowed=False, reason="level2 rejects execute/delete outside explicit grant")
            if network:
                return SandboxDecision(level=2, allowed=False, reason="level2 rejects network")
            if target_path and not _norm(target_path).startswith(self.workspace):
                return SandboxDecision(
                    level=2, allowed=False, reason="target outside workspace root",
                    denied_paths=[target_path],
                )
            return SandboxDecision(level=2, allowed=True, reason="workspace write allowed")

        # Level3: isolated — no writes, no network, no execution outside grant
        if level == 3:
            if network:
                return SandboxDecision(level=3, allowed=False, reason="isolated sandbox rejects network")
            if action not in {"read"}:
                return SandboxDecision(level=3, allowed=False, reason="isolated sandbox allows read only")
            return SandboxDecision(level=3, allowed=True, reason="isolated read allowed")

        return SandboxDecision(level=level, allowed=False, reason="unhandled level")
