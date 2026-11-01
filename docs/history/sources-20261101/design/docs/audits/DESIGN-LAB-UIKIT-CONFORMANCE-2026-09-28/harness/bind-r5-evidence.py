#!/usr/bin/env python
# SPDX-License-Identifier: MIT
"""Bind REAL, verifiable evidence receipts into the R5 task ledger.

Contract constraints honoured (src/design_lab/governance/r5_contract.py):
  * definition / title / depends_on / predecessor_task_ids / required_axes are
    FROZEN against docs/history/taskpacks/r5-20260908/tasks.json -> untouched.
  * reassessment != 'REVIEWED' forbids axis state PASS/IMPLEMENTED_LOCAL
    (:100-101) -> every axis state stays PARTIAL; this run ADDS evidence only.
  * every axis.evidence id must exist in ledger.evidence (:98-99), ids unique.
  * evidence items require 11 fields with artifacts minItems=1.

Nothing is claimed that was not observed in this session at exact SHA
634071f3c8ffa87e08fa1386f49c185ff6fa36d8. Outcome is PARTIAL everywhere: these
receipts record what was verified, not that the task is complete.
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


def now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


OBS = now()
survey_hash = sha(SURVEY)

RECEIPTS = [
    {
        "id": "r5-branch-convergence-live-20260927",
        "task_ids": ["DL-R5-001"],
        "kind": "structural",
        "outcome": "PARTIAL",
        "subject_sha": SUBJECT_SHA,
        "binding": "COMMIT",
        "observed_at": OBS,
        "software": {
            "observation": "git ls-remote --heads origin; git worktree list; git stash list; git rev-parse",
            "git": "2.55.0.windows.3",
            "os": "Windows",
        },
        "subject_files": {
            "design-lab/config/task-ledger-r3.json": sha("design-lab/config/task-ledger-r3.json"),
            ".gitignore": sha(".gitignore"),
        },
        "artifacts": [{"path": SURVEY, "sha256": survey_hash}],
        "note": (
            "实读于 634071f：远端分支 28 -> 1（仅 main）；open PR 0；单 worktree；0 stash。"
            "仅证明分支/账本收敛这一事实面，不等同 DL-R5-001 全部验收（旧 R4 ID 可追踪性、"
            "验收/回退/证据字段完整性未逐项复核），故 outcome=PARTIAL。"
        ),
    },
    {
        "id": "r5-runtime-root-boundary-live-20260927",
        "task_ids": ["DL-R5-002"],
        "kind": "structural",
        "outcome": "PARTIAL",
        "subject_sha": SUBJECT_SHA,
        "binding": "COMMIT",
        "observed_at": OBS,
        "software": {
            "observation": "file mtime sweep of HERMES_HOME; .gitignore check-ignore; ownership-classified cleanup with sha256 before/after",
            "python": "3.13.14 (project .venv)",
            "os": "Windows",
        },
        "subject_files": {
            ".gitignore": sha(".gitignore"),
            ".project/manifest.yaml": sha(".project/manifest.yaml"),
            ".project/paths.json": sha(".project/paths.json"),
        },
        "artifacts": [{"path": SURVEY, "sha256": survey_hash}],
        "note": (
            "活跃运行根 = .project-local/（.gitignore:71 忽略）；项目内 .hermes/ 仅剩 "
            "skill-call-index.json 且 mtime 2026-08-24（一个月无新增写入），与 AUTHORITY.md §7 一致。"
            "本轮按数据所有权清理：4 个会话暂存文件迁入 external-recovery（sha256 移前=移后）、"
            "4 个有契约/引用依据的文件就近保留、删除空的嵌套 .project-local/.project-local/。"
            "PARTIAL：未逐项核查 Adobe/CLI/UI/技能启动器入口，故不宣称本项全部验收。"
        ),
    },
    {
        "id": "r5-ci-required-checks-live-20260927",
        "task_ids": ["DL-R5-003"],
        "kind": "structural",
        "outcome": "PARTIAL",
        "subject_sha": SUBJECT_SHA,
        "binding": "COMMIT",
        "observed_at": OBS,
        "software": {
            "observation": "gh api /repos/DTALEX66/DESIGN-LAB/branches/main/protection; gh pr checks",
            "gh": "GitHub CLI (keyring auth)",
            "runner": "GitHub Actions ubuntu-latest",
        },
        "subject_files": {
            ".github/workflows/canonical-verify.yml": sha(".github/workflows/canonical-verify.yml"),
            ".github/workflows/release-gate.yml": sha(".github/workflows/release-gate.yml"),
        },
        "artifacts": [{"path": SURVEY, "sha256": survey_hash}],
        "note": (
            "main 分支保护 live 读回 = 9 项 required checks（Python gate / MiniGame / Generated-artifact / "
            "License-secret / Open Design / Top-level Authority / Workbench strict-TS / Workbench browser E2E / "
            "DeepSeek authority chain），在 634071f 于 push 与 pull_request 两类 run 上均 pass。"
            "PARTIAL：只证明 required-check 面，不宣称全部验证环境（uv/Ruff enforce 等）已补齐。"
        ),
    },
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
            "在 634071f 实测：strict TypeScript typecheck exit 0；Vite build exit 0（build/main.js 为受 "
            "git diff --exit-code 守卫的提交产物）；node tests/unit.mjs 与 tests/appshell.mjs 全绿。"
            "构建产物真值面由 required check 'Workbench strict-TS product gate' 与 generated-artifact "
            "clean-tree gate 双重守卫。PARTIAL：非全语言迁移；Ruff 是否 enforce 仍未决策（见 AUTHORITY §15）。"
        ),
    },
]

# axis -> receipt id(s)
BIND = {
    ("DL-R5-001", "implementation"): "r5-branch-convergence-live-20260927",
    ("DL-R5-002", "implementation"): "r5-runtime-root-boundary-live-20260927",
    ("DL-R5-003", "implementation"): "r5-ci-required-checks-live-20260927",
    ("DL-R5-028", "implementation"): "r5-workbench-strict-ts-build-truth-20260927",
    ("DL-R5-028", "unit"): "r5-workbench-strict-ts-build-truth-20260927",
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
                print(f"  bind {task['id']}.{axis_name:<15} <- {rid}  (state={axis['state']})")

    ledger["updated_at"] = OBS
    LEDGER.write_text(json.dumps(ledger, ensure_ascii=False, indent=2) + "\n",
                      encoding="utf-8", newline="\n")

    total = sum(1 for t in ledger["tasks"] for a in t["axes"].values() if a["evidence"])
    print(f"\n  receipts added : {len(added)} (total {len(ledger['evidence'])})")
    print(f"  axis refs added: {bound}")
    print(f"  bound axes now : {total} / {len(ledger['tasks']) * 4}")
    print(f"  updated_at     : {OBS}")
    print(f"  subject_sha    : {SUBJECT_SHA}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
