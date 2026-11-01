from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "packages/client-neutral-core/scripts/verify_client_neutral_manifest.py"


def load_module():
    spec = importlib.util.spec_from_file_location("verify_client_neutral_manifest", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ClientNeutralManifestTests(unittest.TestCase):
    def test_product_definition_documents_the_core_boundary(self) -> None:
        readme = (ROOT / "docs/current/workflow-assistance-README.md").read_text(encoding="utf-8")
        definition = (ROOT / "docs/current/workflow-assistance/workflow/project-definition.md").read_text(encoding="utf-8")
        for document in (readme, definition):
            self.assertIn("客户端中立", document)
            self.assertIn("Adapter", document)
            self.assertIn("Agent", document)
            self.assertIn("模型网关", document)

    def test_manifest_declares_client_neutral_product_and_first_class_adapters(self) -> None:
        manifest = yaml.safe_load((ROOT / "packages/client-neutral-core/workflow-manifest.yaml").read_text(encoding="utf-8"))
        self.assertEqual(manifest["product"]["architecture"], "client-neutral")
        self.assertIn("agent", manifest["product"]["non_goals"])
        self.assertIn("chat", manifest["product"]["non_goals"])
        self.assertIn("model_gateway", manifest["product"]["non_goals"])
        self.assertNotIn("hermes", manifest["requirements"])
        self.assertEqual(manifest["requirements"]["optional_adapters"]["hermes"], "capability-discovery")
        self.assertEqual(manifest["compatibility"]["official_schema"], "capability-discovery")
        self.assertEqual(manifest["compatibility"]["official_config_root"], "capability-discovery")
        self.assertNotIn("config_version_range", manifest["compatibility"])
        self.assertNotIn("config_version_snapshot", manifest["compatibility"])
        adapters = {item["id"]: item for item in manifest["adapters"]["entries"]}
        self.assertEqual(
            set(adapters),
            {"hermes", "codex", "cc-switch", "github", "openhuman", "open-design", "cursor", "claude-code", "workbuddy"},
        )
        self.assertEqual(adapters["hermes"]["support"], "deep")
        self.assertEqual(adapters["cursor"]["support"], "manifest-only")
        self.assertEqual(manifest["adapters"]["interface"], ["detect", "capabilities", "plan", "apply", "invoke", "observe", "rollback"])

    def test_manifest_registers_the_six_core_schemas_and_instance_controls(self) -> None:
        manifest = yaml.safe_load((ROOT / "packages/client-neutral-core/workflow-manifest.yaml").read_text(encoding="utf-8"))
        contracts = manifest["contracts"]
        self.assertEqual(contracts["schema_directory"], "packages/contracts/schemas/workflow")
        self.assertEqual(len(contracts["schemas"]), 19)
        self.assertTrue(contracts["instance_controls"]["positive"].endswith("valid-action-plan.json"))
        self.assertTrue(contracts["instance_controls"]["negative"].endswith("invalid-action-plan.json"))

    def test_verifier_runs_without_hermes_cli_or_import(self) -> None:
        env = os.environ.copy()
        env.pop("HERMES_HOME", None)
        env["PYTHONIOENCODING"] = "utf-8"
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--manifest", str(ROOT / "packages/client-neutral-core/workflow-manifest.yaml")],
            cwd=ROOT,
            env=env,
            text=True, encoding="utf-8", errors="replace",
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("CLIENT_NEUTRAL_MANIFEST_PASS", result.stdout)
        self.assertIn("adapters=9", result.stdout)
        self.assertNotIn("hermes-agent", result.stdout)

    def test_verifier_rejects_missing_adapter_interface(self) -> None:
        module = load_module()
        with tempfile.TemporaryDirectory() as raw:
            path = Path(raw) / "manifest.yaml"
            data = yaml.safe_load((ROOT / "packages/client-neutral-core/workflow-manifest.yaml").read_text(encoding="utf-8"))
            data["adapters"]["interface"] = ["detect"]
            path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "interface"):
                module.load_and_validate(path)


if __name__ == "__main__":
    unittest.main()
