"""Project platform observation collector (WL-DSH / Observer redesign).

Reads the project->platform map (config/project-platform-map.json) and records
each project's primary platform into the canonical platform_observations table.
Observer consumes this to show "which project runs on which platform".

Read-only with respect to projects: never touches project content, never
writes outside canonical.sqlite, never routes anything.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]  # workflow-assistance/
CONFIG_PATH = ROOT / "config" / "project-platform-map.json"


def collect_platform_observations(store: Any, project_id: str):
    """CollectorFn-compatible: record project platform facts into canonical store."""
    from durable_worker import CollectorResult

    if not CONFIG_PATH.exists():
        return CollectorResult(kind="platform", ok=False,
                               error=f"platform map missing: {CONFIG_PATH}")
    try:
        data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception as e:
        return CollectorResult(kind="platform", ok=False, error=f"parse failed: {e}")

    projects = data.get("projects", [])
    records = []
    for entry in projects:
        platform = entry.get("primaryPlatform") or (entry.get("platforms") or [None])[0]
        if not platform:
            continue
        payload = {
            "displayName": entry.get("displayName"),
            "primaryPlatform": platform,
            "platforms": entry.get("platforms", [platform]),
            "note": entry.get("note", ""),
        }
        records.append({
            "project_id": entry.get("projectId"),
            "platform": platform,
            "payload": json.dumps(payload, ensure_ascii=False),
        })
    if not records:
        return CollectorResult(kind="platform", ok=False, error="no projects in map")

    try:
        store.record_platform_observations(records)
        return CollectorResult(kind="platform", ok=True, records=records)
    except Exception as e:
        return CollectorResult(kind="platform", ok=False, error=str(e))


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from canonical_store import CanonicalStore
    import project_temp
    import shutil

    tmp = project_temp.fixture_dir(prefix="platform-collector-")
    assert project_temp.inside_project(tmp), f"fixture escaped the project root: {tmp}"
    store = None
    try:
        store = CanonicalStore(tmp / "canonical.sqlite")
        result = collect_platform_observations(store, "work-lab")
        print("ok:", result.ok, "records:", len(result.records), "error:", result.error)
        rows = store.query_platform_observations()
        print("stored:", len(rows))
        for r in rows[:5]:
            print("  ", r.get("project_id"), "->", r.get("platform"))
    finally:
        if store is not None:
            store.close()
        shutil.rmtree(tmp)
        print(f"RESIDUE_CLEANED {tmp}")
