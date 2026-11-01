#!/usr/bin/env python3
"""Read-only verifier for the OPEN-DESIGN-Assistance V4.1 task pack."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_json(path: Path, errors: list[str]):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # verifier must aggregate all readable failures
        errors.append(f"JSON_INVALID {path.relative_to(ROOT)}: {exc}")
        return None


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> int:
    errors: list[str] = []
    manifest_path = ROOT / "PACK_MANIFEST.json"
    phases_path = ROOT / "tasks" / "phases.json"
    tasks_path = ROOT / "tasks" / "task-cards.json"

    for required in (
        ROOT / "00_START_HERE.md",
        ROOT / "01_MASTER_HERMES_TASKPACK.md",
        ROOT / "02_CLOUD_DRIFT_AUDIT_20260808.md",
        manifest_path,
        phases_path,
        tasks_path,
        ROOT / "RUN_FIRST.ps1",
    ):
        if not required.is_file():
            errors.append(f"MISSING {required.relative_to(ROOT)}")

    manifest = load_json(manifest_path, errors) if manifest_path.is_file() else None
    phases_doc = load_json(phases_path, errors) if phases_path.is_file() else None
    tasks_doc = load_json(tasks_path, errors) if tasks_path.is_file() else None

    phases = phases_doc.get("phases", []) if isinstance(phases_doc, dict) else []
    tasks = tasks_doc.get("tasks", []) if isinstance(tasks_doc, dict) else []
    phase_ids = {phase.get("id") for phase in phases if isinstance(phase, dict)}
    task_ids = [task.get("id") for task in tasks if isinstance(task, dict)]
    task_id_set = set(task_ids)

    if isinstance(tasks_doc, dict) and tasks_doc.get("task_count") != len(tasks):
        errors.append(
            f"TASK_COUNT declared={tasks_doc.get('task_count')} actual={len(tasks)}"
        )
    if len(task_ids) != len(task_id_set):
        errors.append("DUPLICATE_TASK_ID")

    if isinstance(manifest, dict):
        package = manifest.get("package", {})
        if package.get("phase_count") != len(phases):
            errors.append(
                f"MANIFEST_PHASE_COUNT declared={package.get('phase_count')} actual={len(phases)}"
            )
        if package.get("task_count") != len(tasks):
            errors.append(
                f"MANIFEST_TASK_COUNT declared={package.get('task_count')} actual={len(tasks)}"
            )

    correction_ids = {
        f"ODA4-01{number:02d}" for number in range(10, 19)
    }
    missing_corrections = sorted(correction_ids - task_id_set)
    if missing_corrections:
        errors.append(f"MISSING_V4_1_CORRECTION_TASKS {missing_corrections}")

    for task in tasks:
        task_id = task.get("id")
        if not isinstance(task_id, str) or not task_id.startswith("ODA4-"):
            errors.append(f"BAD_TASK_ID {task_id!r}")
        if task.get("phase") not in phase_ids:
            errors.append(f"UNKNOWN_PHASE {task_id}: {task.get('phase')}")
        for dependency in task.get("dependencies", []):
            if dependency not in task_id_set:
                errors.append(f"MISSING_DEPENDENCY {task_id}: {dependency}")
        for field in (
            "title",
            "priority",
            "risk",
            "actor",
            "allowed_paths",
            "outputs",
            "acceptance",
            "verification",
            "required_evidence",
        ):
            if field not in task:
                errors.append(f"MISSING_FIELD {task_id}: {field}")

    dependencies_by_task = {
        task.get("id"): task.get("dependencies", [])
        for task in tasks
        if isinstance(task, dict) and isinstance(task.get("id"), str)
    }
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(task_id: str, chain: list[str]) -> None:
        if task_id in visited:
            return
        if task_id in visiting:
            errors.append(f"DEPENDENCY_CYCLE {' -> '.join(chain + [task_id])}")
            return
        visiting.add(task_id)
        for dependency in dependencies_by_task.get(task_id, []):
            if dependency in dependencies_by_task:
                visit(dependency, chain + [task_id])
        visiting.remove(task_id)
        visited.add(task_id)

    for task_id in task_ids:
        if isinstance(task_id, str):
            visit(task_id, [])

    checked_hashes = 0
    if isinstance(manifest, dict):
        for entry in manifest.get("files", []):
            relative = entry.get("path")
            expected = entry.get("sha256")
            if not relative or not expected:
                errors.append(f"BAD_MANIFEST_ENTRY {entry!r}")
                continue
            target = ROOT / relative
            if not target.is_file():
                errors.append(f"MANIFEST_MISSING {relative}")
                continue
            actual = sha256(target)
            checked_hashes += 1
            if actual != expected:
                errors.append(
                    f"HASH_MISMATCH {relative}: expected={expected} actual={actual}"
                )

    print(f"PHASES={len(phases)}")
    print(f"TASKS={len(tasks)}")
    print(f"HASHES_CHECKED={checked_hashes}")
    print(f"ERRORS={len(errors)}")
    for error in errors:
        print(error)

    if errors:
        print("VERIFY_TASKPACK=FAIL")
        return 1
    print("VERIFY_TASKPACK=OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
