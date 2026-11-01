"""Gate: a lease taken on an existing task must reach the Observer, not just a task that appears.

The live watcher decided "changed" from row counts, status tallies and aggregates. A lease acquisition
changes none of those: it rewrites `lease_holder`, bumps `fencing_token` and moves `lease_expires_at` on a
row that already exists. Measured before this gate existed, writing a checkpoint, holder and fencing token
onto a live task left the sidecar's canonical fingerprint byte-identical (`fingerprint_changed=False`,
`differing_keys=[]`), so a desktop user watched a run they believed was queued.

An earlier revision of the fix also gated the whole content read behind `PRAGMA data_version`, and three
deliberate guards in `test_sidecar_v3_snapshot.py` went red: a watcher that only reads when some other
connection commits cannot prove that its readback works, cannot notice its own failure to publish, and
cannot be seen entering the read it is supposed to block in. That optimisation was measured as unnecessary
cost and has been removed; the witness below is the fix.

Evidence level: SYNTHETIC/INTEGRATED locally (two `CanonicalStore` connections on one runtime root), not
native executor evidence.
"""
from __future__ import annotations

import json
import sys
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for entry in (ROOT / "services" / "orchestration", ROOT / "services" / "authority",
              ROOT / "services" / "policy", ROOT / "services" / "receipts",
              ROOT / "packages" / "client-neutral-core" / "scripts"):
    sys.path.insert(0, str(entry))

import sidecar as sidecar_module  # noqa: E402
import canonical_store as canonical_store_module  # noqa: E402
from canonical_store import CanonicalStore  # noqa: E402
from project_temp import fixture_dir  # noqa: E402

TASK = "WL-LEASE-VISIBLE"


