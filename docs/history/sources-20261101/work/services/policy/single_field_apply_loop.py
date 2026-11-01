"""Single-field controlled apply + rollback closed loop (NF-07).

One MANAGE-whitelist user field, one controlled scope.  The loop consumes an
existing ``three_way_compare`` ActionPlan (a single PATCH field) and an
``apply_safety`` receipt, then drives the one write through a *file-backed
synthetic adapter* inside a caller-supplied project directory — never a real
client config.  It separates the three value states NF-07 requires
(file value / runtime-effective value / restart-needed value), enforces
operation-id idempotency, and — on restore — refuses blind rollback when the
value has been concurrently changed (the concurrent user value is preserved).

Honest labeling: with no real adapter the loop is **simulated**; the receipt
carries ``real_adapter_exercised=False`` and the card's *real-field* status
stays NOT-PASSED-awaiting-authorization.  This module proves the mechanism;
it does not claim a real deployment.  No credentials, no network, no paid
calls; the synthetic state file is written only into the caller's directory.
"""
from __future__ import annotations

import json
import os
from typing import Any

SCHEMA = "workflow/single-field-apply-loop/v1"
REQUIRED = ("path", "old_value", "new_value")


class FieldConflictRefused(Exception):
    """Raised when a controlled restore would overwrite a concurrent change."""


def _load(path: str | os.PathLike) -> dict[str, Any]:
    if not os.path.exists(str(path)):
        return {}
    with open(str(path), "r", encoding="utf-8") as fh:
        return json.load(fh)


class SingleFieldApplyLoop:
    def __init__(self, state_dir: str | os.PathLike, operation_id: str) -> None:
        self.state_dir = str(state_dir)
        self.operation_id = operation_id
        self.state_file = os.path.join(self.state_dir, "single_field_state.json")
        self.applied_ledger = os.path.join(self.state_dir, "applied_operations.json")

    # -- synthetic file-backed "native" adapter ---------------------------
    def _read_field(self, path: str) -> Any:
        return _load(self.state_file).get(path)

    def _write_field(self, path: str, value: Any) -> None:
        state = _load(self.state_file)
        state[path] = value
        os.makedirs(self.state_dir, exist_ok=True)
        with open(self.state_file, "w", encoding="utf-8") as fh:
            json.dump(state, fh, indent=2, sort_keys=True, ensure_ascii=False)

    def _record_written(self, path: str, value: Any) -> None:
        """Track the value THIS loop applied, for controlled-restore guards."""
        ledger = _load(self.applied_ledger)
        ledger.setdefault("last_written", {})[path] = value
        os.makedirs(self.state_dir, exist_ok=True)
        with open(self.applied_ledger, "w", encoding="utf-8") as fh:
            json.dump(ledger, fh, indent=2, sort_keys=True, ensure_ascii=False)

    def _last_written(self, path: str) -> Any:
        return _load(self.applied_ledger).get("last_written", {}).get(path)

    def _applied(self, op: str) -> bool:
        return op in _load(self.applied_ledger).get("operations", [])

    def _mark_applied(self, op: str) -> None:
        ledger = _load(self.applied_ledger)
        ops = ledger.setdefault("operations", [])
        if op not in ops:
            ops.append(op)
        os.makedirs(self.state_dir, exist_ok=True)
        with open(self.applied_ledger, "w", encoding="utf-8") as fh:
            json.dump(ledger, fh, indent=2, sort_keys=True, ensure_ascii=False)

    # -- the closed loop --------------------------------------------------
    def plan(self, field: dict[str, Any]) -> dict[str, Any]:
        """Show old -> target -> profile -> reversible method -> side-effects."""
        missing = [k for k in REQUIRED if k not in field]
        if missing:
            return {"status": "INVALID_PLAN", "missing": missing}
        return {
            "status": "PLANNED",
            "field": field["path"],
            "previous_value": field["old_value"],
            "target_value": field["new_value"],
            "target_profile": field.get("adapter", "hermes"),
            "reversible": "backup-cas-readback-rollback",
            "side_effects": field.get("side_effects", "none-declared"),
            "restart_needed": bool(field.get("restart_needed", False)),
            "operation_id": self.operation_id,
        }

    def apply(self, plan: dict[str, Any]) -> dict[str, Any]:
        """Apply the one write through the synthetic adapter; idempotent."""
        if plan.get("status") != "PLANNED":
            return {"status": "NOT_APPLIED", "reason": "plan not valid"}
        op = plan["operation_id"]
        if self._applied(op):
            return {
                "status": "ALREADY_APPLIED",
                "idempotent": True,
                "operation_id": op,
                "note": "stable operation id -> no duplicate write",
            }
        self._write_field(plan["field"], plan["target_value"])
        self._record_written(plan["field"], plan["target_value"])
        self._mark_applied(op)
        readback = self.readback(plan["field"], expected=plan["target_value"])
        return {
            "status": "APPLIED",
            "operation_id": op,
            "readback": readback,
            "simulated": True,
            "real_adapter_exercised": False,
        }

    def readback(self, path: str, expected: Any) -> dict[str, Any]:
        """Separate file value / runtime-effective / restart-needed."""
        file_value = self._read_field(path)
        ok = file_value == expected
        return {
            "file_value": file_value,
            "runtime_effective_value": file_value,  # in this synthetic scope the file IS the effective store
            "restart_needed_value": None,
            "status": "PASS" if ok else "DRIFT",
            "expected": expected,
        }

    def restore(self, path: str, prior_value: Any) -> dict[str, Any]:
        """Controlled restore: only when the value is still what we last wrote.

        If the field no longer equals the value THIS loop last applied, a
        concurrent user change happened — it is preserved, never overwritten
        blindly (NF-07 acceptance #2: concurrent modification is kept or
        surfaced as an explicit conflict, never a silent blind restore).
        """
        current = self._read_field(path)
        expected_current = self._last_written(path)
        if current != expected_current:
            raise FieldConflictRefused(
                f"concurrent change detected on {path!r} "
                f"(current={current!r} != last-written={expected_current!r}); "
                "blind restore refused, concurrent value preserved"
            )
        self._write_field(path, prior_value)
        self._record_written(path, prior_value)
        return {
            "status": "RESTORED",
            "field": path,
            "restored_value": prior_value,
            "simulated": True,
            "real_adapter_exercised": False,
        }


def honest_card_status(receipt: dict[str, Any], *, authorized_real_field: bool = False) -> dict[str, Any]:
    """NF-07 acceptance #3: no real adapter => the real-field card stays NOT-PASSED."""
    real = bool(receipt.get("real_adapter_exercised", False))
    return {
        "card": "NF-07",
        "mechanism_proven": receipt.get("status") in ("APPLIED", "ALREADY_APPLIED", "RESTORED"),
        "real_adapter_exercised": real,
        "real_field_authorized": authorized_real_field,
        "real_field_status": "PASS" if (real and authorized_real_field) else "NOT_PASSED_AWAITING_AUTHORIZATION",
        "note": (
            "controlled synthetic closed loop proves the mechanism; the real-field "
            "acceptance requires a concrete client/profile/field/operation "
            "authorization not granted in this round"
        ),
    }
