# SPDX-License-Identifier: MIT
"""ODA4-0206 / V42-0107: adapter neutrality, evidence-gated status, fallback/unsupported tests."""
from __future__ import annotations

import json
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
REGISTRY = REPO / "integrations" / "adapter-registry.json"
SCHEMA = REPO / "design-lab" / "schemas" / "adapter-contract.schema.json"

VALID_STATUSES = {"declared", "structural", "runtime", "missing", "unsupported", "BLOCKED_BY_LICENSE"}


class AdapterRegistryTest(unittest.TestCase):
    def test_no_available_status_without_runtime_evidence(self):
        """V42-0107: no adapter may claim 'available'; runtime requires evidence."""
        data = json.loads(REGISTRY.read_text(encoding="utf-8"))
        for ad in data["adapters"]:
            self.assertNotEqual(ad["status"], "available", f"{ad['tool']} still says available")
            if ad["status"] in ("declared", "structural"):
                evidence = ad.get("evidence", {})
                self.assertLessEqual(
                    evidence.get("level", "E5"),
                    "E1",
                    f"{ad['tool']} declared/structural status must not claim above E1",
                )
                if evidence.get("level") == "E0":
                    self.assertEqual(evidence.get("task_ids"), [], f"{ad['tool']} E0 must not claim a task run")
                else:
                    self.assertEqual(evidence.get("level"), "E1", f"{ad['tool']} structural evidence must be E1")

    def test_missing_capabilities_not_presented_as_available(self):
        data = json.loads(REGISTRY.read_text(encoding="utf-8"))
        for ad in data["adapters"]:
            if ad["status"] == "missing":
                for cap in ad["capabilities"]:
                    self.assertFalse(cap["supported"], f"{ad['tool']} {cap['name']} supported but missing")
            else:
                for cap in ad["capabilities"]:
                    if cap["supported"]:
                        self.assertIn(ad["status"], ("declared", "structural", "runtime"),
                                      f"{ad['tool']} {cap['name']} supported but status {ad['status']}")

    def test_large_tools_process_isolated(self):
        data = json.loads(REGISTRY.read_text(encoding="utf-8"))
        for ad in data["adapters"]:
            if "Blender" in ad["tool"] or "FFmpeg" in ad["tool"]:
                self.assertEqual(ad["mode"], "process-isolated")
                self.assertEqual(ad["status"], "missing")  # honest: not proven

    def test_fallback_defined_for_missing(self):
        data = json.loads(REGISTRY.read_text(encoding="utf-8"))
        for ad in data["adapters"]:
            if ad["status"] == "missing":
                self.assertTrue(ad.get("fallback"), f"{ad['tool']} missing but no fallback")

    def test_no_default_binding(self):
        data = json.loads(REGISTRY.read_text(encoding="utf-8"))
        self.assertEqual(data["defaultBinding"], "none")
        self.assertNotIn("primaryRuntime", data)
        self.assertIn("hostSelection", data)

    def test_open_design_marked_as_host_adapter(self):
        data = json.loads(REGISTRY.read_text(encoding="utf-8"))
        od = next(ad for ad in data["adapters"] if ad["tool"] == "Open Design")
        self.assertEqual(od.get("hostAdapter"), "open-design")

    def test_every_adapter_has_evidence_block(self):
        data = json.loads(REGISTRY.read_text(encoding="utf-8"))
        for ad in data["adapters"]:
            self.assertIn("evidence", ad, f"{ad['tool']} missing evidence block")
            ev = ad["evidence"]
            self.assertIn("level", ev)
            self.assertIn("task_ids", ev)
            self.assertIn("artifact_paths", ev)

    def test_registry_schema_validates(self):
        """Registry must conform to adapter-contract schema v2 (V42-0107)."""
        import jsonschema  # available via requirements.txt? only if installed
        schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
        data = json.loads(REGISTRY.read_text(encoding="utf-8"))
        for ad in data["adapters"]:
            jsonschema.validate(instance=ad, schema=schema)

    def test_blocked_license_status_is_legal_but_not_executable(self):
        """R0-006: BLOCKED_BY_LICENSE is a legal gate, not an execution claim.

        Schema-accepted, but every capability must be supported=false and the
        entry must carry a license string (rights decision ref). A blocked
        adapter must never advertise an executable capability.
        """
        import jsonschema
        schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
        data = json.loads(REGISTRY.read_text(encoding="utf-8"))
        blocked = [ad for ad in data["adapters"] if ad.get("status") == "BLOCKED_BY_LICENSE"]
        self.assertTrue(blocked, "expected at least one BLOCKED_BY_LICENSE adapter (R0-006 H3 gate)")
        for ad in blocked:
            # legal: schema validates
            jsonschema.validate(instance=ad, schema=schema)
            # but not executable: no capability may be advertised as supported
            for cap in ad["capabilities"]:
                self.assertFalse(
                    cap.get("supported"),
                    f"{ad['adapter_id']} blocked by license but {cap['name']} is supported",
                )
            self.assertTrue(ad.get("license"), f"{ad['adapter_id']} blocked but no license field")

    def test_schema_rejects_supported_capability_when_blocked(self):
        """Schema-level negative fixture: BLOCKED_BY_LICENSE + supported=true must fail."""
        import jsonschema
        schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
        bad = {
            "adapter_id": "adapter-x",
            "tool": "X",
            "status": "BLOCKED_BY_LICENSE",
            "mode": "none",
            "license": "proprietary",
            "capabilities": [{"name": "c1", "supported": True}],
            "evidence": {"level": "E0", "runtime_version": None, "task_ids": [], "artifact_paths": [], "note": ""},
        }
        errors = list(jsonschema.Draft202012Validator(schema).iter_errors(bad))
        self.assertTrue(errors, "blocked adapter with supported capability must be rejected")


if __name__ == "__main__":
    unittest.main(verbosity=2)
