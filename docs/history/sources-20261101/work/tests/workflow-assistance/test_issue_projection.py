"""Gate: the issue centre derives problems only from facts the canonical store already holds.

The audit of 2026-10-22 left the problem centre at NOT_IMPLEMENTED: the snapshot carried counts
(`refusedRows`, coverage numerators, task statuses) but nothing that said which project has which problem,
how many times it has been seen, or what evidence to re-read. Those properties are what this gate pins, and
each is proved by planting the failure the projection could produce:

* **absent is never empty** — no readable source ⇒ the key is absent with a named reason; every source read
  but holding nothing ⇒ `[]` with `complete=true`. Collapsing these two tells a reader "nothing is wrong"
  when the truth is "nobody looked" (the ERR-256 lineage of lies).
* **one dedup mechanism** — a recurring condition folds into a single fingerprinted row whose `occurrences`
  counts the absorbed events, and `foldedOccurrences` reports that folding happened at all.
* **priority is a declared rule** — every row carries the rule sentence that produced it, and every class in
  the closed vocabulary must be reachable from at least one source row, so no rule is decoration.
* **an undescribable row is not published** — a row that fails validation makes the whole key absent
  (fail closed) instead of shipping an issue whose class or evidence pointer is unexplained.

The store accessor is checked too: `list_telemetry_events` must not carry the payload column, because a
read-only projection has no business transporting user-authored text (AGENTS.md).
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "packages" / "client-neutral-core" / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from issue_projection import (  # noqa: E402
    CLASSES, MAX_ISSUES, PRIORITY_RANK, PRIORITY_RULES, SUMMARY_SCHEMA_VERSION,
    load_issues, project_issues, validate_issue)


class FakeStore:
    """A store that answers, or does not, exactly as told."""

    def __init__(self, *, health=None, telemetry=None, executions=None, tasks=None, raises=()):
        self._rows = {"collector_health": health, "telemetry_events": telemetry,
                      "execution_instances": executions, "tasks": tasks}
        self._raises = set(raises)

    def _take(self, name):
        if name in self._raises:
            raise RuntimeError(f"{name} is not answering")
        return self._rows[name] if self._rows[name] is not None else []

    def list_collector_health(self):
        return self._take("collector_health")

    def list_telemetry_events(self, limit=5000):
        return self._take("telemetry_events")[:limit]

    def list_executions(self):
        return self._take("execution_instances")

    def list_tasks(self):
        return self._take("tasks")


def health_row(**over) -> dict:
    row = {"name": "git", "total_runs": 10, "consecutive_failures": 0, "circuit_open_until": None,
           "dropped_count": 0, "refused_rows": 0, "delivered_rows": 8, "last_refusal_reason": None,
           "last_run_at": "2026-10-22T09:00:00Z", "last_success_at": "2026-10-22T09:00:00Z",
           "updated_at": "2026-10-22T09:00:00Z"}
    row.update(over)
    return row


def telemetry_row(**over) -> dict:
    row = {"event_id": "e1", "project_id": "work-lab", "producer": "codex",
           "occurred_at": "2026-10-22T09:00:00Z", "observed_at": "2026-10-22T09:00:01Z",
           "freshness": "FRESH", "coverage": "COMPLETE", "quality": "EXACT"}
    row.update(over)
    return row


def execution_row(**over) -> dict:
    row = {"execution_id": "x1", "agent": "codex", "anchor_project_id": "work-lab", "state": "RUNNING",
           "state_quality": "EXACT", "started_at": "2026-10-22T08:00:00Z",
           "last_heartbeat_at": "2026-10-22T09:00:00Z", "transport_state": "LIVE",
           "updated_at": "2026-10-22T09:00:00Z", "conflict_evidence": None}
    row.update(over)
    return row


def task_row(**over) -> dict:
    row = {"task_id": "t1", "project_id": "work-lab", "status": "RUNNING",
           "created_at": "2026-10-21T00:00:00Z", "updated_at": "2026-10-22T09:00:00Z",
           "lease_holder": "a", "fencing_token": 1}
    row.update(over)
    return row


def one_row_per_class() -> dict:
    """A source set in which every declared class actually fires."""
    import time
    return {
        "health": [health_row(circuit_open_until=time.time() + 600, consecutive_failures=2,
                              refused_rows=5, dropped_count=3),
                   health_row(name="sessions", consecutive_failures=1)],
        "telemetry": [telemetry_row(event_id="s1", freshness="STALE"),
                      telemetry_row(event_id="c1", coverage="PARTIAL")],
        "executions": [execution_row(execution_id="stall", last_heartbeat_at=""),
                       execution_row(execution_id="clash", conflict_evidence='[{"reason":"two-writers"}]')],
        "tasks": [task_row(task_id="blocked", status="BLOCKED"),
                  task_row(task_id="failed", status="FAILED")],
    }


def project_all(fixture: dict, **over):
    return project_issues(collector_health=fixture["health"], telemetry=fixture["telemetry"],
                          executions=fixture["executions"], tasks=fixture["tasks"], **over)


class TelemetryRecencyTests(unittest.TestCase):
    """A producer's newest readings decide whether it currently has the problem.

    Before this rule the projection emitted one issue per historical row, so a single PARTIAL reading from
    weeks ago kept the issue alive forever: nothing a repair did could make the list go empty, and `RESOLVED`
    on an independent re-read was unreachable by construction. The fix is recency only -- older anomalous rows
    still count, and rows tied at the newest timestamp are all treated as current.
    """

    def _issues(self, *rows):
        return project_issues(collector_health=[], telemetry=list(rows), executions=[], tasks=[])["issues"]

    def test_a_healthier_newer_reading_retires_the_standing_coverage_issue(self) -> None:
        issues = self._issues(
            telemetry_row(event_id="old", coverage="PARTIAL",
                          occurred_at="2026-10-19T13:27:45Z"),
            telemetry_row(event_id="new", coverage="FULL", occurred_at="2026-10-25T10:06:00Z"))
        self.assertEqual([], [row for row in issues
                              if row["class"] == "SOURCE_INCOMPLETE_COVERAGE"],
                         "the newest reading says the coverage is complete; the list must stop claiming it")

    def test_an_anomaly_with_no_healthier_successor_still_claims_the_issue(self) -> None:
        issues = self._issues(telemetry_row(event_id="only", coverage="PARTIAL"))
        self.assertEqual(1, len([row for row in issues if row["class"] == "SOURCE_INCOMPLETE_COVERAGE"]))

    def test_recurrence_still_folds_and_counts_when_the_newest_reading_is_the_anomaly(self) -> None:
        issues = self._issues(
            telemetry_row(event_id="a", coverage="PARTIAL", occurred_at="2026-10-21T00:00:00Z"),
            telemetry_row(event_id="b", coverage="DEGRADED", occurred_at="2026-10-22T00:00:00Z"),
            telemetry_row(event_id="c", coverage="PARTIAL", occurred_at="2026-10-23T00:00:00Z"))
        coverage = [row for row in issues if row["class"] == "SOURCE_INCOMPLETE_COVERAGE"]
        self.assertEqual(1, len(coverage), "one producer-subject stays one issue")
        self.assertEqual(3, coverage[0]["occurrences"], "history is folded, not dropped")
        self.assertEqual("2026-10-21T00:00:00Z", coverage[0]["firstSeenAt"])

    def test_rows_tied_at_the_newest_timestamp_are_all_current(self) -> None:
        issues = self._issues(
            telemetry_row(event_id="s", freshness="STALE", occurred_at="2026-10-25T10:00:00Z"),
            telemetry_row(event_id="c", coverage="PARTIAL", occurred_at="2026-10-25T10:00:00Z"))
        produced = {row["class"] for row in issues}
        self.assertIn("SOURCE_STALE", produced,
                      "two readings that cannot be ordered do not license suppressing either one")
        self.assertIn("SOURCE_INCOMPLETE_COVERAGE", produced)


class VocabularyTests(unittest.TestCase):
    def test_every_declared_class_is_reachable_from_a_source_row(self) -> None:
        result = project_all(one_row_per_class())
        produced = {row["class"] for row in result["issues"]}
        self.assertEqual(set(CLASSES), produced,
                        "a class in the vocabulary that no source can produce is decoration, not a contract")

    def test_every_class_carries_a_priority_rule_with_a_sentence(self) -> None:
        self.assertEqual(set(CLASSES), set(PRIORITY_RULES))
        for issue_class, rule in PRIORITY_RULES.items():
            with self.subTest(issue_class=issue_class):
                self.assertIn(rule["priority"], PRIORITY_RANK)
                self.assertTrue(rule["why"].strip(), "the reader must be told why this is P1")

    def test_unknown_freshness_or_coverage_words_do_not_become_issues(self) -> None:
        # Bucketing an unrecognised value into "stale"/"partial" would invent a problem the source never
        # stated; those values are simply not in the trigger sets.
        result = project_all({"health": [], "telemetry": [telemetry_row(freshness="WEIRD",
                                                                       coverage="WEIRD")],
                              "executions": [], "tasks": []})
        self.assertEqual([], result["issues"])
        self.assertEqual(1, result["summary"]["rowsScanned"])


class DedupTests(unittest.TestCase):
    def test_recurring_events_fold_into_one_issue_that_counts_what_it_absorbed(self) -> None:
        fixture = {"health": [], "executions": [], "tasks": [],
                   "telemetry": [telemetry_row(event_id="a", freshness="STALE"),
                                 telemetry_row(event_id="b", freshness="EXPIRED",
                                               occurred_at="2026-10-22T09:30:00Z")]}
        result = project_all(fixture)
        self.assertEqual(1, len(result["issues"]))
        row = result["issues"][0]
        self.assertEqual(2, row["occurrences"])
        self.assertEqual(1, result["summary"]["foldedOccurrences"],
                         "the fold must be visible in the denominator, not silently already-done")
        self.assertEqual("2026-10-22T09:00:00Z", row["firstSeenAt"])
        self.assertEqual("2026-10-22T09:30:00Z", row["lastSeenAt"])

    def test_the_same_subject_under_two_classes_stays_two_problems(self) -> None:
        fixture = {"health": [], "tasks": [],
                   "telemetry": [telemetry_row(event_id="a", freshness="STALE", coverage="PARTIAL")],
                   "executions": []}
        result = project_all(fixture)
        self.assertEqual({"SOURCE_STALE", "SOURCE_INCOMPLETE_COVERAGE"},
                         {row["class"] for row in result["issues"]})

    def test_the_fingerprint_is_stable_and_does_not_depend_on_event_id(self) -> None:
        stale = {"health": [], "executions": [], "tasks": [],
                 "telemetry": [telemetry_row(event_id="a", freshness="STALE")]}
        other = {"health": [], "executions": [], "tasks": [],
                 "telemetry": [telemetry_row(event_id="zzz", freshness="STALE")]}
        first = project_all(stale)["issues"][0]
        second = project_all(other)["issues"][0]
        self.assertEqual(first["fingerprint"], second["fingerprint"],
                         "a new event id for the same condition must not mint a new problem")
        self.assertRegex(first["fingerprint"], r"^[0-9a-f]{16}$")


class AbsentVersusEmptyTests(unittest.TestCase):
    def test_no_readable_source_leaves_the_key_absent_with_the_reasons_named(self) -> None:
        issues, summary, reason = load_issues(FakeStore(raises=("collector_health", "telemetry_events",
                                                               "execution_instances", "tasks")))
        self.assertIsNone(issues)
        self.assertIsNone(summary)
        for name in ("collector_health", "telemetry_events", "execution_instances", "tasks"):
            self.assertIn(name, reason)

    def test_every_source_read_and_empty_is_an_empty_list_not_an_absence(self) -> None:
        issues, summary, reason = load_issues(FakeStore(health=[], telemetry=[], executions=[], tasks=[]))
        self.assertEqual([], issues)
        self.assertIsNone(reason)
        self.assertEqual(4, summary["sourcesRead"])
        self.assertTrue(summary["complete"], "sources all read, nothing found: that IS a complete report")

    def test_one_source_not_answering_is_counted_and_stops_claiming_completeness(self) -> None:
        fixture = one_row_per_class()
        result = project_issues(collector_health=fixture["health"], telemetry=None,
                                executions=fixture["executions"], tasks=fixture["tasks"])
        self.assertFalse(result["summary"]["complete"])
        # two absent sources: the problem source that did not answer, and the identity list that was never
        # passed in. Counting both is the point -- an absent identity list is a real gap in the report.
        self.assertEqual(2, result["summary"]["sourcesAbsent"])
        absent = [item for item in result["summary"]["sources"] if item["state"] == "absent"]
        self.assertEqual({"telemetry_events", "software"}, {item["source"] for item in absent})
        for item in absent:
            self.assertIsNone(item["rowsScanned"],
                              "an absent source must not report a row count it never saw")

    def test_a_truncated_scan_is_not_a_complete_report(self) -> None:
        many = [telemetry_row(event_id=f"e{i}", freshness="STALE") for i in range(6)]
        result = project_issues(collector_health=[], telemetry=many, executions=[], tasks=[],
                               telemetry_limit=6)
        self.assertTrue(result["summary"]["scanTruncated"]["telemetry_events"])
        self.assertFalse(result["summary"]["complete"])
        self.assertEqual({"telemetry_events": 6}, result["summary"]["scanLimits"])


class CapAndOrderTests(unittest.TestCase):
    def test_the_cap_discloses_its_own_denominator_and_ordering_key(self) -> None:
        rows = [health_row(name=f"c{i}", consecutive_failures=1) for i in range(MAX_ISSUES + 9)]
        result = project_issues(collector_health=rows, telemetry=[], executions=[], tasks=[])
        summary = result["summary"]
        self.assertEqual(MAX_ISSUES, summary["emittedCount"])
        self.assertEqual(9, summary["omittedCount"])
        self.assertTrue(summary["truncated"])
        self.assertFalse(summary["complete"])
        self.assertEqual(summary["orderingKey"], "(-priorityRank, -lastSeenEpoch, fingerprint)")

    def test_severity_orders_first_then_recency_then_fingerprint(self) -> None:
        fixture = {"health": [health_row(name="old-p2", consecutive_failures=1,
                                        updated_at="2026-10-01T00:00:00Z"),
                             health_row(name="new-p2", consecutive_failures=1,
                                        updated_at="2026-10-22T00:00:00Z")],
                   "telemetry": [], "executions": [],
                   "tasks": [task_row(status="FAILED")]}
        result = project_all(fixture)
        priorities = [row["priority"] for row in result["issues"]]
        self.assertEqual(sorted(priorities, key=lambda p: PRIORITY_RANK[p]), priorities)
        self.assertEqual("TASK_FAILED", result["issues"][0]["class"])
        seen = [row["subject"] for row in result["issues"] if row["class"] == "SOURCE_FAILURE"]
        self.assertEqual(["new-p2", "old-p2"], seen, "inside one severity the newest reading comes first")


class FailClosedTests(unittest.TestCase):
    def test_a_junk_column_degrades_to_absent_instead_of_killing_the_read(self) -> None:
        # Reachable and real: `circuit_open_until` is a stored column, so one bad write makes the whole
        # derivation raise. The read path must report the gap rather than take the snapshot down with it.
        store = FakeStore(health=[health_row(circuit_open_until="not-a-number")],
                          telemetry=[telemetry_row(freshness="STALE")], executions=[], tasks=[])
        issues, summary, reason = load_issues(store)
        self.assertIsNone(issues)
        self.assertIsNone(summary)
        self.assertIn("projection-error", reason)

    def test_every_emitted_row_satisfies_the_published_contract(self) -> None:
        for row in project_all(one_row_per_class())["issues"]:
            with self.subTest(issue_class=row["class"]):
                self.assertEqual([], validate_issue(row))

    def test_validate_issue_names_every_shape_it_checks(self) -> None:
        good = project_all(one_row_per_class())["issues"][0]
        self.assertEqual([], validate_issue(good))
        for field, value, expected in (
                ("fingerprint", "nope", "16 hex"),
                ("class", "MYSTERY", "vocabulary"),
                ("priority", "P9", "P1/P2/P3"),
                ("priorityRule", "", "rule sentence"),
                ("evidenceRef", "", "evidenceRef"),
                ("occurrences", 0, "invented row")):
            with self.subTest(field=field):
                broken = dict(good, **{field: value})
                problems = validate_issue(broken)
                self.assertEqual(1, len(problems), problems)
                self.assertIn(expected, problems[0])
        self.assertEqual(["schemaVersion is not workflow/issue/v1"],
                         validate_issue(dict(good, schemaVersion="workflow/issue/v2")))


class StoreAccessorTests(unittest.TestCase):
    def test_telemetry_accessor_never_returns_the_payload_column(self) -> None:
        from canonical_store import CanonicalStore
        with tempfile.TemporaryDirectory(dir=ROOT / ".project-local" / "runs") as tmp:
            store = CanonicalStore(Path(tmp) / "canonical.sqlite")
            store.append_telemetry({"event_id": "e1", "project_id": "work-lab", "producer": "codex",
                                    "freshness": "STALE", "coverage": "PARTIAL", "quality": "EXACT",
                                    "noteText": "text that must never travel into a projection"})
            rows = store.list_telemetry_events()
            store.close()
        self.assertEqual(1, len(rows))
        self.assertNotIn("payload", rows[0], "the payload column is user-authored content")
        self.assertNotIn("noteText", str(rows[0]))
        self.assertEqual("STALE", rows[0]["freshness"])

    def test_the_projection_never_carries_content_into_a_row(self) -> None:
        result = project_all(one_row_per_class())
        self.assertFalse(result["summary"]["contentIncluded"])
        for row in result["issues"]:
            self.assertNotIn("payload", row)
            self.assertNotIn("content", row)
            self.assertLessEqual(len(row["detail"]), 160)

    def test_the_summary_declares_its_own_schema_and_scope(self) -> None:
        summary = project_all(one_row_per_class())["summary"]
        self.assertEqual(SUMMARY_SCHEMA_VERSION, summary["schemaVersion"])
        self.assertEqual("canonical-store-facts-only", summary["derivationScope"])
        self.assertFalse(summary["inferencePerformed"],
                         "this module relates facts, it does not diagnose causes")


class EndToEndShapeTests(unittest.TestCase):
    def test_load_issues_matches_project_issues_on_the_same_data(self) -> None:
        fixture = one_row_per_class()
        from_store = load_issues(FakeStore(health=fixture["health"], telemetry=fixture["telemetry"],
                                          executions=fixture["executions"], tasks=fixture["tasks"]))
        direct = project_issues(collector_health=fixture["health"], telemetry=fixture["telemetry"],
                                executions=fixture["executions"], tasks=fixture["tasks"])
        self.assertEqual(direct["issues"], from_store[0])
        self.assertEqual(direct["summary"]["distinctIssueCount"], from_store[1]["distinctIssueCount"])

    def test_priority_counts_and_project_attribution_add_up(self) -> None:
        summary = project_all(one_row_per_class())["summary"]
        self.assertEqual(summary["emittedCount"], sum(summary["priorityCounts"].values()))
        attributed = sum(1 for row in project_all(one_row_per_class())["issues"] if row["projectId"])
        self.assertEqual(attributed + summary["unattributedCount"], summary["emittedCount"],
                         "every row is either attributed to a project or counted as unattributed")
        self.assertTrue(summary["projectsCovered"], "the fixture attributes rows on purpose")


class AttributionTests(unittest.TestCase):
    """Software identity is joined, never guessed, and its absence is reported as absence."""

    identity = [{"softwareId": "codex-desktop", "displayName": "Codex Desktop",
                 "discoveredVersion": "24.10.1"},
                {"softwareId": "cc-switch", "displayName": "CC Switch", "discoveredVersion": None},
                {"softwareId": "dsh", "displayName": "DeepSeek Harness", "discoveredVersion": "0.2.1-rc.2"}]

    def project(self, events, software=identity):
        return project_issues(collector_health=[], telemetry=events, executions=[], tasks=[],
                              software=software, generated_at="2026-10-22T10:00:00Z")

    def test_a_unique_name_is_attributed_and_carries_the_discovered_version(self) -> None:
        result = self.project([telemetry_row(producer="codex-desktop", freshness="STALE")])
        row = result["issues"][0]
        self.assertEqual("codex-desktop", row["softwareId"])
        self.assertEqual("24.10.1", row["softwareVersion"])
        self.assertEqual("discovered", row["softwareVersionSource"])

    def test_matching_is_by_identity_not_by_luck_on_a_substring(self) -> None:
        # "codex" is a prefix of codex-desktop and of its display name, but it is neither identity. Matching
        # on prefix would attach a problem to whichever product happens to share the first letters.
        result = self.project([telemetry_row(producer="codex", freshness="STALE")])
        self.assertIsNone(result["issues"][0]["softwareId"])
        self.assertEqual("unmatched", result["issues"][0]["softwareVersionSource"])

    def test_a_name_two_products_share_stays_unattributed(self) -> None:
        only = [{"softwareId": "codex-desktop", "displayName": "Codex Desktop",
                 "discoveredVersion": "1.0"},
                {"softwareId": "codex-fork", "displayName": "Codex Desktop", "discoveredVersion": "2.0"}]
        result = self.project([telemetry_row(producer="Codex Desktop", freshness="STALE")], software=only)
        row = result["issues"][0]
        self.assertIsNone(row["softwareId"], "guessing which install was meant attributes a false subject")
        self.assertIsNone(row["softwareVersion"])
        self.assertEqual("ambiguous", row["softwareVersionSource"])
        self.assertEqual(1, result["summary"]["softwareAttribution"]["ambiguous"])

    def test_a_product_known_without_a_version_says_not_discovered_rather_than_empty(self) -> None:
        result = self.project([telemetry_row(producer="cc-switch", freshness="STALE")])
        row = result["issues"][0]
        self.assertEqual("cc-switch", row["softwareId"])
        self.assertIsNone(row["softwareVersion"])
        self.assertEqual("not-discovered", row["softwareVersionSource"])

    def test_a_source_that_names_no_product_so_does_the_row(self) -> None:
        result = self.project([telemetry_row(producer="UNKNOWN", freshness="STALE")])
        self.assertEqual("source-names-no-software", result["issues"][0]["softwareVersionSource"])
        health = project_issues(collector_health=[{"name": "git", "consecutive_failures": 2,
                                                  "updated_at": "2026-10-22T09:00:00Z"}],
                                telemetry=[], executions=[], tasks=[], software=self.identity)
        self.assertEqual("source-names-no-software", health["issues"][0]["softwareVersionSource"])

    def test_the_four_buckets_cover_every_row_and_the_absent_list_is_named(self) -> None:
        events = [telemetry_row(event_id="a", producer="codex-desktop", freshness="STALE"),
                  telemetry_row(event_id="b", producer="who-knows", freshness="STALE"),
                  telemetry_row(event_id="c", producer="UNKNOWN", freshness="STALE")]
        with_identity = self.project(events)
        attribution = with_identity["summary"]["softwareAttribution"]
        self.assertEqual(len(with_identity["issues"]),
                         attribution["attributed"] + attribution["unmatched"] + attribution["ambiguous"]
                         + attribution["unattributable"])
        self.assertEqual(1, attribution["versionKnown"])
        self.assertFalse(attribution["identitySourceAbsent"])
        self.assertTrue(with_identity["summary"]["complete"],
                        "the identity list being present or not is a separate fact from the list's scope")

        without = self.project(events, software=None)
        absent = without["summary"]["softwareAttribution"]
        self.assertTrue(absent["identitySourceAbsent"])
        self.assertEqual(0, absent["attributed"])
        self.assertEqual(len(without["issues"]), absent["unattributable"],
                         "attributed=0 with an absent identity list must read as 'nothing was known', "
                         "never as 'no problem belongs to software'")
        self.assertTrue(without["summary"]["complete"], "complete is about the problem sources")

    def test_load_issues_passes_the_injected_identity_rows_through(self) -> None:
        class Store(FakeStore):
            pass

        store = Store(health=[], executions=[], tasks=[],
                      telemetry=[telemetry_row(producer="dsh", freshness="STALE")])
        issues, summary, reason = load_issues(store, software_rows=None)
        self.assertEqual("identity-source-absent", issues[0]["softwareVersionSource"])
        self.assertIsNone(reason)
        issues, summary, _reason = load_issues(store, software_rows=self.identity)
        self.assertEqual("dsh", issues[0]["softwareId"])
        self.assertEqual("0.2.1-rc.2", issues[0]["softwareVersion"])
        self.assertEqual(1, summary["softwareAttribution"]["versionKnown"])

    def test_validate_issue_refuses_an_incoherent_attribution(self) -> None:
        good = self.project([telemetry_row(producer="codex-desktop", freshness="STALE")])["issues"][0]
        self.assertEqual([], validate_issue(good))
        self.assertIn("vocabulary", " ".join(validate_issue(dict(good, softwareVersionSource="guessed"))))
        self.assertIn("how its version was obtained",
                      " ".join(validate_issue(dict(good, softwareVersionSource="unmatched"))))
        self.assertIn("fabricated linkage",
                      " ".join(validate_issue(dict(good, softwareId=None))))


if __name__ == "__main__":
    unittest.main()
