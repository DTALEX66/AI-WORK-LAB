#!/usr/bin/env python
# SPDX-License-Identifier: MIT
"""Read-only: what does HERMES register for DESIGN-LAB, and does anything
schedule/track work for it? Prints schema + rows for the project registry only.

No credentials, no session bodies, no message content.
"""
from __future__ import annotations

import os
import sqlite3
from pathlib import Path

HERMES = Path(os.environ.get("HERMES_HOME", r"C:\Users\ALEX\AppData\Local\hermes"))
db = HERMES / "projects.db"
con = sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True)

for table in ("projects", "project_folders", "project_meta"):
    cols = [r[1] for r in con.execute(f"PRAGMA table_info({table})")]
    print(f"\n=== {table}  columns={cols}")
    rows = con.execute(f"select * from {table}").fetchall()
    for row in rows:
        # print only identity-ish fields; never dump long free text
        out = []
        for c, v in zip(cols, row):
            s = str(v)
            out.append(f"{c}={s[:60]}" + ("..." if len(s) > 60 else ""))
        print("  " + " | ".join(out))

print("\n=== cron executions (last 5, metadata only) ===")
cron_db = HERMES / "cron" / "executions.db"
if cron_db.is_file():
    c2 = sqlite3.connect(f"file:{cron_db.as_posix()}?mode=ro", uri=True)
    tables = [r[0] for r in c2.execute("select name from sqlite_master where type='table'")]
    print("  tables:", tables)
    for t in tables:
        cols = [r[1] for r in c2.execute(f"PRAGMA table_info({t})")]
        n = c2.execute(f"select count(*) from {t}").fetchone()[0]
        print(f"  {t}: rows={n} cols={cols[:8]}")
    c2.close()

con.close()
print("\nDONE (read-only)")
