"""Contract tests for the four bounded collectors (WL3-510)."""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from canonical_store import CanonicalStore
import collectors
from collectors import (
    collect_git_ci,
    collect_source_quality,
    collect_task_ledger,
    collect_usage_files,
)


def _make_directory_link(link: Path, target: Path) -> str | None:
    """Point `link` at the directory `target`. Returns None on success, or why the host refused.

    A Windows junction is tried first because that is the shape the probe used and it needs no privilege;
    a POSIX symlink (or a Windows one, where the host allows it) covers the same traversal.
    """
    attempts: list[str] = []
    if os.name == "nt":
        result = subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(target)],
                                capture_output=True, text=True,
                                encoding="utf-8", errors="replace")
        if result.returncode == 0 and link.is_dir():
            return None
        attempts.append(f"mklink /J rc={result.returncode}")
    try:
        os.symlink(str(target), str(link), target_is_directory=True)
        return None
    except OSError as exc:
        attempts.append(f"os.symlink {type(exc).__name__}(errno={exc.errno})")
    return "; ".join(attempts)


def _remove_directory_link(link: Path) -> None:
    """Remove the link itself, never its target: a recursive delete may otherwise walk through it."""
    for action in (os.rmdir, os.unlink):
        try:
            if link.exists():
                action(link)
            return
        except OSError:
            continue


def _skip_if_no_link_support(reason: str | None) -> None:
    if reason is None:
        return
    raise unittest.SkipTest(
        f"host cannot create a directory link ({reason}); the real-link case cannot run here. "
        "The platform-independent containment cases below convict the same guard and do run in CI.")


def _make_git_project(root: Path, name: str) -> Path:
    project = root / name
    project.mkdir(parents=True)
    (project / "README.md").write_text(f"# {name}\n", encoding="utf-8")
    subprocess.run(["git", "init", "-q"], cwd=project, check=True)
    subprocess.run(["git", "add", "-A"], cwd=project, check=True)
    subprocess.run(
        ["git", "-c", "user.email=test@example.com", "-c", "user.name=test", "commit", "-qm", "init"],
        cwd=project,
        check=True,
    )
    return project


