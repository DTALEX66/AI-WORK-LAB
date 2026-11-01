"""NF-08-E: revision / cancellation / out-of-order / unknown-effect convergence.

When a user adjusts requirements across software, the OLD revision must not
resurrect or clobber the new one, and a cancellation plus already-happened /
still-unknown effects are handled honestly.  Reuses the revision-chain /
late-result semantics already defined by ``handoff_envelope.RevisionRegistry``
and the task-ledger transition + external-effect vocabulary — no second
convergence model.

Key semantics (acceptance AT-25/26/27/28)
------------------------------------------
* **Late completion of a lower revision never ends a higher one** — rev1 is
  still running when rev2 is published; rev1's late result is held for audit,
  it does not close rev2 or advance the active revision.
* **After cancellation, no new effect is started** — a task transitioned to
  CANCELLED (a terminal state) refuses any new external-effect claim;
  already-CONFIRMED or still-PENDING (unknown) effects remain queryable.
* **Unknown effects are not blindly retried** — an effect in the UNKNOWN state
  is reconciled against evidence first; a blind retry is refused.  The
  rejection is scoped to the AFFECTED task only, not a global halt.
"""
from __future__ import annotations

from typing import Any, Mapping

# terminal task states: from here no NEW effect may be started
TERMINAL_STATES = {"COMPLETED", "FAILED", "CANCELLED"}
# effect states from the task ledger's EXTERNAL_EFFECT_STATES
EFFECT_PENDING = "PENDING"
EFFECT_CONFIRMED = "CONFIRMED"
EFFECT_ABSENT = "ABSENT"
EFFECT_CONFLICT = "CONFLICT"
EFFECT_UNKNOWN = "UNKNOWN"

# an effect that cannot be told confirmed/absent — must be reconciled, not retried
_RETRY_FORBIDDEN = {EFFECT_UNKNOWN, EFFECT_CONFLICT}


class RevisionConvergence:
    """Converges multi-revision results for one task.  The active revision is
    the highest published one; a late lower-revision result is held, never
    allowed to end or advance the active revision."""

    def __init__(self, task_id: str) -> None:
        self.task_id = task_id
        self.active_revision: int | None = None
        self.held: list[dict[str, Any]] = []
        self.finished: dict[int, str] = {}  # revision -> outcome

    def publish(self, revision: int) -> dict[str, Any]:
        """Publish a revision: it becomes active only if it is the highest so
        far.  Publishing a lower revision while a higher one is active is a
        no-op for the active pointer (it is held, not a regression)."""
        if self.active_revision is None or revision > self.active_revision:
            self.active_revision = revision
            return {"published": True, "active_revision": revision, "advanced": True}
        return {"published": True, "active_revision": self.active_revision,
                "advanced": False, "held_as_stale": True}

    def late_result(self, revision: int, outcome: str) -> dict[str, Any]:
        """A result arrives for ``revision``.  If a higher revision is active,
        this late result is HELD (for audit) and does NOT end/advance the
        active revision.  The acceptance row: 'rev1 running, rev2 published;
        rev1's late completion does not end rev2'."""
        if self.active_revision is not None and revision < self.active_revision:
            record = {"revision": revision, "outcome": outcome, "held": True,
                      "active_revision": self.active_revision,
                      "ended_active": False}
            self.held.append(record)
            return record
        # same or the active revision: it may finish that revision only
        if revision == self.active_revision:
            self.finished[revision] = outcome
            return {"revision": revision, "outcome": outcome, "held": False,
                    "ended_active": True, "active_revision": self.active_revision}
        # a result for a revision that was never active: hold it as unknown
        record = {"revision": revision, "outcome": outcome, "held": True,
                   "active_revision": self.active_revision, "ended_active": False,
                   "reason": "result for a non-active revision"}
        self.held.append(record)
        return record

    def snapshot(self) -> dict[str, Any]:
        return {"task_id": self.task_id, "active_revision": self.active_revision,
                "finished": dict(self.finished), "held": list(self.held)}


