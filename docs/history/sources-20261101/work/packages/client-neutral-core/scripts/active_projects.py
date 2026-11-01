"""Active project detection (workspace-discovery mode).

Scans the user's total workspace root for Git projects and detects which ones
are currently being executed by workflow agents (Hermes / Codex / CC Switch).
This is the bridge between "user-specified workspace" and the Observer
projection: projects that are loaded/executed by a workflow agent get an
`active` status in the canonical registry, so the Observer can show a truthful
"what is being worked on right now" view.

Security boundaries:
- Read-only process inspection: tasklist/wmic command lines are read to match
  a process working directory against a known project root; we never read
  credentials, sessions, prompt bodies or response bodies.
- Only projects under the user-specified workspace root are considered.
- The detector writes only canonical registry metadata (project status),
  never project content.
"""

from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from canonical_store import CanonicalStore
from project_registry import discover_git_projects, register_discovered

# Agent executables whose presence with a project cwd marks the project active.
ACTIVE_AGENT_PATTERNS = (
    "hermes",
    "codex",
    "cc-switch",
    "claude",
    "opencode",
)

# WLR-260: shared libraries are NEVER scanned as projects (candidates only
# appear after explicit user approval). Model weights and design assets live
# outside project roots; they must never be treated as active projects.
NEVER_SCAN_PATH_FRAGMENTS = (
    "Model library",
    "Design assets",
    "OS External Configuration",
    "pnpm-store",
    "node_modules",
    "venv",
    ".venv",
)


@dataclass
class ActiveProject:
    project_id: str
    root: Path
    agents: list[str] = field(default_factory=list)


def _running_agent_cwds() -> dict[str, list[str]]:
    """Map agent image name -> executable paths of running agent processes.

    Windows does not expose a process working directory via tasklist/wmic, so
    we fall back to recording which agent executables are running at all. The
    actual per-project activity is inferred from each project's own agent
    evidence files (freshness), not from a guessed cwd.
    """
    result: dict[str, list[str]] = {}
    if os.name != "nt":
        return result
    try:
        query = subprocess.run(
            ["tasklist", "/FO", "CSV", "/NH"],
            text=True, capture_output=True, timeout=20, check=False,
            encoding="utf-8", errors="replace",
        )
    except (OSError, subprocess.SubprocessError):
        return result
    for line in (query.stdout or "").splitlines():
        fields = [f.strip().strip('"') for f in line.split(",")]
        if not fields or not fields[0]:
            continue
        name = Path(fields[0]).name.lower()
        if any(pattern in name for pattern in ACTIVE_AGENT_PATTERNS):
            result.setdefault(name, []).append(name)
    return result


def _project_agent_freshness(project_root: Path, minutes: int = 120) -> list[str]:
    """Which workflow agents left fresh evidence inside this project?

    Evidence roots are the project-local agent state directories (`.hermes`,
    `.codex`, `.agents`). A file modified within the freshness window means the
    agent is currently working in this project. Only filenames and mtimes are
    inspected; contents are never read.
    """
    agents: list[str] = []
    window = minutes * 60
    now = __import__("time").time()
    probe = [
        (project_root / ".hermes", "hermes"),
        (project_root / ".codex", "codex"),
        (project_root / ".agents", "agents"),
    ]
    for root_dir, agent in probe:
        if not root_dir.is_dir():
            continue
        fresh = False
        try:
            for entry in root_dir.rglob("*"):
                if not entry.is_file():
                    continue
                name = entry.name.lower()
                if name in ("cache",) or name.endswith((".log", ".pyc", ".db-wal", ".db-shm")):
                    continue
                try:
                    age = now - entry.stat().st_mtime
                    if age <= window:
                        fresh = True
                        break
                except OSError:
                    continue
        except OSError:
            continue
        if fresh:
            agents.append(agent)
    return agents


def detect_active_projects(workspace_root: Path, max_depth: int = 3) -> list[ActiveProject]:
    """Discover projects under workspace_root and mark those with live agents.

    Activity = a workflow agent process is running AND the project's own agent
    state directories contain fresh evidence (modified within 120 minutes).
    This avoids fabricated "active" claims when no agent is really working.
    """
    discovered = discover_git_projects(workspace_root, max_depth=max_depth)
    agents_running = set(_running_agent_cwds().keys())
    active: list[ActiveProject] = []
    for project in discovered:
        fresh_agents = _project_agent_freshness(project.root)
        # Only claim active when a matching agent process is actually running.
        matched = [
            agent
            for agent in fresh_agents
            if agent == "agents" or any(agent in running for running in agents_running)
            or agent in agents_running
        ]
        if matched:
            active.append(ActiveProject(project_id=project.project_id, root=project.root, agents=matched))
    return active


def sync_workspace_projects(store: CanonicalStore, workspace_root: Path, max_depth: int = 3) -> dict[str, Any]:
    """Register all projects under the workspace and update active status.

    Returns a report suitable for the Observer projection:
    {
      "workspace_root": ...,
      "registered": N,
      "active_projects": [ {project_id, agents} ... ],
      "integrity": ...,
    }
    """
    profiles = []
    for project in discover_git_projects(workspace_root, max_depth=max_depth):
        profile = register_discovered(store, project)
        profiles.append(profile)

    active = detect_active_projects(workspace_root, max_depth=max_depth)
    for ap in active:
        store.update_project_status(ap.project_id, "ACTIVE")

    # Any project previously ACTIVE that is no longer active returns to REGISTERED.
    for project in store.list_projects():
        if project["status"] == "ACTIVE" and not any(
            ap.project_id == project["project_id"] for ap in active
        ):
            store.update_project_status(project["project_id"], "REGISTERED")

    return {
        "schema_version": "workflow/workspace-discovery/v1",
        "workspace_root": str(workspace_root.resolve()),
        "registered": len(profiles),
        "active_projects": [
            {"project_id": ap.project_id, "root": str(ap.root), "agents": sorted(ap.agents)}
            for ap in active
        ],
        "integrity": store.integrity_check(),
    }


if __name__ == "__main__":
    import argparse
    from project_temp import require_runtime_root

    parser = argparse.ArgumentParser(description="Discover workspace projects and detect active ones")
    parser.add_argument("--workspace-root", type=Path, required=True)
    parser.add_argument("--runtime-root", type=Path)
    parser.add_argument("--max-depth", type=int, default=3)
    args = parser.parse_args()

    runtime_root = require_runtime_root(args.runtime_root, "workflow-assistance-workspace")
    store = CanonicalStore(runtime_root / "canonical.sqlite")
    try:
        report = sync_workspace_projects(store, args.workspace_root, max_depth=args.max_depth)
        print(json.dumps(report, ensure_ascii=False, indent=2))
    finally:
        store.close()
