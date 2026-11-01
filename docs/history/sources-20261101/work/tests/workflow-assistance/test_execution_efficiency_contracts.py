from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[2]
SCHEMA_DIR = ROOT / "packages" / "contracts" / "schemas" / "workflow"


VALID = {
    "project-profile.schema.json": {
        "schema_version": "workflow/project-profile/v1",
        "project": {"id": "work-lab", "root_policy": "discover_git_root", "windows_native_first": True},
        "configuration": {"precedence": ["global_defaults", "project_profile", "local_runtime", "environment", "cli"]},
        "modules": {"workflow": {"roots": ["packages/client-neutral-core"]}},
        "risk_zones": {"critical": [".github/workflows/**"]},
        "gates": {"workflow": {"command": "python gate.py", "tiers": ["TARGETED", "STAGE"], "platform": "discovered"}},
        "ci": {"stable_aggregate_check": "aggregate", "exact_sha_required_for": ["critical"], "outage_blocks": ["release"]},
    },
    "gate-registry.schema.json": {
        "schema_version": "workflow/gate-registry/v1",
        "gate": {
            "id": "example.module.test",
            "description": "Run the affected gate.",
            "inputs": {"paths": ["src/**"], "invalidators": ["pyproject.toml"]},
            "depends_on": [],
            "tiers": ["TARGETED", "STAGE"],
            "platform": {"capabilities": ["python"], "operating_system": "any"},
            "execution": {"command": "python -m unittest", "timeout": "configurable", "cacheable": True, "resource_class": "cpu"},
            "evidence": {"release_blocking": False, "history_sensitive": False, "cache_trust": "same_project"},
            "failure": {"product_exit_codes": [1], "infrastructure_classification": "explicit_adapter", "automatic_retry_budget": 0},
        },
    },
    "gate-plan.schema.json": {
        "schema_version": "workflow/gate-plan/v1",
        "plan_id": "plan-1",
        "source_identity": {"repository": "DTALEX66/WORK-LAB", "commit": {"algorithm": "repository-default", "object_type": "commit", "oid": "abc"}, "tree": {"algorithm": "repository-default", "object_type": "tree", "oid": "def"}},
        "changed_paths": ["src/a.py"],
        "required_gates": ["workflow.unit"],
        "skipped_gates": [{"gate_id": "observer", "reason": "no affected paths"}],
        "risk": "low",
        "delivery_effect": "none",
        "platform_scope": ["linux"],
        "plan_digest": {"algorithm": "sha256", "value": "a" * 64},
        "generated_at": "2026-08-07T00:00:00Z",
    },
    "blocker.schema.json": {
        "schema_version": "workflow/blocker/v1",
        "blocker_id": "blocker-1",
        "class": "CI_QUEUE_STALLED",
        "scope": "gate",
        "retry_policy": "once_after_recovery",
        "fingerprint": "abcdef0123456789",
        "message": "No job observed within the queue window.",
        "created_at": "2026-08-07T00:00:00Z",
    },
    "ci-observation.schema.json": {
        "schema_version": "workflow/ci-observation/v1",
        "observation_id": "observation-1",
        "repository": "DTALEX66/WORK-LAB",
        "commit": "abc",
        "state": "QUEUED_NO_JOB",
        "workflow": "work-lab-gate",
        "run_id": None,
        "attempt": None,
        "queue_age_seconds": 120,
        "job_count": 0,
        "observed_at": "2026-08-07T00:00:00Z",
        "next_observation_at": "2026-08-07T00:01:00Z",
        "retry_budget": 1,
    },
    "evidence-manifest.schema.json": {
        "schema_version": "workflow/evidence-manifest/v1",
        "manifest_id": "manifest-1",
        "source_identity": {"repository": "DTALEX66/WORK-LAB", "commit": {"algorithm": "repository-default", "object_type": "commit", "oid": "abc"}, "tree": {"algorithm": "repository-default", "object_type": "tree", "oid": "def"}},
        "plan": {"digest": {"algorithm": "sha256", "value": "b" * 64}, "base_oid": "base", "head_oid": "head"},
        "evidence": [{"gate_id": "workflow.unit", "state": "PASS", "coverage": "targeted", "input_fingerprint": {"algorithm": "sha256", "value": "c" * 64}, "log_digest": {"algorithm": "sha256", "value": "d" * 64}, "started_at": "2026-08-07T00:00:00Z", "completed_at": "2026-08-07T00:00:01Z", "duration_ms": 1000}],
        "redaction": {"policy": "secrets-never-stored", "secrets_stored": False},
    },
}


class ExecutionEfficiencyContractTests(unittest.TestCase):
    def test_positive_instances_validate(self) -> None:
        for name, instance in VALID.items():
            with self.subTest(schema=name):
                schema = json.loads((SCHEMA_DIR / name).read_text(encoding="utf-8"))
                errors = list(Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(instance))
                self.assertEqual(errors, [], errors)

    def test_negative_instances_fail_closed(self) -> None:
        for name, instance in VALID.items():
            with self.subTest(schema=name):
                broken = copy.deepcopy(instance)
                required = json.loads((SCHEMA_DIR / name).read_text(encoding="utf-8")).get("required", [])
                broken.pop(required[0])
                schema = json.loads((SCHEMA_DIR / name).read_text(encoding="utf-8"))
                errors = list(Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(broken))
                self.assertTrue(errors, name)

    def test_gate_plan_rejects_non_sha256_digest_shape(self) -> None:
        broken = copy.deepcopy(VALID["gate-plan.schema.json"])
        broken["plan_digest"]["value"] = "not-a-digest"
        schema = json.loads((SCHEMA_DIR / "gate-plan.schema.json").read_text(encoding="utf-8"))
        errors = list(Draft202012Validator(schema).iter_errors(broken))
        self.assertTrue(errors)


if __name__ == "__main__":
    unittest.main()
