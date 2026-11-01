"""Gate: the live open-task register reaches the snapshot as `taskRecords` — one record per real row.

Owner readback 2026-10-27: the Work lane showed 0 条 task records while `taskpacks/current/OPEN-TASK-REGISTER.md`
held 42 registrations. The panel was honest about the store it DID read (`canonical_store.tasks` is empty on
this machine — measured 2026-10-27: tasks=0, execution_instances=0, ci_runs=0, usage_samples=0); what was
missing is that the register, the artifact AGENTS.md names as this repository's single live open-task
register, was parsed by nobody.

The rules this file refuses to let anyone re-break:

* **the count comes from the table.** A fixture register with three rows produces three records and a
  fourth row produces a fourth record. Nothing here pins 42 — 42 is a reading of a file that grows.
* **one parser.** The row count asserted against the register is the count produced by
  `scripts/ci/verify_register_table_shape.py::scan`, the repository's existing shape authority. If this
  module and that file ever disagree, the disagreement is the red.
* **escapes are content.** `\\|` inside a Work cell does not create a column (the defect that nine rows of
  this register historically had); an UNescaped extra pipe is rejoined into the last column and the row
  says it was realigned rather than being dropped.
* **unreadable is never `[]`.** `[]` means "the register was queried and holds nothing", and the Observer
  already renders that differently from "the field is absent". A missing file, a file with no table, a
  header that is not the register's, and a zero-row table each answer with one marker record naming the
  reason.
* **no invented facts.** No timestamp column exists in the register, so `createdAt`/`updatedAt` are null;
  no project column exists, so rows are attributed to the repository that owns the register; the Work cell
  is a disclosed prefix of the prose, with the true character count next to it.
"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "packages" / "client-neutral-core" / "scripts"))
sys.path.insert(0, str(ROOT / "services" / "orchestration"))

import open_task_register_projection as register_projection  # noqa: E402
import snapshot_api  # noqa: E402
import snapshot_validator  # noqa: E402
from canonical_store import CanonicalStore  # noqa: E402
from jsonschema import Draft202012Validator  # noqa: E402
from project_temp import fixture_dir, force_release  # noqa: E402

SCHEMA_PATH = ROOT / "packages/contracts/schemas/workflow/snapshot-v3.schema.json"
LIVE_REGISTER = ROOT / "taskpacks/current/OPEN-TASK-REGISTER.md"

HEADER = "| ID | Priority | Status | Work |\n|---|---|---|---|\n"


def register_text(*rows: str) -> str:
    return f"# 登记\n\n{HEADER}{''.join(row + chr(10) for row in rows)}"


def authority_row_count(text: str, root: Path = ROOT) -> int:
    """The row count the repository's existing shape authority sees in this text."""
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "authority_for_test", root / register_projection.SHAPE_AUTHORITY_RELATIVE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return int(module.scan(text)[2])


def schema_validator() -> Draft202012Validator:
    return Draft202012Validator(json.loads(SCHEMA_PATH.read_text(encoding="utf-8")))


