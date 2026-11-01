"""Contract tests for cross-project registry and minimal profiles (WL3-420)."""

from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from canonical_store import CanonicalStore
from project_registry import (
    DEFAULT_FORBIDDEN,
    build_minimal_profile,
    discover_and_register,
    discover_git_projects,
    load_project_profiles,
    register_discovered,
)

from project_registry import DiscoveredProject, _inspect


def _make_git_project(root: Path, name: str) -> Path:
    project = root / name
    project.mkdir(parents=True)
    (project / "README.md").write_text(f"# {name}\n", encoding="utf-8")
    subprocess.run(["git", "init", "-q"], cwd=project, check=True)
    subprocess.run(["git", "add", "-A"], cwd=project, check=True)
    subprocess.run(
        ["git", "-c", "user.email=test@example.com", "-c", "user.name=test", "commit", "-qm", "init"],
        cwd=project,
        check=True,
    )
    return project


class ProjectRegistryTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temporary = tempfile.TemporaryDirectory()
        self.root = Path(self._temporary.name)
        self.store = CanonicalStore(self.root / "canonical.sqlite")

    def tearDown(self) -> None:
        self.store.close()
        self._temporary.cleanup()

    def test_discovers_git_projects_without_descending_into_repos(self) -> None:
        _make_git_project(self.root, "alpha")
        inner = self.root / "beta" / "nested"
        inner.mkdir(parents=True)
        (inner / "inner.txt").write_text("inner\n", encoding="utf-8")
        subprocess.run(["git", "init", "-q"], cwd=inner, check=True)
        subprocess.run(["git", "add", "-A"], cwd=inner, check=True)
        subprocess.run(
            ["git", "-c", "user.email=test@example.com", "-c", "user.name=test", "commit", "-qm", "init"],
            cwd=inner,
            check=True,
        )
        found = discover_git_projects(self.root, max_depth=2)
        ids = {item.project_id for item in found}
        self.assertIn("alpha", ids)
        self.assertIn("nested", ids)
        # Must not duplicate by descending into an existing repo.
        self.assertEqual(len(found), len(ids))

    def test_minimal_profile_has_no_secrets_and_standalone_fallback(self) -> None:
        project = _make_git_project(self.root, "demo")
        inspected = _inspect(project)
        profile = build_minimal_profile(inspected)
        self.assertEqual(profile["schema_version"], "workflow/project-profile/v1")
        self.assertEqual(profile["release_policy"], "EXPLICIT_APPROVAL")
        self.assertTrue(profile["standalone_fallback"])
        self.assertFalse(profile["work_lab_runtime_copied"])
        self.assertEqual(set(profile["forbidden_paths"]), set(DEFAULT_FORBIDDEN))
        serialized = json.dumps(profile, ensure_ascii=False)
        for fragment in ("token", "secret", "apikey", "password"):
            self.assertNotIn(fragment.lower(), serialized.lower())
        # The forbidden drive is present as a policy, not as a secret leak.
        self.assertIn("e:", serialized.lower())

    def test_register_and_readback_via_canonical_store(self) -> None:
        project = _make_git_project(self.root, "registry-demo")
        inspected = _inspect(project)
        profile = register_discovered(self.store, inspected)
        self.assertIn("project_id", profile)
        projects = load_project_profiles(self.store)
        self.assertIn("registry-demo", projects)

    def test_discover_and_register_pipeline(self) -> None:
        _make_git_project(self.root, "pipeline-a")
        _make_git_project(self.root, "pipeline-b")
        profiles = discover_and_register(self.store, self.root, max_depth=2)
        self.assertEqual(len(profiles), 2)
        self.assertEqual(len(self.store.list_projects()), 2)


if __name__ == "__main__":
    unittest.main()
