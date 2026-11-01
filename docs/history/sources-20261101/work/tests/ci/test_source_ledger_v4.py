"""WLOSS-000 tests: OSS intake ledger contract."""
from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "ci" / "verify_source_ledger_v4.py"
sys.path.insert(0, str(ROOT / "packages" / "client-neutral-core" / "scripts"))

import project_temp  # noqa: E402


def load_verifier():
    spec = importlib.util.spec_from_file_location("verify_source_ledger_v4", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class SourceLedgerV4Tests(unittest.TestCase):
    def test_real_ledger_passes(self) -> None:
        module = load_verifier()
        report = module.verify()
        self.assertTrue(report["valid"], report["errors"])
        self.assertGreaterEqual(report["entries"], 17)

    def test_all_p0_items_recorded(self) -> None:
        ledger = json.loads((ROOT / ".project/governance" / "source-ledger.json").read_text(encoding="utf-8"))
        ids = {e["id"] for e in ledger["entries"]}
        expected = {"opa", "conftest", "trivy", "actionlint", "zizmor", "cosign", "in-toto",
                    "agent-skills", "mcp-inspector", "superpowers", "promptfoo", "otel-semconv"}
        self.assertTrue(expected <= ids, f"missing={sorted(expected - ids)}")

    def test_integration_mode_enum(self) -> None:
        ledger = json.loads((ROOT / ".project/governance" / "source-ledger.json").read_text(encoding="utf-8"))
        allowed = {"VENDOR", "DEPENDENCY", "EXTERNAL_TOOL", "ADAPTER", "DERIVE", "REFERENCE", "QUARANTINE", "REJECT"}
        for entry in ledger["entries"]:
            self.assertIn(entry["integrationMode"], allowed, entry["id"])

    def test_review_required_not_integrated(self) -> None:
        ledger = json.loads((ROOT / ".project/governance" / "source-ledger.json").read_text(encoding="utf-8"))
        for entry in ledger["entries"]:
            if entry.get("freshness") in ("review-required", "unknown"):
                self.assertEqual(entry["implementationStatus"], "not-implemented", entry["id"])

    def test_missing_field_fails(self) -> None:
        module = load_verifier()
        original = module.LEDGER_REL
        fake = project_temp.fixture_dir(prefix="source-ledger-") / "source-ledger.json"
        fake.write_text(json.dumps({"schemaVersion": "work-lab/source-ledger/v4", "entries": [{"id": "x"}]}), encoding="utf-8")
        module.LEDGER_REL = fake  # relative to cwd; absolute path works via find_root fallback
        try:
            report = module.verify()
        finally:
            module.LEDGER_REL = original
        self.assertFalse(report["valid"])
        self.assertTrue(any("missing" in e for e in report["errors"]))


if __name__ == "__main__":
    unittest.main()
