"""Mandatory gate: the per-collector delivery/refusal fact reaches the snapshot, and cannot be laundered on the way.

ERR-256 made `refused_rows` durable; this proves it is reachable. The point of the section is a combination the
previous surfaces could not express: a collector can be **fresh** (it ran, it succeeded, its breaker is closed)
*and* have refused rows. Coverage alone reads that collector as healthy and the reader never learns a source is
being refused — which is why `_collector_coverage` deliberately still answers only the liveness question and this
section carries the delivery question separately.

`circuit_open_until` is a `time.monotonic()` value read in another process, so it is projected as a boolean and
never as a number: a reader that sees "1749.3" cannot tell whether that is a deadline, an age, or nonsense.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "packages" / "client-neutral-core" / "scripts"))
sys.path.insert(0, str(ROOT / "services" / "orchestration"))

import project_temp  # noqa: E402
from canonical_store import CanonicalStore  # noqa: E402
from composition_root import _collector_coverage, _collector_delivery_rows, _collector_is_fresh  # noqa: E402
from snapshot_api import build_snapshot  # noqa: E402


class RecordingStore:
    """Delegates health reads so the unreadable-source branch is reachable without breaking the store."""

    def __init__(self, rows=None, *, fail=False) -> None:
        self.rows = rows if rows is not None else []
        self.fail = fail

    def list_collector_health(self):
        if self.fail:
            raise RuntimeError("database is locked")
        return [dict(row) for row in self.rows]

    def max_watermark(self):
        return None


class CollectorDeliveryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fixture = project_temp.fixture_dir("collector-delivery-")
        self.store = CanonicalStore(self.fixture / "canonical.sqlite")

    def tearDown(self) -> None:
        self.store.close()
        project_temp.force_release(self.fixture)

    def test_rows_carry_delivery_and_refusal_side_by_side(self) -> None:
        self.store.upsert_collector_health({"name": "usage-files", "totalRuns": 5,
                                           "lastRunAt": "2026-10-10T00:00:00Z",
                                           "lastSuccessAt": "2026-10-10T00:00:00Z",
                                           "consecutiveFailures": 0, "circuitOpenUntil": None,
                                           "droppedCount": 2, "refusedRows": 7,
                                           "lastRefusalReason": "7 row(s) refused, most frequent reason: "
                                                                "ValueError: forbidden sensitive field(s) "
                                                                "(first seen at usage.jsonl:4)"})
        rows = _collector_delivery_rows(self.store)
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["collector"], "usage-files")
        self.assertEqual(row["refusedRows"], 7)
        self.assertEqual(row["droppedEvents"], 2, "queue drops and refused rows are different faults")
        self.assertEqual(row["totalRuns"], 5)
        self.assertTrue(row["fresh"], "it did run successfully — the refusals do not make it stale")
        self.assertFalse(row["circuitOpen"])
        self.assertIn("usage.jsonl:4", row["lastRefusalReason"],
                      "the reason must still name where the first refusal happened")
        self.assertNotIn("circuitOpenUntil", row)

    def test_the_fresh_flag_and_the_coverage_numerator_use_one_predicate(self) -> None:
        self.store.upsert_collector_health({"name": "ok", "totalRuns": 1, "lastRunAt": "2026-10-10T00:00:00Z",
                                           "lastSuccessAt": "2026-10-10T00:00:00Z", "consecutiveFailures": 0,
                                           "circuitOpenUntil": None})
        self.store.upsert_collector_health({"name": "failing", "totalRuns": 3, "lastRunAt": "x",
                                           "lastSuccessAt": "y", "consecutiveFailures": 2})
        self.store.upsert_collector_health({"name": "breaker-open", "totalRuns": 4,
                                           "lastRunAt": "x", "lastSuccessAt": "y", "consecutiveFailures": 0,
                                           "circuitOpenUntil": 1749.3})
        coverage = _collector_coverage(self.store)
        rows = {row["collector"]: row for row in _collector_delivery_rows(self.store)}
        self.assertEqual(coverage["numerator"], 1)
        self.assertEqual(coverage["denominator"], 3)
        self.assertEqual({name: row["fresh"] for name, row in rows.items()},
                         {"ok": True, "failing": False, "breaker-open": False},
                         "a collector cannot be fresh in one lane and stale in another")
        self.assertTrue(rows["breaker-open"]["circuitOpen"])
        self.assertEqual(rows["breaker-open"]["consecutiveFailures"], 0)
        for row in rows.values():
            self.assertEqual(row["fresh"], _collector_is_fresh(self.store_row(row["collector"])))

    def store_row(self, name: str) -> dict:
        return next(r for r in self.store.list_collector_health() if r["name"] == name)

    def test_a_health_read_that_fails_produces_no_section_rather_than_an_empty_one(self) -> None:
        self.assertIsNone(_collector_delivery_rows(RecordingStore(fail=True)),
                          "an unreadable health table must read as a source gap, not as \"no collectors\"")
        payload = build_snapshot(revision=3,
                                 collector_delivery=_collector_delivery_rows(RecordingStore(fail=True)))
        self.assertNotIn("collectors", payload)

    def test_a_read_with_no_registered_collectors_is_an_explicit_empty_list(self) -> None:
        rows = _collector_delivery_rows(RecordingStore(rows=[]))
        self.assertEqual(rows, [])
        payload = build_snapshot(revision=4, collector_delivery=rows)
        self.assertEqual(payload["collectors"], [],
                         "empty-list must be expressible, or the surface cannot say 'read, none registered'")

    def test_a_null_timestamp_stays_null_and_is_not_invented(self) -> None:
        rows = _collector_delivery_rows(RecordingStore(rows=[{"name": "cold", "total_runs": 0}]))
        self.assertEqual(rows[0]["lastRunAt"], None)
        self.assertEqual(rows[0]["lastSuccessAt"], None)
        self.assertEqual(rows[0]["refusedRows"], 0, "0 here is a measured empty, not a padded unknown")
        self.assertEqual(rows[0]["lastRefusalReason"], None)
        self.assertFalse(rows[0]["fresh"])

    def test_unknown_row_fields_do_not_become_new_facts(self) -> None:
        rows = _collector_delivery_rows(RecordingStore(rows=[{"name": "x", "total_runs": 1,
                                                              "mystery_column": "hello"}]))
        self.assertNotIn("mystery_column", rows[0],
                         "the projection names what it emits; a new column must arrive as a decision")


if __name__ == "__main__":
    unittest.main(verbosity=2)
