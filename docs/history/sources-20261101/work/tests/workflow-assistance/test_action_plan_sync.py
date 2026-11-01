from __future__ import annotations

import importlib.util
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "integrations/executors/hermes/sync_hermes_workflow_assets.py"
PROJECT_COPY_IGNORE = shutil.ignore_patterns(
    ".git", ".hermes", ".project-local", "node_modules", "__pycache__"
)


def load_module():
    spec = importlib.util.spec_from_file_location("workflow_sync_action_plan", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def make_isolated_roots(raw: str) -> tuple[Path, Path]:
    base = Path(raw)
    repo = base / "repo"
    home = base / "hermes-home"
    shutil.copytree(ROOT, repo, ignore=PROJECT_COPY_IGNORE)
    home.mkdir()
    return repo, home


class ActionPlanSyncTests(unittest.TestCase):
    def test_isolated_copy_excludes_ephemeral_project_data(self) -> None:
        ignored = PROJECT_COPY_IGNORE(
            str(ROOT), [".git", ".hermes", ".project-local", "node_modules", "source.py"]
        )
        self.assertIn(".git", ignored)
        self.assertIn(".hermes", ignored)
        self.assertIn(".project-local", ignored)
        self.assertIn("node_modules", ignored)
        self.assertNotIn("source.py", ignored)

    def test_sync_builds_exact_plan_without_writing_home(self) -> None:
        module = load_module()
        with tempfile.TemporaryDirectory() as raw:
            repo, home = make_isolated_roots(raw)
            plan = module.build_action_plan(repo, home)
            self.assertEqual(plan["schema_version"], "workflow/action-plan/v1")
            self.assertEqual(plan["status"], "WAITING_APPROVAL")
            self.assertTrue(plan["approval"]["approval_required"])
            self.assertTrue(plan["rollback"]["available"])
            targets = {step["target"] for step in plan["steps"]}
            self.assertIn("SOUL.md", targets)
            self.assertIn(".env.template", targets)
            self.assertEqual(plan["config"]["operation"], "skip_mixed_ownership")
            self.assertNotIn("sha256", plan["config"]["before"])
            self.assertFalse(any(home.iterdir()))

    def test_apply_requires_explicit_approval(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            repo, home = make_isolated_roots(raw)
            result = subprocess.run(
                [sys.executable, str(SCRIPT), "--repo", str(repo), "--home", str(home), "--apply"],
                cwd=ROOT,
                text=True, encoding="utf-8", errors="replace",
                capture_output=True,
                check=False,
            )
            self.assertEqual(result.returncode, 2)
            self.assertIn("ACTION_PLAN_BLOCKED", result.stdout)
            self.assertFalse(any(home.iterdir()))

    def test_approved_apply_reads_back_the_planned_state(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            repo, home = make_isolated_roots(raw)
            result = subprocess.run(
                [sys.executable, str(SCRIPT), "--repo", str(repo), "--home", str(home), "--apply", "--approved"],
                cwd=ROOT,
                text=True, encoding="utf-8", errors="replace",
                capture_output=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("ACTION_PLAN_READBACK_PASS", result.stdout)
            self.assertTrue((home / "SOUL.md").is_file())

    def test_approved_apply_does_not_read_or_replace_live_config(self) -> None:
        module = load_module()
        with tempfile.TemporaryDirectory() as raw:
            repo, home = make_isolated_roots(raw)
            live_config = home / "config.yaml"
            original = (
                "model:\n  provider: user-provider\n  default: user-model\n"
                "mcp_servers:\n  user_mcp:\n    command: user-command\n"
                "display:\n  language: en\n  skin: stock\n"
                "  busy_input_mode: immediate\nplugins:\n"
                "  enabled: [user-plugin]\nplatform_toolsets:\n  cli: [terminal]\n"
            )
            live_config.write_text(original, encoding="utf-8")
            module.deploy_portable(
                repo,
                home,
                apply=True,
                include_backup=False,
                allow_project_runtime_home=True,
            )
            self.assertEqual(live_config.read_text(encoding="utf-8"), original)
            self.assertFalse((home / ".workflow-assistance-state.yaml").exists())

    def test_config_merge_preserves_user_plugins_unchanged(self) -> None:
        module = load_module()
        with tempfile.TemporaryDirectory() as raw:
            repo, home = make_isolated_roots(raw)
            live_config = home / "config.yaml"
            live_config.write_text(
                "plugins:\n  enabled: [user-plugin]\n  disabled: [other-plugin]\n",
                encoding="utf-8",
            )
            module.merge_live_config(repo, home, apply=True)
            merged = module.yaml.safe_load(live_config.read_text(encoding="utf-8"))
            self.assertEqual(
                merged["plugins"],
                {"enabled": ["user-plugin"], "disabled": ["other-plugin"]},
            )
            self.assertFalse((home / ".workflow-assistance-state.yaml").exists())


    def test_readback_rejects_source_mutation_after_plan(self) -> None:
        module = load_module()
        with tempfile.TemporaryDirectory() as raw:
            repo, home = make_isolated_roots(raw)
            plan = module.build_action_plan(repo, home)
            soul = repo / "config/SOUL.md"
            soul.write_text(soul.read_text(encoding="utf-8") + "\nmutation-after-plan\n", encoding="utf-8")
            module.deploy_portable(
                repo,
                home,
                apply=True,
                include_backup=False,
                allow_project_runtime_home=True,
            )
            with self.assertRaisesRegex(RuntimeError, "SOUL.md"):
                module.verify_action_plan_readback(plan, repo, home)

    def test_plan_output_rejects_external_path(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            repo, home = make_isolated_roots(raw)
            output = Path(raw) / "outside.json"
            result = subprocess.run(
                [sys.executable, str(SCRIPT), "--repo", str(repo), "--home", str(home), "--plan-json", str(output)],
                cwd=ROOT,
                text=True, encoding="utf-8", errors="replace",
                capture_output=True,
                check=False,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("must stay inside", result.stdout + result.stderr)
            self.assertFalse(output.exists())

    def test_plan_fails_closed_when_a_managed_target_crosses_a_reparse_path(self) -> None:
        module = load_module()
        with tempfile.TemporaryDirectory() as raw:
            repo, home = make_isolated_roots(raw)
            managed_target = home / "skills/github/github-auth"

            real_check = module._is_link_or_reparse

            def marks_managed_target(path: Path) -> bool:
                return path == managed_target or real_check(path)

            with patch.object(module, "_is_link_or_reparse", side_effect=marks_managed_target):
                with self.assertRaisesRegex(ValueError, "symlink or junction"):
                    module.build_action_plan(repo, home)

    def test_plan_rejects_real_symlinked_managed_parent_when_supported(self) -> None:
        module = load_module()
        with tempfile.TemporaryDirectory() as raw:
            repo, home = make_isolated_roots(raw)
            external = Path(raw) / "external-skills"
            external.mkdir()
            skills = home / "skills"
            try:
                os.symlink(external, skills, target_is_directory=True)
            except OSError as exc:
                self.skipTest(f"symlink creation unavailable on this Windows host: {exc}")
            # A creation call that SUCCEEDS is not proof of a link. Measured on this host (2026-07-12):
            # symlink creation returned without raising on both NTFS volumes and left a plain directory
            # behind -- lstat reports FILE_ATTRIBUTE_DIRECTORY (0x10) and no FILE_ATTRIBUTE_REPARSE_POINT
            # (0x400). Skipping states that the premise could not be built; it does not excuse the check,
            # which runs everywhere a real link can be made.
            if not skills.is_symlink() and not (getattr(skills.lstat(), "st_file_attributes", 0) & 0x0400):
                self.skipTest("this filesystem downgrades symlink creation to a plain directory, "
                              "so a symlinked managed parent cannot be constructed here")

            with self.assertRaisesRegex(ValueError, "symlink or junction"):
                module.build_action_plan(repo, home)

    def test_unfenced_retired_asset_blocks_without_deleting_user_content(self) -> None:
        module = load_module()
        with tempfile.TemporaryDirectory() as raw:
            repo, home = make_isolated_roots(raw)
            retired = home / "skills/model-switch/references/oauth-credential-sync.md"
            retired.parent.mkdir(parents=True)
            retired.write_text("user-content", encoding="utf-8")

            with self.assertRaisesRegex(RuntimeError, "retired_asset_ownership_unproven"):
                module.deploy_portable(
                    repo,
                    home,
                    apply=True,
                    include_backup=False,
                    allow_project_runtime_home=True,
                )

            self.assertEqual(retired.read_text(encoding="utf-8"), "user-content")
            self.assertFalse((home / "SOUL.md").exists())


if __name__ == "__main__":
    unittest.main()
