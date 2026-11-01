#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Poll PR 152: 9 required checks green -> READY."""
import subprocess, json, time, sys
ROOT = r"D:\\All projects\\DESIGN-LAB"
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
def gh(*a):
    r = subprocess.run(["gh"]+list(a), cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=90)
    return r.returncode, (r.stdout or "") + (r.stderr or "")
deadline = time.time() + 30*60
while time.time() < deadline:
    rc, out = gh("pr","checks","152")
    lines = [l for l in out.strip().splitlines() if l.strip()]
    snap = {}
    for l in lines:
        parts = l.rsplit(" ", 1)
        if len(parts)==2: snap[parts[0]] = parts[1]
    missing = [c for c in REQUIRED if c not in snap]
    bad = {k:v for k,v in snap.items() if v not in ("success","SUCCESS","skipped","neutral") and k in REQUIRED}
    done = all(c in snap and snap[c] in ("success","SUCCESS","skipped","neutral") for c in REQUIRED)
    print(f"[{int(time.time())%100000}s] present={len([c for c in REQUIRED if c in snap])}/9 missing={len(missing)} failed={list(bad)[:4]}", flush=True)
    if done:
        print("READY: all 9 required green on PR 152", flush=True)
        sys.exit(0)
    if bad:
        print(f"FAIL: {bad}", flush=True)
        sys.exit(1)
    time.sleep(45)
print("TIMEOUT: 30min elapsed, still waiting", flush=True)
sys.exit(2)
