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
import re
import subprocess
import sys
from pathlib import Path

import pytest

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


def test_check_mode_reproduces_the_register_without_writing_it():
    """A verification run must not be a writer.

    The first version of this test called the builder in its normal mode and compared the
    result, which rewrote a tracked register during the suite — the audited tree went dirty
    mid-measurement, and the register was byte-unstable against any unrelated field added
    to a document it merely cites. --check rebuilds in memory and only compares.
    """
    before = OUT_CSV.read_bytes()
    check = subprocess.run([sys.executable, "-B",
                            str(TARGET_ROOT / "scripts" / "build_task_acceptance_register.py"),
                            "--check"], cwd=str(TARGET_ROOT), capture_output=True,
                           text=True, encoding="utf-8", errors="replace", timeout=600)
    tail = check.stdout.strip().splitlines()[-1] if check.stdout.strip() else ""
    assert '"register_drift": false' in check.stdout, check.stdout[-1200:]
    assert check.returncode == 0, (tail, check.stderr[-500:])
    assert OUT_CSV.read_bytes() == before, "a --check run wrote the tracked register"


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


# --------------------------------------------------------------------------- blocker register

BLOCKERS_OUT = TARGET_ROOT / "config" / "blocker-register.json"
BLOCKERS_BUILDER = TARGET_ROOT / "scripts" / "build_blocker_register.py"
_SPEC_BLOCKERS = importlib.util.spec_from_file_location(
    "blocker_register_builder", BLOCKERS_BUILDER)
BLOCKERS = importlib.util.module_from_spec(_SPEC_BLOCKERS)
_SPEC_BLOCKERS.loader.exec_module(BLOCKERS)

COVERAGE_FILES = (("work", "migration/source-coverage-work.csv"),
                  ("design", "migration/source-coverage-design.csv"))

#: Classes that mean the row has still not been decided -- offered as an option, they would
#: let the owner "close" a row by choosing the word that closes nothing.
NON_DECISION_CLASSES = frozenset({"", "SOURCE_UNREGISTERED", "COPIED_MISSING_IN_TARGET",
                                  "OWNER_DECISION_PENDING"})


def _pending_by_repo() -> dict:
    """Read the pending population straight from the registers, without the builder."""
    out = {}
    for repo, relative in COVERAGE_FILES:
        with open(TARGET_ROOT / relative, encoding="utf-8-sig", newline="") as handle:
            out[repo] = [row for row in csv.DictReader(handle)
                         if row["class"] == "OWNER_DECISION_PENDING"]
    return out


def _l10_item(document: dict) -> dict:
    items = [entry for entry in document["items"] if entry["id"] == "L10#0"]
    assert len(items) == 1, [entry["id"] for entry in document["items"]]
    return items[0]


def test_the_blocking_clause_hands_the_owner_every_pending_row():
    """L10#0 blocks the batch on rows only a person can decide -- so the blocker itself must
    carry those rows, byte-for-batch derived from the coverage registers.

    Before this, the register counted them (32) and the owner had to open two CSVs and filter
    a class to see what was being asked. A count is not a queue: the readiness gate reads this
    file, so the work the gate is waiting on has to be *in* the file the gate reads.
    """
    document = json.loads(BLOCKERS_OUT.read_text(encoding="utf-8"))
    item = _l10_item(document)
    pending = _pending_by_repo()
    expected = sorted((row["repo"], row["path"], row["target"],
                       row["source_sha256"], row["reason"])
                      for rows in pending.values() for row in rows)
    got = sorted((row["repo"], row["path"], row["target"], row["source_sha256"], row["reason"])
                 for row in item["owner_queue"])
    assert got == expected, "queue disagrees with the registers it claims to enumerate"
    assert document["owner_queue_rows"] == len(expected) == len(got)
    assert len({(row["repo"], row["path"]) for row in item["owner_queue"]}) == len(got)
    reasons = [row["reason"] for row in item["owner_queue"]]
    assert len(set(reasons)) == len(reasons), "two rows share one reason"
    for row in item["owner_queue"]:
        assert len(row["source_sha256"]) == 64, row
        assert row["reason"].startswith("待 owner 判定"), row

    mandatory_blocking = [entry["id"] for entry in document["items"]
                          if entry["mandatory"] and not entry["scope_excluded_by_owner"]]
    assert mandatory_blocking == ["L10#0"], mandatory_blocking
    assert document["counts"]["blocking"] == 1, document["counts"]


