"""NF-03-SYNC: config-driven project onboarding + local path binding.

Proves the acceptance rows for AT-05 / AT-06 / AT-07:
  * three projects on-boarded by config only, the third one a non-Git
    artifact project, with no new branch in the core code;
  * a same display name on different project_ids is reported, never merged;
  * an unknown project_id is UNKNOWN (shown as "not connected"), not a crash;
  * a cloud task carrying its own absolute path is REJECTED — the local root
    always comes from the user-approved binding only.

Loaded by file path (NF-02 convention).  No filesystem, Git, or network.
"""
from __future__ import annotations

import importlib.util
import os
import sys
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
MOD_PATH = os.path.join(
    ROOT, "packages", "client-neutral-core", "scripts", "project_binding_registry.py"
)


def _load(name: str, path: str):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


PBR = _load("nf03_pbr", MOD_PATH)


def _three_projects():
    """Two Git projects + one non-Git artifact project, config-only."""
    return [
        {"project_id": "proj-a", "display_name": "Alpha", "base_kind": "git",
         "repository_id": "repo-a", "material_root": "alpha-materials"},
        {"project_id": "proj-b", "display_name": "Beta", "base_kind": "git",
         "repository_id": "repo-b", "material_root": "beta-materials"},
        {"project_id": "proj-docs", "display_name": "Docs", "base_kind": "artifact",
         "artifact_revision": "v3", "material_root": "docs-materials"},
    ]


class ConfigOnboardingTests(unittest.TestCase):
    def test_three_projects_onboarded_by_config_only(self):
        reg = PBR.ProjectBindingRegistry(_three_projects())
        for pid in ("proj-a", "proj-b", "proj-docs"):
            self.assertTrue(reg.is_onboarded(pid), pid)
        # core code has no branch keyed to a specific project name: identity
        # is the opaque project_id, and repo association is optional data.
        self.assertEqual(reg.project("proj-a").project_id, "proj-a")
        self.assertEqual(reg.project("proj-a").repository_id, "repo-a")

    def test_non_git_project_uses_artifact_baseline(self):
        reg = PBR.ProjectBindingRegistry(_three_projects())
        res = reg.artifact_baseline("proj-docs")
        self.assertEqual(res["base_kind"], "artifact")
        self.assertEqual(res["revision"], "v3")
        self.assertTrue(res["digest"])

    def test_git_project_does_not_use_content_hash(self):
        reg = PBR.ProjectBindingRegistry(_three_projects())
        res = reg.artifact_baseline("proj-a")
        self.assertEqual(res["base_kind"], "git")
        self.assertNotIn("digest", res)

    def test_artifact_project_requires_revision(self):
        with self.assertRaises(ValueError):
            PBR.ProjectOnboarding(project_id="x", base_kind="artifact").validate()


class SameNameDifferentProjectTests(unittest.TestCase):
    def test_same_display_name_not_merged(self):
        reg = PBR.ProjectBindingRegistry([
            {"project_id": "p1", "display_name": "Alpha"},
            {"project_id": "p2", "display_name": "Alpha"},
        ])
        collisions = reg.detect_name_collisions()
        self.assertIn("Alpha", collisions)
        # both ids remain independently resolvable, untouched
        self.assertTrue(reg.is_onboarded("p1") and reg.is_onboarded("p2"))

    def test_no_collision_when_names_differ(self):
        reg = PBR.ProjectBindingRegistry([
            {"project_id": "p1", "display_name": "Alpha"},
            {"project_id": "p2", "display_name": "Beta"},
        ])
        self.assertEqual(reg.detect_name_collisions(), [])


class UnknownProjectTests(unittest.TestCase):
    def test_unknown_project_id_is_unknown_not_crash(self):
        reg = PBR.ProjectBindingRegistry(_three_projects())
        res = reg.resolve_local_root("never-connected")
        self.assertEqual(res["status"], "UNKNOWN")
        self.assertIn("not connected", res["note"])

    def test_unknown_id_has_no_material_placement(self):
        reg = PBR.ProjectBindingRegistry(_three_projects())
        self.assertIsNone(reg.project("ghost"))

    def test_binding_an_unboarded_project_fails_closed(self):
        reg = PBR.ProjectBindingRegistry(_three_projects())
        with self.assertRaises(KeyError):
            reg.bind_local_root("ghost", "C:/x")


class LocalBindingSecurityTests(unittest.TestCase):
    def test_local_root_resolved_only_from_binding(self):
        reg = PBR.ProjectBindingRegistry(_three_projects())
        reg.bind_local_root("proj-a", "C:/Users/ALEX/alpha")
        res = reg.resolve_local_root("proj-a")
        self.assertEqual(res["status"], "RESOLVED")
        self.assertEqual(res["root"], "C:/Users/ALEX/alpha")

    def test_remote_claim_cannot_repoint_project(self):
        reg = PBR.ProjectBindingRegistry(_three_projects())
        reg.bind_local_root("proj-a", "C:/Users/ALEX/alpha")
        # cloud task claims the project is at a different absolute path
        res = reg.resolve_with_remote_claim("proj-a", remote_claimed_path="C:/other/place")
        self.assertEqual(res["status"], "RESOLVED")
        self.assertEqual(res["root"], "C:/Users/ALEX/alpha")  # local binding wins
        self.assertEqual(res["remote_claim"], "REJECTED")

    def test_remote_claim_matching_binding_is_reported(self):
        reg = PBR.ProjectBindingRegistry(_three_projects())
        reg.bind_local_root("proj-a", "C:/Users/ALEX/alpha")
        res = reg.resolve_with_remote_claim("proj-a", remote_claimed_path="C:/Users/ALEX/alpha")
        self.assertEqual(res["remote_claim"], "MATCHES_LOCAL_BINDING")

    def test_relative_or_non_local_binding_rejected(self):
        reg = PBR.ProjectBindingRegistry(_three_projects())
        with self.assertRaises(ValueError):
            reg.bind_local_root("proj-a", "relative/path")

    def test_onboarded_but_unbound_is_unbound(self):
        reg = PBR.ProjectBindingRegistry(_three_projects())
        res = reg.resolve_local_root("proj-b")  # never bound
        self.assertEqual(res["status"], "UNBOUND")


class DuplicateProjectIdTests(unittest.TestCase):
    def test_duplicate_project_id_rejected(self):
        with self.assertRaises(ValueError):
            PBR.ProjectBindingRegistry([
                {"project_id": "dup"}, {"project_id": "dup"},
            ])


if __name__ == "__main__":
    unittest.main(verbosity=2)
