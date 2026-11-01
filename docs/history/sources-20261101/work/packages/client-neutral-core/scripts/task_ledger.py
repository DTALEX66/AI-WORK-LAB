#!/usr/bin/env python
"""Project-neutral resumable Task Ledger with leases and bounded budgets."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import uuid
from pathlib import Path
from typing import Any

STATES = {
    "QUEUED", "PLANNING", "WAITING_APPROVAL", "RUNNING", "RETRYING", "PAUSED",
    "BLOCKED", "REVIEWING", "COMPLETED", "FAILED", "CANCELLED",
}
MAX_RETRIES = 3
MAX_CHILDREN = 8
EXTERNAL_EFFECT_STATES = {"PENDING", "CONFIRMED", "ABSENT", "CONFLICT"}
TRANSITIONS = {
    "QUEUED": {"PLANNING", "CANCELLED", "BLOCKED"},
    "PLANNING": {"WAITING_APPROVAL", "RUNNING", "PAUSED", "BLOCKED"},
    "WAITING_APPROVAL": {"RUNNING", "CANCELLED", "BLOCKED"},
    "RUNNING": {"RETRYING", "PAUSED", "WAITING_APPROVAL", "REVIEWING", "COMPLETED", "FAILED", "BLOCKED"},
    "RETRYING": {"RUNNING", "BLOCKED", "FAILED"},
    "PAUSED": {"RUNNING", "CANCELLED", "BLOCKED"},
    "REVIEWING": {"COMPLETED", "FAILED", "PAUSED"},
    "BLOCKED": set(), "COMPLETED": set(), "FAILED": set(), "CANCELLED": set(),
}


def _now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


class TaskLedger:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.path = self.root / "ledger.json"

    def _ensure(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        self._recover_orphaned_writes()
        if not self.path.exists():
            self._write({"schema_version": "workflow/task-ledger/v1", "tasks": {}})

    def _recover_orphaned_writes(self) -> None:
        candidates = sorted(self.root.glob(f".{self.path.name}.*.tmp"))
        if not candidates:
            return
        if self.path.exists():
            for candidate in candidates:
                candidate.unlink(missing_ok=True)
            return
        valid: list[Path] = []
        for candidate in candidates:
            try:
                data = json.loads(candidate.read_text(encoding="utf-8"))
                if data.get("schema_version") == "workflow/task-ledger/v1" and isinstance(data.get("tasks"), dict):
                    valid.append(candidate)
            except (OSError, json.JSONDecodeError, AttributeError):
                continue
        if valid:
            os.replace(valid[-1], self.path)
        for candidate in candidates:
            candidate.unlink(missing_ok=True)

    def _read(self) -> dict[str, Any]:
        self._ensure()
        data = json.loads(self.path.read_text(encoding="utf-8"))
        if data.get("schema_version") != "workflow/task-ledger/v1" or not isinstance(data.get("tasks"), dict):
            raise ValueError("invalid task ledger schema")
        return data

    def _write(self, data: dict[str, Any]) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        temp = self.path.with_name(f".{self.path.name}.{uuid.uuid4().hex}.tmp")
        temp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        os.replace(temp, self.path)

    @staticmethod
    def _parse_time(value: str) -> dt.datetime:
        return dt.datetime.fromisoformat(value.replace("Z", "+00:00"))

    def create(
        self,
        task_id: str,
        idempotency_key: str,
        *,
        token_budget: int | None = None,
        time_budget_seconds: int | None = None,
        tool_budget: int | None = None,
    ) -> dict[str, Any]:
        if not task_id or not idempotency_key:
            raise ValueError("task_id and idempotency_key are required")
        data = self._read()
        existing = data["tasks"].get(task_id)
        if existing:
            if existing.get("idempotency_key") != idempotency_key:
                raise ValueError("idempotency key conflict")
            return existing
        task = {
            "task_id": task_id,
            "run_id": str(uuid.uuid4()),
            "idempotency_key": idempotency_key,
            "status": "QUEUED",
            "checkpoint": None,
            "cursor_version": 0,
            "waitpoint": None,
            "retry_count": 0,
            "budget": {
                "tokens": token_budget,
                "time_seconds": time_budget_seconds,
                "tools": tool_budget,
                "max_retries": MAX_RETRIES,
            },
            "usage": {"tokens": 0, "time_seconds": 0, "tools": 0},
            "lease": None,
            "evidence": [],
            "parent_task_id": None,
            "dependencies": [],
            "children": [],
            "external_effects": [],
            "reconciliation": [],
            "created_at": _now(),
            "updated_at": _now(),
            "errors": [],
        }
        data["tasks"][task_id] = task
        self._write(data)
        return task

    def record_external_effect(
        self,
        task_id: str,
        effect_id: str,
        action: str,
        intent_digest: str,
    ) -> dict[str, Any]:
        if not effect_id or not action or not intent_digest:
            raise ValueError("effect_id, action, and intent_digest are required")
        data = self._read()
        task = data["tasks"].get(task_id)
        if not task:
            raise KeyError(f"task not found: {task_id}")
        for effect in task.setdefault("external_effects", []):
            if effect["effect_id"] == effect_id:
                if effect["intent_digest"] != intent_digest or effect["action"] != action:
                    raise ValueError("external effect idempotency conflict")
                return dict(effect)
        effect = {
            "effect_id": effect_id,
            "action": action,
            "intent_digest": intent_digest,
            "status": "PENDING",
            "observed_digest": None,
            "created_at": _now(),
            "updated_at": _now(),
        }
        task["external_effects"].append(effect)
        task["updated_at"] = _now()
        self._write(data)
        return dict(effect)

    def reconcile_external_effect(
        self,
        task_id: str,
        effect_id: str,
        observed_state: str,
        observed_digest: str | None = None,
    ) -> dict[str, Any]:
        if observed_state not in EXTERNAL_EFFECT_STATES - {"PENDING"}:
            raise ValueError("invalid reconciliation state")
        data = self._read()
        task = data["tasks"].get(task_id)
        if not task:
            raise KeyError(f"task not found: {task_id}")
        for effect in task.setdefault("external_effects", []):
            if effect["effect_id"] != effect_id:
                continue
            if effect["status"] == "CONFIRMED" and observed_state != "CONFIRMED":
                raise ValueError("confirmed external effect cannot be downgraded")
            effect["status"] = observed_state
            effect["observed_digest"] = observed_digest
            effect["updated_at"] = _now()
            task.setdefault("reconciliation", []).append({
                "effect_id": effect_id,
                "status": observed_state,
                "observed_digest": observed_digest,
                "at": _now(),
            })
            task["updated_at"] = _now()
            self._write(data)
            return task
        raise KeyError(f"external effect not found: {effect_id}")

    def set_dependencies(self, task_id: str, dependencies: list[str]) -> dict[str, Any]:
        data = self._read()
        if task_id not in data["tasks"]:
            raise KeyError(f"task not found: {task_id}")
        unique = list(dict.fromkeys(dependencies))
        if task_id in unique or any(dep not in data["tasks"] for dep in unique):
            raise ValueError("invalid dependency")
        graph = {key: list(value.get("dependencies", [])) for key, value in data["tasks"].items()}
        graph[task_id] = unique
        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(node: str) -> None:
            if node in visiting:
                raise ValueError("dependency cycle detected")
            if node in visited:
                return
            visiting.add(node)
            for dependency in graph.get(node, []):
                visit(dependency)
            visiting.remove(node)
            visited.add(node)

        for node in graph:
            visit(node)
        task = data["tasks"][task_id]
        task["dependencies"] = unique
        task["updated_at"] = _now()
        self._write(data)
        return task

    def attach_child(self, parent_task_id: str, child_task_id: str) -> dict[str, Any]:
        data = self._read()
        parent = data["tasks"].get(parent_task_id)
        child = data["tasks"].get(child_task_id)
        if not parent or not child:
            raise KeyError("parent and child tasks are required")
        children = parent.setdefault("children", [])
        if child_task_id not in children and len(children) >= MAX_CHILDREN:
            raise ValueError("fan-out limit exceeded")
        if child_task_id not in children:
            children.append(child_task_id)
        child["parent_task_id"] = parent_task_id
        parent["updated_at"] = _now()
        child["updated_at"] = _now()
        self._write(data)
        return parent

    def get(self, task_id: str) -> dict[str, Any]:
        task = self._read()["tasks"].get(task_id)
        if not task:
            raise KeyError(f"task not found: {task_id}")
        return task

    def ready_tasks(self) -> list[str]:
        """Topologically ready tasks: QUEUED tasks whose dependencies are all COMPLETED.

        DAG scheduling entry point (absorbed 2026-08-12): a task starts only
        when every `dependencies` edge is satisfied by a recorded COMPLETED
        verdict; "looks related" is never a dependency edge.
        """
        data = self._read()
        completed = {tid for tid, task in data["tasks"].items() if task.get("status") == "COMPLETED"}
        ready: list[str] = []
        for tid, task in data["tasks"].items():
            if task.get("status") != "QUEUED":
                continue
            if all(dep in completed for dep in task.get("dependencies", [])):
                ready.append(tid)
        return ready

    def _assert_lease(self, task: dict[str, Any], holder: str | None, fence: int | None, now: str | None) -> None:
        lease = task.get("lease")
        if not lease:
            return
        if holder is None or fence is None:
            raise ValueError("active lease required")
        if lease.get("holder") != holder or lease.get("fence") != fence:
            raise ValueError("fence mismatch")
        if self._parse_time(now or _now()) >= self._parse_time(lease["expires_at"]):
            raise ValueError("lease expired")

    def acquire_lease(
        self, task_id: str, holder: str, *, ttl_seconds: int = 60, now: str | None = None
    ) -> dict[str, Any]:
        if not holder or ttl_seconds <= 0:
            raise ValueError("holder and positive ttl_seconds are required")
        data = self._read()
        task = data["tasks"].get(task_id)
        if not task:
            raise KeyError(f"task not found: {task_id}")
        current = now or _now()
        existing = task.get("lease")
        if existing and self._parse_time(current) < self._parse_time(existing["expires_at"]):
            raise ValueError("lease already held")
        fence = int(existing.get("fence", 0)) + 1 if existing else 1
        expires = self._parse_time(current) + dt.timedelta(seconds=ttl_seconds)
        lease = {
            "holder": holder,
            "fence": fence,
            "acquired_at": current,
            "heartbeat_at": current,
            "expires_at": expires.isoformat().replace("+00:00", "Z"),
        }
        task["lease"] = lease
        task["updated_at"] = _now()
        self._write(data)
        return lease

    def renew_lease(
        self, task_id: str, holder: str, fence: int, *, ttl_seconds: int = 60, now: str | None = None
    ) -> dict[str, Any]:
        if ttl_seconds <= 0:
            raise ValueError("positive ttl_seconds is required")
        data = self._read()
        task = data["tasks"].get(task_id)
        if not task:
            raise KeyError(f"task not found: {task_id}")
        self._assert_lease(task, holder, fence, now)
        current = now or _now()
        expires = self._parse_time(current) + dt.timedelta(seconds=ttl_seconds)
        task["lease"]["heartbeat_at"] = current
        task["lease"]["expires_at"] = expires.isoformat().replace("+00:00", "Z")
        task["updated_at"] = _now()
        self._write(data)
        return task["lease"]

    def heartbeat(self, task_id: str, holder: str, fence: int, *, now: str | None = None) -> dict[str, Any]:
        data = self._read()
        task = data["tasks"].get(task_id)
        if not task:
            raise KeyError(f"task not found: {task_id}")
        self._assert_lease(task, holder, fence, now)
        task["lease"]["heartbeat_at"] = now or _now()
        task["updated_at"] = _now()
        self._write(data)
        return task["lease"]

    def detect_zombie(self, task_id: str, *, now: str | None = None) -> bool:
        task = self.get(task_id)
        lease = task.get("lease")
        return bool(lease and self._parse_time(now or _now()) >= self._parse_time(lease["expires_at"]))

    def release_lease(
        self, task_id: str, holder: str, fence: int, *, now: str | None = None
    ) -> dict[str, Any]:
        data = self._read()
        task = data["tasks"].get(task_id)
        if not task:
            raise KeyError(f"task not found: {task_id}")
        self._assert_lease(task, holder, fence, now)
        task["lease"] = None
        task["updated_at"] = _now()
        self._write(data)
        return task

    def transition(
        self,
        task_id: str,
        status: str,
        *,
        holder: str | None = None,
        fence: int | None = None,
        now: str | None = None,
    ) -> dict[str, Any]:
        if status not in STATES:
            raise ValueError(f"unknown status: {status}")
        data = self._read()
        task = data["tasks"].get(task_id)
        if not task:
            raise KeyError(f"task not found: {task_id}")
        self._assert_lease(task, holder, fence, now)
        current = task["status"]
        if status not in TRANSITIONS[current]:
            raise ValueError(f"invalid transition {current} -> {status}")
        task["status"] = status
        task["updated_at"] = _now()
        self._write(data)
        return task

    def checkpoint(
        self,
        task_id: str,
        checkpoint: dict[str, Any],
        *,
        holder: str | None = None,
        fence: int | None = None,
        now: str | None = None,
    ) -> dict[str, Any]:
        if not isinstance(checkpoint, dict):
            raise ValueError("checkpoint must be an object")
        data = self._read()
        task = data["tasks"].get(task_id)
        if not task:
            raise KeyError(f"task not found: {task_id}")
        self._assert_lease(task, holder, fence, now)
        task["checkpoint"] = checkpoint
        task["cursor_version"] = int(task.get("cursor_version", 0)) + 1
        task["updated_at"] = _now()
        self._write(data)
        return task

    def set_waitpoint(
        self,
        task_id: str,
        kind: str,
        cursor: dict[str, Any],
        *,
        holder: str,
        fence: int,
        now: str | None = None,
    ) -> dict[str, Any]:
        if not kind or not isinstance(cursor, dict):
            raise ValueError("waitpoint kind and cursor are required")
        data = self._read()
        task = data["tasks"].get(task_id)
        if not task:
            raise KeyError(f"task not found: {task_id}")
        self._assert_lease(task, holder, fence, now)
        if task["status"] != "RUNNING":
            raise ValueError("waitpoint requires a running task")
        task["cursor_version"] = int(task.get("cursor_version", 0)) + 1
        task["waitpoint"] = {
            "kind": kind,
            "cursor": dict(cursor),
            "holder": holder,
            "fence": fence,
            "created_at": now or _now(),
        }
        task["status"] = "WAITING_APPROVAL"
        task["lease"] = None
        task["updated_at"] = _now()
        self._write(data)
        return task

    def clear_waitpoint(
        self, task_id: str, holder: str, fence: int, *, now: str | None = None
    ) -> dict[str, Any]:
        data = self._read()
        task = data["tasks"].get(task_id)
        if not task:
            raise KeyError(f"task not found: {task_id}")
        waitpoint = task.get("waitpoint")
        if task["status"] != "WAITING_APPROVAL" or not waitpoint:
            raise ValueError("task has no active waitpoint")
        if waitpoint["holder"] != holder or waitpoint["fence"] != fence:
            raise ValueError("waitpoint fence mismatch")
        task["waitpoint"] = None
        task["status"] = "RUNNING"
        task["updated_at"] = _now()
        self._write(data)
        return task

    def record_usage(
        self,
        task_id: str,
        *,
        tokens: int = 0,
        time_seconds: int = 0,
        tools: int = 0,
        holder: str | None = None,
        fence: int | None = None,
        now: str | None = None,
    ) -> dict[str, Any]:
        if min(tokens, time_seconds, tools) < 0:
            raise ValueError("usage values cannot be negative")
        data = self._read()
        task = data["tasks"].get(task_id)
        if not task:
            raise KeyError(f"task not found: {task_id}")
        self._assert_lease(task, holder, fence, now)
        usage = task.setdefault("usage", {"tokens": 0, "time_seconds": 0, "tools": 0})
        usage["tokens"] += tokens
        usage["time_seconds"] += time_seconds
        usage["tools"] += tools
        budget = task["budget"]
        exceeded = (
            budget.get("tokens") is not None and usage["tokens"] > budget["tokens"]
        ) or (
            budget.get("time_seconds") is not None and usage["time_seconds"] > budget["time_seconds"]
        ) or (
            budget.get("tools") is not None and usage["tools"] > budget["tools"]
        )
        if exceeded:
            task["status"] = "BLOCKED"
            task["errors"].append({"code": "BUDGET_EXCEEDED", "usage": dict(usage), "at": _now()})
        task["updated_at"] = _now()
        self._write(data)
        return task

    def record_evidence(
        self,
        task_id: str,
        evidence: dict[str, Any],
        *,
        holder: str | None = None,
        fence: int | None = None,
        now: str | None = None,
    ) -> dict[str, Any]:
        required = {"evidence_id", "state", "source", "sha256"}
        if not isinstance(evidence, dict) or not required.issubset(evidence):
            raise ValueError("evidence requires evidence_id, state, source, sha256")
        if evidence["state"] not in {"PASS", "FAIL", "BLOCKED", "UNVERIFIED"}:
            raise ValueError("invalid evidence state")
        if not isinstance(evidence["sha256"], str) or len(evidence["sha256"]) != 64:
            raise ValueError("evidence sha256 must be 64 hex characters")
        try:
            int(evidence["sha256"], 16)
        except ValueError as exc:
            raise ValueError("evidence sha256 must be hexadecimal") from exc
        data = self._read()
        task = data["tasks"].get(task_id)
        if not task:
            raise KeyError(f"task not found: {task_id}")
        self._assert_lease(task, holder, fence, now)
        task.setdefault("evidence", []).append(dict(evidence))
        task["updated_at"] = _now()
        self._write(data)
        return task

    def resume(self, task_id: str) -> dict[str, Any]:
        task = self.get(task_id)
        if task["status"] not in {"PAUSED", "RETRYING", "BLOCKED", "QUEUED", "PLANNING", "WAITING_APPROVAL"}:
            return task
        if task["status"] == "BLOCKED":
            raise ValueError("blocked task requires a new approved run")
        return self.transition(task_id, "RUNNING") if task["status"] in {"PAUSED", "RETRYING", "WAITING_APPROVAL"} else task

    def record_error(
        self,
        task_id: str,
        error_code: str,
        *,
        retryable: bool,
        external_write: bool,
        holder: str | None = None,
        fence: int | None = None,
        now: str | None = None,
    ) -> dict[str, Any]:
        if not error_code:
            raise ValueError("error_code is required")
        data = self._read()
        task = data["tasks"].get(task_id)
        if not task:
            raise KeyError(f"task not found: {task_id}")
        self._assert_lease(task, holder, fence, now)
        if task["status"] in {"COMPLETED", "CANCELLED"}:
            raise ValueError("terminal task cannot record a new error")
        if external_write or not retryable:
            status = "FAILED"
        elif task["retry_count"] >= MAX_RETRIES:
            status = "BLOCKED"
        else:
            task["retry_count"] += 1
            status = "RETRYING"
        task["status"] = status
        fingerprint = hashlib.sha256(
            f"{error_code}|{retryable}|{external_write}".encode("utf-8")
        ).hexdigest()[:16]
        task["errors"].append({
            "code": error_code,
            "fingerprint": fingerprint,
            "retryable": retryable,
            "external_write": external_write,
            "at": _now(),
        })
        task["updated_at"] = _now()
        self._write(data)
        return task


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, default=Path.cwd())
    parser.add_argument("--root", type=Path)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("init")
    create = sub.add_parser("create")
    create.add_argument("task_id")
    create.add_argument("idempotency_key")
    transition = sub.add_parser("transition")
    transition.add_argument("task_id")
    transition.add_argument("status")
    resume = sub.add_parser("resume")
    resume.add_argument("task_id")
    args = parser.parse_args()
    ledger = TaskLedger((args.root or (args.project / ".hermes" / "task-runtime" / "task-ledger")).resolve())
    if args.command == "init":
        ledger._ensure()
        print(f"TASK_LEDGER_READY root={ledger.root}")
        return 0
    if args.command == "create":
        result = ledger.create(args.task_id, args.idempotency_key)
    elif args.command == "transition":
        result = ledger.transition(args.task_id, args.status)
    else:
        result = ledger.resume(args.task_id)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
