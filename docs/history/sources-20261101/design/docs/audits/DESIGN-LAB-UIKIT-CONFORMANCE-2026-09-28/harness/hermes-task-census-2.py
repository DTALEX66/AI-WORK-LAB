#!/usr/bin/env python
# SPDX-License-Identifier: MIT
"""Finish the HERMES task census: enumerate ALL cron jobs ever recorded (not just
the top-25), the cron output dirs, live spawns, and the two remaining task-ish
surfaces (async_delegations, bot_relay, workflow baseline).

Privacy: prints column NAMES and counts/status/timestamps only. Never prints
prompt/result/message bodies. Reads no credentials.
"""
from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path

H = Path(os.environ["HERMES_HOME"])


def section(t: str) -> None:
    print(f"\n{'=' * 76}\n{t}\n{'=' * 76}")


section("A. cron 全部历史 job_id（executions 全表，不截断）")
con = sqlite3.connect(f"file:{(H / 'cron/executions.db').as_posix()}?mode=ro", uri=True)
rows = con.execute("""
    select job_id, source, status, count(*) n,
           min(claimed_at) first_at, max(claimed_at) last_at
    from executions group by job_id, source, status
    order by last_at desc
""").fetchall()
print(f"  distinct (job_id, source, status) groups: {len(rows)}")
print(f"  distinct job_id: {len({r[0] for r in rows})}")
for r in rows:
    print(f"    {str(r[0]):<22} src={str(r[1]):<9} st={str(r[2]):<10} n={r[3]:<5} last={r[5]}")
print(f"\n  overall window: {con.execute('select min(claimed_at), max(claimed_at) from executions').fetchone()}")
con.close()

section("B. cron/output 目录（作业产物）")
out = H / "cron" / "output"
if out.is_dir():
    for d in sorted(out.iterdir()):
        files = list(d.iterdir()) if d.is_dir() else []
        print(f"  {d.name}/  n={len(files)}  {[f.name for f in files][:6]}")
        for f in files[:3]:
            if f.is_file():
                import datetime
                print(f"      {f.name}  {f.stat().st_size:,} B  "
                      f"mtime={datetime.datetime.fromtimestamp(f.stat().st_mtime):%Y-%m-%d %H:%M}")

section("C. 存活进程（spawn-ledger）")
sl = json.loads((H / "spawn-ledger.json").read_text(encoding="utf-8"))
for e in sl:
    print(f"  pid={e.get('pid'):<8} purpose={e.get('purpose'):<12} port={e.get('port')} argv={str(e.get('argv'))[:70]}")

section("D. state.db 任务类表（仅列名/状态/计数，不读正文）")
con = sqlite3.connect(f"file:{(H / 'state.db').as_posix()}?mode=ro", uri=True)
tabs = [r[0] for r in con.execute("select name from sqlite_master where type='table' order by name")]
print(f"  state.db tables ({len(tabs)}): {tabs}")
for t in ("async_delegations", "delivery_obligations", "gateway_heartbeats", "gateway_hygiene_state"):
    if t not in tabs:
        continue
    cols = [r[1] for r in con.execute(f"PRAGMA table_info({t})")]
    n = con.execute(f"select count(*) from {t}").fetchone()[0]
    print(f"\n  {t}: rows={n}")
    print(f"    columns: {cols}")
    # only safe/structural columns
    for c in ("status", "state", "kind", "purpose", "created_at", "updated_at", "finished_at"):
        if c in cols:
            try:
                dist = con.execute(f"select {c}, count(*) from {t} group by {c} order by 2 desc limit 8").fetchall()
                print(f"    {c}: {dist}")
            except sqlite3.Error as e:
                print(f"    {c}: ERR {e}")
con.close()

section("E. bot_relay / workflow baseline")
br = H / "bot_relay"
if br.is_dir():
    for sub in ("claimed", "outbox", "replies"):
        p = br / sub
        cnt = len(list(p.iterdir())) if p.is_dir() else "MISSING"
        print(f"  bot_relay/{sub:<10} n={cnt}")
    r = br / "roster.json"
    if r.is_file():
        data = json.loads(r.read_text(encoding="utf-8"))
        print(f"  roster.json: {json.dumps(data, ensure_ascii=False)[:300]}")

wb = H / ".workflow-assistance-baseline.json"
if wb.is_file():
    import datetime
    d = json.loads(wb.read_text(encoding="utf-8"))
    print(f"\n  .workflow-assistance-baseline.json  mtime="
          f"{datetime.datetime.fromtimestamp(wb.stat().st_mtime):%Y-%m-%d %H:%M}")
    print(f"    top-level keys: {sorted(d.keys()) if isinstance(d, dict) else type(d)}")
    print(f"    {json.dumps(d, ensure_ascii=False)[:400]}")

section("F. verification_evidence.db 是否涉及 DESIGN-LAB（只看结构与非空计数）")
vp = H / "verification_evidence.db"
con = sqlite3.connect(f"file:{vp.as_posix()}?mode=ro", uri=True)
for t in ("verification_events", "verification_state", "meta"):
    cols = [r[1] for r in con.execute(f"PRAGMA table_info({t})")]
    n = con.execute(f"select count(*) from {t}").fetchone()[0]
    print(f"  {t}: rows={n} cols={cols}")
con.close()

print("\nDONE — read-only; no credentials, no message/prompt bodies read.")