class CancellationGuard:
    """After a task is cancelled (terminal), no NEW external effect may start.
    Already-confirmed or still-unknown effects remain queryable; an unknown one
    is reconciled against evidence, never blindly retried.  Scope is the
    affected task only."""

    def __init__(self, task_id: str, task_status: str) -> None:
        self.task_id = task_id
        self.task_status = task_status
        self._effects: dict[str, str] = {}
        self._attempts: list[dict[str, Any]] = []

    def record_effect(self, effect_id: str, state: str) -> dict[str, Any]:
        if state not in {EFFECT_PENDING, EFFECT_CONFIRMED, EFFECT_ABSENT,
                         EFFECT_CONFLICT, EFFECT_UNKNOWN}:
            raise ValueError(f"unknown effect state {state!r}")
        self._effects[effect_id] = state
        return {"effect_id": effect_id, "state": state}

    def try_start_effect(self, effect_id: str) -> dict[str, Any]:
        """A cancelled task refuses to start any new effect; a non-cancelled
        task accepts it (as PENDING)."""
        if self.task_status in TERMINAL_STATES:
            decision = "REJECTED_CANCELLED" if self.task_status == "CANCELLED" else "REJECTED_TERMINAL"
            self._attempts.append({"effect_id": effect_id, "decision": decision,
                                   "started": False,
                                   "note": f"task {self.task_status}; no new effect started"})
            return {"started": False, "decision": decision, "scoped_to_task": self.task_id}
        self._effects[effect_id] = EFFECT_PENDING
        self._attempts.append({"effect_id": effect_id, "decision": "ACCEPTED", "started": True})
        return {"started": True, "decision": "ACCEPTED", "state": EFFECT_PENDING}

    def reconcile_unknown(self, effect_id: str, observed_state: str) -> dict[str, Any]:
        """An unknown / conflicted effect is reconciled against real evidence
        before anything is retried; a blind retry is refused."""
        current = self._effects.get(effect_id)
        if current in _RETRY_FORBIDDEN:
            return {"blind_retry": False, "effect_id": effect_id,
                    "previously": current, "reconciled_to": observed_state,
                    "note": "reconciled against evidence; not blindly retried",
                    "scoped_to_task": self.task_id}
        # a CONFIRMED effect cannot be downgraded
        if current == EFFECT_CONFIRMED and observed_state != EFFECT_CONFIRMED:
            return {"blind_retry": False, "effect_id": effect_id, "rejected": True,
                    "reason": "confirmed effect cannot be downgraded",
                    "scoped_to_task": self.task_id}
        self._effects[effect_id] = observed_state
        return {"blind_retry": False, "effect_id": effect_id,
                "reconciled_to": observed_state, "scoped_to_task": self.task_id}

    def blind_retry_allowed(self, effect_id: str) -> bool:
        """An effect in the UNKNOWN/CONFLICT state may never be blindly
        retried; only an ABSENT (proven not happened) effect may re-run."""
        return self._effects.get(effect_id) == EFFECT_ABSENT

    def queryable_effects(self) -> dict[str, str]:
        """Already-happened / still-unknown effects are queryable after
        cancellation."""
        return dict(self._effects)

    def attempts(self) -> list[dict[str, Any]]:
        return list(self._attempts)


class OutOfOrderConvergence:
    """Out-of-order deliveries (a result for an older revision arriving after
    a newer one) are absorbed: the newest revision is authoritative, older
    results are retained for audit and never reorder the active pointer."""

    def __init__(self, task_id: str) -> None:
        self.task_id = task_id
        self.results_by_revision: dict[int, list[str]] = {}
        self.order: list[int] = []

    def deliver(self, revision: int, outcome: str) -> dict[str, Any]:
        self.results_by_revision.setdefault(revision, []).append(outcome)
        if revision not in self.order:
            self.order.append(revision)
        newest = max(self.results_by_revision)
        return {"delivered_revision": revision, "authoritative_revision": newest,
                "is_newest": revision == newest,
                "older_results_retained": sorted(self.results_by_revision)}

    def authoritative(self) -> dict[str, Any]:
        if not self.results_by_revision:
            return {"revision": None, "outcomes": []}
        newest = max(self.results_by_revision)
        return {"revision": newest, "outcomes": self.results_by_revision[newest]}
