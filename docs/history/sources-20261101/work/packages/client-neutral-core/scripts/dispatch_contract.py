"""NF-08-C: dispatch-to-execution contract (stop at handoff simulation -> real).

Design layer for "the first genuine closed loop: a planner publishes, a local
native executor claims, and a verifiable artifact is produced with ZERO manual
body copies".  Real native launch / model calls stay authorization-gated and
BLOCKED; this module defines the dispatch *contract* and the failure-layer
attribution so the slice is testable without a live executor.

Key semantics (acceptance AT-11 / AT-18 / AT-21)
-------------------------------------------------
* **Freeze before dispatch** — task / revision / baseline / executor /
  authorization reference are frozen and the local workspace resolved; a dirty
  local worktree is NEVER auto-pull / auto-reset.
* **Real launch intent** — pre-launch intent, the REAL run/session id and the
  actual instruction source are recorded (no global ``--last`` guesswork).
* **Risk ordering** — a low-risk deterministic native task runs first; the
  minimal Agent task only under an existing cost grant; a fake executor is
  contract evidence only.
* **Executor handoff** — switching executor for the same task first confirms
  the old runtime has completed / safely paused; only the REMAINING work is
  handed over, never the whole package again.
* **Failure-layer attribution** — a startup failure is attributed to exactly
  one layer (transport / permission / runtime / model); other projects keep
  running.  A command returning 0 or a model saying DONE is NOT full
  acceptance.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Mapping

FAILURE_LAYERS = ("transport", "permission", "runtime", "model")


def _digest(*parts: Any) -> str:
    blob = json.dumps(parts, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class DispatchFreeze:
    """Everything frozen before a task is handed to an executor."""
    task_id: str
    task_revision: int
    baseline: str                 # git commit or artifact digest
    executor: str                # adapter_id (client-neutral), not a project name
    authorization_ref: str       # trusted local grant record id
    workspace: str              # resolved local workspace path
    intent_digest: str          # pre-launch intent hash (real instruction source)

    @property
    def fingerprint(self) -> str:
        return _digest(self.task_id, self.task_revision, self.baseline,
                       self.executor, self.authorization_ref)

    def to_record(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id, "task_revision": self.task_revision,
            "baseline": self.baseline, "executor": self.executor,
            "authorization_ref": self.authorization_ref, "workspace": self.workspace,
            "intent_digest": self.intent_digest, "fingerprint": self.fingerprint,
        }


def build_freeze(*, task_id: str, task_revision: int, baseline: str,
                 executor: str, authorization_ref: str, workspace: str,
                 instruction_source: str) -> DispatchFreeze:
    """Record the real instruction source (a concrete artifact reference),
    never a global ``--last``.  A dirty workspace is recorded as-is, not
    mutated (no auto pull/reset)."""
    if not instruction_source:
        raise ValueError("instruction source is required; a global --last is not acceptable")
    intent_digest = _digest(task_id, task_revision, instruction_source)
    return DispatchFreeze(task_id, task_revision, baseline, executor,
                          authorization_ref, workspace, intent_digest)


def workspace_clean_check(dirty_files: list[str]) -> dict[str, Any]:
    """A dirty local worktree is NOT auto pull/reset; it is reported so the
    dispatch can proceed in place or block, never silently clean itself."""
    if dirty_files:
        return {"clean": False, "dirty_files": list(dirty_files),
                "auto_cleaned": False,
                "note": "dirty worktree kept as-is; no auto pull/reset"}
    return {"clean": True, "dirty_files": [], "auto_cleaned": False}


class LaunchRecord:
    """Records the real run/session id + instruction source for a launch.

    A launch is valid only when it carries an explicit run/session id and the
    exact instruction source it started from."""

    def __init__(self) -> None:
        self._records: list[dict[str, Any]] = []

    def record(self, freeze: DispatchFreeze, *, run_session_id: str,
               instruction_source: str, fake_executor: bool = False) -> dict[str, Any]:
        if not run_session_id:
            raise ValueError("a real run/session id is required; --last is not a record")
        rec = {
            "fingerprint": freeze.fingerprint,
            "run_session_id": run_session_id,
            "instruction_source": instruction_source,
            "fake_executor": fake_executor,
            "contract_evidence_only": fake_executor,
        }
        self._records.append(rec)
        return rec

    def latest_for(self, freeze: DispatchFreeze) -> dict[str, Any] | None:
        for rec in reversed(self._records):
            if rec["fingerprint"] == freeze.fingerprint:
                return rec
        return None


def startup_failure_attribution(error: Mapping[str, Any]) -> dict[str, Any]:
    """Attribute a startup failure to EXACTLY one layer.

    ``error['layer']`` must be one of FAILURE_LAYERS; an unattributed failure
    is refused (it cannot be blamed on 'the model' by default).  Other projects
    keep running regardless — the attribution carries ``blocks_other_projects``
    = False always.
    """
    layer = error.get("layer")
    if layer not in FAILURE_LAYERS:
        raise ValueError(f"failure must be attributed to one of {FAILURE_LAYERS}; "
                         f"got {layer!r}")
    detail = error.get("detail", "")
    return {
        "layer": layer,
        "detail": detail,
        "blocks_other_projects": False,
        "other_projects_continue": True,
    }


class RiskOrdering:
    """Low-risk deterministic native task first, then the minimal Agent task
    under an existing cost grant; a fake executor is contract evidence only."""

    RISK_ORDER = ("deterministic", "agent")

    def plan(self, tasks: Mapping[str, str], *, cost_grant: bool) -> list[dict[str, Any]]:
        """``tasks``: id -> risk ('deterministic' | 'agent').  Returns the
        execution order; agent tasks are only scheduled when a cost grant
        exists, otherwise they are held, not silently run or silently dropped."""
        ordered: list[dict[str, Any]] = []
        for risk in self.RISK_ORDER:
            for tid, task_risk in tasks.items():
                if task_risk != risk:
                    continue
                if risk == "agent" and not cost_grant:
                    ordered.append({"task_id": tid, "risk": risk, "state": "HELD_NO_COST_GRANT"})
                else:
                    ordered.append({"task_id": tid, "risk": risk, "state": "SCHEDULED"})
        # deterministic must come strictly before any agent task
        first_agent = next((i for i, e in enumerate(ordered) if e["risk"] == "agent"), None)
        last_det = max((i for i, e in enumerate(ordered) if e["risk"] == "deterministic"), default=-1)
        if first_agent is not None and last_det > first_agent:
            raise ValueError("risk ordering violated: a deterministic task is scheduled after an agent task")
        return ordered


def handoff_remaining_work(prior: Mapping[str, Any], *, old_state: str) -> dict[str, Any]:
    """Switching executor for the same task: first confirm the old runtime has
    completed / safely paused, then hand over ONLY the remaining work."""
    if old_state not in ("COMPLETED", "PAUSED"):
        return {"handed_over": False, "reason": f"old runtime not safe ({old_state!r}); "
                                                "must be COMPLETED or PAUSED before handoff",
                "whole_package_again": False}
    remaining = [w for w in prior.get("remaining_work", []) if w.get("done") is not True]
    return {"handed_over": True, "old_state": old_state,
            "remaining_work": remaining,
            "whole_package_again": False,
            "note": "only the remaining work is handed over, never the whole package"}


def acceptance_is_not_command_zero(outcome: Mapping[str, Any]) -> dict[str, Any]:
    """A command returning 0 or a model saying DONE is NOT full acceptance —
    acceptance requires a verifiable artifact / evidence."""
    if outcome.get("exit_code") == 0 and not outcome.get("artifact_verified"):
        return {"accepted": False,
                "reason": "exit code 0 alone is not acceptance; a verified artifact is required"}
    if outcome.get("model_said_done") and not outcome.get("artifact_verified"):
        return {"accepted": False,
                "reason": "a model DONE alone is not acceptance; a verified artifact is required"}
    if outcome.get("artifact_verified"):
        return {"accepted": True, "reason": "verifiable artifact present"}
    return {"accepted": False, "reason": "no verified artifact"}
