from __future__ import annotations

"""U17 — Global Agent Policy projection tests (taskpack section 26/27).

Positive controls prove the real policy renders for Codex and Hermes and that
every loss report is schema-valid and non-deceptive. Negative controls prove
the projection is fail-closed:

- policy weakens the E:\\ guard           -> FAIL
- policy makes UNKNOWN a success           -> FAIL
- renderer tries to alter the user model  -> FAIL
- renderer writes a real credential        -> FAIL
- unowned managed block changed            -> APPLY REFUSED
- unsupported adapter claims VERIFIED      -> FAIL

These live in tests/workflow-assistance/ (the workflow capability domain) so the
standard CI test discovery picks them up.
"""
import copy
import importlib.util
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# --- load the projection contract + renderers by path (no install dependency) ---

def _load(name: str, rel: str):
    path = ROOT / rel
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


pp = _load("wa_policy_projection", "services/policy/policy_projection.py")
codex_renderer = _load("wa_codex_policy_renderer", "integrations/executors/codex/codex_policy_renderer.py")
hermes_renderer = _load("wa_hermes_policy_renderer", "integrations/executors/hermes/hermes_policy_renderer.py")

# The existing Codex syncer (the projection feeds it; drift is refused there).
codex_sync = _load("wa_sync_codex_global_assets", "integrations/executors/codex/sync_codex_global_assets.py")


def _real_policy() -> dict:
    return pp.load_policy(ROOT)


def _registry_entry(adapter: str) -> dict:
    registry = json.loads((ROOT / "config" / "adapter-registry.json").read_text(encoding="utf-8"))
    for entry in registry["entries"]:
        if entry.get("id") == adapter:
            return entry
    raise AssertionError(f"adapter {adapter} not in registry")


class GlobalAgentPolicySchemaTests(unittest.TestCase):
    def test_policy_schema_and_invariants_pass(self) -> None:
        # The real, landed policy must validate clean (schema + invariants).
        result = pp.validate_policy(ROOT)
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["policy_id"], "WORK-LAB-GLOBAL-AGENT-POLICY")
        self.assertGreaterEqual(result["invariants_checked"], 12)

    def test_policy_weakens_protected_drive_guard_fails(self) -> None:
        # Negative control: weakening the protected-storage boundary is rejected.
        policy = _real_policy()
        policy["protected_storage"]["drive_default"] = "allow"
        with self.assertRaises(pp.PolicyProjectionError) as ctx:
            pp.validate_policy(ROOT, policy)
        self.assertIn("drive_default", str(ctx.exception))

    def test_policy_drops_a_machine_baseline_protected_drive_fails(self) -> None:
        # Negative control: dropping the F: drive (user standing rule: E: and F:
        # are both protected) is a fail-closed rejection.
        policy = _real_policy()
        policy["protected_storage"]["protected_drives"] = ["E"]
        with self.assertRaises(pp.PolicyProjectionError) as ctx:
            pp.validate_policy(ROOT, policy)
        self.assertIn("F", str(ctx.exception))

    def test_policy_makes_unknown_a_success_fails(self) -> None:
        # Negative control: UNKNOWN==SUCCESS is an evidence-invariant violation.
        policy = _real_policy()
        policy["evidence_semantics"]["unknown_is_success"] = True
        with self.assertRaises(pp.PolicyProjectionError) as ctx:
            pp.validate_policy(ROOT, policy)
        self.assertIn("unknown_is_success", str(ctx.exception))

    def test_policy_unknown_is_zero_fails(self) -> None:
        policy = _real_policy()
        policy["evidence_semantics"]["unknown_is_zero"] = True
        with self.assertRaises(pp.PolicyProjectionError):
            pp.validate_policy(ROOT, policy)

    def test_policy_simulated_is_real_fails(self) -> None:
        policy = _real_policy()
        policy["evidence_semantics"]["simulated_is_real"] = True
        with self.assertRaises(pp.PolicyProjectionError):
            pp.validate_policy(ROOT, policy)

    def test_policy_plaintext_credentials_not_weakenable(self) -> None:
        policy = _real_policy()
        policy["credentials"]["plaintext_forbidden"] = False
        with self.assertRaises(pp.PolicyProjectionError):
            pp.validate_policy(ROOT, policy)

    def test_policy_credential_material_rejected(self) -> None:
        # Negative control: a real token in the document is fail-closed. The
        # secret is planted in a schema-legal free-text slot (supersedes) so the
        # check that fires is the credential scan, not the schema.
        policy = _real_policy()
        policy["supersedes"] = "api_key = sk-" + "a" * 32
        with self.assertRaises(pp.PolicyProjectionError) as ctx:
            pp.validate_policy(ROOT, policy)
        self.assertIn("credential", str(ctx.exception))


