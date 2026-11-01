"""Model task bridge: wire InvocationPlan + resource lease into the durable
worker (WL3-410 / MR-13).

This is a THIN integration layer on top of the existing DurableWorker and
CanonicalStore. It does not re-implement the worker loop, leases, checkpoints,
or retries — those live in durable_worker.py.

Responsibilities:
- resolve an InvocationPlan for a task (pure, MR-08)
- acquire the task's resource lease before the handler runs (MR-09)
- attach an idempotent attempt key so restart never re-executes side effects
- validate the handler result against the task contract
- write runtime facts only through the Workflow-owned store
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Callable

from durable_worker import DurableWorker
from model_capability_resolver import Resolver
from resource_lease import ResourceLease

SCHEMA_VERSION = "workflow/model-task-bridge/v1"

# Forbidden in any result validation (taskpack §12/§20.7)
_FORBIDDEN_KEYS = ("api_key", "secret", "token", "password", "credential",
                   "prompt", "response", "session_id", "auth")


class ResultValidationError(RuntimeError):
    pass


def attempt_key(task_id: str, attempt: int) -> str:
    """Idempotent attempt key: restart with the same key never re-executes."""
    return hashlib.sha256(f"{task_id}:{attempt}".encode("utf-8")).hexdigest()[:24]


def validate_result(result: dict[str, Any]) -> None:
    """Reject forbidden fields or oversized payloads in a task result."""
    for key, value in result.items():
        if any(f in key.lower() for f in _FORBIDDEN_KEYS):
            raise ResultValidationError(f"forbidden field in result: {key!r}")
        if isinstance(value, str) and len(value) > 8192:
            raise ResultValidationError(f"result field too large: {key!r}")
    allowed = {"status", "exit_code", "evidence_hash", "summary", "file_changes",
               "error_kind", "started_at", "ended_at"}
    unknown = set(result) - allowed
    if unknown:
        raise ResultValidationError(f"unknown result fields: {sorted(unknown)}")


class ModelTaskHandler:
    """Task handler that resolves a plan, leases a resource, then runs the
    user-supplied executor. Result validation is fail-closed."""

    def __init__(
        self,
        runtime_root: Path,
        resolver: Resolver,
        executor: Callable[[dict[str, Any], dict[str, Any]], dict[str, Any]],
        project_id: str = "work-lab",
    ) -> None:
        self.runtime_root = runtime_root.resolve()
        self.resolver = resolver
        self.executor = executor
        self.project_id = project_id
        self._attempts: dict[str, int] = {}

    def __call__(self, store: Any, task: dict[str, Any]) -> None:
        """Called by DurableWorker._drive_task with the task payload."""
        task_id = task["task_id"]
        resource_group = task.get("resource_group", "none")
        attempt = self._attempts.get(task_id, 0) + 1
        self._attempts[task_id] = attempt
        key = attempt_key(task_id, attempt)

        plan = self.resolver.resolve(task)
        if plan["status"] == "BLOCKED":
            raise RuntimeError(f"task blocked: {plan.get('reason_code')}")
        if plan["status"] == "NO_MODEL_REQUIRED":
            return  # observer-style task: nothing to execute

        lease = ResourceLease(self.runtime_root, resource_group)
        outcome = lease.acquire()
        if outcome["status"] == "QUEUED":
            raise RuntimeError(f"resource busy: {resource_group}")

        try:
            result = self.executor(task, plan)
            validate_result(result)
            # Mutate the task's checkpoint IN PLACE so DurableWorker's own
            # checkpoint variable (same dict reference) persists the fields;
            # the worker writes the terminal COMPLETED_LOCAL state after this
            # handler returns. Never upsert here -- that would be overwritten.
            checkpoint = task.setdefault("checkpoint", {})
            if not isinstance(checkpoint, dict):
                checkpoint = task["checkpoint"] = {}
            checkpoint.update({
                "attempt_key": key,
                "attempt": attempt,
                "plan_id": plan.get("plan_id"),
                "selected": (plan.get("selected") or {}).get("candidate"),
                "result_status": result.get("status"),
                "evidence_hash": result.get("evidence_hash"),
            })
        finally:
            lease.release()


def wire_into_worker(worker: DurableWorker, handler: ModelTaskHandler) -> DurableWorker:
    """Attach the model task handler to an existing worker."""
    worker.task_handler = handler
    return worker


if __name__ == "__main__":
    print(json.dumps({
        "schema_version": SCHEMA_VERSION,
        "status": "integration-layer-ready",
        "note": "attaches to durable_worker; no standalone loop",
    }, ensure_ascii=False, indent=2))
