"""Three-way configuration coordinator (WL3-210).

Discover actual -> classify ownership -> compare previous upstream / new
upstream / user overlay -> ActionPlan -> approval when required -> narrow apply
through stable official interface -> readback -> rollback or evidence commit.

Apply is approval-gated and intentionally not invoked here; this module only
produces plans and readback/rollback evidence for already-applied overlays.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

UNKNOWN_DEFAULT = {
    "mode": "OBSERVE",
    "layer": "USER_OVERLAY",
    "adapter": None,
    "apply_supported": False,
    "quarantine": True,
}
NON_PATCH_MODES = {"OBSERVE", "IGNORE", "FORBIDDEN"}


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def classify_field(rule: dict[str, Any] | None) -> dict[str, Any]:
    if not rule:
        return dict(UNKNOWN_DEFAULT)
    return {
        "mode": str(rule.get("mode", "OBSERVE")),
        "layer": str(rule.get("layer", rule.get("owner", "USER_OVERLAY"))),
        "adapter": rule.get("adapter"),
        "apply_supported": bool(rule.get("apply_supported", True)),
        "quarantine": (
            rule.get("layer") == "SECRET"
            or rule.get("mode") in NON_PATCH_MODES
            or not bool(rule.get("apply_supported", True))
        ),
    }


def three_way_compare(
    ownership_registry: dict[str, Any],
    *,
    previous_upstream: dict[str, Any],
    new_upstream: dict[str, Any],
    user_overlay: dict[str, Any],
    identity_apply_allowed: bool,
    machine_identity: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Emit a discovery-first, machine-scoped, minimum-write ActionPlan.

    Existing machine values are evidence of user intent, including values for
    otherwise managed fields.  They are preserved rather than silently reset
    to a repository default.  The coordinator therefore only exposes a write
    set for a declared MANAGE field that is absent from the machine overlay and
    differs between the old and new official baselines.
    """
    declared = {item["path"]: item for item in ownership_registry.get("fields", [])}
    paths = sorted(set(previous_upstream) | set(new_upstream) | set(user_overlay))
    fields: list[dict[str, Any]] = []
    for path in paths:
        old = previous_upstream.get(path)
        new = new_upstream.get(path)
        has_user_value = path in user_overlay
        if old == new and not has_user_value:
            continue  # no drift, no overlay
        rule = declared.get(path)
        classification = classify_field(rule)
        if has_user_value and old != new:
            # Keep the machine's intent. Reconciliation needs explicit human
            # review, but it is not an authorization to overwrite it.
            change = "UPSTREAM_CHANGED_WITH_OVERLAY"
            action = "QUARANTINE" if classification["quarantine"] else "PRESERVE"
        elif has_user_value:
            change = "USER_OVERLAY"
            action = "QUARANTINE" if classification["quarantine"] else "PRESERVE"
        elif old != new:
            change = "UPSTREAM_CHANGED"
            action = (
                "PATCH"
                if classification["mode"] == "MANAGE" and classification["apply_supported"]
                else "QUARANTINE"
            )
        else:
            change = "UNCHANGED"
            action = "NONE"
        field = {
            "path": path,
            "layer": classification["layer"],
            "mode": classification["mode"],
            "change": change,
            "action": action,
            "adapter": classification["adapter"],
            "apply_supported": classification["apply_supported"],
        }
        # Never put user-, unknown-, or secret-owned values into an ActionPlan.
        # The path/classification is enough to review an exclusion safely.
        if action == "PATCH":
            field["previous_upstream"] = old
            field["new_upstream"] = new
        fields.append(field)
    patchable = [f for f in fields if f["action"] == "PATCH"]
    quarantined = [f for f in fields if f["action"] == "QUARANTINE"]
    preserved = [f for f in fields if f["action"] == "PRESERVE"]
    write_set = [f["path"] for f in patchable]
    machine_discovered = bool(machine_identity and machine_identity.get("machine_id") and machine_identity.get("config_scope"))
    if not write_set:
        status = "NOOP"
    elif not machine_discovered:
        status = "WAITING_MACHINE_DISCOVERY"
    else:
        status = "WAITING_APPROVAL"
    apply_allowed = identity_apply_allowed and machine_discovered and bool(write_set) and not quarantined
    return {
        "schema_version": "workflow/config-action-plan/v1",
        "status": status,
        "machine_identity": machine_identity if machine_discovered else None,
        "identity_apply_allowed": identity_apply_allowed,
        "approval_required": bool(write_set),
        "apply_allowed": apply_allowed,
        "write_set": write_set,
        "patchable_fields": write_set,
        "preserved_fields": [f["path"] for f in preserved],
        "quarantined_fields": [f["path"] for f in quarantined],
        "rollback": {"required": bool(write_set), "strategy": "backup-cas-readback-rollback"},
        "fields": fields,
    }


def overlay_digest(values: dict[str, Any]) -> str:
    """Stable digest over the overlay for CAS and readback evidence."""
    encoded = json.dumps(values, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def readback_overlay(path: Path, expected_digest: str) -> dict[str, Any]:
    """Read back an applied overlay and verify it matches the recorded digest."""
    if not path.is_file():
        return {"status": "MISSING", "expected_digest": expected_digest}
    values = _load_json(path)
    actual = overlay_digest(values)
    return {
        "status": "PASS" if actual == expected_digest else "DRIFT",
        "expected_digest": expected_digest,
        "actual_digest": actual,
        "values": values,
    }


def rollback_plan(plan: dict[str, Any], backup: dict[str, Any] | None) -> dict[str, Any]:
    """Fenced rollback plan: only actually planned writes, from the backup."""
    if not backup:
        return {"status": "NO_BACKUP", "apply": False}
    paths = set(plan.get("write_set", []))
    restore = [p for p in sorted(paths) if p in backup]
    return {
        "schema_version": "workflow/config-rollback-plan/v1",
        "status": "READY" if restore else "NOOP",
        "apply": bool(restore),
        "restore_fields": restore,
        "strategy": "recorded-ownership-hash-fenced",
    }
