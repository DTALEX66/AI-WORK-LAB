from __future__ import annotations

import json
import sys
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_json(relative: str) -> dict:
    path = ROOT / relative
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def fail(message: str) -> None:
    print(f"FAIL: {message}")
    raise SystemExit(1)


def main() -> int:
    manifest = load_json("PACK_MANIFEST.json")
    phases = load_json("tasks/phases.json")
    cards = load_json("tasks/task-cards.json")

    missing = [name for name in manifest["required_files"] if not (ROOT / name).is_file()]
    if missing:
        fail(f"missing required files: {missing}")

    phase_items = phases.get("phases", [])
    task_items = cards.get("tasks", [])
    if len(phase_items) != manifest["active_phase_count"]:
        fail("phase count does not match manifest")
    if len(task_items) != manifest["active_task_count"]:
        fail("task count does not match manifest")
    if cards.get("task_count") != len(task_items):
        fail("task_count field does not match tasks array")
    drift = cards.get("drift_contract", {})
    if not drift.get("required") or drift.get("policy_file") != "06_PROJECT_DRIFT_CONTROL.md":
        fail("mandatory drift contract is missing")
    if not (ROOT / drift["policy_file"]).is_file():
        fail("drift policy file is missing")

    ids = [task.get("id") for task in task_items]
    if None in ids or len(ids) != len(set(ids)):
        fail("task ids are missing or duplicated")

    id_set = set(ids)
    phase_set = {phase["id"] for phase in phase_items}
    for task in task_items:
        if task.get("phase") not in phase_set:
            fail(f"unknown phase for {task['id']}")
        unknown = [dependency for dependency in task.get("depends_on", []) if dependency not in id_set]
        if unknown:
            fail(f"unknown dependencies for {task['id']}: {unknown}")
        if not task.get("gate") or not task.get("evidence"):
            fail(f"missing gate/evidence for {task['id']}")

    positions = {task_id: index for index, task_id in enumerate(ids)}
    for task in task_items:
        for dependency in task.get("depends_on", []):
            if positions[dependency] >= positions[task["id"]]:
                fail(f"dependency order is not acyclic for {task['id']}")

    legacy = ROOT / "legacy-source/OPEN-DESIGN-Assistance-Complete-TaskPack-v3.0.zip"
    if not zipfile.is_zipfile(legacy):
        fail("legacy V3 source is not a valid zip")
    with zipfile.ZipFile(legacy) as archive:
        names = archive.namelist()
        if not any(name.endswith("tasks/task-cards.json") for name in names):
            fail("legacy V3 task cards missing")
        overlay_files = [name for name in names if "/overlay/" in name and not name.endswith("/")]
        if len(overlay_files) < 199:
            fail(f"legacy overlay incomplete: {len(overlay_files)} files")

    print(f"PASS: {len(phase_items)} phases, {len(task_items)} active tasks, {len(overlay_files)} legacy overlay files")
    return 0


if __name__ == "__main__":
    sys.exit(main())
