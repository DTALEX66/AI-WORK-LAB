"""Gate: a write made by another writer must reach the Observer as a NEW revision, not just new content.

The journey the product promises ends with "Observer sees the same task at a new revision". Content
visibility and revision advancement are different guarantees: a snapshot fetched between the write and
the watcher's next tick shows the record with the OLD revision, which is exactly what an early read
looks like. That mistake was made with an ad-hoc probe and reported as a product gap, so this gate now
holds the two apart on every run.

Shape: one project-local runtime root, a real ``WorkflowSidecar`` with live updates, and a SECOND
``CanonicalStore`` connection standing in for the Control service (the sidecar's watcher is designed for
deltas written by a separate writer). Evidence level: SYNTHETIC/INTEGRATED locally — it is not native
executor evidence and is not claimed as such.

Discovered dynamically by ``run_quality_gate.py governance``.
"""
from __future__ import annotations

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
from canonical_store import CanonicalStore  # noqa: E402
from project_temp import fixture_dir  # noqa: E402


class CrossProcessRevisionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.runtime = fixture_dir(prefix="sidecar-revision-")
        self.sidecar = sidecar_module.WorkflowSidecar(ROOT, self.runtime)

    def tearDown(self) -> None:
        self.sidecar.stop_live_updates()
        self.sidecar.close()

    def _await_revision(self, floor: int, timeout: float = 20.0) -> int:
        deadline = time.time() + timeout
        while time.time() < deadline:
            revision = self.sidecar.v3_snapshot()["revision"]
            if revision > floor:
                return revision
            time.sleep(0.2)
        self.fail(f"revision stayed at {floor} for {timeout}s after a committed cross-connection write")

    def test_a_write_on_a_second_connection_advances_the_observer_revision(self) -> None:
        self.sidecar.start_live_updates(interval_seconds=0.2)
        baseline = self.sidecar.v3_snapshot()["revision"]

        writer = CanonicalStore(self.runtime / "canonical.sqlite")
        try:
            writer.upsert_task({"task_id": "WL-REVISION-GATE", "project_id": "work-lab", "status": "QUEUED"})
        finally:
            writer.close()

        advanced = self._await_revision(baseline)
        snapshot = self.sidecar.v3_snapshot()
        self.assertGreater(advanced, baseline)
        records = [record["taskId"] for record in snapshot.get("taskRecords") or []]
        self.assertIn("WL-REVISION-GATE", records,
                      "the revision moved but the new Work Unit is not in the projection")
        self.assertEqual(snapshot["transport"]["freshnessState"], "FRESH",
                         "a published revision must mark the projection freshly written, not stale")

    def test_the_revision_is_monotonic_across_successive_writes(self) -> None:
        """A restart must not hand out a lower cursor than a client already saw (SSE resumes by cursor)."""
        self.sidecar.start_live_updates(interval_seconds=0.2)
        first = self.sidecar.v3_snapshot()["revision"]
        writer = CanonicalStore(self.runtime / "canonical.sqlite")
        try:
            writer.upsert_task({"task_id": "WL-REV-A", "project_id": "work-lab", "status": "QUEUED"})
        finally:
            writer.close()
        second = self._await_revision(first)

        self.sidecar.stop_live_updates()
        self.sidecar.close()

        restarted = sidecar_module.WorkflowSidecar(ROOT, self.runtime)
        self.addCleanup(restarted.close)
        seeded = restarted.v3_snapshot()["revision"]
        self.assertGreaterEqual(seeded, second,
                                "a restarted sidecar seeded a cursor BELOW one already published")
