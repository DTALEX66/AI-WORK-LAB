from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "packages/client-neutral-core/scripts/task_ledger.py"


def load_module():
    spec = importlib.util.spec_from_file_location("task_ledger", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TaskLedgerTests(unittest.TestCase):
    def test_create_checkpoint_resume_and_idempotency(self) -> None:
        module = load_module()
        with tempfile.TemporaryDirectory() as raw:
            ledger = module.TaskLedger(Path(raw) / ".hermes" / "task-runtime" / "task-ledger")
            task = ledger.create("task-a", "idem-a", token_budget=100, time_budget_seconds=30)
            self.assertEqual(task["status"], "QUEUED")
            ledger.transition("task-a", "PLANNING")
            ledger.checkpoint("task-a", {"step": "manifest", "count": 1})
            resumed = ledger.resume("task-a")
            self.assertEqual(resumed["checkpoint"]["step"], "manifest")
            self.assertEqual(ledger.create("task-a", "idem-a")["run_id"], task["run_id"])

    def test_state_machine_rejects_invalid_transition(self) -> None:
        module = load_module()
        with tempfile.TemporaryDirectory() as raw:
            ledger = module.TaskLedger(Path(raw) / ".hermes" / "task-runtime" / "task-ledger")
            ledger.create("task-a", "idem-a")
            with self.assertRaisesRegex(ValueError, "transition"):
                ledger.transition("task-a", "COMPLETED")

    def test_external_write_is_never_retryable(self) -> None:
        module = load_module()
        with tempfile.TemporaryDirectory() as raw:
            ledger = module.TaskLedger(Path(raw) / ".hermes" / "task-runtime" / "task-ledger")
            ledger.create("task-a", "idem-a")
            result = ledger.record_error("task-a", "REMOTE_WRITE_CONFLICT", retryable=True, external_write=True)
            self.assertEqual(result["status"], "FAILED")
            self.assertEqual(result["retry_count"], 0)

    def test_errors_have_stable_non_secret_fingerprints(self) -> None:
        module = load_module()
        with tempfile.TemporaryDirectory() as raw:
            ledger = module.TaskLedger(Path(raw) / "ledger.json")
            ledger.create("task-a", "idem-a")
            result = ledger.record_error("task-a", "NETWORK_TIMEOUT", retryable=True, external_write=False)
            self.assertRegex(result["errors"][0]["fingerprint"], r"^[0-9a-f]{16}$")
            again = ledger.record_error("task-a", "NETWORK_TIMEOUT", retryable=True, external_write=False)
            self.assertEqual(again["errors"][0]["fingerprint"], result["errors"][0]["fingerprint"])

    def test_retryable_error_stops_after_three_rounds(self) -> None:
        module = load_module()
        with tempfile.TemporaryDirectory() as raw:
            ledger = module.TaskLedger(Path(raw) / ".hermes" / "task-runtime" / "task-ledger")
            ledger.create("task-a", "idem-a")
            for expected in ("RETRYING", "RETRYING", "RETRYING", "BLOCKED"):
                result = ledger.record_error("task-a", "NETWORK_TIMEOUT", retryable=True, external_write=False)
                self.assertEqual(result["status"], expected)
            self.assertEqual(result["retry_count"], 3)

    def test_cli_defaults_to_project_hermes_runtime_root(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            project = Path(raw)
            result = subprocess.run([sys.executable, str(SCRIPT), "--project", str(project), "init"], capture_output=True, text=True, encoding="utf-8", errors="replace", check=False)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertTrue((project / ".hermes" / "task-runtime" / "task-ledger" / "ledger.json").is_file())

    def test_new_ledger_instance_rebuilds_persistent_task_state(self) -> None:
        module = load_module()
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw) / ".hermes" / "task-runtime" / "task-ledger"
            ledger = module.TaskLedger(root)
            ledger.create("task-a", "idem-a", token_budget=100, time_budget_seconds=30)
            ledger.transition("task-a", "PLANNING")
            ledger.checkpoint("task-a", {"step": "persisted"})
            restarted = module.TaskLedger(root)
            task = restarted.get("task-a")
            self.assertEqual(task["status"], "PLANNING")
            self.assertEqual(task["checkpoint"], {"step": "persisted"})

    def test_checkpoint_and_transition_remain_valid_after_reopen(self) -> None:
        module = load_module()
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw) / ".hermes" / "task-runtime" / "task-ledger"
            module.TaskLedger(root).create("task-a", "idem-a")
            reopened = module.TaskLedger(root)
            reopened.transition("task-a", "PLANNING")
            reopened.checkpoint("task-a", {"phase": "plan"})
            reopened.transition("task-a", "WAITING_APPROVAL")
            final = module.TaskLedger(root).get("task-a")
            self.assertEqual(final["status"], "WAITING_APPROVAL")
            self.assertEqual(final["checkpoint"]["phase"], "plan")

    def test_expired_lease_cannot_continue_a_guarded_write(self) -> None:
        module = load_module()
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw) / ".hermes" / "task-runtime" / "task-ledger"
            ledger = module.TaskLedger(root)
            ledger.create("task-a", "idem-a")
            lease = ledger.acquire_lease("task-a", "worker-a", ttl_seconds=10, now="2026-01-01T00:00:00Z")
            with self.assertRaisesRegex(ValueError, "expired"):
                ledger.checkpoint(
                    "task-a",
                    {"step": "stale"},
                    holder="worker-a",
                    fence=lease["fence"],
                    now="2026-01-01T00:00:11Z",
                )
            replacement = ledger.acquire_lease("task-a", "worker-b", ttl_seconds=10, now="2026-01-01T00:00:11Z")
            self.assertGreater(replacement["fence"], lease["fence"])

    def test_release_lease_requires_current_fence_and_clears_holder(self) -> None:
        module = load_module()
        with tempfile.TemporaryDirectory() as raw:
            ledger = module.TaskLedger(Path(raw) / "ledger.json")
            ledger.create("task-a", "idem-a")
            lease = ledger.acquire_lease("task-a", "worker-a", ttl_seconds=10, now="2026-01-01T00:00:00Z")
            with self.assertRaisesRegex(ValueError, "fence"):
                ledger.release_lease("task-a", "worker-b", lease["fence"])
            released = ledger.release_lease("task-a", "worker-a", lease["fence"], now="2026-01-01T00:00:01Z")
            self.assertIsNone(released["lease"])

    def test_heartbeat_and_zombie_detection_preserve_fencing(self) -> None:
        module = load_module()
        with tempfile.TemporaryDirectory() as raw:
            ledger = module.TaskLedger(Path(raw) / "ledger.json")
            ledger.create("task-a", "idem-a")
            lease = ledger.acquire_lease("task-a", "worker-a", ttl_seconds=10, now="2026-01-01T00:00:00Z")
            heartbeat = ledger.heartbeat("task-a", "worker-a", lease["fence"], now="2026-01-01T00:00:05Z")
            self.assertEqual(heartbeat["heartbeat_at"], "2026-01-01T00:00:05Z")
            self.assertFalse(ledger.detect_zombie("task-a", now="2026-01-01T00:00:09Z"))
            self.assertTrue(ledger.detect_zombie("task-a", now="2026-01-01T00:00:10Z"))
            replacement = ledger.acquire_lease("task-a", "worker-b", ttl_seconds=10, now="2026-01-01T00:00:10Z")
            with self.assertRaisesRegex(ValueError, "fence"):
                ledger.heartbeat("task-a", "worker-a", lease["fence"], now="2026-01-01T00:00:11Z")
            self.assertGreater(replacement["fence"], lease["fence"])

    def test_waitpoint_releases_and_resumes_a_versioned_cursor(self) -> None:
        module = load_module()
        with tempfile.TemporaryDirectory() as raw:
            ledger = module.TaskLedger(Path(raw) / "ledger.json")
            ledger.create("task-a", "idem-a")
            ledger.transition("task-a", "PLANNING")
            ledger.transition("task-a", "RUNNING")
            lease = ledger.acquire_lease("task-a", "worker-a", now="2026-01-01T00:00:00Z")
            waiting = ledger.set_waitpoint("task-a", "CI_JOB", {"run": "unknown"}, holder="worker-a", fence=lease["fence"], now="2026-01-01T00:00:01Z")
            self.assertEqual(waiting["status"], "WAITING_APPROVAL")
            self.assertEqual(waiting["waitpoint"]["kind"], "CI_JOB")
            self.assertEqual(waiting["cursor_version"], 1)
            resumed = ledger.clear_waitpoint("task-a", "worker-a", lease["fence"], now="2026-01-01T00:00:02Z")
            self.assertEqual(resumed["status"], "RUNNING")
            self.assertIsNone(resumed["waitpoint"])

    def test_budget_usage_blocks_after_token_time_or_tool_limit(self) -> None:
        module = load_module()
        with tempfile.TemporaryDirectory() as raw:
            ledger = module.TaskLedger(Path(raw) / ".hermes" / "task-runtime" / "task-ledger")
            ledger.create("task-a", "idem-a", token_budget=10, time_budget_seconds=5, tool_budget=2)
            ledger.record_usage("task-a", tokens=4, time_seconds=1, tools=1)
            result = ledger.record_usage("task-a", tokens=7, time_seconds=0, tools=0)
            self.assertEqual(result["status"], "BLOCKED")
            self.assertEqual(result["usage"]["tokens"], 11)

    def test_evidence_requires_state_source_and_content_hash(self) -> None:
        module = load_module()
        with tempfile.TemporaryDirectory() as raw:
            ledger = module.TaskLedger(Path(raw) / ".hermes" / "task-runtime" / "task-ledger")
            ledger.create("task-a", "idem-a")
            result = ledger.record_evidence("task-a", {
                "evidence_id": "e-1",
                "state": "PASS",
                "source": "local-test",
                "sha256": "a" * 64,
            })
            self.assertEqual(result["evidence"][0]["evidence_id"], "e-1")
            with self.assertRaisesRegex(ValueError, "sha256"):
                ledger.record_evidence("task-a", {
                    "evidence_id": "e-2", "state": "PASS", "source": "local-test", "sha256": "bad"
                })

    def test_external_effect_is_idempotent_and_requires_reconciliation(self) -> None:
        module = load_module()
        with tempfile.TemporaryDirectory() as raw:
            ledger = module.TaskLedger(Path(raw) / "ledger.json")
            ledger.create("task-a", "idem-a")
            effect = ledger.record_external_effect(
                "task-a", "effect-a", "remote-write", "intent-digest-a"
            )
            self.assertEqual(effect["status"], "PENDING")
            repeated = ledger.record_external_effect(
                "task-a", "effect-a", "remote-write", "intent-digest-a"
            )
            self.assertEqual(repeated, effect)
            failed = ledger.record_error(
                "task-a", "REMOTE_WRITE_CONFLICT", retryable=True, external_write=True
            )
            self.assertEqual(failed["status"], "FAILED")
            self.assertEqual(failed["retry_count"], 0)
            reconciled = ledger.reconcile_external_effect(
                "task-a", "effect-a", "CONFIRMED", "remote-digest-a"
            )
            self.assertEqual(reconciled["external_effects"][0]["status"], "CONFIRMED")

    def test_dependency_cycle_is_rejected(self) -> None:
        module = load_module()
        with tempfile.TemporaryDirectory() as raw:
            ledger = module.TaskLedger(Path(raw) / "ledger.json")
            ledger.create("task-a", "idem-a")
            ledger.create("task-b", "idem-b")
            ledger.set_dependencies("task-b", ["task-a"])
            with self.assertRaisesRegex(ValueError, "cycle"):
                ledger.set_dependencies("task-a", ["task-b"])

    def test_ready_tasks_returns_topologically_ready_queued_tasks(self) -> None:
        module = load_module()
        with tempfile.TemporaryDirectory() as raw:
            ledger = module.TaskLedger(Path(raw) / "ledger.json")
            ledger.create("leaf-1", "idem-l1")
            ledger.create("leaf-2", "idem-l2")
            ledger.create("mid", "idem-mid")
            ledger.create("root", "idem-root")
            ledger.set_dependencies("mid", ["leaf-1"])
            ledger.set_dependencies("root", ["mid"])
            # 无依赖的任务立即就绪
            self.assertEqual(sorted(ledger.ready_tasks()), ["leaf-1", "leaf-2"])
            # 完成 leaf-1 后 mid 就绪，但 root 仍阻塞（依赖 mid）
            for state in ("PLANNING", "RUNNING"):
                ledger.transition("leaf-1", state)
            ledger.transition("leaf-1", "COMPLETED")
            self.assertEqual(sorted(ledger.ready_tasks()), ["leaf-2", "mid"])
            # 完成全部依赖后 root 就绪
            for tid in ("leaf-2", "mid"):
                for state in ("PLANNING", "RUNNING"):
                    ledger.transition(tid, state)
                ledger.transition(tid, "COMPLETED")
            self.assertEqual(ledger.ready_tasks(), ["root"])
            # 非 QUEUED 任务不进入就绪集
            ledger.transition("root", "PLANNING")
            ledger.transition("root", "RUNNING")
            self.assertEqual(ledger.ready_tasks(), [])

    def test_child_fanout_is_bounded(self) -> None:
        module = load_module()
        with tempfile.TemporaryDirectory() as raw:
            ledger = module.TaskLedger(Path(raw) / "ledger.json")
            ledger.create("parent", "idem-parent")
            for index in range(module.MAX_CHILDREN):
                child_id = f"child-{index}"
                ledger.create(child_id, f"idem-{child_id}")
                ledger.attach_child("parent", child_id)
            ledger.create("overflow", "idem-overflow")
            with self.assertRaisesRegex(ValueError, "fan-out"):
                ledger.attach_child("parent", "overflow")

    def test_orphaned_atomic_write_is_recovered(self) -> None:
        module = load_module()
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            ledger_path = root / "ledger.json"
            payload = {"schema_version": "workflow/task-ledger/v1", "tasks": {}}
            temp_path = root / ".ledger.json.crash.tmp"
            root.mkdir(parents=True, exist_ok=True)
            temp_path.write_text(json.dumps(payload), encoding="utf-8")
            recovered = module.TaskLedger(root)
            recovered._ensure()
            self.assertTrue(ledger_path.is_file())
            self.assertFalse(temp_path.exists())

    def test_runtime_ledger_matches_task_ledger_schema(self) -> None:
        module = load_module()
        schema = json.loads((ROOT / "packages/contracts/schemas/workflow/task-ledger.schema.json").read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            ledger = module.TaskLedger(root)
            ledger.create("parent", "idem-parent")
            ledger.create("child", "idem-child")
            ledger.set_dependencies("child", ["parent"])
            ledger.attach_child("parent", "child")
            ledger.record_external_effect("parent", "effect-a", "remote-write", "intent-a")
            ledger.reconcile_external_effect("parent", "effect-a", "CONFIRMED", "remote-a")
            instance = json.loads((root / "ledger.json").read_text(encoding="utf-8"))
            errors = sorted(Draft202012Validator(schema).iter_errors(instance), key=lambda item: list(item.path))
            self.assertEqual(errors, [], errors)


if __name__ == "__main__":
    unittest.main()
