"""Project Identity Resolver (WLGM-020/030).

Maps an arbitrary execution path to a stable *product project* using this
resolution order:

1. normalize the path and record filesystem identity;
2. ``git rev-parse --show-toplevel`` (nearest work-tree root);
3. ``git rev-parse --git-common-dir`` (worktree-aware common dir);
4. ``git rev-parse --show-superproject-working-tree`` (submodule parent);
5. match an approved remote identity;
6. match a git-common-dir / worktree identity;
7. match an approved root containment relationship;
8. apply submodule/module policy;
9. otherwise return an UNRESOLVED candidate.

Pure-ish by design: the Git probe is injectable so the resolver logic is fully
unit-testable without a real checkout. No content of any agent private state is
read; only git plumbing metadata.
"""
from __future__ import annotations

import json
import ntpath
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Sequence

from product_project import (
    BindingKind,
    IdentityQuality,
    ProductProject,
    ResolutionState,
    normalize_remote_identity,
)


def _norm_path(value: str) -> str:
    return value.replace("\\", "/").rstrip("/") or "/"


def _same_path(left: str, right: str) -> bool:
    return ntpath.normcase(_norm_path(left)) == ntpath.normcase(_norm_path(right))


@dataclass
class ResolutionResult:
    project_id: str | None = None
    repository_id: str | None = None
    worktree_id: str | None = None
    working_area: str | None = None
    resolution_state: ResolutionState = ResolutionState.UNRESOLVED
    quality: IdentityQuality = IdentityQuality.UNKNOWN
    evidence_refs: list[str] = field(default_factory=list)
    # WLOSS-410: V2 output fields (never fabricated; filled by callers where known).
    display_name: str | None = None
    runtime_instances: list[str] = field(default_factory=list)
    active_tasks: list[str] = field(default_factory=list)
    nested_projects: list[str] = field(default_factory=list)
    confidence: str = "UNKNOWN"

    def as_json(self) -> dict[str, Any]:
        return {
            "projectId": self.project_id,
            "displayName": self.display_name,
            "repositoryId": self.repository_id,
            "worktreeId": self.worktree_id,
            "workingArea": self.working_area,
            "resolutionState": self.resolution_state.value,
            "quality": self.quality.value,
            "confidence": self.confidence,
            "runtimeInstances": list(self.runtime_instances),
            "activeTasks": list(self.active_tasks),
            "nestedProjects": list(self.nested_projects),
            "evidenceRefs": self.evidence_refs,
        }

    def mark_resolved(
        self,
        project: ProductProject,
        *,
        top: str,
        quality: IdentityQuality,
        evidence: str,
    ) -> None:
        """Centralized RESOLVED state fill (WLOSS-410 V2 fields)."""
        self.project_id = project.project_id
        self.display_name = project.display_name or project.project_id
        self.repository_id = _first_repo_id(project)
        self.worktree_id = _match_worktree(project, top)
        self.working_area = _working_area(project, top)
        self.resolution_state = ResolutionState.RESOLVED
        self.quality = quality
        self.confidence = quality.value
        self.evidence_refs.append(evidence)


class GitProbe:
    """Thin, injectable Git metadata probe (no lock-refreshing commands)."""

    def __init__(self, runner: Callable[[list[str], str], str | None] | None = None) -> None:
        self._runner = runner or self._default_runner

    @staticmethod
    def _default_runner(args: list[str], cwd: str) -> str | None:
        try:
            result = subprocess.run(
                ["git", *args],
                cwd=cwd,
                text=True, encoding="utf-8", errors="replace",
                capture_output=True,
                check=False,
                timeout=20,
                env={"GIT_OPTIONAL_LOCKS": "0", **__import__("os").environ},
            )
        except (OSError, subprocess.SubprocessError):
            return None
        return result.stdout.strip() if result.returncode == 0 else None

    def toplevel(self, path: str) -> str | None:
        return self._runner(["rev-parse", "--show-toplevel"], path)

    def common_dir(self, path: str) -> str | None:
        return self._runner(["rev-parse", "--git-common-dir"], path)

    def superproject(self, path: str) -> str | None:
        return self._runner(["rev-parse", "--show-superproject-working-tree"], path)

    def remotes(self, path: str) -> list[str]:
        raw = self._runner(["remote", "-v"], path)
        identities: list[str] = []
        if not raw:
            return identities
        for line in raw.splitlines():
            parts = line.split()
            if len(parts) >= 2:
                identity = normalize_remote_identity(parts[1])
                if identity and identity not in identities:
                    identities.append(identity)
        return identities

    def worktree_list(self, path: str) -> list[tuple[str, str, str]]:
        """Return (worktree root, common dir, branch) triples via --porcelain."""
        raw = self._runner(["worktree", "list", "--porcelain"], path)
        triples: list[tuple[str, str, str]] = []
        if not raw:
            return triples
        current: dict[str, str] = {}
        for line in raw.splitlines():
            if line.startswith("worktree "):
                current["root"] = line.split(" ", 1)[1].strip()
            elif line.startswith("HEAD "):
                current["head"] = line.split(" ", 1)[1].strip()
            elif line.startswith("branch "):
                current["branch"] = line.split(" ", 1)[1].strip()
            elif line == "" and current:
                triples.append(
                    (current.get("root", ""), current.get("head", ""), current.get("branch", ""))
                )
                current = {}
        if current:
            triples.append((current.get("root", ""), current.get("head", ""), current.get("branch", "")))
        return triples


