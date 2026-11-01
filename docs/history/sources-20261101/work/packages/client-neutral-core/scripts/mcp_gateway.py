"""WORK-LAB MCP Gateway（工具治理，调研报告 Module07）。

统一管理 MCP（Model Context Protocol）工具/插件的声明与治理：
- 注册 MCP 服务器声明（name / transport / tools / approval）
- 评估工具调用是否符合策略（允许/拒绝/需审批）
- 插件声明是「转化沉淀产物」：阶段 1 归 WORK-LAB 自有，阶段 2 逆向归档 ArcheAxis

本地优先：只做声明治理与策略评估，不实际启动 MCP 服务器（实际服务器由客户端
宿主运行，如 Hermes/Codex 的 mcp_servers 配置）。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class McpServerDecl:
    name: str
    transport: str  # stdio | http | sse
    tools: list[str] = field(default_factory=list)
    approval_required: bool = False
    enabled: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "transport": self.transport,
            "tools": list(self.tools),
            "approvalRequired": self.approval_required,
            "enabled": self.enabled,
        }


@dataclass
class McpDecision:
    allowed: bool
    reason: str
    approval_required: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {"allowed": self.allowed, "reason": self.reason, "approvalRequired": self.approval_required}


class McpGateway:
    """MCP 工具声明治理与调用评估。"""

    def __init__(self) -> None:
        self._servers: dict[str, McpServerDecl] = {}

    def register(self, decl: McpServerDecl) -> None:
        self._servers[decl.name] = decl

    def unregister(self, name: str) -> None:
        self._servers.pop(name, None)

    def list_servers(self) -> list[dict[str, Any]]:
        return [s.to_dict() for s in self._servers.values()]

    def evaluate(self, *, server: str, tool: str) -> McpDecision:
        decl = self._servers.get(server)
        if decl is None:
            return McpDecision(allowed=False, reason=f"unknown MCP server {server}")
        if not decl.enabled:
            return McpDecision(allowed=False, reason=f"MCP server {server} disabled")
        if tool not in decl.tools:
            return McpDecision(allowed=False, reason=f"tool {tool} not declared on {server}")
        if decl.approval_required:
            return McpDecision(allowed=False, approval_required=True, reason=f"tool {tool} requires approval")
        return McpDecision(allowed=True, reason=f"tool {tool} allowed")


def default_gateway() -> McpGateway:
    """默认网关：无服务器（调用方显式注册，避免隐式信任）。"""
    return McpGateway()
