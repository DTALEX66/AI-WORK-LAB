# SPDX-License-Identifier: MIT
"""Generate ``config/blocker-register.json`` from the clause register, for the gate.

``acceptance_gate.py --blockers`` decides batch readiness partly from this file, so the
file must be *derived*: a hand-maintained blocker list drifts the moment a clause is
closed, and the round then either over-reports readiness or keeps a stale blocker. Each
non-CONFIRMED clause of ``migration/task-acceptance.csv`` becomes one item, carrying its
phase and, for owner-boundary refusals, the authority that put it out of scope.
"""
from __future__ import annotations

import argparse
import csv
import datetime
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from published_stamp import keeping_the_recorded_stamp  # noqa: E402

TARGET_ROOT = Path(__file__).resolve().parents[1]
CLAUSES = TARGET_ROOT / "migration" / "task-acceptance.csv"
PACK = TARGET_ROOT / "AI-WORK-LAB_HANDOFF_20261029" / "09_任务分期与验收.json"
OUT = TARGET_ROOT / "config" / "blocker-register.json"

# clause verdict -> register status. PARTIAL and GAP are blocking for a mandatory phase:
# the pack's own completion_rule is 「P0/P1全部通过且无阻断才可交审」, and a partially
# passing clause is not a passing clause.
STATUS_MAP = {"PARTIAL": "PARTIAL", "GAP": "GAP", "BLOCKED_BY_BOUNDARY": "BLOCKED",
              "DEFERRED_P2": "DEFERRED", "DEFERRED_P3": "DEFERRED"}

#: Clauses the owner removed from this batch's duty list. Each carries the authority text
#: so the register never turns an exclusion into an invisible pass.
OWNER_EXCLUDED = {
    ("L00", "可证明的隔离范围"): "交接提示词 §安全边界：不承诺已证明全机绝无外传；"
                                        "系统级出站隔离不在本批义务内",
    ("L20", "真实调用/保存/重开/读回"): "交接提示词 §本批不做：不执行真实 Photoshop/Illustrator "
                                            "文档写入；宿主写操作走 Human Gate",
}


#: The three classes an owner decision can move a pending row into. Each requires a
#: ``file:line`` authority in this tree; the queue below deliberately does not offer a
#: fourth option that would let a row be "decided" by assertion.
DECISION_OPTIONS = ("UNREGISTERED_TARGET_PATH_PRESENT", "UNREGISTERED_EXCLUDED_CAPABILITY",
                    "UNREGISTERED_DEV_TOOLING")

#: Where the rows still awaiting that decision live. Read, never transcribed: the population
#: is the registers', not this script's.
COVERAGE_REGISTERS = (("work", "migration/source-coverage-work.csv"),
                      ("design", "migration/source-coverage-design.csv"))


def owner_queue() -> list[dict]:
    """Enumerate every row the coverage registers still hold for the owner.

    ``L10#0`` is the one mandatory clause that blocks this batch, and it blocks on 32 rows
    that no machine can decide -- but until now the register only *counted* them, so the
    owner had to re-derive the list from two CSVs to answer. The queue puts the rows, their
    bytes and their per-row reason where the blocker already lives.
    """
    queue: list[dict] = []
    for repo, relative in COVERAGE_REGISTERS:
        path = TARGET_ROOT / relative
        if not path.is_file():
            raise SystemExit("coverage register missing, cannot enumerate the owner queue: "
                             + relative)
        with open(path, encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                if row["class"] != "OWNER_DECISION_PENDING":
                    continue
                queue.append(dict(repo=repo, path=row["path"], target=row["target"],
                                  source_sha256=row["source_sha256"], reason=row["reason"]))
    queue.sort(key=lambda item: (item["repo"], item["path"]))
    if len({(item["repo"], item["path"]) for item in queue}) != len(queue):
        raise SystemExit("owner queue has a duplicate row key")
    reasons = [item["reason"] for item in queue]
    if len(set(reasons)) != len(reasons):
        raise SystemExit("owner queue rows share one reason: the per-row adjudication is gone")
    return queue


def build() -> dict:
    pack = json.loads(PACK.read_text(encoding="utf-8-sig"))
    phase_by_task = {task["id"]: task["phase"] for task in pack["tasks"]}
    mandatory = set(pack["mandatory"])
    with open(CLAUSES, encoding="utf-8-sig", newline="") as handle:
        clauses = list(csv.DictReader(handle))

    items: list[dict] = []
    queue = owner_queue()
    for row in clauses:
        verdict = row["结论"]
        if verdict == "CONFIRMED":
            continue
        if verdict not in STATUS_MAP:
            raise SystemExit("unknown clause verdict: " + verdict)
        phase = phase_by_task[row["任务"]]
        excluded = OWNER_EXCLUDED.get((row["任务"], row["条款原文"]))
        item = dict(
            id=row["任务"] + "#" + row["条款序号"],
            task=row["任务"], clause=row["条款原文"], status=STATUS_MAP[verdict],
            phase=phase,
            mandatory=phase in mandatory,
            scope_excluded_by_owner=bool(excluded),
            authority=excluded or ("migration/task-acceptance.csv 结论=" + verdict),
            detail=row["依据与限制"],
        )
        if item["id"] == "L10#0":
            item["decision_options"] = list(DECISION_OPTIONS)
            item["decision_how"] = ("逐行从 decision_options 中任选一个类别，并在 "
                                   "migration/source-coverage-<repo>.csv 的 authority 列补出处"
                                   "（file:line）；改完重跑两个 build 脚本与 "
                                   "tests/unified/test_v14_registers.py。不选 = 本条继续 PARTIAL，"
                                   "本批继续 REFUSED。")
            item["owner_queue"] = queue
        items.append(item)
    return dict(
        generated_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        source="migration/task-acceptance.csv",
        rule="必做阶段(P0/P1)的非通过条款一律阻断本批就绪；owner 明确移出义务的条款"
             "登记为 disclosed 并带出处",
        clauses=len(clauses),
        owner_queue_rows=len(queue),
        items=items,
        counts=dict(
            total=len(items),
            blocking=sum(1 for item in items if item["mandatory"] and not item["scope_excluded_by_owner"]),
            disclosed=sum(1 for item in items if not item["mandatory"]
                          or item["scope_excluded_by_owner"]),
        ),
    )


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json-out")
    parser.add_argument("--check", action="store_true",
                        help="report only; fail if the tracked register differs")
    args = parser.parse_args(argv[1:])

    document = build()
    document = keeping_the_recorded_stamp(OUT, document)
    text = json.dumps(document, ensure_ascii=False, indent=2) + "\n"
    if args.check:
        current = OUT.read_text(encoding="utf-8") if OUT.is_file() else ""
        same = json.loads(current)["items"] == document["items"]
        print(json.dumps(dict(matches=same, items=len(document["items"]),
                              blocking=document["counts"]["blocking"]), ensure_ascii=True))
        return 0 if same else 1
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(text, encoding="utf-8", newline="\n")
    if args.json_out:
        Path(args.json_out).write_text(text, encoding="utf-8", newline="\n")
    read_back = json.loads(OUT.read_text(encoding="utf-8"))
    print(json.dumps(dict(written=str(OUT), items=len(read_back["items"]),
                          blocking=read_back["counts"]["blocking"],
                          disclosed=read_back["counts"]["disclosed"],
                          clauses=read_back["clauses"]), ensure_ascii=True))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
