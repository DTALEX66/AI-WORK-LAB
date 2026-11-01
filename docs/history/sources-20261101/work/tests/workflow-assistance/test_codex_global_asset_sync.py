from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import tomllib
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "integrations/executors/codex/sync_codex_global_assets.py"
spec = importlib.util.spec_from_file_location("sync_codex_global_assets", SCRIPT)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)
RAW_APPLY_OVERLAY = module.apply_overlay


def _runtime_tmp() -> Path:
    """WL-010: project-local runtime tmp dir (git-ignored), auto-created."""
    p = ROOT / ".project-local" / "runs" / "tmp"
    p.mkdir(parents=True, exist_ok=True)
    return p


def approved_apply_overlay(codex_home: Path, agent_home: Path, source_root: Path) -> dict[str, object]:
    """Test-only helper that models explicit review of an isolated dry-run."""

    plan = module.build_plan(codex_home, agent_home, source_root)
    return RAW_APPLY_OVERLAY(
        codex_home,
        agent_home,
        source_root,
        approved_plan_digest=plan["plan_digest"],
    )

class CodexGlobalAssetSyncTests(unittest.TestCase):
    def make_homes(self, base: Path) -> tuple[Path, Path]:
        codex_home = base / ".codex"
        agent_home = base / ".agents"
        codex_home.mkdir(parents=True)
        (codex_home / "config.toml").write_text(
            'model_provider = "user-provider"\n'
            'model = "user-model"\n'
            'base_url = "https://user-owned.invalid/v1"\n'
            '\n[mcp_servers.user-owned]\n'
            'command = "safe-placeholder"\n'
            '\n[plugins.user-owned]\n'
            'enabled = true\n'
            '\n[future_settings]\n'
            'opaque = "keep-me"\n',
            encoding="utf-8",
        )
        (codex_home / "AGENTS.md").write_text(
            "# User guidance\n\nKeep my existing preference.\n", encoding="utf-8"
        )
        return codex_home, agent_home

    def test_block_hash_normalizes_crlf_line_endings(self) -> None:
        # Codex Desktop 重写 config.toml 会写 CRLF 行尾；_block_hash 必须归一化行尾，
        # 否则 CRLF 块 hash 与 LF state hash 不匹配 → fail-closed BLOCK
        # （2026-08-14 DESIGN-LAB 交接复核：CRLF 50d589cb vs LF c2e56fdf）。
        lf_block = (
            "# BEGIN WORKFLOW-ASSISTANCE MANAGED CODEX OVERLAY\n"
            'model_provider = "cc-switch-official"\n'
            'sandbox_mode = "workspace-write"\n'
            "# END WORKFLOW-ASSISTANCE MANAGED CODEX OVERLAY\n"
        )
        crlf_block = lf_block.replace("\n", "\r\n")
        self.assertEqual(module._block_hash(lf_block), module._block_hash(crlf_block))

    def test_apply_preserves_user_config_and_installs_owned_assets(self) -> None:
        with tempfile.TemporaryDirectory(dir=_runtime_tmp()) as td:
            codex_home, agent_home = self.make_homes(Path(td))

            result = approved_apply_overlay(codex_home, agent_home, ROOT / "integrations" / "executors" / "codex")

            self.assertEqual(result["status"], "APPLIED")
            parsed = tomllib.loads((codex_home / "config.toml").read_text("utf-8"))
            self.assertEqual(parsed["model_provider"], "user-provider")
            self.assertEqual(parsed["model"], "user-model")
            self.assertEqual(parsed["base_url"], "https://user-owned.invalid/v1")
            self.assertIn("user-owned", parsed["mcp_servers"])
            self.assertTrue(parsed["plugins"]["user-owned"]["enabled"])
            self.assertEqual(parsed["future_settings"]["opaque"], "keep-me")
            self.assertEqual(parsed["approval_policy"], "on-request")
            self.assertEqual(parsed["sandbox_mode"], "workspace-write")
            self.assertEqual(parsed["project_doc_max_bytes"], 65536)
            guidance = (codex_home / "AGENTS.md").read_text("utf-8")
            self.assertIn("Keep my existing preference.", guidance)
            self.assertEqual(guidance.count(module.GUIDANCE_BEGIN), 1)
            self.assertTrue((codex_home / "rules/workflow-assistance.rules").is_file())
            installed = sorted((agent_home / "skills").glob("workflow-assistance-*/SKILL.md"))
            self.assertEqual(len(installed), len(module._skill_sources(ROOT / "integrations/executors/codex")))
            self.assertEqual(module.verify_overlay(codex_home, agent_home, ROOT / "integrations" / "executors" / "codex")["status"], "PASS")

    def test_writer_rejects_direct_apply_without_reviewed_plan_digest(self) -> None:
        with tempfile.TemporaryDirectory(dir=_runtime_tmp()) as td:
            codex_home, agent_home = self.make_homes(Path(td))
            with self.assertRaisesRegex(module.ManagedConflict, "ACTION_PLAN_DIGEST_REQUIRED"):
                RAW_APPLY_OVERLAY(
                    codex_home,
                    agent_home,
                    ROOT / "integrations" / "executors" / "codex",
                    approved_plan_digest=None,
                )
            with self.assertRaisesRegex(module.ManagedConflict, "ACTION_PLAN_DIGEST_MISMATCH"):
                RAW_APPLY_OVERLAY(
                    codex_home,
                    agent_home,
                    ROOT / "integrations" / "executors" / "codex",
                    approved_plan_digest="0" * 64,
                )
            self.assertFalse((codex_home / module.STATE_FILE).exists())

    def test_apply_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory(dir=_runtime_tmp()) as td:
            codex_home, agent_home = self.make_homes(Path(td))
            approved_apply_overlay(codex_home, agent_home, ROOT / "integrations" / "executors" / "codex")
            first = {
                "config": (codex_home / "config.toml").read_bytes(),
                "guidance": (codex_home / "AGENTS.md").read_bytes(),
            }

            result = approved_apply_overlay(codex_home, agent_home, ROOT / "integrations" / "executors" / "codex")

            self.assertEqual(result["status"], "NO_CHANGE")
            self.assertEqual((codex_home / "config.toml").read_bytes(), first["config"])
            self.assertEqual((codex_home / "AGENTS.md").read_bytes(), first["guidance"])

    def test_cli_apply_requires_explicit_reviewed_approval_before_any_write(self) -> None:
        with tempfile.TemporaryDirectory(dir=_runtime_tmp()) as td:
            codex_home, agent_home = self.make_homes(Path(td))
            config_before = (codex_home / "config.toml").read_bytes()

            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "apply",
                    "--codex-home",
                    str(codex_home),
                    "--agent-home",
                    str(agent_home),
                    "--source-root",
                    str(ROOT / "integrations" / "executors" / "codex"),
                ],
                cwd=ROOT,
                text=True, encoding="utf-8", errors="replace",
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
            self.assertIn("ACTION_PLAN_BLOCKED", result.stdout)
            self.assertEqual((codex_home / "config.toml").read_bytes(), config_before)
            self.assertFalse((codex_home / module.STATE_FILE).exists())
            self.assertFalse(agent_home.exists())

    def test_cli_apply_requires_current_plan_digest_and_accepts_matching_review(self) -> None:
        with tempfile.TemporaryDirectory(dir=_runtime_tmp()) as td:
            codex_home, agent_home = self.make_homes(Path(td))
            plan = module.build_plan(codex_home, agent_home, ROOT / "integrations" / "executors" / "codex")
            digest = plan["plan_digest"]

            blocked = subprocess.run(
                [
                    sys.executable, str(SCRIPT), "apply", "--approved",
                    "--codex-home", str(codex_home), "--agent-home", str(agent_home),
                    "--source-root", str(ROOT / "integrations" / "executors" / "codex"),
                ],
                cwd=ROOT, text=True, encoding="utf-8", errors="replace", capture_output=True, check=False,
            )
            self.assertEqual(blocked.returncode, 2, blocked.stdout + blocked.stderr)
            self.assertIn("ACTION_PLAN_DIGEST_REQUIRED", blocked.stdout)
            self.assertFalse((codex_home / module.STATE_FILE).exists())

            applied = subprocess.run(
                [
                    sys.executable, str(SCRIPT), "apply", "--approved",
                    "--approved-plan-digest", digest,
                    "--codex-home", str(codex_home), "--agent-home", str(agent_home),
                    "--source-root", str(ROOT / "integrations" / "executors" / "codex"),
                ],
                cwd=ROOT, text=True, encoding="utf-8", errors="replace", capture_output=True, check=False,
            )
            self.assertEqual(applied.returncode, 0, applied.stdout + applied.stderr)
            self.assertIn('"status": "APPLIED"', applied.stdout)

    def test_cli_apply_rejects_stale_or_other_machine_plan_digest_before_any_write(self) -> None:
        with tempfile.TemporaryDirectory(dir=_runtime_tmp()) as td:
            root = Path(td)
            codex_home, agent_home = self.make_homes(root / "first")
            _, other_agent_home = self.make_homes(root / "second")
            plan = module.build_plan(codex_home, agent_home, ROOT / "integrations" / "executors" / "codex")
            config_before = (codex_home / "config.toml").read_bytes()

            stale = subprocess.run(
                [
                    sys.executable, str(SCRIPT), "apply", "--approved",
                    "--approved-plan-digest", "0" * 64,
                    "--codex-home", str(codex_home), "--agent-home", str(agent_home),
                    "--source-root", str(ROOT / "integrations" / "executors" / "codex"),
                ],
                cwd=ROOT, text=True, encoding="utf-8", errors="replace", capture_output=True, check=False,
            )
            self.assertEqual(stale.returncode, 2, stale.stdout + stale.stderr)
            self.assertIn("ACTION_PLAN_DIGEST_MISMATCH", stale.stdout)

            other_scope = subprocess.run(
                [
                    sys.executable, str(SCRIPT), "apply", "--approved",
                    "--approved-plan-digest", plan["plan_digest"],
                    "--codex-home", str(codex_home), "--agent-home", str(other_agent_home),
                    "--source-root", str(ROOT / "integrations" / "executors" / "codex"),
                ],
                cwd=ROOT, text=True, encoding="utf-8", errors="replace", capture_output=True, check=False,
            )
            self.assertEqual(other_scope.returncode, 2, other_scope.stdout + other_scope.stderr)
            self.assertIn("ACTION_PLAN_DIGEST_MISMATCH", other_scope.stdout)
            self.assertEqual((codex_home / "config.toml").read_bytes(), config_before)
            self.assertFalse((codex_home / module.STATE_FILE).exists())

    def test_conflicting_skill_fails_before_writes(self) -> None:
        with tempfile.TemporaryDirectory(dir=_runtime_tmp()) as td:
            codex_home, agent_home = self.make_homes(Path(td))
            conflict = agent_home / "skills/workflow-assistance-safe-project-execution/SKILL.md"
            conflict.parent.mkdir(parents=True)
            conflict.write_text("user-owned conflict", encoding="utf-8")
            original_config = (codex_home / "config.toml").read_bytes()
            original_guidance = (codex_home / "AGENTS.md").read_bytes()

            with self.assertRaises(module.ManagedConflict):
                approved_apply_overlay(codex_home, agent_home, ROOT / "integrations" / "executors" / "codex")

            self.assertEqual((codex_home / "config.toml").read_bytes(), original_config)
            self.assertEqual((codex_home / "AGENTS.md").read_bytes(), original_guidance)
            self.assertEqual(conflict.read_text("utf-8"), "user-owned conflict")

    def test_rollback_removes_only_managed_overlay(self) -> None:
        with tempfile.TemporaryDirectory(dir=_runtime_tmp()) as td:
            codex_home, agent_home = self.make_homes(Path(td))
            approved_apply_overlay(codex_home, agent_home, ROOT / "integrations" / "executors" / "codex")

            result = module.rollback_overlay(codex_home, agent_home, ROOT / "integrations" / "executors" / "codex")

            self.assertEqual(result["status"], "ROLLED_BACK")
            parsed = tomllib.loads((codex_home / "config.toml").read_text("utf-8"))
            self.assertEqual(parsed["model_provider"], "user-provider")
            self.assertEqual(parsed["model"], "user-model")
            self.assertEqual(parsed["base_url"], "https://user-owned.invalid/v1")
            self.assertTrue(parsed["plugins"]["user-owned"]["enabled"])
            self.assertEqual(parsed["future_settings"]["opaque"], "keep-me")
            self.assertNotIn("approval_policy", parsed)
            self.assertNotIn("sandbox_mode", parsed)
            self.assertNotIn("project_doc_max_bytes", parsed)
            guidance = (codex_home / "AGENTS.md").read_text("utf-8")
            self.assertIn("Keep my existing preference.", guidance)
            self.assertNotIn(module.GUIDANCE_BEGIN, guidance)
            self.assertFalse((codex_home / "rules/workflow-assistance.rules").exists())
            self.assertFalse(list((agent_home / "skills").glob("workflow-assistance-*")))

    def test_plan_never_manages_user_routing_or_mcp(self) -> None:
        with tempfile.TemporaryDirectory(dir=_runtime_tmp()) as td:
            codex_home, agent_home = self.make_homes(Path(td))

            plan = module.build_plan(codex_home, agent_home, ROOT / "integrations" / "executors" / "codex")

            managed_fields = set(plan["managed_config_fields"])
            self.assertEqual(
                managed_fields,
                {"approval_policy", "sandbox_mode", "project_doc_max_bytes"},
            )
            rendered = str(plan).lower()
            self.assertNotIn("model_provider", managed_fields)
            self.assertNotIn("mcp_servers", managed_fields)
            self.assertNotIn("safe-placeholder", rendered)

    def test_legacy_state_is_migrated_without_replacing_owned_assets(self) -> None:
        with tempfile.TemporaryDirectory(dir=_runtime_tmp()) as td:
            codex_home, agent_home = self.make_homes(Path(td))
            approved_apply_overlay(codex_home, agent_home, ROOT / "integrations" / "executors" / "codex")
            state_path = codex_home / module.STATE_FILE
            legacy = json.loads(state_path.read_text("utf-8"))
            legacy["version"] = 1
            legacy.pop("managed_skill_names", None)
            state_path.write_text(json.dumps(legacy), encoding="utf-8")

            plan = module.build_plan(codex_home, agent_home, ROOT / "integrations" / "executors" / "codex")
            result = approved_apply_overlay(codex_home, agent_home, ROOT / "integrations" / "executors" / "codex")

            self.assertIn("MIGRATE_OWNERSHIP_STATE", [action["action"] for action in plan["actions"]])
            self.assertEqual(result["status"], "APPLIED")
            migrated = json.loads(state_path.read_text("utf-8"))
            self.assertEqual(migrated["version"], module.VERSION)
            self.assertEqual(migrated["phase"], "applied")
            self.assertEqual(len(migrated["managed_skill_names"]), len(module._skill_sources(ROOT / "integrations" / "executors" / "codex")))
            self.assertEqual(module.verify_overlay(codex_home, agent_home, ROOT / "integrations" / "executors" / "codex")["status"], "PASS")
            self.assertEqual(
                module.rollback_overlay(codex_home, agent_home, ROOT / "integrations" / "executors" / "codex")["status"],
                "ROLLED_BACK",
            )
            self.assertEqual(
                approved_apply_overlay(codex_home, agent_home, ROOT / "integrations" / "executors" / "codex")["status"],
                "APPLIED",
            )
            self.assertEqual(module.verify_overlay(codex_home, agent_home, ROOT / "integrations" / "executors" / "codex")["status"], "PASS")

    def test_legacy_migration_survives_advanced_source_and_dissolved_config_block(self) -> None:
        with tempfile.TemporaryDirectory(dir=_runtime_tmp()) as td:
            codex_home, agent_home = self.make_homes(Path(td))
            approved_apply_overlay(codex_home, agent_home, ROOT / "integrations" / "executors" / "codex")

            # Simulate the source advancing after the legacy apply.
            tmp_src = Path(td) / "codex-assets-advanced"
            shutil.copytree(ROOT / "integrations" / "executors" / "codex", tmp_src)
            marker = "\n- advanced source marker for migration regression\n"
            with tmp_src.joinpath("global-guidance.md").open("a", encoding="utf-8") as handle:
                handle.write(marker)

            # Simulate a Codex Desktop rewrite dissolving the managed config block.
            (codex_home / "config.toml").write_text(
                'model_provider = "user-provider"\n'
                'model = "user-model"\n'
                'base_url = "https://user-owned.invalid/v1"\n',
                encoding="utf-8",
            )

            state_path = codex_home / module.STATE_FILE
            legacy = json.loads(state_path.read_text("utf-8"))
            legacy["version"] = 2
            for key in ("phase", "managed_block_hashes", "previous_block_hashes", "previous_target_hashes"):
                legacy.pop(key, None)
            state_path.write_text(json.dumps(legacy), encoding="utf-8")

            plan = module.build_plan(codex_home, agent_home, tmp_src)
            result = approved_apply_overlay(codex_home, agent_home, tmp_src)

            self.assertIn("MIGRATE_OWNERSHIP_STATE", [action["action"] for action in plan["actions"]])
            self.assertEqual(result["status"], "APPLIED")
            parsed = tomllib.loads((codex_home / "config.toml").read_text("utf-8"))
            self.assertEqual(parsed["approval_policy"], "on-request")
            self.assertEqual(parsed["sandbox_mode"], "workspace-write")
            self.assertEqual(parsed["project_doc_max_bytes"], 65536)
            guidance = (codex_home / "AGENTS.md").read_text("utf-8")
            self.assertIn("advanced source marker", guidance)
            migrated = json.loads(state_path.read_text("utf-8"))
            self.assertEqual(migrated["version"], module.VERSION)
            self.assertEqual(sorted(migrated["managed_config_fields"]), sorted(module.MANAGED_CONFIG))
            self.assertEqual(module.verify_overlay(codex_home, agent_home, tmp_src)["status"], "PASS")

    def test_legacy_migration_still_blocks_on_edited_managed_block(self) -> None:
        with tempfile.TemporaryDirectory(dir=_runtime_tmp()) as td:
            codex_home, agent_home = self.make_homes(Path(td))
            approved_apply_overlay(codex_home, agent_home, ROOT / "integrations" / "executors" / "codex")

            # Keep the managed config block but edit a value inside it.
            config_text = (codex_home / "config.toml").read_text("utf-8")
            config_text = config_text.replace('approval_policy = "on-request"', 'approval_policy = "never"')
            (codex_home / "config.toml").write_text(config_text, encoding="utf-8")

            state_path = codex_home / module.STATE_FILE
            legacy = json.loads(state_path.read_text("utf-8"))
            legacy["version"] = 2
            for key in ("phase", "managed_block_hashes", "previous_block_hashes", "previous_target_hashes"):
                legacy.pop(key, None)
            state_path.write_text(json.dumps(legacy), encoding="utf-8")

            with self.assertRaisesRegex(module.ManagedConflict, "managed config block changed after apply"):
                module.build_plan(codex_home, agent_home, ROOT / "integrations" / "executors" / "codex")

    def test_legacy_migration_blocks_on_unmarked_guidance_block(self) -> None:
        with tempfile.TemporaryDirectory(dir=_runtime_tmp()) as td:
            codex_home, agent_home = self.make_homes(Path(td))
            approved_apply_overlay(codex_home, agent_home, ROOT / "integrations" / "executors" / "codex")

            # Replace the marked guidance block with unmarked user content.
            (codex_home / "AGENTS.md").write_text(
                "# User guidance\n\nUser-owned paragraph without managed markers.\n",
                encoding="utf-8",
            )

            state_path = codex_home / module.STATE_FILE
            legacy = json.loads(state_path.read_text("utf-8"))
            legacy["version"] = 2
            for key in ("phase", "managed_block_hashes", "previous_block_hashes", "previous_target_hashes"):
                legacy.pop(key, None)
            state_path.write_text(json.dumps(legacy), encoding="utf-8")

            with self.assertRaisesRegex(module.ManagedConflict, "managed guidance block changed after apply"):
                module.build_plan(codex_home, agent_home, ROOT / "integrations" / "executors" / "codex")

    def test_verify_rejects_modified_guidance_block(self) -> None:
        with tempfile.TemporaryDirectory(dir=_runtime_tmp()) as td:
            codex_home, agent_home = self.make_homes(Path(td))
            approved_apply_overlay(codex_home, agent_home, ROOT / "integrations" / "executors" / "codex")
            guidance_path = codex_home / "AGENTS.md"
            guidance_path.write_text(
                guidance_path.read_text("utf-8").replace(
                    "默认用清楚易懂的中文",
                    "CHANGED_BY_USER_DIAGNOSTIC",
                ),
                encoding="utf-8",
            )

            result = module.verify_overlay(codex_home, agent_home, ROOT / "integrations" / "executors" / "codex")

            self.assertEqual(result["status"], "FAIL")
            self.assertIn("guidance_drift", result["issues"])

    def test_rollback_without_state_never_deletes_managed_looking_assets(self) -> None:
        with tempfile.TemporaryDirectory(dir=_runtime_tmp()) as td:
            codex_home, agent_home = self.make_homes(Path(td))
            approved_apply_overlay(codex_home, agent_home, ROOT / "integrations" / "executors" / "codex")
            state_path = codex_home / module.STATE_FILE
            state_path.unlink()
            rule_path = codex_home / module.RULE_RELATIVE
            skill_path = agent_home / "skills/workflow-assistance-safe-project-execution/SKILL.md"

            with self.assertRaises(module.ManagedConflict):
                module.rollback_overlay(codex_home, agent_home, ROOT / "integrations" / "executors" / "codex")

            self.assertTrue(rule_path.exists())
            self.assertTrue(skill_path.exists())
            self.assertIn(module.GUIDANCE_BEGIN, (codex_home / "AGENTS.md").read_text("utf-8"))

    def test_exact_preexisting_skill_is_not_silently_adopted(self) -> None:
        with tempfile.TemporaryDirectory(dir=_runtime_tmp()) as td:
            codex_home, agent_home = self.make_homes(Path(td))
            source = ROOT / "integrations/executors/codex/skills/workflow-assistance-safe-project-execution"
            target = agent_home / "skills/workflow-assistance-safe-project-execution"
            target.parent.mkdir(parents=True)
            shutil.copytree(source, target)

            with self.assertRaises(module.ManagedConflict):
                approved_apply_overlay(codex_home, agent_home, ROOT / "integrations" / "executors" / "codex")

            self.assertEqual((target / "SKILL.md").read_bytes(), (source / "SKILL.md").read_bytes())

    def test_apply_rejects_managed_config_drift_instead_of_repairing_it(self) -> None:
        with tempfile.TemporaryDirectory(dir=_runtime_tmp()) as td:
            codex_home, agent_home = self.make_homes(Path(td))
            approved_apply_overlay(codex_home, agent_home, ROOT / "integrations" / "executors" / "codex")
            config_path = codex_home / "config.toml"
            config_path.write_text(
                config_path.read_text("utf-8").replace(
                    'sandbox_mode = "workspace-write"',
                    'sandbox_mode = "read-only"',
                ),
                encoding="utf-8",
            )

            with self.assertRaises(module.ManagedConflict):
                approved_apply_overlay(codex_home, agent_home, ROOT / "integrations" / "executors" / "codex")

            self.assertEqual(tomllib.loads(config_path.read_text("utf-8"))["sandbox_mode"], "read-only")

    def test_apply_rejects_managed_guidance_drift_instead_of_repairing_it(self) -> None:
        with tempfile.TemporaryDirectory(dir=_runtime_tmp()) as td:
            codex_home, agent_home = self.make_homes(Path(td))
            approved_apply_overlay(codex_home, agent_home, ROOT / "integrations" / "executors" / "codex")
            guidance_path = codex_home / "AGENTS.md"
            guidance_path.write_text(
                guidance_path.read_text("utf-8").replace(
                    "默认用清楚易懂的中文",
                    "CHANGED_BY_USER_DIAGNOSTIC",
                ),
                encoding="utf-8",
            )

            with self.assertRaises(module.ManagedConflict):
                approved_apply_overlay(codex_home, agent_home, ROOT / "integrations" / "executors" / "codex")

            self.assertIn("CHANGED_BY_USER_DIAGNOSTIC", guidance_path.read_text("utf-8"))

    def test_rollback_rejects_extra_user_field_inside_managed_config_block(self) -> None:
        with tempfile.TemporaryDirectory(dir=_runtime_tmp()) as td:
            codex_home, agent_home = self.make_homes(Path(td))
            approved_apply_overlay(codex_home, agent_home, ROOT / "integrations" / "executors" / "codex")
            config_path = codex_home / "config.toml"
            config_path.write_text(
                config_path.read_text("utf-8").replace(
                    module.CONFIG_BEGIN,
                    module.CONFIG_BEGIN + '\npost_apply_user_field = "keep-me"',
                ),
                encoding="utf-8",
            )

            with self.assertRaises(module.ManagedConflict):
                module.rollback_overlay(codex_home, agent_home, ROOT / "integrations" / "executors" / "codex")

            self.assertEqual(
                tomllib.loads(config_path.read_text("utf-8"))["post_apply_user_field"],
                "keep-me",
            )

    def test_apply_detects_config_change_between_preflight_and_atomic_replace(self) -> None:
        with tempfile.TemporaryDirectory(dir=_runtime_tmp()) as td:
            codex_home, agent_home = self.make_homes(Path(td))
            config_path = codex_home / "config.toml"
            original_atomic_write = module._atomic_write
            injected = False

            def racing_atomic_write(path, data, *, expected_current=module.NO_EXPECTATION):
                nonlocal injected
                if path == config_path and not injected:
                    injected = True
                    path.write_text(
                        path.read_text("utf-8").replace("user-provider", "concurrent-provider"),
                        encoding="utf-8",
                    )
                return original_atomic_write(path, data, expected_current=expected_current)

            module._atomic_write = racing_atomic_write
            try:
                with self.assertRaises(module.ManagedConflict):
                    approved_apply_overlay(codex_home, agent_home, ROOT / "integrations" / "executors" / "codex")
            finally:
                module._atomic_write = original_atomic_write

            self.assertEqual(
                tomllib.loads(config_path.read_text("utf-8"))["model_provider"],
                "concurrent-provider",
            )

    def test_interrupted_apply_records_recoverable_pending_state(self) -> None:
        with tempfile.TemporaryDirectory(dir=_runtime_tmp()) as td:
            codex_home, agent_home = self.make_homes(Path(td))
            guidance_path = codex_home / "AGENTS.md"
            original_atomic_write = module._atomic_write

            def failing_atomic_write(path, data, *, expected_current=module.NO_EXPECTATION):
                if path == guidance_path:
                    raise OSError("simulated interrupted apply")
                return original_atomic_write(path, data, expected_current=expected_current)

            module._atomic_write = failing_atomic_write
            try:
                with self.assertRaises(OSError):
                    approved_apply_overlay(codex_home, agent_home, ROOT / "integrations" / "executors" / "codex")
            finally:
                module._atomic_write = original_atomic_write

            state_path = codex_home / module.STATE_FILE
            pending = json.loads(state_path.read_text("utf-8"))
            self.assertEqual(pending["phase"], "applying")

            result = module.rollback_overlay(codex_home, agent_home, ROOT / "integrations" / "executors" / "codex")

            self.assertEqual(result["status"], "ROLLED_BACK")
            self.assertFalse(state_path.exists())
            parsed = tomllib.loads((codex_home / "config.toml").read_text("utf-8"))
            self.assertEqual(parsed["model_provider"], "user-provider")
            self.assertNotIn("approval_policy", parsed)
            self.assertNotIn(module.GUIDANCE_BEGIN, guidance_path.read_text("utf-8"))

    def test_apply_removes_retired_owned_skill_before_dropping_ownership(self) -> None:
        with tempfile.TemporaryDirectory(dir=_runtime_tmp()) as td:
            base = Path(td)
            codex_home, agent_home = self.make_homes(base / "homes")
            source_root = base / "codex-assets"
            shutil.copytree(ROOT / "integrations" / "executors" / "codex", source_root)
            approved_apply_overlay(codex_home, agent_home, source_root)
            retired = "workflow-assistance-windows-development"
            shutil.rmtree(source_root / "skills" / retired)

            result = approved_apply_overlay(codex_home, agent_home, source_root)

            self.assertEqual(result["status"], "APPLIED")
            self.assertFalse((agent_home / "skills" / retired).exists())
            state = json.loads((codex_home / module.STATE_FILE).read_text("utf-8"))
            self.assertNotIn(retired, state["managed_skill_names"])

    def test_skills_only_migration_preserves_drifted_user_rules_and_config(self) -> None:
        with tempfile.TemporaryDirectory(dir=_runtime_tmp()) as td:
            base = Path(td)
            codex_home, agent_home = self.make_homes(base / "homes")
            source_root = base / "assets"
            shutil.copytree(ROOT / "integrations/executors/codex", source_root)
            approved_apply_overlay(codex_home, agent_home, source_root)
            (codex_home / "AGENTS.md").write_text("User replaced global guidance.\n", encoding="utf-8")
            config_before = (codex_home / "config.toml").read_bytes()
            guidance_before = (codex_home / "AGENTS.md").read_bytes()
            state_before = module._load_state(codex_home)
            retired = "workflow-assistance-windows-development"
            shutil.rmtree(source_root / "skills" / retired)
            plan = module.build_plan(codex_home, agent_home, source_root, skills_only=True)
            self.assertTrue(all(a["target"].startswith("skills/") for a in plan["actions"]))
            with self.assertRaisesRegex(module.ManagedConflict, "ACTION_PLAN_DIGEST_MISMATCH"):
                module.apply_overlay(codex_home, agent_home, source_root,
                    approved_plan_digest="0" * 64, skills_only=True)
            result = module.apply_overlay(codex_home, agent_home, source_root,
                approved_plan_digest=plan["plan_digest"], skills_only=True)
            self.assertEqual(result["status"], "APPLIED")
            self.assertEqual((codex_home / "config.toml").read_bytes(), config_before)
            self.assertEqual((codex_home / "AGENTS.md").read_bytes(), guidance_before)
            self.assertFalse((agent_home / "skills" / retired).exists())
            state_after = module._load_state(codex_home)
            self.assertEqual(state_after["managed_block_hashes"], state_before["managed_block_hashes"])
            self.assertEqual(state_after["managed_config_fields"], state_before["managed_config_fields"])
            self.assertEqual(module.verify_overlay(codex_home, agent_home, source_root, skills_only=True)["status"], "PASS")
            self.assertEqual(module.build_plan(codex_home, agent_home, source_root, skills_only=True)["write_set_count"], 0)
            self.assertEqual(module.verify_overlay(codex_home, agent_home, source_root)["status"], "FAIL")

    def test_personal_guidance_requires_current_digest_and_backs_up_exact_file(self) -> None:
        with tempfile.TemporaryDirectory(dir=_runtime_tmp()) as td:
            base = Path(td)
            codex_home, _ = self.make_homes(base)
            source = base / "personal.md"
            source.write_text("# User selected concise rules\n", encoding="utf-8")
            before = (codex_home / "AGENTS.md").read_bytes()
            backup = base / "backup.md"
            plan = module.build_personal_guidance_plan(codex_home, source, backup)
            (codex_home / "AGENTS.md").write_bytes(before + b"User edit\n")
            with self.assertRaisesRegex(module.ManagedConflict, "ACTION_PLAN_DIGEST_MISMATCH"):
                module.apply_personal_guidance(codex_home, source, backup, plan["plan_digest"])
            current = (codex_home / "AGENTS.md").read_bytes()
            plan = module.build_personal_guidance_plan(codex_home, source, backup)
            result = module.apply_personal_guidance(codex_home, source, backup, plan["plan_digest"])
            self.assertEqual(result["status"], "APPLIED")
            self.assertEqual(backup.read_bytes(), current)
            self.assertEqual((codex_home / "AGENTS.md").read_bytes(), source.read_bytes())
            self.assertEqual(module.build_personal_guidance_plan(codex_home, source, backup)["write_set_count"], 0)
            self.assertNotIn('model', (codex_home / 'AGENTS.md').read_text('utf-8'))

    def test_interrupted_rollback_is_retryable_from_rolling_back_state(self) -> None:
        with tempfile.TemporaryDirectory(dir=_runtime_tmp()) as td:
            codex_home, agent_home = self.make_homes(Path(td))
            approved_apply_overlay(codex_home, agent_home, ROOT / "integrations" / "executors" / "codex")
            original_rmtree = module.shutil.rmtree
            removed_skills = 0

            def failing_rmtree(path, *args, **kwargs):
                nonlocal removed_skills
                target = Path(path)
                if target.name.startswith("workflow-assistance-"):
                    removed_skills += 1
                    if removed_skills == 2:
                        raise OSError("simulated interrupted rollback")
                return original_rmtree(path, *args, **kwargs)

            module.shutil.rmtree = failing_rmtree
            try:
                with self.assertRaises(OSError):
                    module.rollback_overlay(codex_home, agent_home, ROOT / "integrations" / "executors" / "codex")
            finally:
                module.shutil.rmtree = original_rmtree

            state_path = codex_home / module.STATE_FILE
            interrupted = json.loads(state_path.read_text("utf-8"))
            self.assertEqual(interrupted["phase"], "rolling_back")

            result = module.rollback_overlay(codex_home, agent_home, ROOT / "integrations" / "executors" / "codex")

            self.assertEqual(result["status"], "ROLLED_BACK")
            self.assertFalse(state_path.exists())
            self.assertFalse((codex_home / module.RULE_RELATIVE).exists())
            self.assertFalse(list((agent_home / "skills").glob("workflow-assistance-*")))
            parsed = tomllib.loads((codex_home / "config.toml").read_text("utf-8"))
            self.assertEqual(parsed["model_provider"], "user-provider")
            self.assertNotIn("approval_policy", parsed)

    def test_apply_rejects_skill_root_symlink_or_windows_junction(self) -> None:
        with tempfile.TemporaryDirectory(dir=_runtime_tmp()) as td:
            base = Path(td)
            codex_home, agent_home = self.make_homes(base / "homes")
            agent_home.mkdir(parents=True)
            outside = base / "outside"
            outside.mkdir()
            skills_link = agent_home / "skills"
            try:
                if os.name == "nt":
                    result = subprocess.run(
                        ["cmd.exe", "/d", "/c", "mklink", "/J", str(skills_link), str(outside)],
                        text=True,
                        encoding="mbcs",
                        errors="replace",
                        capture_output=True,
                    )
                    if result.returncode != 0:
                        self.skipTest(f"junction creation unavailable: {result.stderr.strip()}")
                else:
                    os.symlink(outside, skills_link, target_is_directory=True)

                with self.assertRaises(module.ManagedConflict):
                    approved_apply_overlay(codex_home, agent_home, ROOT / "integrations" / "executors" / "codex")

                self.assertFalse(list(outside.iterdir()))
                self.assertFalse((codex_home / module.STATE_FILE).exists())
            finally:
                if skills_link.is_symlink():
                    skills_link.unlink()
                elif skills_link.exists():
                    os.rmdir(skills_link)


if __name__ == "__main__":
    unittest.main()