class InPlaceUpdateReachesTheObserver(unittest.TestCase):
    def setUp(self) -> None:
        self.runtime = fixture_dir(prefix="sidecar-inplace-")
        self.sidecar = sidecar_module.WorkflowSidecar(ROOT, self.runtime)
        self.db = self.runtime / "canonical.sqlite"

    def tearDown(self) -> None:
        self.sidecar.stop_live_updates()
        self.sidecar.close()

    def _write_from_elsewhere(self, action) -> None:
        writer = CanonicalStore(self.db)
        try:
            action(writer)
        finally:
            writer.close()

    def _revision(self) -> int:
        return self.sidecar.v3_snapshot()["revision"]

    def _await_revision(self, floor: int, timeout: float = 20.0) -> int:
        deadline = time.time() + timeout
        while time.time() < deadline:
            revision = self._revision()
            if revision > floor:
                return revision
            time.sleep(0.2)
        self.fail(f"revision stayed at {floor} for {timeout}s; an in-place write is invisible to the watch")

    def test_a_lease_acquired_on_an_existing_task_advances_the_revision(self) -> None:
        self.sidecar.start_live_updates(interval_seconds=0.2)
        baseline = self._revision()
        self._write_from_elsewhere(lambda store: store.upsert_task(
            {"task_id": TASK, "project_id": "work-lab", "status": "QUEUED"}))
        appeared = self._await_revision(baseline)

        self._write_from_elsewhere(lambda store: store.acquire_lease(TASK, "worker-A"))

        moved = self._await_revision(appeared)
        self.assertGreater(moved, appeared)
        taken = next(task for task in self.sidecar.store.list_tasks() if task["task_id"] == TASK)
        self.assertEqual("worker-A", taken["lease_holder"],
                         "the revision moved without the lease actually being stored")
        self.assertGreaterEqual(int(taken["fencing_token"] or 0), 1)

    def test_a_lease_released_on_an_existing_task_advances_the_revision(self) -> None:
        """Releasing is the same class of change and was equally invisible."""
        self._write_from_elsewhere(lambda store: store.upsert_task(
            {"task_id": TASK, "project_id": "work-lab", "status": "QUEUED"}))
        self.sidecar.start_live_updates(interval_seconds=0.2)
        seen = self._await_revision(self._revision() - 1)
        self._write_from_elsewhere(lambda store: store.release_lease(TASK, "nobody"))
        self._write_from_elsewhere(lambda store: store.acquire_lease(TASK, "worker-B"))
        held = self._await_revision(seen)
        self._write_from_elsewhere(lambda store: store.release_lease(TASK, "worker-B"))
        released = self._await_revision(held)
        self.assertGreater(released, held)
        row = next(task for task in self.sidecar.store.list_tasks() if task["task_id"] == TASK)
        self.assertIsNone(row["lease_holder"])

    def test_the_witness_sees_an_update_that_changes_no_count_and_no_status(self) -> None:
        """Unit level: the fingerprint itself, with no thread and no timing in the way."""
        self.sidecar.store.upsert_task({"task_id": TASK, "project_id": "work-lab", "status": "QUEUED"})
        before = json.loads(self.sidecar._canonical_fingerprint())
        self.sidecar.store.acquire_lease(TASK, "worker-B")
        after = json.loads(self.sidecar._canonical_fingerprint())
        self.assertEqual(before["tables"], after["tables"],
                         "row counts moved; this is not the case the witness exists for")
        self.assertEqual(before["tasks_by_status"], after["tasks_by_status"])
        self.assertNotEqual(before["newest"], after["newest"],
                            "an in-place update must move the newest-changes witness")

    def _await_next_tick(self, timeout: float = 1.0) -> None:
        """The host clock moves in ~1 ms steps here, so wait for a tick instead of asserting on it."""
        started = canonical_store_module._now()
        deadline = time.time() + timeout
        while canonical_store_module._now() == started:
            if time.time() > deadline:
                self.fail(f"_now() did not advance within {timeout}s; the clock itself is stuck")
            time.sleep(0.0002)

    def test_a_renewal_that_moves_the_expiry_moves_the_witness(self) -> None:
        """A heartbeat in a later clock tick changes lease_expires_at, and the witness must notice."""
        self.sidecar.store.upsert_task({"task_id": TASK, "project_id": "work-lab", "status": "QUEUED"})
        self.sidecar.store.acquire_lease(TASK, "worker-C", ttl_seconds=30)
        before = json.loads(self.sidecar._canonical_fingerprint())["newest"]
        self._await_next_tick()
        self.assertTrue(self.sidecar.store.heartbeat(TASK, "worker-C", ttl_seconds=30))
        after = json.loads(self.sidecar._canonical_fingerprint())["newest"]
        self.assertNotEqual(before, after,
                            "the lease expiry and updated_at moved and no witness noticed")

    def test_a_renewal_is_witnessed_by_the_expiry_even_when_the_timestamp_is_not(self) -> None:
        """Pinned because this host's `_now()` returned one value across 2000 back-to-back calls.

        The first version of the renewal test compared `before` and `after` with no clock movement of its
        own and went red at 9fb20f24 in the full batch while passing standalone: acquire and heartbeat had
        written byte-identical values. The witness has to key on the thing a renewal actually changes --
        the expiry -- not only on the column that happens to be stamped in the same statement. Here the
        store's timestamp is frozen before the lease is taken, so the only thing the renewal can move is
        `lease_expires_at`, and the witness must still see it.
        """
        frozen = "2026-10-08T00:00:00.000000Z"
        original = canonical_store_module._now
        try:
            canonical_store_module._now = lambda: frozen
            self.sidecar.store.upsert_task({"task_id": TASK, "project_id": "work-lab", "status": "QUEUED"})
            self.sidecar.store.acquire_lease(TASK, "worker-C", ttl_seconds=30)
            before = json.loads(self.sidecar._canonical_fingerprint())["newest"]
            time.sleep(0.01)  # the expiry is computed from the real clock; one granularity step is enough
            self.assertTrue(self.sidecar.store.heartbeat(TASK, "worker-C", ttl_seconds=30))
        finally:
            canonical_store_module._now = original
        row = self.sidecar.store._conn.execute(
            "SELECT lease_expires_at, updated_at FROM tasks WHERE task_id=?", (TASK,)).fetchone()
        self.assertEqual(frozen, row["updated_at"],
                         "the frozen clock did not reach the write, so this case proves nothing")
        after = json.loads(self.sidecar._canonical_fingerprint())["newest"]
        self.assertEqual(before["tasks_state"][:5], after["tasks_state"][:5],
                         "something other than the expiry moved; the frozen clock did not hold")
        self.assertNotEqual(before, after,
                            "the expiry moved and the witness did not see it -- updated_at was the only "
                            "lease column in the witness")

    def test_the_witness_column_is_discovered_not_restatement(self) -> None:
        """A schema rename must not leave the witness silently watching nothing."""
        witness = self.sidecar.store.newest_changes()
        self.assertIn("tasks", witness)
        self.assertIn("tasks_state", witness)
        self.assertEqual(3, len(witness["tasks"]), "expected [count, max rowid, newest timestamp]")
        for table in ("projects", "telemetry_events", "schema_migrations"):
            self.assertIn(table, witness, f"{table} left the witness set")


if __name__ == "__main__":
    unittest.main()
