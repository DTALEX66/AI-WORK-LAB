# SPDX-License-Identifier: MIT
"""DL-TP-R2-018: Operation / Attempt state machine.

One logical Operation has multiple JobAttempts. Retry keeps operation /
idempotency key stable; each attempt has unique attempt_no. After DISPATCHING
without a receipt -> OUTCOME_UNKNOWN -> RECONCILING. A2/A3 unresolved unknown
never auto-retries.
"""
from __future__ import annotations

from .attempt_contract import validate_evidence

VALID = {
    "operation": ("PENDING", "RETRYABLE", "DISPATCHING", "OUTCOME_UNKNOWN", "CANCEL_REQUESTED", "RECONCILING", "SUCCEEDED", "COMPENSATING", "PAUSED_NEEDS_USER", "CANCELLED", "FAILED"),
    "attempt": ("PENDING", "RUNNING", "OUTCOME_UNKNOWN", "CANCEL_REQUESTED", "RECONCILING", "RECEIPTED", "FAILED", "TIMED_OUT", "CANCELLED"),
}
RISK_A2_A3 = {"A2", "A3"}


class OperationCoordinator:
    def __init__(self) -> None:
        self.state = "PENDING"
        self.cancel_requested = False

    def _require(self, *states: str) -> None:
        if self.state not in states:
            raise RuntimeError(f"operation transition not allowed from {self.state}")

    def dispatch(self) -> None:
        self._require("PENDING", "RETRYABLE")
        self.state = "DISPATCHING"

    def receipt_missing_after_dispatch(self, risk: str) -> str:
        self._require("DISPATCHING")
        self.state = "OUTCOME_UNKNOWN"
        if risk in RISK_A2_A3:
            return "RECONCILING_NO_AUTO_RETRY"
        return "RECONCILING"

    def reconcile(self, proof: str, *, evidence: dict | None = None) -> None:
        self._require("OUTCOME_UNKNOWN", "RECONCILING", "PAUSED_NEEDS_USER")
        if proof == "effect_verified":
            validate_evidence(evidence)
            self.state = "SUCCEEDED"
        elif proof == "effect_not_started":
            self.state = "CANCELLED" if self.cancel_requested else "RETRYABLE"
        elif proof == "verified_idempotent":
            self.state = "RECONCILING"
        elif proof == "document_reverted":
            self.state = "COMPENSATING"
        elif proof == "needs_user":
            self.state = "PAUSED_NEEDS_USER"
        else:
            raise ValueError(f"unresolvable proof: {proof}")

    def request_cancel(self) -> None:
        self._require("PENDING", "RETRYABLE", "DISPATCHING", "OUTCOME_UNKNOWN", "RECONCILING")
        self.cancel_requested = True
        self.state = "CANCELLED" if self.state in {"PENDING", "RETRYABLE"} else "CANCEL_REQUESTED"

    def cancel(self, acked: bool) -> None:
        if not acked:
            raise RuntimeError("cancel requires adapter ack before reconciliation")
        self._require("CANCEL_REQUESTED")
        self.state = "RECONCILING"
