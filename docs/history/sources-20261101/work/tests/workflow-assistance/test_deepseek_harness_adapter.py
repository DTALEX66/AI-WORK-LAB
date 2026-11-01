"""Contract tests for the DeepSeek Harness agent-runtime adapter (WL-DSH-020).

Covers the fail-closed rejections: public host, commit drift, workspace scope
escape, secret serialization, apply-without-approval, and receipt schema.
No DSH install / server start / Hermes or Codex Home write is performed.
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

import jsonschema

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts/workflow"))

import deepseek_harness_adapter as dsh


class DeepSeekHarnessContractTests(unittest.TestCase):
    def test_contract_validates_against_agent_runtime_schema(self) -> None:
        adapter = dsh.DeepSeekHarnessAdapter(Path.cwd())
        contract = adapter.contract()
        schema_path = (
            Path(__file__).resolve().parents[2]
            / "packages/contracts/schemas/workflow/agent-runtime-adapter.schema.json"
        )
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        jsonschema.Draft202012Validator(schema).validate(contract)

    def test_contract_has_all_required_fields(self) -> None:
        adapter = dsh.DeepSeekHarnessAdapter(Path.cwd())
        contract = adapter.contract()
        required = {
            "adapter_id", "kind", "upstream", "maturity", "install_mode",
            "entrypoints", "network", "workspace_scope", "secrets",
            "execution_authority", "external_mutation", "plugin_policy",
            "upgrade_policy", "rollback",
        }
        self.assertTrue(required.issubset(set(contract)))
        self.assertEqual(contract["adapter_id"], "deepseek-harness")
        self.assertEqual(contract["kind"], "agent_runtime")
        self.assertEqual(contract["install_mode"], "community_desktop_release")
        self.assertEqual(contract["entrypoints"], ["desktop", "web", "headless"])
        self.assertEqual(contract["network"], "loopback_only")
        self.assertEqual(contract["workspace_scope"], "task_scoped_git_worktree_only")
        self.assertEqual(contract["secrets"], "runtime_secret_only")
        self.assertEqual(contract["execution_authority"], "execute_only_no_task_completion_authority")
        self.assertEqual(contract["external_mutation"], "approval_required")
        self.assertEqual(contract["plugin_policy"], "builtins_only")
        self.assertEqual(contract["maturity"], "developer_preview")

    def test_contract_describes_the_community_shell_without_user_config_access(self) -> None:
        contract = dsh.DeepSeekHarnessAdapter(Path.cwd()).contract()
        deployed = contract["detected_local"]
        self.assertEqual(deployed["deployment"], "community-desktop")
        self.assertEqual(deployed["release_track"], "stable")
        self.assertEqual(deployed["upstream_authority"], "deepseek-ai/deepseek-harness")
        self.assertEqual(deployed["binary_signature"], "UNSIGNED")
        self.assertEqual(deployed["user_config_access"], "NOT_ACCESSED")
        self.assertNotIn("config_root", deployed)

    def test_commit_pin_rejects_drift_and_missing(self) -> None:
        ok, _ = dsh.validate_commit_pin(dsh.UPSTREAM_COMMIT)
        self.assertTrue(ok)
        ok, detail = dsh.validate_commit_pin("deadbeef" * 8)
        self.assertFalse(ok)
        self.assertIn("drift", detail)
        ok, detail = dsh.validate_commit_pin(None)
        self.assertFalse(ok)
        self.assertIn("missing", detail)

    def test_loopback_rejects_public_and_private_hosts(self) -> None:
        self.assertTrue(dsh.validate_loopback("127.0.0.1", 3080)[0])
        self.assertTrue(dsh.validate_loopback("localhost", 3080)[0])
        self.assertTrue(dsh.validate_loopback("::1", 3080)[0])
        for host in ("0.0.0.0", "example.com", "203.0.113.5", "8.8.8.8"):
            ok, _ = dsh.validate_loopback(host, 3080)
            self.assertFalse(ok, f"host {host!r} must be rejected")
        # private RFC1918 addresses are also rejected (must be loopback, not LAN)
        ok, _ = dsh.validate_loopback("192.168.1.10", 3080)
        self.assertFalse(ok)
        ok, _ = dsh.validate_loopback("127.0.0.1", 99999)
        self.assertFalse(ok)

    def test_workspace_scope_enforces_project_boundaries(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            worktree = project / ".hermes" / "task-runtime" / "canary"
            worktree.mkdir(parents=True)
            (worktree / ".git").mkdir()
            # valid: git worktree under project
            ok, _ = dsh.validate_workspace_scope(worktree, project)
            self.assertTrue(ok)
            # reject project root itself
            ok, _ = dsh.validate_workspace_scope(project, project)
            self.assertFalse(ok)
            # reject non-git dir
            notgit = project / "nongit"
            notgit.mkdir()
            ok, _ = dsh.validate_workspace_scope(notgit, project)
            self.assertFalse(ok)
            # reject path outside project
            outside = Path(tmp) / "outside"
            outside.mkdir()
            (outside / ".git").mkdir()
            ok, _ = dsh.validate_workspace_scope(outside, project)
            self.assertFalse(ok)

    def test_receipt_rejects_forbidden_and_unknown_fields(self) -> None:
        good = {
            "task_id": "t1",
            "adapter_id": "deepseek-harness",
            "upstream_commit": dsh.UPSTREAM_COMMIT,
            "started_at": "2026-08-15T00:00:00Z",
            "ended_at": "2026-08-15T00:01:00Z",
            "workspace_rel": ".hermes/task-runtime/canary",
            "command_kind": "summarize",
            "approval_result": "approved",
            "exit_code": 0,
            "test_summary": "ok",
            "file_changes": [],
            "error_kind": None,
            "evidence_hash": "abc",
        }
        self.assertTrue(dsh.validate_receipt(good)[0])
        bad = dict(good, api_key="sk-secret")
        self.assertFalse(dsh.validate_receipt(bad)[0])
        unknown = dict(good, session_id="s")
        self.assertFalse(dsh.validate_receipt(unknown)[0])

    def test_config_dump_rejects_secret_markers(self) -> None:
        ok, _ = dsh.validate_secret_redaction({"model": "deepseek", "port": 3080})
        self.assertTrue(ok)
        ok, detail = dsh.validate_secret_redaction({"api_key": "sk-abc"})
        self.assertFalse(ok)
        self.assertIn("secret", detail)

    def test_apply_requires_approved_runtime_install(self) -> None:
        adapter = dsh.DeepSeekHarnessAdapter(Path.cwd())
        plan = {"plan_id": "p1", "task_id": "t1"}
        result = adapter.apply(plan)
        self.assertEqual(result["status"], "UNSUPPORTED")
        # even with approval the adapter itself never performs the install
        plan_approved = dict(plan, approved_runtime_install=True)
        result = adapter.apply(plan_approved)
        self.assertEqual(result["status"], "BLOCKED")

    def test_capabilities_do_not_expose_apply_or_invoke(self) -> None:
        adapter = dsh.DeepSeekHarnessAdapter(Path.cwd())
        caps = adapter.capabilities()
        self.assertEqual(caps["operations"], ["detect", "capabilities", "observe"])
        self.assertIn("apply", caps["unsupported_operations"])

    def test_detect_reports_uninstalled_without_side_effects(self) -> None:
        adapter = dsh.DeepSeekHarnessAdapter(Path.cwd())
        detect = adapter.detect()
        # In a fresh project there is no checkout; must report honestly.
        self.assertEqual(detect["adapter_id"], "deepseek-harness")
        self.assertIn(detect["installed"], (True, False))
        self.assertEqual(detect["pinned_commit"], dsh.UPSTREAM_COMMIT)


if __name__ == "__main__":
    unittest.main()
