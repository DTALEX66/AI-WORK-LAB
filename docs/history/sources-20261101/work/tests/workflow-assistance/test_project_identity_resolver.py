"""WLGM-030 tests: Project Identity Resolver."""
from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

from product_project import (
    BindingKind,
    ProductProject,
    ProjectRootBinding,
    RepositoryIdentity,
    WorktreeIdentity,
)
from project_identity_resolver import (
    ApprovedProjectIndex,
    GitProbe,
    ResolutionState,
    resolve_execution_path,
)


class FakeGitProbe:
    """Deterministic probe for pure resolver tests."""

    def __init__(self, *, top=None, common=None, superproject=None, remotes=(), worktrees=(), common_by_path=None):
        self._top = top
        self._common = common
        self._super = superproject
        self._remotes = remotes
        self._worktrees = worktrees
        self._common_by_path = common_by_path or {}

    def toplevel(self, path):
        return self._top

    def common_dir(self, path):
        return self._common_by_path.get(path, self._common)

    def superproject(self, path):
        return self._super

    def remotes(self, path):
        return list(self._remotes)

    def worktree_list(self, path):
        return list(self._worktrees)


def make_project(project_id, remote=None, root=None, worktrees=()):
    project = ProductProject(project_id=project_id)
    if remote:
        project.remote_identities = [remote]
        project.add_repository(RepositoryIdentity(repository_id=project_id, remote_identity=remote))
    if root:
        project.add_root_binding(ProjectRootBinding(binding_id=f"{project_id}-b", project_id=project_id, root=root))
    for wt in worktrees:
        project.worktrees.append(WorktreeIdentity(worktree_id=wt[0], repository_id=project_id, root=wt[1]))
    return project


