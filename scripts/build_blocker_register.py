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


def build() -> dict:
    pack = json.loads(PACK.read_text(encoding="utf-8-sig"))
    phase_by_task = {task["id"]: task["phase"] for task in pack["tasks"]}
    mandatory = set(pack["mandatory"])
    with open(CLAUSES, encoding="utf-8-sig", newline="") as handle:
        clauses = list(csv.DictReader(handle))

    items: list[dict] = []
    for row in clauses:
        verdict = row["结论"]
        if verdict == "CONFIRMED":
            continue
        if verdict not in STATUS_MAP:
            raise SystemExit("unknown clause verdict: " + verdict)
        phase = phase_by_task[row["任务"]]
        excluded = OWNER_EXCLUDED.get((row["任务"], row["条款原文"]))
        items.append(dict(
            id=row["任务"] + "#" + row["条款序号"],
            task=row["任务"], clause=row["条款原文"], status=STATUS_MAP[verdict],
            phase=phase,
            mandatory=phase in mandatory,
            scope_excluded_by_owner=bool(excluded),
            authority=excluded or ("migration/task-acceptance.csv 结论=" + verdict),
            detail=row["依据与限制"],
        ))
    return dict(
        generated_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        source="migration/task-acceptance.csv",
        rule="必做阶段(P0/P1)的非通过条款一律阻断本批就绪；owner 明确移出义务的条款"
             "登记为 disclosed 并带出处",
        clauses=len(clauses),
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
