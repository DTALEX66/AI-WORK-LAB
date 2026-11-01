from __future__ import annotations

import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "packages/client-neutral-core/scripts" / "execution_preflight.py"


def load_module():
    spec = importlib.util.spec_from_file_location("execution_preflight", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ExecutionPreflightTests(unittest.TestCase):
    def run_git(self, root: Path, *args: str) -> str:
        result = subprocess.run(
            ["git", "-C", str(root), *args],
            check=True,
            capture_output=True,
            text=True, encoding="utf-8", errors="replace",
        )
        return result.stdout.strip()

    def make_repo(self) -> Path:
        raw = tempfile.TemporaryDirectory()
        self.addCleanup(raw.cleanup)
        root = Path(raw.name) / "repo"
        root.mkdir()
        self.run_git(root, "init", "-q", "-b", "main")
        self.run_git(root, "config", "user.name", "Test User")
        self.run_git(root, "config", "user.email", "test@example.invalid")
        (root / "README.md").write_text("base\n", encoding="utf-8")
        self.run_git(root, "add", "README.md")
        self.run_git(root, "commit", "-q", "-m", "base")
        self.run_git(root, "branch", "origin/main")
        self.run_git(root, "switch", "-q", "-c", "feature")
        (root / "feature.txt").write_text("feature\n", encoding="utf-8")
        self.run_git(root, "add", "feature.txt")
        self.run_git(root, "commit", "-q", "-m", "feature")
        return root

    def test_git_state_separates_current_branch_from_main(self) -> None:
        module = load_module()
        repo = self.make_repo()

        state = module.collect_git_state(repo, main_ref="origin/main")

        self.assertEqual(state["branch"], "feature")
        self.assertFalse(state["head_equals_main"])
        self.assertFalse(state["tree_equals_main"])
        self.assertEqual(state["divergence_from_main"], {"current_only": 1, "main_only": 0})
        self.assertTrue(state["clean"])

    def test_python_state_reports_interpreter_and_missing_optional_modules(self) -> None:
        module = load_module()

        state = module.collect_python_state(["json", "definitely_missing_workflow_module"])

        self.assertEqual(Path(state["executable"]).resolve(), Path(sys.executable).resolve())
        self.assertTrue(state["modules"]["json"])
        self.assertFalse(state["modules"]["definitely_missing_workflow_module"])
        self.assertFalse(state["requirements_satisfied"])

    def test_markdown_links_resolve_from_document_directory(self) -> None:
        module = load_module()
        repo = self.make_repo()
        truth = repo / "docs" / "truth"
        taskpacks = repo / "docs" / "taskpacks"
        truth.mkdir(parents=True)
        taskpacks.mkdir(parents=True)
        (taskpacks / "TASK.md").write_text("task\n", encoding="utf-8")
        handoff = truth / "HANDOFF.md"
        handoff.write_text("[task](../taskpacks/TASK.md)\n", encoding="utf-8")

        passing = module.check_markdown_links(repo, [handoff])
        handoff.write_text("[task](../../taskpacks/TASK.md)\n", encoding="utf-8")
        failing = module.check_markdown_links(repo, [handoff])

        self.assertEqual(passing["issues"], [])
        self.assertEqual(len(failing["issues"]), 1)
        self.assertEqual(failing["issues"][0]["target"], "../../taskpacks/TASK.md")

    def test_strip_ansi_removes_terminal_control_sequences(self) -> None:
        module = load_module()

        self.assertEqual(module.strip_ansi("\x1b[31;1mAccess denied\x1b[0m"), "Access denied")


if __name__ == "__main__":
    unittest.main()