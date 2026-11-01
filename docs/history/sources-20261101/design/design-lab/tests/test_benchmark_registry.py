# SPDX-License-Identifier: MIT
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "verify_benchmark_registry.py"
REGISTRY = ROOT / "evals" / "benchmarks" / "benchmark-registry.json"


def load_module():
    spec = importlib.util.spec_from_file_location("verify_benchmark_registry", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class BenchmarkRegistryTests(unittest.TestCase):
    def test_registry_has_twelve_repeatable_benchmarks(self):
        result = subprocess.run([sys.executable, str(SCRIPT)], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace", check=False)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("BENCHMARK_REGISTRY_PASS benchmarks=12", result.stdout)

    def test_registry_rejects_missing_brief(self):
        module = load_module()
        data = json.loads(REGISTRY.read_text(encoding="utf-8"))
        data["benchmarks"][0]["brief"] = "evals/benchmarks/briefs/missing.json"
        with tempfile.TemporaryDirectory() as raw:
            path = Path(raw) / "benchmark-registry.json"
            path.write_text(json.dumps(data), encoding="utf-8")
            errors = module.verify(path)
        self.assertTrue(any("missing brief" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
