"""Mandatory gate: a refused ingest row is a named, counted fact — and one refused row no longer buries the batch.

WUI-18's poison-row clause asked a design question: the old behaviour let ONE bad row raise out of
`DurableWorker.run_once`, which marked the whole collector failed and dropped every row after it. That was
better than silent filtering — a raised error is visible and feeds the circuit breaker — but it made an honest
row collateral damage of a dishonest neighbour, and the canary gate already had to prove the opposite property
for a *planted secret* ("an honest line must not be collateral damage",
`test_canary_synthetic_secret_never_reaches_the_store.py:113`).

The answer implemented here is per-row isolation PLUS first-class refusal accounting:

  * the store refuses a row, the tick continues, and the refusal is counted and attributed by reason;
  * a collector whose every row was refused is NOT healthy — the source did not get through;
  * refusals accumulate in `collector_health.refused_rows` instead of describing one tick, so a clean tick
    cannot launder the debt;
  * `upsert_collector_health` writes only the fields its caller named, because the scheduler and the worker
    are two authors of one row and a whole-row write from either resets the other's column to a default —
    an unwritten field becoming "0" is the same lie as padding an unknown;
  * the collectors' own line-level `continue`s (unparseable JSON, a line that is not an object, a line with
    no usable token fields, a candidate rejected by intake) are counted and located rather than omitted:
    the growth collector's comment literally used to say "quarantine implicitly by omission".
"""
from __future__ import annotations

import json
import unittest
from pathlib import Path

import project_temp
from canonical_store import CanonicalStore
from durable_worker import CollectorResult, DurableWorker, _first_reason_text

# Synthetic only, in the same shape the canary uses: sk- + 28 mixed-case alphanumerics. Nothing real is
# planted, and nothing here is read from a live credential.
POISON_KEY = "sk-" + "Zx9Qw7Er5Ty3Ui1Op0As2Df4Gh6J"


def usage_row(project_id: str, index: int, provider: str = "deepseek") -> dict:
    return {
        "project_id": project_id,
        "provider": provider,
        "model": "deepseek-v4-flash",
        "input_tokens": 100 + index,
        "output_tokens": 20 + index,
        "total_tokens": 120 + index,
        "quality": "EXACT_SOURCE",
        "source_ref": f".hermes/task-artifacts/usage-{index}.jsonl",
    }


def make_usage_collector(rows: list[dict], *, ok: bool = True, refusals: dict | None = None,
                         samples: dict | None = None):
    def collector(store: CanonicalStore, project_id: str) -> CollectorResult:
        return CollectorResult(kind="usage", ok=ok, records=[dict(r) for r in rows],
                               refusals=dict(refusals or {}), refusal_samples=dict(samples or {}))

    collector.collector_name = "usage-fixture"
    return collector


class PoisonRowIsolationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fixture = project_temp.fixture_dir("ingest-refusal-")
        self.store = CanonicalStore(self.fixture / "canonical.sqlite")

    def tearDown(self) -> None:
        self.store.close()
        project_temp.force_release(self.fixture)

    def health(self, name: str = "usage-fixture") -> dict:
        rows = {row["name"]: row for row in self.store.list_collector_health()}
        self.assertIn(name, rows, f"no health row for {name}: {list(rows)}")
        return rows[name]

    def test_one_refused_row_does_not_bury_the_rows_after_it(self) -> None:
        rows = [usage_row("work-lab", 1), usage_row("work-lab", 2, provider=POISON_KEY),
                usage_row("work-lab", 3), usage_row("work-lab", 4)]
        worker = DurableWorker(self.store, collectors=[make_usage_collector(rows)])
        result = worker.run_once()
        outcome = next(c for c in result["collectors"] if c["kind"] == "usage")
        self.assertEqual(outcome["stored"], 3, f"the poison row took honest rows down with it: {outcome}")
        self.assertEqual(outcome["refused"], 1)
        self.assertEqual(outcome["records"], 4, "the report must still say how many rows were offered")
        self.assertTrue(outcome["ok"], "three of four rows got through; the source did deliver")

    def test_a_refused_row_reaches_neither_the_store_nor_the_projection(self) -> None:
        rows = [usage_row("work-lab", 1), usage_row("work-lab", 2, provider=POISON_KEY)]
        DurableWorker(self.store, collectors=[make_usage_collector(rows)]).run_once()
        stored = json.dumps(self.store.list_usage_samples(), ensure_ascii=False)
        self.assertNotIn(POISON_KEY, stored)
        self.assertNotIn(POISON_KEY, json.dumps(self.store.projection(), ensure_ascii=False),
                         "the refused row survived somewhere the Observer can read")
        self.assertIn("usage-1", stored, "the honest row is missing")

    def test_the_refusal_reason_names_the_rule_and_the_first_place_it_happened(self) -> None:
        rows = [usage_row("work-lab", i, provider=POISON_KEY if i == 2 else "deepseek")
                for i in (1, 2, 3)]
        result = DurableWorker(self.store, collectors=[make_usage_collector(rows)]).run_once()
        outcome = next(c for c in result["collectors"] if c["kind"] == "usage")
        reasons = outcome["refusalReasons"]
        self.assertEqual(sum(reasons.values()), 1)
        reason = next(iter(reasons))
        self.assertIn("ValueError", reason)
        self.assertIn("sensitive", reason.lower(), f"an unattributable reason: {reason}")
        self.assertEqual(outcome["refusalSamples"][reason], ".hermes/task-artifacts/usage-2.jsonl",
                         "the sample must point at the row that was refused, not at any other")

    def test_a_collector_whose_rows_are_all_refused_is_not_reported_healthy(self) -> None:
        rows = [usage_row("work-lab", i, provider=POISON_KEY) for i in (1, 2)]
        result = DurableWorker(self.store, collectors=[make_usage_collector(rows)]).run_once()
        outcome = next(c for c in result["collectors"] if c["kind"] == "usage")
        self.assertEqual(outcome["stored"], 0)
        self.assertFalse(outcome["ok"],
                         "nothing reached the store, so the source did not get through")
        self.assertEqual(int(self.health()["consecutive_failures"]), 1,
                         "the failure must reach the breaker, not only the payload")

    def test_refusals_accumulate_and_a_clean_tick_does_not_launder_them(self) -> None:
        dirty = [usage_row("work-lab", 1), usage_row("work-lab", 2, provider=POISON_KEY),
                 usage_row("work-lab", 3, provider=POISON_KEY)]
        worker = DurableWorker(self.store, collectors=[make_usage_collector(dirty)])
        worker.run_once()
        self.assertEqual(int(self.health()["refused_rows"]), 2)
        reason_text = self.health()["last_refusal_reason"]
        self.assertIn("2 row(s) refused", str(reason_text))

        clean = DurableWorker(self.store, collectors=[make_usage_collector([usage_row("work-lab", 9)])])
        clean.run_once()
        self.assertEqual(int(self.health()["refused_rows"]), 2,
                         "a clean tick overwrote the refusal debt — the debt is cumulative, not per-tick")

    def test_a_collector_level_refusal_is_carried_into_the_same_count(self) -> None:
        # The collector already gave up on a line before it could become a record; that row must not be
        # invisible because the store never saw it.
        collector = make_usage_collector(
            [usage_row("work-lab", 1)],
            refusals={"line_unparseable_json": 2},
            samples={"line_unparseable_json": "usage.jsonl:7"},
        )
        result = DurableWorker(self.store, collectors=[collector]).run_once()
        outcome = next(c for c in result["collectors"] if c["kind"] == "usage")
        self.assertEqual(outcome["refused"], 2)
        self.assertEqual(int(self.health()["refused_rows"]), 2)
        self.assertIn("usage.jsonl:7", str(self.health()["last_refusal_reason"]))

    def test_an_unnamed_field_is_not_reset_by_another_author_of_the_same_row(self) -> None:
        """The scheduler writes queue drops and says nothing about ingest refusals."""
        self.store.upsert_collector_health({"name": "usage-fixture", "totalRuns": 1, "refusedRows": 5,
                                            "lastRefusalReason": "ValueError: sensitive value(s)",
                                            "consecutiveFailures": 0})
        self.store.upsert_collector_health({"name": "usage-fixture", "totalRuns": 2, "droppedCount": 3,
                                            "consecutiveFailures": 0})
        row = self.health()
        self.assertEqual(int(row["refused_rows"]), 5,
                         "a writer that never spoke about refusals reset the count — whole-row upsert is "
                         "how an unwritten field silently becomes zero")
        self.assertEqual(int(row["dropped_count"]), 3)
        self.assertEqual(int(row["total_runs"]), 2)
        self.assertEqual(row["last_refusal_reason"], "ValueError: sensitive value(s)")

    def test_an_explicit_none_closes_the_circuit_instead_of_leaving_it_open(self) -> None:
        self.store.upsert_collector_health({"name": "usage-fixture", "totalRuns": 1,
                                            "circuitOpenUntil": 123.5})
        self.assertEqual(float(self.health()["circuit_open_until"]), 123.5)
        self.store.upsert_collector_health({"name": "usage-fixture", "totalRuns": 2,
                                            "circuitOpenUntil": None})
        self.assertIsNone(self.health()["circuit_open_until"],
                          "naming a field as None must clear it, or a closed breaker can never be stored")

    def test_the_reason_sentence_names_every_cause_with_its_count_and_place(self) -> None:
        text = _first_reason_text({"ValueError: b": 1, "ValueError: a": 4},
                                  {"ValueError: a": "usage.jsonl:9", "ValueError: b": "usage.jsonl:2"})
        self.assertIn("5 row(s) refused", text)
        self.assertIn("ValueError: a ×4 @ usage.jsonl:9", text)
        self.assertIn("ValueError: b ×1 @ usage.jsonl:2", text,
                      "the second cause used to be counted and then dropped from the sentence — a reader "
                      "would have seen one cause where two existed")
        # the most frequent cause leads, so a truncated read still gets the dominant symptom
        self.assertLess(text.index("ValueError: a"), text.index("ValueError: b"))
        self.assertIsNone(_first_reason_text({}, {}), "no refusals must produce no claim")

    def test_a_missing_location_is_said_to_be_missing(self) -> None:
        text = _first_reason_text({"RuntimeError: x": 2}, {})
        self.assertIn("<no location reported>", text)

    def test_more_causes_than_the_limit_are_counted_and_declared_truncated(self) -> None:
        counts = {f"ValueError: cause-{index}": 1 for index in range(7)}
        text = _first_reason_text(counts, {})
        self.assertIn("7 row(s) refused", text)
        self.assertIn("另有 3 类原因未列出", text,
                      "a cap that is not declared is how a bounded sentence reads as a complete one")
        self.assertLessEqual(len(text), 600)


