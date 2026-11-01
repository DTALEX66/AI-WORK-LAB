"""Candidate discovery + allowlist boundary (WLGM-050).

Replaces the old "scan-to-register" behaviour: a discovery pass only produces
*candidates* with minimal metadata (root fingerprint, Git identity, display
name). Nothing is written to the canonical registry and no collector starts
until the user approves a candidate. Deny-listed and ``never_scan`` roots are
skipped, large resource trees (node_modules, design assets, models, virtual
envs, build output) are never recursed.
"""
from __future__ import annotations

import hashlib
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

EXCLUDED_DIR_NAMES = {
    ".git",
    ".hg",
    ".svn",
    ".hermes",
    ".codex",
    ".agents",
    ".venv",
    "venv",
    ".tox",
    "node_modules",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "dist",
    "build",
    "target",
    ".idea",
    ".vscode",
    "models",
    "assets",
    "design-assets",
    ".cache",
    ".next",
    ".nuxt",
    "coverage",
}


@dataclass
class DiscoveryConfig:
    discovery_root: Path
    max_depth: int = 2
    excluded_names: set[str] = field(default_factory=lambda: set(EXCLUDED_DIR_NAMES))
    deny_list: set[str] = field(default_factory=set)  # project_ids denied
    never_scan: set[str] = field(default_factory=set)  # absolute roots never scanned


@dataclass
class ProjectCandidate:
    candidate_id: str
    root: str  # normalized absolute path
    root_fingerprint: str  # sha256 of normalized root
    display_name_candidate: str
    git_identity: dict[str, str] = field(default_factory=dict)  # remote_identity, head_sha
    status: str = "CANDIDATE"  # CANDIDATE | APPROVED | DENIED
    discovered_at: str = ""

    def minimal_metadata(self) -> dict[str, Any]:
        """Only minimal, secret-free metadata for review."""
        return {
            "candidate_id": self.candidate_id,
            "root": self.root,
            "root_fingerprint": self.root_fingerprint,
            "display_name_candidate": self.display_name_candidate,
            "git_identity": self.git_identity,
            "status": self.status,
        }


def _norm(value: str) -> str:
    return value.replace("\\", "/").rstrip("/") or "/"


def _fingerprint(root: str) -> str:
    return hashlib.sha256(_norm(root).encode("utf-8")).hexdigest()


def _git(root: Path, *args: str) -> str | None:
    try:
        result = subprocess.run(
            ["git", *args], cwd=str(root), text=True, encoding="utf-8", errors="replace", capture_output=True, check=False, timeout=20
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return result.stdout.strip() if result.returncode == 0 else None


def _is_git_root(path: Path) -> bool:
    top = _git(path, "rev-parse", "--show-toplevel")
    if not top:
        return False
    try:
        return Path(top).resolve() == path.resolve()
    except OSError:
        return False


def _remote_identity(root: Path) -> str | None:
    raw = _git(root, "remote", "get-url", "origin")
    if not raw:
        return None
    return raw


def _head_sha(root: Path) -> str | None:
    value = _git(root, "rev-parse", "HEAD")
    return value if value and len(value) == 40 else None


def discover_candidates(config: DiscoveryConfig) -> list[ProjectCandidate]:
    """Scan for candidates WITHOUT writing any registry entry."""
    candidates: list[ProjectCandidate] = []
    root = config.discovery_root
    if not root.is_dir():
        return candidates
    root_norm = _norm(str(root.resolve()))
    if root_norm in {_norm(r) for r in config.never_scan}:
        return candidates
    queue: list[tuple[Path, int]] = [(root, 0)]
    while queue:
        current, depth = queue.pop(0)
        if depth > config.max_depth:
            continue
        if _is_git_root(current):
            project_id = current.name.lower().replace(" ", "-")
            if project_id in config.deny_list:
                continue
            remote = _remote_identity(current)
            candidates.append(
                ProjectCandidate(
                    candidate_id=project_id,
                    root=_norm(str(current.resolve())),
                    root_fingerprint=_fingerprint(str(current.resolve())),
                    display_name_candidate=current.name,
                    git_identity={
                        **( {"remote_identity": remote} if remote else {}),
                        **( {"head_sha": head} if (head := _head_sha(current)) else {}),
                    },
                )
            )
            continue  # never descend into a repo
        try:
            entries = sorted(current.iterdir())
        except OSError:
            continue
        for entry in entries:
            if not entry.is_dir() or entry.name.startswith(".") and entry.name not in (".git",):
                if entry.name in config.excluded_names:
                    continue
            if entry.name in config.excluded_names:
                continue
            if entry.name.startswith("."):
                continue
            queue.append((entry, depth + 1))
    return candidates


def approve_candidate(candidate: ProjectCandidate) -> ProjectCandidate:
    candidate.status = "APPROVED"
    return candidate


def deny_candidate(candidate: ProjectCandidate) -> ProjectCandidate:
    candidate.status = "DENIED"
    return candidate
