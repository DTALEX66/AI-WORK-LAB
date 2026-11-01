"""Git / worktree / submodule low-frequency fallback collector (WLGM-120).

Minimal-Git-overhead identity and activity evidence:

- uses GIT_OPTIONAL_LOCKS=0 (never refreshes the index, never creates locks);
- dirty-state checks are low-frequency, time-boxed and disable-able;
- HEAD changes are NOT attributed to any agent;
- submodules are never promoted to product projects;
- file mtime produces only an activity hint;
- never recursively scans repository content.
"""
from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

_GIT_ENV = {**os.environ, "GIT_OPTIONAL_LOCKS": "0"}


@dataclass
class GitObservation:
    root: str
    head_sha: str | None = None
    common_dir: str | None = None
    superproject: str | None = None
    worktrees: list[str] = field(default_factory=list)
    dirty_count: int | None = None
    remote_identity: str | None = None
    observed_at: str = ""

    def to_record(self) -> dict[str, Any]:
        return {
            "root": self.root,
            "headSha": self.head_sha,
            "commonDir": self.common_dir,
            "superproject": self.superproject,
            "worktrees": self.worktrees,
            "dirtyCount": self.dirty_count,
            "remoteIdentity": self.remote_identity,
            "observedAt": self.observed_at,
        }


def _git(root: Path, *args: str, timeout: float = 20.0) -> str | None:
    try:
        result = subprocess.run(
            ["git", *args], cwd=str(root), text=True, encoding="utf-8", errors="replace", capture_output=True, check=False,
            timeout=timeout, env=_GIT_ENV,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return result.stdout.strip() if result.returncode == 0 else None


def collect_git_observation(
    root: Path,
    *,
    include_dirty: bool = True,
    dirty_timeout: float = 15.0,
    skip_worktrees: bool = False,
) -> GitObservation:
    """Collect low-frequency Git evidence for one repository root."""
    observed = GitObservation(root=str(root.resolve()))
    observed.head_sha = _git(root, "rev-parse", "HEAD", timeout=10)
    common = _git(root, "rev-parse", "--git-common-dir", timeout=10)
    if common:
        observed.common_dir = common
    observed.superproject = _git(root, "rev-parse", "--show-superproject-working-tree", timeout=10)
    if not skip_worktrees:
        raw = _git(root, "worktree", "list", "--porcelain", timeout=15)
        if raw:
            observed.worktrees = [
                line.split(" ", 1)[1].strip()
                for line in raw.splitlines()
                if line.startswith("worktree ")
            ]
    remote = _git(root, "remote", "get-url", "origin", timeout=10)
    if remote:
        from product_project import normalize_remote_identity

        observed.remote_identity = normalize_remote_identity(remote)
    if include_dirty:
        dirty = _git(root, "status", "--porcelain=v1", timeout=dirty_timeout)
        if dirty is not None:
            observed.dirty_count = len([line for line in dirty.splitlines() if line.strip()])
    return observed
