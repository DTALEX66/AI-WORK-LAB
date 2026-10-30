"""The live open-task register, projected as ``taskRecords``.

Why this module exists (owner readback 2026-10-27: 「现在界面上登记记录的内容 都是假的啊 都给我接入进来啊 我要真实的啊」):
the Work lane's 任务记录 panel has been answering `0 条` because the ONLY source it read was
``canonical_store.tasks``, and that table is empty on this machine (measured 2026-10-27 against the live
store: tasks=0, execution_instances=0, ci_runs=0, usage_samples=0). The tasks that actually exist are
written by hand in `taskpacks/current/OPEN-TASK-REGISTER.md` — the single live open-task register named in
AGENTS.md's mandatory bootstrap — and until now no code in this repository parsed it at all, so 42 real
registrations reached nobody.

Discipline this module is built on:

* **one parser, not two.** Cell splitting and row judgement are imported from
  ``scripts/ci/verify_register_table_shape.py`` — the repository's existing authority for this exact table
  — through ``importlib`` rather than restated here. Two parsers over one register is how a second,
  disagreeing "truth" gets produced; the row count this module reports is additionally reconciled against
  ``scan()`` and a disagreement is an UNREADABLE state, never a quietly different number.
* **shape, not guess.** A table is accepted when its header names the four columns
  ``ID | Priority | Status | Work``. Column positions come from the header, never from an assumed index.
* **escapes are content.** ``\\|`` inside a cell is a pipe in the sentence, not a column boundary. Nine
  rows of this register were historically mis-read that way, and ``cells_of`` is what decides it.
* **verbatim mapping.** Status is the register's own string (``EXECUTED_20261009 / REAL``,
  ``PARTIAL_20261010 / …``). Translating it to 完成/进行中 would drop exactly the information the owner
  wrote. Priority and Work are the cells as written (minus the escape markers).
* **no invented columns.** The register has no timestamp column and no project column, so ``createdAt`` /
  ``updatedAt`` are null and ``projectId`` is the register's OWNER (this repository), never a per-row guess.
* **bounded, and the bound is disclosed.** Work cells are prose: measured 121,257 characters over the 42
  live rows, one cell alone 18,447. A read-only projection re-sent on every snapshot tick cannot carry
  that, so ``register.work`` is a verbatim PREFIX capped at ``WORK_EXCERPT_CHARS``, and every row also
  carries the cell's true length (``workChars``) and whether it was cut (``workTruncated``). A cap applied
  in silence is the same defect as a filter applied in silence.
* **unreadable is a state, not an empty list.** ``[]`` reads as "the register was queried and holds
  nothing"; the front already distinguishes the two, so a missing file, a file with no table, a header that
  is not the register's, a register with zero data rows, or a parser disagreement each yield exactly one
  record whose ``register.state`` is ``UNREADABLE`` and whose ``register.reason`` names the failure.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType
from typing import Any

REGISTER_RELATIVE_PATH = Path("taskpacks/current/OPEN-TASK-REGISTER.md")
# The existing authority for this table's shape. Re-read from disk by the loader below so this module
# never owns a second copy of the splitting rule.
SHAPE_AUTHORITY_RELATIVE_PATH = Path("scripts/ci/verify_register_table_shape.py")
SHAPE_AUTHORITY_MODULE_NAME = "worklab_register_table_shape_authority"

# The four columns the register declares, in this order. Matched case-insensitively against the header.
REGISTER_COLUMNS = ("ID", "Priority", "Status", "Work")

# Projection bound for the Work cell, mirrored by `maxLength` on the same field in
# packages/contracts/schemas/workflow/snapshot-v3.schema.json. The test
# `test_the_excerpt_bound_and_the_schema_max_length_are_the_same_number` is what keeps them one number.
WORK_EXCERPT_CHARS = 600

SOURCE = "OPEN_TASK_REGISTER"
STATE_READ = "READ"
STATE_UNREADABLE = "UNREADABLE"
STATE_ID_CONFLICT = "ID_CONFLICT"

# The register is this repository's own live open-task register (AGENTS.md, mandatory bootstrap item 6).
# Its rows carry no project column, so a per-row project would be invented; the honest attribution is the
# repository that owns the file.
REGISTER_OWNER_PROJECT_ID = "work-lab"

# A row whose status cell is blank states nothing. `UNSTATED` is that, and is deliberately not a translation.
UNSTATED_STATUS = "UNSTATED"
# Marker identities. Each is a statement about the READ, not a task id from the register.
UNREADABLE_MARKER_TASK_ID = "OPEN-TASK-REGISTER-UNREADABLE"


def register_path(root: Path) -> Path:
    """The register file for a repository root."""
    return Path(root) / REGISTER_RELATIVE_PATH


# The shape authority is CODE that lives beside this module, while the register it judges is DATA in
# whatever repository is being read. Resolving the authority from the data root would mean a caller that
# points the projection at a fixture register also silently loses the authority — measured: every such
# call answered UNREADABLE and the tests had to say so out loud before it was fixed.
_MODULE_REPO_ROOT = Path(__file__).resolve().parents[3]


def _load_shape_authority(authority_root: Path) -> ModuleType:
    """Import the repository's register-table shape authority, or raise with the reason."""
    path = Path(authority_root) / SHAPE_AUTHORITY_RELATIVE_PATH
    if not path.is_file():
        raise OSError(f"shape authority missing: {path.as_posix()}")
    spec = importlib.util.spec_from_file_location(SHAPE_AUTHORITY_MODULE_NAME, path)
    if spec is None or spec.loader is None:
        raise OSError(f"shape authority not importable: {path.as_posix()}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    for name in ("scan", "cells_of", "SEPARATOR"):
        if not hasattr(module, name):
            raise OSError(f"shape authority lost `{name}`: {path.as_posix()}")
    return module


def _unescape(cell: str) -> str:
    r"""`\|` is a pipe inside the sentence. `cells_of` kept it so the split could see it; the reader must not."""
    return cell.replace("\\|", "|").strip()


def realign(cells: list[str], column_count: int) -> tuple[list[str], bool]:
    """Bring one row back to the width its own header declared, keeping every character.

    A row wider than the header is the historical defect (an unescaped pipe inside backticked shell text):
    the surplus belongs to the LAST column, so it is rejoined with ` | ` rather than dropped and the row is
    marked realigned. A narrower row is padded with empty cells — empty means the register said nothing,
    which is not the same as a guess.
    """
    if len(cells) == column_count:
        return cells, False
    if len(cells) > column_count:
        head = cells[: column_count - 1]
        tail = " | ".join(cells[column_count - 1:])
        return head + [tail], True
    return cells + [""] * (column_count - len(cells)), True


def excerpt(text: str) -> tuple[str, int, bool]:
    """(verbatim prefix, true character count, was it cut) for one prose cell."""
    return text[:WORK_EXCERPT_CHARS], len(text), len(text) > WORK_EXCERPT_CHARS


def register_task_record(*, cells: list[str], line: int, column_count: int,
                         project_id: str = REGISTER_OWNER_PROJECT_ID,
                         state: str = STATE_READ) -> dict[str, Any]:
    """One parsed table row -> one `taskRecords` entry.

    The store-only fields are null/empty because a register row IS not a `tasks` table row: it has no
    lease, no fencing token, no checkpoint. Saying `checkpointPresent: false` with no keys and no digest is
    the truthful answer, and it is also what `snapshot_validator` demands of a checkpoint-less record.
    """
    # A record always needs the four register slots; a caller that names fewer columns than the register
    # declares is answered with blanks (marked realigned), not with an IndexError in the read path.
    width = max(int(column_count), len(REGISTER_COLUMNS))
    values, realigned = realign([_unescape(cell) for cell in cells], width)
    task_id = values[0]
    reason: str | None = None
    if not task_id:
        # An ID-less row cannot be addressed. The marker names the LINE so the reader can find the row in
        # the file; the register's own text is still carried instead of being thrown away.
        reason = "登记行缺少 ID，定位符由行号生成"
        task_id = f"REGISTER-ROW-L{line}"
    status = values[2] or UNSTATED_STATUS
    if not values[2]:
        reason = "登记行 Status 为空" if reason is None else f"{reason}；登记行 Status 为空"
    work, work_chars, work_truncated = excerpt(values[3])
    if realigned:
        note = "该行单元格数与表头声明的列数不一致，多余内容已并回 Work 列"
        reason = note if reason is None else f"{reason}；{note}"
    return {
        "taskId": task_id,
        "projectId": project_id,
        "status": status,
        "createdAt": None,
        "updatedAt": None,
        "leaseHolder": None,
        "leaseExpiresAt": None,
        "fencingToken": None,
        "checkpointPresent": False,
        "checkpointKeys": [],
        "checkpointDigest": None,
        "register": {
            "source": SOURCE,
            "state": state,
            "priority": values[1] or None,
            "work": work,
            "workChars": work_chars,
            "workTruncated": work_truncated,
            "cellsRealigned": realigned,
            "evidenceRef": f"{REGISTER_RELATIVE_PATH.as_posix()}#L{line}",
            "reason": reason,
        },
    }


def _marker_record(*, task_id: str, status: str, state: str, reason: str,
                   evidence_ref: str) -> dict[str, Any]:
    """A record about the read itself — unreadable, or an id that collides with the tasks table."""
    return {
        "taskId": task_id,
        "projectId": REGISTER_OWNER_PROJECT_ID,
        "status": status,
        "createdAt": None,
        "updatedAt": None,
        "leaseHolder": None,
        "leaseExpiresAt": None,
        "fencingToken": None,
        "checkpointPresent": False,
        "checkpointKeys": [],
        "checkpointDigest": None,
        "register": {
            "source": SOURCE,
            "state": state,
            "priority": None,
            "work": "",
            "workChars": 0,
            "workTruncated": False,
            "cellsRealigned": False,
            "evidenceRef": evidence_ref,
            "reason": reason,
        },
    }


def unreadable_marker(reason: str, *, evidence_ref: str | None = None) -> dict[str, Any]:
    return _marker_record(task_id=UNREADABLE_MARKER_TASK_ID, status=STATE_UNREADABLE,
                          state=STATE_UNREADABLE, reason=reason,
                          evidence_ref=evidence_ref or REGISTER_RELATIVE_PATH.as_posix())


def id_conflict_marker(task_id: str, reason: str) -> dict[str, Any]:
    return _marker_record(task_id=f"OPEN-TASK-REGISTER-CONFLICT-{task_id}", status=STATE_ID_CONFLICT,
                          state=STATE_ID_CONFLICT, reason=reason,
                          evidence_ref=REGISTER_RELATIVE_PATH.as_posix())


def merge_task_rows(store_rows: list[dict[str, Any]],
                    register_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Store rows first, then the register's — with no silent loser when an id repeats.

    ``snapshot_validator`` refuses a duplicate ``taskId`` in ``taskRecords`` outright, so a collision
    cannot be shipped as two rows. Deleting the register row quietly is the ERR-256 shape (a filter nobody
    declared), so the colliding row is replaced by a marker record that names the id it lost to: the count
    still matches the register, and the reason is in the snapshot rather than in the code path.
    """
    store_ids = {str(row.get("taskId") or "") for row in store_rows}
    owned = set(store_ids)
    merged: list[dict[str, Any]] = list(store_rows)
    for record in register_rows:
        task_id = str(record.get("taskId") or "")
        if record["register"]["state"] == STATE_READ and task_id in owned:
            source = "canonical tasks 表" if task_id in store_ids else "登记表的前一行"
            merged.append(id_conflict_marker(
                task_id, f"登记行 `{task_id}` 与{source}的同 id 记录冲突，登记行未投影"))
            continue
        owned.add(task_id)
        merged.append(record)
    return merged


def parse_register(text: str, *, authority_root: Path = _MODULE_REPO_ROOT) -> tuple[list[dict[str, Any]], str, str | None]:
    """(taskRecords, state, reason) for the register's own text.

    `state` is `READ` only when the authoritative shape parser and this module's walk agree on the row
    count and the header names the four register columns.
    """
    try:
        authority = _load_shape_authority(Path(authority_root))
    except Exception as error:  # noqa: BLE001 - an unavailable authority is reported, never substituted
        return [unreadable_marker(f"权威解析器不可用:{type(error).__name__}:{error}")], STATE_UNREADABLE, \
            "shape-authority-unavailable"

    _, tables, scanned_rows = authority.scan(text)
    if not tables:
        reason = "文件中没有竖线表格"
        return [unreadable_marker(reason)], STATE_UNREADABLE, reason
    if scanned_rows == 0:
        # Same refusal as `verify_register_table_shape.py:74-77`: a header with no rows is not a register.
        reason = "表格没有数据行（tables 有表头、rows=0）"
        return [unreadable_marker(reason)], STATE_UNREADABLE, reason

    header: list[str] | None = None
    expected: int | None = None
    raw: list[tuple[int, list[str]]] = []
    for number, line in enumerate(text.splitlines(), 1):
        stripped = line.strip()
        if not stripped.startswith("|"):
            expected = None
            continue
        if authority.SEPARATOR.match(stripped):
            continue
        cells = authority.cells_of(stripped)
        if expected is None:
            expected = len(cells)
            header = cells
            continue
        raw.append((number, cells))

    # Judged before anything is mapped: a header that is not the register's has no Work column to write
    # into, and mapping it anyway is how a foreign table gets read as a task list.
    if header is None or [c.lower() for c in header] != [c.lower() for c in REGISTER_COLUMNS]:
        reason = f"表头不是 `{' | '.join(REGISTER_COLUMNS)}`，实际是 `{' | '.join(header or [])}`"
        return [unreadable_marker(reason)], STATE_UNREADABLE, reason
    if len(raw) != scanned_rows:
        reason = f"解析行数 {len(raw)} 与权威行数 {scanned_rows} 不一致"
        return [unreadable_marker(reason)], STATE_UNREADABLE, reason
    rows = [register_task_record(cells=cells, line=number, column_count=len(header))
            for number, cells in raw]
    return rows, STATE_READ, None


def load_register_task_records(root: Path,
                               *, authority_root: Path = _MODULE_REPO_ROOT,
                               ) -> tuple[list[dict[str, Any]], str, str | None]:
    """(taskRecords, state, reason) read from a repository's live register.

    `root` is the data root whose `taskpacks/current/OPEN-TASK-REGISTER.md` is read (a test may point it at
    a fixture tree); `authority_root` is where the shared shape authority lives and defaults to this
    module's own repository, because the authority is code rather than data.

    Never returns an empty list: a register that could not be read answers with one marker record, and a
    register that was read answers with one record per row its own header declared.
    """
    path = register_path(root)
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as error:
        reason = f"登记表不可读:{error.strerror or type(error).__name__}"
        return [unreadable_marker(reason, evidence_ref=path.as_posix())], STATE_UNREADABLE, reason
    except UnicodeDecodeError:
        reason = "登记表不是 UTF-8 文本"
        return [unreadable_marker(reason, evidence_ref=path.as_posix())], STATE_UNREADABLE, reason
    return parse_register(text, authority_root=authority_root)
