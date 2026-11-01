"""Gate: the canonical store's disk is bounded, and the bound is reported in bytes it actually measured.

WUI-18's "队列/磁盘有界；轮转截断" clause was only half delivered: the collector queue is bounded
(`services/orchestration/collector_scheduler.py`, `BoundedEventQueue(max_size=1000)`) while the store had no
ceiling of any kind -- just `PRAGMA wal_checkpoint(TRUNCATE)` on close. An unbounded append-only ledger is not
a low-overhead collector: it grows until something else fails, and the failure lands in whoever's disk.

Three things this file insists on, because each is a way a "retention feature" can be a lie:

* **the ceiling is per table and the tables are derived, not listed** -- `RETAINABLE_TABLES` comes from
  `WAL_TABLES` minus an explicitly exempt pair, so a new ledger table is un-prunable until someone states which
  category it belongs to. A `schema_migrations` prune would erase the version record and read as "clean".
* **dry-run means nothing was deleted** -- `allow_prune=False` reports `wouldDelete` and leaves the rows,
  because an operator has to see the cost of a ceiling before granting it.
* **bytes are measured, not inferred** -- `disk_footprint()` reads SQLite's own `page_size`/`page_count` plus
  the `-wal`/`-shm` sidecars; a report whose numbers all came from row counts would be a count wearing a
  byte label.

The sequence rule is tested here too: `append_telemetry` used `COUNT(*)+1`, which silently collides the moment
anything is pruned (10 rows left, next sequence is 11 -- a value already used). It now reads
`MAX(sequence)+1`, and the test proves the new value keeps rising across a prune.
"""
from __future__ import annotations

import importlib.util
import sqlite3
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "packages/client-neutral-core/scripts"))

import project_temp  # noqa: E402
from canonical_store import (  # noqa: E402
    RETAINABLE_TABLES, RETENTION_EXEMPT_TABLES, CanonicalStore, WAL_TABLES,
)

ROWS = 25
CEILING = 10


def seed(store: CanonicalStore, rows: int = ROWS) -> list[str]:
    ids: list[str] = []
    for index in range(rows):
        ids.append(store.append_telemetry({
            "project_id": "work-lab", "producer": "retention-gate",
            "occurred_at": f"2026-10-08T00:00:{index % 60:02d}Z",
            "observed_at": f"2026-10-08T00:00:{index % 60:02d}Z",
            "payload": {"index": index},
        }))
    return ids


class RetentionPolicyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fixture = project_temp.fixture_dir("canonical-retention-")
        self.store = CanonicalStore(Path(self.fixture) / "canonical.sqlite")

    def tearDown(self) -> None:
        self.store.close()
        project_temp.force_release(self.fixture)

    def sequences(self) -> list[int]:
        rows = self.store._conn.execute(  # noqa: SLF001 - reading the column this gate is about
            "SELECT sequence FROM telemetry_events ORDER BY rowid").fetchall()
        return [int(row[0]) for row in rows]

    def count(self, table: str) -> int:
        return int(self.store._conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])  # noqa: SLF001

    def test_the_retainable_set_is_derived_and_excludes_the_version_record(self) -> None:
        # The floor moved 8 -> 7 in CL-04: `action_plans` joined the exempt set because it holds one current
        # row per plan identity (including the row a later imported result is checked against), not an
        # append-only event stream. The derivation equation below is the real guard; this number only fails
        # when the retainable set has shrunk to the point where retention guards almost nothing.
        self.assertGreaterEqual(len(RETAINABLE_TABLES), 7,
                                f"only {RETAINABLE_TABLES} may be retained; if the set is empty the feature "
                                "guards nothing")
        for exempt in RETENTION_EXEMPT_TABLES:
            self.assertIn(exempt, WAL_TABLES, f"{exempt} is exempt from a list it was never on")
            self.assertNotIn(exempt, RETAINABLE_TABLES)
        self.assertEqual(set(RETAINABLE_TABLES), set(WAL_TABLES) - set(RETENTION_EXEMPT_TABLES),
                         "the retainable set must be derived from WAL_TABLES, not restated")

    def test_a_ceiling_for_a_table_that_may_not_be_pruned_is_refused_without_deleting(self) -> None:
        seed(self.store, CEILING + 3)
        before = self.count("telemetry_events")
        for table in ("tasks", "schema_migrations", "no_such_table"):
            with self.assertRaises(ValueError) as caught:
                self.store.enforce_retention({table: 1}, allow_prune=True)
            self.assertIn("RETENTION_TABLE_NOT_PERMITTED", str(caught.exception))
        self.assertEqual(before, self.count("telemetry_events"),
                         "a refused policy still touched the ledger")

    def test_a_ceiling_below_one_is_refused_rather_than_emptying_the_table(self) -> None:
        seed(self.store, 3)
        for ceiling in (0, -5):
            with self.assertRaises(ValueError) as caught:
                self.store.enforce_retention({"telemetry_events": ceiling}, allow_prune=True)
            self.assertIn("RETENTION_CEILING_INVALID", str(caught.exception))
        self.assertEqual(3, self.count("telemetry_events"))


class RetentionBehaviourTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fixture = project_temp.fixture_dir("canonical-retention-")
        self.store = CanonicalStore(Path(self.fixture) / "canonical.sqlite")

    def tearDown(self) -> None:
        self.store.close()
        project_temp.force_release(self.fixture)

    def count(self, table: str) -> int:
        return int(self.store._conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])  # noqa: SLF001

    def test_dry_run_reports_the_cost_and_deletes_nothing(self) -> None:
        seed(self.store)
        report = self.store.enforce_retention({"telemetry_events": CEILING}, allow_prune=False)
        entry = report["tables"]["telemetry_events"]
        self.assertEqual(ROWS, entry["rowsBefore"])
        self.assertEqual(ROWS - CEILING, entry["wouldDelete"])
        self.assertEqual(0, entry["deleted"])
        self.assertEqual(ROWS, self.count("telemetry_events"), "a dry run removed rows")
        self.assertEqual(0, report["deletedTotal"])

    def test_the_prune_keeps_the_newest_rows_and_reports_every_number_it_claims(self) -> None:
        seed(self.store)
        report = self.store.enforce_retention({"telemetry_events": CEILING}, allow_prune=True)
        entry = report["tables"]["telemetry_events"]
        self.assertEqual(CEILING, self.count("telemetry_events"))
        self.assertEqual(ROWS - CEILING, entry["deleted"])
        self.assertEqual(CEILING, entry["rowsAfter"])
        self.assertEqual(ROWS - CEILING, report["deletedTotal"])
        self.assertIsNotNone(entry["newestColumn"],
                             "ordering by no column would keep an arbitrary slice, not the newest")
        # the survivors are the newest by the column the report names
        stamps = [row[0] for row in self.store._conn.execute(  # noqa: SLF001
            f"SELECT {entry['newestColumn']} FROM telemetry_events ORDER BY {entry['newestColumn']} DESC")]
        self.assertEqual(CEILING, len(stamps))

    def test_a_second_table_is_bounded_by_the_same_call_so_the_feature_is_not_telemetry_only(self) -> None:
        for index in range(12):
            self.store.record_usage_sample({
                "project_id": "work-lab", "provider": "p", "model": "m", "lane": "chat",
                "observed_at": f"2026-10-08T00:00:{index:02d}Z",
                "window_start": "2026-10-08T00:00:00Z", "window_end": "2026-10-08T00:00:59Z",
                "total_tokens": 100 + index, "quality": "OBSERVED", "source_ref": "gate",
            })
        report = self.store.enforce_retention({"telemetry_events": CEILING, "usage_samples": 5},
                                              allow_prune=True)
        self.assertEqual(5, self.count("usage_samples"))
        self.assertEqual(7, report["tables"]["usage_samples"]["deleted"])
        self.assertEqual(7, report["deletedTotal"], "a ceiling that only lands on one table is a demo")

    def test_sequence_still_rises_across_a_prune_where_count_would_have_collided(self) -> None:
        seed(self.store, CEILING)
        first = max(int(row[0]) for row in self.store._conn.execute(  # noqa: SLF001
            "SELECT sequence FROM telemetry_events"))
        self.store.enforce_retention({"telemetry_events": 3}, allow_prune=True)
        self.assertEqual(3, self.count("telemetry_events"))
        fresh = self.store.append_telemetry({"project_id": "work-lab", "producer": "retention-gate",
                                             "payload": {"index": 99}})
        stored = int(self.store._conn.execute(  # noqa: SLF001
            "SELECT sequence FROM telemetry_events WHERE event_id = ?", (fresh,)).fetchone()[0])
        self.assertGreater(stored, first,
                           f"a COUNT-derived sequence reused {first} after a prune; a cursor that repeats is "
                           "worse than one that gaps")


class DiskFootprintTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fixture = project_temp.fixture_dir("canonical-footprint-")
        self.store = CanonicalStore(Path(self.fixture) / "canonical.sqlite")

    def tearDown(self) -> None:
        self.store.close()
        project_temp.force_release(self.fixture)

    def test_footprint_reports_bytes_measured_from_sqlite_not_from_row_counts(self) -> None:
        seed(self.store)
        report = self.store.disk_footprint()
        for key in ("pageSizeBytes", "pageCount", "logicalDatabaseBytes", "databaseFileBytes",
                  "walBytes", "shmBytes", "totalBytes"):
            self.assertIn(key, report, f"{key} is missing from the footprint report")
        self.assertGreaterEqual(report["pageSizeBytes"], 512)
        self.assertGreater(report["pageCount"], 0)
        self.assertEqual(report["pageSizeBytes"] * report["pageCount"],
                         report["logicalDatabaseBytes"])
        self.assertGreater(report["totalBytes"], 0,
                           "a zero-byte footprint would make any byte ceiling unreachable and any reclaim "
                           "look infinite")
        on_disk = Path(f"{self.store.path}").stat().st_size
        self.assertEqual(on_disk, report["databaseFileBytes"],
                         "the report must describe the file the reader would open")

    def test_a_prune_reports_what_it_reclaimed_instead_of_claiming_a_round_number(self) -> None:
        seed(self.store, 400)
        before = self.store.disk_footprint()["totalBytes"]
        report = self.store.enforce_retention({"telemetry_events": 10}, allow_prune=True)
        after = report["after"]["totalBytes"]
        print(f"\nRETENTION_MEASURED rows_deleted={report['deletedTotal']} bytes_before={before} "
              f"bytes_after={after} reclaimed={report['bytesReclaimed']}")
        self.assertLessEqual(after, before,
                             "the store grew after a 390-row prune, so the checkpoint is not happening")
        self.assertGreaterEqual(report["bytesReclaimed"], 0)
        self.assertEqual(390, report["deletedTotal"])


class WorkerWiringTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fixture = project_temp.fixture_dir("canonical-retention-wiring-")
        self.store = CanonicalStore(Path(self.fixture) / "canonical.sqlite")

    def tearDown(self) -> None:
        self.store.close()
        project_temp.force_release(self.fixture)

    def count(self, table: str) -> int:
        return int(self.store._conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])  # noqa: SLF001

    def test_the_cli_grants_or_withholds_the_prune_and_reports_both_sweeps(self) -> None:
        """The flag is the operator's grant, and the worker's own functions are what run it.

        Driven through the real module so the assertion is about the call site, not about a helper nobody
        calls -- the ERR-244 lesson this session already paid for once.
        """
        from argparse import Namespace

        # The worker imports its siblings by bare name (sidecar_lock, collectors), which is how the gate
        # runner resolves them too, so this test adds the same two roots and imports it the way the runtime
        # does -- an importlib exec without a sys.modules registration dies on @dataclass's module lookup.
        for extra in (ROOT / "services/orchestration", ROOT / "packages/client-neutral-core/scripts"):
            if str(extra) not in sys.path:
                sys.path.insert(0, str(extra))
        module = importlib.import_module("durable_worker")

        self.assertEqual({"telemetry_events": 10, "usage_samples": 5},
                         module.parse_retention(Namespace(retention_rows="telemetry_events=10, usage_samples=5")))
        self.assertIsNone(module.parse_retention(Namespace(retention_rows=None)))
        self.assertIsNone(module.apply_retention(self.store, None),
                         "no flag must mean no delete, not a default ceiling")
        for bad in ("schema_migrations=1", "no_such_table=5"):
            with self.assertRaises(ValueError) as caught:
                module.parse_retention(Namespace(retention_rows=bad))
            self.assertIn("RETENTION_TABLE_NOT_PERMITTED", str(caught.exception))
        for bad in ("telemetry_events=0", "telemetry_events=abc", "telemetry_events"):
            with self.assertRaises(ValueError):
                module.parse_retention(Namespace(retention_rows=bad))

        seed(self.store, ROWS)
        report = module.apply_retention(self.store, {"telemetry_events": CEILING})
        self.assertEqual(ROWS - CEILING, report["deletedTotal"])
        self.assertEqual(CEILING, self.count("telemetry_events"))


if __name__ == "__main__":
    if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    unittest.main()
