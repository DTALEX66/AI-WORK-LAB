# SPDX-License-Identifier: MIT
import os, sqlite3, datetime
from pathlib import Path
H = Path(os.environ["HERMES_HOME"])
def ts(v):
    try: return datetime.datetime.fromtimestamp(float(v)).strftime("%Y-%m-%d %H:%M")
    except Exception: return str(v)

c = sqlite3.connect(f"file:{(H/'state.db').as_posix()}?mode=ro", uri=True)
print("=== async_delegations（HERMES 异步委派任务，仅状态/时间，不读 task_json）===")
rows = c.execute("select state, count(*), min(dispatched_at), max(dispatched_at) from async_delegations group by state").fetchall()
for st, n, mn, mx in rows:
    print(f"  state={st:<10} n={n:<4} first={ts(mn)}  last={ts(mx)}")
print("  per-row (delegation_id 前缀 + state + dispatched + completed):")
for did, st, d, cp in c.execute("select delegation_id, state, dispatched_at, completed_at from async_delegations order by dispatched_at desc limit 8"):
    print(f"    {str(did)[:14]:<16} {st:<10} dispatched={ts(d)} completed={ts(cp) if cp else '-'}")
c.close()

v = sqlite3.connect(f"file:{(H/'verification_evidence.db').as_posix()}?mode=ro", uri=True)
print("\n=== verification_events（HERMES 验证命令记录，仅 root/cwd/kind/status）===")
print("  roots:")
for root, n in v.execute("select root, count(*) from verification_events group by root order by 2 desc limit 12"):
    print(f"    {str(root)[:70]:<72} n={n}")
print("  kinds:", v.execute("select kind, count(*) from verification_events group by kind").fetchall())
print("  status:", v.execute("select status, count(*) from verification_events group by status").fetchall())
print("  window:", v.execute("select min(created_at), max(created_at) from verification_events").fetchone())
print("  DESIGN-LAB 命中的行数:", v.execute("select count(*) from verification_events where root like '%DESIGN-LAB%' or cwd like '%DESIGN-LAB%'").fetchone()[0])
v.close()
