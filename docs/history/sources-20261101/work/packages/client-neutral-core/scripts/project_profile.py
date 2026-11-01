from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_registry(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema_version") != "workflow/project-profile-registry/v1":
        raise ValueError("unsupported profile registry")
    profiles = data.get("profiles")
    if not isinstance(profiles, list) or not profiles:
        raise ValueError("profiles are required")
    ids = [p.get("project", {}).get("id") for p in profiles]
    if any(not item for item in ids) or len(ids) != len(set(ids)):
        raise ValueError("profile ids must be unique")
    return data


def resolve_profile(registry: dict[str, Any], project_id: str) -> dict[str, Any]:
    matches = [p for p in registry["profiles"] if p.get("project", {}).get("id") == project_id]
    if len(matches) != 1:
        raise LookupError("project profile unavailable or ambiguous")
    profile = matches[0]
    if profile.get("project", {}).get("id") == "work-lab":
        observer = profile.get("modules", {}).get("work-lab-observer", {})
        if not observer.get("observation_only"):
            raise ValueError("observer profile must be read-only")
    return profile
