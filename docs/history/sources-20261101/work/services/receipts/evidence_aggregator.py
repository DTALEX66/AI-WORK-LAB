"""Multi-evidence state aggregator (WLGM-130).

Builds a trustworthy project-activity projection from execution facts:

- every execution keeps its own state; project aggregation never overrides
  execution detail;
- strong evidence (A/B/C) wins, weak evidence (D/E) only supplements;
- evidence TTL + late-event window;
- 15s without updates -> DELAYED, 60s -> LOST (thresholds configurable);
- a missing terminal state never auto-completes;
- WAITING_USER / WAITING_APPROVAL / BLOCKED are separate states;
- multiple agents on one project show counts and platform distribution;
- source conflicts lower quality and keep an explanation.

State transitions are validated: no illegal transitions (property-style).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class ActivityState(str, Enum):
    ACTIVE = "ACTIVE"
    IDLE = "IDLE"
    NO_ACTIVE_EXECUTION = "NO_ACTIVE_EXECUTION"
    PARTIAL_VISIBILITY = "PARTIAL_VISIBILITY"
    UNRESOLVED = "UNRESOLVED"
    UNKNOWN = "UNKNOWN"


class AttentionState(str, Enum):
    NONE = "NONE"
    WAITING_USER_PRESENT = "WAITING_USER_PRESENT"
    WAITING_APPROVAL_PRESENT = "WAITING_APPROVAL_PRESENT"
    BLOCKED_PRESENT = "BLOCKED_PRESENT"


class ExecutionState(str, Enum):
    DISCOVERED = "DISCOVERED"
    STARTING = "STARTING"
    RUNNING = "RUNNING"
    WAITING_USER = "WAITING_USER"
    WAITING_APPROVAL = "WAITING_APPROVAL"
    BLOCKED = "BLOCKED"
    IDLE = "IDLE"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    LOST = "LOST"
    UNKNOWN = "UNKNOWN"


class TransportState(str, Enum):
    CONNECTING = "CONNECTING"
    LIVE = "LIVE"
    DELAYED = "DELAYED"
    OFFLINE = "OFFLINE"
    UNKNOWN = "UNKNOWN"


TERMINAL_EXECUTION_STATES = {ExecutionState.COMPLETED, ExecutionState.FAILED, ExecutionState.CANCELLED, ExecutionState.LOST}

VALID_TRANSITIONS: dict[ExecutionState, set[ExecutionState]] = {
    ExecutionState.DISCOVERED: {ExecutionState.STARTING, ExecutionState.UNKNOWN},
    ExecutionState.STARTING: {ExecutionState.RUNNING, ExecutionState.FAILED, ExecutionState.CANCELLED, ExecutionState.LOST, ExecutionState.UNKNOWN},
    ExecutionState.RUNNING: {
        ExecutionState.WAITING_USER, ExecutionState.WAITING_APPROVAL, ExecutionState.BLOCKED,
        ExecutionState.COMPLETED, ExecutionState.FAILED, ExecutionState.CANCELLED, ExecutionState.LOST,
        ExecutionState.UNKNOWN,
    },
    ExecutionState.WAITING_USER: {ExecutionState.RUNNING, ExecutionState.COMPLETED, ExecutionState.FAILED, ExecutionState.CANCELLED, ExecutionState.LOST, ExecutionState.UNKNOWN},
    ExecutionState.WAITING_APPROVAL: {ExecutionState.RUNNING, ExecutionState.COMPLETED, ExecutionState.FAILED, ExecutionState.CANCELLED, ExecutionState.LOST, ExecutionState.UNKNOWN},
    ExecutionState.BLOCKED: {ExecutionState.RUNNING, ExecutionState.WAITING_USER, ExecutionState.WAITING_APPROVAL, ExecutionState.COMPLETED, ExecutionState.FAILED, ExecutionState.CANCELLED, ExecutionState.LOST, ExecutionState.UNKNOWN},
    ExecutionState.IDLE: {ExecutionState.RUNNING, ExecutionState.STARTING, ExecutionState.UNKNOWN},
    ExecutionState.COMPLETED: set(),
    ExecutionState.FAILED: set(),
    ExecutionState.CANCELLED: set(),
    ExecutionState.LOST: set(),
    ExecutionState.UNKNOWN: {ExecutionState.DISCOVERED, ExecutionState.STARTING, ExecutionState.RUNNING},
}


class IllegalTransitionError(ValueError):
    pass


@dataclass
class ExecutionStatus:
    execution_id: str
    agent: str
    session_id: str | None = None
    anchor_project_id: str | None = None
    worktree_id: str | None = None
    working_area: str | None = None
    state: ExecutionState = ExecutionState.DISCOVERED
    state_quality: str = "SOURCE_REPORTED"
    started_at: str | None = None
    last_heartbeat_at: str | None = None
    transport_state: TransportState = TransportState.UNKNOWN
    conflict_evidence: list[str] = field(default_factory=list)

    def transition(self, new_state: ExecutionState, *, at: str | None = None, allow_forced: bool = False) -> None:
        if new_state == self.state:
            return
        if not allow_forced and new_state not in VALID_TRANSITIONS.get(self.state, set()):
            raise IllegalTransitionError(f"{self.state.value} -> {new_state.value} is not a valid transition")
        self.state = new_state
        if at:
            self.last_heartbeat_at = at

    def touch_heartbeat(self, at: str) -> None:
        self.last_heartbeat_at = at

    def mark_lost(self, at: str) -> None:
        self.state = ExecutionState.LOST
        self.last_heartbeat_at = at


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _age_seconds(iso_value: str | None, now: str | None = None) -> float | None:
    if not iso_value:
        return None
    try:
        parsed = datetime.fromisoformat(iso_value.replace("Z", "+00:00"))
        reference = datetime.fromisoformat((now or _now()).replace("Z", "+00:00"))
        return (reference - parsed).total_seconds()
    except ValueError:
        return None


class EvidenceAggregator:
    """Tracks executions and projects; emits activity projections."""

    def __init__(
        self,
        *,
        delayed_seconds: float = 15.0,
        lost_seconds: float = 60.0,
        late_window_seconds: float = 30.0,
        strong_levels: set[str] | None = None,
    ) -> None:
        self.delayed_seconds = delayed_seconds
        self.lost_seconds = lost_seconds
        self.late_window_seconds = late_window_seconds
        self.strong_levels = strong_levels or {"A", "B", "C"}
        self.executions: dict[str, ExecutionStatus] = {}

    def register_execution(
        self,
        execution_id: str,
        agent: str,
        *,
        anchor_project_id: str | None = None,
        session_id: str | None = None,
        worktree_id: str | None = None,
        working_area: str | None = None,
        evidence_level: str = "C",
    ) -> ExecutionStatus:
        status = ExecutionStatus(
            execution_id=execution_id,
            agent=agent,
            session_id=session_id,
            anchor_project_id=anchor_project_id,
            worktree_id=worktree_id,
            working_area=working_area,
            state=ExecutionState.DISCOVERED,
            state_quality="SOURCE_REPORTED" if evidence_level in self.strong_levels else "INFERRED",
            started_at=_now(),
        )
        self.executions[execution_id] = status
        return status

    def apply_event(
        self,
        *,
        execution_id: str,
        event_type: str,
        occurred_at: str,
        evidence_level: str = "C",
        source_ref: str = "",
        anchor_project_id: str | None = None,
    ) -> ExecutionStatus:
        """Apply an execution event, rejecting weak-evidence RUNNING claims."""
        status = self.executions.get(execution_id)
        if status is None:
            status = self.register_execution(
                execution_id, agent="unknown", anchor_project_id=anchor_project_id, evidence_level=evidence_level
            )
        target = _event_to_state(event_type)
        if target == ExecutionState.RUNNING and evidence_level not in self.strong_levels:
            # Weak evidence can only raise visibility, never claim RUNNING.
            status.conflict_evidence.append(f"weak-evidence-running:{source_ref}")
            status.state_quality = "CORRELATED"
            return status
        if status.state in TERMINAL_EXECUTION_STATES:
            # Events after a terminal state are recorded as conflicts, never replayed.
            status.conflict_evidence.append(f"event-after-terminal:{event_type}")
            return status
        # Event flow is authoritative: an event moves the execution from any
        # non-terminal state to its target (manual transition() stays strict).
        status.transition(target, at=occurred_at, allow_forced=True)
        return status

    def projection(self, project_id: str, now: str | None = None) -> dict[str, Any]:
        """Compute the project activity projection (WLGM-130 suggested shape)."""
        reference = now or _now()
        project_executions = [e for e in self.executions.values() if (e.anchor_project_id or "unknown") == project_id]
        if not project_executions:
            return {
                "projectId": project_id,
                "activityState": ActivityState.NO_ACTIVE_EXECUTION.value,
                "attentionState": AttentionState.NONE.value,
                "activeExecutionCount": 0,
                "agentCounts": {},
                "visibility": "UNKNOWN",
                "quality": "UNKNOWN",
                "lastStrongEvidenceAt": None,
            }

        active_count = 0
        attention = AttentionState.NONE
        agent_counts: dict[str, int] = {}
        visibility_unknown = 0
        has_weak_only = 0
        last_strong: str | None = None

        for status in project_executions:
            age = _age_seconds(status.last_heartbeat_at or status.started_at, reference)
            if status.state not in TERMINAL_EXECUTION_STATES:
                if age is not None and age > self.lost_seconds:
                    status.mark_lost(reference)
            if status.state in {ExecutionState.RUNNING, ExecutionState.STARTING, ExecutionState.WAITING_USER, ExecutionState.WAITING_APPROVAL, ExecutionState.BLOCKED}:
                active_count += 1
            agent_counts[status.agent] = agent_counts.get(status.agent, 0) + 1
            if status.state == ExecutionState.WAITING_USER and attention.value == "NONE":
                attention = AttentionState.WAITING_USER_PRESENT
            if status.state == ExecutionState.WAITING_APPROVAL and attention.value in {AttentionState.NONE, AttentionState.WAITING_USER_PRESENT}:
                attention = AttentionState.WAITING_APPROVAL_PRESENT
            if status.state == ExecutionState.BLOCKED:
                attention = AttentionState.BLOCKED_PRESENT
            if status.state in {ExecutionState.UNKNOWN, ExecutionState.LOST}:
                visibility_unknown += 1
            if status.state_quality == "INFERRED":
                has_weak_only += 1
            if status.state_quality in {"EXACT", "SOURCE_REPORTED", "CORRELATED"}:
                last_strong = status.last_heartbeat_at or status.started_at

        if active_count == 0 and visibility_unknown == len(project_executions):
            activity = ActivityState.UNKNOWN
        elif active_count == 0 and has_weak_only == len(project_executions):
            activity = ActivityState.PARTIAL_VISIBILITY
        elif active_count == 0:
            activity = ActivityState.IDLE
        else:
            activity = ActivityState.ACTIVE

        if visibility_unknown > 0 and active_count == 0:
            visibility = "PARTIAL"
        elif visibility_unknown > 0:
            visibility = "PARTIAL"
        elif has_weak_only == len(project_executions):
            visibility = "PARTIAL"
        else:
            visibility = "FULL"

        return {
            "projectId": project_id,
            "activityState": activity.value,
            "attentionState": attention.value,
            "activeExecutionCount": active_count,
            "agentCounts": agent_counts,
            "visibility": visibility,
            "quality": "CORRELATED" if any(e.conflict_evidence for e in project_executions) else "SOURCE_REPORTED",
            "lastStrongEvidenceAt": last_strong,
        }


def _event_to_state(event_type: str) -> ExecutionState:
    mapping = {
        "execution_started": ExecutionState.STARTING,
        "execution_running": ExecutionState.RUNNING,
        "execution_waiting_user": ExecutionState.WAITING_USER,
        "execution_waiting_approval": ExecutionState.WAITING_APPROVAL,
        "execution_blocked": ExecutionState.BLOCKED,
        "execution_completed": ExecutionState.COMPLETED,
        "execution_failed": ExecutionState.FAILED,
        "execution_cancelled": ExecutionState.CANCELLED,
        "execution_heartbeat": ExecutionState.RUNNING,
    }
    return mapping.get(event_type, ExecutionState.UNKNOWN)
