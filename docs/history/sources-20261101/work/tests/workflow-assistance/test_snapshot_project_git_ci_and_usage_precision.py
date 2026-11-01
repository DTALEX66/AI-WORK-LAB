"""WL-L01 / WL-L02 / WL-L03 — three cloud-audit findings against the v3 snapshot producer.

Source: WL-REC-0104 (AAOS-WORK-DESIGN-cloud-audit-20261011), triaged in
docs/history/archive/ui-priority-20261009/CLOUD-AUDIT-INTAKE-2026-10-11.md and registered on the WUI-19 row.

Each finding is proved twice: once on the shape the producer emits now, and once against the exact
claim the audit made (the borrowed SHA is not present, the CI list is not empty, the precision is not
promoted). The negative half is what stops the fix from being re-broken into a different silence.
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "packages" / "client-neutral-core" / "scripts"))
sys.path.insert(0, str(ROOT / "services" / "orchestration"))

from canonical_store import CanonicalStore  # noqa: E402
from composition_root import _ci_rows, _git_state, build_v3_snapshot, load_approved_index  # noqa: E402
from snapshot_api import _merge_cost_quality, _rollup_usage, build_snapshot  # noqa: E402
from snapshot_validator import validate_snapshot  # noqa: E402

WORKLAB_SHA = "769345d21fb9df9d0acafe13f953e41597658b80"
OTHER_SHA = "1111111111111111111111111111111111111111"


def _git_row(project_id: str, sha: str, branch: str) -> dict:
    return {
        "row_id": f"git-{project_id}",
        "project_id": project_id,
        "scope": "git",
        "quality": "EXACT_SOURCE",
        "coverage": "PARTIAL",
        "freshness": "STALE",
        "observed_at": "2026-08-14T14:59:30Z",
        "last_good_at": "2026-08-14T14:59:30Z",
        "head_sha": sha,
        "branch": branch,
        "dirty_count": 3,
        "sourceRef": "git-rev-parse",
    }


def _ci_row(run_id: str, project_id: str, conclusion: str) -> dict:
    return {
        "run_id": run_id,
        "project_id": project_id,
        "workflow": "work-lab-gate",
        "head_sha": WORKLAB_SHA,
        "status": "completed",
        "conclusion": conclusion,
        "jobs": [],
    }


class ProjectGitAttributionTests(unittest.TestCase):
    """WL-L01: a project without its own Git observation must read UNKNOWN, never borrow a repo."""

    def test_a_project_without_its_own_git_row_is_unknown_and_not_another_projects_sha(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = CanonicalStore(Path(tmp) / "c.sqlite")
            try:
                store.register_project("work-lab", str(ROOT), display_name="WORK-LAB")
                store.register_project("design-lab", str(Path(tmp) / "other"), display_name="OTHER")
                store.append_quality(_git_row("work-lab", WORKLAB_SHA, "main"))
                snap = build_v3_snapshot(store, load_approved_index(store), revision=0)
                by_id = {p["projectId"]: p for p in snap["projects"]}
                self.assertIn("design-lab", by_id)
                other = by_id["design-lab"]["git"]
                # Positive: the block still exists and still answers, with an honest state.
                self.assertEqual(other["matchState"], "NO_LOCAL_CLAIM")
                for field in ("localSha", "remoteSha", "branch", "dirtyCount", "observedAt",
                              "quality", "freshness", "sourceRef"):
                    self.assertIsNone(other[field], f"{field} must be null, not borrowed")
                self.assertIsNone(other["sourceProjectId"])
                # Negative: the whole point of the fix. The old code fell back to git_state, which
                # composition_root built with next(iter(git_states.values())) — under this fixture that
                # is work-lab, so OTHER used to be printed with WORK-LAB's SHA and branch.
                self.assertNotEqual(other["localSha"], WORKLAB_SHA)
                self.assertNotEqual(other["branch"], "main")
                # And the project that does own an observation keeps it, named as its own.
                self.assertEqual(by_id["work-lab"]["git"]["localSha"], WORKLAB_SHA)
                self.assertEqual(by_id["work-lab"]["git"]["sourceProjectId"], "work-lab")
                self.assertTrue(validate_snapshot(snap)["valid"])
            finally:
                store.close()

    def test_a_legacy_git_state_argument_is_not_used_as_a_per_project_fallback(self) -> None:
        snap = build_snapshot(
            revision=1,
            projects=[{"projectId": "design-lab", "displayName": "OTHER"}],
            git_state={"localSha": WORKLAB_SHA, "branch": "main", "remoteSha": WORKLAB_SHA},
        )
        project_git = snap["projects"][0]["git"]
        self.assertIsNone(project_git["localSha"])
        self.assertIsNone(project_git["sourceProjectId"])
        self.assertEqual(project_git["matchState"], "NO_LOCAL_CLAIM")
        # The top-level legacy summary is unchanged by this fix — it is WORK-LAB's own surface.
        self.assertEqual(snap["git"]["localSha"], WORKLAB_SHA)

    def test_the_top_level_summary_does_not_borrow_a_non_work_lab_observation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = CanonicalStore(Path(tmp) / "c.sqlite")
            try:
                store.append_quality(_git_row("some-second-project", OTHER_SHA, "feature/x"))
                self.assertIsNone(
                    _git_state(store),
                    "no work-lab row means no top-level git claim, not someone else's SHA",
                )
                store.register_project("work-lab", str(ROOT), display_name="WORK-LAB")
                snap = build_v3_snapshot(store, load_approved_index(store), revision=0)
                self.assertIsNone(snap["git"]["localSha"])
                self.assertNotEqual(snap["git"]["localSha"], OTHER_SHA)
                self.assertEqual(snap["git"]["matchState"], "NO_LOCAL_CLAIM")
            finally:
                store.close()


class ProjectCiAttributionTests(unittest.TestCase):
    """WL-L02: ci_runs carries project_id in the store; dropping it made every project's ci empty."""

    def test_ci_rows_carry_the_project_id_the_downstream_filter_reads(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = CanonicalStore(Path(tmp) / "c.sqlite")
            try:
                store.record_ci_run(_ci_row("r1", "work-lab", "success"))
                rows = _ci_rows(store)
                self.assertEqual(len(rows), 1)
                # Without this key the filter `r.get("projectId") == project_id` is false for every
                # row, which is why ci was [] for every project including ones with real runs.
                self.assertEqual(rows[0]["projectId"], "work-lab")
            finally:
                store.close()

    def test_each_project_sees_only_its_own_runs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = CanonicalStore(Path(tmp) / "c.sqlite")
            try:
                store.register_project("work-lab", str(ROOT), display_name="WORK-LAB")
                store.register_project("design-lab", str(Path(tmp) / "other"), display_name="OTHER")
                store.record_ci_run(_ci_row("r-work-lab", "work-lab", "success"))
                store.record_ci_run(_ci_row("r-other", "design-lab", "failure"))
                snap = build_v3_snapshot(store, load_approved_index(store), revision=0)
                by_id = {p["projectId"]: p for p in snap["projects"]}
                self.assertEqual([r["runId"] for r in by_id["work-lab"]["ci"]], ["r-work-lab"])
                self.assertEqual([r["runId"] for r in by_id["design-lab"]["ci"]], ["r-other"])
                self.assertEqual(by_id["design-lab"]["ci"][0]["conclusion"], "failure")
                self.assertTrue(validate_snapshot(snap)["valid"])
            finally:
                store.close()

    def test_a_project_with_no_runs_still_reports_empty_and_the_snapshot_still_carries_all_runs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = CanonicalStore(Path(tmp) / "c.sqlite")
            try:
                store.register_project("work-lab", str(ROOT), display_name="WORK-LAB")
                store.register_project("design-lab", str(Path(tmp) / "q"), display_name="QUIET")
                store.record_ci_run(_ci_row("r-work-lab", "work-lab", "success"))
                snap = build_v3_snapshot(store, load_approved_index(store), revision=0)
                by_id = {p["projectId"]: p for p in snap["projects"]}
                self.assertEqual(by_id["design-lab"]["ci"], [])
                # The distinction the audit asked for: if this were the pre-fix bug, work-lab's list
                # would be empty too. It is not, so an empty list here means "this project has none"
                # rather than "the predicate never held".
                self.assertEqual(len(by_id["work-lab"]["ci"]), 1)
                self.assertEqual(len(snap["ci"]), 1)
            finally:
                store.close()


class UsagePrecisionTests(unittest.TestCase):
    """WL-L03: one merge rule, shared as a predicate by the rollup and the token summary."""

    def test_a_mixed_project_is_not_promoted_to_exact(self) -> None:
        usage = [
            {"projectId": "work-lab", "inputTokens": 10, "costQuality": "EXACT"},
            {"projectId": "work-lab", "inputTokens": 20, "costQuality": "ESTIMATED"},
        ]
        self.assertEqual(_rollup_usage(usage)["work-lab"]["costQuality"], "ESTIMATED")
        snap = build_snapshot(revision=1, usage=usage,
                              projects=[{"projectId": "work-lab"}])
        self.assertEqual(snap["projects"][0]["token"]["costQuality"], "ESTIMATED")
        self.assertEqual(snap["tokenSummary"]["costQuality"], "ESTIMATED")

    def test_the_two_surfaces_agree_on_every_combination(self) -> None:
        combos = [
            ["EXACT"], ["EXACT", "EXACT"], ["ESTIMATED"], ["ESTIMATED", "ESTIMATED"],
            ["EXACT", "ESTIMATED"], ["ESTIMATED", "EXACT"], [None], [None, "EXACT"],
            ["UNKNOWN"], ["EXACT", "UNKNOWN"],
        ]
        for combo in combos:
            usage = [{"projectId": "work-lab", "inputTokens": 1, "costQuality": q} for q in combo]
            snap = build_snapshot(revision=1, usage=usage, projects=[{"projectId": "work-lab"}])
            project_quality = snap["projects"][0]["token"]["costQuality"]
            summary_quality = snap["tokenSummary"]["costQuality"]
            self.assertEqual(project_quality, summary_quality, f"surfaces disagree for {combo}")
            self.assertEqual(project_quality, _merge_cost_quality(combo))

    def test_no_samples_is_unknown_and_not_exact(self) -> None:
        # all([]) is True, so a naive shared predicate would call "no samples" exact.
        self.assertEqual(_merge_cost_quality([]), "UNKNOWN")
        self.assertEqual(_rollup_usage([]), {})
        self.assertEqual(build_snapshot(revision=1)["tokenSummary"]["costQuality"], "UNKNOWN")

    def test_two_projects_keep_their_own_precision(self) -> None:
        usage = [
            {"projectId": "one", "inputTokens": 5, "costQuality": "EXACT"},
            {"projectId": "two", "inputTokens": 7, "costQuality": "ESTIMATED"},
        ]
        rolled = _rollup_usage(usage)
        self.assertEqual(rolled["one"]["costQuality"], "EXACT")
        self.assertEqual(rolled["two"]["costQuality"], "ESTIMATED")
        self.assertEqual(rolled["one"]["inputTokens"], 5)
        self.assertEqual(rolled["two"]["inputTokens"], 7)
        # The global summary over both is the pessimistic one, not the per-project maximum.
        snap = build_snapshot(revision=1, usage=usage)
        self.assertEqual(snap["tokenSummary"]["costQuality"], "ESTIMATED")
        self.assertEqual(snap["tokenSummary"]["inputTokens"], 12)

    def test_the_rollup_does_not_leak_its_scratch_key(self) -> None:
        rolled = _rollup_usage([{"projectId": "one", "inputTokens": 1, "costQuality": "EXACT"}])
        self.assertEqual(set(rolled["one"]), {"inputTokens", "outputTokens", "totalTokens", "costQuality"})


if __name__ == "__main__":
    unittest.main()
