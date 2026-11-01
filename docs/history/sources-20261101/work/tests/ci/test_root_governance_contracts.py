import json
import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class RootGovernanceContractTests(unittest.TestCase):
    def load_verifier(self, relative_path: str, name: str):
        spec = importlib.util.spec_from_file_location(name, ROOT / relative_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def run_verifier(self, relative_path: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(ROOT / relative_path)],
            cwd=ROOT,
            text=True, encoding="utf-8", errors="replace",
            capture_output=True,
        )

    def test_module_dependencies_are_typed_and_runtime_neutral(self):
        result = self.run_verifier("scripts/ci/verify_module_dependencies.py")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("MODULE_DEPENDENCIES_PASS", result.stdout)

    def test_project_data_boundary_has_one_canonical_runtime_and_evidence_policy(self):
        result = self.run_verifier("scripts/ci/verify_project_data_boundary.py")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("PROJECT_DATA_BOUNDARY_PASS", result.stdout)

    def test_supply_chain_gate_requires_pinned_actions_and_source_metadata(self):
        result = self.run_verifier("scripts/ci/verify_supply_chain.py")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("SUPPLY_CHAIN_PASS", result.stdout)

    def test_error_ledger_is_fail_closed_and_replayable(self):
        result = self.run_verifier("scripts/ci/verify_error_ledger.py")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("ERROR_LEDGER_PASS", result.stdout)

    def test_boundary_contract_is_machine_readable(self):
        data = json.loads(
            (ROOT / ".project/governance/project-data-boundary.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(data["runtimeRoot"], ".project-local/runs")
        self.assertEqual(data["taskArtifactsRoot"], ".project-local/artifacts")
        self.assertEqual(data["canonicalEvidenceRoot"], ".project-local/artifacts")

    def test_dependency_verifier_rejects_runtime_edge(self):
        module = self.load_verifier(
            "scripts/ci/verify_module_dependencies.py", "module_dependencies"
        )
        data = json.loads(
            (ROOT / ".project/governance/module-dependencies.json").read_text(encoding="utf-8")
        )
        data["modules"]["work-lab-observer"]["dependencies"][0]["types"] = ["runtime"]
        with tempfile.TemporaryDirectory() as temp:
            temp_root = Path(temp) / "repo"
            (temp_root / ".project/governance").mkdir(parents=True)
            (temp_root / ".project/governance/module-dependencies.json").write_text(
                json.dumps(data), encoding="utf-8"
            )
            errors = module.verify(temp_root)
        self.assertTrue(any("runtime coupling" in error for error in errors))

    def test_supply_chain_verifier_rejects_floating_action(self):
        module = self.load_verifier(
            "scripts/ci/verify_supply_chain.py", "supply_chain"
        )
        with tempfile.TemporaryDirectory() as temp:
            temp_root = Path(temp) / "repo"
            workflow_dir = temp_root / ".github/workflows"
            workflow_dir.mkdir(parents=True)
            (workflow_dir / "bad.yml").write_text(
                "name: bad\njobs:\n  x:\n    steps:\n      - uses: actions/checkout@v4 # v4\n",
                encoding="utf-8",
            )
            errors = module.verify(temp_root)
        self.assertTrue(any("full commit SHA" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
