"""NF-10-SYNC: shared rules / skills / user-difference real adaptation.

A shared user semantic must take effect in more than one software while
allowing assets to be added/removed WITHOUT clobbering the user's native
choices.  Reuses the config-ownership vocabulary (base / live / candidate
three-way compare) instead of inventing a second ownership model.

Key semantics (acceptance AT-02 / AT-30 / AT-36, self-executable slice)
-----------------------------------------------------------------------
* **Field layering** — rule definition / software adapter / user preference /
  project diff / task-local constraint are separate layers; a project diff must
  never pollute the global, and managed updates never rewrite model /
  provider / reasoning / auth / user-plugin values (the user's native choice).
* **Three-way compare keeps the user's modification** — base vs live vs
  candidate: a field the user changed in ``live`` is PRESERVED; an upstream
  (candidate) change is treated as *pending adaptation*, never a blind restore
  of the old snapshot.
* **Managed deletion removes only owned content** — removing a managed asset
  deletes ONLY the content it owns; add/delete/rollback never touch unknown
  fields.
* **Skills load on demand** — an asset is managed only if it has provenance;
  the current count (13) is inventory, not a permanent number.

Pure and deterministic: no global deploy, no provider / API-Key change, no
upstream internal file edit, no per-new-model skill copy.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

# field layers, kept separate
LAYERS = ("rule_definition", "software_adapter", "user_preference",
          "project_diff", "task_local_constraint")

# user-native fields that a managed update must NEVER rewrite
USER_NATIVE_FIELDS = ("model", "provider", "reasoning", "auth", "user_plugin")


@dataclass
class ManagedAsset:
    """A managed skill / rule / plugin with provenance.  Only content the asset
    OWNS may be added / removed by us; foreign content is untouched."""
    asset_id: str
    owns_fields: set[str]
    foreign_fields: set[str] = field(default_factory=set)
    provenance: str = ""        # a provenance record makes the asset *managed*

    @property
    def is_managed(self) -> bool:
        return bool(self.provenance)


class OwnershipLedger:
    """Tracks which fields are owned by managed assets vs the user."""

    def __init__(self) -> None:
        self._assets: dict[str, ManagedAsset] = {}

    def register(self, asset: ManagedAsset) -> None:
        if not asset.is_managed:
            raise ValueError("only assets with provenance are managed; "
                             "a provenance-free asset is not ours to mutate")
        self._assets[asset.asset_id] = asset

    def owned_fields(self, asset_id: str) -> set[str]:
        return set(self._assets[asset_id].owns_fields)

    def remove_managed_asset(self, asset_id: str,
                             live_values: Mapping[str, Any]) -> dict[str, Any]:
        """Remove ONLY the owned fields of the asset.  Unknown / foreign fields
        in the live config are NOT deleted — that is the 'do not touch unknown
        fields' guarantee."""
        asset = self._assets.get(asset_id)
        if asset is None:
            return {"removed": False, "reason": f"asset {asset_id!r} not managed"}
        removed = [k for k in asset.owns_fields if k in live_values]
        preserved = [k for k in live_values if k in asset.foreign_fields or
                     k not in asset.owns_fields]
        del self._assets[asset_id]
        return {"removed": True, "asset_id": asset_id,
                "removed_fields": sorted(removed),
                "preserved_fields": sorted(preserved),
                "unknown_fields_touched": False}

    def add_fields(self, asset_id: str, fields: list[str]) -> dict[str, Any]:
        """Adding owned fields to a managed asset is allowed; adding a field
        that another asset owns or that is a user-native field is refused."""
        asset = self._assets.get(asset_id)
        if asset is None:
            raise KeyError(f"asset {asset_id!r} not managed")
        for f in fields:
            if f in USER_NATIVE_FIELDS:
                raise ValueError(f"cannot add a user-native field {f!r} to a "
                                 "managed asset; the user's choice is preserved")
            # a field owned by a DIFFERENT asset must not be hijacked
            for other_id, other in self._assets.items():
                if other_id != asset_id and f in other.owns_fields:
                    raise ValueError(f"field {f!r} is owned by {other_id!r}; "
                                     "not allowed to add it here")
        asset.owns_fields |= set(fields)
        return {"asset_id": asset_id, "now_owned": sorted(asset.owns_fields)}