class ParsedRowCountTests(unittest.TestCase):
    def setUp(self) -> None:
        self.root = fixture_dir(prefix="register-parse-")
        (self.root / register_projection.REGISTER_RELATIVE_PATH).parent.mkdir(parents=True, exist_ok=True)

    def tearDown(self) -> None:
        force_release(self.root)

    def write(self, text: str) -> Path:
        (self.root / register_projection.REGISTER_RELATIVE_PATH).write_text(text, encoding="utf-8")
        return self.root

    def test_three_rows_produce_three_records_and_a_fourth_row_produces_a_fourth(self) -> None:
        root = self.write(register_text(
            "| W-01 | P0 | OPEN_20261027 | 第一条 |",
            "| W-02 | P1 | EXECUTED_20261026 | 第二条 |",
            "| W-03 | P2 | BLOCKED_20261027 | 第三条 |"))
        rows, state, reason = register_projection.load_register_task_records(root)
        self.assertEqual(state, register_projection.STATE_READ, reason)
        self.assertEqual([row["taskId"] for row in rows], ["W-01", "W-02", "W-03"])

        # The count is a reading of the table: grow the table and the projection grows with it.
        root = self.write(register_text(
            "| W-01 | P0 | OPEN_20261027 | 第一条 |",
            "| W-02 | P1 | EXECUTED_20261026 | 第二条 |",
            "| W-03 | P2 | BLOCKED_20261027 | 第三条 |",
            "| W-04 | P0 | OPEN_20261027 | 第四条 |"))
        rows, state, reason = register_projection.load_register_task_records(root)
        self.assertEqual(state, register_projection.STATE_READ, reason)
        self.assertEqual(len(rows), 4)
        self.assertEqual(len(rows), authority_row_count(
            (root / register_projection.REGISTER_RELATIVE_PATH).read_text(encoding="utf-8"), ROOT))

    def test_every_column_is_mapped_verbatim_and_nothing_is_translated(self) -> None:
        status = "PARTIAL_20261010 / 角色密度已解决；剩余为控制资源未判定"
        root = self.write(register_text(f"| CL-16 | P1 | {status} | 动效层，依赖 WUI-07；先出承接表 |"))
        row = register_projection.load_register_task_records(root)[0][0]
        self.assertEqual(row["taskId"], "CL-16")
        self.assertEqual(row["status"], status, "the Status cell must arrive as written, not summarised")
        self.assertEqual(row["register"]["priority"], "P1")
        self.assertEqual(row["register"]["work"], "动效层，依赖 WUI-07；先出承接表")
        self.assertEqual(row["register"]["workTruncated"], False)
        self.assertEqual(row["register"]["workChars"], len("动效层，依赖 WUI-07；先出承接表"))

    def test_no_timestamp_lease_or_checkpoint_is_invented_for_a_register_row(self) -> None:
        root = self.write(register_text("| X-01 | P0 | OPEN | 正文 |"))
        row = register_projection.load_register_task_records(root)[0][0]
        self.assertIsNone(row["createdAt"], "the register has no created column")
        self.assertIsNone(row["updatedAt"], "the register has no updated column")
        self.assertIsNone(row["leaseHolder"])
        self.assertIsNone(row["leaseExpiresAt"])
        self.assertIsNone(row["fencingToken"])
        self.assertIsNone(row["checkpointDigest"])
        self.assertFalse(row["checkpointPresent"])
        self.assertEqual(row["checkpointKeys"], [])
        # The register carries no project column: the honest attribution is the owning repository.
        self.assertEqual(row["projectId"], register_projection.REGISTER_OWNER_PROJECT_ID)

    def test_an_escaped_pipe_stays_inside_the_work_cell(self) -> None:
        root = self.write(register_text(
            r"| X-02 | P0 | OPEN | 执行 `git rev-parse HEAD \| wc -l` 取证 |"))
        rows, state, reason = register_projection.load_register_task_records(root)
        self.assertEqual(state, register_projection.STATE_READ, reason)
        self.assertEqual(len(rows), 1, "an escaped pipe was read as an extra column")
        self.assertEqual(rows[0]["taskId"], "X-02")
        self.assertEqual(rows[0]["register"]["work"], "执行 `git rev-parse HEAD | wc -l` 取证")
        self.assertFalse(rows[0]["register"]["cellsRealigned"])

    def test_an_unescaped_extra_pipe_is_rejoined_and_declared(self) -> None:
        # The historical defect: an unescaped `|` inside backticks splits the row into five cells.
        root = self.write(register_text("| X-03 | P0 | OPEN | 执行 `git status | head` |"))
        rows, state, reason = register_projection.load_register_task_records(root)
        self.assertEqual(state, register_projection.STATE_READ, reason)
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertTrue(row["register"]["cellsRealigned"],
                        "a row wider than its header was reshaped without saying so")
        self.assertIn("git status | head", row["register"]["work"])
        self.assertEqual(row["taskId"], "X-03")
        self.assertEqual(row["status"], "OPEN")

    def test_the_work_excerpt_is_bounded_and_the_bound_is_declared(self) -> None:
        long_text = "证据" * 900  # 1800 characters
        root = self.write(register_text(f"| X-04 | P0 | OPEN | {long_text} |"))
        row = register_projection.load_register_task_records(root)[0][0]
        register = row["register"]
        cap = register_projection.WORK_EXCERPT_CHARS
        self.assertEqual(register["work"], long_text[:cap])
        self.assertEqual(register["workChars"], len(long_text), "the true length was not disclosed")
        self.assertTrue(register["workTruncated"])

    def test_the_excerpt_bound_and_the_schema_max_length_are_the_same_number(self) -> None:
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        declared = schema["properties"]["taskRecords"]["items"]["properties"]["register"]["properties"]["work"]
        self.assertEqual(declared["maxLength"], register_projection.WORK_EXCERPT_CHARS,
                         "the projection cap and the contract cap drifted into two different numbers")


class UnreadableRegisterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.root = fixture_dir(prefix="register-unreadable-")

    def tearDown(self) -> None:
        force_release(self.root)

    def assert_marker(self, rows: list[dict[str, Any]], state: str, reason: str | None) -> None:
        self.assertEqual(state, register_projection.STATE_UNREADABLE)
        self.assertNotEqual(rows, [], "an unreadable register answered with the empty list, which reads "
                                      "to the Observer as 'queried, nothing registered'")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["register"]["state"], register_projection.STATE_UNREADABLE)
        self.assertTrue(rows[0]["register"]["reason"], "the marker named no reason")
        self.assertEqual(rows[0]["taskId"], register_projection.UNREADABLE_MARKER_TASK_ID)
        self.assertIn(reason, str(rows[0]["register"]["reason"]))

    def test_a_missing_file_is_unreadable_not_empty(self) -> None:
        rows, state, reason = register_projection.load_register_task_records(self.root)
        self.assert_marker(rows, state, reason or "")

    def test_a_file_with_no_table_is_unreadable_not_empty(self) -> None:
        path = self.root / register_projection.REGISTER_RELATIVE_PATH
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("# 登记\n\n今天没有表格，只有一段话。\n", encoding="utf-8")
        rows, state, reason = register_projection.load_register_task_records(self.root)
        self.assert_marker(rows, state, reason or "")

    def test_a_header_that_is_not_the_register_is_unreadable(self) -> None:
        path = self.root / register_projection.REGISTER_RELATIVE_PATH
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("| ID | Status | Work |\n|---|---|---|\n| A-1 | OPEN | 少了一列 |\n", encoding="utf-8")
        rows, state, reason = register_projection.load_register_task_records(self.root)
        self.assert_marker(rows, state, reason or "")

    def test_a_header_with_no_rows_is_unreadable_like_the_shape_authority_calls_it(self) -> None:
        """`verify_register_table_shape.py` refuses rows=0; a projection that accepted it would disagree."""
        path = self.root / register_projection.REGISTER_RELATIVE_PATH
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(HEADER, encoding="utf-8")
        rows, state, reason = register_projection.load_register_task_records(self.root)
        self.assert_marker(rows, state, reason or "")
        self.assertEqual(authority_row_count(path.read_text(encoding="utf-8")), 0)

    def test_blank_id_and_blank_status_are_marked_not_invented_as_a_date(self) -> None:
        path = self.root / register_projection.REGISTER_RELATIVE_PATH
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(register_text("|  | P0 |  | 没有编号也没有状态的一行 |"), encoding="utf-8")
        rows, state, reason = register_projection.load_register_task_records(self.root)
        self.assertEqual(state, register_projection.STATE_READ, reason)
        self.assertEqual(len(rows), 1)
        self.assertTrue(rows[0]["taskId"].startswith("REGISTER-ROW-L"),
                        f"a row with no ID got an invented-looking identifier: {rows[0]['taskId']}")
        self.assertEqual(rows[0]["status"], register_projection.UNSTATED_STATUS)
        self.assertTrue(rows[0]["register"]["reason"])