class ModelNeutralityNegativeTests(unittest.TestCase):
    def test_policy_hardcodes_model_id_fails(self) -> None:
        policy = _real_policy()
        policy["model_neutrality"]["no_hardcoded_model_id_default"] = False
        with self.assertRaises(pp.PolicyProjectionError) as ctx:
            pp.validate_policy(ROOT, policy)
        self.assertIn("no_hardcoded_model_id_default", str(ctx.exception))

    def test_policy_makes_user_model_worklab_managed_fails(self) -> None:
        policy = _real_policy()
        policy["model_neutrality"]["user_model_is_user_owned_not_worklab_managed"] = False
        with self.assertRaises(pp.PolicyProjectionError):
            pp.validate_policy(ROOT, policy)

    def test_renderer_cannot_alter_user_model(self) -> None:
        # The Codex extension must NOT name a model/provider/endpoint.
        ext = pp.load_extension(ROOT, "codex")
        self.assertNotIn("model", ext.get("managed_config_values", {}))
        self.assertNotIn("model_provider", ext.get("managed_config_values", {}))
        # The managed config fields are the guardrails only — never routing.
        self.assertEqual(
            set(ext.get("managed_config_values", {})),
            {"approval_policy", "sandbox_mode", "project_doc_max_bytes"},
        )


class CodexProjectionTests(unittest.TestCase):
    def test_codex_policy_projection(self) -> None:
        renderer = codex_renderer.build_renderer(ROOT)
        result = renderer.project()  # fail-closed: validates the policy first
        golden = result["assets"]["global-guidance.md"]
        core = (ROOT / "config/universal-agent/AGENT_CORE.md").read_text(encoding="utf-8-sig").strip()
        self.assertEqual(golden.count(core), 1)
        self.assertIn("E/F 盘须有精确路径与操作授权", golden)
        self.assertNotIn("Keep task runtime under .project-local/", golden)
        # The loss report must honestly carry the coverage-state buckets.
        report = result["loss_report"]
        for bucket in ("native_enforced", "native_guidance", "workflow_guard", "observe_only", "unsupported"):
            self.assertIn(bucket, report)
        self.assertEqual(report["adapter"], "codex")
        # model_neutrality is observe-only: the projection never names a model.
        self.assertIn("model_neutrality", report["observe_only"])

    def test_codex_stale_drift_removed_from_golden(self) -> None:
        golden = (ROOT / "integrations" / "executors" / "codex" / "global-guidance.md").read_text(encoding="utf-8")
        # Section 10: these stale R4/R5 semantics must be gone from the new golden.
        self.assertNotIn(".hermes/task-runtime", golden)
        self.assertNotIn("scripts/workflow/", golden)
        self.assertNotIn("only one item actively owned", golden)

    def test_codex_loss_report_schema_valid(self) -> None:
        renderer = codex_renderer.build_renderer(ROOT)
        report = renderer.loss_report(_real_policy(), pp.load_extension(ROOT, "codex"))
        pp.validate_loss_report(report, ROOT)
        # every capability appears in exactly one bucket
        self.assertEqual(
            sum(len(report[b]) for b in ("native_enforced", "native_guidance", "workflow_guard", "observe_only", "unsupported")),
            len(pp.POLICY_CAPABILITIES),
        )


class UniversalMotherConvergenceTests(unittest.TestCase):
    def test_snapshot_drift_is_refused(self):
        import tempfile
        import shutil
        from universal_agent_core import render_core_block
        with tempfile.TemporaryDirectory(dir=ROOT / ".project-local/runs") as name:
            root = Path(name)
            shutil.copytree(ROOT / "config/universal-agent", root / "config/universal-agent")
            (root / "config/universal-agent/AGENT_CORE.md").write_text("unreviewed", encoding="utf8")
            with self.assertRaisesRegex(ValueError, "checksum"):
                render_core_block(root)

    def test_existing_identical_core_is_moved_once_and_user_text_preserved(self):
        from universal_agent_core import render_core_block
        core = render_core_block(ROOT)
        overlay = codex_renderer.build_renderer(ROOT).golden_text(
            _real_policy(), pp.load_extension(ROOT, "codex"))
        existing = "user preface\n\n" + core + "\n\nuser suffix\n"
        after = codex_sync._render_guidance(existing, overlay)
        self.assertEqual(after.count(core), 1)
        self.assertIn("user preface", after)
        self.assertIn("user suffix", after)
        self.assertEqual(codex_sync._render_guidance(after, overlay), after)

    def test_divergent_universal_core_is_not_silently_replaced(self):
        from universal_agent_core import render_core_block
        core = render_core_block(ROOT)
        with self.assertRaises(codex_sync.ManagedConflict):
            codex_sync._render_guidance(core.replace("规则版本：1.0.0", "规则版本：unreviewed"), core)


