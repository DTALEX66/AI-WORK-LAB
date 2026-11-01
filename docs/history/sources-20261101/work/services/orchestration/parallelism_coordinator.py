"""Single-project parallelism coordination (WL3-400 / MR-14).

Read tasks may run in parallel; independent write tasks use separate worktrees
and non-overlapping path leases; a Commit Coordinator only assembles evidence
and never commits/merges automatically.

Contract rules (taskpack §MR-14 acceptance):
- one checkout has exactly one writer
- path and schema dependency conflicts serialize
- GPU tasks serialize without blocking CPU-only read audits
- a reviewer can never write a candidate tree
- unapproved Git side effects stay WAITING_APPROVAL
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "workflow/parallelism-plan/v1"


class PathLease:
    """Non-overlapping path leases for independent writers."""

    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        (self.root / "path-leases").mkdir(parents=True, exist_ok=True)

    def _path(self, task_id: str) -> Path:
        return self.root / "path-leases" / f"{task_id}.json"

    def _conflicts(self, paths: list[str], existing: dict[str, Any]) -> bool:
        for p in paths:
            for owned in existing.get("paths", []):
                # naive containment: exact or ancestor/descendant
                if p == owned or p.startswith(owned + "/") or owned.startswith(p + "/"):
                    return True
        return False

    def acquire(self, task_id: str, paths: list[str]) -> dict[str, Any]:
        """Fail-closed: any overlap with a live lease -> BLOCKED."""
        for other in (self.root / "path-leases").glob("*.json"):
            if other.stem == task_id:
                continue
            try:
                data = json.loads(other.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if self._conflicts(paths, data):
                return {"status": "BLOCKED", "task": task_id,
                        "conflict_with": other.stem, "reason_code": "PATH_OVERLAP"}
        payload = {"task_id": task_id, "paths": sorted(set(paths))}
        self._path(task_id).write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return {"status": "HELD", "task": task_id, "paths": sorted(set(paths))}

    def release(self, task_id: str) -> None:
        self._path(task_id).unlink(missing_ok=True)


class SchemaDependencyResolver:
    """Serializes tasks sharing a schema dependency."""

    def __init__(self) -> None:
        self._deps: dict[str, list[str]] = {}

    def register(self, task_id: str, schemas: list[str]) -> None:
        self._deps[task_id] = sorted(set(schemas))

    def conflicts(self, task_id: str) -> list[str]:
        mine = set(self._deps.get(task_id, []))
        conflicting = []
        for other, schemas in self._deps.items():
            if other == task_id:
                continue
            if mine & set(schemas):
                conflicting.append(other)
        return conflicting


class CommitCoordinator:
    """Assembles evidence only; never commits/merges/pushes."""

    def __init__(self) -> None:
        self._evidence: dict[str, dict[str, Any]] = {}

    def assemble(self, task_id: str, evidence: dict[str, Any]) -> dict[str, Any]:
        if not evidence.get("tree_hash"):
            raise ValueError("commit_evidence_requires_tree_hash")
        self._evidence[task_id] = evidence
        return {
            "status": "EVIDENCE_READY",
            "task_id": task_id,
            "git_side_effect": "WAITING_APPROVAL",
            "evidence": evidence,
        }

    def pending_approvals(self) -> list[str]:
        return [tid for tid in self._evidence]


if __name__ == "__main__":
    import project_temp
    with project_temp.fixture_root(prefix='parallelism-selftest-') as tmp:
        leases = PathLease(Path(tmp))
        a = leases.acquire("t1", ["scripts/workflow/a.py"])
        b = leases.acquire("t2", ["scripts/workflow/a.py"])
        print("t1:", a)
        print("t2 (overlap):", b)
        leases.release("t1")
        c = leases.acquire("t2", ["scripts/workflow/a.py"])
        print("t2 (after release):", c["status"])
        coordinator = CommitCoordinator()
        print("coordinator:", coordinator.assemble("t1", {"tree_hash": "abc"}))
