"""Producers for the WUI-21 read models: operation progress and isolated trial.

The owner's pack (§5, scenes 05/06) names five stages — 未开始 → 提交中 → 排队/运行 → 通过/失败/取消/未知,
with 超时 = 未知或超时 — and this module is the server-side answer to how much of that this repository can
actually say. The mapping is deliberately narrow and each unmapped name becomes a declared gap:

* ``task_ledger.py:15`` holds the real state set (QUEUED, PLANNING, WAITING_APPROVAL, RUNNING, RETRYING,
  PAUSED, BLOCKED, REVIEWING, COMPLETED, FAILED, CANCELLED). The pack's stages that exist there are mapped;
  everything else the pack asks for is carried in ``producer_gaps``.
* **There is no SUBMITTING state**, because nothing records the client-to-ledger handoff. A page that showed
  "submitting" would be inventing a stage from latency, so the gap is named instead.
* **Timeout is not failure.** `TaskLedger.detect_zombie` says the lease stopped being renewed: the observation
  went stale. That yields ``UNKNOWN_OR_TIMEOUT``. Turning it into FAILED would tell the owner the operation
  broke when the only fact is that we stopped being able to see it (the same rule ERR-222 records for
  disconnects, one level up).
* **The three results stay three.** ``build_isolated_trial`` reports write, native read-back and target
  behaviour as separate status+basis objects. A COMPLETED child answers the write stage only;
  `target_behaviour` is answered solely from a reconciled external effect
  (`task_ledger.py:21`, EXTERNAL_EFFECT_STATES), which is why a source-side success can never light it.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping

PROGRESS_SCHEMA = "worklab/operation-progress/v1"
TRIAL_SCHEMA = "worklab/isolated-trial/v1"

# Task Ledger spelling -> the contract's stage. COMPLETED -> PASSED and nothing else maps to PASSED.
LEDGER_TO_STATE: dict[str, str] = {
    "PLANNING": "PLANNING",
    "QUEUED": "QUEUED",
    "WAITING_APPROVAL": "WAITING_APPROVAL",
    "RUNNING": "RUNNING",
    "RETRYING": "RETRYING",
    "PAUSED": "PAUSED",
    "BLOCKED": "BLOCKED",
    "REVIEWING": "REVIEWING",
    "COMPLETED": "PASSED",
    "FAILED": "FAILED",
    "CANCELLED": "CANCELLED",
}
# Stages the pack names that this repository cannot answer, and the gap token each becomes.
UNANSWERED_STAGES = {"SUBMITTING": "SUBMITTING_STAGE"}
# Fields the pack's read model names that no producer here answers, carried as named gaps so a reader
# sees why they are absent. `sequence` (2026-10-13): nothing names a per-operation progress counter.
# The snapshot's `revision` is the STORE's cursor — borrowing it would make two different monotonic
# things look like one, which is the error ERR-225 keeps recording under other names.
UNANSWERED_FIELDS: tuple[str, ...] = ("PROGRESS_SEQUENCE",)
EXTERNAL_TO_BEHAVIOUR = {"CONFIRMED": "PASSED", "PENDING": "PENDING", "ABSENT": "ABSENT", "CONFLICT": "CONFLICT"}
_NO_PRODUCER = "NO_PRODUCER"


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _stage(status: str | None, basis: str, note: str = "") -> dict[str, str]:
    """One separated result. A stage with no producer cannot carry a friendly status."""
    return {"status": status or "UNKNOWN", "basis": basis, "note": note[:400]}


def build_operation_progress(ledger: Any, task_id: str, *, now: str | None = None,
                            transport_state: str | None = None,
                            child_task_id: str | None = None) -> dict[str, Any]:
    """One progress record for one operation, or an honest UNKNOWN record when the ledger cannot answer."""
    observed = now or _now()
    gaps: list[str] = sorted(set(UNANSWERED_STAGES.values()) | set(UNANSWERED_FIELDS))
    try:
        task = ledger.get(task_id)
    except (KeyError, ValueError, OSError):
        # A missing or unreadable record is not a not-started operation: it is an unanswered question.
        return {
            "schema_version": PROGRESS_SCHEMA, "task_id": task_id, "observed_at": observed,
            "state": "UNKNOWN", "ledger_status": None,
            "last_trusted_progress": {"state": None, "at": None, "basis": "NONE"},
            "transport_state": transport_state,
            "sourceTimes": {"createdAt": None, "updatedAt": None, "heartbeatAt": None},
            "producer_gaps": sorted(set(gaps) | {"TARGET_BEHAVIOUR_CONFIRMATION"}),
            "target_behaviour": None,
        }

    status = str(task.get("status") or "")
    state = LEDGER_TO_STATE.get(status)
    if state is None:
        # An unknown spelling in the ledger must not be repaired into a plausible stage.
        state = "UNKNOWN"
    if _expired(ledger, task_id, now):
        state = "UNKNOWN_OR_TIMEOUT"

    updated_at = task.get("updated_at")
    # The lease spells its stamp heartbeat_at (task_ledger.py:300); reading a name that does not exist
    # would silently fall through to updated_at and report a heartbeat that never happened.
    lease = task.get("lease") if isinstance(task.get("lease"), Mapping) else {}
    heartbeat = lease.get("heartbeat_at")
    if heartbeat:
        trusted = {"state": state if state != "UNKNOWN" else None, "at": heartbeat, "basis": "LEDGER_HEARTBEAT"}
    elif updated_at:
        trusted = {"state": state if state != "UNKNOWN" else None, "at": updated_at, "basis": "LEDGER_UPDATED_AT"}
    else:
        trusted = {"state": None, "at": None, "basis": "NONE"}

    effects = [e for e in (task.get("external_effects") or []) if isinstance(e, Mapping)]
    behaviour = None
    if effects:
        # The reconciled verdict of the last effect is what the target did; more than one effect needs the
        # caller to say which one this row is about, so an ambiguous set is reported as a conflict, not a pick.
        statuses = {str(e.get("status") or "") for e in effects}
        if len(statuses) == 1:
            behaviour = next(iter(statuses))
        else:
            behaviour = "CONFLICT"
    else:
        gaps.append("TARGET_BEHAVIOUR_CONFIRMATION")

    record = {
        "schema_version": PROGRESS_SCHEMA, "task_id": task_id, "observed_at": observed,
        "state": state, "ledger_status": status or None,
        "last_trusted_progress": trusted, "transport_state": transport_state,
        # The three stamps are read separately from the record we just read: `observed_at` is when WE
        # looked, these are when the SOURCE attested. A missing one stays null rather than borrowing
        # its neighbour — `updated_at` is not a heartbeat, and a lease stamp is not an update.
        "sourceTimes": {
            "createdAt": task.get("created_at"),
            "updatedAt": updated_at,
            "heartbeatAt": heartbeat,
        },
        "producer_gaps": sorted(set(gaps)),
    }
    if behaviour is not None:
        record["target_behaviour"] = behaviour
    return record


def build_isolated_trial(ledger: Any, parent_task_id: str, *, now: str | None = None,
                         executions: list[dict[str, Any]] | None = None,
                         trial_id: str | None = None) -> dict[str, Any]:
    """One trial record: separated results only, no aggregate success field to misread."""
    observed = now or _now()
    gaps = {UNANSWERED_STAGES["SUBMITTING"], "DURATION", "NATIVE_READBACK", "TRIAL_ISOLATION",
            "TARGET_BEHAVIOUR_CONFIRMATION"}
    try:
        parent = ledger.get(parent_task_id)
    except (KeyError, ValueError, OSError):
        parent = None
    child_id = _first_child_id(parent) if parent else ""
    child = None
    if child_id:
        try:
            child = ledger.get(child_id)
        except (KeyError, ValueError, OSError):
            child = None
    if child is None:
        return {
            "schema_version": TRIAL_SCHEMA,
            "trial_id": trial_id or f"{parent_task_id}.trial.{child_id or 'ABSENT'}",
            "parent_task_id": parent_task_id,
            "child_task_id": child_id or None, "observed_at": observed,
            "isolation": {"basis": "NONE", "value": None},
            "separated_results": {
                "write": _stage("ABSENT", _NO_PRODUCER,
                                "试用没有可核对的子任务记录，因此它不存在，而不是正在等待。"),
                "native_readback": _stage(None, _NO_PRODUCER),
                "target_behaviour": _stage(None, _NO_PRODUCER),
            },
            "producer_gaps": sorted(gaps),
        }

    child_state = str(child.get("status") or "")
    write = _stage({"COMPLETED": "PASSED", "FAILED": "FAILED", "CANCELLED": "CANCELLED"}.get(child_state,
                                             "PENDING" if child_state else "UNKNOWN"),
                   "LEDGER_STATE", f"子任务账本状态为 {child_state or '空'}。")

    behaviour = _stage(None, _NO_PRODUCER)
    effects = [e for e in (child.get("external_effects") or []) if isinstance(e, Mapping)]
    if effects:
        statuses = {str(e.get("status") or "") for e in effects}
        single = next(iter(statuses)) if len(statuses) == 1 else "CONFLICT"
        reconciled = single != "PENDING"
        behaviour = _stage(EXTERNAL_TO_BEHAVIOUR.get(single, "UNKNOWN"),
                           "EXTERNAL_EFFECT_RECONCILED" if reconciled else _NO_PRODUCER,
                           f"外部效应核对状态为 {single}。")
        if reconciled:
            # PENDING is a recorded intent, not an observation of the target: the gap stays open until the
            # ledger actually reconciles it, or a page would read "we asked" as "the target did it".
            gaps.discard("TARGET_BEHAVIOUR_CONFIRMATION")

    isolation = {"basis": "NONE", "value": None}
    for row in executions or []:
        if not isinstance(row, Mapping):
            continue
        if child_id in {str(row.get("task_id") or ""), str(row.get("execution_id") or "")}:
            for basis, key in (("WORKTREE_ID", "worktree_id"), ("SESSION_ID", "session_id")):
                if row.get(key):
                    isolation = {"basis": basis, "value": str(row[key])}
                    gaps.discard("TRIAL_ISOLATION")
                    break
            break

    return {
        "schema_version": TRIAL_SCHEMA,
        "trial_id": trial_id or f"{parent_task_id}.trial.{child_id or 'UNNAMED'}",
        "parent_task_id": parent_task_id, "child_task_id": child_id or None, "observed_at": observed,
        "isolation": isolation,
        "separated_results": {"write": write, "native_readback": _stage(None, _NO_PRODUCER),
                              "target_behaviour": behaviour},
        "producer_gaps": sorted(gaps),
    }


def _expired(ledger: Any, task_id: str, now: str | None) -> bool:
    try:
        return bool(ledger.detect_zombie(task_id, now=now) if now else ledger.detect_zombie(task_id))
    except (KeyError, ValueError, OSError, TypeError):
        return False


def _first_child_id(parent: Mapping[str, Any]) -> str:
    """The ledger stores children as task ids (task_ledger.py:236-240), so the record has to be fetched."""
    children = parent.get("children") or []
    first = children[0] if isinstance(children, list) and children else None
    return str(first.get("task_id")) if isinstance(first, Mapping) else str(first or "")
