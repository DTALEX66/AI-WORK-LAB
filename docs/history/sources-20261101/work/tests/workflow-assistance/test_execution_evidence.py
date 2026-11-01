"""WLGM-060 tests: Execution Evidence standard contract."""
from __future__ import annotations

import unittest

from execution_evidence import (
    EvidenceValidationError,
    ExecutionEvidence,
    stable_dedupe_key,
)


def make_event(**overrides):
    base = dict(
        event_id="evt-1",
        event_type="execution_running",
        occurred_at="2026-08-14T00:00:00Z",
        source_event_id="src-1",
        adapter_id="hermes",
        anchor_project_id="work-lab",
        evidence_level="A",
    )
    base.update(overrides)
    return ExecutionEvidence(**base)


class ExecutionEvidenceTests(unittest.TestCase):
    def test_valid_event_passes(self) -> None:
        event = make_event()
        record = event.as_record()
        self.assertEqual(record["eventType"], "execution_running")
        self.assertIn("dedupeKey", record)

    def test_rejects_prompt_body(self) -> None:
        with self.assertRaises(EvidenceValidationError):
            make_event(payload={"prompt": "secret instruction"}).validate()

    def test_rejects_api_key_field(self) -> None:
        with self.assertRaises(EvidenceValidationError):
            make_event(payload={"api_key": "sk-xxx"}).validate()

    def test_rejects_env_file(self) -> None:
        with self.assertRaises(EvidenceValidationError):
            make_event(payload={"env_file": "path/to/.env"}).validate()

    def test_rejects_unknown_event_type(self) -> None:
        with self.assertRaises(EvidenceValidationError):
            make_event(event_type="execution_teleport").validate()

    def test_rejects_invalid_evidence_level(self) -> None:
        with self.assertRaises(EvidenceValidationError):
            make_event(evidence_level="Z").validate()

    def test_unknown_fields_forward_compatible(self) -> None:
        record = make_event(payload={"future_flag": True}).as_record()
        self.assertEqual(record["payload"]["future_flag"], True)

    def test_missing_key_fields_quarantine(self) -> None:
        with self.assertRaises(EvidenceValidationError):
            ExecutionEvidence(event_id="", event_type="execution_running", occurred_at="t").validate()

    def test_derived_dedupe_key_stable(self) -> None:
        k1 = stable_dedupe_key("src-1", "execution_running", "2026-08-14T00:00:00Z")
        k2 = stable_dedupe_key("src-1", "execution_running", "2026-08-14T00:00:00Z")
        self.assertEqual(k1, k2)
        k3 = stable_dedupe_key("src-1", "execution_completed", "2026-08-14T00:00:00Z")
        self.assertNotEqual(k1, k3)

    def test_paths_projected_by_default(self) -> None:
        record = make_event(payload={"output": "C:/Users/admin/secret/out.txt"}).as_record()
        self.assertEqual(record["payload"]["output"], "<path-projected>")


if __name__ == "__main__":
    unittest.main()
