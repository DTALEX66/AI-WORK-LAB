#!/usr/bin/env python
# SPDX-License-Identifier: MIT
"""Read-only census of EVERY place the HERMES runtime could be executing or
tracking work, so this session can state with evidence whether any project task
is running outside this conversation.

Deliberately SKIPS credentials and private content:
  .env, auth.json, nous_auth.json, vault/**, sessions/**, memories/**,
  state.db message tables, browser profiles.

Outputs only: paths, row counts, table names, job ids, timestamps, statuses.
"""
from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path

H = Path(os.environ["HERMES_HOME"])


def section(t: str) -> None:
    print(f"\n{'=' * 76}\n{t}\n{'=' * 76}")


def ls(rel: str, limit: int = 14) -> None:
    p = H / rel
    if not p.exists():
        print(f"  {rel:<26} MISSING")
        return
    if p.is_file():
        print(f"  {rel:<26} FILE {p.stat().st_size:,} B  mtime={_ts(p)}")
        return
    items = sorted(p.iterdir(), key=lambda e: e.name)[:limit]
    names = [f"{e.name}{'/' if e.is_dir() else ''}" for e in items]
    more = "" if len(list(p.iterdir())) <= limit else f" ...(+{len(list(p.iterdir())) - limit})"
    print(f"  {rel:<26} DIR  n={len(list(p.iterdir()))}  {names}{more}")


def _ts(p: Path) -> str:
    import datetime
    return datetime.datetime.fromtimestamp(p.stat().st_mtime).strftime("%Y-%m-%d %H:%M")


def sqlite_peek(rel: str, max_tables: int = 12) -> None:
    p = H / rel
    if not p.is_file():
        print(f"  {rel:<26} MISSING")
        return
    print(f"  {rel:<26} {p.stat().st_size:>12,} B  mtime={_ts(p)}")
    try:
        con = sqlite3.connect(f"file:{p.as_posix()}?mode=ro", uri=True)
        tables = [r[0] for r in con.execute(
            "select name from sqlite_master where type='table' order by name")]
        for t in tables[:max_tables]:
            try:
                n = con.execute(f"select count(*) from {t}").fetchone()[0]
                mark = "  <-- NON-EMPTY" if n else ""
                print(f"      {t:<30} rows={n}{mark}")
            except sqlite3.Error as e:
                print(f"      {t:<30} ERR {e}")
        con.close()
    except sqlite3.Error as e:
        print(f"      OPEN FAILED: {e}")


section("1. 定时/调度类（唯一会“自己跑任务”的来源）")
cron = H / "cron/jobs.json"
print(f"  cron/jobs.json             {json.loads(cron.read_text(encoding='utf-8'))}")
sqlite_peek("cron/executions.db")
print(f"  cron/ticker_heartbeat      mtime={_ts(H / 'cron/ticker_heartbeat') if (H / 'cron/ticker_heartbeat').exists() else 'MISSING'}")
print(f"  cron/ticker_last_success   mtime={_ts(H / 'cron/ticker_last_success') if (H / 'cron/ticker_last_success').exists() else 'MISSING'}")
ls("cron/output")

section("2. 看板 / 任务队列")
sqlite_peek("kanban.db")
ls("pending")
ls("pending_messages")

section("3. 项目级运行与派工账本")
ls("project-local-runs", limit=20)
sp = H / "spawn-ledger.json"
if sp.is_file():
    print(f"\n  spawn-ledger.json ({sp.stat().st_size} B, mtime={_ts(sp)}):")
    print("   ", json.dumps(json.loads(sp.read_text(encoding="utf-8")), ensure_ascii=False)[:600])

section("4. 扩展面（hook / plugin / tool / desktop 均可挂任务）")
for rel in ("hooks", "plugins", "desktop-plugins", "desktop",
            "tools", "installs", "platforms", "profiles"):
    ls(rel)

section("5. 服务/网关/中继（可能含后台作业）")
for rel in ("gateway-service", "bot_relay", "runtime", "shared", "source-checks"):
    ls(rel)

section("6. 代理工作流状态（可能记录待执行任务）")
for rel in (".workflow-assistance-state.yaml", ".workflow-assistance-baseline.json",
            "gateway_state.json", "processes.json"):
    p = H / rel
    if p.is_file():
        print(f"  {rel:<34} {p.stat().st_size:>8,} B  mtime={_ts(p)}")

section("7. 凭据/私有区（本会话刻意不读）")
for rel in (".env", "auth.json", "vault", "sessions", "memories", "state.db"):
    p = H / rel
    print(f"  {rel:<26} {'present (NOT READ)' if p.exists() else 'absent'}")

section("8. 状态库（只报表名与非空计数，不读内容）")
for rel in ("shared-state.db", "verification_evidence.db", "state.db"):
    print()
    sqlite_peek(rel, max_tables=8)

print("\nDONE — read-only; nothing written, no credentials read.")