class TaskLedgerCoverageTests(unittest.TestCase):
    """Coverage is an observation about the ledger, not a word written next to it.

    The old collector stamped `coverage: "PARTIAL"` unconditionally and counted every project's tasks while
    attributing the record to one project. `issue_projection` turns PARTIAL into a standing
    `SOURCE_INCOMPLETE_COVERAGE` issue, so the shipped store carried an issue that no repair could close.
    """

    def setUp(self) -> None:
        self._dir = tempfile.TemporaryDirectory()
        self.addCleanup(self._dir.cleanup)
        self.root = Path(self._dir.name)
        self.store = CanonicalStore(self.root / "canonical.sqlite")
        self.addCleanup(self.store.close)

    def _collect(self, project: str):
        result = collect_task_ledger(self.store, project)
        self.assertEqual(len(result.records), 1)
        return result.records[0]

    def test_counts_are_scoped_to_the_project_they_are_attributed_to(self) -> None:
        self.store.upsert_task({"task_id": "a1", "project_id": "alpha", "status": "PENDING"})
        self.store.upsert_task({"task_id": "b1", "project_id": "beta", "status": "PENDING"})
        self.store.upsert_task({"task_id": "b2", "project_id": "beta", "status": "COMPLETED_LOCAL"})
        self.assertEqual(self._collect("alpha")["total"], 1)
        self.assertEqual(self._collect("beta")["total"], 2)

    def test_a_fully_attributed_ledger_reads_full_and_names_why(self) -> None:
        self.store.upsert_task({"task_id": "a1", "project_id": "alpha", "status": "PENDING"})
        record = self._collect("alpha")
        self.assertEqual(record["coverage"], "FULL")
        self.assertTrue(str(record["coverage_why"]).strip(), "a FULL claim still has to say what it compared")

    def test_an_empty_ledger_is_a_complete_read_of_nothing_not_a_partial_read(self) -> None:
        record = self._collect("alpha")
        self.assertEqual(record["coverage"], "FULL")
        self.assertEqual(record["total"], 0)

    def test_unattributed_or_unclassified_rows_are_what_makes_it_partial(self) -> None:
        self.store.upsert_task({"task_id": "a1", "project_id": "alpha", "status": "PENDING"})
        self.store.upsert_task({"task_id": "x1", "project_id": "", "status": "PENDING"})
        self.store.upsert_task({"task_id": "a2", "project_id": "alpha", "status": "UNKNOWN"})
        record = self._collect("alpha")
        self.assertEqual(record["coverage"], "PARTIAL")
        self.assertEqual(record["unattributed"], 1)
        self.assertIn("1 行无项目归属", record["coverage_why"])

    def test_a_full_read_produces_no_standing_coverage_issue(self) -> None:
        import issue_projection

        self.store.register_project("alpha", str(self.root / "alpha"), display_name="alpha")
        self.store.upsert_task({"task_id": "a1", "project_id": "alpha", "status": "PENDING"})
        record = self._collect("alpha")
        self.store.append_telemetry(record)
        issues, _summary, _absent = issue_projection.load_issues(
            self.store, generated_at="2026-10-25T00:00:00+00:00")
        self.assertEqual(
            [], [row for row in issues
                 if row.get("subject") == "task-ledger-collector:coverage"
                 and row.get("class") == "SOURCE_INCOMPLETE_COVERAGE"],
            "the shipped store carried exactly this issue forever, because PARTIAL was a constant")

    def test_the_partial_read_still_produces_the_issue(self) -> None:
        import issue_projection

        self.store.register_project("alpha", str(self.root / "alpha"), display_name="alpha")
        self.store.upsert_task({"task_id": "x1", "project_id": "", "status": "PENDING"})
        self.store.upsert_task({"task_id": "a1", "project_id": "alpha", "status": "PENDING"})
        self.store.append_telemetry(self._collect("alpha"))
        issues, _summary, _absent = issue_projection.load_issues(
            self.store, generated_at="2026-10-25T00:00:00+00:00")
        self.assertTrue([row for row in issues
                         if row.get("subject") == "task-ledger-collector:coverage"],
                        "a genuinely incomplete read must still arrive as an issue")


class CollectorsTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temporary = tempfile.TemporaryDirectory()
        self.root = Path(self._temporary.name)
        self.store = CanonicalStore(self.root / "canonical.sqlite")

    def tearDown(self) -> None:
        self.store.close()
        self._temporary.cleanup()

    def test_task_ledger_collector(self) -> None:
        self.store.upsert_task({"task_id": "t1", "project_id": "p", "status": "PENDING"})
        self.store.upsert_task({"task_id": "t2", "project_id": "p", "status": "COMPLETED_LOCAL"})
        result = collect_task_ledger(self.store, "p")
        self.assertTrue(result.ok)
        self.assertEqual(len(result.records), 1)
        self.assertEqual(result.records[0]["total"], 2)
        self.assertEqual(result.records[0]["task_counts"]["PENDING"], 1)
        repeated = collect_task_ledger(self.store, "p")
        self.assertEqual(result.records[0]["event_id"], repeated.records[0]["event_id"])
        self.store.append_telemetry(result.records[0])
        self.store.append_telemetry(repeated.records[0])
        self.assertEqual(self.store.projection()["telemetry_events"], 1)

    def test_git_ci_collector_reads_real_head_without_estimates(self) -> None:
        project = _make_git_project(self.root, "collector-demo")
        result = collect_git_ci(self.store, "collector-demo", project)
        self.assertTrue(result.ok)
        self.assertEqual(len(result.records), 1)
        record = result.records[0]
        self.assertEqual(record["quality"], "EXACT_SOURCE")
        self.assertRegex(record["head_sha"], r"^[0-9a-f]{40}$")
        self.assertEqual(record["dirty_count"], 0)
        repeated = collect_git_ci(self.store, "collector-demo", project).records[0]
        self.assertEqual(record["row_id"], repeated["row_id"])
        self.store.append_quality(record)
        self.store.append_quality(repeated)
        self.assertEqual(len(self.store.list_source_quality()), 1)

    def test_usage_collector_accepts_only_explicit_counters(self) -> None:
        artifacts = self.root / ".hermes" / "task-artifacts"
        artifacts.mkdir(parents=True)
        (artifacts / "usage.jsonl").write_text(
            json.dumps(
                {
                    "provider": "deepseek",
                    "model": "deepseek-v4-flash",
                    "input_tokens": 10,
                    "output_tokens": 5,
                    "total_tokens": 15,
                    "api_key": "should-never-enter",
                }
            )
            + "\n",
            encoding="utf-8",
        )
        result = collect_usage_files(self.store, "p", self.root)
        self.assertEqual(len(result.records), 1)
        record = result.records[0]
        self.assertEqual(record["total_tokens"], 15)
        self.assertNotIn("api_key", record)
        # Worker writes canonical facts; verify the record round-trips through the store.
        sample_id = self.store.record_usage_sample(record)
        self.assertTrue(sample_id)
        projection = self.store.projection()
        self.assertEqual(projection["usage_summary"][0]["tokens"], 15)

    def test_usage_collector_ignores_negative_and_non_numeric(self) -> None:
        artifacts = self.root / ".hermes" / "task-artifacts"
        artifacts.mkdir(parents=True)
        (artifacts / "usage.jsonl").write_text(
            json.dumps(
                {
                    "provider": "x",
                    "model": "m",
                    "input_tokens": -1,
                    "output_tokens": "many",
                    "total_tokens": 0,
                }
            )
            + "\n",
            encoding="utf-8",
        )
        result = collect_usage_files(self.store, "p", self.root)
        # total_tokens=0 is a legal explicit zero; input -1 and string dropped.
        self.assertEqual(len(result.records), 1)
        self.assertEqual(result.records[0]["total_tokens"], 0)

    def test_usage_polling_is_idempotent_and_preserves_identical_lines(self) -> None:
        artifacts = self.root / ".hermes" / "task-artifacts"
        artifacts.mkdir(parents=True)
        line = json.dumps(
            {
                "provider": "deepseek",
                "model": "deepseek-v4-flash",
                "input_tokens": 10,
                "output_tokens": 5,
                "total_tokens": 15,
            }
        )
        (artifacts / "usage.jsonl").write_text(line + "\n" + line + "\n", encoding="utf-8")

        first = collect_usage_files(self.store, "p", self.root)
        second = collect_usage_files(self.store, "p", self.root)
        self.assertEqual(len(first.records), 2)
        self.assertEqual(
            [record["sample_id"] for record in first.records],
            [record["sample_id"] for record in second.records],
            "polling the same source must keep stable event identities",
        )
        self.assertEqual(len({record["sample_id"] for record in first.records}), 2)
        for record in first.records + second.records:
            self.store.record_usage_sample(record)
        projection = self.store.projection()
        self.assertEqual(projection["usage_summary"][0]["samples"], 2)
        self.assertEqual(projection["usage_summary"][0]["tokens"], 30)

    def test_usage_jsonl_prepend_keeps_existing_sample_identities(self) -> None:
        artifacts = self.root / ".hermes" / "task-artifacts"
        artifacts.mkdir(parents=True)
        usage_path = artifacts / "usage.jsonl"
        existing = [
            {
                "provider": "deepseek",
                "model": "deepseek-v4-flash",
                "input_tokens": 10,
                "output_tokens": 5,
                "total_tokens": 15,
            },
            {
                "provider": "openai",
                "model": "gpt-5",
                "input_tokens": 20,
                "output_tokens": 10,
                "total_tokens": 30,
            },
        ]
        usage_path.write_text(
            "".join(json.dumps(item) + "\n" for item in existing),
            encoding="utf-8",
        )
        first = collect_usage_files(self.store, "p", self.root)
        for record in first.records:
            self.store.record_usage_sample(record)

        prepended = {
            "provider": "anthropic",
            "model": "claude",
            "input_tokens": 3,
            "output_tokens": 2,
            "total_tokens": 5,
        }
        usage_path.write_text(
            "".join(json.dumps(item) + "\n" for item in [prepended, *existing]),
            encoding="utf-8",
        )
        second = collect_usage_files(self.store, "p", self.root)
        for record in second.records:
            self.store.record_usage_sample(record)

        first_ids = {record["sample_id"] for record in first.records}
        existing_ids_after_prepend = {
            record["sample_id"]
            for record in second.records
            if record["provider"] != "anthropic"
        }
        self.assertEqual(
            first_ids,
            existing_ids_after_prepend,
            "prepending a JSONL event must not change identities of prior usage facts",
        )
        projection = self.store.projection()["usage_summary"]
        self.assertEqual(sum(row["samples"] for row in projection), 3)
        self.assertEqual(sum(row["tokens"] for row in projection), 50)

    def test_source_quality_collector(self) -> None:
        project = _make_git_project(self.root, "quality-demo")
        result = collect_source_quality(self.store, "quality-demo", project)
        self.assertTrue(result.ok)
        self.assertEqual(result.records[0]["quality"], "EXACT_SOURCE")
        repeated = collect_source_quality(self.store, "quality-demo", project)
        self.assertEqual(result.records[0]["row_id"], repeated.records[0]["row_id"])
        self.store.append_quality(result.records[0])
        self.store.append_quality(repeated.records[0])
        self.assertEqual(len(self.store.list_source_quality()), 1)