class UsageCollectorLineRefusalTests(unittest.TestCase):
    def setUp(self) -> None:
        self.root = project_temp.fixture_root(prefix="ingest-lines-")
        self.dir = self.root.__enter__()
        self.artifacts = self.dir / ".hermes" / "task-artifacts"
        self.artifacts.mkdir(parents=True)

    def tearDown(self) -> None:
        self.root.__exit__(None, None, None)

    def _write(self, lines: list[str]) -> Path:
        path = self.artifacts / "usage.jsonl"
        path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
        return path

    def _collect(self):
        import collectors
        return collectors.collect_usage_files(None, "work-lab", self.artifacts)

    def test_lines_the_collector_cannot_use_are_counted_and_located(self) -> None:
        good = json.dumps({"provider": "deepseek", "model": "m", "input_tokens": 5, "total_tokens": 5})
        self._write([good, "{not json at all", json.dumps(["array", "not", "object"]),
                     json.dumps({"provider": "deepseek", "model": "m"}), ""])
        result = self._collect()
        self.assertEqual(len(result.records), 1)
        self.assertEqual(result.refusals.get("line_unparseable_json"), 1, result.refusals)
        self.assertEqual(result.refusals.get("line_not_an_object"), 1, result.refusals)
        self.assertEqual(result.refusals.get("line_has_no_usable_token_fields"), 1, result.refusals)
        self.assertTrue(result.refusal_samples["line_unparseable_json"].endswith(":2"),
                        f"sample must name the line: {result.refusal_samples}")
        self.assertTrue(result.refusal_samples["line_not_an_object"].endswith(":3"))

    def test_an_empty_source_and_a_source_of_only_unusable_lines_are_different_statements(self) -> None:
        self._write([json.dumps({"note": "no counters here"})] * 3)
        refused = self._collect()
        self.assertEqual(refused.records, [])
        self.assertEqual(refused.refusals.get("line_has_no_usable_token_fields"), 3)

        (self.artifacts / "usage.jsonl").unlink()
        empty = self._collect()
        self.assertEqual(empty.records, [])
        self.assertEqual(empty.refusals, {},
                         "'nothing in the directory' and 'three lines I could not use' must not read alike")

    def test_the_sample_stays_the_first_occurrence_not_the_newest(self) -> None:
        self._write(["{broken a", "{broken b"])
        result = self._collect()
        self.assertEqual(result.refusals["line_unparseable_json"], 2)
        self.assertTrue(result.refusal_samples["line_unparseable_json"].endswith(":1"),
                        "the location moved to the newest symptom instead of naming the first")


