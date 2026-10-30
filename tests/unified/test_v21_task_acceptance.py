# SPDX-License-Identifier: MIT
"""V21: the clause-level acceptance register must be complete, closed-vocabulary and
reproducible — and a CONFIRMED row must survive being re-checked right now.

This is the round's answer to "全部闭环": completion is reported per acceptance clause,
not per task, so one strong test can no longer stand in for a clause it does not cover.
"""
from __future__ import annotations

import csv
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

TARGET_ROOT = Path(__file__).resolve().parents[2]
_SPEC = importlib.util.spec_from_file_location(
    "task_acceptance_builder", TARGET_ROOT / "scripts" / "build_task_acceptance_register.py")
BUILDER = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(BUILDER)

OUT_CSV, PACK, ROWS, STATUSES, _resolve, main = (
    BUILDER.OUT_CSV, BUILDER.PACK, BUILDER.ROWS, BUILDER.STATUSES, BUILDER._resolve,
    BUILDER.main)

VOCABULARY = set(STATUSES)


def _rows() -> list[dict]:
    with open(OUT_CSV, encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def test_register_covers_every_clause_in_the_pack():
    pack = json.loads(PACK.read_text(encoding="utf-8-sig"))
    expected = {(task["id"], index) for task in pack["tasks"]
                for index in range(len(task["acceptance"]))}
    on_disk = {(row["任务"], int(row["条款序号"])) for row in _rows()}
    assert expected == on_disk, ("missing " + str(sorted(expected - on_disk))
                                 + " extra " + str(sorted(on_disk - expected)))
    assert len(expected) == len(ROWS), (len(expected), len(ROWS))


def test_clause_text_is_transcribed_not_paraphrased():
    pack = json.loads(PACK.read_text(encoding="utf-8-sig"))
    clauses = {task["id"]: task["acceptance"] for task in pack["tasks"]}
    for row in _rows():
        assert row["条款原文"] == clauses[row["任务"]][int(row["条款序号"])], row


def test_status_vocabulary_is_closed_and_totals_reconcile():
    rows = _rows()
    bad = [row for row in rows if row["结论"] not in VOCABULARY]
    assert bad == [], bad
    counted = sum(1 for row in rows if row["结论"] in VOCABULARY)
    assert counted == len(rows), (counted, len(rows))


def test_no_mandatory_clause_is_left_a_gap():
    """P0/P1 are the pack's mandatory set (09…json mandatory=["P0","P1"]); a GAP there is
    a real unfinished item, so this test has to be red until it is closed."""
    rows = _rows()
    hard = [row["任务"] + "#" + row["条款序号"] + " " + row["条款原文"]
            for row in rows if row["期"] in ("P0", "P1") and row["结论"] == "GAP"]
    assert hard == [], hard


def test_every_confirmed_row_resolves_on_recheck_right_now():
    """A CONFIRMED row is a claim about this tree, not a transcript of last run: the
    cited test, route, register or tracked file must resolve at the moment of checking."""
    failures = []
    for row in _rows():
        if row["结论"] != "CONFIRMED":
            continue
        resolved, detail = _resolve(row["证据类型"], row["证据目标"])
        if not resolved:
            failures.append(row["任务"] + "#" + row["条款序号"] + " → " + detail)
    assert failures == [], failures


def test_unresolved_evidence_is_downgraded_never_deleted():
    """A CONFIRMED claim whose target cannot be found must be reported, not silently
    dropped: the row stays with the reason prefixed."""
    unresolved = [row for row in _rows() if row["机验结果"].startswith("未解析")]
    for row in unresolved:
        assert row["结论"] in ("PARTIAL", "GAP", "BLOCKED_BY_BOUNDARY", "DEFERRED_P2",
                               "DEFERRED_P3"), row
        assert row["条款原文"].strip(), row


def test_rerunning_the_builder_does_not_change_the_register():
    before = OUT_CSV.read_bytes()
    code = main(["build_task_acceptance_register.py"])
    assert code in (0, 1), code
    after = OUT_CSV.read_bytes()
    assert before == after, "the register is generated, so a rerun must be byte-identical"


DEFERRAL = TARGET_ROOT / "migration" / "deferral-register.json"
DEFERRAL_BUILDER = TARGET_ROOT / "scripts" / "build_deferral_register.py"
DEFERRED_TASK_IDS = {"L20", "L21", "L30", "L31", "L32"}


def test_deferral_register_names_a_real_seam_for_every_deferred_item():
    """L03「延期有来源/依赖/接缝/验收」: a deferral is only a seam if the seam exists.

    Before this file, deferred work was a ``phase`` string in the capability catalog, so
    「保留接入位置」could not be checked at all. Every row therefore names files, and this
    test checks the files, the dependency list and the verbatim acceptance clause.
    """
    document = json.loads(DEFERRAL.read_text(encoding="utf-8-sig"))
    entries = document["entries"]
    assert entries, "deferral register is empty"
    tasks = [entry for entry in entries if entry["kind"] == "task"]
    assert {entry["id"] for entry in tasks} == DEFERRED_TASK_IDS, tasks
    for entry in entries:
        assert entry["seams"], entry
        for seam in entry["seams"]:
            assert (TARGET_ROOT / seam).exists(), (entry["id"], seam)
    for entry in tasks:
        assert entry["depends_on"], entry
        assert entry["acceptance"], entry

    pack = json.loads(PACK.read_text(encoding="utf-8-sig"))
    clauses = {task["id"]: task["acceptance"] for task in pack["tasks"]}
    for entry in tasks:
        assert entry["acceptance"] == clauses[entry["id"]], entry

    check = subprocess.run([sys.executable, str(DEFERRAL_BUILDER), "--check"],
                           cwd=str(TARGET_ROOT), capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=300)
    assert check.returncode == 0, check.stdout + check.stderr
