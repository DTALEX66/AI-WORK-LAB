from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "packages/client-neutral-core/scripts/observer_event.py"


def load_module():
    spec = importlib.util.spec_from_file_location("observer_event", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ObserverEventTests(unittest.TestCase):
    def test_append_is_monotonic_and_rebuilds_projection_after_reopen(self) -> None:
        module = load_module()
        with tempfile.TemporaryDirectory() as raw:
            store = module.ObserverEventStore(Path(raw) / ".hermes" / "task-runtime" / "observer.jsonl")
            first = store.append({
                "event_id": "e-1", "run_id": "r-1", "task_id": "t-1",
                "event_type": "task.status", "occurred_at": "2026-01-01T00:00:00Z",
                "source": "local-test", "projection_key": "task:t-1",
                "payload": {"status": "RUNNING", "heartbeat": "2026-01-01T00:00:00Z", "budget": {"tokens": 10}, "blocked": False, "evidence": []},
            })
            second = module.ObserverEventStore(store.path).append({
                "event_id": "e-2", "run_id": "r-1", "task_id": "t-1",
                "event_type": "task.status", "occurred_at": "2026-01-01T00:00:01Z",
                "source": "local-test", "projection_key": "task:t-1", "payload": {"status": "COMPLETED"},
            })
            self.assertEqual(first["sequence"], 1)
            self.assertEqual(second["sequence"], 2)
            reopened = module.ObserverEventStore(store.path)
            self.assertEqual(reopened.rebuild_projection()["task:t-1"]["status"], "COMPLETED")
            self.assertIn("task:t-1", reopened.rebuild_task_projection())

    def test_duplicate_event_id_and_sensitive_payload_fail_closed(self) -> None:
        module = load_module()
        with tempfile.TemporaryDirectory() as raw:
            path = Path(raw) / "events.jsonl"
            store = module.ObserverEventStore(path)
            event = {
                "event_id": "e-1", "run_id": "r-1", "task_id": "t-1",
                "event_type": "task.status", "occurred_at": "2026-01-01T00:00:00Z",
                "source": "local-test", "projection_key": "task:t-1", "payload": {"status": "RUNNING"},
            }
            store.append(event)
            with self.assertRaisesRegex(ValueError, "duplicate"):
                store.append(event)
            with self.assertRaisesRegex(ValueError, "sensitive"):
                store.append({**event, "event_id": "e-2", "payload": {"token": "redacted-test"}})

    def test_event_file_is_json_lines_with_explicit_schema_version(self) -> None:
        module = load_module()
        with tempfile.TemporaryDirectory() as raw:
            path = Path(raw) / "events.jsonl"
            module.ObserverEventStore(path).append({
                "event_id": "e-1", "run_id": "r-1", "task_id": "t-1",
                "event_type": "observer.health", "occurred_at": "2026-01-01T00:00:00Z",
                "source": "local-test", "projection_key": "observer", "payload": {"state": "PASS"},
            })
            line = path.read_text(encoding="utf-8").strip()
            self.assertEqual(json.loads(line)["schema_version"], module.SCHEMA_VERSION)


if __name__ == "__main__":
    unittest.main()