class GrowthQuarantineTests(unittest.TestCase):
    def test_a_candidate_rejected_by_intake_is_counted_not_omitted_silently(self) -> None:
        import collectors
        import growth_candidates

        root = project_temp.fixture_root(prefix="ingest-growth-")
        with root as directory:
            skills = directory / ".agents" / "skills"
            skills.mkdir(parents=True)
            (skills / "candidate.md").write_text("# body\n", encoding="utf-8")
            original = growth_candidates.intake

            def rejecting(candidate_id, origin, classification, risk, source):
                raise ValueError("candidate name is not discoverable")

            growth_candidates.intake = rejecting
            try:
                result = collectors.collect_growth_watcher(None, "work-lab", directory)
            finally:
                growth_candidates.intake = original
            self.assertEqual(result.records, [])
            self.assertEqual(result.refusals.get("candidate_rejected_by_intake"), 1,
                             "intake refused a candidate and nobody was told")
            self.assertIn("not discoverable", str(result.refusal_samples["candidate_rejected_by_intake"]))


class ExistingDatabaseMigrationTests(unittest.TestCase):
    """A store created before this change has no `refused_rows` column, and it is the live case.

    The fresh-database path proves nothing on its own: `CREATE TABLE IF NOT EXISTS` simply builds the new
    shape, so a missing ALTER would read as green here and break the moment an existing canonical store is
    opened. This case writes the PRE-change DDL with sqlite directly, records migration version 1 only, then
    opens `CanonicalStore` on it and requires the columns and the migration row to arrive.
    """

    OLD_DDL = """
    CREATE TABLE collector_health (
        name TEXT PRIMARY KEY,
        total_runs INTEGER NOT NULL DEFAULT 0,
        last_run_at TEXT,
        last_success_at TEXT,
        consecutive_failures INTEGER NOT NULL DEFAULT 0,
        circuit_open_until REAL,
        dropped_count INTEGER NOT NULL DEFAULT 0,
        updated_at TEXT NOT NULL
    );
    INSERT INTO collector_health (name, total_runs, dropped_count, updated_at)
        VALUES ('legacy-collector', 7, 4, '2026-10-09T00:00:00Z');
    """

    def test_an_older_store_gains_the_refusal_columns_without_losing_its_rows(self) -> None:
        import sqlite3

        directory = project_temp.fixture_dir("ingest-migration-")
        path = directory / "canonical.sqlite"
        connection = sqlite3.connect(str(path))
        connection.execute("""CREATE TABLE IF NOT EXISTS schema_migrations (
            version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL)""")
        connection.execute("INSERT INTO schema_migrations (version, applied_at) VALUES (1, '2026-08-01T00:00:00Z')")
        connection.executescript(self.OLD_DDL)
        connection.commit()
        columns_before = {row[1] for row in connection.execute("PRAGMA table_info(collector_health)")}
        connection.close()
        self.assertNotIn("refused_rows", columns_before, "the fixture is not the pre-change shape")

        store = CanonicalStore(path)
        try:
            row = {r["name"]: r for r in store.list_collector_health()}["legacy-collector"]
            self.assertEqual(int(row["total_runs"]), 7, "the migration disturbed stored health history")
            self.assertIn("refused_rows", row, f"columns after migration: {sorted(row)}")
            self.assertEqual(int(row["refused_rows"]), 0)
            self.assertIn("last_refusal_reason", row)
            store.upsert_collector_health({"name": "legacy-collector", "refusedRows": 3,
                                           "lastRefusalReason": "ValueError: sensitive value(s)"})
            after = {r["name"]: r for r in store.list_collector_health()}["legacy-collector"]
            self.assertEqual(int(after["refused_rows"]), 3)
            self.assertEqual(int(after["total_runs"]), 7,
                             "an unspoken field was rewritten to its default by the partial upsert")
            versions = {int(v[0]) for v in store._conn.execute(
                "SELECT version FROM schema_migrations")}
            self.assertIn(4, versions, f"migration 4 was not recorded: {sorted(versions)}")
        finally:
            store.close()
            project_temp.force_release(directory)


