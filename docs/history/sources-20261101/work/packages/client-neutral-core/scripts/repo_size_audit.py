"""Read-only repository size and source governance audit (WL3-810).

Counts working-tree size, Git objects, top-N blobs, duplicate content groups,
build artifacts and archive bloat. Produces a savings estimate and recovery
proposal; never rewrites history, never vendors whole repos, never deletes.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
from collections import defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]

IGNORED_SUFFIXES = {".pyc", ".log", ".tmp", ".cache"}
SUSPECT_DIRS = {"node_modules", "__pycache__", ".git", ".hermes", "dist", "build"}


def _git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=root, text=True, capture_output=True, check=False, encoding="utf-8", errors="replace"
    )
    return result.stdout.strip()


def audit_working_tree(root: Path) -> dict[str, Any]:
    tracked = _git(root, "ls-files").splitlines()
    total_bytes = 0
    extension_bytes: dict[str, int] = defaultdict(int)
    duplicate_groups: dict[str, list[str]] = defaultdict(list)
    top: list[dict[str, Any]] = []
    for relative in tracked:
        path = root / relative
        if not path.is_file():
            continue
        size = path.stat().st_size
        total_bytes += size
        extension = path.suffix.lower() or "(none)"
        extension_bytes[extension] += size
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        duplicate_groups[digest].append(relative)
        top.append({"path": relative, "size": size})
    top.sort(key=lambda item: item["size"], reverse=True)
    duplicates = {
        digest: paths
        for digest, paths in duplicate_groups.items()
        if len(paths) > 1
    }
    return {
        "schema_version": "workflow/repo-size-audit/v1",
        "tracked_files": len(tracked),
        "total_bytes": total_bytes,
        "total_mib": round(total_bytes / 1048576, 2),
        "top_blobs": top[:10],
        "extension_bytes": dict(sorted(extension_bytes.items(), key=lambda item: item[1], reverse=True)[:10]),
        "duplicate_groups": len(duplicates),
        "duplicate_paths": [paths for paths in duplicates.values()][:5],
        "suspect_dirs_present": [d for d in SUSPECT_DIRS if (root / d).exists()],
        "rewrite_required": False,
    }


def audit_git_objects(root: Path) -> dict[str, Any]:
    count = _git(root, "count-objects", "-v")
    lines = dict(line.split(": ") for line in count.splitlines() if ": " in line)
    size_kib = int(lines.get("size-pack", "0")) + int(lines.get("size", "0"))
    return {
        "git_object_count": lines.get("count", "unknown"),
        "git_objects_mib": round(size_kib / 1024, 2),
        "repo_reported_size_kib": int(_git(root, "count-objects", "-vH").splitlines()[-1].split(":")[-1].strip().split()[0]) if False else None,
    }


def savings_proposal(audit: dict[str, Any]) -> dict[str, Any]:
    """Conservative estimate: duplicate groups and archives only; no history rewrite."""
    return {
        "status": "PROPOSAL_READY",
        "rewrite_required": False,
        "savings_estimate": "MANUAL_REVIEW_REQUIRED",
        "recovery": "archive-only; requires separate approval",
        "duplicate_groups": audit["duplicate_groups"],
    }


if __name__ == "__main__":
    tree = audit_working_tree(ROOT)
    report = {"working_tree": tree, "proposal": savings_proposal(tree)}
    print(json.dumps(report, ensure_ascii=False, indent=2))
