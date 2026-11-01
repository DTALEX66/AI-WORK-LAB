"""Cross-project registry and minimal Project Profile (WL3-420).

Discovers candidate Git projects under a configured root, registers them in the
canonical SQLite store, and maintains a tiny project profile per project. The
profile stays minimal (root resolution, allowed/forbidden paths, gate IDs, CI
identity, release policy, namespaces, data-source capabilities). WORK-LAB never
copies its runtime or rules into external projects; standalone fallback keeps
external projects usable when WORK-LAB is unavailable.
"""
from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator

from canonical_store import CanonicalStore

PROFILE_SCHEMA_VERSION = "workflow/project-profile/v1"
DEFAULT_FORBIDDEN = {"E:\\", "F:\\", "C:\\Windows", "C:\\Program Files"}
GIT_HEAD_RE = re.compile(r"^[0-9a-f]{40}$")
GIT_ROOT_RE = re.compile(r"^([A-Za-z]:[\\/].*)$")


@dataclass
class DiscoveredProject:
    project_id: str
    root: Path
    git_root: bool
    head_sha: str | None
    dirty_count: int
    has_work_lab_manifest: bool
    profile: dict[str, Any] = field(default_factory=dict)


def _git(root: Path, *args: str) -> str | None:
    try:
        result = subprocess.run(
            ["git", *args], cwd=root, text=True, encoding="utf-8", errors="replace", capture_output=True, check=False, timeout=30
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return result.stdout.strip() if result.returncode == 0 else None


def is_git_root(path: Path) -> bool:
    """True only when the path is the top level of a Git work tree.

    ``--is-inside-work-tree`` returns true for any directory inside a repo
    (including temporary dirs under a repo's ignored runtime path), so we must
    compare ``--show-toplevel`` against the candidate path itself.
    """
    top_level = _git(path, "rev-parse", "--show-toplevel")
    if not top_level:
        return False
    try:
        return Path(top_level).resolve() == path.resolve()
    except OSError:
        return False


def discover_git_projects(search_root: Path, max_depth: int = 2) -> list[DiscoveredProject]:
    """Find candidate Git repositories without scanning whole disks."""
    discovered: list[DiscoveredProject] = []
    if not search_root.is_dir():
        return discovered
    queue: list[tuple[Path, int]] = [(search_root, 0)]
    while queue:
        current, depth = queue.pop(0)
        if depth > max_depth:
            continue
        if is_git_root(current):
            discovered.append(_inspect(current))
            continue  # do not descend into a repo
        try:
            entries = sorted(current.iterdir())
        except OSError:
            continue
        for entry in entries:
            if entry.is_dir() and not entry.name.startswith((".", "$")):
                queue.append((entry, depth + 1))
    return discovered


def _inspect(root: Path) -> DiscoveredProject:
    head = _git(root, "rev-parse", "HEAD")
    if not head or not GIT_HEAD_RE.match(head):
        head = None
    dirty_raw = _git(root, "status", "--porcelain=v1")
    dirty = len([line for line in (dirty_raw or "").splitlines() if line.strip()])
    manifest = root / "workflow-manifest.yaml"
    project_id = root.name.lower().replace(" ", "-")
    return DiscoveredProject(
        project_id=project_id,
        root=root,
        git_root=True,
        head_sha=head,
        dirty_count=dirty,
        has_work_lab_manifest=manifest.is_file(),
    )


def build_minimal_profile(project: DiscoveredProject) -> dict[str, Any]:
    """Minimal, secret-free project profile for the canonical registry."""
    return {
        "schema_version": PROFILE_SCHEMA_VERSION,
        "project_id": project.project_id,
        "root_resolution": str(project.root.resolve()),
        "git_head_sha": project.head_sha,
        "dirty_count": project.dirty_count,
        "allowed_paths": [str(project.root.resolve())],
        "forbidden_paths": list(DEFAULT_FORBIDDEN),
        "gate_ids": ["work-lab-gate"] if project.has_work_lab_manifest else [],
        "ci_identity": {"workflow": "work-lab-gate"} if project.has_work_lab_manifest else {},
        "release_policy": "EXPLICIT_APPROVAL",
        "rule_namespace": f"{project.project_id}/rules",
        "skill_namespace": f"{project.project_id}/skills",
        "memory_namespace": f"{project.project_id}/memory",
        "data_source_capabilities": ["git-status", "git-head", "git-dirty"],
        "standalone_fallback": True,
        "work_lab_runtime_copied": False,
    }


def register_discovered(store: CanonicalStore, project: DiscoveredProject) -> dict[str, Any]:
    profile = build_minimal_profile(project)
    store.register_project(
        project.project_id,
        str(project.root.resolve()),
        display_name=project.root.name,
    )
    return profile


def discover_and_register(store: CanonicalStore, search_root: Path, max_depth: int = 2) -> list[dict[str, Any]]:
    """Discover Git projects and register them; returns registered profiles."""
    profiles: list[dict[str, Any]] = []
    for project in discover_git_projects(search_root, max_depth=max_depth):
        profile = register_discovered(store, project)
        profiles.append(profile)
    return profiles


def load_project_profiles(store: CanonicalStore) -> dict[str, dict[str, Any]]:
    """Read registered projects back from the canonical store."""
    result: dict[str, dict[str, Any]] = {}
    for project in store.list_projects():
        result[project["project_id"]] = {
            "project_id": project["project_id"],
            "root_path": project["root_path"],
            "display_name": project["display_name"],
            "status": project["status"],
        }
    return result


if __name__ == "__main__":
    import argparse
    from project_temp import require_runtime_root

    parser = argparse.ArgumentParser(description="Discover and register Git projects")
    parser.add_argument("--search-root", type=Path, required=True)
    parser.add_argument("--runtime-root", type=Path)
    parser.add_argument("--max-depth", type=int, default=2)
    args = parser.parse_args()
    runtime_root = require_runtime_root(args.runtime_root, "workflow-assistance-registry")
    store = CanonicalStore(runtime_root / "canonical.sqlite")
    try:
        profiles = discover_and_register(store, args.search_root, max_depth=args.max_depth)
        print(json.dumps(
            {
                "registered": len(profiles),
                "profiles": profiles,
                "integrity": store.integrity_check(),
            },
            ensure_ascii=False,
            indent=2,
        ))
    finally:
        store.close()
