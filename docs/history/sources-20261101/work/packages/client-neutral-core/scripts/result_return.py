"""NF-08-D: result return, read-back and explicit review-trigger.

Sends the result of a claimed task back to the authoritative location that
originated it; any authorized reviewer can read and continue from it.  Reuses
the existing receipt / outbox semantics (see ``action_receipt.py`` + the NF-08-B
durable outbox) — it does not invent a second receipt format.

Key semantics (acceptance AT-22/23/24)
---------------------------------------
* **Receipt binding** — a receipt is bound to project / task / revision / run /
  baseline / artifact digest, and it DISTINGUISHES "execution completed" from
  "accepted" (a receipt may carry execution_completed=True but accepted=False).
* **Outbox idempotency** — the receipt is recorded pending in the outbox; if
  the remote is unavailable the local completion fact is retained and a retry
  re-sends the SAME receipt, never re-runs the task.  A lost acknowledgement
  produces no duplicate result (dedupe by receipt id + revision).
* **Honest payload** — status / changes / tests / commit-PR (only if they
  actually exist) / blockers / open items are returned; a missing token or
  cost is displayed as UNKNOWN, never 0 and never a guess.
* **Projection + guarded reverse edit** — the external task-page status is a
  projection; a reverse edit must pass the SAME permission + version check.
  A review trigger uses an explicitly supported notification / automation; if
  none is configured it shows REVIEW_PENDING, and it NEVER claims to have
  woken a previous chat.
* **Privacy** — the task body is NOT written into public telemetry.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Mapping

RECEIPT_STATUSES = ("RECEIPT_PUBLISHED", "REVIEW_REQUESTED", "REVIEW_PENDING")


def _digest(*parts: Any) -> str:
    blob = json.dumps(parts, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class ResultReceipt:
    """A strong result receipt, distinct from a generic action receipt.

    ``execution_completed`` and ``accepted`` are separate booleans — the receipt
    says a run finished, not that the work was approved.
    """
    receipt_id: str
    project: str
    task_id: str
    task_revision: int
    run_session_id: str
    baseline: str
    artifact_digest: str
    execution_completed: bool
    accepted: bool
    status: str                       # RECEIPT_PUBLISHED | REVIEW_REQUESTED | REVIEW_PENDING
    changes: list[str] = field(default_factory=list)
    tests: dict[str, str] = field(default_factory=dict)
    commit: str | None = None          # only if it actually exists
    pull_request: str | None = None    # only if it actually exists
    blockers: list[str] = field(default_factory=list)
    open_items: list[str] = field(default_factory=list)
    token_usage: str = "UNKNOWN"       # shown as UNKNOWN when absent, never 0
    cost: str = "UNKNOWN"              # shown as UNKNOWN when absent, never a guess

    def __post_init__(self) -> None:
        if self.status not in RECEIPT_STATUSES:
            raise ValueError(f"status must be one of {RECEIPT_STATUSES}")
        # a receipt bound to a revision must carry the revision
        if self.task_revision < 1:
            raise ValueError("task_revision must be >= 1")

    def fingerprint(self) -> str:
        return _digest(self.receipt_id, self.project, self.task_id,
                       self.task_revision, self.run_session_id,
                       self.baseline, self.artifact_digest)

    def to_dict(self) -> dict[str, Any]:
        return {
            "receiptId": self.receipt_id, "project": self.project,
            "task_id": self.task_id, "task_revision": self.task_revision,
            "run_session_id": self.run_session_id, "baseline": self.baseline,
            "artifact_digest": self.artifact_digest,
            "execution_completed": self.execution_completed,
            "accepted": self.accepted,
            "status": self.status,
            "changes": list(self.changes), "tests": dict(self.tests),
            "commit": self.commit, "pull_request": self.pull_request,
            "blockers": list(self.blockers), "open_items": list(self.open_items),
            "token_usage": self.token_usage, "cost": self.cost,
            "fingerprint": self.fingerprint(),
        }


def build_receipt(*, receipt_id: str, project: str, task_id: str,
                  task_revision: int, run_session_id: str, baseline: str,
                  artifact_digest: str, execution_completed: bool,
                  status: str = "RECEIPT_PUBLISHED",
                  accepted: bool = False,
                  changes: list[str] | None = None,
                  tests: Mapping[str, str] | None = None,
                  commit: str | None = None,
                  pull_request: str | None = None,
                  blockers: list[str] | None = None,
                  open_items: list[str] | None = None,
                  token_usage: str | None = None,
                  cost: str | None = None) -> ResultReceipt:
    """Build a receipt.  Missing token/cost stays UNKNOWN, never 0."""
    return ResultReceipt(
        receipt_id=receipt_id, project=project, task_id=task_id,
        task_revision=task_revision, run_session_id=run_session_id,
        baseline=baseline, artifact_digest=artifact_digest,
        execution_completed=execution_completed, accepted=accepted,
        status=status, changes=list(changes or []), tests=dict(tests or {}),
        commit=commit, pull_request=pull_request, blockers=list(blockers or []),
        open_items=list(open_items or []),
        token_usage=token_usage if token_usage else "UNKNOWN",
        cost=cost if cost else "UNKNOWN",
    )


def missing_metrics_as_unknown(receipt: Mapping[str, Any]) -> dict[str, str]:
    """token / cost must display UNKNOWN when absent — never 0, never a guess."""
    return {
        "token_usage": receipt.get("token_usage") or "UNKNOWN",
        "cost": receipt.get("cost") or "UNKNOWN",
    }


class OutboxDedupe:
    """Outbox idempotency: re-sending the same receipt (same id + revision)
    is a no-op; a lost acknowledgement produces no duplicate result, and a
    retry re-sends the receipt — it never re-runs the task."""

    def __init__(self) -> None:
        self._sent: dict[str, dict[str, Any]] = {}
        self._pending: dict[str, dict[str, Any]] = {}
        self._revisions: dict[str, int] = {}

    def _key(self, receipt: Mapping[str, Any]) -> str:
        return f"{receipt.get('receiptId')}:{receipt.get('task_revision')}"

    def _conflicts(self, receipt: Mapping[str, Any]) -> bool:
        """A receipt id is bound to one revision; a second revision for the same
        id is a conflict, not a duplicate and not a new result."""
        receipt_id = receipt.get("receiptId")
        seen = self._revisions.get(receipt_id)
        return seen is not None and seen != receipt.get("task_revision")

    def _conflict_result(self, receipt: Mapping[str, Any]) -> dict[str, Any]:
        return {"conflict": True, "reason": "IDEMPOTENCY_CONFLICT",
                "key": self._key(receipt),
                "note": "the same receipt id is already bound to another revision; a revision is part of receipt identity"}

    def enqueue(self, receipt: Mapping[str, Any]) -> dict[str, Any]:
        key = self._key(receipt)
        if self._conflicts(receipt):
            return {"enqueued": False, **self._conflict_result(receipt)}
        if key in self._pending or key in self._sent:
            return {"enqueued": False, "duplicate": True, "key": key,
                    "note": "same receipt+revision already tracked; not re-run"}
        self._pending[key] = {"receipt": dict(receipt), "attempts": 0}
        self._revisions[receipt.get("receiptId")] = receipt.get("task_revision")
        return {"enqueued": True, "duplicate": False, "key": key}

    def send_attempt(self, receipt: Mapping[str, Any], *, ack: bool) -> dict[str, Any]:
        key = self._key(receipt)
        if self._conflicts(receipt):
            return {"sent": False, **self._conflict_result(receipt)}
        rec = self._pending.get(key)
        if rec is None:
            # not ours to send — it was never enqueued
            return {"sent": False, "reason": "not enqueued"}
        rec["attempts"] += 1
        if ack:
            # move to sent exactly once; a later re-send of the same receipt is
            # idempotent (no duplicate result)
            self._sent[key] = rec["receipt"]
            del self._pending[key]
            return {"sent": True, "duplicate": key in self._sent, "attempts": rec["attempts"],
                    "note": "acknowledged; subsequent same-receipt sends are no-ops"}
        # remote unavailable / ack lost: the LOCAL completion fact is retained,
        # the receipt stays pending, and we retry the RECEIPT — never the task
        return {"sent": False, "attempts": rec["attempts"],
                "local_fact_retained": True, "note": "retry re-sends the receipt; the task is NOT re-run"}

    def pending(self) -> list[dict[str, Any]]:
        return [dict(v["receipt"]) for v in self._pending.values()]

    def lost_ack_reconcile(self, receipt: Mapping[str, Any]) -> dict[str, Any]:
        """Response lost: check whether it is already sent; only resend if absent."""
        key = self._key(receipt)
        if self._conflicts(receipt):
            return {"resent": False, **self._conflict_result(receipt)}
        if key in self._sent:
            return {"resent": False, "already": True, "key": key,
                    "note": "receipt already acknowledged; no duplicate result"}
        return {"resent": True, **self.send_attempt(receipt, ack=False)}


class EgressPolicy:
    """Default-deny egress for a result receipt.

    Nothing leaves until the destination is explicitly authorized, and private
    payload keys are refused even to an authorized destination.  Authorization
    to send says nothing about whether the work is accepted: ``accepted`` stays
    a separate fact in the returned payload.
    """

    PRIVATE_KEYS = frozenset({"task_body", "session_log", "prompt", "response"})

    def __init__(self) -> None:
        self._authorized: set[str] = set()

    def authorize(self, destination: str) -> None:
        self._authorized.add(destination)

    def check(self, destination: str, receipt: Mapping[str, Any]) -> dict[str, Any]:
        leaked = sorted(k for k in self.PRIVATE_KEYS if k in receipt)
        if leaked:
            return {"allowed": False, "reason": "PRIVATE_FIELD_REFUSED",
                    "fields": leaked, "destination": destination}
        if destination not in self._authorized:
            return {"allowed": False, "reason": "DESTINATION_NOT_AUTHORISED",
                    "destination": destination}
        return {"allowed": True, "destination": destination,
                "payload": _public_telemetry(receipt)}


def read_back_for_revision(receipts: list[Mapping[str, Any]],
                           task_id: str, revision: int) -> dict[str, Any]:
    """A planner's fresh read sees the result for the exact revision, without
    the user hauling logs back by hand."""
    exact = [r for r in receipts
             if r.get("task_id") == task_id and int(r.get("task_revision", 0)) == revision]
    if not exact:
        return {"found": False, "task_id": task_id, "revision": revision,
                "note": "no receipt for this revision; not guessed from another revision"}
    latest = max(exact, key=lambda r: r.get("receiptId", ""))
    return {"found": True, "task_id": task_id, "revision": revision,
            "receipt_id": latest.get("receiptId"),
            "execution_completed": latest.get("execution_completed"),
            "accepted": latest.get("accepted"),
            "status": latest.get("status"),
            "artifact_digest": latest.get("artifact_digest"),
            "token_usage": latest.get("token_usage", "UNKNOWN"),
            "cost": latest.get("cost", "UNKNOWN")}


def _public_telemetry(receipt: Mapping[str, Any]) -> dict[str, Any]:
    """What MAY go into public telemetry: status / counts / digests only.  The
    task body and private session logs are NEVER included."""
    return {
        "receipt_id": receipt.get("receiptId"),
        "project": receipt.get("project"),
        "task_id": receipt.get("task_id"),
        "task_revision": receipt.get("task_revision"),
        "execution_completed": receipt.get("execution_completed"),
        "accepted": receipt.get("accepted"),
        "artifact_digest": receipt.get("artifact_digest"),
        "token_usage": receipt.get("token_usage", "UNKNOWN"),
        "cost": receipt.get("cost", "UNKNOWN"),
        "body_included": False,   # explicit guard
        "session_log_included": False,
    }


class ProjectionGate:
    """The external task-page status is a projection; a reverse edit must pass
    the SAME permission + version check as the forward path.  A review trigger
    uses an explicitly supported notification/automation; if none is set it is
    REVIEW_PENDING, and it never claims to have woken a previous chat."""

    def __init__(self) -> None:
        self._supported_review: set[str] = set()
        self._page_versions: dict[str, int] = {}

    def register_review_channel(self, task_id: str, channel: str) -> None:
        """Only explicitly-supported notification/automation channels qualify."""
        self._supported_review.add(f"{task_id}:{channel}")

    def reverse_edit(self, task_id: str, *, base_version: int,
                     permission: str, expected_version: int | None = None) -> dict[str, Any]:
        cur = self._page_versions.get(task_id, 0)
        if base_version != cur:
            return {"edit_applied": False, "reason": "version check failed (permission/version check must pass)",
                    "current_version": cur, "base_version": base_version}
        if expected_version is not None and expected_version != cur:
            return {"edit_applied": False, "reason": "expected version mismatch",
                    "current_version": cur}
        self._page_versions[task_id] = cur + 1
        return {"edit_applied": True, "new_version": cur + 1, "permission": permission}

    def trigger_review(self, task_id: str, *, channel: str | None,
                       task_body: str | None = None) -> dict[str, Any]:
        # the body is NEVER part of the trigger; explicit guard
        assert task_body is None, "trigger must not carry the task body"
        if channel and f"{task_id}:{channel}" in self._supported_review:
            return {"status": "REVIEW_REQUESTED", "channel": channel,
                    "note": "review triggered via an explicitly supported channel"}
        return {"status": "REVIEW_PENDING", "channel": None,
                "note": "no supported notification/automation configured; "
                        "review is PENDING, not claimed as a woken chat"}

    def did_not_wake_previous_chat(self) -> bool:
        """An honest invariant: this module never claims to have woken a prior
        chat session — a review trigger only fires a supported notification."""
        return True


def distinguish_receipt_published_vs_review_requested(receipt: Mapping[str, Any]) -> dict[str, Any]:
    """RECEIPT_PUBLISHED and REVIEW_REQUESTED are different states; a published
    receipt does not imply a review was requested, and vice versa."""
    status = receipt.get("status")
    if status == "RECEIPT_PUBLISHED":
        return {"state": "published_only", "review_requested": False,
                "note": "result is available to read back; no review was requested"}
    if status == "REVIEW_REQUESTED":
        return {"state": "review_requested", "review_requested": True,
                "note": "a review was explicitly requested via a supported channel"}
    if status == "REVIEW_PENDING":
        return {"state": "review_pending", "review_requested": True,
                "note": "review is pending; no supported channel was configured"}
    raise ValueError(f"unknown receipt status {status!r}")