class HermesProjectionTests(unittest.TestCase):
    def test_hermes_policy_projection(self) -> None:
        renderer = hermes_renderer.build_renderer(ROOT)
        result = renderer.project()
        soul = result["assets"]["config/SOUL.md"]
        core = (ROOT / "config/universal-agent/AGENT_CORE.md").read_text(encoding="utf-8-sig").strip()
        self.assertEqual(soul.count(core), 1)
        self.assertIn("凭据", soul)
        self.assertIn("项目数据目录约束只在对应项目范围内生效", soul)
        self.assertEqual(result["loss_report"]["adapter"], "hermes")
        # protected storage is machine-enforced on Hermes (terminal guard hook)
        self.assertIn("protected_storage", result["loss_report"]["native_enforced"])

    def test_hermes_loss_report_schema_valid(self) -> None:
        renderer = hermes_renderer.build_renderer(ROOT)
        report = renderer.loss_report(_real_policy(), pp.load_extension(ROOT, "hermes"))
        pp.validate_loss_report(report, ROOT)
        self.assertEqual(
            sum(len(report[b]) for b in ("native_enforced", "native_guidance", "workflow_guard", "observe_only", "unsupported")),
            len(pp.POLICY_CAPABILITIES),
        )


class AdapterMaturityNegativeTests(unittest.TestCase):
    def test_unsupported_adapter_cannot_claim_readback_verified(self) -> None:
        # cc-switch / cursor / openhuman / open-design are OBSERVE_ONLY: they must
        # NOT carry apply_supported=true / readback_supported=true.
        for adapter in ("cc-switch", "cursor", "openhuman", "open-design"):
            pp_block = _registry_entry(adapter).get("policy_projection", {})
            self.assertEqual(
                pp_block.get("apply_supported"), False,
                f"{adapter} must not claim apply_supported",
            )
            self.assertEqual(pp_block.get("readback_supported"), False)
            self.assertIn(pp_block.get("maturity"), ("OBSERVE_ONLY", "UNSUPPORTED"))

    def test_supported_adapters_do_claim_readback(self) -> None:
        for adapter in ("codex", "hermes"):
            pp_block = _registry_entry(adapter).get("policy_projection", {})
            self.assertTrue(pp_block.get("apply_supported"))
            self.assertTrue(pp_block.get("readback_supported"))
            self.assertTrue(pp_block.get("rollback_supported"))
            self.assertTrue(pp_block.get("drift_supported"))

    def test_dsh_is_plan_only_until_native_interface_proven(self) -> None:
        pp_block = _registry_entry("deepseek-harness").get("policy_projection", {})
        self.assertEqual(pp_block.get("apply_supported"), False)
        self.assertIn(pp_block.get("maturity"), ("PLAN_SUPPORTED", "DETECTED"))


class UnownedManagedBlockTests(unittest.TestCase):
    def test_unowned_managed_block_changed_refuses_apply(self) -> None:
        # A user who edits inside the managed guidance block cannot trigger an
        # overwrite; the existing syncer fails closed instead of repairing.
        import tempfile

        with tempfile.TemporaryDirectory(dir=ROOT / ".project-local" / "runs" / "tmp") as td:
            base = Path(td)
            codex_home, agent_home = self._make_homes(base)
            self._apply(codex_home, agent_home)
            guidance = codex_home / "AGENTS.md"
            guidance.write_text(
                guidance.read_text("utf-8").replace(
                    "默认用清楚易懂的中文",
                    "CHANGED_BY_USER_DIAGNOSTIC",
                ),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(codex_sync.ManagedConflict, "managed guidance block changed"):
                self._apply(codex_home, agent_home)

    @staticmethod
    def _make_homes(base: Path):
        import tomllib  # noqa: F401  (kept for parity with the syncer test)
        codex_home = base / ".codex"
        agent_home = base / ".agents"
        codex_home.mkdir(parents=True)
        (codex_home / "config.toml").write_text(
            'model_provider = "user-provider"\n'
            'model = "user-model"\n'
            'base_url = "https://user-owned.invalid/v1"\n',
            encoding="utf-8",
        )
        (codex_home / "AGENTS.md").write_text("# User guidance\n\nKeep my existing preference.\n", encoding="utf-8")
        return codex_home, agent_home

    @staticmethod
    def _apply(codex_home, agent_home):
        plan = codex_sync.build_plan(codex_home, agent_home, ROOT / "integrations" / "executors" / "codex")
        codex_sync.apply_overlay(
            codex_home, agent_home,
            ROOT / "integrations" / "executors" / "codex",
            approved_plan_digest=plan["plan_digest"],
        )


class RealEvidenceWithoutReadbackTests(unittest.TestCase):
    def test_real_evidence_requires_readback_is_locked(self) -> None:
        # The policy invariant is schema-locked: real evidence must carry readback.
        policy = _real_policy()
        self.assertIs(policy["evidence_semantics"]["real_evidence_requires_readback"], True)
        self.assertIs(policy["evidence_semantics"]["apply_equals_verified"], False)
        # A projection that would flip APPLIED->VERIFIED without readback is rejected.
        policy["evidence_semantics"]["apply_equals_verified"] = True
        with self.assertRaises(pp.PolicyProjectionError):
            pp.validate_policy(ROOT, policy)


if __name__ == "__main__":
    unittest.main()
