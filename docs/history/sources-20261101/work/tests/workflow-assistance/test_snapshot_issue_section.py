"""Gate: the issue sections survive the producer → build_snapshot → snapshot_validator chain intact.

The projection module (`test_issue_projection.py`) proves what a row means. This gate proves the snapshot
cannot *misrepresent* it: a list without its scope, a scope report that contradicts its own list, a
duplicated fingerprint, or a row that smuggled in file content must all be refused by the validator the
sidecar actually uses, not merely by the JSON schema.

Refusals pinned here, in the order they would have hurt a reader:

* issues without `issuesSummary` — an enumeration with no stated scope reads as a complete list;
* `issuesSummary` without issues — a scope report about a list this snapshot does not carry;
* a repeated fingerprint — the fold did not happen, so `occurrences` double-counts one problem across rows;
* a content field on a row — an issue row is a pointer to evidence; letting bytes ride in would undo the
  range route's read-on-demand rule;
* denominators that disagree (`emittedCount`, `distinctIssueCount != emitted + omitted`, `rowsScanned` vs
  the per-source sums, `priorityCounts` vs the rows), `truncated` with nothing omitted, and `complete`
  while any source did not answer.

Discovered dynamically by the mandatory `test_*.py` glob in `run_quality_gate.governance`.
"""
from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "packages" / "client-neutral-core" / "scripts"))

import snapshot_api  # noqa: E402
import snapshot_validator  # noqa: E402
from issue_projection import project_issues  # noqa: E402


def source_rows() -> dict:
    return {
        "health": [{"name": "git", "total_runs": 9, "consecutive_failures": 2,
                    "circuit_open_until": None, "dropped_count": 3, "refused_rows": 5,
                    "delivered_rows": 40, "last_refusal_reason": "OUT_OF_BOUNDARY",
                    "last_run_at": "2026-10-22T09:00:00Z", "last_success_at": "2026-10-22T08:00:00Z",
                    "updated_at": "2026-10-22T09:00:00Z"}],
        "telemetry": [{"event_id": "t1", "project_id": "work-lab", "producer": "codex",
                       "occurred_at": "2026-10-22T09:00:00Z", "observed_at": "2026-10-22T09:00:01Z",
                       "freshness": "STALE", "coverage": "PARTIAL", "quality": "EXACT"}],
        "executions": [{"execution_id": "x1", "agent": "codex", "anchor_project_id": "work-lab",
                        "state": "RUNNING", "state_quality": "ESTIMATED",
                        "started_at": "2026-10-22T08:00:00Z", "last_heartbeat_at": "",
                        "transport_state": "LIVE", "updated_at": "2026-10-22T09:00:00Z",
                        "conflict_evidence": '[{"reason":"two-writers"}]'}],
        "tasks": [{"task_id": "t-blocked", "project_id": "work-lab", "status": "BLOCKED",
                   "created_at": "2026-10-21T00:00:00Z", "updated_at": "2026-10-22T09:00:00Z",
                   "lease_holder": None, "fencing_token": None}],
    }


def built(**over) -> dict:
    kwargs = {"revision": 3, "generated_at": "2026-10-22T10:00:00Z"}
    kwargs.update(over)
    return snapshot_api.build_snapshot(**kwargs)


def snapshot_with_issues() -> dict:
    fixture = source_rows()
    projection = project_issues(collector_health=fixture["health"], telemetry=fixture["telemetry"],
                                executions=fixture["executions"], tasks=fixture["tasks"],
                                generated_at="2026-10-22T10:00:00Z")
    return built(issues=projection["issues"], issues_summary=projection["summary"])


def errors_of(snapshot: dict) -> list[str]:
    return snapshot_validator.validate_snapshot(snapshot)["errors"]


class HappyPathTests(unittest.TestCase):
    def test_the_producer_output_validates_end_to_end(self) -> None:
        snapshot = snapshot_with_issues()
        self.assertEqual([], errors_of(snapshot))
        self.assertGreaterEqual(len(snapshot["issues"]), 5,
                                "the fixture must actually exercise several classes")

    def test_absent_pair_is_absent_not_empty(self) -> None:
        snapshot = built(issues=None, issues_summary=None)
        self.assertNotIn("issues", snapshot)
        self.assertNotIn("issuesSummary", snapshot)
        self.assertEqual([], errors_of(snapshot))


