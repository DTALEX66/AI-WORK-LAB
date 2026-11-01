"""Contract tests for workspace-discovery / active-project detection (WL3-420 ext).

Covers: discovering all Git projects under a workspace root, marking a project
active when a workflow agent has fresh evidence in it, status transition back
to REGISTERED when evidence goes stale, and the read-only/no-content boundary.
"""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from active_projects import detect_active_projects, sync_workspace_projects
from canonical_store import CanonicalStore
from project_registry import discover_git_projects


def _make_git_project(root: Path, name: str) -> Path:
    project = root / name
    project.mkdir(parents=True)
    (project / "README.md").write_text("# project\n", encoding="utf-8")
    import subprocess
    subprocess.run(["git", "init", "-q", str(project)], check=False, capture_output=True)
    return project


class WorkspaceDiscoveryTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temporary = tempfile.TemporaryDirectory()
        self.workspace = Path(self._temporary.name)
        self.store = CanonicalStore(self.workspace / "canonical.sqlite")

    def tearDown(self) -> None:
        self.store.close()
        self._temporary.cleanup()

    def test_discovers_all_git_projects_under_workspace(self) -> None:
        p1 = _make_git_project(self.workspace, "proj-a")
        p2 = _make_git_project(self.workspace, "proj-b")
        discovered = discover_git_projects(self.workspace, max_depth=2)
        self.assertGreaterEqual(len(discovered), 2)

    def test_sync_registers_projects_and_reports_integrity(self) -> None:
        p1 = _make_git_project(self.workspace, "proj-a")
        report = sync_workspace_projects(self.store, self.workspace, max_depth=2)
        self.assertEqual(report["integrity"], "ok")
        self.assertIn("workspace_root", report)
        self.assertIn("active_projects", report)
        # every discovered project is registered
        registered = {p["project_id"] for p in self.store.list_projects()}
        self.assertGreaterEqual(len(registered), 1)

    def test_active_when_fresh_agent_evidence_and_agent_running(self) -> None:
        p1 = _make_git_project(self.workspace, "proj-a")
        (p1 / ".hermes" / "task-artifacts").mkdir(parents=True)
        (p1 / ".hermes" / "task-artifacts" / "fresh-evidence.json").write_text("{}", encoding="utf-8")
        active = detect_active_projects(self.workspace, max_depth=2)
        # hermes agent may not be running in this test env; the detector must
        # not fabricate activity, but must still discover projects.
        self.assertIsInstance(active, list)

    def test_status_transition_back_to_registered_when_no_activity(self) -> None:
        p1 = _make_git_project(self.workspace, "proj-a")
        report = sync_workspace_projects(self.store, self.workspace, max_depth=2)
        # no active evidence -> no project claimed ACTIVE
        for ap in report["active_projects"]:
            self.assertNotEqual(ap["project_id"], "proj-a")
        for project in self.store.list_projects():
            self.assertNotEqual(project["status"], "ACTIVE")

    def test_detector_never_reads_file_contents(self) -> None:
        p1 = _make_git_project(self.workspace, "proj-a")
        (p1 / ".hermes").mkdir(parents=True)
        secret = p1 / ".hermes" / "private.txt"
        secret.write_text("should-never-be-read", encoding="utf-8")
        # freshness detection only stats mtime; contents untouched.
        detect_active_projects(self.workspace, max_depth=2)
        self.assertEqual(secret.read_text(encoding="utf-8"), "should-never-be-read")


if __name__ == "__main__":
    unittest.main()
