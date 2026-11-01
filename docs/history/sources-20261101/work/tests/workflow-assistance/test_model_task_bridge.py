"""Contract tests for model task bridge wiring (WL3-410 / MR-13).

Covers attempt idempotency keys, result validation fail-closed, resource
lease integration, observer no-model skip, plan block propagation.
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts/workflow"))

from model_task_bridge import (ModelTaskHandler, ResultValidationError,
                               attempt_key, validate_result)
from model_capability_resolver import Resolver


def simple_catalog() -> dict:
    return {"models": {
        "local-general": {"provider": "ollama", "locality": "local", "role": "local.general.fast",
                          "capabilities": ["text"], "lifecycle": "ACTIVE", "quality_state": "OK"},
    }}


def make_handler(runtime_root: Path, executor=None) -> ModelTaskHandler:
    resolver = Resolver({}, simple_catalog(), {}, {})
    return ModelTaskHandler(
        runtime_root, resolver,
        executor or (lambda task, plan: {"status": "ok", "evidence_hash": "abc"}))


class FakeStore:
    def __init__(self) -> None:
        self.last = None

    def upsert_task(self, payload: dict) -> None:
        self.last = payload


class ModelTaskBridgeTests(unittest.TestCase):
    def test_attempt_key_deterministic(self) -> None:
        self.assertEqual(attempt_key("t1", 1), attempt_key("t1", 1))
        self.assertNotEqual(attempt_key("t1", 1), attempt_key("t1", 2))

    def test_validate_result_allows_clean(self) -> None:
        validate_result({"status": "ok", "evidence_hash": "x"})

    def test_validate_result_rejects_secret(self) -> None:
        with self.assertRaises(ResultValidationError):
            validate_result({"api_key": "secret"})

    def test_validate_result_rejects_prompt_body(self) -> None:
        with self.assertRaises(ResultValidationError):
            validate_result({"prompt": "private"})

    def test_validate_result_rejects_unknown_field(self) -> None:
        with self.assertRaises(ResultValidationError):
            validate_result({"bogus_field": 1})

    def test_handler_runs_executor_and_records_checkpoint(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = FakeStore()
            handler = make_handler(Path(tmp))
            task = {"task_id": "t1", "task_kind": "general",
                    "data_privacy": "public", "required_capabilities": ["text"],
                    "checkpoint": {}}
            handler(store, task)
            # Bridge mutates the task checkpoint in place; the DurableWorker
            # persists the terminal state after the handler returns.
            self.assertIn("attempt_key", task["checkpoint"])
            self.assertEqual(task["checkpoint"]["selected"], "local-general")

    def test_observer_task_skips_executor(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = FakeStore()
            called = []
            handler = ModelTaskHandler(
                Path(tmp), Resolver({}, simple_catalog(), {}, {}),
                executor=lambda task, plan: called.append(task) or {"status": "ok"})
            handler(store, {"task_id": "obs", "task_kind": "observer", "data_privacy": "public"})
            self.assertEqual(called, [])  # NO_MODEL_REQUIRED -> skip

    def test_blocked_task_raises(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = FakeStore()
            handler = make_handler(Path(tmp))
            with self.assertRaises(RuntimeError):
                handler(store, {"task_id": "b1", "task_kind": "general",
                                "data_privacy": "public",
                                "required_capabilities": ["reasoning"]})

    @mock.patch("model_task_bridge.ResourceLease")
    def test_resource_busy_raises(self, LeaseMock) -> None:
        LeaseMock.return_value.acquire.return_value = {"status": "QUEUED"}
        with tempfile.TemporaryDirectory() as tmp:
            store = FakeStore()
            handler = make_handler(Path(tmp))
            with self.assertRaises(RuntimeError):
                handler(store, {"task_id": "t2", "task_kind": "general",
                                "data_privacy": "public", "resource_group": "gpu.heavy",
                                "required_capabilities": ["text"]})

    @mock.patch("model_task_bridge.ResourceLease")
    def test_lease_released_after_run(self, LeaseMock) -> None:
        lease = mock.Mock()
        lease.acquire.return_value = {"status": "HELD"}
        LeaseMock.return_value = lease
        with tempfile.TemporaryDirectory() as tmp:
            store = FakeStore()
            handler = make_handler(Path(tmp))
            handler(store, {"task_id": "t3", "task_kind": "general",
                            "data_privacy": "public", "required_capabilities": ["text"]})
            lease.release.assert_called_once()


if __name__ == "__main__":
    unittest.main()
