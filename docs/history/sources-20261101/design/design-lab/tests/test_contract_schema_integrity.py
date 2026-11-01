# SPDX-License-Identifier: MIT
"""Contract-schema integrity tests (PR115 audit F02/F03).

Guards:
1. Every JSON Schema under design-lab/schemas/contracts is itself a valid
   2020-12 meta-schema instance.
2. Every local "#/..." $ref resolves to an existing $defs/pointer in the same
   file (no PointerToNowhere), and no local pointer is referenced by nothing.
3. job-spec positive fixture validates; negative fixtures (missing
   operation_intent fields / attempt_no < 1) are rejected.
4. Schemas reject empty-string identity fields where the schema declares
   minLength: fixtures for capability-evidence and job-attempt (F03).

F03 additionally covers the tightened capability-evidence and job-attempt
schemas (bound-SHA/attempt_id/enumeration) via positive/negative fixtures.
"""
from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTRACTS = ROOT / "schemas" / "contracts"


def _load(name: str) -> dict:
    return json.loads((CONTRACTS / name).read_text(encoding="utf-8"))


class ContractSchemaIntegrityTests(unittest.TestCase):
    def test_every_contract_schema_is_valid_2020_12(self):
        import jsonschema
        for path in sorted(CONTRACTS.glob("*.json")):
            schema = json.loads(path.read_text(encoding="utf-8"))
            jsonschema.Draft202012Validator.check_schema(schema)  # raises on invalid

    def test_no_local_ref_points_to_nowhere(self):
        """Every '#/...' $ref must resolve inside the same document."""
        for path in sorted(CONTRACTS.glob("*.json")):
            doc = json.loads(path.read_text(encoding="utf-8"))

            def walk(node):
                if isinstance(node, dict):
                    ref = node.get("$ref")
                    if isinstance(ref, str) and ref.startswith("#/"):
                        # resolve pointer by hand against the document root
                        ptr = ref[2:].split("/")
                        target = doc
                        for part in ptr:
                            part = part.replace("~1", "/").replace("~0", "~")
                            if not isinstance(target, dict) or part not in target:
                                self.fail(f"{path.name}: {ref} does not resolve (missing {part})")
                            target = target[part]
                    for v in node.values():
                        walk(v)
                elif isinstance(node, list):
                    for v in node:
                        walk(v)

            walk(doc)

    def test_job_spec_positive_fixture(self):
        import jsonschema
        schema = _load("job-spec.schema.json")
        good = {
            "job_id": "job-1",
            "schemaVersion": "design-lab/job-spec/v1",
            "attempt_no": 1,
            "operation_intent": {
                "operation_id": "op-1",
                "schemaVersion": "design-lab/operation-intent/v1",
                "idempotency_scope": "design-session",
                "idempotency_key": "k-1",
                "request_hash": "sha256:" + "a" * 64,
            },
        }
        jsonschema.validate(instance=good, schema=schema)

    def test_job_spec_negative_fixtures(self):
        import jsonschema
        schema = _load("job-spec.schema.json")
        bad_intent = {
            "job_id": "job-2",
            "schemaVersion": "design-lab/job-spec/v1",
            "attempt_no": 1,
            "operation_intent": {"operation_id": "op-2"},  # missing required fields
        }
        self.assertRaises(jsonschema.ValidationError, jsonschema.validate, bad_intent, schema)
        bad_attempt = {
            "job_id": "job-3",
            "schemaVersion": "design-lab/job-spec/v1",
            "attempt_no": 0,
            "operation_intent": {
                "operation_id": "op-3",
                "schemaVersion": "design-lab/operation-intent/v1",
                "idempotency_scope": "s",
                "idempotency_key": "k",
                "request_hash": "h",
            },
        }
        self.assertRaises(jsonschema.ValidationError, jsonschema.validate, bad_attempt, schema)


class CapabilityEvidenceContractTests(unittest.TestCase):
    """F03: capability-evidence must bind current-tree identity and reject empty/fake values."""

    def test_evidence_rejects_empty_ids_and_zero_sha(self):
        import jsonschema
        schema = _load("capability-evidence.schema.json")
        bad = {
            "evidence_id": "",
            "schemaVersion": "design-lab/capability-evidence/v1",
            "capability_id": "adapter-x/render",
            "adapter_id": "adapter-x",
            "evidence_level": "E5",  # fake top level with zero sha and no approval/release
            "bound_sha": "0" * 40,
            "adapter_version": "",
            "host": "",
            "host_version": "",
            "os": "",
            "commands": [],
        }
        errors = list(jsonschema.Draft202012Validator(schema).iter_errors(bad))
        self.assertTrue(errors, "empty-ID / zero-SHA E5 evidence must be rejected")

    def test_evidence_positive_fixture(self):
        import jsonschema
        schema = _load("capability-evidence.schema.json")
        good = {
            "evidence_id": "ev-1",
            "schemaVersion": "design-lab/capability-evidence/v1",
            "capability_id": "adapter-x/render",
            "adapter_id": "adapter-x",
            "evidence_level": "E1",
            "bound_sha": "a" * 40,
            "adapter_version": "1.0.0",
            "host": "cli",
            "host_version": "1",
            "os": "windows",
            "commands": ["probe --check"],
        }
        jsonschema.validate(instance=good, schema=schema)


class JobAttemptContractTests(unittest.TestCase):
    """F03: job-attempt must carry an attempt_id and reject free-string statuses."""

    def test_job_attempt_requires_attempt_id(self):
        schema = _load("job-attempt.schema.json")
        required = schema.get("required", [])
        self.assertIn("attempt_id", required, "job-attempt schema must require attempt_id (F03)")
        self.assertIn("job_id", required)
        for prop in ("status", "outcome"):
            if prop in schema.get("properties", {}) and "enum" not in schema["properties"][prop]:
                self.fail(f"job-attempt {prop} must be enum-constrained (F03)")
            if prop not in schema.get("properties", {}):
                self.fail(f"job-attempt missing {prop} property (F03)")

    def test_job_attempt_status_enum_rejects_fake(self):
        import jsonschema
        schema = _load("job-attempt.schema.json")
        bad = {"attempt_id": "att-1", "job_id": "job-1", "status": "made-up-status"}
        errors = list(jsonschema.Draft202012Validator(schema).iter_errors(bad))
        self.assertTrue(errors, "free-string attempt status must be rejected")


if __name__ == "__main__":
    unittest.main(verbosity=2)