class ApprovedProjectIndex:
    """In-memory approved project definitions (portable) + machine root bindings."""

    def __init__(
        self,
        projects: Sequence[ProductProject] = (),
        machine_roots: dict[str, str] | None = None,
    ) -> None:
        self.projects: dict[str, ProductProject] = {p.project_id: p for p in projects}
        # machine_roots: remote_identity -> absolute local root (user overlay, never in Git)
        self.machine_roots: dict[str, str] = machine_roots or {}

    def add(self, project: ProductProject) -> None:
        self.projects[project.project_id] = project

    def by_root(self, root: str) -> ProductProject | None:
        for project in self.projects.values():
            if project.has_root(root):
                return project
        return None

    def by_remote(self, remote_identity: str) -> ProductProject | None:
        for project in self.projects.values():
            if remote_identity in project.remote_identities:
                return project
        return None


def _is_within(root: str, candidate: str) -> bool:
    """candidate is root or directly below root (path-segment aware)."""
    root_n = _norm_path(root).lower() if ntpath.normcase("a") == "a" else _norm_path(root)
    cand_n = _norm_path(candidate).lower() if ntpath.normcase("a") == "a" else _norm_path(candidate)
    if cand_n == root_n:
        return True
    return cand_n.startswith(root_n.rstrip("/") + "/")


def resolve_execution_path(
    path: str,
    index: ApprovedProjectIndex,
    git: GitProbe | None = None,
) -> ResolutionResult:
    """Resolve a single execution path to a product project (WLGM-030 order)."""
    probe = git or GitProbe()
    normalized = _norm_path(path)
    result = ResolutionResult(working_area=normalized)

    top = probe.toplevel(path)
    common = probe.common_dir(path)
    superproject = probe.superproject(path)

    if not top and not common:
        # Not inside any Git repository at all.
        return result

    if superproject:
        result.evidence_refs.append("superproject")
    if common:
        result.evidence_refs.append("git-common-dir")
    if top:
        result.evidence_refs.append("git-toplevel")

    # Step 4b: submodule attach policy — superproject is an approved root.
    if superproject:
        for project in index.projects.values():
            if project.has_root(superproject) and project.submodule_policy.value == "attach_to_parent":
                result.nested_projects.append(normalized)
                result.mark_resolved(
                    project, top=superproject,
                    quality=IdentityQuality.CORRELATED,
                    evidence="submodule-attach",
                )
                return result

    # Step 5: remote identity match.
    if top:
        remotes = probe.remotes(top)
        for remote in remotes:
            project = index.by_remote(remote)
            if project is not None:
                result.mark_resolved(
                    project, top=top,
                    quality=IdentityQuality.EXACT if remote in project.remote_identities else IdentityQuality.SOURCE_REPORTED,
                    evidence=f"remote:{remote}",
                )
                return result

    # Step 6: exact worktree root match.
    for project in index.projects.values():
        worktree = _match_worktree(project, top)
        if worktree is not None:
            result.mark_resolved(project, top=top, quality=IdentityQuality.EXACT, evidence="worktree-root")
            return result

    # Step 7: approved-root containment, only within the SAME repository.
    for project in index.projects.values():
        if project.has_root(top):
            result.mark_resolved(project, top=top, quality=IdentityQuality.EXACT, evidence="approved-root")
            return result
        for binding in project.root_bindings:
            if not _is_within(binding.root, top):
                continue
            # Independent nested repository must not merge by path containment alone.
            root_common = probe.common_dir(binding.root)
            if common and root_common and not _same_path(root_common, common):
                continue
            if common and not root_common:
                continue
            result.nested_projects.append(top)
            result.mark_resolved(
                project, top=top,
                quality=IdentityQuality.CORRELATED,
                evidence="approved-root-containment",
            )
            return result

    # Step 8/9: machine roots from the user overlay.
    for remote, root in index.machine_roots.items():
        if _same_path(root, top) or _is_within(root, top):
            project = index.by_remote(remote)
            if project is not None:
                result.mark_resolved(
                    project, top=top,
                    quality=IdentityQuality.CORRELATED,
                    evidence=f"machine-root:{remote}",
                )
                return result

    # No match: unresolved candidate.
    result.resolution_state = ResolutionState.UNRESOLVED
    result.quality = IdentityQuality.UNKNOWN
    result.evidence_refs.append("unresolved-candidate")
    return result


def _first_repo_id(project: ProductProject) -> str | None:
    return project.repositories[0].repository_id if project.repositories else project.project_id


def _match_worktree(project: ProductProject, top: str) -> str | None:
    for worktree in project.worktrees:
        if _same_path(worktree.root, top):
            return worktree.worktree_id
    return None


def _working_area(project: ProductProject, top: str) -> str | None:
    """Return the module/working-area path relative to the project root, if any."""
    for module in project.modules:
        candidate = module.relative_path
        if _is_within(_norm_path(top), _norm_path(module.repository_id + "/" + candidate)):
            return candidate
    return None


def _relative(root: str, candidate: str) -> str | None:
    root_n = _norm_path(root)
    cand_n = _norm_path(candidate)
    if cand_n == root_n:
        return None
    if cand_n.startswith(root_n.rstrip("/") + "/"):
        return cand_n[len(root_n.rstrip("/")) + 1 :]
    return None
