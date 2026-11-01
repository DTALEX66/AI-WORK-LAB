"""WORK-LAB Action Receipt（吸收 Nucleus 执行回执机制，调研报告 Module08/10）。

每次 Agent 执行动作 → 生成不可变回执（身份 / 策略 / 执行 / 结果）：
- identity: agent_id、actor（谁）
- policy: 策略评估结果（allow/deny/require_approval）（为何允许）
- execution: action、target、时间、耗时（做了什么）
- result: outcome、evidence、error（结果如何，证据驱动，不采信自述）

本地优先：JSONL 回执账本（追加式，不可变），证据链可审计。
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


@dataclass
class ActionReceipt:
    receipt_id: str
    agent_id: str
    actor: str
    action: str
    target: Any
    policy_decision: dict[str, Any]          # {allowed, action, reason}
    outcome: str                             # SUCCEEDED | FAILED | BLOCKED | APPROVED
    evidence: list[str] = field(default_factory=list)
    error: str | None = None
    started_at: str = field(default_factory=_now)
    finished_at: str | None = None
    duration_ms: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "receiptId": self.receipt_id,
            "agentId": self.agent_id,
            "actor": self.actor,
            "action": self.action,
            "target": self.target,
            "policy": self.policy_decision,
            "outcome": self.outcome,
            "evidence": self.evidence,
            "error": self.error,
            "startedAt": self.started_at,
            "finishedAt": self.finished_at,
            "durationMs": self.duration_ms,
        }


class ReceiptLedger:
    """JSONL 回执账本（追加式）。"""

    def __init__(self, root: Path) -> None:
        self.path = (root / "action_receipts.jsonl").resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, receipt: ActionReceipt) -> None:
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(receipt.to_dict(), ensure_ascii=False) + "\n")

    def read(self, limit: int = 100) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        rows: list[dict[str, Any]] = []
        with self.path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        return rows[-limit:][::-1]

    def by_agent(self, agent_id: str, limit: int = 50) -> list[dict[str, Any]]:
        return [r for r in self.read(limit * 5) if r.get("agentId") == agent_id][:limit]


def record_execution(
    ledger: ReceiptLedger,
    *,
    agent_id: str,
    actor: str,
    action: str,
    target: Any,
    policy_decision: dict[str, Any],
    outcome: str,
    evidence: list[str] | None = None,
    error: str | None = None,
    started_at: str | None = None,
    finished_at: str | None = None,
) -> ActionReceipt:
    """记录一次 Agent 执行动作的回执（结果驱动的完整闭环）。"""
    receipt = ActionReceipt(
        receipt_id=uuid.uuid4().hex[:12],
        agent_id=agent_id,
        actor=actor,
        action=action,
        target=target,
        policy_decision=dict(policy_decision),
        outcome=outcome,
        evidence=list(evidence or []),
        error=error,
        started_at=started_at or _now(),
        finished_at=finished_at or _now(),
    )
    if receipt.started_at and receipt.finished_at:
        try:
            s = datetime.fromisoformat(receipt.started_at.replace("Z", "+00:00"))
            f = datetime.fromisoformat(receipt.finished_at.replace("Z", "+00:00"))
            receipt.duration_ms = round((f - s).total_seconds() * 1000, 1)
        except (ValueError, TypeError):
            pass
    ledger.append(receipt)
    return receipt
