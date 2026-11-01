from __future__ import annotations

import copy
import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/ci/verify_capability_conformance.py"
MANIFEST = ROOT / "config/capability-conformance.json"


def load_module():
    spec = importlib.util.spec_from_file_location("verify_capability_conformance", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class CapabilityConformanceTests(unittest.TestCase):
    def test_static_manifest_passes_without_live_probe(self) -> None:
        result = load_module().verify_document(json.loads(MANIFEST.read_text(encoding="utf-8")), ROOT)
        self.assertEqual(result, {"protocols": 3, "entries": 5, "mcp_unverified": 1})

    def test_malicious_write_execute_network_fixture_fails_closed(self) -> None:
        module = load_module()
        document = json.loads(MANIFEST.read_text(encoding="utf-8"))
        malicious = copy.deepcopy(document)
        malicious["mcp"]["entries"][0]["permissions"] = ["write", "execute", "network"]
        with self.assertRaisesRegex(ValueError, "permissions"):
            module.verify_document(malicious, ROOT)

    def test_retired_design_entry_fails_closed(self) -> None:
        module = load_module()
        document = json.loads(MANIFEST.read_text(encoding="utf-8"))
        retired = copy.deepcopy(document)
        retired["mcp"]["entries"].append(
            {"id": "opendesign-assistance", "capabilities": ["read"], "transport": "external", "permissions": ["read-only"], "source": "opendesign-assistance"}
        )
        with self.assertRaisesRegex(ValueError, "retired Open Design migration alias"):
            module.verify_document(retired, ROOT)

    def test_open_design_client_adapter_is_allowed_read_only(self) -> None:
        """The Open Design client adapter (experimental, read-only) is a current
        managed client, not a retired capability."""
        module = load_module()
        result = module.verify_document(json.loads(MANIFEST.read_text(encoding="utf-8")), ROOT)
        self.assertEqual(result["protocols"], 3)


if __name__ == "__main__":
    unittest.main()