def test_the_owner_queue_offers_only_classes_the_ladder_can_emit():
    """An option the adjudication ladder cannot emit is a decision that would be written off
    as a class name no register ever produces.

    ``UNREGISTERED_TARGET_PATH_PRESENT`` has no rows today -- a pending row by definition has
    no file at that path yet -- so "already used by some row" is the wrong test. The right one
    is that the class is a return value of ``build_source_coverage.adjudicate_unregistered``,
    which is what the next rebuild reads the owner's decision into.
    """
    document = json.loads(BLOCKERS_OUT.read_text(encoding="utf-8"))
    item = _l10_item(document)
    options = item["decision_options"]
    assert len(set(options)) == len(options) >= 2, options

    ladder = (TARGET_ROOT / "scripts" / "build_source_coverage.py").read_text(encoding="utf-8")
    emittable = set(re.findall(r'return \("([A-Z][A-Z0-9_]+)",', ladder))
    assert len(emittable) >= 3, sorted(emittable)
    invented = [option for option in options if option not in emittable]
    assert invented == [], ("decision options the ladder cannot produce: " + str(invented))
    still_open = [option for option in options if option in NON_DECISION_CLASSES]
    assert still_open == [], ("options that leave the row undecided: " + str(still_open))
    assert item["decision_how"].startswith("逐行从 decision_options"), item["decision_how"]


def test_the_published_blocker_register_is_still_what_the_builder_produces():
    """The gate decides readiness from these bytes: a stale register is a stale verdict."""
    check = subprocess.run([sys.executable, str(BLOCKERS_BUILDER), "--check"],
                           cwd=str(TARGET_ROOT), capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=300)
    assert check.returncode == 0, check.stdout + check.stderr


def test_the_queue_guard_can_actually_fail(monkeypatch, tmp_path):
    """Each refusal must be reachable, or the enumeration is decoration.

    A builder that returns an empty queue when its input register is missing would let the
    single blocking clause quietly lose its rows -- the same shape of bug as a gate that reads
    "no blockers" from an unreadable file.
    """
    fake_root = tmp_path / "root"
    (fake_root / "migration").mkdir(parents=True)
    pending = _pending_by_repo()

    def write(repo: str, rows: list) -> None:
        with open(TARGET_ROOT / ("migration/source-coverage-" + repo + ".csv"),
                  encoding="utf-8-sig", newline="") as handle:
            fieldnames = csv.DictReader(handle).fieldnames
        destination = fake_root / "migration" / ("source-coverage-" + repo + ".csv")
        with destination.open("w", encoding="utf-8", newline="") as out:
            writer = csv.DictWriter(out, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)

    monkeypatch.setattr(BLOCKERS, "TARGET_ROOT", fake_root)

    # 1. a missing register is a refusal, not an empty queue
    write("design", pending["design"])
    with pytest.raises(SystemExit, match="coverage register missing"):
        BLOCKERS.owner_queue()

    # 2. rows that stopped carrying their own reason are refused
    write("work", pending["work"])
    rows = [dict(row) for row in pending["work"]]
    rows[1]["reason"] = rows[0]["reason"]
    write("work", rows)
    with pytest.raises(SystemExit, match="share one reason"):
        BLOCKERS.owner_queue()

    # 3. a duplicated row key is refused (the same file counted twice is not two decisions)
    rows = [dict(row) for row in pending["work"]]
    rows.append(dict(rows[0]))
    write("work", rows)
    with pytest.raises(SystemExit, match="duplicate row key"):
        BLOCKERS.owner_queue()

    # and with the real registers in place the queue is non-empty -- the falsifier above
    # must not be the only thing this function ever proves
    monkeypatch.undo()
    assert BLOCKERS.owner_queue(), "no row enumerated from the tracked registers"
