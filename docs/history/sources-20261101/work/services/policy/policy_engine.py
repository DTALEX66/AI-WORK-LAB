"""WORK-LAB Policy Engine（调研报告 Module08 Governance 起步）。

动作级策略检查：Agent 请求动作 → 规则评估 → allow / deny / require_approval。
规则类型：路径规则（禁写/禁删生产目录）、命令规则（危险命令黑名单）、
越权规则（Agent 权限 vs 目标权限）。
确定性评估（无 LLM 参与），本地优先。

注意：本文件避免字面反斜杠（Windows 路径统一用正斜杠归一化比较），
正则空白用 [ \t ] 字符类，防止生成/搬运过程中的转义破坏。
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


@dataclass
class PolicyDecision:
    allowed: bool
    reason: str
    action: str = "deny"  # allow | deny | require_approval

    def to_dict(self) -> dict[str, Any]:
        return {"allowed": self.allowed, "action": self.action, "reason": self.reason}


def _norm_path(value: Any) -> str:
    return str(value or "").replace("\\", "/").lower()


class PolicyRule:
    """单个策略规则。evaluate 返回 None 表示不适用；否则返回决策。"""

    def evaluate(self, agent: dict[str, Any], action: str, target: Any) -> PolicyDecision | None:
        raise NotImplementedError


class PathRule(PolicyRule):
    """路径规则：禁止对保护路径的写/删操作（路径统一正斜杠小写比较）。"""

    def __init__(self, protected_paths: list[str], name: str = "path-protect",
                 forbidden_actions: set[str] | None = None) -> None:
        self.protected = [_norm_path(p) for p in protected_paths]
        self.name = name
        self.forbidden = forbidden_actions or {"delete", "remove", "rm", "truncate", "write"}

    def evaluate(self, agent: dict[str, Any], action: str, target: Any) -> PolicyDecision | None:
        t = _norm_path(target)
        if not t:
            return None
        hit = next((p for p in self.protected if t.startswith(p)), None)
        if hit is None:
            return None
        act = str(action or "").lower()
        if act in self.forbidden:
            return PolicyDecision(False, f"{self.name}: {action} on protected path {hit}", "deny")
        return PolicyDecision(True, f"{self.name}: allowed on {hit}", "allow")


class CommandRule(PolicyRule):
    """命令规则：危险命令黑名单（空白用 [ \t ] 字符类，避免反斜杠转义）。"""

    def __init__(self, patterns: list[str], name: str = "command-block") -> None:
        self.patterns = [re.compile(p, re.IGNORECASE) for p in patterns]
        self.name = name

    def evaluate(self, agent: dict[str, Any], action: str, target: Any) -> PolicyDecision | None:
        text = str(target or "") + " " + str(action or "")
        if any(p.search(text) for p in self.patterns):
            return PolicyDecision(False, f"{self.name}: dangerous command blocked", "deny")
        return None


class CapabilityRule(PolicyRule):
    """越权规则：动作需要的能力不在 Agent 权限列表 → require_approval。"""

    def __init__(self, action_capability: dict[str, str], name: str = "capability-gate") -> None:
        self.map = action_capability  # action -> required capability
        self.name = name

    def evaluate(self, agent: dict[str, Any], action: str, target: Any) -> PolicyDecision | None:
        required = self.map.get(str(action or "").lower())
        if not required:
            return None
        caps = set(agent.get("capabilities", []) or [])
        if required in caps:
            return PolicyDecision(True, f"{self.name}: capability {required} present", "allow")
        return PolicyDecision(False, f"{self.name}: missing capability {required}", "require_approval")


class PolicyEngine:
    """策略引擎：顺序评估规则，首个决定性结果胜出；默认 allow。"""

    def __init__(self, rules: list[PolicyRule] | None = None) -> None:
        self.rules: list[PolicyRule] = list(rules or [])

    def add_rule(self, rule: PolicyRule) -> None:
        self.rules.append(rule)

    def check(self, agent: dict[str, Any], action: str, target: Any) -> PolicyDecision:
        for rule in self.rules:
            decision = rule.evaluate(agent, action, target)
            if decision is not None:
                return decision
        return PolicyDecision(True, "no rule matched", "allow")

    def check_many(self, agent: dict[str, Any], actions: list[dict[str, Any]]) -> list[PolicyDecision]:
        return [self.check(agent, a.get("action", ""), a.get("target")) for a in actions]


def default_worklab_engine() -> PolicyEngine:
    """WORK-LAB 默认策略引擎（本地开发语义，路径用正斜杠归一化）。"""
    return PolicyEngine([
        PathRule([r"D:/All projects/WORK-LAB/.git", r"D:/All projects/WORK-LAB/.project/governance"],
                 forbidden_actions={"delete", "remove", "rm", "truncate"}),
        CommandRule([
            r"git[ 	]+push[ 	]+(-f|--force)",
            r"rm[ 	]+-rf[ 	]+/",
            r"format[ 	]+[a-z]:",
            r"del[ 	]+/s[ 	]+/q[ 	]+[a-z]:",
        ]),
        CapabilityRule({
            "git-push": "git:push",
            "delete-production": "production:delete",
            "apply-config": "config:apply",
        }),
    ])
