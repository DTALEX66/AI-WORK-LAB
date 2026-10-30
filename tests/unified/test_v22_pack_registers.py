# SPDX-License-Identifier: MIT
"""V22: the semantic mapping register (837 rows) and the design-task register (50 rows)
must reconcile against evidence that exists in this tree, not merely keep their counts.

The audited round was told that 198 rows pointed at a destination that did not exist.
Row-count assertions cannot see that, so the earlier fix added disposition registers and
left ``mapping.csv`` itself claiming only "837 rows, unchanged". These two tests close
that by tying every semantic row to a file the coverage register accounts for, and every
task definition pointer to the bytes it names.
"""
from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

TARGET_ROOT = Path(__file__).resolve().parents[2]
SOURCE_WORK = Path(r"D:\All projects\WORK-LAB")
SOURCE_DESIGN = Path(r"D:\All projects\DESIGN-LAB")


def _read(relative: str) -> list[dict]:
    with open(TARGET_ROOT / relative, encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _covered_paths() -> tuple[set[str], list[str]]:
    exact: set[str] = set()
    for row in _read("migration/source-coverage-work.csv"):
        exact.add("work:" + "/" + row["path"].lstrip("/"))
    for row in _read("migration/source-coverage-design.csv"):
        exact.add("design:" + "/" + row["path"].lstrip("/"))
    # a directory named by the semantic register is covered when files under it are covered
    directories = sorted({key.split(":", 1)[1] for key in exact})
    return exact, directories


def test_every_mapping_row_reconciles_to_a_covered_source_file():
    """L02「历史与当前差异」: each of the 837 semantic entries names a source file, and
    that file must be accounted for in the per-file coverage registers."""
    mapping = _read("migration/mapping.csv")
    assert mapping, "mapping.csv must not be empty"
    exact, covered = _covered_paths()

    unexplained = []
    for row in mapping:
        relative = (row["原路径"] or "").replace("\\", "/").lstrip("/")
        if not relative:
            unexplained.append((row["来源键"], "空 原路径"))
            continue
        key = row["仓"] + ":" + "/" + relative
        if key in exact:
            continue
        prefix = "/" + relative.rstrip("/") + "/"
        if any(path.startswith(prefix) for path in covered):
            continue
        unexplained.append((row["来源键"], relative))
    assert unexplained == [], unexplained[:10]


def test_mapped_target_state_is_a_closed_vocabulary():
    """The 目标状态 column is uniform by design (every semantic entry is registered, none
    is accepted); that is only meaningful while the vocabulary is closed, so pin it."""
    states = {row["目标状态"] for row in _read("migration/mapping.csv")}
    assert states == {"MAPPED_P0"}, states


def test_design_task_definition_pointers_match_their_bytes():
    """L02「50任务定义来源保全」: every recorded path must exist and hash to the recorded
    digest. The frozen originals stay in the read-only source repository — this register
    pins them by SHA-256 rather than copying them and creating a second truth."""
    rows = _read("migration/design-tasks.csv")
    assert len(rows) == 50, len(rows)
    problems = []
    for row in rows:
        relative = (row["定义来源路径"] or "").replace("\\", "/").lstrip("/")
        digest = row["定义来源sha256"]
        if not relative or not digest:
            problems.append((row["原任务ID"], "缺路径或缺摘要"))
            continue
        candidates = [SOURCE_DESIGN / relative, SOURCE_WORK / relative,
                      TARGET_ROOT / relative]
        found = [path for path in candidates if path.is_file()]
        if not found:
            problems.append((row["原任务ID"], "定义原件不存在: " + relative))
            continue
        actual = hashlib.sha256(found[0].read_bytes()).hexdigest()
        if actual != digest:
            problems.append((row["原任务ID"], "摘要不符 " + actual[:12] + " != " + digest[:12]))
    assert problems == [], problems[:10]
