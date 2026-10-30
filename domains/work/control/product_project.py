"""Product project domain model (WLGM-010).

Separates the user-perceived *product project* from repositories, worktrees,
modules and submodules. One product project may bind multiple repositories; one
repository may own multiple worktrees (all belonging to the same product
project); modules are only *working areas* and never promoted to projects by
default; submodules attach to the parent or stand alone via an explicit policy.

The model is a pure data/validation layer: no filesystem, Git or process IO.
Resolution logic lives in ``project_identity_resolver`` (WLGM-030).
"""
from __future__ import annotations

import ntpath
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class RepositoryRole(str, Enum):
    PRIMARY = "primary"
    SUPPORT = "support"
    CONFIG = "config"
    OBSERVER = "observer"


class WorktreeKind(str, Enum):
    PRIMARY = "primary"
    LINKED = "linked"
    BARE = "bare"


class BindingKind(str, Enum):
    ROOT = "root"
    WORKTREE = "worktree"
    MODULE = "module"
    SUBMODULE = "submodule"


class SubmodulePolicy(str, Enum):
    ATTACH_TO_PARENT = "attach_to_parent"
    INDEPENDENT_PROJECT = "independent_project"


class ResolutionState(str, Enum):
    RESOLVED = "RESOLVED"
    UNRESOLVED = "UNRESOLVED"
    CONFLICT = "CONFLICT"


class IdentityQuality(str, Enum):
    EXACT = "EXACT"
    SOURCE_REPORTED = "SOURCE_REPORTED"
    CORRELATED = "CORRELATED"
    DERIVED = "DERIVED"
    INFERRED = "INFERRED"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class RepositoryIdentity:
    """Identity of a single Git repository bound to a product project."""

    repository_id: str
    remote_identity: str | None = None  # normalized remote (e.g. github:DTALEX66/WORK-LAB)
    common_dir: str | None = None  # normalized git-common-dir (worktree-aware)
    role: RepositoryRole = RepositoryRole.PRIMARY

    def normalize(self) -> "RepositoryIdentity":
        return self


@dataclass(frozen=True)
class WorktreeIdentity:
    """A concrete checkout (primary or linked worktree) of a repository."""

    worktree_id: str
    repository_id: str
    root: str  # normalized absolute path
    kind: WorktreeKind = WorktreeKind.PRIMARY


@dataclass(frozen=True)
class ModuleIdentity:
    """A subdirectory inside a repository; only ever a working area."""

    module_id: str
    repository_id: str
    relative_path: str  # path relative to the repository root


@dataclass(frozen=True)
class SubmoduleRelation:
    """A submodule entry: path + policy (attach or independent)."""

    repository_id: str
    submodule_path: str
    policy: SubmodulePolicy = SubmodulePolicy.ATTACH_TO_PARENT


@dataclass(frozen=True)
class ProjectRootBinding:
    """Binds a concrete root (normalized path) to a product project.

    ``kind`` says whether the root IS the project root, a linked worktree of an
    owned repository, a module working area, or a submodule of an owned repo.
    """

    binding_id: str
    project_id: str
    root: str  # normalized absolute path
    repository_id: str | None = None
    worktree_id: str | None = None
    kind: BindingKind = BindingKind.ROOT


