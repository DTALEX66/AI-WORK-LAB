from __future__ import annotations

import importlib.util
import os
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class HermesFallbackTests(unittest.TestCase):
    def test_registry_ledger_and_observer_are_readable_without_hermes_home(self):
        previous = os.environ.pop("HERMES_HOME", None)
        try:
            manifest = (ROOT / "packages/client-neutral-core/workflow-manifest.yaml").read_text(encoding="utf-8")
            self.assertIn("client_neutral", manifest)
            ledger_module = load("task_ledger_fallback", ROOT / "packages/client-neutral-core/scripts/task_ledger.py")
            observer_module = load("observer_event_fallback", ROOT / "packages/client-neutral-core/scripts/observer_event.py")
            with tempfile.TemporaryDirectory() as raw:
                ledger = ledger_module.TaskLedger(Path(raw) / "ledger.json")
                task = ledger.create("fallback-task", "fallback-key", token_budget=10)
                self.assertEqual(task["status"], "QUEUED")
                observer = observer_module.ObserverEventStore(Path(raw) / "observer.jsonl")
                observer.append({
                    "event_id": "fallback-event", "run_id": "fallback-run", "task_id": "fallback-task",
                    "event_type": "task.status", "occurred_at": "2026-01-01T00:00:00Z",
                    "source": "fallback-test", "projection_key": "task:fallback-task", "payload": {"status": "QUEUED"},
                })
                self.assertEqual(observer.rebuild_task_projection()["task:fallback-task"]["status"], "QUEUED")
        finally:
            if previous is not None:
                os.environ["HERMES_HOME"] = previous


if __name__ == "__main__":
    unittest.main()
