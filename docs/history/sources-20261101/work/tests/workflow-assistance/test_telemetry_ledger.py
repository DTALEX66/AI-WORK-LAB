from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("telemetry_ledger", ROOT / "services/receipts/telemetry_ledger.py")
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)

class TelemetryLedgerTests(unittest.TestCase):
    def test_trace_and_trace_tree_link_parent_child_events(self):
        with tempfile.TemporaryDirectory() as raw:
            ledger = module.TelemetryLedger(Path(raw) / "telemetry.jsonl")
            ledger.append({"event_id": "e-root", "trace_id": "t1", "source": "test", "outcome": "ok"})
            ledger.append({"event_id": "e-child", "trace_id": "t1", "parent_id": "e-root", "source": "test", "outcome": "ok"})
            ledger.append({"event_id": "e-other", "trace_id": "t2", "source": "test", "outcome": "ok"})
            trace = ledger.trace("t1")
            self.assertEqual([r["event_id"] for r in trace], ["e-root", "e-child"])
            tree = ledger.trace_tree("t1")
            self.assertEqual(tree[0]["event_id"], "e-root")
            self.assertEqual(tree[0]["trace_depth"], 0)
            self.assertEqual(tree[1]["event_id"], "e-child")
            self.assertEqual(tree[1]["trace_depth"], 1)
            self.assertEqual(tree[1]["trace_path"], "e-root.e-child")
            self.assertEqual(ledger.trace("t2"), [r for r in ledger.read() if r["event_id"] == "e-other"])

    def test_append_is_idempotence_guarded_and_projection_is_redacted(self):
        with tempfile.TemporaryDirectory() as raw:
            ledger = module.TelemetryLedger(Path(raw) / "telemetry.jsonl")
            row = ledger.append({"event_id": "e1", "occurred_at": "2026-08-08T00:00:00Z", "source": "workflow", "outcome": "completed", "usage_total": 3})
            self.assertEqual(row["sequence"], 1)
            self.assertEqual(ledger.projection()["event_count"], 1)
            with self.assertRaises(ValueError):
                ledger.append({"event_id": "e1", "source": "workflow"})

    def test_sensitive_fields_are_rejected(self):
        with tempfile.TemporaryDirectory() as raw:
            ledger = module.TelemetryLedger(Path(raw) / "telemetry.jsonl")
            for key in ("prompt", "prompt_body", "responseBody", "api-key", "credential_value"):
                with self.subTest(key=key), self.assertRaisesRegex(ValueError, "sensitive telemetry key"):
                    ledger.append({"event_id": f"e2-{key}", "nested": {key: "redacted"}})

    def test_reserved_producer_and_sequence_cannot_be_spoofed(self):
        with tempfile.TemporaryDirectory() as raw:
            ledger = module.TelemetryLedger(Path(raw) / "telemetry.jsonl")
            for field, value in (("producer", "observer"), ("sequence", 999), ("schemaVersion", "fake")):
                with self.subTest(field=field), self.assertRaisesRegex(ValueError, "reserved telemetry key"):
                    ledger.append({"event_id": f"e-{field}", field: value})

            row = ledger.append({"event_id": "good", "source": "workflow"})
            self.assertEqual(row["producer"], "workflow-assistance")
            self.assertEqual(row["sequence"], 1)

if __name__ == "__main__":
    unittest.main()
