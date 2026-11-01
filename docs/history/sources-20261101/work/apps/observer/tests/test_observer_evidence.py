from __future__ import annotations

import hashlib
import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from observer_evidence import telemetry_events, token_usage_events, workflow_evidence_events  # noqa: E402
from observer_runtime import ObserverInputError, project_read_only_dashboard  # noqa: E402


class ObserverEvidenceTests(unittest.TestCase):
    def envelope(self, *, state: str = "PASS") -> dict:
        digest = hashlib.sha256(b"artifact").hexdigest()
        return {
            "schema_version": "workflow/evidence-envelope/v1",
            "evidence_id": "evidence-001",
            "task_id": "WA-001",
            "state": state,
            "level": "E2",
            "source": {"kind": "isolated", "identity": "local-test"},
            "artifacts": [{"path": "tests/test.py", "sha256": digest, "kind": "test"}],
            "redaction": {"policy": "secrets-never-stored", "secrets_stored": False},
            "checks": ["targeted-test"],
        }

    def test_normalizes_workflow_input_without_payloads(self) -> None:
        workflow = workflow_evidence_events([self.envelope()])[0]
        self.assertEqual(workflow["eventType"], "evidence.pass")
        self.assertEqual(workflow["sourceModule"], "workflow-assistance")
        self.assertNotIn("artifacts", workflow)
        self.assertEqual(len(workflow["contentDigest"]), 64)

    def test_rebuilds_cross_module_projection_without_a_second_store(self) -> None:
        events = workflow_evidence_events([self.envelope()])
        projection = project_read_only_dashboard(events)
        rebuilt = project_read_only_dashboard(events)
        self.assertEqual(projection, rebuilt)
        self.assertEqual(projection["tasks"][0]["events"], 1)
        self.assertNotIn("taskId", projection["tasks"][0])

    def test_token_usage_adapter_emits_sanitized_observer_event(self) -> None:
        events = token_usage_events([{"input_tokens": 12, "output_tokens": 8, "total_tokens": 20, "records": 1}])
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["eventType"], "usage.summary")
        self.assertEqual(events[0]["usage"]["total_tokens"], 20)
        self.assertNotIn("model", events[0])

    def test_telemetry_adapter_keeps_only_stable_fields(self) -> None:
        events = telemetry_events([{"operation": "chat", "provider": "fixture", "model": "unknown", "task_id": "WA-001", "source_digest": hashlib.sha256(b"source").hexdigest(), "input_tokens": 12, "output_tokens": 8, "latency_ms": 12, "outcome": "ok"}])
        self.assertEqual(events[0]["eventType"], "telemetry.summary")
        self.assertEqual(events[0]["coverage"], "full")
        self.assertNotIn("prompt", events[0])
        self.assertEqual(events[0]["telemetry"]["input_tokens"], 12)

    def test_telemetry_missing_optional_data_is_partial_without_zero_inference(self) -> None:
        event = telemetry_events([{"operation": "chat", "provider": "fixture", "task_id": "WA-001", "outcome": "unknown"}])[0]
        self.assertEqual(event["coverage"], "partial")
        self.assertNotIn("input_tokens", event["telemetry"])

    def test_telemetry_rejects_invalid_source_digest_and_numeric_values(self) -> None:
        with self.assertRaises(ObserverInputError):
            telemetry_events([{"operation": "chat", "provider": "fixture", "task_id": "WA-001", "source_digest": "not-a-digest"}])
        with self.assertRaises(ObserverInputError):
            telemetry_events([{"operation": "chat", "provider": "fixture", "task_id": "WA-001", "latency_ms": -1}])

    def test_telemetry_rejects_body_and_unknown_fields(self) -> None:
        with self.assertRaises(ObserverInputError):
            telemetry_events([{"operation": "chat", "provider": "fixture", "task_id": "WA-001", "prompt": "body"}])
        with self.assertRaises(ObserverInputError):
            telemetry_events([{"operation": "chat", "provider": "fixture", "task_id": "WA-001", "unknown": 1}])

    def test_token_usage_adapter_rejects_raw_or_inferred_usage(self) -> None:
        with self.assertRaises(ObserverInputError):
            token_usage_events([{"input_tokens": 1, "output_tokens": 2, "total_tokens": 3, "records": 1, "log_line": "raw"}])
        with self.assertRaises(ObserverInputError):
            token_usage_events([{"input_tokens": 1, "output_tokens": 2, "records": 1}])

    def test_sensitive_and_unsafe_states_fail_closed(self) -> None:
        unsafe = self.envelope()
        unsafe["payload"] = {"prompt": "redacted"}
        with self.assertRaises(ObserverInputError):
            workflow_evidence_events([unsafe])
        unsafe_state = self.envelope(state="APPROVED")
        with self.assertRaises(ObserverInputError):
            workflow_evidence_events([unsafe_state])



if __name__ == "__main__":
    unittest.main()