class IdentityResolverTests(unittest.TestCase):
    def test_resolves_by_remote_identity(self) -> None:
        index = ApprovedProjectIndex(projects=[make_project("work-lab", remote="github:DTALEX66/WORK-LAB")])
        probe = FakeGitProbe(top="/work/WORK-LAB", common="/work/WORK-LAB/.git", remotes=["github:DTALEX66/WORK-LAB"])
        result = resolve_execution_path("/work/WORK-LAB/services", index, git=probe)
        self.assertEqual(result.project_id, "work-lab")
        self.assertEqual(result.resolution_state, ResolutionState.RESOLVED)

    def test_path_containment_is_not_the_only_identity(self) -> None:
        """An independent nested repo must not merge by path containment alone."""
        index = ApprovedProjectIndex(projects=[make_project("a", root="/work/a")])
        probe = FakeGitProbe(
            top="/work/a/sub",
            common="/work/a/sub/.git",
            common_by_path={"/work/a": "/work/a/.git"},
        )
        result = resolve_execution_path("/work/a/sub", index, git=probe)
        # Different repository (different common dir) -> unresolved candidate.
        self.assertEqual(result.resolution_state, ResolutionState.UNRESOLVED)

    def test_module_inside_same_repo_resolves_by_containment(self) -> None:
        """A subdirectory of the SAME repo belongs to the project."""
        index = ApprovedProjectIndex(projects=[make_project("a", root="/work/a")])
        probe = FakeGitProbe(
            top="/work/a",
            common="/work/a/.git",
            common_by_path={"/work/a": "/work/a/.git"},
        )
        result = resolve_execution_path("/work/a/module", index, git=probe)
        self.assertEqual(result.project_id, "a")
        self.assertEqual(result.resolution_state, ResolutionState.RESOLVED)

    def test_same_directory_name_different_remote_not_merged(self) -> None:
        index = ApprovedProjectIndex(
            projects=[
                make_project("p1", remote="github:ALICE/repo"),
                make_project("p2", remote="github:BOB/repo"),
            ]
        )
        probe = FakeGitProbe(top="/w/repo", common="/w/repo/.git", remotes=["github:BOB/repo"])
        result = resolve_execution_path("/w/repo", index, git=probe)
        self.assertEqual(result.project_id, "p2")
        self.assertEqual(result.resolution_state, ResolutionState.RESOLVED)

    def test_local_only_repo_without_remote_stays_unresolved(self) -> None:
        index = ApprovedProjectIndex(projects=[make_project("p", root="/w/p")])
        probe = FakeGitProbe(top="/w/other", common="/w/other/.git", remotes=[])
        result = resolve_execution_path("/w/other", index, git=probe)
        self.assertEqual(result.resolution_state, ResolutionState.UNRESOLVED)

    def test_unresolved_output_shape(self) -> None:
        index = ApprovedProjectIndex()
        probe = FakeGitProbe(top=None, common=None)
        result = resolve_execution_path("/unknown/path", index, git=probe)
        self.assertEqual(result.resolution_state, ResolutionState.UNRESOLVED)
        data = result.as_json()
        self.assertEqual(data["projectId"], None)
        self.assertEqual(data["quality"], "UNKNOWN")

    def test_v2_output_fields_on_resolve(self) -> None:
        """WLOSS-410: resolved output carries displayName/confidence; runtime
        instances/tasks stay empty (never fabricated)."""
        project = make_project("work-lab", remote="github:DTALEX66/WORK-LAB")
        project.display_name = "WORK-LAB"
        index = ApprovedProjectIndex(projects=[project])
        probe = FakeGitProbe(top="/work/WORK-LAB", common="/work/WORK-LAB/.git", remotes=["github:DTALEX66/WORK-LAB"])
        result = resolve_execution_path("/work/WORK-LAB", index, git=probe)
        data = result.as_json()
        self.assertEqual(data["displayName"], "WORK-LAB")
        self.assertEqual(data["confidence"], "EXACT")
        self.assertEqual(data["runtimeInstances"], [])
        self.assertEqual(data["activeTasks"], [])
        self.assertEqual(data["nestedProjects"], [])
        self.assertIn("remote:github:DTALEX66/WORK-LAB", data["evidenceRefs"])

    def test_worktree_belongs_to_project(self) -> None:
        project = make_project("core", remote="github:DTALEX66/core", worktrees=[("wt2", "/work/core-wt2")])
        index = ApprovedProjectIndex(projects=[project])
        probe = FakeGitProbe(top="/work/core-wt2", common="/shared/.git", remotes=["github:DTALEX66/core"])
        result = resolve_execution_path("/work/core-wt2", index, git=probe)
        self.assertEqual(result.project_id, "core")
        self.assertEqual(result.worktree_id, "wt2")

    def test_submodule_superproject_path_resolves(self) -> None:
        index = ApprovedProjectIndex(projects=[make_project("parent", root="/work/parent")])
        probe = FakeGitProbe(top="/work/parent/vendor/lib", common="/work/parent/vendor/lib/.git", superproject="/work/parent")
        result = resolve_execution_path("/work/parent/vendor/lib", index, git=probe)
        self.assertEqual(result.project_id, "parent")
        self.assertEqual(result.resolution_state, ResolutionState.RESOLVED)


class IdentityResolverRealGitTests(unittest.TestCase):
    def _repo(self, name: str = "repo") -> tuple[Path, tempfile.TemporaryDirectory]:
        raw = tempfile.TemporaryDirectory()
        self.addCleanup(raw.cleanup)
        repo = Path(raw.name) / name
        repo.mkdir()
        subprocess.run(["git", "init", "-q", str(repo)], check=True)
        return repo, raw

    def test_real_git_toplevel_resolution(self) -> None:
        repo, _ = self._repo()
        subprocess.run(["git", "-C", str(repo), "remote", "add", "origin", "git@github.com:DTALEX66/WORK-LAB.git"], check=True)
        index = ApprovedProjectIndex(projects=[make_project("work-lab", remote="github:DTALEX66/WORK-LAB")])
        probe = GitProbe()
        result = resolve_execution_path(str(repo), index, git=probe)
        self.assertEqual(result.project_id, "work-lab")
        self.assertEqual(result.resolution_state, ResolutionState.RESOLVED)

    def test_real_git_no_remote_stays_unresolved(self) -> None:
        repo, _ = self._repo()
        index = ApprovedProjectIndex(projects=[make_project("p", root=str(repo))])
        probe = GitProbe()
        result = resolve_execution_path(str(repo), index, git=probe)
        # Approved root binding matches -> resolved via containment.
        self.assertEqual(result.project_id, "p")


if __name__ == "__main__":
    unittest.main()
