"""Deterministic, credential-free platform identity resolution.

The resolver consumes already-discovered metadata. It never scans private state,
reads credentials, or chooses a configuration root on ambiguity.
"""
from __future__ import annotations

from dataclasses import dataclass
from collections import Counter, defaultdict
from typing import Any, Iterable

STATES = {
    "UNIQUE", "ALIAS_DUPLICATE", "STALE_SHORTCUT", "CONFIG_SPLIT",
    "VERSION_COLLISION", "DUAL_INSTALLATION", "PROFILE_SPLIT",
    "IDENTITY_AMBIGUOUS", "UNAVAILABLE",
}


def _key(item: dict[str, Any]) -> tuple[str, str, str]:
    return (
        str(item.get("package_identity", "")),
        str(item.get("executable_realpath", "")),
        str(item.get("binary_digest", "")),
    )


def _state(items: list[dict[str, Any]]) -> str:
    if not items:
        return "UNAVAILABLE"
    if any(item.get("freshness") == "STALE" for item in items):
        return "STALE_SHORTCUT"
    configs = {str(item.get("effective_config_root", "")) for item in items}
    profiles = {str(item.get("profile_id", "")) for item in items}
    versions = {str(item.get("discovered_version", "")) for item in items}
    binaries = {_key(item) for item in items}
    if len(configs) > 1 and len(binaries) == 1:
        return "CONFIG_SPLIT"
    if len(profiles) > 1 and len(binaries) == 1:
        return "PROFILE_SPLIT"
    if len(versions) > 1 and len(binaries) == 1:
        return "VERSION_COLLISION"
    if len(binaries) > 1:
        return "DUAL_INSTALLATION"
    if len({str(item.get("launcher_id", "")) for item in items}) > 1:
        return "ALIAS_DUPLICATE"
    return "UNIQUE"


def resolve_identity(observations: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """Return stable logical identities and fail-closed state classifications."""
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for raw in observations:
        item = dict(raw)
        logical = str(item.get("logical_instance_id", "")).strip()
        if logical:
            groups[logical].append(item)
    identities = []
    for logical in sorted(groups):
        items = groups[logical]
        state = _state(items)
        canonical = dict(sorted(items, key=lambda item: (
            str(item.get("package_identity", "")),
            str(item.get("executable_realpath", "")),
            str(item.get("launcher_id", "")),
        ))[0])
        canonical["state"] = state
        canonical["logical_instance_id"] = logical
        canonical["launcher_ids"] = sorted({str(i.get("launcher_id", "")) for i in items if i.get("launcher_id")})
        canonical["observation_count"] = len(items)
        canonical["alias_count"] = len({str(i.get("launcher_target", "")) for i in items})
        identities.append(canonical)
    return {"schema_version": "workflow/platform-identity/v1", "identities": identities, "identity_count": len(identities), "ambiguous_count": sum(i["state"] != "UNIQUE" for i in identities)}