class SnapshotWiringTests(unittest.TestCase):
    """The parsed rows have to survive the real contract, not just the parser's own shape."""

    def test_records_validate_against_the_v3_schema_and_the_semantic_validator(self) -> None:
        rows, state, reason = register_projection.load_register_task_records(ROOT)
        self.assertEqual(state, register_projection.STATE_READ, reason)
        snapshot = snapshot_api.build_snapshot(revision=3, projects=[], task_records=rows)
        errors = [error.message for error in schema_validator().iter_errors(snapshot)]
        self.assertEqual([], errors)
        verdict = snapshot_validator.validate_snapshot(snapshot)
        self.assertTrue(verdict["valid"], verdict["errors"])

    def test_the_live_register_count_reaches_the_snapshot_and_matches_the_shape_authority(self) -> None:
        """What the owner has to be able to count: N registrations in, N records out."""
        rows, state, reason = register_projection.load_register_task_records(ROOT)
        self.assertEqual(state, register_projection.STATE_READ, reason)
        live_rows = authority_row_count(LIVE_REGISTER.read_text(encoding="utf-8"))
        self.assertGreater(live_rows, 0, "the live register parsed to nothing — the gate is reading air")
        self.assertEqual(len(rows), live_rows)
        snapshot = snapshot_api.build_snapshot(revision=4, projects=[], task_records=rows)
        self.assertEqual(len(snapshot["taskRecords"]), live_rows)

    def test_every_live_record_points_at_a_line_that_actually_holds_that_id(self) -> None:
        """Anti-fabrication: re-read the cited line and find the row's own identifier in it."""
        lines = LIVE_REGISTER.read_text(encoding="utf-8").splitlines()
        rows, state, _reason = register_projection.load_register_task_records(ROOT)
        self.assertEqual(state, register_projection.STATE_READ)
        for row in rows:
            if not row["taskId"].startswith("REGISTER-ROW-L"):
                self.assertIn(row["taskId"], lines[int(row["register"]["evidenceRef"].rsplit("#L", 1)[1]) - 1])

    def test_a_conflicting_id_becomes_a_named_marker_instead_of_a_duplicate_or_a_drop(self) -> None:
        rows, state, reason = register_projection.load_register_task_records(ROOT)
        self.assertEqual(state, register_projection.STATE_READ, reason)
        stolen = rows[1]["taskId"]
        store_rows = [snapshot_api.project_task_record(
            {"task_id": stolen, "project_id": "work-lab", "status": "RUNNING"})]
        merged = register_projection.merge_task_rows(store_rows, rows)
        self.assertEqual(len(merged), len(rows) + 1, "a colliding row vanished instead of being declared")
        markers = [row for row in merged if row.get("register", {}).get("state")
                   == register_projection.STATE_ID_CONFLICT]
        self.assertEqual(len(markers), 1)
        self.assertIn(stolen, markers[0]["register"]["reason"])
        snapshot = snapshot_api.build_snapshot(revision=5, projects=[], task_records=merged)
        verdict = snapshot_validator.validate_snapshot(snapshot)
        self.assertTrue(verdict["valid"], "duplicate taskIds reached the validator: " + str(verdict["errors"]))

    def test_the_semantic_validator_refuses_a_truncation_claim_that_does_not_match_the_text(self) -> None:
        rows, state, _reason = register_projection.load_register_task_records(ROOT)
        self.assertEqual(state, register_projection.STATE_READ)
        candidate = next(row for row in rows if row["register"]["workTruncated"])
        tampered = dict(candidate)
        tampered["register"] = {**candidate["register"], "workTruncated": False}
        verdict = snapshot_validator.validate_snapshot(
            snapshot_api.build_snapshot(revision=6, projects=[], task_records=[tampered]))
        self.assertFalse(verdict["valid"], "a row claimed its prose was complete and the validator agreed")
        self.assertIn("workTruncated", " ".join(verdict["errors"]))

    def test_the_semantic_validator_refuses_a_marker_that_names_no_reason(self) -> None:
        marker = register_projection.unreadable_marker("")
        verdict = snapshot_validator.validate_snapshot(
            snapshot_api.build_snapshot(revision=7, projects=[], task_records=[marker]))
        self.assertFalse(verdict["valid"], "an unexplained gap passed the semantic gate")

    def test_an_ordinary_row_is_never_mistaken_for_a_marker(self) -> None:
        rows, state, reason = register_projection.load_register_task_records(ROOT)
        self.assertEqual(state, register_projection.STATE_READ, reason)
        self.assertEqual([row for row in rows if row["register"]["state"] != register_projection.STATE_READ],
                         [])

    def test_the_store_side_of_the_list_is_kept_beside_the_register_not_replaced_by_it(self) -> None:
        rows, state, _reason = register_projection.load_register_task_records(ROOT)
        self.assertEqual(state, register_projection.STATE_READ)
        store_rows = [snapshot_api.project_task_record(
            {"task_id": "WL-LEDGER-001", "project_id": "work-lab", "status": "RUNNING"})]
        merged = register_projection.merge_task_rows(store_rows, rows)
        self.assertEqual(merged[0]["taskId"], "WL-LEDGER-001")
        self.assertNotIn("register", merged[0], "a canonical tasks row was tagged as register-sourced")
        self.assertEqual(len(merged), len(rows) + 1)


