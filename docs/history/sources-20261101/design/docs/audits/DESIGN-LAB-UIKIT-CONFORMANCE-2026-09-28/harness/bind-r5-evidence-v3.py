#!/usr/bin/env python
# SPDX-License-Identifier: MIT
"""Bind the two receipts that the `apps` allowlist change unblocks (rev 3).

Before the reporting.py change, NO receipt could cite apps/workbench/**, so the
R5 ledger could not record a single front-end fact. With owner intent granted
("加入，全部开始"), these two receipts become bindable:

  * DL-R5-028  language governance / strict-TS + build-output strategy
  * DL-R5-010  workbench execute / modify / cancel / export

Contract constraints honoured (r5_contract.py): frozen fields untouched;
reassessment != REVIEWED forbids PASS/IMPLEMENTED_LOCAL, so axis states stay
PARTIAL -- these record what was verified, never that a task is complete.
KINDS (reporting.py:31): implementation accepts local_test; unit requires it.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(r"D:\All projects\DESIGN-LAB")
LEDGER = ROOT / "design-lab/config/task-ledger-r3.json"
SURVEY = ".project-local/task-artifacts/project-survey-2026-09-27/PROJECT-SURVEY-2026-09-27.md"
SUBJECT_SHA = "634071f3c8ffa87e08fa1386f49c185ff6fa36d8"


def sha(rel: str) -> str:
    h = hashlib.sha256()
    with (ROOT / rel).open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


OBS = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
survey_hash = sha(SURVEY)

RECEIPTS = [
    {
        "id": "r5-workbench-strict-ts-build-truth-20260927",
        "task_ids": ["DL-R5-028"],
        "kind": "local_test",
        "outcome": "PARTIAL",
        "subject_sha": SUBJECT_SHA,
        "binding": "COMMIT",
        "observed_at": OBS,
        "software": {
            "node": "v24.18.1",
            "typescript": "~5.6.3",
            "vite": "6.4.3",
            "runner": "node node_modules/typescript/bin/tsc --noEmit; node node_modules/vite/bin/vite.js build; node tests/unit.mjs; node tests/appshell.mjs",
            "os": "Windows",
        },
        "subject_files": {
            "apps/workbench/tsconfig.json": sha("apps/workbench/tsconfig.json"),
            "apps/workbench/package.json": sha("apps/workbench/package.json"),
            "apps/workbench/vite.config.ts": sha("apps/workbench/vite.config.ts"),
        },
        "artifacts": [
            {"path": "apps/workbench/build/main.js", "sha256": sha("apps/workbench/build/main.js")},
            {"path": SURVEY, "sha256": survey_hash},
        ],
        "note": (
            "在 634071f 实测：strict TypeScript typecheck exit 0；Vite build exit 0；"
            "node tests/unit.mjs 与 tests/appshell.mjs 全绿。构建产物真值面由 required check "
            "'Workbench strict-TS product gate' 与 'Generated-artifact clean-tree gate' 双重守卫"
            "（后者要求全树干净，故 apps/workbench/build/main.js 必须与源码同提交）。"
            "PARTIAL：非全语言迁移；Ruff 是否 enforce 仍未决策。"
            "本 receipt 直到 `apps` 被加入 reporting.py 的证据根 allowed 集合后才可绑定。"
        ),
    },
    {
        "id": "r5-workbench-native-task-ui-tests-20260927",
        "task_ids": ["DL-R5-010"],
        "kind": "local_test",
        "outcome": "PARTIAL",
        "subject_sha": SUBJECT_SHA,
        "binding": "COMMIT",
        "observed_at": OBS,
        "software": {
            "python": "3.13.14 (project .venv)",
            "runner": "python scripts/run_python_tests.py  ->  Ran 1755 tests, OK (skipped=37)",
            "os": "Windows",
        },
        "subject_files": {
            "apps/workbench/workbench.ts": sha("apps/workbench/workbench.ts"),
            "apps/workbench/index.html": sha("apps/workbench/index.html"),
            "design-lab/tests/test_workbench_native_ui.py": sha("design-lab/tests/test_workbench_native_ui.py"),
        },
        "artifacts": [
            {"path": "design-lab/tests/test_workbench_native_ui.py",
             "sha256": sha("design-lab/tests/test_workbench_native_ui.py")},
            {"path": SURVEY, "sha256": survey_hash},
        ],
        "note": (
            "工作台侧的提交 / 修改 / 取消 / 导出 / 预览 / 原生校验 handler 与契约测试"
            "（test_workbench_native_ui.py：分页游标、旧响应不得覆盖新视图、patch 幂等、"
            "start/cancel attempt 绑定、bundle hash 校验、409/401 fail-closed）在 634071f 随全量套件"
            "执行通过。PARTIAL：这些是受控运行与结构证据，**不**构成真实宿主 E3，"
            "也不代表人工验收；host_live 轴因此不绑定。"
        ),
    },
]

BIND = {
    ("DL-R5-028", "implementation"): "r5-workbench-strict-ts-build-truth-20260927",
    ("DL-R5-028", "unit"): "r5-workbench-strict-ts-build-truth-20260927",
    ("DL-R5-010", "implementation"): "r5-workbench-native-task-ui-tests-20260927",
    ("DL-R5-010", "unit"): "r5-workbench-native-task-ui-tests-20260927",
}


def main() -> int:
    ledger = json.loads(LEDGER.read_text(encoding="utf-8"))
    existing = {e["id"] for e in ledger["evidence"]}
    added = [r for r in RECEIPTS if r["id"] not in existing]
    ledger["evidence"].extend(added)

    bound = 0
    for task in ledger["tasks"]:
        for axis_name, axis in task["axes"].items():
            rid = BIND.get((task["id"], axis_name))
            if rid and rid not in axis["evidence"]:
                axis["evidence"].append(rid)
                bound += 1
                print(f"  bind {task['id']}.{axis_name:<15} <- {rid}")

    ledger["updated_at"] = OBS
    LEDGER.write_text(json.dumps(ledger, ensure_ascii=False, indent=2) + "\n",
                      encoding="utf-8", newline="\n")

    total = sum(1 for t in ledger["tasks"] for a in t["axes"].values() if a["evidence"])
    print(f"\n  receipts added : {len(added)} (total {len(ledger['evidence'])})")
    print(f"  axis refs added: {bound}")
    print(f"  bound axes now : {total} / {len(ledger['tasks']) * 4}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
