# SPDX-License-Identifier: MIT
import os, sqlite3, datetime
from pathlib import Path
H = Path(os.environ["HERMES_HOME"])
c = sqlite3.connect(f"file:{(H/'cron/executions.db').as_posix()}?mode=ro", uri=True)
print("=== distinct job_id / source / status ===")
for row in c.execute("select job_id, source, status, count(*) n, max(claimed_at) last from executions group by job_id, source, status order by n desc limit 25"):
    print(f"  job_id={row[0]!r:<28} source={str(row[1])[:14]:<14} status={str(row[2]):<10} n={row[3]:<5} last_claimed={row[4]}")
print("\n=== claimed_at range ===")
print(" ", c.execute("select min(claimed_at), max(claimed_at) from executions").fetchone())
c.close()