class ScopeCouplingTests(unittest.TestCase):
    def test_a_list_without_its_scope_is_refused(self) -> None:
        snapshot = snapshot_with_issues()
        del snapshot["issuesSummary"]
        self.assertTrue(any("requires issuesSummary" in e for e in errors_of(snapshot)),
                        "an unscoped problem list claims completeness it has not earned")

    def test_a_scope_report_without_a_list_is_refused(self) -> None:
        snapshot = snapshot_with_issues()
        del snapshot["issues"]
        self.assertTrue(any("issuesSummary without issues" in e for e in errors_of(snapshot)))


class RowIntegrityTests(unittest.TestCase):
    def test_a_repeated_fingerprint_is_refused(self) -> None:
        snapshot = snapshot_with_issues()
        duplicate = copy.deepcopy(snapshot["issues"][0])
        snapshot["issues"].append(duplicate)
        snapshot["issuesSummary"]["emittedCount"] = len(snapshot["issues"])
        self.assertTrue(any("fingerprint repeats" in e for e in errors_of(snapshot)))

    def test_a_row_may_not_carry_evidence_content(self) -> None:
        for field in ("content", "body", "payload", "text", "lines"):
            with self.subTest(field=field):
                snapshot = snapshot_with_issues()
                snapshot["issues"][0][field] = "bytes that belong to the range route, not a list row"
                self.assertTrue(any(field in e and "must not carry" in e for e in errors_of(snapshot)))

    def test_each_required_identity_field_is_enforced(self) -> None:
        for field in ("fingerprint", "class", "priority", "priorityRule", "evidenceRef", "origin",
                      "occurrences", "status"):
            with self.subTest(field=field):
                snapshot = snapshot_with_issues()
                del snapshot["issues"][0][field]
                self.assertTrue(any("missing" in e and field in e for e in errors_of(snapshot)))

    def test_values_outside_the_declared_vocabulary_are_refused(self) -> None:
        for field, value, phrase in (("class", "SOMETHING_NEW", "outside the declared vocabulary"),
                                     ("priority", "P0", "must be P1/P2/P3"),
                                     ("status", "RESOLVED", "status must be OPEN")):
            with self.subTest(field=field):
                snapshot = snapshot_with_issues()
                snapshot["issues"][0][field] = value
                self.assertTrue(any(phrase in e for e in errors_of(snapshot)),
                                f"{field}={value!r} slipped through the runtime validator")

    def test_a_fingerprint_that_is_not_16_hex_is_refused(self) -> None:
        snapshot = snapshot_with_issues()
        snapshot["issues"][0]["fingerprint"] = "ZZZZ"
        self.assertTrue(any("16 hex" in e for e in errors_of(snapshot)))

    def test_zero_occurrences_and_oversized_detail_are_refused(self) -> None:
        snapshot = snapshot_with_issues()
        snapshot["issues"][0]["occurrences"] = 0
        snapshot["issues"][0]["detail"] = "x" * 400
        errors = errors_of(snapshot)
        self.assertTrue(any("occurrences" in e for e in errors))
        self.assertTrue(any("160-char bound" in e for e in errors))