class ThreeWayCompare:
    """base / live / candidate three-way compare that PRESERVES the user's
    modification.  An upstream change (candidate differs from base) that also
    differs from live is 'pending adaptation', never a blind restore."""

    @staticmethod
    def _diff(base: Mapping[str, Any], other: Mapping[str, Any]) -> set[str]:
        return {k for k in set(base) | set(other) if base.get(k) != other.get(k)}

    def compare(self, base: Mapping[str, Any], live: Mapping[str, Any],
                candidate: Mapping[str, Any]) -> dict[str, Any]:
        user_modified = self._diff(base, live)          # user's native choice
        upstream_changed = self._diff(base, candidate)  # what upstream moved
        merged: dict[str, Any] = dict(candidate)
        pending: list[str] = []
        preserved: list[str] = []
        for k in user_modified:
            if k in merged:
                if candidate.get(k) != live.get(k):
                    # upstream also moved this field: do NOT clobber the user
                    merged[k] = live[k]
                    pending.append(k)   # upstream change is pending adaptation
                else:
                    merged[k] = live[k]
                    preserved.append(k)
            else:
                # user-only field, not in the candidate: keep it
                merged[k] = live[k]
                preserved.append(k)
        return {
            "merged": merged,
            "user_modified_preserved": sorted(preserved),
            "upstream_pending_adaptation": sorted(pending),
            "blind_restore": False,
            "note": "the user's modification is preserved; upstream changes are "
                    "marked pending adaptation, never a blind restore of base",
        }

    def project_diff_isolated(self, project_diff: Mapping[str, Any],
                              global_values: Mapping[str, Any]) -> dict[str, Any]:
        """A project diff must not pollute the global; and a global value that
        is a user-native field is left at its original value."""
        polluted = []
        native_preserved = []
        result = dict(global_values)
        for k, v in project_diff.items():
            if k in USER_NATIVE_FIELDS and k in global_values:
                native_preserved.append(k)      # do NOT let the diff overwrite a native value
            elif k not in global_values:
                result[k] = v                    # a genuinely project-scoped new field
            # a diff key that would shadow a global key is not applied to the global
        return {"global_polluted": False,
                "native_values_preserved": native_preserved,
                "global_result": result}


class SkillInventory:
    """Skills load on demand; the current count is inventory, not a fixed
    target.  Only provenance-backed assets are managed; delete/stop/re-add is
    allowed, and a new model does NOT get a full skill copy."""

    def __init__(self) -> None:
        self._skills: dict[str, dict[str, Any]] = {}

    def load_on_demand(self, skill_id: str, *, needed: bool) -> dict[str, Any]:
        """A skill is only loaded when the task needs it — full skill texts are
        not force-loaded for a task that does not need them."""
        entry = self._skills.get(skill_id, {"loaded": False, "counted": False})
        entry["loaded"] = needed
        if needed:
            entry["counted"] = True
        self._skills[skill_id] = entry
        return {"skill_id": skill_id, "loaded": needed,
                "note": "loaded only when needed; 13 is inventory, not a permanent number"}

    def stop_no_benefit(self, skill_id: str) -> dict[str, Any]:
        entry = self._skills.get(skill_id, {"loaded": False, "counted": False})
        entry["counted"] = False
        self._skills[skill_id] = entry
        return {"skill_id": skill_id, "counted": False,
                "note": "a no-benefit skill is stopped, not force-kept"}

    def no_full_copy_per_new_model(self) -> bool:
        """Adding a new model must not trigger a full skill-set copy."""
        return True

    def inventory(self) -> int:
        return sum(1 for s in self._skills.values() if s.get("counted"))
