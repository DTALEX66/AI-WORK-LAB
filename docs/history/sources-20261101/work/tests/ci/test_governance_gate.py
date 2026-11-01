import importlib.util
import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

class GovernanceGateTests(unittest.TestCase):
    def test_classifier_assigns_each_owner(self):
        spec = importlib.util.spec_from_file_location("classifier", ROOT / "scripts/ci/classify_paths.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        result = module.classify([
            "packages/client-neutral-core/x",
            "apps/observer/x",
            "README.md",
        ])
        self.assertEqual([len(result[k]) for k in ["workflow", "observer", "root"]], [1, 1, 1])

    def test_aggregate_rejects_cancelled_job(self):
        payload = json.dumps({"jobs": {"workflow": "success", "observer": "cancelled", "integration": "success"}})
        result = subprocess.run([sys.executable, str(ROOT / "scripts/ci/aggregate_gate.py")], input=payload, text=True, encoding="utf-8", errors="replace", capture_output=True)
        self.assertNotEqual(result.returncode, 0)

    def test_root_workflow_uses_real_needs_results(self):
        workflow = (ROOT / ".github/workflows/work-lab-gate.yml").read_text(encoding="utf-8")
        normalized = "".join(workflow.split())
        for job in ("workflow", "observer", "token-monitor", "supply-chain-security", "integration"):
            self.assertIn(f"needs.{job}.result", normalized)
        self.assertNotIn('"workflow":"success"', normalized)
        self.assertIn("needs:", workflow)

    def test_token_monitor_has_a_windows_locked_build_and_test_gate(self):
        workflow = (ROOT / ".github/workflows/work-lab-gate.yml").read_text(encoding="utf-8")
        self.assertIn("token-monitor:", workflow)
        self.assertIn("runs-on: windows-latest", workflow)
        self.assertIn("npm ci", workflow)
        self.assertIn("npm run build", workflow)
        self.assertIn("cargo test --locked", workflow)
        self.assertIn("cargo check --locked", workflow)
        self.assertIn("needs.plan.outputs.run_token_monitor == 'true'", workflow)

    def test_supply_chain_security_is_selected_and_aggregated_by_gate_plan(self):
        workflow = (ROOT / ".github/workflows/work-lab-gate.yml").read_text(encoding="utf-8")
        self.assertIn("run_supply_chain_security:", workflow)
        self.assertIn("needs.plan.outputs.run_supply_chain_security == 'true'", workflow)
        self.assertIn("SUPPLY_CHAIN_SECURITY_RESULT: ${{ needs.supply-chain-security.result }}", workflow)

    def test_required_workflow_checks_current_state_freshness_and_stage3_baseline(self):
        workflow = (ROOT / ".github/workflows/work-lab-gate.yml").read_text(encoding="utf-8")
        self.assertIn("python scripts/ci/generate_current_state.py --check-current", workflow)
        self.assertIn("python tests/ci/test_stage3_baseline.py", workflow)

    def test_required_integration_runs_aggregate_negative_controls(self):
        workflow = (ROOT / ".github/workflows/work-lab-gate.yml").read_text(encoding="utf-8")
        self.assertIn("python tests/ci/test_aggregate_gate.py", workflow)


    def test_contract_catalog_references_real_schemas(self):
        script = ROOT / "scripts/ci/verify_contract_catalog.py"
        result = subprocess.run(
            [sys.executable, str(script)],
            cwd=ROOT,
            text=True, encoding="utf-8", errors="replace",
            capture_output=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        # P0-07 / TaskPack §4.1: contract counts are a DYNAMIC inventory. Assert
        # the verifier reports the authoritative catalog count — never a
        # hard-coded number (a fixed "33" would silently go stale the next time
        # a contract is added).
        catalog = json.loads(
            (ROOT / ".project/governance/contracts/contract-catalog.json").read_text(encoding="utf-8"))
        expected = len(catalog["contracts"])
        self.assertGreater(expected, 0)
        self.assertIn(f"CONTRACT_CATALOG_PASS contracts={expected} schemas={expected}", result.stdout)

if __name__ == "__main__":
    unittest.main()
