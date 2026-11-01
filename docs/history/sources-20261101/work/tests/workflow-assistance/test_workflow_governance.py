from __future__ import annotations

import importlib.util
import contextlib
import errno
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml


ROOT = Path(__file__).resolve().parents[2]


class WorkflowGovernanceTests(unittest.TestCase):
    def require_posix_anonymous_staging(self, home: Path) -> None:
        """Skip POSIX staging-race tests when the current filesystem lacks O_TMPFILE."""
        if os.name == "nt":
            return
        anonymous_flag = getattr(os, "O_TMPFILE", 0)
        if not anonymous_flag:
            self.skipTest("current POSIX runtime does not expose O_TMPFILE")
        directory_fd = os.open(home, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        descriptor: int | None = None
        try:
            descriptor = os.open(".", os.O_RDWR | anonymous_flag, 0o600, dir_fd=directory_fd)
        except OSError as error:
            self.skipTest(f"current filesystem does not support O_TMPFILE: errno={error.errno}")
        finally:
            if descriptor is not None:
                os.close(descriptor)
            os.close(directory_fd)

    def test_portable_package_declares_config_ownership_and_compatibility(self) -> None:
        ownership_path = ROOT / "config/managed-config-schema.yaml"
        manifest_path = ROOT / "packages/client-neutral-core/workflow-manifest.yaml"
        self.assertTrue(ownership_path.exists())
        self.assertTrue(manifest_path.exists())

        ownership = yaml.safe_load(ownership_path.read_text(encoding="utf-8"))
        manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(ownership["schema_version"], 1)
        self.assertEqual(ownership["authority"], "config/config-ownership.json")
        self.assertEqual(ownership["compatibility_scope"], "isolated-empty-home")
        self.assertEqual(ownership["global_workflow"]["deployment"], "isolated-empty-home-only")
        for forbidden in (
            "model.max_tokens",
            "agent.reasoning_effort",
            "model_picker.custom_lanes",
            "quick_commands",
        ):
            self.assertNotIn(forbidden, ownership["managed"])
        self.assertEqual(ownership["managed"]["platform_toolsets.cli"], "replace")
        self.assertEqual(ownership["managed"]["sessions.auto_prune"], "replace")
        self.assertEqual(ownership["global_workflow"]["source_of_truth"], "repository")
        owned_roots = ownership["global_workflow"]["owned_asset_roots"]
        self.assertEqual(len(owned_roots), 13)
        self.assertIn("packages/client-neutral-core/skills/github/github-auth", owned_roots)
        self.assertNotIn("packages/client-neutral-core/skills/github", owned_roots)
        self.assertNotIn("packages/client-neutral-core/skills/software-development", owned_roots)
        owned_binaries = ownership["global_workflow"]["owned_binary_paths"]
        self.assertEqual(len(owned_binaries), 6)
        self.assertIn("packages/client-neutral-core/bin/codex", owned_binaries)
        self.assertNotIn("bin", owned_binaries)
        owned_file_mappings = ownership["global_workflow"]["owned_file_mappings"]
        self.assertEqual(
            owned_file_mappings,
            [{"source": "config/SOUL.md", "target": "SOUL.md"}],
        )
        self.assertIn("model.provider", ownership["preserved"])
        self.assertIn("model.api_key", ownership["preserved"])
        self.assertEqual(manifest["schema_version"], 1)
        self.assertIn("portable_config", manifest["capabilities"])
        self.assertNotIn("custom_model_lanes", manifest["capabilities"])
        self.assertNotIn("quick_model_commands", manifest["capabilities"])

    def test_portable_install_verifier_accepts_isolated_empty_home(self) -> None:
        script = ROOT / "packages/client-neutral-core/scripts/verify_portable_install.py"
        self.assertTrue(script.exists())
        runtime = ROOT / ".hermes" / "task-runtime" / "portable-install"
        runtime.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=runtime) as raw:
            home = Path(raw) / "isolated-home"
            result = subprocess.run(
                [sys.executable, str(script), "--repo", str(ROOT), "--home", str(home)],
                text=True, encoding="utf-8", errors="replace",
                capture_output=True,
                check=False,
            )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("STRUCTURAL_PORTABLE_PASS", result.stdout)

    def test_windows_codex_launchers_share_the_store_runtime_owner(self) -> None:
        bash_launcher = (ROOT / "packages/client-neutral-core/bin/codex").read_text(encoding="utf-8")
        cmd_launcher = (ROOT / "packages/client-neutral-core/bin/codex.cmd").read_text(encoding="utf-8")
        runner = (ROOT / "services/orchestration/run_taskpack_agent.py").read_text(encoding="utf-8")
        self.assertIn("Get-AppxPackage -Name OpenAI.Codex", bash_launcher)
        self.assertIn("Get-AppxPackage -Name OpenAI.Codex", cmd_launcher)
        self.assertIn("app/resources/codex.exe", bash_launcher)
        self.assertIn("app\\resources\\codex.exe", cmd_launcher)
        self.assertLess(
            runner.index("AppData/Local/OpenAI/Codex/bin/codex.exe"),
            runner.index(".codex/plugins/.plugin-appserver/codex.exe"),
        )

    def test_codex_runner_discovers_current_exec_flags_without_user_layer_bypass(self) -> None:
        script = ROOT / "services/orchestration/run_taskpack_agent.py"
        spec = importlib.util.spec_from_file_location("workflow_taskpack_runner", script)
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)

        help_output = """
          -s, --sandbox <SANDBOX_MODE>
              --ephemeral
              --output-last-message <FILE>
              --output-schema <FILE>
              --ignore-user-config
              --ignore-rules
        """
        completed = subprocess.CompletedProcess(
            ["codex", "exec", "--help"], 0, stdout=help_output, stderr=""
        )
        with patch("subprocess.run", return_value=completed) as run:
            flags = module.discover_codex_exec_flags("codex", env={"HERMES_PROJECT_ROOT": str(ROOT)})

        self.assertTrue({"sandbox", "ephemeral", "output-last-message", "output-schema"} <= flags)
        self.assertIn(["codex", "exec", "--help"], [call.args[0] for call in run.call_args_list])

    def test_portable_deployment_copies_exact_owned_root_file_mappings(self) -> None:
        script = ROOT / "integrations/executors/hermes/sync_hermes_workflow_assets.py"
        spec = importlib.util.spec_from_file_location("workflow_sync_root_files", script)
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        with tempfile.TemporaryDirectory() as raw:
            raw_path = Path(raw)
            repo = raw_path / "repo"
            home = raw_path / "home"
            for directory in (
                "config",
                "packages/client-neutral-core/skills",
                "packages/client-neutral-core/bin",
            ):
                shutil.copytree(ROOT / directory, repo / directory)
            home.mkdir()

            module.deploy_portable(
                repo,
                home,
                apply=True,
                include_backup=False,
                allow_project_runtime_home=True,
            )

            self.assertEqual(
                (home / "SOUL.md").read_bytes(),
                (repo / "config/SOUL.md").read_bytes(),
            )

    def test_sync_rejects_managed_file_mapping_outside_the_soul_allowlist(self) -> None:
        script = ROOT / "integrations/executors/hermes/sync_hermes_workflow_assets.py"
        spec = importlib.util.spec_from_file_location("workflow_sync_mapping_allowlist", script)
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        with tempfile.TemporaryDirectory() as raw:
            repo = Path(raw) / "repo"
            shutil.copytree(ROOT / "config", repo / "config")
            schema = repo / "config/managed-config-schema.yaml"
            contract = yaml.safe_load(schema.read_text(encoding="utf-8"))
            contract["global_workflow"]["owned_file_mappings"] = [
                {"source": "config/SOUL.md", "target": "auth.json"}
            ]
            schema.write_text(yaml.safe_dump(contract, sort_keys=False), encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "approved managed file mapping"):
                module.load_managed_file_mappings(repo)

    def test_portable_install_verifier_marks_runtime_compatibility_unverified_by_default(self) -> None:
        script = ROOT / "packages/client-neutral-core/scripts/verify_portable_install.py"
        runtime = ROOT / ".hermes" / "task-runtime" / "portable-install"
        runtime.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=runtime) as raw:
            home = Path(raw) / "isolated-home"
            result = subprocess.run(
                [sys.executable, str(script), "--repo", str(ROOT), "--home", str(home)],
                text=True, encoding="utf-8", errors="replace",
                capture_output=True,
                check=False,
            )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("STRUCTURAL_PORTABLE_PASS", result.stdout)
        self.assertIn("RUNTIME_COMPATIBILITY_UNVERIFIED", result.stdout)

    def test_portable_install_verifier_enforces_manifest_and_context7_wrapper_contract(self) -> None:
        script = ROOT / "packages/client-neutral-core/scripts/verify_portable_install.py"
        spec = importlib.util.spec_from_file_location("portable_install_verify", script)
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        runtime = ROOT / ".hermes" / "task-runtime" / "portable-install"
        runtime.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=runtime) as raw:
            checks = module.verify(ROOT, Path(raw) / "isolated-home")

        self.assertIn("manifest.capability_discovery", checks)
        self.assertIn("manifest.required_runtime_features", checks)
        self.assertIn("context7.wrapper", checks)

        self.assertTrue(module.has_pinned_context7_package(["-y", "@upstash/context7-mcp@3.2.2"]))
        self.assertFalse(module.has_pinned_context7_package(["-y", "@upstash/context7-mcp"]))
        self.assertFalse(module.has_pinned_context7_package(["-y", "@upstash/context7-mcp@latest"]))
        self.assertFalse(module.has_pinned_context7_package(["-y", "@other/context7-mcp@1.0.0"]))

    def test_portable_runtime_verifier_uses_only_isolated_home_and_fails_closed(self) -> None:
        script = ROOT / "packages/client-neutral-core/scripts/verify_portable_install.py"
        spec = importlib.util.spec_from_file_location("portable_install_runtime", script)
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        with tempfile.TemporaryDirectory() as raw:
            home = Path(raw) / "isolated-home"
            home.mkdir()
            with patch.object(module.shutil, "which", return_value="fake-hermes"):
                with patch.object(
                    module.subprocess,
                    "run",
                    return_value=subprocess.CompletedProcess(["fake-hermes"], 0, "ok", ""),
                ) as run:
                    module.run_isolated_hermes_config_check(home)
            self.assertEqual(run.call_args.args[0], ["fake-hermes", "config", "check"])
            self.assertEqual(run.call_args.kwargs["cwd"], home)
            self.assertEqual(run.call_args.kwargs["env"]["HERMES_HOME"], str(home))

            with patch.object(module.shutil, "which", return_value=None):
                with self.assertRaisesRegex(RuntimeError, "executable"):
                    module.run_isolated_hermes_config_check(home)

            with patch.object(module.shutil, "which", return_value="fake-hermes"):
                with patch.object(
                    module.subprocess,
                    "run",
                    return_value=subprocess.CompletedProcess(["fake-hermes"], 1, "", "failed"),
                ):
                    with self.assertRaisesRegex(RuntimeError, "config check failed"):
                        module.run_isolated_hermes_config_check(home)

    def test_portable_install_verifier_rejects_nonempty_home_without_writing(self) -> None:
        script = ROOT / "packages/client-neutral-core/scripts/verify_portable_install.py"
        spec = importlib.util.spec_from_file_location("portable_install_nonempty", script)
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        runtime = ROOT / ".hermes" / "task-runtime" / "portable-install"
        runtime.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=runtime) as raw:
            home = Path(raw) / "isolated-home"
            home.mkdir()
            sentinel = home / "sentinel.txt"
            sentinel.write_text("keep", encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "empty"):
                module.verify(ROOT, home)
            self.assertEqual(sentinel.read_text(encoding="utf-8"), "keep")

    def test_portable_install_verifier_rejects_uncontrolled_empty_home_without_writing(self) -> None:
        script = ROOT / "packages/client-neutral-core/scripts/verify_portable_install.py"
        spec = importlib.util.spec_from_file_location("portable_install_outside_runtime", script)
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        with tempfile.TemporaryDirectory() as raw:
            home = Path(raw) / "isolated-home"
            with self.assertRaisesRegex(RuntimeError, "project runtime root"):
                module.verify(ROOT, home)
            self.assertFalse(home.exists())

    def test_sync_rejects_repo_and_hermes_home_path_overlap_before_writing(self) -> None:
        script = ROOT / "integrations/executors/hermes/sync_hermes_workflow_assets.py"
        spec = importlib.util.spec_from_file_location("workflow_sync_overlap", script)
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        with tempfile.TemporaryDirectory() as raw:
            repo = Path(raw) / "repo"
            repo.mkdir()
            home = repo / "hermes-home"
            home.mkdir()
            with self.assertRaisesRegex(ValueError, "non-overlapping"):
                module.deploy_portable(repo, home, apply=False, include_backup=False)

    def test_project_bootstrap_dry_run_is_non_destructive_and_lists_outputs(self) -> None:
        script = ROOT / "services/orchestration/bootstrap_project.py"
        self.assertTrue(script.exists())
        with tempfile.TemporaryDirectory() as raw:
            target = Path(raw) / "new-project"
            target.mkdir()
            (target / ".gitignore").write_text(".hermes/\n.project-local/\n", encoding="utf-8")
            subprocess.run(["git", "init", "-q", str(target)], check=True)
            result = subprocess.run(
                [sys.executable, str(script), str(target), "--dry-run"],
                text=True, encoding="utf-8", errors="replace",
                capture_output=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("BOOTSTRAP_DRY_RUN", result.stdout)
            self.assertFalse((target / ".hermes").exists())

    def test_project_bootstrap_can_add_agent_rules_without_overwriting_existing_rules(self) -> None:
        script = ROOT / "services/orchestration/bootstrap_project.py"
        with tempfile.TemporaryDirectory() as raw:
            target = Path(raw) / "new-project"
            target.mkdir()
            (target / ".gitignore").write_text(".hermes/\n.project-local/\n", encoding="utf-8")
            subprocess.run(["git", "init", "-q", str(target)], check=True)

            created = subprocess.run(
                [sys.executable, str(script), str(target), "--agent-rules"],
                text=True, encoding="utf-8", errors="replace",
                capture_output=True,
                check=False,
            )
            self.assertEqual(created.returncode, 0, created.stdout + created.stderr)
            self.assertIn("AGENTS.md", created.stdout)
            self.assertIn("Agent Rules", (target / "AGENTS.md").read_text(encoding="utf-8"))

            (target / "AGENTS.md").write_text("# existing rules\n", encoding="utf-8")
            rerun = subprocess.run(
                [sys.executable, str(script), str(target), "--agent-rules"],
                text=True, encoding="utf-8", errors="replace",
                capture_output=True,
                check=False,
            )
            self.assertEqual(rerun.returncode, 0, rerun.stdout + rerun.stderr)
            self.assertEqual((target / "AGENTS.md").read_text(encoding="utf-8"), "# existing rules\n")

    def test_project_bootstrap_preserves_existing_project_runtime_metadata(self) -> None:
        script = ROOT / "services/orchestration/bootstrap_project.py"
        with tempfile.TemporaryDirectory() as raw:
            target = Path(raw) / "existing-project"
            runtime = target / ".hermes"
            runtime.mkdir(parents=True)
            (target / ".gitignore").write_text(".hermes/\n.project-local/\n", encoding="utf-8")
            subprocess.run(["git", "init", "-q", str(target)], check=True)
            readme = runtime / "README.md"
            manifest = runtime / "BOOTSTRAP_MANIFEST.yaml"
            readme.write_text("# project-specific runtime notes\n", encoding="utf-8")
            manifest.write_text("source: project-specific\n", encoding="utf-8")

            result = subprocess.run(
                [sys.executable, str(script), str(target)],
                text=True, encoding="utf-8", errors="replace",
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(readme.read_text(encoding="utf-8"), "# project-specific runtime notes\n")
            self.assertEqual(manifest.read_text(encoding="utf-8"), "source: project-specific\n")

    def test_codex_global_guidance_install_is_non_destructive_and_respects_override(self) -> None:
        script = ROOT / "integrations/executors/codex/install_codex_global_guidance.py"
        self.assertTrue(script.exists())
        with tempfile.TemporaryDirectory() as raw:
            home = Path(raw) / ".codex"
            home.mkdir()
            self.require_posix_anonymous_staging(home)
            dry_run = subprocess.run(
                [sys.executable, str(script), "--codex-home", str(home)],
                text=True, encoding="utf-8", errors="replace",
                capture_output=True,
                check=False,
            )
            self.assertEqual(dry_run.returncode, 0, dry_run.stdout + dry_run.stderr)
            self.assertIn("CODEX_GUIDANCE_READY", dry_run.stdout)
            self.assertFalse((home / "AGENTS.md").exists())

            created = subprocess.run(
                [sys.executable, str(script), "--codex-home", str(home), "--apply"],
                text=True, encoding="utf-8", errors="replace",
                capture_output=True,
                check=False,
            )
            self.assertEqual(created.returncode, 0, created.stdout + created.stderr)
            self.assertIn("CODEX_GUIDANCE_WRITTEN", created.stdout)
            self.assertIn("Global Codex baseline", (home / "AGENTS.md").read_text(encoding="utf-8"))

            existing = subprocess.run(
                [sys.executable, str(script), "--codex-home", str(home), "--apply"],
                text=True, encoding="utf-8", errors="replace",
                capture_output=True,
                check=False,
            )
            self.assertEqual(existing.returncode, 0, existing.stdout + existing.stderr)
            self.assertIn("CODEX_GUIDANCE_EXISTS", existing.stdout)

            (home / "AGENTS.override.md").write_text("# user override\n", encoding="utf-8")
            override = subprocess.run(
                [sys.executable, str(script), "--codex-home", str(home), "--apply"],
                text=True, encoding="utf-8", errors="replace",
                capture_output=True,
                check=False,
            )
            self.assertEqual(override.returncode, 0, override.stdout + override.stderr)
            self.assertIn("CODEX_GUIDANCE_BLOCKED_OVERRIDE", override.stdout)

    def test_codex_global_guidance_returns_nonzero_for_override_after_publication(self) -> None:
        script = ROOT / "integrations/executors/codex/install_codex_global_guidance.py"
        spec = importlib.util.spec_from_file_location("codex_guidance_late_override", script)
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        with tempfile.TemporaryDirectory() as raw:
            home = Path(raw) / ".codex"
            home.mkdir()
            self.require_posix_anonymous_staging(home)
            override = home / "AGENTS.override.md"
            real_publish = module.publish_private_staging

            def publish_then_create_override(*args: object) -> None:
                real_publish(*args)
                override.write_text("# user override\n", encoding="utf-8")

            with patch.object(module, "publish_private_staging", side_effect=publish_then_create_override):
                result = module.main(["--codex-home", str(home), "--apply"])

            self.assertEqual(result, 1)
            self.assertTrue(override.is_file())
            if os.name == "nt":
                self.assertFalse((home / "AGENTS.md").exists())

    def test_codex_global_guidance_apply_does_not_overwrite_a_concurrent_user_file(self) -> None:
        script = ROOT / "integrations/executors/codex/install_codex_global_guidance.py"
        spec = importlib.util.spec_from_file_location("codex_guidance_atomic", script)
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        with tempfile.TemporaryDirectory() as raw:
            home = Path(raw) / ".codex"
            home.mkdir()
            target = home / "AGENTS.md"
            real_plan = module.plan
            plan_calls = 0

            def ready_then_user_creates_file(_codex_home: Path) -> tuple[int, str, Path]:
                nonlocal plan_calls
                plan_calls += 1
                if plan_calls == 1:
                    target.write_text("# user rules\n", encoding="utf-8")
                    return 0, "CODEX_GUIDANCE_READY", target
                return real_plan(_codex_home)

            with patch.object(module, "plan", side_effect=ready_then_user_creates_file):
                self.assertEqual(module.main(["--codex-home", str(home), "--apply"]), 0)

            self.assertEqual(plan_calls, 2)
            self.assertEqual(target.read_text(encoding="utf-8"), "# user rules\n")

    def test_codex_global_guidance_refuses_an_empty_existing_file(self) -> None:
        script = ROOT / "integrations/executors/codex/install_codex_global_guidance.py"
        with tempfile.TemporaryDirectory() as raw:
            home = Path(raw) / ".codex"
            home.mkdir()
            target = home / "AGENTS.md"
            target.write_bytes(b"")

            result = subprocess.run(
                [sys.executable, str(script), "--codex-home", str(home), "--apply"],
                text=True, encoding="utf-8", errors="replace",
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("CODEX_GUIDANCE_BLOCKED_EMPTY", result.stdout)
            self.assertEqual(target.read_bytes(), b"")

            target.write_text("# user rules\n", encoding="utf-8")
            preserved = subprocess.run(
                [sys.executable, str(script), "--codex-home", str(home), "--apply"],
                text=True, encoding="utf-8", errors="replace",
                capture_output=True,
                check=False,
            )
            self.assertIn("CODEX_GUIDANCE_EXISTS", preserved.stdout)
            self.assertEqual(target.read_text(encoding="utf-8"), "# user rules\n")

    def test_codex_global_guidance_reports_missing_or_invalid_home_by_mode(self) -> None:
        script = ROOT / "integrations/executors/codex/install_codex_global_guidance.py"
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            missing_home = root / "missing-home"
            invalid_home = root / "invalid-home"
            invalid_home.write_text("not a directory\n", encoding="utf-8")

            for home, marker in (
                (missing_home, "CODEX_GUIDANCE_HOME_MISSING"),
                (invalid_home, "CODEX_GUIDANCE_HOME_INVALID"),
            ):
                preview = subprocess.run(
                    [sys.executable, str(script), "--codex-home", str(home)],
                    text=True, encoding="utf-8", errors="replace",
                    capture_output=True,
                    check=False,
                )
                self.assertEqual(preview.returncode, 0, preview.stdout + preview.stderr)
                self.assertIn(marker, preview.stdout)

                applied = subprocess.run(
                    [sys.executable, str(script), "--codex-home", str(home), "--apply"],
                    text=True, encoding="utf-8", errors="replace",
                    capture_output=True,
                    check=False,
                )
                self.assertEqual(applied.returncode, 1, applied.stdout + applied.stderr)
                self.assertIn(marker, applied.stdout)

    @unittest.skipIf(os.name == "nt", "POSIX anonymous staging semantics")
    def test_codex_global_guidance_refuses_publish_without_anonymous_staging(self) -> None:
        script = ROOT / "integrations/executors/codex/install_codex_global_guidance.py"
        spec = importlib.util.spec_from_file_location("codex_guidance_no_otmpfile", script)
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        with tempfile.TemporaryDirectory() as raw:
            home = Path(raw) / ".codex"
            home.mkdir()
            target = home / "AGENTS.md"
            real_open = module.os.open

            def reject_anonymous_staging(path: object, flags: int, *args: object, **kwargs: object) -> int:
                if path == "." and flags & module.os.O_TMPFILE:
                    raise OSError(errno.EOPNOTSUPP, "O_TMPFILE unavailable")
                return real_open(path, flags, *args, **kwargs)

            stdout = io.StringIO()
            with patch.object(module.os, "open", side_effect=reject_anonymous_staging):
                with contextlib.redirect_stdout(stdout):
                    result = module.main(["--codex-home", str(home), "--apply"])

            self.assertEqual(result, 1)
            self.assertIn("CODEX_GUIDANCE_ATOMIC_PUBLISH_UNSUPPORTED", stdout.getvalue())
            self.assertFalse(target.exists())
            self.assertEqual(list(home.iterdir()), [])

    def test_codex_global_guidance_rechecks_a_concurrent_override(self) -> None:
        script = ROOT / "integrations/executors/codex/install_codex_global_guidance.py"
        spec = importlib.util.spec_from_file_location("codex_guidance_override_race", script)
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        with tempfile.TemporaryDirectory() as raw:
            home = Path(raw) / ".codex"
            target = home / "AGENTS.md"

            def ready_then_override(_codex_home: Path) -> tuple[int, str, Path]:
                home.mkdir()
                (home / "AGENTS.override.md").write_text("# user override\n", encoding="utf-8")
                return 0, "CODEX_GUIDANCE_READY", target

            with patch.object(module, "plan", side_effect=ready_then_override):
                self.assertEqual(module.main(["--codex-home", str(home), "--apply"]), 0)

            self.assertFalse(target.exists())
            self.assertEqual(
                (home / "AGENTS.override.md").read_text(encoding="utf-8"),
                "# user override\n",
            )

    def test_codex_global_guidance_rechecks_override_after_exclusive_create(self) -> None:
        script = ROOT / "integrations/executors/codex/install_codex_global_guidance.py"
        spec = importlib.util.spec_from_file_location("codex_guidance_late_override", script)
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        with tempfile.TemporaryDirectory() as raw:
            home = Path(raw) / ".codex"
            home.mkdir()
            self.require_posix_anonymous_staging(home)
            target = home / "AGENTS.md"
            override = home / "AGENTS.override.md"
            real_entry_exists = module.entry_exists
            override_checks = 0

            def override_after_target_create(
                parent: Path,
                name: str,
                directory_fd: int | None,
            ) -> bool:
                nonlocal override_checks
                if name == "AGENTS.override.md":
                    override_checks += 1
                if name == "AGENTS.override.md" and override_checks == 2:
                    self.assertFalse(target.exists(), "public target must not exist before publication")
                    staging_files = list(home.glob(".workflow-assistance-AGENTS-*.tmp"))
                    self.assertLessEqual(len(staging_files), 1)
                    if os.name != "nt":
                        for staging in staging_files:
                            self.assertEqual(staging.stat().st_size, module.TEMPLATE.stat().st_size)
                    override.write_text("# late user override\n", encoding="utf-8")
                return real_entry_exists(parent, name, directory_fd)

            stdout = io.StringIO()
            with patch.object(
                module,
                "entry_exists",
                side_effect=override_after_target_create,
            ):
                with contextlib.redirect_stdout(stdout):
                    result = module.main(["--codex-home", str(home), "--apply"])

            self.assertEqual(override_checks, 2)
            self.assertEqual(result, 1)
            self.assertIn("CODEX_GUIDANCE_OVERRIDE_BEFORE_PUBLICATION", stdout.getvalue())
            self.assertFalse(target.exists())
            self.assertEqual(override.read_text(encoding="utf-8"), "# late user override\n")

    def test_codex_global_guidance_returns_nonzero_when_pinning_home_fails(self) -> None:
        script = ROOT / "integrations/executors/codex/install_codex_global_guidance.py"
        spec = importlib.util.spec_from_file_location("codex_guidance_pin_failure", script)
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        with tempfile.TemporaryDirectory() as raw:
            home = Path(raw) / ".codex"
            home.mkdir()
            stdout = io.StringIO()
            with patch.object(module, "pinned_directory", side_effect=PermissionError("injected pin failure")):
                with contextlib.redirect_stdout(stdout):
                    result = module.main(["--codex-home", str(home), "--apply"])

            self.assertEqual(result, 1)
            self.assertIn("CODEX_GUIDANCE_DIRECTORY_PIN_FAILED", stdout.getvalue())
            self.assertFalse((home / "AGENTS.md").exists())

    def test_codex_global_guidance_handles_partial_target_after_write_failure(self) -> None:
        script = ROOT / "integrations/executors/codex/install_codex_global_guidance.py"
        spec = importlib.util.spec_from_file_location("codex_guidance_partial_write", script)
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        with tempfile.TemporaryDirectory() as raw:
            home = Path(raw) / ".codex"
            home.mkdir()
            self.require_posix_anonymous_staging(home)
            target = home / "AGENTS.md"
            real_write = module.os.write
            calls = 0

            def partial_write_then_fail(descriptor: int, content: bytes) -> int:
                nonlocal calls
                calls += 1
                if calls == 1:
                    return real_write(descriptor, content[:1])
                raise OSError("injected write failure")

            stdout = io.StringIO()
            with patch.object(module.os, "write", side_effect=partial_write_then_fail):
                with contextlib.redirect_stdout(stdout):
                    result = module.main(["--codex-home", str(home), "--apply"])

            self.assertEqual(result, 1)
            self.assertGreaterEqual(calls, 2)
            if os.name == "nt":
                self.assertIn("CODEX_GUIDANCE_WRITE_FAILED_CLEANED", stdout.getvalue())
                self.assertFalse(target.exists())
            else:
                self.assertFalse(target.exists())
                staging_files = list(home.glob(".workflow-assistance-AGENTS-*.tmp"))
                expected_marker = (
                    "CODEX_GUIDANCE_WRITE_INCOMPLETE"
                    if staging_files
                    else "CODEX_GUIDANCE_WRITE_FAILED_CLEANED"
                )
                self.assertIn(expected_marker, stdout.getvalue())
                for staging in staging_files:
                    self.assertEqual(staging.read_bytes(), module.TEMPLATE.read_bytes()[:1])

    @unittest.skipIf(os.name == "nt", "POSIX dirfd cleanup semantics")
    def test_codex_global_guidance_never_unlinks_a_posix_race_target(self) -> None:
        script = ROOT / "integrations/executors/codex/install_codex_global_guidance.py"
        spec = importlib.util.spec_from_file_location("codex_guidance_posix_no_unlink", script)
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        with tempfile.TemporaryDirectory() as raw:
            home = Path(raw) / ".codex"
            home.mkdir()
            self.require_posix_anonymous_staging(home)
            target = home / "AGENTS.md"
            override = home / "AGENTS.override.md"
            real_entry_exists = module.entry_exists
            checks = 0

            def late_override(parent: Path, name: str, directory_fd: int | None) -> bool:
                nonlocal checks
                if name == "AGENTS.override.md":
                    checks += 1
                if name == "AGENTS.override.md" and checks == 2:
                    override.write_text("# late override\n", encoding="utf-8")
                return real_entry_exists(parent, name, directory_fd)

            stdout = io.StringIO()
            with patch.object(module, "entry_exists", side_effect=late_override):
                with patch.object(
                    module.os,
                    "unlink",
                    side_effect=AssertionError("POSIX installer must not unlink a contested target name"),
                ):
                    with contextlib.redirect_stdout(stdout):
                        result = module.main(["--codex-home", str(home), "--apply"])

            self.assertEqual(result, 1)
            self.assertIn("CODEX_GUIDANCE_OVERRIDE_BEFORE_PUBLICATION", stdout.getvalue())
            self.assertFalse(target.exists())
            self.assertEqual(override.read_text(encoding="utf-8"), "# late override\n")

    @unittest.skipUnless(os.name == "nt", "Windows parent-junction semantics")
    def test_codex_global_guidance_does_not_create_a_missing_home_through_a_swapped_parent(
        self,
    ) -> None:
        script = ROOT / "integrations/executors/codex/install_codex_global_guidance.py"
        spec = importlib.util.spec_from_file_location("codex_guidance_missing_home_race", script)
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            requested_parent = root / "requested-parent"
            requested_parent.mkdir()
            moved_parent = root / "moved-parent"
            outside_parent = root / "outside-parent"
            outside_parent.mkdir()
            home = requested_parent / ".codex"
            concrete_path_type = type(home)
            real_mkdir = concrete_path_type.mkdir
            swapped = False

            def swap_parent_before_mkdir(candidate: Path, *args: object, **kwargs: object) -> None:
                nonlocal swapped
                if candidate == home and not swapped:
                    swapped = True
                    requested_parent.rename(moved_parent)
                    junction = subprocess.run(
                        [
                            "cmd.exe",
                            "/d",
                            "/c",
                            "mklink",
                            "/J",
                            str(requested_parent),
                            str(outside_parent),
                        ],
                        capture_output=True,
                        check=False,
                    )
                    self.assertEqual(junction.returncode, 0, junction.stdout + junction.stderr)
                real_mkdir(candidate, *args, **kwargs)

            stdout = io.StringIO()
            with patch.object(
                concrete_path_type,
                "mkdir",
                autospec=True,
                side_effect=swap_parent_before_mkdir,
            ):
                with contextlib.redirect_stdout(stdout):
                    result = module.main(["--codex-home", str(home), "--apply"])

            self.assertEqual(result, 1)
            self.assertIn("CODEX_GUIDANCE_HOME_MISSING", stdout.getvalue())
            self.assertFalse((outside_parent / ".codex").exists())

    @unittest.skipUnless(os.name == "nt", "Windows target handle semantics")
    def test_codex_global_guidance_reports_finalize_failure_without_claiming_a_race_block(
        self,
    ) -> None:
        script = ROOT / "integrations/executors/codex/install_codex_global_guidance.py"
        spec = importlib.util.spec_from_file_location("codex_guidance_finalize_failure", script)
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        with tempfile.TemporaryDirectory() as raw:
            home = Path(raw) / ".codex"
            home.mkdir()
            target = home / "AGENTS.md"
            real_close = module.os.close

            def close_then_fail(descriptor: int) -> None:
                real_close(descriptor)
                raise OSError("injected finalize failure")

            stdout = io.StringIO()
            with patch.object(module.os, "close", side_effect=close_then_fail):
                with contextlib.redirect_stdout(stdout):
                    result = module.main(["--codex-home", str(home), "--apply"])

            self.assertEqual(result, 1)
            self.assertIn("CODEX_GUIDANCE_FINALIZE_INCOMPLETE", stdout.getvalue())
            self.assertNotIn("CODEX_GUIDANCE_BLOCKED_RACE", stdout.getvalue())
            self.assertEqual(target.read_bytes(), module.TEMPLATE.read_bytes())

    @unittest.skipUnless(os.name == "nt", "Windows HANDLE ownership semantics")
    def test_codex_global_guidance_cleans_staging_if_open_osfhandle_fails(self) -> None:
        import msvcrt

        script = ROOT / "integrations/executors/codex/install_codex_global_guidance.py"
        spec = importlib.util.spec_from_file_location("codex_guidance_osfhandle_failure", script)
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        with tempfile.TemporaryDirectory() as raw:
            home = Path(raw) / ".codex"
            home.mkdir()
            target = home / "AGENTS.md"
            stdout = io.StringIO()

            with patch.object(msvcrt, "open_osfhandle", side_effect=OSError("injected conversion failure")):
                with contextlib.redirect_stdout(stdout):
                    result = module.main(["--codex-home", str(home), "--apply"])

            self.assertEqual(result, 1)
            self.assertIn("CODEX_GUIDANCE_STAGING_CREATE_FAILED_CLEANED", stdout.getvalue())
            self.assertFalse(target.exists())
            self.assertEqual(list(home.iterdir()), [])

    @unittest.skipUnless(os.name == "nt", "Windows share-mode semantics")
    def test_codex_global_guidance_never_writes_after_the_public_target_exists(self) -> None:
        import ctypes
        import msvcrt
        from ctypes import wintypes

        script = ROOT / "integrations/executors/codex/install_codex_global_guidance.py"
        spec = importlib.util.spec_from_file_location("codex_guidance_private_write", script)
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        with tempfile.TemporaryDirectory() as raw:
            home = Path(raw) / ".codex"
            home.mkdir()
            target = home / "AGENTS.md"
            real_write_all = module.write_all
            writer_opened = False
            staging_writer_opened = False

            def probe_public_target(descriptor: int, content: bytes) -> None:
                nonlocal staging_writer_opened, writer_opened
                real_write_all(descriptor, content)
                create_file = ctypes.WinDLL("kernel32", use_last_error=True).CreateFileW
                create_file.argtypes = [
                    wintypes.LPCWSTR,
                    wintypes.DWORD,
                    wintypes.DWORD,
                    wintypes.LPVOID,
                    wintypes.DWORD,
                    wintypes.DWORD,
                    wintypes.HANDLE,
                ]
                create_file.restype = wintypes.HANDLE
                handle = create_file(
                    str(target),
                    0x40000000,
                    0x00000001 | 0x00000002 | 0x00000004,
                    None,
                    3,
                    0x00000080,
                    None,
                )
                invalid = ctypes.c_void_p(-1).value
                if handle not in (None, invalid):
                    writer_opened = True
                    concurrent_fd = msvcrt.open_osfhandle(
                        handle,
                        os.O_WRONLY | getattr(os, "O_BINARY", 0),
                    )
                    os.write(concurrent_fd, b"X")
                    os.close(concurrent_fd)
                staging_files = list(home.glob(".workflow-assistance-AGENTS-*.tmp"))
                self.assertEqual(len(staging_files), 1)
                staging_handle = create_file(
                    str(staging_files[0]),
                    0x40000000,
                    0x00000001 | 0x00000002 | 0x00000004,
                    None,
                    3,
                    0x00000080,
                    None,
                )
                if staging_handle not in (None, invalid):
                    staging_writer_opened = True
                    ctypes.WinDLL("kernel32", use_last_error=True).CloseHandle(staging_handle)

            with patch.object(module, "write_all", side_effect=probe_public_target):
                result = module.main(["--codex-home", str(home), "--apply"])

            self.assertEqual(result, 0)
            self.assertFalse(writer_opened, "AGENTS.md became public before its content was complete")
            self.assertFalse(staging_writer_opened, "private staging accepted a concurrent writer")
            self.assertEqual(target.read_bytes(), module.TEMPLATE.read_bytes())

    @unittest.skipUnless(os.name == "nt", "Windows hardlink semantics")
    def test_codex_global_guidance_does_not_write_through_a_post_create_hardlink(self) -> None:
        script = ROOT / "integrations/executors/codex/install_codex_global_guidance.py"
        spec = importlib.util.spec_from_file_location("codex_guidance_late_hardlink", script)
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            home = root / ".codex"
            home.mkdir()
            target = home / "AGENTS.md"
            outside = root / "outside-hardlink.md"
            real_entry_exists = module.entry_exists
            checks = 0
            linked = False
            hardlink_blocked = False

            def link_at_final_override_check(parent: Path, name: str, directory_fd: int | None) -> bool:
                nonlocal checks, hardlink_blocked, linked
                if name == "AGENTS.override.md":
                    checks += 1
                if name == "AGENTS.override.md" and checks == 2:
                    staging_files = list(home.glob(".workflow-assistance-AGENTS-*.tmp"))
                    self.assertEqual(len(staging_files), 1)
                    try:
                        os.link(staging_files[0], outside)
                    except OSError:
                        hardlink_blocked = True
                    else:
                        linked = True
                return real_entry_exists(parent, name, directory_fd)

            with patch.object(module, "entry_exists", side_effect=link_at_final_override_check):
                result = module.main(["--codex-home", str(home), "--apply"])

            # The invariant is "a compromised staging is never published", not "the platform
            # prevents hard links". Measured on this host: CreateHardLink succeeds even against a
            # handle opened with FILE_SHARE_NONE, and the delete-pending disposition that WOULD
            # prevent it returns WinError 24 here — so prevention is unavailable and the installer
            # detects it instead (st_nlink != 1) and refuses. Both outcomes are correct; what must
            # never happen is publishing into a staging entry somebody else can reach.
            if hardlink_blocked:
                self.assertFalse(linked)
                self.assertEqual(result, 0, "a staging nobody could reach still failed to install")
                self.assertTrue(target.is_file())
            else:
                self.assertTrue(linked, "the fixture never created the hard link it promised")
                self.assertEqual(result, 1, "a hard-linked staging must not be published as success")
                self.assertFalse(target.exists(), "a compromised staging was published anyway")
                # The hard link the fixture managed to make DOES exist — that is the point of
                # the detection path. What must not exist is a published AGENTS.md beside it.
                self.assertTrue(outside.exists())
            if hardlink_blocked:
                self.assertFalse(outside.exists())
                self.assertEqual(target.read_bytes(), module.TEMPLATE.read_bytes())

    @unittest.skipIf(os.name == "nt", "POSIX public-path identity semantics")
    def test_codex_global_guidance_does_not_publish_into_a_moved_home(self) -> None:
        script = ROOT / "integrations/executors/codex/install_codex_global_guidance.py"
        spec = importlib.util.spec_from_file_location("codex_guidance_posix_home_swap", script)
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            home = root / ".codex"
            home.mkdir()
            self.require_posix_anonymous_staging(home)
            moved_home = root / "moved-codex"
            real_entry_exists = module.entry_exists
            checks = 0

            def move_home_before_publish(parent: Path, name: str, directory_fd: int | None) -> bool:
                nonlocal checks
                if name == "AGENTS.override.md":
                    checks += 1
                if name == "AGENTS.override.md" and checks == 2:
                    home.rename(moved_home)
                    home.mkdir()
                return real_entry_exists(parent, name, directory_fd)

            stdout = io.StringIO()
            with patch.object(module, "entry_exists", side_effect=move_home_before_publish):
                with contextlib.redirect_stdout(stdout):
                    result = module.main(["--codex-home", str(home), "--apply"])

            self.assertEqual(result, 1)
            self.assertIn("CODEX_GUIDANCE_HOME_CHANGED", stdout.getvalue())
            self.assertFalse((home / "AGENTS.md").exists())
            self.assertFalse((moved_home / "AGENTS.md").exists())

    @unittest.skipIf(os.name == "nt", "POSIX public-target identity semantics")
    def test_codex_global_guidance_reports_a_public_target_replacement(self) -> None:
        script = ROOT / "integrations/executors/codex/install_codex_global_guidance.py"
        spec = importlib.util.spec_from_file_location("codex_guidance_posix_target_swap", script)
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        with tempfile.TemporaryDirectory() as raw:
            home = Path(raw) / ".codex"
            home.mkdir()
            self.require_posix_anonymous_staging(home)
            target = home / "AGENTS.md"
            moved_target = home / "installer-reservation.md"
            real_entry_exists = module.entry_exists
            checks = 0

            def replace_after_publish(parent: Path, name: str, directory_fd: int | None) -> bool:
                nonlocal checks
                if name == "AGENTS.override.md":
                    checks += 1
                if name == "AGENTS.override.md" and checks == 3:
                    target.rename(moved_target)
                    target.write_text("# concurrent user target\n", encoding="utf-8")
                return real_entry_exists(parent, name, directory_fd)

            stdout = io.StringIO()
            with patch.object(module, "entry_exists", side_effect=replace_after_publish):
                with contextlib.redirect_stdout(stdout):
                    result = module.main(["--codex-home", str(home), "--apply"])

            self.assertEqual(checks, 3)
            self.assertEqual(result, 1)
            self.assertIn("CODEX_GUIDANCE_PUBLIC_TARGET_CHANGED", stdout.getvalue())
            self.assertEqual(target.read_text(encoding="utf-8"), "# concurrent user target\n")
            self.assertEqual(moved_target.read_bytes(), module.TEMPLATE.read_bytes())

    def test_codex_global_guidance_reports_directory_finalize_failure_nonzero(self) -> None:
        script = ROOT / "integrations/executors/codex/install_codex_global_guidance.py"
        spec = importlib.util.spec_from_file_location("codex_guidance_directory_close", script)
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        real_pinned_directory = module.pinned_directory

        @contextlib.contextmanager
        def directory_close_fails(path: Path) -> object:
            with real_pinned_directory(path) as directory_fd:
                yield directory_fd
            cause = OSError("injected directory close failure")
            raise module.DirectoryFinalizeError(str(cause)) from cause

        with tempfile.TemporaryDirectory() as raw:
            home = Path(raw) / ".codex"
            home.mkdir()
            target = home / "AGENTS.md"
            target.write_text("# concurrent user target\n", encoding="utf-8")
            stdout = io.StringIO()
            with patch.object(module, "pinned_directory", side_effect=directory_close_fails):
                with patch.object(module, "plan", return_value=(0, "CODEX_GUIDANCE_READY", target)):
                    with patch.object(
                        module,
                        "create_private_staging",
                        side_effect=module.AtomicPublishUnsupportedError("injected"),
                    ):
                        with contextlib.redirect_stdout(stdout):
                            result = module.main(["--codex-home", str(home), "--apply"])

            self.assertEqual(result, 1)
            self.assertIn("CODEX_GUIDANCE_DIRECTORY_FINALIZE_INCOMPLETE", stdout.getvalue())
            self.assertEqual(target.read_text(encoding="utf-8"), "# concurrent user target\n")

    @unittest.skipUnless(os.name == "nt", "Windows junction semantics")
    def test_codex_global_guidance_pins_home_against_late_junction_swap(self) -> None:
        script = ROOT / "integrations/executors/codex/install_codex_global_guidance.py"
        spec = importlib.util.spec_from_file_location("codex_guidance_junction_race", script)
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            home = root / ".codex"
            home.mkdir()
            moved_home = root / "moved-codex"
            outside = root / "outside"
            outside.mkdir()
            target = home / "AGENTS.md"
            real_create = module.create_private_staging
            swap_attempted = False
            swap_blocked = False

            def swap_home_immediately_before_staging_create(
                candidate_home: Path,
                directory_fd: int,
            ) -> tuple[int, str | None]:
                nonlocal swap_attempted, swap_blocked
                if not swap_attempted and candidate_home == home:
                    swap_attempted = True
                    try:
                        home.rename(moved_home)
                    except PermissionError:
                        swap_blocked = True
                    else:
                        junction = subprocess.run(
                            ["cmd.exe", "/d", "/c", "mklink", "/J", str(home), str(outside)],
                            capture_output=True,
                            check=False,
                        )
                        self.assertEqual(junction.returncode, 0, junction.stdout + junction.stderr)
                return real_create(candidate_home, directory_fd)

            with patch.object(
                module,
                "create_private_staging",
                side_effect=swap_home_immediately_before_staging_create,
            ):
                self.assertEqual(module.main(["--codex-home", str(home), "--apply"]), 0)

            self.assertTrue(swap_attempted)
            self.assertTrue(swap_blocked, "Codex Home was renamed after the final link check")
            self.assertFalse((outside / "AGENTS.md").exists())
            self.assertTrue(target.is_file())

    def test_codex_global_guidance_refuses_a_hardlinked_empty_file(self) -> None:
        script = ROOT / "integrations/executors/codex/install_codex_global_guidance.py"
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            home = root / ".codex"
            home.mkdir()
            outside = root / "outside-user-rules.md"
            outside.write_bytes(b"")
            target = home / "AGENTS.md"
            try:
                os.link(outside, target)
            except OSError as error:
                self.skipTest(f"hardlink creation is unavailable: {error}")

            result = subprocess.run(
                [sys.executable, str(script), "--codex-home", str(home), "--apply"],
                text=True, encoding="utf-8", errors="replace",
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("CODEX_GUIDANCE_BLOCKED_HARDLINK", result.stdout)
            self.assertEqual(target.read_bytes(), b"")
            self.assertEqual(outside.read_bytes(), b"")

    def test_codex_global_guidance_rejects_a_linked_ancestor_directory(self) -> None:
        script = ROOT / "integrations/executors/codex/install_codex_global_guidance.py"
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            physical_parent = root / "physical-parent"
            physical_parent.mkdir()
            linked_parent = root / "linked-parent"
            try:
                linked_parent.symlink_to(physical_parent, target_is_directory=True)
            except OSError as error:
                self.skipTest(f"symlink creation is unavailable: {error}")
            # A creation call that SUCCEEDS is not proof of a link. Measured on this host
            # (2026-10-12): symlink_to returned without raising on both NTFS volumes and left a plain
            # directory behind -- lstat reports FILE_ATTRIBUTE_DIRECTORY (0x10) and no
            # FILE_ATTRIBUTE_REPARSE_POINT (0x400). Skipping here says the premise could not be built;
            # it does not excuse the check, which runs everywhere a real link can be made.
            status = linked_parent.lstat()
            if not linked_parent.is_symlink() and not (
                getattr(status, "st_file_attributes", 0) & 0x0400
            ):
                self.skipTest(
                    "this filesystem downgrades symlink creation to a plain directory, "
                    "so a linked ancestor cannot be constructed here"
                )

            home = linked_parent / ".codex"
            result = subprocess.run(
                [sys.executable, str(script), "--codex-home", str(home), "--apply"],
                text=True, encoding="utf-8", errors="replace",
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("CODEX_GUIDANCE_BLOCKED_LINK", result.stdout)
            self.assertFalse((physical_parent / ".codex" / "AGENTS.md").exists())

    def test_provider_health_generates_secret_free_unverified_inventory(self) -> None:
        script = ROOT / "packages/client-neutral-core/scripts/provider_health.py"
        self.assertTrue(script.exists())
        with tempfile.TemporaryDirectory() as raw:
            output = Path(raw) / "provider-health.json"
            result = subprocess.run(
                [sys.executable, str(script), "--config", str(ROOT / "config/config.yaml"), "--output", str(output)],
                text=True, encoding="utf-8", errors="replace",
                capture_output=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            report = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual(report["schema_version"], 1)
        self.assertTrue(report["secret_free"])
        self.assertEqual(report["overall_status"], "UNVERIFIED")
        self.assertEqual(report["models"], {})

    def test_context_budget_policy_has_hard_tool_and_session_limits(self) -> None:
        policy_path = ROOT / "config/context-budget.yaml"
        self.assertTrue(policy_path.exists())
        policy = yaml.safe_load(policy_path.read_text(encoding="utf-8"))
        self.assertEqual(policy["schema_version"], 1)
        self.assertGreater(policy["session"]["hard_tokens"], policy["session"]["warning_tokens"])
        self.assertGreater(policy["tool_output"]["failure_chars"], policy["tool_output"]["default_chars"])

    def test_portable_config_defaults_to_context7_and_preserves_plugins(self) -> None:
        config = yaml.safe_load((ROOT / "config/config.yaml").read_text(encoding="utf-8"))
        for forbidden in ("model", "fallback_providers", "model_picker", "quick_commands", "agent"):
            self.assertNotIn(forbidden, config)
        self.assertEqual(set(config["mcp_servers"]), {"context7"})
        self.assertNotIn("plugins", config)
        self.assertEqual(config["display"]["busy_input_mode"], "queue")
        self.assertNotIn("skin", config["display"])
        self.assertEqual(config["display"]["language"], "zh")
        self.assertFalse(config["sessions"]["auto_prune"])
        self.assertTrue(config["memory"]["memory_enabled"])
        self.assertTrue(config["memory"]["user_profile_enabled"])
        terminal_hooks = [
            hook for hook in config["hooks"]["pre_tool_call"] if hook["matcher"] == "terminal"
        ]
        self.assertEqual(len(terminal_hooks), 1)
        self.assertIn("hermes-project-terminal-guard.py", terminal_hooks[0]["command"])
        non_core = {"spotify", "x_search", "video", "tts"}
        self.assertTrue(non_core.isdisjoint(config["platform_toolsets"]["cli"]))

    def test_portable_config_is_model_and_provider_neutral(self) -> None:
        config = yaml.safe_load((ROOT / "config/config.yaml").read_text(encoding="utf-8"))
        serialized = yaml.safe_dump(config, allow_unicode=True, sort_keys=False)
        for forbidden in ("model:", "provider:", "base_url:", "model_picker:", "quick_commands:"):
            self.assertNotIn(forbidden, serialized)

    def test_model_switch_docs_never_instruct_credential_or_cc_switch_db_access(self) -> None:
        source = "\n".join(
            path.read_text(encoding="utf-8")
            for path in (ROOT / "packages/client-neutral-core/skills/model-switch").rglob("*.md")
        )
        self.assertNotIn("cc-switch.db", source)
        self.assertNotIn("sqlite3.connect", source)
        self.assertNotIn("gpt-5.3-codex-spark", source)
        self.assertNotIn("gpt-fast", source)

    def test_workflow_doctor_never_reads_private_codex_config(self) -> None:
        source = (ROOT / "integrations/executors/hermes/hermes_workflow_doctor.py").read_text(encoding="utf-8")
        self.assertNotIn('Path.home() / ".codex/config.toml"', source)
        self.assertIn("private config is intentionally not inspected", source)

    def test_model_switcher_uses_environment_and_official_single_field_reads_only(self) -> None:
        source = (ROOT / "integrations/executors/hermes/switch_model.py").read_text(encoding="utf-8")
        self.assertIn("never inspect Hermes .env", source)
        self.assertIn("hermes', 'config', 'get', '--json'", source)
        self.assertNotIn("read_text(encoding='utf-8', errors='ignore').splitlines()", source)
        self.assertNotIn("yaml.safe_load", source)
        self.assertNotIn("model.api_key", source)

    def test_doctor_network_checks_are_explicit(self) -> None:
        source = (ROOT / "integrations/executors/hermes/hermes_workflow_doctor.py").read_text(encoding="utf-8")
        self.assertIn('"--network"', source)
        self.assertIn("network_checks = args.network or args.live", source)
        self.assertIn("Context7 MCP connectivity (use --network or --live)", source)

    def test_security_scanner_covers_executable_rule_files(self) -> None:
        scanner = ROOT / "packages/client-neutral-core/scripts/security/scan_agent_rules.py"
        with tempfile.TemporaryDirectory() as raw:
            sample = Path(raw) / "agent.py"
            sample.write_text('api_key = "' + "A" * 32 + '"\n', encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(scanner), str(sample)],
                text=True, encoding="utf-8", errors="replace",
                capture_output=True,
                check=False,
            )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("possible hardcoded secret", result.stdout)

    def test_skill_provenance_manifest_and_gate_are_present(self) -> None:
        manifest = ROOT / "config/skill-provenance.yaml"
        checker = ROOT / "packages/client-neutral-core/scripts/security/check_skill_provenance.py"
        gate = (ROOT / "services/orchestration/run_quality_gate.py").read_text(encoding="utf-8")
        self.assertTrue(manifest.exists())
        self.assertTrue(checker.exists())
        self.assertIn("skill-provenance", gate)

    def test_skill_provenance_discovers_every_declared_source_skill(self) -> None:
        """The checker must discover the declared source roots, not a guessed path.

        Regression guard: the checker previously hard-coded ``repo_root/"skills"``,
        so it discovered zero skills and reported a meaningless
        ``SKILL_PROVENANCE_PASS skills=0``.
        """
        checker = ROOT / "packages/client-neutral-core/scripts/security/check_skill_provenance.py"
        manifest_path = ROOT / "config/skill-provenance.yaml"
        manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(manifest.get("source_roots"), ["packages/client-neutral-core/skills"])
        result = subprocess.run(
            [sys.executable, str(checker), "--manifest", str(manifest_path)],
            text=True,
            capture_output=True,
            check=False,
            encoding="utf-8",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        match = re.search(r"SKILL_PROVENANCE_PASS skills=(\d+)", result.stdout)
        self.assertIsNotNone(match, result.stdout)
        discovered = int(match.group(1))
        self.assertGreater(discovered, 0)
        self.assertEqual(discovered, len(manifest["entries"]))

    def test_skill_provenance_source_error_contracts(self) -> None:
        """Negative controls for the provenance source-root contract."""
        checker = ROOT / "packages/client-neutral-core/scripts/security/check_skill_provenance.py"
        skill_body = (
            "---\nname: sample\nversion: 1.0.0\nmetadata:\n  hermes:\n    related_skills: []\n---\n\nbody\n"
        )
        with tempfile.TemporaryDirectory() as temp:
            repo = Path(temp)
            skills_root = repo / "packages" / "demo" / "skills"
            (skills_root / "sample").mkdir(parents=True)
            (skills_root / "sample" / "SKILL.md").write_text(skill_body, encoding="utf-8")
            manifest_path = repo / "manifest.yaml"

            def invoke(manifest: dict, *extra: str) -> subprocess.CompletedProcess[str]:
                manifest_path.write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")
                return subprocess.run(
                    [sys.executable, str(checker), "--repo", str(repo), "--manifest", str(manifest_path), *extra],
                    text=True,
                    capture_output=True,
                    check=False,
                    encoding="utf-8",
                )

            # the legacy hard-coded guess must not be used silently
            result = invoke({"schema_version": 1, "source_roots": ["skills"], "entries": []})
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("declared source root does not exist", result.stderr)

            # no declaration at all is a hard error, never a silent empty discovery
            result = invoke({"schema_version": 1, "entries": []})
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("source_roots", result.stderr)

            # a declared root holding no SKILL.md must fail
            (repo / "empty-root").mkdir()
            result = invoke({"schema_version": 1, "source_roots": ["empty-root"], "entries": []})
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("zero source skills discovered", result.stderr)

            # a discovered skill absent from the manifest must fail (coverage)
            result = invoke({"schema_version": 1, "source_roots": ["packages/demo/skills"], "entries": []})
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("does not cover", result.stderr)

            # the same skill name under two roots must fail
            other_root = repo / "other-skills"
            (other_root / "sample").mkdir(parents=True)
            (other_root / "sample" / "SKILL.md").write_text(skill_body, encoding="utf-8")
            result = invoke(
                {"schema_version": 1, "source_roots": ["packages/demo/skills", "other-skills"], "entries": []}
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("duplicate skill name across source roots", result.stderr)

            # a wrong recorded hash must fail
            good_entry = {
                "name": "sample",
                "source": "packages/demo/skills/sample/SKILL.md",
                "source_sha256": "0" * 64,
                "version": "1.0.0",
                "trust": "repository-controlled",
                "enabled": True,
                "permission": "skill-guidance",
            }
            result = invoke({"schema_version": 1, "source_roots": ["packages/demo/skills"], "entries": [good_entry]})
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("source SHA drift", result.stderr)

            # write mode must refuse an empty discovery and leave the file byte-identical
            populated = dict(good_entry)
            populated["source_sha256"] = "irrelevant-because-write-must-refuse"
            manifest_path.write_text(
                yaml.safe_dump(
                    {"schema_version": 1, "source_roots": ["empty-root"], "entries": [populated]}, sort_keys=False
                ),
                encoding="utf-8",
            )
            before = manifest_path.read_text(encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(checker), "--repo", str(repo), "--manifest", str(manifest_path), "--write"],
                text=True,
                capture_output=True,
                check=False,
                encoding="utf-8",
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("refusing to write a manifest with zero discovered skills", result.stderr)
            self.assertEqual(manifest_path.read_text(encoding="utf-8"), before)

    def test_skill_provenance_refresh_preserves_decisions_and_adds_pending(self) -> None:
        """R3: a hash refresh must not promote trust/enable or rewrite the live mapping."""
        checker = ROOT / "packages/client-neutral-core/scripts/security/check_skill_provenance.py"

        def skill_body(name: str, related: list[str] | None = None) -> str:
            related_yaml = "".join(f"\n      - {item}" for item in (related or []))
            return (
                f"---\nname: {name}\nversion: 1.0.0\nmetadata:\n  hermes:\n"
                f"    related_skills:{related_yaml or ' []'}\n---\n\nbody\n"
            )

        with tempfile.TemporaryDirectory() as temp:
            repo = Path(temp)
            root = repo / "packages" / "demo" / "skills"
            for name in ("kept", "fresh"):
                (root / name).mkdir(parents=True)
                (root / name / "SKILL.md").write_text(skill_body(name), encoding="utf-8")
            manifest_path = repo / "manifest.yaml"
            manifest_path.write_text(
                yaml.safe_dump(
                    {
                        "schema_version": 1,
                        "profile_scope": "default",
                        "source_roots": ["packages/demo/skills"],
                        "entries": [
                            {
                                "name": "kept",
                                "source": "packages/demo/skills/kept/SKILL.md",
                                "live": "native/demo/kept/SKILL.md",
                                "source_sha256": "0" * 64,
                                "version": "1.0.0",
                                "trust": "quarantined",
                                "enabled": False,
                                "permission": "observe-only",
                                "profile_scope": "default",
                                "live_sha256": "1" * 64,
                            }
                        ],
                    },
                    sort_keys=False,
                ),
                encoding="utf-8",
            )

            result = subprocess.run(
                [sys.executable, str(checker), "--repo", str(repo), "--manifest", str(manifest_path), "--write"],
                text=True, capture_output=True, check=False, encoding="utf-8",
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            written = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
            by_name = {entry["name"]: entry for entry in written["entries"]}

            kept = by_name["kept"]
            self.assertEqual(kept["trust"], "quarantined", "refresh must not re-trust an entry")
            self.assertIs(kept["enabled"], False, "refresh must not enable a disabled entry")
            self.assertEqual(kept["permission"], "observe-only", "refresh must not widen permission")
            self.assertEqual(kept["live"], "native/demo/kept/SKILL.md", "refresh must not rewrite the live mapping")
            self.assertEqual(kept["live_sha256"], "1" * 64, "refresh must carry a recorded live hash across")
            self.assertNotEqual(kept["source_sha256"], "0" * 64, "the source hash is what a refresh recomputes")

            fresh = by_name["fresh"]
            self.assertEqual(fresh["trust"], "pending-review")
            self.assertIs(fresh["enabled"], False, "a newly discovered skill must not be auto-enabled")
            self.assertEqual(fresh["permission"], "observe-only")

    def test_skill_provenance_write_validates_before_replacing(self) -> None:
        """R3: a candidate that fails validation must not modify the manifest."""
        checker = ROOT / "packages/client-neutral-core/scripts/security/check_skill_provenance.py"
        with tempfile.TemporaryDirectory() as temp:
            repo = Path(temp)
            root = repo / "packages" / "demo" / "skills"
            (root / "broken").mkdir(parents=True)
            (root / "broken" / "SKILL.md").write_text(
                "---\nname: broken\nversion: 1.0.0\nmetadata:\n  hermes:\n    related_skills:\n"
                "      - does-not-exist\n---\n\nbody\n",
                encoding="utf-8",
            )
            manifest_path = repo / "manifest.yaml"
            original = yaml.safe_dump(
                {"schema_version": 1, "source_roots": ["packages/demo/skills"], "entries": []},
                sort_keys=False,
            )
            manifest_path.write_text(original, encoding="utf-8")

            result = subprocess.run(
                [sys.executable, str(checker), "--repo", str(repo), "--manifest", str(manifest_path), "--write"],
                text=True, capture_output=True, check=False, encoding="utf-8",
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("unknown source skills", result.stderr)
            self.assertEqual(manifest_path.read_text(encoding="utf-8"), original,
                             "the manifest must be untouched when the candidate fails validation")
            self.assertFalse((manifest_path.parent / (manifest_path.name + ".candidate")).exists(),
                             "no staging artifact may be left behind")

    def test_global_github_skills_are_repository_owned(self) -> None:
        expected = {
            "github-auth",
            "github-code-review",
            "github-issues",
            "github-pr-workflow",
            "github-repo-management",
        }
        manifest = yaml.safe_load(
            (ROOT / "config/skill-provenance.yaml").read_text(encoding="utf-8")
        )
        entries = {entry["name"]: entry for entry in manifest["entries"]}
        for name in sorted(expected):
            source = ROOT / "packages/client-neutral-core/skills/github" / name / "SKILL.md"
            self.assertTrue(source.is_file(), name)
            entry = entries[name]
            self.assertEqual(entry["source"], f"packages/client-neutral-core/skills/github/{name}/SKILL.md")
            self.assertEqual(entry["trust"], "repository-controlled")
            self.assertNotEqual(entry["source_sha256"], "profile-live-only")

    def test_sync_backup_covers_global_github_skills(self) -> None:
        script = ROOT / "integrations/executors/hermes/sync_hermes_workflow_assets.py"
        spec = importlib.util.spec_from_file_location("workflow_sync_backup_inventory", script)
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        with tempfile.TemporaryDirectory() as raw:
            home = Path(raw) / "home"
            home.mkdir()
            with patch.object(module, "backup_paths") as backup:
                module.deploy_portable(
                    ROOT,
                    home,
                    apply=False,
                    allow_project_runtime_home=True,
                )

        backup_rels = set(backup.call_args.args[1])
        for name in (
            "github-auth",
            "github-code-review",
            "github-issues",
            "github-pr-workflow",
            "github-repo-management",
        ):
            self.assertIn(f"skills/github/{name}", backup_rels)
        self.assertNotIn("skills/github", backup_rels)
        for relative in (
            "bin/codex",
            "bin/codex.cmd",
            "bin/hermes-npx",
            "bin/hermes-npx.cmd",
            "bin/hermes-project-data.py",
            "bin/hermes-project-terminal-guard.py",
        ):
            self.assertIn(relative, backup_rels)
        self.assertNotIn("bin", backup_rels)

    def test_isolated_portable_install_contains_global_github_skills(self) -> None:
        script = ROOT / "packages/client-neutral-core/scripts/verify_portable_install.py"
        runtime = ROOT / ".hermes" / "task-runtime" / "portable-install"
        runtime.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=runtime) as raw:
            home = Path(raw) / "isolated-home"
            result = subprocess.run(
                [sys.executable, str(script), "--repo", str(ROOT), "--home", str(home)],
                text=True, encoding="utf-8", errors="replace",
                capture_output=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            for name in (
                "github-auth",
                "github-code-review",
                "github-issues",
                "github-pr-workflow",
                "github-repo-management",
            ):
                self.assertTrue((home / "skills/github" / name / "SKILL.md").is_file(), name)

    def test_bootstrap_and_project_wrapper_work_for_multiple_projects(self) -> None:
        bootstrap = ROOT / "services/orchestration/bootstrap_project.py"
        wrapper = ROOT / "packages/client-neutral-core/bin/hermes-project-data.py"
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            for name in ("alpha", "beta", "windows-shaped-project"):
                target = root / name
                target.mkdir()
                (target / ".gitignore").write_text(".hermes/\n.project-local/\n", encoding="utf-8")
                subprocess.run(["git", "init", "-q", str(target)], check=True)
                boot = subprocess.run(
                    [sys.executable, str(bootstrap), str(target), "--agent-rules"],
                    text=True, encoding="utf-8", errors="replace",
                    capture_output=True,
                    check=False,
                )
                self.assertEqual(boot.returncode, 0, boot.stdout + boot.stderr)
                check = subprocess.run(
                    [sys.executable, str(wrapper), "--project", str(target), "check"],
                    text=True, encoding="utf-8", errors="replace",
                    capture_output=True,
                    check=False,
                )
                self.assertEqual(check.returncode, 0, check.stdout + check.stderr)
                # Guard picks .project-local when git-ignored, else .hermes (legacy)
                self.assertTrue(
                    "task-runtime" in check.stdout or "runs" in check.stdout,
                    f"guard check output should name the selected runtime root: {check.stdout}",
                )

    def test_manifest_requires_nonempty_exact_sha_workflow_contract(self) -> None:
        manifest = yaml.safe_load((ROOT / "packages/client-neutral-core/workflow-manifest.yaml").read_text(encoding="utf-8"))
        self.assertTrue(manifest["delivery"]["exact_sha_ci"])
        self.assertEqual(manifest["delivery"]["required_workflows"], ["work-lab-gate"])

    def test_governance_actions_are_commit_pinned_and_dependency_versioned(self) -> None:
        workflow = (ROOT / "docs/current/workflow-assistance/workflow/examples/governance.yml.example").read_text(encoding="utf-8")
        manifest = yaml.safe_load((ROOT / "packages/client-neutral-core/workflow-manifest.yaml").read_text(encoding="utf-8"))
        self.assertNotIn("actions/checkout@v", workflow)
        self.assertNotIn("actions/setup-python@v", workflow)
        self.assertIn("actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683", workflow)
        self.assertIn("actions/setup-python@42375524e23c412d93fb67b49958b491fce71c38", workflow)
        self.assertIn(
            "--require-hashes -r packages/client-neutral-core/requirements.lock",
            workflow,
        )
        self.assertNotIn("hermes-agent", workflow)
        self.assertNotIn("hermes", manifest["requirements"])
        self.assertIn("hermes", manifest["requirements"]["optional_adapters"])
        self.assertEqual(manifest["requirements"]["optional_adapters"]["hermes"], "capability-discovery")
        self.assertEqual(manifest["compatibility"]["official_schema"], "capability-discovery")
        self.assertEqual(manifest["compatibility"]["official_config_root"], "capability-discovery")
    def test_readme_removed_kimi_speed_lanes_and_keeps_deepseek_gpt(self) -> None:
        readme = (ROOT / "docs/current/workflow-assistance-README.md").read_text(encoding="utf-8")
        for command in (
            'switch_model.py kimi --model',
            'switch_model.py kimi-fast --model',
            'switch_model.py kimi-turbo --model',
        ):
            self.assertNotIn(command, readme)
        self.assertIn('switch_model.py deepseek --model "$HERMES_DEEPSEEK_MODEL"', readme)
        self.assertIn('switch_model.py gpt --model "$HERMES_GPT_MODEL"', readme)
        self.assertIn("不会自动更改当前会话", readme)
        self.assertIn("`/reset`", readme)

    def test_sync_uses_repo_skills_as_single_source(self) -> None:
        source = (ROOT / "integrations/executors/hermes/sync_hermes_workflow_assets.py").read_text(
            encoding="utf-8"
        )
        self.assertNotIn("MERGED_MODEL_SWITCH", source)
        self.assertNotIn("write_text(MERGED_MODEL_SWITCH", source)

    def test_sync_replaces_repo_owned_skill_trees_without_stale_live_assets(self) -> None:
        script = ROOT / "integrations/executors/hermes/sync_hermes_workflow_assets.py"
        spec = importlib.util.spec_from_file_location("workflow_sync_skills", script)
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        with tempfile.TemporaryDirectory() as raw:
            temp = Path(raw)
            repo = temp / "repo"
            staging = temp / "staging"
            managed_root = "packages/client-neutral-core/skills/software-development/managed"
            managed_repo = repo / managed_root
            managed_live = staging / managed_root
            custom_live = staging / "packages/client-neutral-core/skills/custom/keep-me"

            (managed_repo / "references").mkdir(parents=True)
            managed_repo.joinpath("SKILL.md").write_text("repo", encoding="utf-8")
            managed_repo.joinpath("references/current.md").write_text(
                "current", encoding="utf-8"
            )
            (managed_live / "references").mkdir(parents=True)
            managed_live.joinpath("SKILL.md").write_text("old", encoding="utf-8")
            managed_live.joinpath("references/stale.md").write_text(
                "stale", encoding="utf-8"
            )
            managed_live.joinpath(".hermes-origin.json").write_text(
                "{}", encoding="utf-8"
            )
            custom_live.mkdir(parents=True)
            custom_live.joinpath("SKILL.md").write_text("keep", encoding="utf-8")

            module.replace_managed_skill_trees(repo, staging, [managed_root])

            self.assertEqual(managed_live.joinpath("SKILL.md").read_text(), "repo")
            self.assertTrue(managed_live.joinpath("references/current.md").exists())
            self.assertFalse(managed_live.joinpath("references/stale.md").exists())
            self.assertFalse(managed_live.joinpath(".hermes-origin.json").exists())
            self.assertEqual(custom_live.joinpath("SKILL.md").read_text(), "keep")

    def test_sync_promotion_preserves_a_concurrent_nonmanaged_skill(self) -> None:
        script = ROOT / "integrations/executors/hermes/sync_hermes_workflow_assets.py"
        spec = importlib.util.spec_from_file_location("workflow_sync_concurrent_skill", script)
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        with tempfile.TemporaryDirectory() as raw:
            temp = Path(raw)
            home = temp / "home"
            staging = temp / "staging"
            managed_root = "packages/client-neutral-core/skills/software-development/managed"
            managed_live = home / managed_root
            managed_staged = staging / managed_root
            concurrent = home / "packages/client-neutral-core/skills/custom/concurrent/SKILL.md"
            managed_live.mkdir(parents=True)
            managed_live.joinpath("SKILL.md").write_text("old", encoding="utf-8")
            managed_staged.mkdir(parents=True)
            managed_staged.joinpath("SKILL.md").write_text("new", encoding="utf-8")

            # Simulate a user-installed skill appearing after staging and before promotion.
            concurrent.parent.mkdir(parents=True)
            concurrent.write_text("keep", encoding="utf-8")
            module.atomic_replace_paths(staging, home, [managed_root])

            self.assertEqual(managed_live.joinpath("SKILL.md").read_text(), "new")
            self.assertEqual(concurrent.read_text(encoding="utf-8"), "keep")

    def test_sync_promotion_preserves_nonmanaged_live_bin_entries(self) -> None:
        script = ROOT / "integrations/executors/hermes/sync_hermes_workflow_assets.py"
        spec = importlib.util.spec_from_file_location("workflow_sync_live_bin", script)
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        with tempfile.TemporaryDirectory() as raw:
            temp = Path(raw)
            home = temp / "home"
            staging = temp / "staging"
            managed = "bin/codex"
            (home / managed).parent.mkdir(parents=True)
            (home / managed).write_text("old-wrapper", encoding="utf-8")
            (staging / managed).parent.mkdir(parents=True)
            (staging / managed).write_text("new-wrapper", encoding="utf-8")
            official = home / "bin/official-runtime-entry"
            official.write_text("preserve", encoding="utf-8")

            module.atomic_replace_paths(staging, home, [managed])

            self.assertEqual((home / managed).read_text(encoding="utf-8"), "new-wrapper")
            self.assertEqual(official.read_text(encoding="utf-8"), "preserve")

    def test_sync_prepare_failure_removes_partial_staging(self) -> None:
        script = ROOT / "integrations/executors/hermes/sync_hermes_workflow_assets.py"
        spec = importlib.util.spec_from_file_location("workflow_sync_prepare_cleanup", script)
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        with tempfile.TemporaryDirectory() as raw:
            temp = Path(raw)
            repo = temp / "repo"
            home = temp / "home"
            managed_root = "packages/client-neutral-core/skills/software-development/managed"
            (repo / managed_root).mkdir(parents=True)
            (repo / managed_root / "SKILL.md").write_text("repo", encoding="utf-8")
            home.mkdir()

            with patch.object(module.shutil, "copytree", side_effect=OSError("prepare failed")):
                with self.assertRaisesRegex(OSError, "prepare failed"):
                    module.prepare_staging(repo, home, [managed_root], [], [])

            self.assertFalse(any(home.glob(".wa-stg-*")))

    def test_sync_atomic_replace_rolls_back_when_install_fails(self) -> None:
        script = ROOT / "integrations/executors/hermes/sync_hermes_workflow_assets.py"
        spec = importlib.util.spec_from_file_location("workflow_sync_atomic", script)
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        with tempfile.TemporaryDirectory() as raw:
            temp = Path(raw)
            home = temp / "home"
            staging = temp / "staging"
            home.mkdir()
            staging.mkdir()
            (home / "config.yaml").write_text("old", encoding="utf-8")
            (staging / "config.yaml").write_text("new", encoding="utf-8")
            real_replace = module.os.replace
            calls = 0

            def flaky_replace(source: str | Path, target: str | Path) -> None:
                nonlocal calls
                calls += 1
                if calls == 2:
                    raise OSError("simulated atomic install failure")
                real_replace(source, target)

            with patch.object(module.os, "replace", side_effect=flaky_replace):
                with self.assertRaisesRegex(OSError, "simulated atomic install failure"):
                    module.atomic_replace_paths(staging, home, ["config.yaml"])
            self.assertEqual((home / "config.yaml").read_text(encoding="utf-8"), "old")
            self.assertFalse(any(home.glob(".workflow-assistance-rollback-*")))

    def test_sync_atomic_replace_rolls_back_earlier_roots_when_a_later_root_fails(self) -> None:
        script = ROOT / "integrations/executors/hermes/sync_hermes_workflow_assets.py"
        spec = importlib.util.spec_from_file_location("workflow_sync_multi_root", script)
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        with tempfile.TemporaryDirectory() as raw:
            temp = Path(raw)
            home = temp / "home"
            staging = temp / "staging"
            home.mkdir()
            staging.mkdir()
            for name in ("first", "second"):
                (home / name).write_text(f"old-{name}", encoding="utf-8")
                (staging / name).write_text(f"new-{name}", encoding="utf-8")
            real_replace = module.os.replace

            def fail_second_install(source: str | Path, target: str | Path) -> None:
                if Path(source) == staging / "second":
                    raise OSError("simulated later-root failure")
                real_replace(source, target)

            with patch.object(module.os, "replace", side_effect=fail_second_install):
                with self.assertRaisesRegex(OSError, "simulated later-root failure"):
                    module.atomic_replace_paths(staging, home, ["first", "second"])

            self.assertEqual((home / "first").read_text(encoding="utf-8"), "old-first")
            self.assertEqual((home / "second").read_text(encoding="utf-8"), "old-second")
            self.assertFalse(any(home.glob(".workflow-assistance-rollback-*")))

    def test_sync_atomic_remove_is_restored_when_a_later_install_fails(self) -> None:
        script = ROOT / "integrations/executors/hermes/sync_hermes_workflow_assets.py"
        spec = importlib.util.spec_from_file_location("workflow_sync_remove_rollback", script)
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        with tempfile.TemporaryDirectory() as raw:
            temp = Path(raw)
            home = temp / "home"
            staging = temp / "staging"
            retired = "packages/client-neutral-core/skills/retired/SKILL.md"
            (home / retired).parent.mkdir(parents=True)
            (home / retired).write_text("retired-user-visible", encoding="utf-8")
            (staging / "config.yaml").parent.mkdir(parents=True)
            (staging / "config.yaml").write_text("new-config", encoding="utf-8")
            (home / "config.yaml").write_text("old-config", encoding="utf-8")
            real_replace = module.os.replace

            def fail_config_install(source: str | Path, target: str | Path) -> None:
                if Path(source) == staging / "config.yaml":
                    raise OSError("simulated config failure")
                real_replace(source, target)

            with patch.object(module.os, "replace", side_effect=fail_config_install):
                with self.assertRaisesRegex(OSError, "simulated config failure"):
                    module.atomic_replace_paths(
                        staging,
                        home,
                        [retired, "config.yaml"],
                        remove_rels=[retired],
                    )

            self.assertEqual((home / retired).read_text(encoding="utf-8"), "retired-user-visible")
            self.assertEqual((home / "config.yaml").read_text(encoding="utf-8"), "old-config")

    def test_sync_preserves_rollback_when_cleanup_fails(self) -> None:
        script = ROOT / "integrations/executors/hermes/sync_hermes_workflow_assets.py"
        spec = importlib.util.spec_from_file_location("workflow_sync_cleanup", script)
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        with tempfile.TemporaryDirectory() as raw:
            temp = Path(raw)
            home = temp / "home"
            staging = temp / "staging"
            home.mkdir()
            staging.mkdir()
            (home / "config.yaml").write_text("old", encoding="utf-8")
            (staging / "config.yaml").write_text("new", encoding="utf-8")
            real_rmtree = module.shutil.rmtree

            def fail_rollback_cleanup(path: str | Path, *args: object, **kwargs: object) -> None:
                if Path(path).name.startswith(".workflow-assistance-rollback-"):
                    raise OSError("simulated rollback cleanup failure")
                real_rmtree(path, *args, **kwargs)

            with patch.object(module.shutil, "rmtree", side_effect=fail_rollback_cleanup):
                with self.assertRaisesRegex(OSError, "simulated rollback cleanup failure"):
                    module.atomic_replace_paths(staging, home, ["config.yaml"])
            self.assertTrue(any(home.glob(".workflow-assistance-rollback-*")))

    def test_sync_preserves_unowned_historical_mcps_and_model(self) -> None:
        script = ROOT / "integrations/executors/hermes/sync_hermes_workflow_assets.py"
        spec = importlib.util.spec_from_file_location("workflow_sync", script)
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        with tempfile.TemporaryDirectory() as raw:
            temp = Path(raw)
            repo = temp / "repo"
            home = temp / "home"
            (repo / "config").mkdir(parents=True)
            home.mkdir()
            (repo / "config/config.yaml").write_text(
                "mcp_servers:\n  context7:\n    command: hermes-npx\n    args: [-y, context7]\n"
                "display:\n  busy_input_mode: queue\n",
                encoding="utf-8",
            )
            (home / "config.yaml").write_text(
                "model:\n  provider: openai-codex\n  default: gpt-current\n"
                "mcp_servers:\n  public-apis: {}\n  sequential-thinking: {}\n  custom: {}\n"
                "plugins:\n  enabled: [disk-cleanup, google_meet, spotify, custom-plugin]\n"
                "display:\n  busy_input_mode: interrupt\n  skin: live\n"
                "model_picker:\n  custom_lanes:\n    enabled: false\n  local_picker_flag: true\n"
                "quick_commands:\n  custom: {type: alias, target: /help}\n",
                encoding="utf-8",
            )

            module.merge_live_config(repo, home, apply=True)
            result = yaml.safe_load((home / "config.yaml").read_text(encoding="utf-8"))
            self.assertEqual(result["model"]["default"], "gpt-current")
            self.assertEqual(
                set(result["mcp_servers"]),
                {"context7", "public-apis", "sequential-thinking", "custom"},
            )
            self.assertEqual(
                set(result["plugins"]["enabled"]),
                {"disk-cleanup", "google_meet", "spotify", "custom-plugin"},
            )
            self.assertEqual(result["display"]["busy_input_mode"], "queue")
            self.assertEqual(result["display"]["skin"], "live")
            self.assertFalse(result["model_picker"]["custom_lanes"]["enabled"])
            self.assertTrue(result["model_picker"]["local_picker_flag"])
            self.assertEqual(result["quick_commands"]["custom"]["target"], "/help")

            result["plugins"]["enabled"].append("spotify")
            (home / "config.yaml").write_text(
                yaml.safe_dump(result, sort_keys=False), encoding="utf-8"
            )
            module.merge_live_config(repo, home, apply=True)
            rerun = yaml.safe_load((home / "config.yaml").read_text(encoding="utf-8"))
            self.assertIn("spotify", rerun["plugins"]["enabled"])
            self.assertEqual(rerun["display"]["busy_input_mode"], "queue")
            self.assertFalse((home / ".workflow-assistance-state.yaml").exists())

    def test_sync_installs_terminal_hook_and_preserves_custom_hooks(self) -> None:
        script = ROOT / "integrations/executors/hermes/sync_hermes_workflow_assets.py"
        spec = importlib.util.spec_from_file_location("workflow_sync_hooks", script)
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        with tempfile.TemporaryDirectory() as raw:
            temp = Path(raw)
            repo = temp / "repo"
            home = temp / "home"
            (repo / "config").mkdir(parents=True)
            home.mkdir()
            (repo / "config/config.yaml").write_text(
                "hooks:\n  pre_tool_call:\n"
                "    - matcher: terminal\n"
                "      command: python ${HERMES_HOME}/bin/hermes-project-terminal-guard.py\n"
                "      timeout: 10\n",
                encoding="utf-8",
            )
            (home / "config.yaml").write_text(
                "hooks:\n  pre_tool_call:\n"
                "    - matcher: browser\n      command: custom-browser-hook\n",
                encoding="utf-8",
            )

            module.merge_live_config(repo, home, apply=True)
            result = yaml.safe_load((home / "config.yaml").read_text(encoding="utf-8"))
            hooks = result["hooks"]["pre_tool_call"]
            self.assertEqual({hook["matcher"] for hook in hooks}, {"browser", "terminal"})
            terminal = next(hook for hook in hooks if hook["matcher"] == "terminal")
            self.assertIn(str(home / "bin/hermes-project-terminal-guard.py").replace("\\", "/"), terminal["command"])

    def test_sync_blocks_unfenced_retired_skill_assets_without_deleting_them(self) -> None:
        script = ROOT / "integrations/executors/hermes/sync_hermes_workflow_assets.py"
        spec = importlib.util.spec_from_file_location("workflow_sync_retired", script)
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        with tempfile.TemporaryDirectory() as raw:
            home = Path(raw)
            retired = [
                "model-switch/references/oauth-credential-sync.md",
                "software-development/windows-development-environment/references/github-credential-extraction.md",
                "software-development/windows-development-environment/references/codex++-proxy-routing.md",
                "software-development/windows-development-environment/references/cognitive-loop-os-tauri-build.md",
                "software-development/windows-development-environment/references/cognitive-loop-os-desktop-workflow.md",
                "software-development/python-testing/references/deterministic-e2e-test-pattern.md",
                "software-development/hermes-provider-routing/SKILL.md",
                "software-development/cognitive-loop-os/SKILL.md",
                "software-development/screenlingua/SKILL.md",
            ]
            for relative in retired:
                target = home / "skills" / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text("stale", encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "retired_asset_ownership_unproven"):
                module._block_unfenced_retired_assets(home)
            for relative in retired:
                self.assertEqual((home / "skills" / relative).read_text(encoding="utf-8"), "stale", relative)

    def test_sync_initializes_missing_live_config_without_injecting_a_model_route(self) -> None:
        script = ROOT / "integrations/executors/hermes/sync_hermes_workflow_assets.py"
        spec = importlib.util.spec_from_file_location("workflow_sync_new", script)
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        with tempfile.TemporaryDirectory() as raw:
            temp = Path(raw)
            repo = temp / "repo"
            home = temp / "home"
            (repo / "config").mkdir(parents=True)
            home.mkdir()
            (repo / "config/config.yaml").write_text(
                "model:\n  provider: openai-codex\n  default: gpt-portable\n"
                "platform_toolsets:\n  cli: [terminal, file]\n"
                "mcp_servers:\n  context7:\n    command: hermes-npx\n",
                encoding="utf-8",
            )

            module.merge_live_config(repo, home, apply=True)
            result = yaml.safe_load((home / "config.yaml").read_text(encoding="utf-8"))
            self.assertNotIn("model", result)
            self.assertEqual(result["platform_toolsets"]["cli"], ["terminal", "file"])
            self.assertEqual(set(result["mcp_servers"]), {"context7"})

    def test_sync_is_model_neutral_and_manages_only_user_workflow_overlay(self) -> None:
        script = ROOT / "integrations/executors/hermes/sync_hermes_workflow_assets.py"
        spec = importlib.util.spec_from_file_location("workflow_sync_model_ux", script)
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        with tempfile.TemporaryDirectory() as raw:
            temp = Path(raw)
            repo = temp / "repo"
            home = temp / "home"
            (repo / "config").mkdir(parents=True)
            home.mkdir()
            (repo / "config/config.yaml").write_text(
                "model:\n  max_tokens: 8192\n"
                "agent:\n  reasoning_effort: low\n"
                "display:\n  busy_input_mode: queue\n"
                "model_picker:\n  custom_lanes:\n    enabled: true\n    lanes: [{label: KIMI 系列}]\n"
                "quick_commands:\n  切换kimi: {type: alias, target: /model kimi-k3 --provider kimi-coding}\n"
                "platform_toolsets:\n  cli: [terminal, file, skills]\n"
                "sessions:\n  auto_prune: false\n"
                "memory:\n  memory_enabled: true\n  user_profile_enabled: true\n",
                encoding="utf-8",
            )
            (home / "config.yaml").write_text(
                "model:\n  provider: deepseek\n  default: deepseek-v4-pro\n  max_tokens: 123\n"
                "agent:\n  reasoning_effort: high\n"
                "display:\n  busy_input_mode: interrupt\n"
                "model_picker:\n  custom_lanes:\n    enabled: false\n"
                "quick_commands:\n  切换旧模型: {type: alias, target: /model old}\n  我的命令: {type: alias, target: /help}\n",
                encoding="utf-8",
            )
            module.merge_live_config(repo, home, apply=True)
            result = yaml.safe_load((home / "config.yaml").read_text(encoding="utf-8"))
            self.assertEqual(result["model"]["provider"], "deepseek")
            self.assertEqual(result["model"]["default"], "deepseek-v4-pro")
            self.assertEqual(result["model"]["max_tokens"], 123)
            self.assertEqual(result["agent"]["reasoning_effort"], "high")
            self.assertEqual(result["display"]["busy_input_mode"], "queue")
            self.assertFalse(result["model_picker"]["custom_lanes"]["enabled"])
            self.assertEqual(set(result["quick_commands"]), {"切换旧模型", "我的命令"})
            self.assertEqual(result["platform_toolsets"]["cli"], ["terminal", "file", "skills"])
            self.assertFalse(result["sessions"]["auto_prune"])
            self.assertTrue(result["memory"]["memory_enabled"])

    def test_sync_rejects_changes_to_user_owned_config_snapshot(self) -> None:
        script = ROOT / "integrations/executors/hermes/sync_hermes_workflow_assets.py"
        spec = importlib.util.spec_from_file_location("workflow_sync_preservation", script)
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        contract = {
            "managed": {

                "mcp_servers": {"strategy": "merge_owned", "owned_names": ["context7"]},
                "hooks.pre_tool_call": "replace_owned_matcher",
            },
            "preserved": [
                "model.provider",
                "model.default",
                "model.base_url",
                "model.api_key",
                "model.other",
                "credentials",
                "model_picker.user_defined",
                "quick_commands.user_defined",
                "mcp_servers.user_defined",
                "plugins",
            ],
        }
        live = {
            "model": {
                "provider": "user-provider",
                "default": "user-model",
                "base_url": "https://user.example.invalid/v1",
                "api_key": "[REDACTED]",
                "extra": {"user_flag": True},
            },
            "credentials": {"user_owned": True},
            "model_picker": {"lanes": ["user lane"]},
            "quick_commands": {"user-command": {"target": "/help"}},
            "mcp_servers": {"context7": {"command": "managed"}, "custom": {"command": "user"}},
            "plugins": {"enabled": ["security-guidance", "custom-plugin"], "disabled": ["user-disabled"]},
            "hooks": {
                "pre_tool_call": [
                    {"matcher": "terminal", "command": "managed"},
                    {"matcher": "browser", "command": "user"},
                ],
                "custom_hook_setting": "keep",
            },
            "display": {"skin": "managed", "custom_display_setting": "keep"},
            "unknown_future_section": {"user_value": "keep"},
        }
        repo_data = {"mcp_servers": {"context7": {"command": "managed"}}}

        snapshot = module.snapshot_preserved_live_config(live, repo_data, contract)

        def assert_rejected(changed: dict) -> None:
            with self.assertRaisesRegex(ValueError, "preserved live config"):
                module.assert_preserved_live_config(snapshot, changed, repo_data, contract)

        for label, path, value in (
            ("model route", ("model", "base_url"), "https://overwritten.invalid/v1"),
            ("unknown future field", ("unknown_future_section", "user_value"), "overwritten"),
            ("custom MCP", ("mcp_servers", "custom", "command"), "overwritten"),
            ("custom hook", ("hooks", "custom_hook_setting"), "overwritten"),
            ("managed sibling", ("display", "custom_display_setting"), "overwritten"),
        ):
            changed = yaml.safe_load(yaml.safe_dump(live))
            target = changed
            for key in path[:-1]:
                target = target[key]
            target[path[-1]] = value
            with self.subTest(label=label):
                assert_rejected(changed)

        changed = yaml.safe_load(yaml.safe_dump(live))
        changed["plugins"]["enabled"].remove("custom-plugin")
        assert_rejected(changed)

    def test_isolated_baseline_can_merge_managed_config_and_preserve_user_config(self) -> None:
        """The isolated verifier path can construct the portable config baseline."""

        script = ROOT / "integrations/executors/hermes/sync_hermes_workflow_assets.py"
        spec = importlib.util.spec_from_file_location("workflow_sync_config_promotion", script)
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        with tempfile.TemporaryDirectory() as raw:
            temp_root = Path(raw)
            repo = temp_root / "portable-repo"
            for relative in (
                "config",
                "packages/client-neutral-core/skills",
                "packages/client-neutral-core/bin",
            ):
                shutil.copytree(ROOT / relative, repo / relative)
            home = temp_root / "home"
            home.mkdir()
            config = home / "config.yaml"
            config.write_text(
                "model:\n  provider: user-provider\n  default: user-model\n"
                "mcp_servers:\n  user-owned: {command: user-command}\n",
                encoding="utf-8",
            )

            module.deploy_portable(
                repo,
                home,
                apply=True,
                include_backup=False,
                include_config=True,
                allow_project_runtime_home=True,
            )

            live = yaml.safe_load(config.read_text(encoding="utf-8"))
            self.assertEqual(live["model"]["provider"], "user-provider")
            self.assertEqual(live["model"]["default"], "user-model")
            self.assertIn("user-owned", live["mcp_servers"])
            self.assertIn("context7", live["mcp_servers"])
            self.assertEqual(live["display"]["language"], "zh")
            self.assertTrue((home / "SOUL.md").is_file())
            self.assertFalse(any(home.glob(".workflow-assistance-staging-*")))

    def test_setup_does_not_default_enable_optional_capabilities(self) -> None:
        scripts = "\n".join(
            (ROOT / name).read_text(encoding="utf-8") for name in ("scripts/setup-workflow.sh", "scripts/setup-workflow.ps1")
        )
        self.assertIn("PyYAML >=6,<7 is required", scripts)
        self.assertIn("import yaml", scripts)
        for command in (
            "tools enable x_search",
            "tools enable video",
            "tools enable spotify",
            "plugins enable disk-cleanup",
            "plugins enable google_meet",
            "plugins enable spotify",
        ):
            self.assertNotIn(command, scripts)
        self.assertNotIn("[switch]$DryRun", (ROOT / "scripts/setup-workflow.ps1").read_text(encoding="utf-8"))
        ps_setup = (ROOT / "scripts/setup-workflow.ps1").read_text(encoding="utf-8")
        sh_setup = (ROOT / "scripts/setup-workflow.sh").read_text(encoding="utf-8")
        self.assertIn("[switch]$Apply", ps_setup)
        self.assertIn("APPLY=0", sh_setup)
        for setup in (ps_setup, sh_setup):
            self.assertIn("sync_hermes_workflow_assets.py", setup)
            self.assertIn("--plan-json", setup)
            self.assertIn("--approved", setup)
        self.assertNotIn("--apply --approved\n", ps_setup)
        self.assertNotIn("--apply --approved \\\n", sh_setup)

    def test_readme_never_extracts_credentials_from_auth_files(self) -> None:
        readme = (ROOT / "docs/current/workflow-assistance-README.md").read_text(encoding="utf-8")
        self.assertNotIn("json.load(open(r'~/.codex/auth.json'))", readme)
        self.assertIn("packages/client-neutral-core/skills/model-switch/SKILL.md", readme)

    def test_readme_documents_the_complete_current_feature_surface(self) -> None:
        readme = (ROOT / "docs/current/workflow-assistance-README.md").read_text(encoding="utf-8")
        for heading in (
            "## 项目定位",
            "## 功能总览",
            "## Portable 部署与安全同步",
            "## 模型切换与路由诊断",
            "## Codex 编码执行器",
            "## MCP 与 Hermes 原生工具",
            "## Agent 工作流治理",
            "## Skills 能力库",
            "## 安全与隐私",
            "## 模板、文档与审计",
            "## 测试与持续集成",
            "## 使用边界",
        ):
            self.assertIn(heading, readme)
        for command_or_path in (
            "integrations/executors/hermes/sync_hermes_workflow_assets.py",
            "packages/client-neutral-core/scripts/build_context_pack.py",
            "packages/client-neutral-core/scripts/mcp_candidate_audit.py",
            "services/orchestration/run_quality_gate.py",
            "integrations/executors/hermes/switch_model.py",
            "integrations/executors/hermes/hermes_workflow_doctor.py",
            "packages/client-neutral-core/scripts/security/scan_agent_rules.py",
            "Justfile",
            "templates/task-tickets/model-neutral-agent-task.md",
            "templates/evals/agent-behavior-smoke.yaml",
            "templates/ui/skin-presets.yaml",
            "templates/windows-terminal/catppuccin-mocha.json",
            "docs/history/archive/workflow-assistance/audit/model-neutral-agent-harness-absorption-2026-07.yaml",
            "hermes mcp test context7",
            "git write-tree",
            "--live",
        ):
            self.assertIn(command_or_path, readme)
        for skill in (ROOT / "packages" / "client-neutral-core" / "skills").rglob("SKILL.md"):
            self.assertIn(skill.parent.name, readme, skill.relative_to(ROOT).as_posix())
        for template in (ROOT / "packages" / "client-neutral-core" / "templates").rglob("*.md"):
            self.assertIn(template.name, readme, template.relative_to(ROOT).as_posix())
        # README must only reference real repository files (markdown link and
        # code-span integrity). After the directory convergence the docs tree is
        # repository-wide, so a complete enumeration obligation no longer holds;
        # the meaningful contract is: every path the README cites must exist.
        for cited in re.findall(r"[`\[]([A-Za-z0-9_./\-]+\.(?:md|yaml|json|py|sh|ps1|cmd|yml))[`\]]", readme):
            if not cited.startswith(("docs/", "packages/", "config/", ".project/", "services/", "integrations/", "scripts/", "templates/", "apps/", "bin/")):
                continue
            if "$" in cited or cited.startswith("../../") or "workflow-assistance-" in cited and cited.count("/") == 0:
                continue
            if cited.startswith("docs/current/workflow-assistance-TROUBLESHOOTING.md"):
                self.assertTrue((ROOT / cited).exists(), cited)
                continue
            self.assertTrue((ROOT / cited).exists(), cited)
        config = yaml.safe_load((ROOT / "config/config.yaml").read_text(encoding="utf-8"))
        for toolset in config["platform_toolsets"]["cli"]:
            self.assertIn(f"`{toolset}`", readme)
        for semantic in (
            "创建时间戳备份",
            "mcp_servers.owned_names",
            "历史或用户 MCP",
            "绝不 promotion live `config.yaml`",
            "plugin migration state 同属 mixed-ownership config",
            "输出 repo/live 目录哈希",
            "绝不把 live skills",
            "显示脱敏后的 Hermes Provider/模型配置",
            "Hermes 版本、配置、认证 inventory 和 MCP inventory",
            "普通端口、HTTP 状态和结构检查不等于真实模型执行",
            "Context7 查询会外发数据",
            "一个 checkout 只能有一个 writer",
            "Task Ticket、plan mode、hook、路径声明和 worktree 都不是安全 sandbox",
            "客户端中立工作流控制、治理、任务、交付与可观测层",
            "不是 Agent Runtime、聊天软件、模型网关",
            "Hermes 当前仍是一级深度支持 Adapter，但不是核心架构前提",
            "只对本仓库有用的临时脚本不得被包装成默认全局能力",
            "Context Pack",
            ".project-local/artifacts/context-pack.md",
            "MCP_CANDIDATE_AUDIT_PASS",
            "UI/Skin 系统",
            "不默认安装 UI runtime",
            "本地 quality gate runner 命令顺序",
            "python services/orchestration/run_quality_gate.py verify",
            "每次 push 和 pull request",
            "CI verdict 绑定提交 SHA",
        ):
            self.assertIn(semantic, readme)
        self.assertNotIn("一次性迁移状态只保护退役插件", readme)
        self.assertNotIn("避免后续误删用户重新启用的功能", readme)
        self.assertIn("不会安装 Hermes、Codex 或 CC Switch 主体", readme)
        self.assertIn("结构检查不等于真实模型执行", readme)

    def test_project_definition_scope_is_global_workflow_enhancement(self) -> None:
        definition = (ROOT / "docs/current/workflow-assistance/workflow/project-definition.md").read_text(
            encoding="utf-8"
        )
        for marker in (
            "客户端中立的工作流控制、治理、任务、交付与可观测层",
            "本仓库是可审计的 portable source",
            "Hermes、Codex、CC Switch、GitHub、OpenHuman、Open Design 是当前一级可替换 Adapter",
            "## 全局增强边界",
            "任意业务项目",
            "不得进入默认 portable config、全局 skill、默认 MCP 或同步脚本",
        ):
            self.assertIn(marker, definition)
        self.assertIn("核心不是 Agent、聊天软件或模型网关", definition)
        self.assertNotIn("只对本仓库生效的局部工具集：\n\n## 四层职责", definition)

    def test_doctor_distinguishes_structural_and_live_checks(self) -> None:
        doctor = (ROOT / "integrations/executors/hermes/hermes_workflow_doctor.py").read_text(
            encoding="utf-8"
        )
        self.assertNotIn("server-sequential-thinking", doctor)
        self.assertNotIn("public-apis-mcp", doctor)
        self.assertIn("['hermes', 'mcp', 'test', 'context7']", doctor)
        self.assertIn("--live", doctor)
        self.assertIn("structural checks do not prove provider execution", doctor)

        sys.path.insert(0, str(ROOT / "scripts/workflow"))
        try:
            spec = importlib.util.spec_from_file_location(
                "workflow_doctor", ROOT / "integrations/executors/hermes/hermes_workflow_doctor.py"
            )
            self.assertIsNotNone(spec)
            self.assertIsNotNone(spec.loader)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
        finally:
            sys.path.pop(0)
        self.assertFalse(module.has_exact_marker("Only reply OK_LIVE", "OK_LIVE"))
        self.assertFalse(module.has_exact_marker("prompt: OK_LIVE", "OK_LIVE"))
        self.assertTrue(module.has_exact_marker("noise\nOK_LIVE\n", "OK_LIVE"))
        with patch.object(module, "print_command", return_value=(1, "simulated required failure")):
            self.assertFalse(module.required_command("required smoke", ["fake"], timeout=1))
        leaked = "github_pat_" + "A" * 30 + " npm_" + "B" * 30 + " xoxb-" + "C" * 30
        redacted = module.redact(leaked)
        self.assertNotIn("A" * 30, redacted)
        self.assertNotIn("B" * 30, redacted)
        self.assertNotIn("C" * 30, redacted)

        json_secret = '"access_token": "' + "D" * 30 + '"'
        redacted_json = module.redact(json_secret)
        self.assertNotIn("D" * 30, redacted_json)
        self.assertIn("[REDACTED]", redacted_json)

        with patch.dict(
            "os.environ",
            {"HTTPS_PROXY": "http://user:password@127.0.0.1:7890"},
            clear=True,
        ):
            summary = module.proxy_environment_summary("HTTPS_PROXY")
        self.assertIn("HTTPS_PROXY=set", summary)
        self.assertIn("local_loopback=yes", summary)
        self.assertIn("credentials=present-redacted", summary)
        self.assertNotIn("user", summary)
        self.assertNotIn("password", summary)

        with patch.dict("os.environ", {"HTTPS_PROXY": "http://[::1"}, clear=True):
            invalid_summary = module.proxy_environment_summary("HTTPS_PROXY")
        self.assertEqual(
            invalid_summary,
            "HTTPS_PROXY=set scheme=invalid local_loopback=unknown credentials=redacted",
        )

        with patch.dict("os.environ", {"HTTPS_PROXY": "secret-token:rest"}, clear=True):
            secret_prefix_summary = module.proxy_environment_summary("HTTPS_PROXY")
        self.assertEqual(
            secret_prefix_summary,
            "HTTPS_PROXY=set scheme=invalid local_loopback=unknown credentials=redacted",
        )

        with patch.dict("os.environ", {"HTTPS_PROXY": "http://127.0.0.2:7890"}, clear=True):
            loopback_summary = module.proxy_environment_summary("HTTPS_PROXY")
        self.assertIn("local_loopback=yes", loopback_summary)

    def test_doctor_live_codex_workspace_is_confined_to_project_runtime(self) -> None:
        script = ROOT / "integrations/executors/hermes/hermes_workflow_doctor.py"
        sys.path.insert(0, str(ROOT / "scripts/workflow"))
        try:
            spec = importlib.util.spec_from_file_location("workflow_doctor_workspace", script)
            self.assertIsNotNone(spec)
            self.assertIsNotNone(spec.loader)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
        finally:
            sys.path.pop(0)

        with tempfile.TemporaryDirectory() as raw:
            project = Path(raw)
            subprocess.run(["git", "init", "-q"], cwd=project, check=True, capture_output=True)
            canonical_project = Path(
                subprocess.run(
                    ["git", "-C", str(project), "rev-parse", "--show-toplevel"],
                    check=True,
                    capture_output=True,
                    text=True, encoding="utf-8", errors="replace",
                ).stdout.strip()
            ).resolve()
            default_workspace = module.resolve_live_codex_workspace(project, None)
            self.assertEqual(
                default_workspace.relative_to(canonical_project).as_posix(),
                ".hermes/task-runtime",
            )
            custom_workspace = module.resolve_live_codex_workspace(
                project, Path(".hermes/task-runtime/custom-codex-smoke")
            )
            self.assertEqual(
                custom_workspace.relative_to(canonical_project).as_posix(),
                ".hermes/task-runtime/custom-codex-smoke",
            )
            with self.assertRaises(SystemExit):
                module.resolve_live_codex_workspace(project, Path("../outside"))
            non_project = project / "not-a-git-project"
            non_project.mkdir()
            with self.assertRaises(SystemExit):
                module.resolve_live_codex_workspace(non_project, None)

    def test_windows_skill_does_not_bypass_provider_or_credential_boundaries(self) -> None:
        skill = ROOT / "packages/client-neutral-core/skills/software-development/windows-development-environment"
        body = (skill / "SKILL.md").read_text(encoding="utf-8")
        self.assertNotIn("hermes config set model.provider", body)
        self.assertNotIn('cp config/config.yaml "$HERMES_HOME/config.yaml"', body)
        self.assertNotIn('cp -r skills/* "$HERMES_HOME/skills/"', body)
        self.assertNotIn("tools enable x_search", body)
        self.assertIn("sync_hermes_workflow_assets.py", body)
        for marker in (
            "PowerShell selection policy",
            "prefer **PowerShell 7** via `pwsh`",
            "powershell.exe",
        ):
            self.assertIn(marker, body)
        for name in (
            "codex++-proxy-routing.md",
            "provider-network-troubleshooting.md",
            "third-party-proxy-setup.md",
            "credential-audit-and-template.md",
            "github-credential-extraction.md",
        ):
            self.assertFalse((skill / "references" / name).exists(), name)

    def test_sleep_mode_is_portable_and_enforces_durable_queue_boundaries(self) -> None:
        skill = ROOT / "packages/client-neutral-core/skills/software-development/sleep-mode/SKILL.md"
        self.assertTrue(skill.exists())
        body = skill.read_text(encoding="utf-8")
        for marker in (
            ".hermes/sleep-mode/",
            "state.json",
            "activity.jsonl",
            "每个项目只允许一条活跃写队列",
            "one writer, one bounded task per cycle",
            "不计入进度",
            "mode != active",
            "高风险",
        ):
            self.assertIn(marker, body)

        sync = (ROOT / "integrations/executors/hermes/sync_hermes_workflow_assets.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("def deploy_portable", sync)
        self.assertIn("def prepare_staging", sync)
        self.assertIn("def atomic_replace_paths", sync)
        self.assertIn("rollback-capable filesystem transaction", sync)

    def test_project_data_boundary_is_deployable_and_fail_closed(self) -> None:
        helper = ROOT / "packages/client-neutral-core/bin/hermes-project-data.py"
        skill = ROOT / "packages/client-neutral-core/skills/software-development/project-data-boundary/SKILL.md"
        doc = ROOT / "docs/current/workflow-assistance/workflow/project-data-boundary.md"
        self.assertTrue(helper.exists())
        self.assertTrue(skill.exists())
        self.assertTrue(doc.exists())
        body = helper.read_text(encoding="utf-8")
        for marker in (
            "git-ignored",
            "check-ignore",
            "TMP",
            "PIP_CACHE_DIR",
            "PYTHONPYCACHEPREFIX",
            "path escapes project root",
        ):
            self.assertIn(marker, body)
        self.assertIn("hermes-project-data.py", (ROOT / "docs/current/workflow-assistance-README.md").read_text(encoding="utf-8"))

    def test_context_pack_generator_is_project_local_and_secret_redacting(self) -> None:
        script = ROOT / "packages/client-neutral-core/scripts/build_context_pack.py"
        doc = ROOT / "docs/current/workflow-assistance/workflow/context-pack.md"
        self.assertTrue(script.exists())
        self.assertTrue(doc.exists())

        spec = importlib.util.spec_from_file_location("context_pack", script)
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        with tempfile.TemporaryDirectory() as raw:
            repo = Path(raw)
            subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
            (repo / ".gitignore").write_text(".hermes/\n.project-local/\n", encoding="utf-8")
            (repo / "README.md").write_text("# Demo\n", encoding="utf-8")
            (repo / "config").mkdir()
            secret = "github_pat_" + "A" * 30
            (repo / "config/config.yaml").write_text(
                f"display:\n  busy_input_mode: queue\napi_key: {secret}\n",
                encoding="utf-8",
            )
            (repo / "docs/current/workflow-assistance/workflow").mkdir(parents=True)
            (repo / "docs/current/workflow-assistance/workflow/project-definition.md").write_text(
                "# Definition\nHermes Agent + CC Switch + Codex\n",
                encoding="utf-8",
            )
            subprocess.run(
                [
                    "git",
                    "add",
                    ".gitignore",
                    "README.md",
                    "config/config.yaml",
                    "docs/current/workflow-assistance/workflow/project-definition.md",
                ],
                cwd=repo,
                check=True,
                capture_output=True,
            )

            output = module.write_context_pack(repo, module.DEFAULT_OUTPUT, max_chars=20000)
            body = output.read_text(encoding="utf-8")
            self.assertEqual(
                module.canonical_path(output).relative_to(module.canonical_path(repo)).as_posix(),
                ".project-local/artifacts/context-pack.md",
            )
            self.assertIn("Workflow-assistance Context Pack", body)
            self.assertIn("global Hermes Agent + CC Switch + Codex workflow", body)
            self.assertIn("[REDACTED]", body)
            self.assertNotIn(secret, body)
            self.assertNotIn("auth.json", "\n".join(module.tracked_inventory(repo)))
            outside = repo.parent / "outside-context.txt"
            outside.write_text("must not enter context", encoding="utf-8")
            self.assertIsNone(module.read_safe_text(repo, "../outside-context.txt"))

            with self.assertRaises(SystemExit):
                module.write_context_pack(repo, Path("context-pack.md"), max_chars=20000)
            with self.assertRaises(SystemExit):
                module.write_context_pack(repo, Path("../context-pack.md"), max_chars=20000)

    def test_context_pack_uses_canonical_paths_for_windows_short_name_aliases(self) -> None:
        script = ROOT / "packages/client-neutral-core/scripts/build_context_pack.py"
        spec = importlib.util.spec_from_file_location("context_pack_alias", script)
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        with tempfile.TemporaryDirectory() as raw:
            repo = Path(raw)
            subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
            (repo / ".gitignore").write_text(".hermes/\n.project-local/\n", encoding="utf-8")
            (repo / "README.md").write_text("# Demo\n", encoding="utf-8")
            subprocess.run(
                ["git", "add", ".gitignore", "README.md"],
                cwd=repo,
                check=True,
                capture_output=True,
            )

            alias_root = Path(str(repo) + "-SHORT-ALIAS")
            real_canonical_path = module.canonical_path

            def fake_canonical_path(path: Path) -> Path:
                text = str(path)
                alias = str(alias_root)
                if text == alias or text.startswith(alias + "\\") or text.startswith(alias + "/"):
                    suffix = text[len(alias) :].lstrip("\\/")
                    return repo / suffix if suffix else repo
                return real_canonical_path(path)

            module.canonical_path = fake_canonical_path
            try:
                output = module.write_context_pack(
                    alias_root, module.DEFAULT_OUTPUT, max_chars=20000
                )
            finally:
                module.canonical_path = real_canonical_path

            self.assertEqual(
                module.canonical_path(output).relative_to(module.canonical_path(repo)).as_posix(),
                ".project-local/artifacts/context-pack.md",
            )

    def test_quality_gate_runner_is_canonical_and_just_is_optional(self) -> None:
        runner = ROOT / "services/orchestration/run_quality_gate.py"
        justfile = ROOT / "Justfile"
        doc = ROOT / "docs/current/workflow-assistance/workflow/local-quality-gates.md"
        workflow = ROOT / "docs/current/workflow-assistance/workflow/examples/governance.yml.example"
        self.assertTrue(runner.exists())
        self.assertTrue(justfile.exists())
        self.assertTrue(doc.exists())

        spec = importlib.util.spec_from_file_location("quality_gate", runner)
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        self.assertEqual(
            module.VERIFY_ORDER,
            (
                "governance",
                "compile",
                "skill-provenance",
                "security",
                "context-pack",
                "client-neutral-manifest",
                "core-schemas",
                "adapter-registry",
                "capability-matrix",
                "model-registry-integrity",
                "acp-adapter-honesty",
                "observer-readonly-boundary",
                # Added 2026-10-08: `verify` said GATE_EXIT=0 twice while the CI observer job went red,
                # because the observer JS contract suite and vitest had no local route.
                "observer-frontend-contracts",
                "registry-closure-report",
                "evidence-tiering",
                "root-governance-suite",
                "policy-coverage",
                # added 2026-10-08: the blueprint projection was a CI-only rule and went stale from an
                # honest register edit that a local run could not see.
                "blueprint-projection",
                "context-control-plane",
                "external-libraries-index",
                "protected-drives-consistency",
                "three-project-boundary",
                "github-delivery",
                "adapter-conformance",
                "acp-conformance",
                "otel-mapping",
                "usage-ingestion",
                "memory-contamination",
                "task-ledger-replay",
                "portable-install",
                "provider-inventory",
                "plugin-inventory-honesty",
                "mcp-audit",
                "shell",
                "runtime-convergence",
                "powershell",
                # WLGM §7 named gates.
                "project-identity-contract",
                "agent-adapter-readonly-contract",
                "execution-state-machine",
                "collector-noninterference",
                "canonical-single-writer",
                "observer-no-business-write",
                "snapshot-schema-v3",
                "sse-browser-reconnect",
                "field-quality-no-fabrication",
                "privacy-redaction",
                "windows-project-resolution",
                "tauri-readonly-shell",
                "work-lab-os-canary",
                "exact-sha-ci",
            ),
        )
        self.assertEqual(set(module.GATES), set(module.VERIFY_ORDER) | {"portable-install-runtime"})
        self.assertIn("services/orchestration/run_quality_gate.py", module.tracked_python_files())
        self.assertIn("tests/workflow-assistance/test_workflow_governance.py", module.tracked_python_files())
        self.assertIn("packages/client-neutral-core/bin/hermes-project-data.py", module.tracked_python_files())
        self.assertIn("packages/client-neutral-core/bin/hermes-project-terminal-guard.py", module.tracked_python_files())

        body = runner.read_text(encoding="utf-8")
        for marker in (
            "QUALITY_GATE_PASS",
            "QUALITY_GATE_FAIL",
            "build_context_pack.py",
            "mcp_candidate_audit.py",
            "verify_client_neutral_manifest.py",
            "client-neutral-manifest",
            "verify_core_schemas.py",
            "core-schemas",
            "verify_adapter_registry.py",
            "adapter-registry",
            "portable-install-runtime",
            "--runtime",
            "scan_agent_rules.py",
            "usable_bash()",
            "QUALITY_GATE_NOT_RUN gate=shell reason=BASH_ABSENT",
            "QUALITY_GATE_NOT_RUN gate=powershell reason=PWSH_ABSENT",
            "shutil.which(\"pwsh\") or shutil.which(\"powershell.exe\")",
            "ParseFile((Resolve-Path ./scripts/setup-workflow.ps1)",
        ):
            self.assertIn(marker, body)
        self.assertNotIn("shell=True", body)
        self.assertNotIn("npm install just", body)
        self.assertNotIn("choco install just", body)

        just = justfile.read_text(encoding="utf-8")
        self.assertIn("python services/orchestration/run_quality_gate.py verify", just)
        self.assertIn("python services/orchestration/run_quality_gate.py mcp-audit", just)
        self.assertIn("just is not a required dependency", just)

        combined = "\n".join(
            (
                doc.read_text(encoding="utf-8"),
                workflow.read_text(encoding="utf-8"),
                (ROOT / "docs/current/workflow-assistance-README.md").read_text(encoding="utf-8"),
            )
        )
        for marker in (
            "python services/orchestration/run_quality_gate.py verify",
            "just is not a required dependency",
            "QUALITY_GATE_PASS",
            "QUALITY_GATE_FAIL",
            "context-pack",
            "client-neutral-manifest",
            "core-schemas",
            "mcp-audit",
            "PowerShell gate 优先 `pwsh`",
        ):
            self.assertIn(marker, combined)
        self.assertEqual(
            workflow.read_text(encoding="utf-8").count(
                "python services/orchestration/run_quality_gate.py verify"
            ),
            2,
        )
        for setup in ("scripts/setup-workflow.sh", "scripts/setup-workflow.ps1"):
            self.assertNotIn("just", (ROOT / setup).read_text(encoding="utf-8").lower())

        list_result = subprocess.run(
            [sys.executable, str(runner), "list"],
            cwd=ROOT,
            text=True, encoding="utf-8", errors="replace",
            capture_output=True,
            check=True,
        )
        self.assertIn(
            # Derived rather than retyped: the tuple above is what pins the order, and this asserts the
            # runner's own `list` output agrees with it. The literal this replaces had to be edited in
            # two places on every gate addition and stopped matching after the first new gate.
            "verify: Run " + ", ".join(module.VERIFY_ORDER),
            list_result.stdout,
        )
        self.assertTrue({"design-contract", "production-evidence", "standard-validators"}.isdisjoint(module.GATES))

    def test_mcp_candidate_audit_is_fail_closed_and_does_not_enable_defaults(self) -> None:
        script = ROOT / "packages/client-neutral-core/scripts/mcp_candidate_audit.py"
        doc = ROOT / "docs/current/workflow-assistance/mcp/mcp-catalog-governance.md"
        stack = ROOT / "docs/current/workflow-assistance/mcp/workflow-mcp-stack.md"
        self.assertTrue(script.exists())
        self.assertTrue(doc.exists())

        spec = importlib.util.spec_from_file_location("mcp_candidate_audit", script)
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        good = {
            "schema_version": 1,
            "name": "docs-search-mcp",
            "status": "candidate",
            "default_enable": False,
            "source": {
                "package": "@example/docs-search-mcp@1.2.3",
                "repository": "https://github.com/example/docs-search-mcp",
                "license": "MIT",
                "version": "1.2.3",
            },
            "purpose": "Search a public docs index not covered by Context7.",
            "distinct_advantage": "Narrow public docs index with stable citations.",
            "data_external": True,
            "permissions": {
                "filesystem": "none",
                "network": "public docs API",
                "browser": "none",
                "credentials": [],
            },
            "required_env": [],
            "overlaps_native_tools": ["web_search"],
            "smoke": {
                "command": "hermes mcp test docs-search-mcp",
                "status": "not_run",
                "evidence": "candidate only",
            },
            "prompt_schema_budget": {
                "measured": False,
                "command": "hermes prompt-size --json",
                "delta_tokens": None,
            },
        }
        passed, findings = module.audit_candidate(good)
        self.assertTrue(passed, findings)

        bad = dict(good)
        bad["default_enable"] = True
        bad["source"] = dict(good["source"], package="@example/docs-search-mcp@latest", version="latest")
        bad["smoke"] = dict(good["smoke"], status="not_run")
        passed, findings = module.audit_candidate(bad)
        self.assertFalse(passed)
        codes = {finding["code"] for finding in findings}
        self.assertTrue(
            {
                "default_enable_requested",
                "default_without_smoke_pass",
                "default_without_prompt_budget",
                "unpinned_version",
            }.issubset(codes),
            findings,
        )

        with tempfile.TemporaryDirectory() as raw:
            temp = Path(raw)
            template = temp / "candidate.yaml"
            module.write_template(template)
            template_body = yaml.safe_load(template.read_text(encoding="utf-8"))
            self.assertFalse(template_body["default_enable"])
            result = subprocess.run(
                [sys.executable, str(script), str(template)],
                cwd=ROOT,
                text=True, encoding="utf-8", errors="replace",
                capture_output=True,
                check=True,
            )
            self.assertIn("MCP_CANDIDATE_AUDIT_PASS", result.stdout)

        combined = "\n".join(
            (
                script.read_text(encoding="utf-8"),
                doc.read_text(encoding="utf-8"),
                stack.read_text(encoding="utf-8"),
                (ROOT / "docs/current/workflow-assistance-README.md").read_text(encoding="utf-8"),
            )
        )
        for marker in (
            "MCP_CANDIDATE_AUDIT_PASS",
            "MCP_CANDIDATE_AUDIT_FAIL",
            "default_enable_requested",
            "overlaps_native_tools",
            "prompt_schema_budget",
            "不等于 server 已配置、已运行、已安全或已默认启用",
        ):
            self.assertIn(marker, combined)
        self.assertNotIn("hermes mcp add", script.read_text(encoding="utf-8"))
        self.assertEqual(
            set(yaml.safe_load((ROOT / "config/config.yaml").read_text(encoding="utf-8"))["mcp_servers"]),
            {"context7"},
        )

    def test_portable_skills_do_not_link_to_missing_references(self) -> None:
        for skill in (ROOT / "packages" / "client-neutral-core" / "skills").rglob("SKILL.md"):
            body = skill.read_text(encoding="utf-8")
            references = re.findall(r"references/[A-Za-z0-9._+/-]+\.md", body)
            missing = [ref for ref in references if not (skill.parent / ref).exists()]
            self.assertEqual(missing, [], skill.relative_to(ROOT).as_posix())

    def test_codex_skill_matches_current_noninteractive_boundary(self) -> None:
        body = (ROOT / "packages/client-neutral-core/skills/autonomous-ai-agents/codex/SKILL.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("`codex exec`, `codex review`", body)
        self.assertIn("use `pty=false`", body)
        self.assertIn("One writer per checkout", body)
        self.assertNotIn("codex --yolo exec", body)
        self.assertNotIn("exec --full-auto", body)
        self.assertNotIn("background=true, pty=true", body)
        self.assertNotIn("C:/Users/", body)

    def test_review_alias_has_no_second_commit_or_autofix_pipeline(self) -> None:
        body = (ROOT / "packages/client-neutral-core/skills/software-development/requesting-code-review/SKILL.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("agent-workflow-fortress", body)
        self.assertNotIn("git add -A &&", body)
        self.assertNotIn("Auto-fix loop", body)
        self.assertNotIn("git stash", body)
        self.assertNotIn("frozen-review references", body)

    def test_model_routing_has_one_executable_source_of_truth(self) -> None:
        active = [
            ROOT / "config/config.yaml",
            ROOT / "integrations/executors/hermes/switch_model.py",
            ROOT / "integrations/executors/hermes/hermes_workflow_doctor.py",
            ROOT / "packages/client-neutral-core/skills/model-switch/SKILL.md",
        ]
        config = yaml.safe_load((ROOT / "config/config.yaml").read_text(encoding="utf-8"))
        switcher = (ROOT / "integrations/executors/hermes/switch_model.py").read_text(encoding="utf-8")
        doctor = (ROOT / "integrations/executors/hermes/hermes_workflow_doctor.py").read_text(encoding="utf-8")
        self.assertNotIn("model", config)
        self.assertIn("selected_model", switcher)
        self.assertIn("--model", switcher)
        self.assertIn("HERMES_GPT_MODEL", switcher)
        self.assertIn("configured_model", doctor)
        self.assertNotIn("from switch_model import DEEPSEEK_MODEL, GPT_MODEL", doctor)
        self.assertNotIn('os.environ.get("HERMES_GPT_MODEL", "gpt-5.6-sol")', switcher)
        self.assertIn("--live", switcher)
        refs = ROOT / "packages/client-neutral-core/skills/model-switch/references"
        self.assertFalse((refs / "cc-switch-codex-hermes.md").exists())
        self.assertFalse((refs / "oauth-credential-sync.md").exists())
        fortress_ref = ROOT / "packages/client-neutral-core/skills/software-development/agent-workflow-fortress/references/hermes-provider-mcp-workflow.md"
        self.assertFalse(fortress_ref.exists())

    def test_gpt_oauth_switch_does_not_require_cc_switch_proxy(self) -> None:
        switcher = (ROOT / "integrations/executors/hermes/switch_model.py").read_text(encoding="utf-8")
        skill = (ROOT / "packages/client-neutral-core/skills/model-switch/SKILL.md").read_text(encoding="utf-8")
        self.assertIn("codex_auth_present", switcher)
        self.assertNotIn("CC Switch proxy 127.0.0.1:7890 is not open", switcher)
        self.assertIn("不能因该端口关闭而阻断", skill)

    def test_windows_skill_requires_explicit_interpreter_selection(self) -> None:
        skill = (ROOT / "packages/client-neutral-core/skills/software-development/windows-development-environment/SKILL.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("Do not assume `python` and `python3` resolve to the same interpreter.", skill)
        self.assertIn("Hermes workflow scripts use `python`", skill)
        legacy_deployment = (
            ROOT
            / "packages/client-neutral-core/skills/software-development/windows-development-environment/references"
            / "hermes-deployment-pack-structure.md"
        ).read_text(encoding="utf-8")
        self.assertIn("routing-neutral", legacy_deployment)
        self.assertNotIn("CC Switch", legacy_deployment)
        self.assertNotIn("复制 config.yaml / SOUL.md", legacy_deployment)

    def test_kimi_retired_and_model_switch_contract_kept(self) -> None:
        switcher = (ROOT / "integrations/executors/hermes/switch_model.py").read_text(encoding="utf-8")
        skill = (ROOT / "packages/client-neutral-core/skills/model-switch/SKILL.md").read_text(encoding="utf-8")
        lanes = (ROOT / "packages/client-neutral-core/skills/model-switch/references/current-model-lanes.md").read_text(
            encoding="utf-8"
        )
        latency = (ROOT / "packages/client-neutral-core/skills/model-switch/references/latency-tuning.md").read_text(
            encoding="utf-8"
        )

        for marker in (
            "HERMES_KIMI_MODEL",
            "HERMES_KIMI_FAST_MODEL",
            "HERMES_KIMI_TURBO_MODEL",
            "'kimi-fast'",
            "'kimi-turbo'",
            "if args.target == 'kimi-turbo':",
            "elif args.target == 'kimi-fast':",
            "KIMI_BASE_URL",
        ):
            self.assertNotIn(marker, switcher)
        for command in (
            'switch_model.py kimi --model',
            'switch_model.py kimi-fast --model',
            'switch_model.py kimi-turbo --model',
        ):
            self.assertNotIn(command, skill)
            self.assertNotIn(command, lanes)

        self.assertIn("def selected_model(override: str | None, env_name: str, target: str)", switcher)
        self.assertIn("HERMES_DEEPSEEK_MODEL", switcher)
        self.assertIn("HERMES_GPT_MODEL", switcher)
        self.assertIn("Provider 路线只作为入口", skill)
        self.assertIn("具体模型必须由用户", skill)
        self.assertIn("HERMES_DEEPSEEK_MODEL", lanes)
        self.assertIn("HERMES_GPT_MODEL", lanes)
        self.assertIn("default model", lanes)
        self.assertIn("--model", lanes)
        self.assertIn("kimi-k2.7-code", latency)
        self.assertIn("kimi-k2.7-code-highspeed", latency)
        self.assertIn("explicitly selected", latency)

    def test_external_harness_absorption_is_model_and_paid_api_neutral(self) -> None:
        fortress = ROOT / "packages/client-neutral-core/skills/software-development/agent-workflow-fortress"
        reference = fortress / "references/free-local-agent-harness-absorption.md"
        template = ROOT / "packages" / "client-neutral-core" / "templates/task-tickets/model-neutral-agent-task.md"
        self.assertTrue(reference.exists())
        self.assertTrue(template.exists())

        skill = (fortress / "SKILL.md").read_text(encoding="utf-8")
        reference_body = reference.read_text(encoding="utf-8")
        template_body = template.read_text(encoding="utf-8")
        combined = "\n".join((skill, reference_body, template_body))

        self.assertIn("references/free-local-agent-harness-absorption.md", skill)
        self.assertIn("https://github.com/xai-org/grok-build", reference_body)
        for marker in (
            "Completion contract",
            "Structured run state",
            "Fail-closed safety",
            "Single writer",
            "Exact-tree evidence",
        ):
            self.assertIn(marker, combined)
        for section in (
            "## Completion Contract",
            "## Run State Contract",
            "## Isolation and Permissions",
            "## Verification Evidence",
            "## Cost and Network Boundary",
        ):
            self.assertIn(section, template_body)
        self.assertNotIn(
            "Planning/review blocks edit tools, shell writes, redirection, and write-capable child workers.",
            template_body,
        )
        for enforcement_field in (
            "Enforcement mechanism: `<external sandbox/container/VM plus path and tool policy>`",
            "Tool deny list: `<edit, shell, redirection, child-worker and other denied capabilities>`",
            "Sandbox support verified: `<OS, command, result, or no>`",
            "Negative-control command/result: `<prove shell writes, chained commands and child writes are denied>`",
            "Declaring `plan` or `review` does not enforce read-only behavior.",
            "If enforcement or a negative control is unavailable, the task is `blocked`; do not claim read-only execution.",
            "Policy checks fail closed on errors, timeouts, malformed output, or uninspectable input.",
        ):
            self.assertIn(enforcement_field, template_body)

        forbidden = (
            "XAI_API_KEY",
            "api.x.ai",
            "provider: xai",
            "grok -p",
            "--model",
            "grok-4",
            "grok-build-0",
        )
        for marker in forbidden:
            self.assertNotIn(marker, combined)

    def test_model_neutral_absorption_is_discoverable_and_audited(self) -> None:
        readme = (ROOT / "docs/current/workflow-assistance-README.md").read_text(encoding="utf-8")
        audit = ROOT / "docs/history/archive/workflow-assistance/audit/model-neutral-agent-harness-absorption-2026-07.md"
        manifest_path = ROOT / "docs/history/archive/workflow-assistance/audit/model-neutral-agent-harness-absorption-2026-07.yaml"
        self.assertIn("templates/task-tickets/model-neutral-agent-task.md", readme)
        self.assertTrue(audit.exists())
        self.assertTrue(manifest_path.exists())

        manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(manifest["schema_version"], 1)
        self.assertEqual(
            manifest["source"]["commit"],
            "98c3b2438aa922fbbe6178a5c0a4c48f85edc8ce",
        )
        self.assertEqual(
            manifest["source"]["source_revision"],
            "124d85bc5dc6e7805560215fcc6d5413944920e1",
        )
        self.assertEqual(manifest["source"]["license"], "Apache-2.0")
        self.assertEqual(manifest["runtime_assets"], [])
        self.assertEqual(
            set(manifest["excluded_capabilities"]),
            {"models", "paid_apis", "providers", "credentials", "external_binaries"},
        )
        local_artifacts = manifest["local_artifacts"]
        self.assertGreaterEqual(len(local_artifacts), 6)
        for relative in local_artifacts:
            self.assertTrue((ROOT / relative).is_file(), relative)
            self.assertFalse(relative.startswith(("config/", "scripts/", "bin/")), relative)
        for evidence in manifest["evidence"]:
            self.assertTrue(evidence["upstream_paths"])
            self.assertTrue(evidence["local_paths"])
            for upstream_path in evidence["upstream_paths"]:
                self.assertFalse(upstream_path.startswith("http"), upstream_path)
            for local_path in evidence["local_paths"]:
                self.assertIn(local_path, local_artifacts)
                self.assertTrue((ROOT / local_path).is_file(), local_path)

        body = audit.read_text(encoding="utf-8")
        self.assertIn("https://github.com/xai-org/grok-build/tree/", body)
        self.assertIn(manifest["source"]["commit"], body)
        self.assertIn(manifest["source"]["source_revision"], body)
        self.assertIn("契约要求，不是运行时隔离证明", body)
        self.assertIn("已吸收", body)
        self.assertIn("明确排除", body)
        self.assertIn("未安装外部执行器", body)
        for marker in ("api.x.ai", "XAI_API_KEY", "grok -p", "--model"):
            self.assertNotIn(marker, body)

    def test_agent_behavior_eval_template_is_safe_and_model_neutral(self) -> None:
        readme = (ROOT / "docs/current/workflow-assistance-README.md").read_text(encoding="utf-8")
        doc_path = ROOT / "docs/current/workflow-assistance/workflow/agent-evaluation.md"
        template_path = ROOT / "packages" / "client-neutral-core" / "templates/evals/agent-behavior-smoke.yaml"
        absorption = (ROOT / "docs/current/workflow-assistance/absorption/open-source-workflow-absorption.md").read_text(
            encoding="utf-8"
        )

        self.assertTrue(doc_path.exists())
        self.assertTrue(template_path.exists())
        self.assertIn("docs/current/workflow-assistance/workflow/agent-evaluation.md", readme)
        self.assertIn("templates/evals/agent-behavior-smoke.yaml", readme)
        self.assertIn("promptfoo/promptfoo", absorption)

        doc = doc_path.read_text(encoding="utf-8")
        template_body = template_path.read_text(encoding="utf-8")
        template = yaml.safe_load(template_body)

        self.assertEqual(template["schema_version"], 1)
        self.assertEqual(template["source"]["inspiration"], "promptfoo/promptfoo")
        self.assertEqual(template["source"]["runtime_dependency"], "none")
        self.assertEqual(template["source"]["license"], "MIT")
        self.assertEqual(
            template["assertion_policy"]["artifact_root"],
            ".hermes/task-artifacts/evals/",
        )
        self.assertGreaterEqual(len(template["cases"]), 6)

        combined = "\n".join((doc, template_body, absorption))
        for marker in (
            "不安装 runner",
            "不配置 provider",
            "不保存真实 trace",
            "不把任何外部评估运行时",
            "不默认发起模型请求",
            "不是完整测试套件 green",
            "Gateway process running",
            "interrupted delegation",
            "PowerShell 7",
            "display.busy_input_mode: queue",
        ):
            self.assertIn(marker, combined)

        forbidden = (
            "OPENAI_API_KEY",
            "ANTHROPIC_API_KEY",
            "LANGFUSE_PUBLIC_KEY",
            "LANGFUSE_SECRET_KEY",
            "provider: openai",
            "provider: anthropic",
            "npm install promptfoo",
            "npx promptfoo",
        )
        for marker in forbidden:
            self.assertNotIn(marker, combined)

    def test_ui_skin_absorption_pack_is_lightweight_and_runtime_neutral(self) -> None:
        readme = (ROOT / "docs/current/workflow-assistance-README.md").read_text(encoding="utf-8")
        doc_path = ROOT / "docs/current/workflow-assistance/workflow/ui-skin-system.md"
        presets_path = ROOT / "packages" / "client-neutral-core" / "templates/ui/skin-presets.yaml"
        patterns_path = ROOT / "packages" / "client-neutral-core" / "templates/ui/agent-chat-ui-patterns.md"
        checklist_path = ROOT / "packages" / "client-neutral-core" / "templates/ui/terminal-theme-checklist.md"
        terminal_path = ROOT / "packages" / "client-neutral-core" / "templates/windows-terminal/catppuccin-mocha.json"
        absorption = (ROOT / "docs/current/workflow-assistance/absorption/open-source-workflow-absorption.md").read_text(
            encoding="utf-8"
        )
        skill = (
            ROOT / "packages/client-neutral-core/skills/software-development/agent-workflow-fortress/SKILL.md"
        ).read_text(encoding="utf-8")
        reference = (
            ROOT
            / "packages/client-neutral-core/skills/software-development/agent-workflow-fortress/references/ui-skin-absorption.md"
        ).read_text(encoding="utf-8")

        for path in (doc_path, presets_path, patterns_path, checklist_path, terminal_path):
            self.assertTrue(path.exists(), path.relative_to(ROOT).as_posix())
            self.assertIn(path.relative_to(ROOT).as_posix(), readme)

        presets = yaml.safe_load(presets_path.read_text(encoding="utf-8"))
        terminal = json.loads(terminal_path.read_text(encoding="utf-8"))

        self.assertEqual(presets["schema_version"], 1)
        self.assertEqual(presets["runtime_dependency"], "none")
        self.assertFalse(presets["default_applied"])
        self.assertEqual(
            presets["presets"]["catppuccin-mocha"]["colors"]["base"],
            "#1e1e2e",
        )
        self.assertEqual(
            presets["presets"]["catppuccin-mocha"]["colors"]["mauve"],
            "#cba6f7",
        )
        self.assertEqual(
            terminal["name"],
            "Catppuccin Mocha - Workflow Assistance",
        )
        self.assertEqual(terminal["background"], "#1e1e2e")
        self.assertEqual(terminal["foreground"], "#cdd6f4")

        sources = {item["repository"] for item in presets["sources"]}
        self.assertTrue(
            {
                "catppuccin/catppuccin",
                "catppuccin/windows-terminal",
                "shadcn-ui/ui",
                "assistant-ui/assistant-ui",
            }.issubset(sources)
        )
        self.assertTrue(presets["boundaries"]["no_default_install"])
        self.assertTrue(presets["boundaries"]["no_runtime_assets"])
        self.assertTrue(presets["boundaries"]["no_terminal_settings_write"])
        self.assertTrue(presets["boundaries"]["no_hermes_live_config_write"])

        combined = "\n".join(
            (
                doc_path.read_text(encoding="utf-8"),
                presets_path.read_text(encoding="utf-8"),
                patterns_path.read_text(encoding="utf-8"),
                checklist_path.read_text(encoding="utf-8"),
                absorption,
                skill,
                reference,
            )
        )
        for marker in (
            "Catppuccin",
            "shadcn-ui",
            "assistant-ui",
            "template available, not applied",
            "不默认安装 UI runtime",
            "不自动修改 Hermes live config",
            "不自动改用户 settings",
            "repo/live/session",
            "tool call timeline",
            "verification evidence",
            "Open WebUI / NextChat / Vercel AI Chatbot",
        ):
            self.assertIn(marker, combined)

        forbidden = (
            "npm install shadcn",
            "npx shadcn",
            "npm install assistant-ui",
            "npm install open-webui",
            "git clone https://github.com/open-webui/open-webui",
            "Copy-Item",
            "Set-Content $env:LOCALAPPDATA",
            "hermes config set model.provider",
            "hermes mcp add",
            "plugins enable",
        )
        for marker in forbidden:
            self.assertNotIn(marker, combined)


if __name__ == "__main__":
    unittest.main()
