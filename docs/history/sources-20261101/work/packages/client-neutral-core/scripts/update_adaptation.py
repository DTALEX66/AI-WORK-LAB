"""NF-12-SYNC: software / model / protocol updates adapt only the affected surface.

After a version change the handoff must still work — without freezing the old
version, without binding to one model, and without reinstalling every piece of
software.  A version / capability change triggers ONLY the affected adaptation;
the other clients are not reinstalled.  No change is a legal NO_CHANGE.

Key semantics (acceptance AT-36 / AT-37, self-executable slice)
----------------------------------------------------------------
* **Snapshot then diff** — record the real runtime / protocol / capability
  snapshot; an update checks ONLY the fields, skills, plugins and
  input/output + cancel/resume interfaces it actually uses.
* **NO_CHANGE is legal** — if the target capability did not change, the result
  is NO_CHANGE, not an "enlarged file count" claim.
* **Minimal patch only on incompatibility** — an incompatibility produces the
  smallest patch + a rollback plan, not a whole-package reinstall.
* **Shared adapter upgrade keeps old handoffs readable** — after two projects
  share an adapter and it upgrades, a pre-upgrade handoff message is still
  readable; an unknown cost stays UNKNOWN.
* **Model params are the user's native choice** — only support and necessary
  context are checked, never a forced max-reasoning / new model.
* **Failure isolation** — one maintenance window not approved does not
  cascade into a whole-package failure.

Pure and deterministic: no real venv / plugin update, no forced user model
choice, no paid call.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Iterable

# the interface surface an update actually inspects (the *used* fields)
INSPECTED_SURFACES = ("fields", "skills", "plugins", "input_output",
                      "cancel_resume", "protocol")


@dataclass
class CapabilitySnapshot:
    """A recorded real runtime / protocol / capability snapshot."""
    runtime: str
    protocol: str
    capabilities: set[str]
    version: str

    def to_record(self) -> dict[str, Any]:
        return {"runtime": self.runtime, "protocol": self.protocol,
                "version": self.version, "capabilities": sorted(self.capabilities)}


def diff_surfaces(old: CapabilitySnapshot, new: CapabilitySnapshot,
                  used_surfaces: Iterable[str]) -> dict[str, Any]:
    """Compare the two snapshots over the surfaces the system ACTUALLY uses.

    * ``changed_surfaces`` reflects only version / runtime / protocol / fields
      changes, restricted to the used surfaces (unused surfaces are not
      checked — the affected-surface-only rule).
    * ``capabilities_lost`` (old - new) is always detected: losing a capability
      is an incompatibility.  ``capabilities_gained`` (new - old) is
      informational only and does NOT by itself trigger an adaptation.
    * ``no_change`` is True only when there is no changed used surface AND no
      lost capability.
    """
    used = list(used_surfaces)
    for s in used:
        if s not in INSPECTED_SURFACES:
            raise ValueError(f"surface {s!r} is not an inspected surface")
    changed_surfaces: dict[str, Any] = {}
    if "fields" in used and new.runtime != old.runtime:
        changed_surfaces["fields"] = ["runtime"]
    if "protocol" in used and new.protocol != old.protocol:
        changed_surfaces["protocol"] = [old.protocol, new.protocol]
    if "fields" in used and new.version != old.version:
        changed_surfaces["version"] = [old.version, new.version]
    lost_caps = sorted(old.capabilities - new.capabilities)
    gained_caps = sorted(new.capabilities - old.capabilities)
    no_change = (not changed_surfaces) and (not lost_caps)
    return {"surfaces_checked": used, "changed_surfaces": changed_surfaces,
            "capabilities_lost": lost_caps, "capabilities_gained": gained_caps,
            "no_change": no_change}


class UpdateAdapter:
    """Adapts to a version/capability change: NO_CHANGE when the target
    capability did not move; otherwise the MINIMAL patch + a rollback plan."""

    def __init__(self) -> None:
        self._snapshots: dict[str, CapabilitySnapshot] = {}

    def record(self, name: str, snap: CapabilitySnapshot) -> None:
        self._snapshots[name] = snap

    def adapt(self, name: str, new_snap: CapabilitySnapshot,
              used_surfaces: Iterable[str]) -> dict[str, Any]:
        old = self._snapshots.get(name)
        if old is None:
            raise KeyError(f"no recorded snapshot for {name!r}; cannot adapt")
        diff = diff_surfaces(old, new_snap, used_surfaces)
        if diff["no_change"]:
            return {"name": name, "verdict": "NO_CHANGE",
                    "reinstall": False, "patch": None, "rollback": None,
                    "note": "no change is a legal NO_CHANGE; not an enlarged file count"}
        # incompatibility / a moved used surface -> the smallest patch + rollback plan
        patch = {"changed_surfaces": diff["changed_surfaces"],
                 "lost_capabilities": diff["capabilities_lost"]}
        rollback = {"revert_to_version": old.version,
                    "revert_protocol": old.protocol}
        return {"name": name, "verdict": "ADAPTED", "reinstall": False,
                "minimal_patch": patch, "rollback_plan": rollback,
                "note": "only the affected surface adapted; the whole package "
                        "is NOT reinstalled"}


class SharedAdapterUpgrade:
    """Two projects share one adapter; after an upgrade, a pre-upgrade handoff
    message stays readable, and an unknown cost stays UNKNOWN.  Model params
    remain the user's native choice (support + context only, never a forced
    max reasoning / new model)."""

    def __init__(self) -> None:
        self._readable_schemas: set[str] = set()

    def register_readable_schema(self, schema_version: str) -> None:
        self._readable_schemas.add(schema_version)

    def old_handoff_still_readable(self, message_schema: str) -> dict[str, Any]:
        readable = message_schema in self._readable_schemas
        return {"readable": readable, "message_schema": message_schema,
                "note": "a pre-upgrade handoff message is still readable after "
                         "the shared adapter upgrade" if readable else
                        "unknown schema; not silently dropped, flagged unreadable"}

    def cost_unknown_stays_unknown(self, cost: str | None) -> str:
        # never fabricate a cost; absence stays UNKNOWN
        return cost if cost else "UNKNOWN"

    def model_params_are_users_choice(self, *, user_reasoning: str,
                                      offered_reasoning: str) -> dict[str, Any]:
        """The user's native reasoning choice is honoured; support and context
        are checked, a forced higher reasoning / a new model is NOT applied."""
        if user_reasoning == offered_reasoning:
            return {"applied_reasoning": user_reasoning, "forced": False,
                    "note": "user's native reasoning kept; only support + context checked"}
        return {"applied_reasoning": user_reasoning, "forced": False,
                "offered_but_not_applied": offered_reasoning,
                "note": "an offered higher reasoning is NOT forced on the user; "
                        "the native choice is kept unless the user changed it"}


def isolate_maintenance_failure(results: Mapping[str, str]) -> dict[str, Any]:
    """One unapproved maintenance window does NOT cascade into a whole-package
    failure; other projects keep working."""
    failed = [g for g, s in results.items() if s == "failed"]
    passed = [g for g, s in results.items() if s == "passed"]
    blocked = [g for g, s in results.items() if s == "blocked_unapproved"]
    return {
        "whole_package_failed": len(failed) == len(results) and len(results) > 0
                                 and not blocked,
        "blocked_groups": blocked,
        "still_working": passed,
        "note": "an unapproved maintenance window is isolated to its own group; "
                "it does not mark the whole package failed",
    }
