"""Memory governance engine (WL3-310).

Applies scope, TTL, supersedes, conflict, project isolation and pinned-context
rules to memory metadata. Never persists content bodies. User's most recent
explicit instruction wins over old memories; safety/approval/completion
contracts are pinned and cannot be dropped by compaction.

v5 分层定位（2026-08-18）：本模块治理的是「客户端适配记忆」的元数据规则
（WORK-LAB 控制平面的 portable Memory 投影）。长期知识记忆属于
ArcheAxis（唯一知识真源）；阶段 2（ArcheAxis 完整后）经 Knowledge/Memory
API 对接，本模块不存知识内容、不替代 ArcheAxis 记忆治理。
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from growth_watcher import validate_memory

PINNED_CONTEXT_KINDS = {"safety-boundary", "approval-boundary", "completion-contract"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _iso_to_epoch(value: str | None) -> float | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def is_expired(record: dict[str, Any], *, at: str | None = None) -> bool:
    if record.get("pinned_context") is True:
        return False  # pinned contracts never expire by TTL
    valid_to = _iso_to_epoch(record.get("valid_to"))
    if valid_to is None and record.get("ttl_days") is not None:
        valid_from = _iso_to_epoch(record.get("valid_from")) or _iso_to_epoch(_now())
        valid_to = valid_from + float(record["ttl_days"]) * 86400
    if valid_to is None:
        return False
    reference = _iso_to_epoch(at) or _iso_to_epoch(_now())
    return reference > valid_to


def supersedes_active(memory_id: str, records: Iterable[dict[str, Any]]) -> bool:
    return any(
        record.get("supersedes") == memory_id and record.get("status") == "approved"
        for record in records
    )


def detect_conflicts(records: Iterable[dict[str, Any]]) -> list[list[str]]:
    groups: list[list[str]] = []
    index = list(records)
    for record in index:
        memory_id = record["memory_id"]
        conflicts = set(record.get("conflicts_with") or [])
        members = [memory_id]
        for other in index:
            if other["memory_id"] == memory_id:
                continue
            if other["memory_id"] in conflicts or memory_id in (other.get("conflicts_with") or []):
                members.append(other["memory_id"])
        if len(members) > 1:
            key = tuple(sorted(members))
            if key not in [tuple(sorted(g)) for g in groups]:
                groups.append(sorted(members))
    return groups


def project_isolation(records: Iterable[dict[str, Any]], project_id: str) -> list[dict[str, Any]]:
    """Project A memories never leak into project B (domain/global shared)."""
    return [
        record
        for record in records
        if record.get("project_id") == project_id or record.get("scope") in {"domain", "global"}
    ]


def compaction_manifest(records: Iterable[dict[str, Any]], *, at: str | None = None) -> dict[str, Any]:
    """Deterministic compaction plan with retained/dropped/reason manifest.

    Pinned safety/approval/completion contracts are always retained. No
    semantic-less drop-oldest is performed; each drop carries a reason and
    traces back to the original content digest.
    """
    retained: list[dict[str, Any]] = []
    dropped: list[dict[str, Any]] = []
    for record in records:
        reason = None
        if record.get("pinned_context") is True:
            reason = None  # never dropped
        elif is_expired(record, at=at):
            reason = "expired-ttl"
        elif supersedes_active(record["memory_id"], records):
            reason = "superseded"
        if reason:
            dropped.append(
                {
                    "memory_id": record["memory_id"],
                    "content_digest": record["content_digest"],
                    "reason": reason,
                    "dropped_at": at or _now(),
                }
            )
        else:
            retained.append(record)
    return {
        "schema_version": "workflow/memory-compaction/v1",
        "retained": [record["memory_id"] for record in retained],
        "dropped": dropped,
        "retained_count": len(retained),
        "dropped_count": len(dropped),
        "traceable": all(item.get("content_digest") for item in dropped),
    }


def latest_instruction_wins(records: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """Deterministic winner across conflicting approved memories.

    Tie-break order: pinned_context first, then higher confidence, then newer
    valid_from, then memory_id. This models 'user's latest explicit instruction
    wins' without requiring wall-clock order.
    """
    approved = [record for record in records if record["status"] == "approved"]
    if not approved:
        return {"status": "NO_APPROVED_MEMORY", "winner": None}
    winner = max(
        approved,
        key=lambda record: (
            record.get("pinned_context") is True,
            _iso_to_epoch(record.get("valid_from")) or 0.0,
            {"low": 0, "medium": 1, "high": 2}.get(record.get("confidence"), 0),
            record["memory_id"],
        ),
    )
    return {"status": "WINNER_SELECTED", "winner": winner["memory_id"]}


if __name__ == "__main__":
    import sys

    raise SystemExit("Use memory governance functions with offline metadata; no live memory store is exposed.")
