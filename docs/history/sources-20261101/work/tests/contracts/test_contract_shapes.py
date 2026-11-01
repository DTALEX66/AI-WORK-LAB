import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

class ContractShapeTests(unittest.TestCase):
    def test_root_contracts_have_schema_versions(self):
        files = [
            ROOT / ".project/governance/contracts/compatibility-manifest.json",
            ROOT / ".project/governance/contracts/contract-catalog.json",
            ROOT / ".project/governance/contracts/evidence-envelope.schema.json",
            ROOT / ".project/governance/contracts/runtime-lock.schema.json",
            ROOT / ".project/governance/migration-status.json",
            ROOT / ".project/governance/module-ownership.json",
            ROOT / ".project/governance/projects.json",
        ]
        for path in files:
            data = json.loads(path.read_text(encoding="utf-8"))
            self.assertTrue(data.get("schemaVersion") or data.get("$id"), path.as_posix())

    def test_projects_preserve_two_active_module_paths(self):
        data = json.loads((ROOT / ".project/governance/projects.json").read_text(encoding="utf-8"))
        self.assertEqual([m["path"] for m in data["modules"]], ["packages/client-neutral-core", "apps/observer"])
        self.assertTrue(data["singleWriter"])
        self.assertFalse(data["externalMutationDefault"])

if __name__ == "__main__":
    unittest.main()