class RefusalTraceabilityTests(unittest.TestCase):
    """End to end through the shipped collector: a store-level refusal must name the LINE it refused."""

    def setUp(self) -> None:
        self.root = project_temp.fixture_root(prefix="ingest-trace-")
        self.dir = self.root.__enter__()
        self.artifacts = self.dir / ".hermes" / "task-artifacts"
        self.artifacts.mkdir(parents=True)
        self.store = CanonicalStore(self.dir / "canonical.sqlite")

    def tearDown(self) -> None:
        self.store.close()
        self.root.__exit__(None, None, None)

    def test_the_refused_credential_row_is_located_by_line_not_just_by_file(self) -> None:
        import collectors
        good = json.dumps({"provider": "deepseek", "model": "m", "input_tokens": 5,
                           "output_tokens": 2, "total_tokens": 7})
        (self.artifacts / "usage.jsonl").write_text(
            good + "\n" + json.dumps({"provider": POISON_KEY, "model": "m", "input_tokens": 3}) + "\n",
            encoding="utf-8", newline="\n")

        def real_collector(store: CanonicalStore, project_id: str) -> CollectorResult:
            return collectors.collect_usage_files(store, project_id, self.artifacts)

        real_collector.collector_name = "usage-files"
        result = DurableWorker(self.store, collectors=[real_collector]).run_once()
        outcome = next(c for c in result["collectors"] if c["kind"] == "usage")
        self.assertEqual(outcome["stored"], 1)
        self.assertEqual(outcome["refused"], 1)
        reason = next(iter(outcome["refusalReasons"]))
        self.assertEqual(outcome["refusalSamples"][reason], "usage.jsonl:2",
                         "the refusal named the file but not the line, so the reader has to guess "
                         "(source_ref is relative to the search root the collector was handed)")
        self.assertIn("usage.jsonl:2", str(self.health()["last_refusal_reason"]))

    def health(self) -> dict:
        return {row["name"]: row for row in self.store.list_collector_health()}["usage-files"]

    def test_the_diagnostic_line_key_is_never_persisted(self) -> None:
        import collectors
        (self.artifacts / "usage.jsonl").write_text(
            json.dumps({"provider": "openai", "model": "m", "total_tokens": 9}) + "\n",
            encoding="utf-8", newline="\n")
        rows = collectors.collect_usage_files(self.store, "work-lab", self.artifacts).records
        self.assertEqual(rows[0]["source_line"], 1)
        DurableWorker(self.store, collectors=[make_usage_collector(rows)]).run_once()
        stored = self.store.list_usage_samples()
        self.assertEqual(len(stored), 1)
        self.assertNotIn("source_line", json.dumps(stored[0]),
                         "a diagnostic locator must not become a canonical column")


if __name__ == "__main__":
    unittest.main(verbosity=2)
