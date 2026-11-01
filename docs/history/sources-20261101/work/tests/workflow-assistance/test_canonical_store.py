"""Contract tests for the canonical SQLite WAL store (WL3-500)."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from canonical_store import CanonicalStore, validate_record


class CanonicalStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temporary = tempfile.TemporaryDirectory()
        self.store = CanonicalStore(Path(self._temporary.name) / "canonical.sqlite")

    def tearDown(self) -> None:
        self.store.close()
        self._temporary.cleanup()

    def test_schema_migration_and_tables(self) -> None:
        projection = self.store.projection()
        self.assertEqual(projection["integrity"], "ok")
        for table in (
            "projects", "tasks", "task_events", "telemetry_events",
            "usage_samples", "ci_runs", "source_quality", "action_plans",
            "solutions", "growth_candidates", "schema_migrations",
        ):
            self.assertIn(table, projection["tables"])

    def test_project_registration_and_readback(self) -> None:
        # T11: use a tmp workspace root, never a machine-fixed path
        with tempfile.TemporaryDirectory() as tmp:
            self.store.register_project("work-lab", tmp)
        projects = self.store.list_projects()
        self.assertEqual(len(projects), 1)
        self.assertEqual(projects[0]["project_id"], "work-lab")

    def test_legal_usage_token_fields_accepted(self) -> None:
        sample_id = self.store.record_usage_sample(
            {
                "project_id": "work-lab",
                "provider": "deepseek",
                "model": "deepseek-v4-flash",
                "input_tokens": 100,
                "output_tokens": 50,
                "total_tokens": 150,
                "quality": "EXACT_SOURCE",
            }
        )
        self.assertTrue(sample_id)
        projection = self.store.projection()
        self.assertEqual(projection["usage_summary"][0]["tokens"], 150)

    def test_auth_token_fields_rejected_even_in_nested_keys(self) -> None:
        with self.assertRaises(ValueError):
            validate_record(
                {"project_id": "x", "credentials": {"api_key": "secret"}},
                allow_usage_tokens=True,
            )
        with self.assertRaises(ValueError):
            validate_record(
                {"project_id": "x", "prompt": "full prompt body"},
                allow_usage_tokens=True,
            )

    def test_ci_run_upsert_is_idempotent(self) -> None:
        run = {
            "run_id": "31344245919",
            "project_id": "work-lab",
            "workflow": "work-lab-gate",
            "head_sha": "699ab50f47da5dcf3e92c81bea72504b6425f475",
            "status": "completed",
            "conclusion": "success",
            "jobs": [{"name": "aggregate", "conclusion": "success"}],
        }
        self.store.record_ci_run(run)
        run["conclusion"] = "failure"
        self.store.record_ci_run(run)
        projection = self.store.projection()
        self.assertEqual(projection["ci_summary"][0]["n"], 1)

    def test_lease_fencing_and_zombie_recovery(self) -> None:
        self.store.upsert_task(
            {
                "task_id": "WL3-410-test",
                "project_id": "work-lab",
                "status": "RUNNING",
            }
        )
        self.assertTrue(self.store.acquire_lease("WL3-410-test", "writer-a", ttl_seconds=60))
        # A different holder cannot acquire while lease is live.
        self.assertFalse(self.store.acquire_lease("WL3-410-test", "writer-b", ttl_seconds=60))
        self.assertTrue(self.store.heartbeat("WL3-410-test", "writer-a"))
        self.assertFalse(self.store.heartbeat("WL3-410-test", "writer-b"))
        # Force the live lease to expire, then writer-b may take over (fencing).
        self.store._conn.execute(
            "UPDATE tasks SET lease_expires_at=? WHERE task_id=?",
            ("2000-01-01T00:00:00Z", "WL3-410-test"),
        )
        self.store._conn.commit()
        self.assertTrue(self.store.acquire_lease("WL3-410-test", "writer-b", ttl_seconds=60))
        self.assertTrue(self.store.release_lease("WL3-410-test", "writer-b"))

    def test_claim_expired_reclaims_stale_leases(self) -> None:
        self.store.upsert_task({"task_id": "t1", "project_id": "p", "status": "RUNNING"})
        self.store.acquire_lease("t1", "dead-writer", ttl_seconds=-30)
        claimed = self.store.claim_expired_tasks("recovery-writer", ttl_seconds=0)
        self.assertIn("t1", claimed)
        self.assertTrue(self.store.heartbeat("t1", "recovery-writer"))


if __name__ == "__main__":
    unittest.main()
