"""Worktree manager — per-agent isolated worktrees + serialized landing (parallel framework R3+R5).

Each agent/instance gets its own worktree + branch; landing goes through a
queue (CI-green then merge), so parallel writers never clobber each other.
Advisory: scripts here are tools for the parallel workflow, not auto-run.
"""
from __future__ import annotations

import subprocess
from pathlib import Path


def create_worktree(root: Path, owner: str, task: str, base: str = "main") -> dict:
    """Create an isolated worktree + branch for one agent/instance.

    WL-DLC-065: default target lives under .hermes/task-runtime/worktrees/
    (task data boundary); never write outside the project .hermes/.
    """
    wt_path = root / ".hermes" / "task-runtime" / "worktrees" / f"{owner}-{task}"
    branch = f"{owner}-{task}"
    r = subprocess.run(
        ["git", "-C", str(root), "worktree", "add", str(wt_path), "-b", branch, base],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    if r.returncode != 0:
        return {"ok": False, "error": r.stderr.strip()[:200]}
    return {"ok": True, "worktree": str(wt_path), "branch": branch}


def land(root: Path, owner: str, task: str, *, approved: bool = False,
         expected_branch: str | None = None, ci_green: bool = False) -> dict:
    """Land a branch into main — WL-DLC-065: requires explicit approval,
    exact branch, and CI-green evidence; otherwise BLOCKED (never touch main)."""
    branch = f"{owner}-{task}"
    if not approved:
        return {"ok": False, "status": "BLOCKED", "error": "land requires explicit approval"}
    if expected_branch and expected_branch != branch:
        return {"ok": False, "status": "BLOCKED", "error": f"branch mismatch: expected {expected_branch}"}
    if not ci_green:
        return {"ok": False, "status": "BLOCKED", "error": "CI-green evidence required before land"}
    branch = expected_branch or branch
    r = subprocess.run(
        ["git", "-C", str(root), "checkout", "main"], capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        return {"ok": False, "error": r.stderr.strip()[:200]}
    m = subprocess.run(
        ["git", "-C", str(root), "merge", "--no-ff", branch], capture_output=True, text=True, encoding="utf-8", errors="replace")
    if m.returncode != 0:
        return {"ok": False, "error": m.stderr.strip()[:300]}
    subprocess.run(["git", "-C", str(root), "worktree", "remove", str(root / ".hermes" / "task-runtime" / "worktrees" / f"{owner}-{task}")], capture_output=True, text=True, encoding="utf-8", errors="replace")
    subprocess.run(["git", "-C", str(root), "branch", "-d", branch], capture_output=True, text=True, encoding="utf-8", errors="replace")
    return {"ok": True, "merged": branch}


def list_worktrees(root: Path) -> list[str]:
    r = subprocess.run(["git", "-C", str(root), "worktree", "list", "--porcelain"], capture_output=True, text=True, encoding="utf-8", errors="replace")
    return [l.split()[1] for l in r.stdout.splitlines() if l.startswith("worktree ")]
