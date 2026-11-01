"""Minimal cross-software task handoff primitive (integrated-taskpack NF-08).

Reuses the existing Task Ledger semantics and adds only the *gap set* NF-08
calls out — the scenarios the 8 single-writer replay classes do NOT cover in a
cross-execution-entry handoff:

  1. response-lost: the receiving entry never confirms; the SAME delivery id
     is re-sent and must be idempotent (no duplicate side effect).
  2. restart-duplicate: after a restart the same task is delivered twice to
     one entry; only the first is a real effect.
  3. produce-after-cancel: a task already in a terminal state (CANCELLED /
     COMPLETED / FAILED) must NOT produce a new side effect.
  4. external-effect-unknown: an effect whose external outcome is unknown is
     reconciled (observed absent/unknown) and is NOT blindly retried.

The payload is desensitized: only the handoff whitelist travels (repo / head /
task / goal / verified / next / permission scope).  Credentials and raw
conversation are dropped by construction.  Everything here is pure and
deterministic — no real network, no native private database, no paid calls,
and it never claims exactly-once (it claims idempotency + fail-closed).
"""
from __future__ import annotations

import hashlib
import json
from typing import Any

# Only these keys travel in a handoff.  Anything else (credentials, raw
# conversation, tokens, session internals) is dropped by construction.
HANDOFF_WHITELIST = (
    "repo", "head", "task_id", "goal", "verified", "next_step", "permission_scope",
)

TERMINAL_STATES = frozenset({"CANCELLED", "COMPLETED", "FAILED"})

SCHEMA = "workflow/task-handoff/v1"


def sanitize_payload(raw: dict[str, Any]) -> dict[str, Any]:
    """Keep only the handoff whitelist; drop credentials/conversation."""
    clean = {k: raw[k] for k in HANDOFF_WHITELIST if k in raw}
    clean["schema"] = SCHEMA
    return clean


def payload_digest(payload: dict[str, Any]) -> str:
    """Stable digest over the desensitized payload (for idempotency)."""
    blob = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


class HandoffRelay:
    """Idempotent two-entry handoff relay.

    ``delivery_id`` is stable across re-sends, so a lost acknowledgement is
    recovered by re-sending the SAME id (no duplicate side effect).  A
    delivery id reused for a DIFFERENT payload is a conflict, never silently
    accepted.
    """

    def __init__(self) -> None:
        self._delivered: dict[str, str] = {}
        self.effects_executed = 0

    def deliver(self, raw_payload: dict[str, Any], delivery_id: str) -> dict[str, Any]:
        payload = sanitize_payload(raw_payload)
        digest = payload_digest(payload)
        if delivery_id in self._delivered:
            if self._delivered[delivery_id] != digest:
                return {
                    "status": "CONFLICT",
                    "delivery_id": delivery_id,
                    "reason": "same delivery_id carried a different payload",
                    "side_effect_executed": False,
                }
            return {
                "status": "ALREADY_DELIVERED",
                "delivery_id": delivery_id,
                "idempotent": True,
                "side_effect_executed": False,
            }
        self._delivered[delivery_id] = digest
        self.effects_executed += 1
        return {
            "status": "DELIVERED",
            "delivery_id": delivery_id,
            "idempotent": False,
            "side_effect_executed": True,
            "digest": digest,
        }

    def response_lost_redelivery(self, raw_payload: dict[str, Any], delivery_id: str) -> dict[str, Any]:
        """Send, lose the ack, re-send the SAME id: exactly one real effect."""
        first = self.deliver(raw_payload, delivery_id)
        second = self.deliver(raw_payload, delivery_id)  # same id -> idempotent
        return {
            "first": first["status"],
            "second": second["status"],
            "side_effects": self.effects_executed,
            "idempotent": second.get("idempotent", False),
        }

    def restart_duplicate(self, raw_payload: dict[str, Any], delivery_id: str) -> dict[str, Any]:
        """After a restart the task is delivered twice to one entry."""
        before = self.effects_executed
        a = self.deliver(raw_payload, delivery_id)
        b = self.deliver(raw_payload, delivery_id)
        return {
            "first": a["status"],
            "second": b["status"],
            "side_effects_this_delivery": self.effects_executed - before,
            "redundant_is_noop": b.get("idempotent", False),
        }


def produce_after_cancel(task_status: str, effect_id: str, action: str) -> dict[str, Any]:
    """A terminal task must not produce a new external side effect."""
    if task_status in TERMINAL_STATES:
        return {
            "status": "REFUSED",
            "task_status": task_status,
            "effect_id": effect_id,
            "side_effect_executed": False,
            "reason": f"task in terminal state {task_status}; no new effect produced",
        }
    return {
        "status": "ALLOWED",
        "task_status": task_status,
        "effect_id": effect_id,
        "action": action,
        "side_effect_executed": True,
    }


def external_effect_unknown(effect_id: str, action: str, observed: str = "ABSENT") -> dict[str, Any]:
    """An unknown external effect is reconciled, never blindly retried."""
    if observed not in ("CONFIRMED", "ABSENT", "CONFLICT"):
        raise ValueError(f"unknown observation: {observed!r}")
    return {
        "status": "RECONCILED_UNKNOWN" if observed == "ABSENT" else "RECONCILED",
        "effect_id": effect_id,
        "action": action,
        "observed": observed,
        "blind_retry": False,
        "note": "external outcome unknown -> reconciled as observed; "
                "a blind re-attempt of a side effect is never performed",
    }
