"""Fail-closed canonical package/launcher/config/profile reconciliation."""
from __future__ import annotations

from typing import Any, Iterable


AMBIGUOUS = {"ALIAS_DUPLICATE", "STALE_SHORTCUT", "CONFIG_SPLIT", "VERSION_COLLISION", "DUAL_INSTALLATION", "PROFILE_SPLIT", "IDENTITY_AMBIGUOUS", "UNAVAILABLE"}


def reconcile(identity_projection: dict[str, Any]) -> dict[str, Any]:
    """Build a read-only canonical chain; never select a config on conflict."""
    chains = []
    for item in identity_projection.get("identities", []):
        state = str(item.get("state", "UNAVAILABLE"))
        chains.append({
            "logical_instance_id": item.get("logical_instance_id"),
            "package": item.get("package_identity"),
            "executable": item.get("executable_realpath"),
            "launchers": item.get("launcher_ids", []),
            "config_root": item.get("effective_config_root") if state not in AMBIGUOUS else None,
            "profile_id": item.get("profile_id") if state not in AMBIGUOUS else None,
            "state": state,
            "apply_allowed": state not in AMBIGUOUS and state == "UNIQUE",
            "quarantine_plan": state in {"ALIAS_DUPLICATE", "STALE_SHORTCUT"},
        })
    return {
        "schema_version": "workflow/canonical-reconciliation/v1",
        "chains": chains,
        "apply_allowed": bool(chains) and all(chain["apply_allowed"] for chain in chains),
    }


def compare(previous: dict[str, Any], current: dict[str, Any]) -> dict[str, Any]:
    """Return deterministic drift classes without selecting a winner."""
    fields = ("package", "executable", "config_root", "profile_id", "state")
    changes = []
    before = {x.get("logical_instance_id"): x for x in previous.get("chains", [])}
    after = {x.get("logical_instance_id"): x for x in current.get("chains", [])}
    for key in sorted(set(before) | set(after)):
        if key not in before:
            changes.append({"logical_instance_id": key, "change": "ADDED"})
        elif key not in after:
            changes.append({"logical_instance_id": key, "change": "REMOVED"})
        else:
            changed = [field for field in fields if before[key].get(field) != after[key].get(field)]
            if changed:
                changes.append({"logical_instance_id": key, "change": "DRIFT", "fields": changed})
    return {"schema_version": "workflow/canonical-reconciliation/v1", "changes": changes, "safe_to_apply": not any(c.get("change") == "DRIFT" and "state" in c.get("fields", []) for c in changes)}
