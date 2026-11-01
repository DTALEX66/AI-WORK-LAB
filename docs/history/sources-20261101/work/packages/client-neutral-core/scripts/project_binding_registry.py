"""NF-03-SYNC: config-driven project registration + local path binding.

Extends the existing ProductProject / registry surfaces WITHOUT a new project
model.  The goal is: a new project is onboarded by *declaration + local
binding only* — Git, multi-repo, plain-folder and document-based projects all
work; identity is a stable opaque ``project_id`` (never three names, a Git
remote string, or a single drive letter); and a cloud task may NOT carry its
own absolute local path to re-point at another project.

Pure and deterministic: no filesystem, no Git, no network.  Machine roots are
an in-memory user overlay (never committed to Git), mirroring the existing
``project_identity_resolver.machine_roots`` design.  Default-deny: a project
that is not on-boarded cannot be scanned or executed.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any, Iterable, Mapping

BASELINE_KINDS = ("git", "artifact")

# A local root binding must look like an absolute path on some drive / mount,
# not a cloud-issued relative token.  We only reject obvious non-absolute
# forms; the *ownership* rule (never trust a remote claim) is enforced in
# ``resolve_local_root`` regardless of this shape check.
_PATH_KIND = "absolute"


def _stable_digest(project_id: str, repo_id: str | None, base_kind: str) -> str:
    """Content-addressable artifact baseline for non-Git projects."""
    blob = f"{project_id}|{repo_id or ''}|{base_kind}".encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def _looks_like_local_root(value: str) -> bool:
    """Heuristic: an absolute local path (Windows drive or POSIX root)."""
    if not isinstance(value, str) or not value:
        return False
    v = value.replace("\\", "/")
    # Windows absolute:  C:/...  (drive letter + separator)
    if len(v) >= 3 and v[1:2] == ":" and v[2] == "/":
        return True
    if v.startswith("/") or v.startswith("~"):
        return True
    return False


@dataclass(frozen=True)
class ProjectOnboarding:
    """A declared project entry — identity + baseline + material placement.

    ``project_id`` is the stable opaque identity.  ``repository_id`` is an
    OPTIONAL association; two projects may share a repo, a project may have
    several repos, and a non-Git project has none.
    """

    project_id: str
    display_name: str = ""
    base_kind: str = "git"            # "git" | "artifact"
    repository_id: str | None = None  # optional association, not the identity
    material_root: str = ""           # where task materials live for THIS project
    receiving_node: str = ""          # which node receives this project's work
    allowed_artifacts: tuple[str, ...] = ()
    allowed_capabilities: tuple[str, ...] = ()
    artifact_revision: str | None = None  # for base_kind == "artifact"

    def validate(self) -> None:
        if not self.project_id:
            raise ValueError("project_id is required and must be opaque/non-empty")
        if self.base_kind not in BASELINE_KINDS:
            raise ValueError(f"unknown base_kind {self.base_kind!r}")
        if self.base_kind == "artifact" and not self.artifact_revision:
            raise ValueError("artifact baseline requires an artifact_revision")


def _to_onboarding(raw: Mapping[str, Any]) -> ProjectOnboarding:
    onb = ProjectOnboarding(
        project_id=str(raw["project_id"]),
        display_name=str(raw.get("display_name", "")),
        base_kind=str(raw.get("base_kind", "git")),
        repository_id=raw.get("repository_id"),
        material_root=str(raw.get("material_root", "")),
        receiving_node=str(raw.get("receiving_node", "")),
        allowed_artifacts=tuple(raw.get("allowed_artifacts", ())),
        allowed_capabilities=tuple(raw.get("allowed_capabilities", ())),
        artifact_revision=raw.get("artifact_revision"),
    )
    onb.validate()
    return onb


class ProjectBindingRegistry:
    """On-boarded projects + a user-owned machine-root overlay.

    Only on-boarded project ids are resolvable; everything else is UNKNOWN and
    must be surfaced as "not connected", never executed.  Local roots come
    ONLY from the machine overlay keyed by project_id.
    """

    def __init__(self, onboardings: Iterable[Mapping[str, Any]] = ()) -> None:
        self._projects: dict[str, ProjectOnboarding] = {}
        for raw in onboardings:
            onb = _to_onboarding(raw)
            if onb.project_id in self._projects:
                raise ValueError(f"duplicate project_id {onb.project_id!r}")
            self._projects[onb.project_id] = onb
        # machine_roots: project_id -> local absolute root (user overlay, NOT in Git)
        self.machine_roots: dict[str, str] = {}

    # -- registration -------------------------------------------------------
    def add_project(self, raw: Mapping[str, Any]) -> ProjectOnboarding:
        onb = _to_onboarding(raw)
        if onb.project_id in self._projects:
            raise ValueError(f"duplicate project_id {onb.project_id!r}")
        self._projects[onb.project_id] = onb
        return onb

    def bind_local_root(self, project_id: str, local_root: str) -> None:
        """Record a user-approved local binding for an on-boarded project."""
        if project_id not in self._projects:
            raise KeyError(f"project not on-boarded: {project_id!r}")
        if not _looks_like_local_root(local_root):
            raise ValueError(f"local binding must be an absolute local path, got {local_root!r}")
        self.machine_roots[project_id] = local_root.replace("\\", "/").rstrip("/")

    # -- resolution ----------------------------------------------------------
    def is_onboarded(self, project_id: str) -> bool:
        return project_id in self._projects

    def project(self, project_id: str) -> ProjectOnboarding | None:
        return self._projects.get(project_id)

    def resolve_local_root(self, project_id: str) -> dict[str, Any]:
        """Resolve a project's local root ONLY from the user's machine binding.

        Fail-closed: not on-boarded -> UNKNOWN; on-boarded but no local
        binding -> UNBOUND; bound -> RESOLVED.  A remote-claimed path is never
        consulted here, so a cloud task cannot re-point the project elsewhere.
        """
        if not self.is_onboarded(project_id):
            return {"status": "UNKNOWN", "project_id": project_id,
                    "note": "project not on-boarded; shown as 'not connected', not executed"}
        root = self.machine_roots.get(project_id)
        if not root:
            return {"status": "UNBOUND", "project_id": project_id,
                    "note": "on-boarded but no local binding recorded on this machine"}
        return {"status": "RESOLVED", "project_id": project_id, "root": root}

    def resolve_with_remote_claim(self, project_id: str,
                                  remote_claimed_path: str | None = None) -> dict[str, Any]:
        """Prove the security rule: a cloud task's own absolute path is IGNORED.

        The returned root, if any, comes exclusively from the local binding.
        A foreign / re-pointing claim is reported as rejected, never applied.
        """
        base = self.resolve_local_root(project_id)
        out = dict(base)
        if remote_claimed_path is None:
            return out
        trusted = self.machine_roots.get(project_id)
        claim_norm = remote_claimed_path.replace("\\", "/").rstrip("/")
        if trusted and claim_norm == trusted:
            out["remote_claim"] = "MATCHES_LOCAL_BINDING"
        else:
            out["remote_claim"] = "REJECTED"
            out["remote_claim_reason"] = (
                "a cloud task may not carry its own absolute path to re-point "
                "at a local project; only the user-approved local binding is used"
            )
        return out

    def artifact_baseline(self, project_id: str) -> dict[str, Any]:
        """Stable content address for a non-Git project; Git projects key on commit."""
        onb = self._projects.get(project_id)
        if onb is None:
            return {"status": "UNKNOWN", "project_id": project_id}
        if onb.base_kind == "artifact":
            return {"status": "RESOLVED", "project_id": project_id,
                    "base_kind": "artifact",
                    "revision": onb.artifact_revision,
                    "digest": _stable_digest(onb.project_id, onb.repository_id, "artifact")}
        return {"status": "RESOLVED", "project_id": project_id,
                "base_kind": "git",
                "note": "Git project keys on exact commit/worktree, not content hash"}

    # -- collision / alias safety -------------------------------------------
    def detect_name_collisions(self) -> list[str]:
        """Same display name on different project_id -> reported, never merged."""
        by_name: dict[str, list[str]] = {}
        for pid, onb in self._projects.items():
            if onb.display_name:
                by_name.setdefault(onb.display_name, []).append(pid)
        return sorted(name for name, pids in by_name.items() if len(pids) > 1)
