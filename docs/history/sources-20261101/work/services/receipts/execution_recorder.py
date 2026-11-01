"""WORK-LAB Observer - execution instance recorder (activity-based).

Writes execution_instances from real DSH session activity: a project with
recent user/assistant messages is an active execution. state_quality=ESTIMATED
(derived from session activity, not exact runtime heartbeat).
"""
import json, os, sqlite3, zstandard, uuid
from datetime import datetime, timezone

BASE = r'D:\All projects\WORK-LAB\.hermes\task-runtime\deepseek-harness\dsh-home\sessions'
DB = r'D:\All projects\WORK-LAB\.hermes\task-runtime\canonical.sqlite'
dctx = zstandard.ZstdDecompressor()

PROJECTS = {
    '--D-All~0020projects-WORK-LAB--': 'work-lab',
    '--D-All~0020projects-DESIGN-LAB--': 'design-lab',
    '--D-All~0020projects-ArcheAxis-Knowledge-OS--': 'archeaxis-knowledge-os',
}

def decode(path):
    try:
        with open(path, 'rb') as fh:
            reader = dctx.stream_reader(fh)
            chunks = []
            while True:
                c = reader.read(65536)
                if not c: break
                chunks.append(c)
        return b''.join(chunks).decode('utf-8', errors='replace').splitlines()
    except Exception:
        return []

def activity(proj_dir):
    pdir = os.path.join(BASE, proj_dir)
    counts = {}
    latest_ts = None
    if not os.path.isdir(pdir): return counts, latest_ts
    for root, dirs, files in os.walk(pdir):
        for fn in files:
            if not fn.endswith('.zstd'): continue
            for line in decode(os.path.join(root, fn)):
                try:
                    rec = json.loads(line)
                    t = rec.get('type') or 'unknown'
                    counts[t] = counts.get(t, 0) + 1
                    ts = rec.get('timestamp') or rec.get('time') or rec.get('ts')
                    if ts and (latest_ts is None or ts > latest_ts):
                        latest_ts = ts
                except Exception:
                    pass
    return counts, latest_ts

conn = sqlite3.connect(DB)
cur = conn.cursor()
now = datetime.now(timezone.utc).isoformat()
for proj_dir, pid in PROJECTS.items():
    c, latest_ts = activity(proj_dir)
    calls = c.get('assistant/message', 0)
    if calls == 0:
        continue
    # activity => active execution; idle if no messages in last 30 min
    state = 'RUNNING'
    if latest_ts:
        try:
            from datetime import datetime as dt
            lt = dt.fromisoformat(str(latest_ts).replace('Z', '+00:00'))
            age_min = (datetime.now(timezone.utc) - lt).total_seconds() / 60
            if age_min > 30:
                state = 'IDLE'
        except Exception:
            pass
    eid = f'exec-{pid}'
    cur.execute("""
        INSERT INTO execution_instances
        (execution_id, agent, session_id, anchor_project_id, repository_id, worktree_id,
         working_area, state, state_quality, started_at, last_heartbeat_at, transport_state, updated_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT(execution_id) DO UPDATE SET
          state=excluded.state, last_heartbeat_at=excluded.last_heartbeat_at,
          state_quality=excluded.state_quality, updated_at=excluded.updated_at
    """, (eid, 'deepseek-harness', f'session-{pid}', pid, None, None,
          os.path.join(r'D:\All projects', pid), state, 'ESTIMATED', now, now, 'LOCAL', now))
    print(f'{pid}: calls={calls} state={state}')
conn.commit()
print('execution instances updated')
conn.close()