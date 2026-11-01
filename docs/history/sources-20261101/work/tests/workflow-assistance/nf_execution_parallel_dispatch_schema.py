"""P2 / parallel-dispatch spec §P2: schema-conformance negative controls.

Validates that the registered ``workflow/execution-parallel-dispatch/v1`` JSON
Schema accepts a well-formed OK receipt and rejects the spec's listed INVALID
shapes (missing/unknown status, non-array executors, events missing phase),
plus a non-workflow-namespace receipt. Pure + fixture-driven; no filesystem
writes, no credentials, no auto relocation/deletion (§40).
"""
from __future__ import annotations

import json
import os
import sys
import unittest

try:
    import jsonschema
except ImportError:  # pragma: no cover
    jsonschema = None

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

SCHEMA_NAME = "execution-parallel-dispatch.schema.json"
SCHEMA_VERSION = "workflow/execution-parallel-dispatch/v1"
NON_WORKFLOW_NAMESPACE = "execution-federation/execution-parallel-dispatch/v1"


def _schema() -> dict:
    p = os.path.join(ROOT, "packages", "contracts", "schemas", "workflow", SCHEMA_NAME)
    with open(p, encoding="utf-8") as handle:
        return json.load(handle)


def _ok_receipt() -> dict:
    """A valid OK receipt: both legs succeed, no failures."""
    return {
        "schema_version": SCHEMA_VERSION,
        "op": "NEW",
        "executors": ["hermes", "codex"],
        "payload": {"task": "refactor"},
        "adapter_kind": "new",
        "per_executor_timeout": 30.0,
        "fail_fast": False,
        "status": "OK",
        "per_executor": {
            "hermes": {"op": "NEW", "executor": "hermes", "ok": True, "status": "OK"},
            "codex": {"op": "NEW", "executor": "codex", "ok": True, "status": "OK"},
        },
        "succeeded": ["hermes", "codex"],
        "failed": [],
        "timed_out": [],
        "unknown": [],
        "events": [
            {"executor": "hermes", "phase": "STARTED", "ts": 1.0, "ok": True, "status": "OK"},
            {"executor": "hermes", "phase": "DONE", "ts": 2.0, "ok": True, "status": "OK"},
            {"executor": "codex", "phase": "STARTED", "ts": 1.0, "ok": True, "status": "OK"},
            {"executor": "codex", "phase": "DONE", "ts": 2.0, "ok": True, "status": "OK"},
        ],
        "notes": [],
    }


class ExecutionParallelDispatchSchemaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if jsonschema is None:
            raise unittest.SkipTest("jsonschema not available")
        cls.schema = _schema()
        cls.validator = jsonschema.Draft202012Validator(cls.schema)

    def _valid(self, instance: dict) -> None:
        errors = list(self.validator.iter_errors(instance))
        self.assertEqual(
            errors, [],
            "expected VALID but got: " + "; ".join(e.message for e in errors),
        )

    def _invalid(self, instance: dict) -> None:
        errors = list(self.validator.iter_errors(instance))
        self.assertNotEqual(errors, [], "expected INVALID but the instance passed the schema")

    def test_ok_receipt_is_valid(self):
        self._valid(_ok_receipt())

    def test_missing_status_is_invalid(self):
        bad = _ok_receipt()
        del bad["status"]
        self._invalid(bad)

    def test_unknown_status_is_invalid(self):
        bad = _ok_receipt()
        bad["status"] = "EXPLODED"
        self._invalid(bad)

    def test_non_array_executors_is_invalid(self):
        bad = _ok_receipt()
        bad["executors"] = "hermes,codex"
        self._invalid(bad)

    def test_event_missing_phase_is_invalid(self):
        bad = _ok_receipt()
        for event in bad["events"]:
            del event["phase"]
        self._invalid(bad)

    def test_non_workflow_namespace_is_rejected(self):
        # The schema is registered under the workflow namespace; a receipt that
        # claims a non-workflow top-level namespace must be INVALID (const on
        # schema_version pins the workflow/ ownership boundary).
        bad = _ok_receipt()
        bad["schema_version"] = NON_WORKFLOW_NAMESPACE
        self._invalid(bad)

    def test_ownership_is_workflow(self):
        # Ownership check: the registered id is owned by the workflow module,
        # so a non-workflow namespace must NOT satisfy the ownership const.
        self.assertNotEqual(
            self.schema["properties"]["schema_version"]["const"],
            NON_WORKFLOW_NAMESPACE,
        )
        self.assertEqual(
            self.schema["properties"]["schema_version"]["const"],
            SCHEMA_VERSION,
        )


if __name__ == "__main__":
    unittest.main()
