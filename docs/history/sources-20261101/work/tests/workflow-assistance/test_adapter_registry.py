from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
VERIFY = ROOT / "packages/client-neutral-core/scripts" / "verify_adapter_registry.py"
REGISTRY = ROOT / "config" / "adapter-registry.json"
SCHEMA = ROOT / "packages" / "contracts" / "schemas" / "workflow" / "adapter-registry.schema.json"


class AdapterRegistryTests(unittest.TestCase):
    def run_verify(self, registry: Path = REGISTRY) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(VERIFY), "--registry", str(registry), "--schema", str(SCHEMA), "--root", str(ROOT)],
            cwd=ROOT,
            capture_output=True,
            text=True, encoding="utf-8", errors="replace",
            check=False,
        )

    def test_registry_is_fail_closed_and_traceable(self) -> None:
        result = self.run_verify()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("ADAPTER_REGISTRY_PASS", result.stdout)
        self.assertIn("hash_unavailable=", result.stdout)

    def test_missing_provenance_risk_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            path = Path(raw) / "registry.json"
            data = json.loads(REGISTRY.read_text(encoding="utf-8"))
            del data["entries"][0]["provenance"]["risk"]
            path.write_text(json.dumps(data), encoding="utf-8")
            result = self.run_verify(path)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("risk", result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
