#!/usr/bin/env python
# SPDX-License-Identifier: MIT
"""Read-only project + HERMES task-surface survey for DESIGN-LAB.

Prints a compact dashboard of:
  1. the authoritative task ledger (design-lab/config/task-ledger-r3.json)
  2. the generated projections in reports/current vs the live main SHA
  3. the HERMES runtime surfaces that actually execute project work
  4. top-level .project-local hygiene

Never writes anything. Never reads credentials/session bodies.
"""
from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(r"D:\All projects\DESIGN-LAB")
HERMES = Path(os.environ.get("HERMES_HOME", r"C:\Users\ALEX\AppData\Local\hermes"))


def sh(*args: str) -> str:
    return subprocess.run(args, cwd=ROOT, capture_output=True, text=True, check=False).stdout.strip()


def section(title: str) -> None:
    print(f"\n{'=' * 78}\n{title}\n{'=' * 78}")


# ---------------------------------------------------------------- 1. ledger
section("1. 权威任务账本  design-lab/config/task-ledger-r3.json (唯一状态编辑源)")
ledger = json.loads((ROOT / "design-lab/config/task-ledger-r3.json").read_text(encoding="utf-8"))
print(f"schemaVersion : {ledger.get('schemaVersion')!r}")
print(f"top-level keys: {sorted(ledger.keys())}")
tasks = ledger.get("tasks", [])
print(f"tasks         : {len(tasks)}")

axes = ["implementation", "unit", "host_live", "delivery"]
print("\n-- 轴状态分布 --")
for ax in axes:
    c = Counter((t.get("axes") or {}).get(ax, {}).get("state", "<none>") for t in tasks)
    print(f"  {ax:<16} {dict(c)}")

print("\n-- reassessment 分布 --")
print(" ", dict(Counter(t.get("reassessment", "<none>") for t in tasks)))

print("\n-- definition.execution_state 分布 --")
print(" ", dict(Counter((t.get("definition") or {}).get("execution_state", "<none>") for t in tasks)))

print("\n-- 优先级分布 --")
print(" ", dict(Counter((t.get("definition") or {}).get("priority", "<none>") for t in tasks)))

print("\n-- 有证据绑定的轴（非空 evidence 数组） --")
with_ev = []
for t in tasks:
    for ax in axes:
        ev = ((t.get("axes") or {}).get(ax) or {}).get("evidence") or []
        if ev:
            with_ev.append((t["id"], ax, ev))
for tid, ax, ev in with_ev:
    print(f"  {tid:<12} {ax:<16} {ev}")
print(f"  total bound axes: {len(with_ev)} / {len(tasks) * len(axes)}")
print(f"\nledger-level evidence records: {len(ledger.get('evidence', []))}")

ids = {t["id"] for t in tasks}
broken = [(t["id"], d) for t in tasks for d in (t.get("depends_on") or []) if d not in ids]
print(f"\n依赖图完整性: {'OK (无悬空 depends_on)' if not broken else f'BROKEN {broken}'}")

# ------------------------------------------------- 2. projections vs live SHA
section("2. 生成投影 fresh 性（reports/current vs live main）")
live = sh("git", "rev-parse", "HEAD")
print(f"live HEAD            : {live}")
status_md = (ROOT / "reports/current/PROJECT_STATUS.md").read_text(encoding="utf-8")
first = status_md.splitlines()[:8]
observed = next((l for l in first if "观察 SHA" in l or "observed" in l.lower()), "")
print(f"PROJECT_STATUS.md    : {observed.strip()[:120]}")
prog = json.loads((ROOT / "reports/current/TASK_PROGRESS.json").read_text(encoding="utf-8"))
for key in ("observedMainSha", "observed_main_sha", "subject_sha", "generatedAt", "generated_at",
            "worktree_clean", "worktree_digest", "test_run_id"):
    if key in prog:
        print(f"TASK_PROGRESS.{key:<18}: {str(prog[key])[:100]}")
print("classification: PROJECTION (authority-index projectionRule) -> 必须经 fresh 校验才可用")

# ------------------------------------------------------- 3. HERMES surfaces
section("3. HERMES 运行时的“任务”面（只读元数据）")
cron = json.loads((HERMES / "cron/jobs.json").read_text(encoding="utf-8"))
print(f"cron/jobs.json       : jobs={cron.get('jobs')}  updated_at={cron.get('updated_at')}")
print(f"cron/executions.db   : {(HERMES / 'cron/executions.db').stat().st_size:,} B")
runs = HERMES / "project-local-runs"
print(f"project-local-runs   : {[p.name for p in runs.iterdir()] if runs.is_dir() else 'MISSING'}")
for sub in sorted(runs.iterdir()) if runs.is_dir() else []:
    print(f"   {sub.name}: {[f.name for f in sub.iterdir()][:6]}")

for db in ("projects.db", "kanban.db"):
    p = HERMES / db
    if not p.is_file():
        continue
    try:
        con = sqlite3.connect(f"file:{p.as_posix()}?mode=ro", uri=True)
        tables = [r[0] for r in con.execute("select name from sqlite_master where type='table'")]
        print(f"\n-- {db}  tables={tables}")
        for tb in tables:
            try:
                n = con.execute(f"select count(*) from {tb}").fetchone()[0]
                print(f"   {tb:<28} rows={n}")
            except sqlite3.Error as exc:
                print(f"   {tb:<28} ERR {exc}")
        con.close()
    except sqlite3.Error as exc:
        print(f"\n-- {db}: OPEN FAILED {exc}")

# ------------------------------------------------------------ 4. hygiene
section("4. .project-local 顶层卫生（任务数据 vs 会话暂存 归属）")
pl = ROOT / ".project-local"
for entry in sorted(pl.iterdir(), key=lambda e: (e.is_file(), e.name)):
    kind = "DIR " if entry.is_dir() else "FILE"
    print(f"  {kind} {entry.name}")
print("\n规则: 任务数据 -> .project-local/<task>/ ；agent 会话暂存 -> "
      ".project-local/task-artifacts/external-recovery-<date>/")
print("project-local-runs 仅在 HERMES_HOME 下（不在项目内），与项目 .project-local 是两处")

print("\nDONE (read-only, nothing written)")
sys.exit(0)