class SearchRootContainmentTests(unittest.TestCase):
    """A link planted in the searched root is not a boundary — and must not read like one.

    Measured defect: `rglob("*")` on CPython 3.11 walks through a directory link, `is_file()` follows it,
    and the record then cited `linked/hermes_usage.jsonl` while the bytes came from outside the root. The
    guard is the resolved-path containment; these cases convict it with a real link where the host can make
    one and without one everywhere else.
    """

    LINE = json.dumps({"provider": "deepseek", "model": "deepseek-v4-flash",
                       "input_tokens": 40, "output_tokens": 11, "total_tokens": 51})

    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        base = Path(temporary.name)
        self.root = base / "task-artifacts"
        self.root.mkdir()
        # "Outside" means outside the search root the collector is handed, not outside the fixture.
        self.outside = base / "other-project-data"
        self.outside.mkdir()
        (self.outside / "hermes_usage.jsonl").write_text(self.LINE + "\n", encoding="utf-8")

    def _plant_link_to(self, target: Path) -> Path:
        link = self.root / "linked"
        _skip_if_no_link_support(_make_directory_link(link, target))
        self.addCleanup(_remove_directory_link, link)
        return link

    def _honest_row(self) -> Path:
        path = self.root / "usage.jsonl"
        path.write_text(self.LINE + "\n", encoding="utf-8")
        return path

    def test_a_link_out_of_the_search_root_is_refused_not_read(self) -> None:
        self._plant_link_to(self.outside)
        result = collect_usage_files(None, "p", self.root)
        self.assertEqual([], result.records,
                         "bytes from outside the root were turned into canonical records")
        self.assertEqual(1, result.refusals.get("symlink_outside_root"),
                         f"the escape was not counted and named: {result.refusals}")
        sample = result.refusal_samples["symlink_outside_root"]
        self.assertIn("linked", sample, f"the refusal does not locate the link: {sample}")
        self.assertNotIn(str(self.outside), json.dumps(result.refusal_samples),
                         "the refusal leaked the outside absolute path into the reported sample")

    def test_containment_convicts_an_outside_target_without_needing_a_real_link(self) -> None:
        """The CI-portable case, on Linux and Windows alike: the guard reads the resolved path.

        The same fixture that reads cleanly one line below is convicted once resolution reports an outside
        target, so a blanket "refuse everything" fix could not pass this either.
        """
        self._honest_row()
        baseline = collect_usage_files(None, "p", self.root)
        self.assertEqual(1, len(baseline.records),
                         f"the fixture itself is unreadable, so the guard proves nothing: {baseline.refusals}")

        real_resolve = collectors._resolved_path

        def resolves_files_outside(path: Path) -> Path:
            candidate = Path(path)
            return self.outside / candidate.name if candidate.is_file() else real_resolve(candidate)

        collectors._resolved_path = resolves_files_outside
        try:
            result = collect_usage_files(None, "p", self.root)
        finally:
            collectors._resolved_path = real_resolve
        self.assertEqual([], result.records)
        self.assertEqual(1, result.refusals.get("symlink_outside_root"),
                         f"refusals: {result.refusals}")

    def test_a_candidate_that_is_itself_a_link_is_refused_by_name(self) -> None:
        self._honest_row()
        baseline = collect_usage_files(None, "p", self.root)
        self.assertEqual(1, len(baseline.records), "fixture control: a plain file must read")

        real_is_link = collectors._is_link
        collectors._is_link = lambda path: True
        try:
            result = collect_usage_files(None, "p", self.root)
        finally:
            collectors._is_link = real_is_link
        self.assertEqual([], result.records)
        self.assertEqual(1, result.refusals.get("symlink_candidate_refused"),
                         f"refusals: {result.refusals}")

    def test_one_escape_is_counted_once_however_many_files_hang_behind_it(self) -> None:
        """The refusal counts escapes, not the files reached through them -- so it agrees on every platform.

        This is the shape that made CI disagree with every local run: the enumeration descended into the
        link, so the total scaled with the number of files behind it and differed between a POSIX symlink
        and a Windows junction. A count that depends on the walker's platform cannot be evidence about the
        fixture at all.
        """
        for name in ("other_usage.jsonl", "third_usage.jsonl"):
            (self.outside / name).write_text(self.LINE + "\n", encoding="utf-8")
        link = self._plant_link_to(self.outside)
        self.assertEqual(3, len(list(link.glob("*.jsonl"))),
                         "the linked directory itself must hold three readable files for this to mean anything")
        result = collect_usage_files(None, "p", self.root)
        self.assertEqual([], result.records, "bytes behind an escaping link must not be read at all")
        self.assertEqual(1, result.refusals.get("symlink_outside_root"),
                         f"one escape must be one refusal, however many files sit behind it: {result.refusals}")

    def test_a_link_that_stays_inside_the_root_is_cited_by_where_the_bytes_live(self) -> None:
        """`source_ref` must not launder the origin: an inside link is read, and cited by its real location."""
        real = self.root / "real-store"
        real.mkdir()
        (real / "hermes_usage.jsonl").write_text(self.LINE + "\n", encoding="utf-8")
        self._plant_link_to(real)
        result = collect_usage_files(None, "p", self.root)
        self.assertEqual({}, result.refusals, f"an in-root link is not an escape: {result.refusals}")
        cited = {record["source_ref"] for record in result.records}
        self.assertEqual({"real-store/hermes_usage.jsonl"}, cited,
                         "the link's in-root name was recorded instead of where the bytes came from")

    def test_a_measured_refusal_makes_coverage_partial_and_a_clean_read_stays_full(self) -> None:
        self._honest_row()
        self.assertEqual("FULL", collect_usage_files(None, "p", self.root).records[0]["coverage"],
                         "a clean read must not be stamped PARTIAL")
        self._plant_link_to(self.outside)
        result = collect_usage_files(None, "p", self.root)
        self.assertEqual(1, len(result.records),
                         "the honest in-root row must not be collateral damage of the refused neighbour")
        self.assertEqual("PARTIAL", result.records[0]["coverage"])
        self.assertIn("symlink_outside_root", result.records[0]["coverage_why"])


if __name__ == "__main__":
    unittest.main()