class CompositionRootTests(unittest.TestCase):
    """`_task_rows(store)` is what `build_v3_snapshot` feeds the snapshot, so pin the whole call."""

    def setUp(self) -> None:
        import composition_root

        self.composition_root = composition_root
        self.root = fixture_dir(prefix="register-composition-")
        (self.root / register_projection.REGISTER_RELATIVE_PATH).parent.mkdir(parents=True, exist_ok=True)
        composition_root.clear_register_projection_cache()

    def tearDown(self) -> None:
        self.composition_root.clear_register_projection_cache()
        force_release(self.root)

    def test_the_snapshot_row_count_grows_with_the_fixture_table_not_with_a_constant(self) -> None:
        first = register_text("| A-01 | P0 | OPEN | 一 |", "| A-02 | P0 | OPEN | 二 |")
        (self.root / register_projection.REGISTER_RELATIVE_PATH).write_text(first, encoding="utf-8")
        store = CanonicalStore(self.root / "canonical.sqlite")
        try:
            count_two = len(self.composition_root._task_rows(store, root=self.root))
            (self.root / register_projection.REGISTER_RELATIVE_PATH).write_text(
                first + "| A-03 | P1 | OPEN | 三 |\n", encoding="utf-8")
            count_three = len(self.composition_root._task_rows(store, root=self.root))
        finally:
            store.close()
        self.assertEqual(count_two, 2)
        self.assertEqual(count_three, 3)

    def test_an_unreadable_register_reaches_the_snapshot_as_a_marker_not_as_zero_rows(self) -> None:
        store = CanonicalStore(self.root / "canonical.sqlite")
        try:
            rows = self.composition_root._task_rows(store, root=self.root)
        finally:
            store.close()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["register"]["state"], register_projection.STATE_UNREADABLE)

    def test_build_v3_snapshot_publishes_the_register_through_task_records(self) -> None:
        (self.root / register_projection.REGISTER_RELATIVE_PATH).write_text(
            register_text("| B-01 | P0 | OPEN_20261027 | 正文 |"), encoding="utf-8")
        store = CanonicalStore(self.root / "canonical.sqlite")
        try:
            store.register_project("work-lab", str(ROOT), display_name="WORK-LAB")
            snapshot = self.composition_root.build_v3_snapshot(
                store, self.composition_root.load_approved_index(store), revision=9,
                register_root=self.root)
        finally:
            store.close()
        self.assertEqual([row["taskId"] for row in snapshot["taskRecords"]], ["B-01"])
        errors = [error.message for error in schema_validator().iter_errors(snapshot)]
        self.assertEqual([], errors, "the snapshot built through the composition root broke its contract")
        self.assertTrue(snapshot_validator.validate_snapshot(snapshot)["valid"])


if __name__ == "__main__":
    unittest.main()