@dataclass
class ProductProject:
    """User-perceived product project.

    ``remote_identities`` are normalized remote strings; ``root_bindings`` are
    approved concrete paths. Definitions (without machine-specific roots) may be
    versioned in Git; the concrete binding layer lives in the canonical store.
    """

    project_id: str
    display_name: str = ""
    remote_identities: list[str] = field(default_factory=list)
    root_bindings: list[ProjectRootBinding] = field(default_factory=list)
    repositories: list[RepositoryIdentity] = field(default_factory=list)
    worktrees: list[WorktreeIdentity] = field(default_factory=list)
    modules: list[ModuleIdentity] = field(default_factory=list)
    submodules: list[SubmoduleRelation] = field(default_factory=list)
    include_policy: str = "explicit"  # explicit | discovered
    submodule_policy: SubmodulePolicy = SubmodulePolicy.ATTACH_TO_PARENT
    deny_listed: bool = False
    never_scan: bool = False
    approved: bool = False  # user-approved before collectors may run

    def add_repository(self, repo: RepositoryIdentity) -> None:
        if not any(r.repository_id == repo.repository_id for r in self.repositories):
            self.repositories.append(repo)
        if repo.remote_identity and repo.remote_identity not in self.remote_identities:
            self.remote_identities.append(repo.remote_identity)

    def add_root_binding(self, binding: ProjectRootBinding) -> None:
        normalized = _normalize_path(binding.root)
        if not any(_same_path(b.root, normalized) for b in self.root_bindings):
            self.root_bindings.append(
                ProjectRootBinding(
                    binding_id=binding.binding_id,
                    project_id=self.project_id,
                    root=normalized,
                    repository_id=binding.repository_id,
                    worktree_id=binding.worktree_id,
                    kind=binding.kind,
                )
            )

    def has_root(self, root: str) -> bool:
        normalized = _normalize_path(root)
        return any(_same_path(b.root, normalized) for b in self.root_bindings)

    def to_definition(self) -> dict[str, Any]:
        """Portable (machine-agnostic) definition safe to version in Git."""
        return {
            "schema_version": "workflow/product-project/v1",
            "project_id": self.project_id,
            "display_name": self.display_name,
            "remote_identities": sorted(self.remote_identities),
            "repositories": [
                {
                    "repository_id": r.repository_id,
                    "remote_identity": r.remote_identity,
                    "role": r.role.value,
                }
                for r in self.repositories
            ],
            "include_policy": self.include_policy,
            "submodule_policy": self.submodule_policy.value,
            "deny_listed": self.deny_listed,
            "never_scan": self.never_scan,
            "approved": self.approved,
        }

    @classmethod
    def from_definition(cls, data: dict[str, Any]) -> "ProductProject":
        """Rebuild from a portable definition (unknown keys preserved by caller)."""
        project = cls(project_id=str(data["project_id"]), display_name=str(data.get("display_name", "")))
        project.remote_identities = list(data.get("remote_identities", []))
        project.include_policy = str(data.get("include_policy", "explicit"))
        project.deny_listed = bool(data.get("deny_listed", False))
        project.never_scan = bool(data.get("never_scan", False))
        project.approved = bool(data.get("approved", False))
        try:
            project.submodule_policy = SubmodulePolicy(data.get("submodule_policy", "attach_to_parent"))
        except ValueError:
            project.submodule_policy = SubmodulePolicy.ATTACH_TO_PARENT
        for repo in data.get("repositories", []):
            try:
                role = RepositoryRole(repo.get("role", "primary"))
            except ValueError:
                role = RepositoryRole.PRIMARY
            project.add_repository(
                RepositoryIdentity(
                    repository_id=str(repo["repository_id"]),
                    remote_identity=repo.get("remote_identity"),
                    role=role,
                )
            )
        return project


def normalize_remote_identity(remote_url: str) -> str | None:
    """Normalize an SSH/HTTPS remote URL to a stable identity (e.g. github:DTALEX66/WORK-LAB).

    Host names are lowercased; the owner/repo portion keeps its original case.
    Returns None for local-only or unparseable remotes.
    """
    value = remote_url.strip()
    if not value:
        return None
    if value.lower().startswith(("https://", "http://")):
        value = value.split("://", 1)[1]
    if value.endswith(".git"):
        value = value[:-4]
    value = value.rstrip("/")
    lowered = value.lower()
    if "github.com/" in lowered:
        owner, _, repo = value.split("github.com/", 1)[1].partition("/")
        return f"github:{owner}/{repo}"
    if lowered.startswith("git@") and ":" in value:
        host, _, path = value[4:].partition(":")
        host = host.lower()
        if host == "github.com":
            host = "github"
        return f"{host}:{path}"
    if ":" in value and "/" in value.split(":", 1)[1]:
        host, _, path = value.partition(":")
        return f"{host.lower()}:{path}"
    return None


def _normalize_path(value: str) -> str:
    return str(PathLike(value))


def _same_path(left: str, right: str) -> bool:
    """Windows-aware path equality: case-insensitive on Windows, case-sensitive elsewhere."""
    if ntpath.normcase(left) == ntpath.normcase(right):
        return True
    return left == right


class PathLike:
    """Minimal path normalizer avoiding ``pathlib`` drive/posix ambiguity."""

    def __init__(self, value: str) -> None:
        self._value = value.replace("\\", "/").rstrip("/") or "/"

    def __str__(self) -> str:
        return self._value
