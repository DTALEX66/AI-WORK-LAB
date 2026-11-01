# SPDX-License-Identifier: MIT
"""Poll PR #147 until all 9 required status checks resolve. exit 0=clean, 1=fail, 2=timeout."""
import json, subprocess, sys, time

def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=90)
    return r.returncode, r.stdout.strip()

REQUIRED = [
 "Python gate (V3 verifiers + unit tests)",
 "MiniGame node gate (+ drift check)",
 "Generated-artifact clean-tree gate",
 "License & secret hygiene gate",
 "Open Design host adapter gate",
 "Top-level Authority consistency gate (DL-AUTHORITY-2026-09-18-R2)",
 "Workbench strict-TS product gate (taskpack 12.2/12.3/12.4/12.5)",
 "Workbench browser E2E (exact-SHA controlled-runtime, no-skip)",
 "DeepSeek authority gate chain (DLDS-H010 / DL-AUDIT-20260914-07)",
]
PASS = {"pass", "passed", "success"}
rank = {"failure": 0, "fail": 0, "cancelled": 0, "skipped": 0,
        "pending": 2, "queued": 2, "in_progress": 2, "wait": 2,
        "pass": 3, "passed": 3, "success": 3}

deadline = time.time() + 20 * 60
while time.time() < deadline:
    rc, out = run(["gh", "pr", "checks", "147", "--json", "name,state"])
    try:
        checks = json.loads(out)
    except Exception:
        print("poll: cannot parse checks rc=%s: %s" % (rc, out[:200]), file=sys.stderr, flush=True)
        time.sleep(30); continue
    agg = {}
    for c in checks:
        n, s = c["name"], c.get("state") or c.get("status")
        if n not in agg or rank.get(s, -1) < rank.get(agg[n], -1):
            agg[n] = s
    missing = [r for r in REQUIRED if r not in agg]
    states = {r: agg.get(r, "missing") for r in REQUIRED}
    print("poll:", json.dumps(states, ensure_ascii=False), flush=True)
    if not missing:
        bad = [k for k, v in states.items() if v not in PASS]
        if bad:
            print("PR147 RESULT: FAIL ->", bad, file=sys.stderr, flush=True)
            sys.exit(1)
        print("PR147 RESULT: CLEAN (all 9 required checks pass)", flush=True)
        sys.exit(0)
    time.sleep(45)
print("PR147 RESULT: TIMEOUT still waiting", file=sys.stderr, flush=True)
sys.exit(2)
