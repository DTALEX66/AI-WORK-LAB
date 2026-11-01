"""WLGM-010 tests: product project domain model."""
from __future__ import annotations

import unittest

from product_project import (
    BindingKind,
    ProductProject,
    ProjectRootBinding,
    RepositoryIdentity,
    RepositoryRole,
    SubmodulePolicy,
    WorktreeIdentity,
    normalize_remote_identity,
)


class ProductProjectModelTests(unittest.TestCase):
    def test_frontend_backend_docs_are_not_projects(self) -> None:
        """Module dirs are working areas, not projects."""
        project = ProductProject(project_id="web-app")
        module_ids = {"frontend", "backend", "docs"}
        for name in module_ids:
            project.modules.append(__import__("product_project").ModuleIdentity(
                module_id=name,
                repository_id="web-app",
                relative_path=name,
            ))
        # No ModuleIdentity may be promoted to a ProductProject.
        self.assertEqual(len(project.root_bindings), 0)
        self.assertTrue(all(m.repository_id == "web-app" for m in project.modules))

    def test_one_repo_many_worktrees_belong_to_one_project(self) -> None:
        project = ProductProject(project_id="core")
        project.add_repository(RepositoryIdentity(repository_id="core-repo", remote_identity="github:DTALEX66/core"))
        for suffix in ("", "-wt2"):
            project.worktrees.append(WorktreeIdentity(
                worktree_id=f"wt{suffix or '-1'}",
                repository_id="core-repo",
                root=f"/work/{project.project_id}{suffix}",
            ))
        self.assertEqual(len({w.repository_id for w in project.worktrees}), 1)
        self.assertEqual(len(project.worktrees), 2)

    def test_submodule_attach_policy_default(self) -> None:
        project = ProductProject(project_id="mono")
        self.assertEqual(project.submodule_policy, SubmodulePolicy.ATTACH_TO_PARENT)

    def test_unapproved_project_has_no_collector_rights(self) -> None:
        project = ProductProject(project_id="candidate")
        self.assertFalse(project.approved)
        self.assertEqual(project.include_policy, "explicit")

    def test_root_binding_dedupes_normalized_roots(self) -> None:
        project = ProductProject(project_id="p")
        project.add_root_binding(ProjectRootBinding(binding_id="b1", project_id="p", root="D:\\All projects\\WORK-LAB"))
        project.add_root_binding(ProjectRootBinding(binding_id="b2", project_id="p", root="D:/All projects/WORK-LAB/"))
        self.assertEqual(len(project.root_bindings), 1)
        self.assertTrue(project.has_root("d:/all projects/work-lab"))

    def test_definition_roundtrip_portable(self) -> None:
        project = ProductProject(project_id="work-lab", display_name="WORK-LAB")
        project.add_repository(RepositoryIdentity(
            repository_id="work-lab",
            remote_identity="github:DTALEX66/WORK-LAB",
            role=RepositoryRole.PRIMARY,
        ))
        rebuilt = ProductProject.from_definition(project.to_definition())
        self.assertEqual(rebuilt.project_id, "work-lab")
        self.assertEqual(rebuilt.remote_identities, project.remote_identities)
        self.assertEqual(rebuilt.repositories[0].remote_identity, "github:DTALEX66/WORK-LAB")
        self.assertNotIn("root_bindings", project.to_definition())  # machine paths never versioned

    def test_normalize_remote_identity(self) -> None:
        self.assertEqual(normalize_remote_identity("git@github.com:DTALEX66/WORK-LAB.git"), "github:DTALEX66/WORK-LAB")
        self.assertEqual(normalize_remote_identity("https://github.com/DTALEX66/WORK-LAB"), "github:DTALEX66/WORK-LAB")
        self.assertIsNone(normalize_remote_identity(""))


if __name__ == "__main__":
    unittest.main()
