"""WLOSS-700 tests: changed-files gate selection."""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "services/orchestration" / "run_quality_gate.py"


def load_runner():
    spec = importlib.util.spec_from_file_location("quality_gate", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ChangedFilesSelectionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.m = load_runner()

    def test_snapshot_change_selects_snapshot_gate(self) -> None:
        selected = self.m.select_gates_for_changed(["packages/client-neutral-core/scripts/snapshot_api.py"])
        self.assertIn("snapshot-schema-v3", selected)
        self.assertIn("compile", selected)

    def test_workflow_change_selects_only_fast_gates(self) -> None:
        selected = self.m.select_gates_for_changed([".github/workflows/work-lab-gate.yml"])
        self.assertEqual(set(selected), {"compile"})

    def test_store_test_selects_writer_and_convergence(self) -> None:
        selected = self.m.select_gates_for_changed(["tests/workflow-assistance/test_canonical_store_v2.py"])
        for gate in ("canonical-single-writer", "runtime-convergence", "governance", "compile"):
            self.assertIn(gate, selected)

    def test_tauri_change_selects_tauri_gate(self) -> None:
        selected = self.m.select_gates_for_changed(["apps/observer/src-tauri/tauri.conf.json"])
        self.assertIn("tauri-readonly-shell", selected)

    def test_canary_change_selects_canary_gate(self) -> None:
        selected = self.m.select_gates_for_changed(["services/orchestration/canary_runner.py"])
        self.assertIn("work-lab-os-canary", selected)

    def test_module_relative_path_matches(self) -> None:
        selected = self.m.select_gates_for_changed(["services/receipts/evidence_aggregator.py"])
        self.assertIn("execution-state-machine", selected)

    def test_order_follows_verify_order(self) -> None:
        selected = self.m.select_gates_for_changed(["tests/workflow-assistance/test_snapshot_sse_live.py"])
        order = self.m.VERIFY_ORDER
        positions = [order.index(g) for g in selected]
        self.assertEqual(positions, sorted(positions))


class CanaryExitCodeContractTests(unittest.TestCase):
    """P0-7: canary FAIL must propagate to the exit code; exact-sha gate is
    PENDING by default and fails only when required."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.root = Path(__file__).resolve().parents[2]
        cls.canary = cls.root / "services/orchestration" / "canary_runner.py"
        cls.gate = cls.root / "services/orchestration" / "run_quality_gate.py"

    def _run(self, script: Path, args: list[str], env_extra: dict[str, str] | None = None) -> subprocess.CompletedProcess:
        pythonpath = str(self.root / "scripts" / "workflow")
        inherited_pythonpath = os.environ.get("PYTHONPATH")
        if inherited_pythonpath:
            pythonpath += os.pathsep + inherited_pythonpath
        env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1", "PYTHONPATH": pythonpath}
        if env_extra:
            env.update(env_extra)
        return subprocess.run(
            [sys.executable, str(script), *args], cwd=str(self.root), capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=180, env=env
        )

    def test_canary_exit_code_matches_all_pass(self) -> None:
        result = self._run(self.canary, [])
        blob = result.stdout + result.stderr
        start = blob.find("{")
        report = json.loads(blob[start : blob.rfind("}") + 1]) if start != -1 else {}
        expected = 0 if report.get("all_pass") else 1
        self.assertEqual(result.returncode, expected, f"all_pass={report.get('all_pass')} rc={result.returncode}")

    def test_exact_sha_gate_pending_by_default(self) -> None:
        result = self._run(self.gate, ["exact-sha-ci"])
        self.assertEqual(result.returncode, 0)
        self.assertIn("PENDING", result.stdout)

    def test_exact_sha_gate_fails_when_required_and_missing(self) -> None:
        result = self._run(self.gate, ["exact-sha-ci"], env_extra={"WLGM_EXACT_SHA_CI_REQUIRED": "1"})
        self.assertEqual(result.returncode, 1)
        self.assertIn("EXACT_SHA_CI_FAIL", result.stdout)


if __name__ == "__main__":
    unittest.main()