class DenominatorTests(unittest.TestCase):
    def test_emitted_count_must_match_the_rows_present(self) -> None:
        snapshot = snapshot_with_issues()
        snapshot["issuesSummary"]["emittedCount"] = len(snapshot["issues"]) + 4
        self.assertTrue(any("emittedCount" in e for e in errors_of(snapshot)))

    def test_the_cap_tail_is_counted_exactly_once(self) -> None:
        snapshot = snapshot_with_issues()
        summary = snapshot["issuesSummary"]
        summary["distinctIssueCount"] = summary["emittedCount"] + 1  # omitted stays 0
        self.assertTrue(any("distinctIssueCount" in e for e in errors_of(snapshot)))

    def test_truncated_without_an_omitted_tail_is_refused(self) -> None:
        snapshot = snapshot_with_issues()
        summary = snapshot["issuesSummary"]
        summary["truncated"] = True
        summary["omittedCount"] = 0
        self.assertTrue(any("truncated is true while omittedCount is 0" in e for e in errors_of(snapshot)))

    def test_complete_cannot_be_true_while_a_source_did_not_answer(self) -> None:
        fixture = source_rows()
        projection = project_issues(collector_health=fixture["health"], telemetry=None,
                                    executions=fixture["executions"], tasks=fixture["tasks"],
                                    generated_at="2026-10-22T10:00:00Z")
        snapshot = built(issues=projection["issues"], issues_summary=projection["summary"])
        self.assertEqual([], errors_of(snapshot), "the projection already set complete=False")
        snapshot["issuesSummary"]["complete"] = True
        self.assertTrue(any("complete cannot be true" in e for e in errors_of(snapshot)))

    def test_rows_scanned_must_equal_the_sum_of_per_source_counts(self) -> None:
        snapshot = snapshot_with_issues()
        snapshot["issuesSummary"]["rowsScanned"] += 7
        self.assertTrue(any("rowsScanned" in e for e in errors_of(snapshot)))

    def test_priority_counts_must_add_up_to_the_rows(self) -> None:
        snapshot = snapshot_with_issues()
        snapshot["issuesSummary"]["priorityCounts"]["P1"] = 9
        self.assertTrue(any("priorityCounts" in e for e in errors_of(snapshot)))

    def test_attribution_buckets_must_cover_every_row(self) -> None:
        snapshot = snapshot_with_issues()
        snapshot["issuesSummary"]["softwareAttribution"]["unmatched"] += 3
        self.assertTrue(any("exactly one attribution bucket" in e for e in errors_of(snapshot)))

    def test_version_known_must_match_the_rows_that_carry_a_version(self) -> None:
        snapshot = snapshot_with_issues()
        snapshot["issues"][0]["softwareVersion"] = "9.9.9"
        snapshot["issues"][0]["softwareVersionSource"] = "discovered"
        snapshot["issues"][0]["softwareId"] = "some-product"
        self.assertTrue(any("versionKnown" in e for e in errors_of(snapshot)))

    def test_a_version_without_identity_and_a_lucky_state_are_refused(self) -> None:
        snapshot = snapshot_with_issues()
        snapshot["issues"][0]["softwareVersion"] = "1.2.3"
        snapshot["issues"][0]["softwareVersionSource"] = "unmatched"
        errors = errors_of(snapshot)
        self.assertTrue(any("no product identity" in e for e in errors),
                        "a version attached to no product is a fabricated linkage")
        # the same row, but now claiming a product while the state says nothing matched
        snapshot = snapshot_with_issues()
        snapshot["issues"][0]["softwareId"] = "guessed-product"
        snapshot["issues"][0]["softwareVersionSource"] = "unmatched"
        errors = errors_of(snapshot)
        self.assertTrue(any("without saying how that was known" in e for e in errors), errors)

    def test_the_identity_source_state_must_be_agreed_by_both_places(self) -> None:
        # complete is about the four problem sources; the identity list is disclosed by identitySourceAbsent.
        # If the two ever disagree, a reader cannot tell whether attribution was impossible or empty.
        snapshot = snapshot_with_issues()
        snapshot["issuesSummary"]["softwareAttribution"]["identitySourceAbsent"] = False
        self.assertTrue(any("identitySourceAbsent disagrees" in e for e in errors_of(snapshot)))
        self.assertTrue(snapshot["issuesSummary"]["complete"], "the list itself is still complete")

    def test_an_inference_claim_or_content_claim_on_the_scope_is_refused(self) -> None:
        for field, value in (("inferencePerformed", True), ("contentIncluded", True),
                             ("derivationScope", "whatever-the-model-said")):
            with self.subTest(field=field):
                snapshot = snapshot_with_issues()
                snapshot["issuesSummary"][field] = value
                self.assertTrue(any(field in e for e in errors_of(snapshot)))


if __name__ == "__main__":
    unittest.main()
