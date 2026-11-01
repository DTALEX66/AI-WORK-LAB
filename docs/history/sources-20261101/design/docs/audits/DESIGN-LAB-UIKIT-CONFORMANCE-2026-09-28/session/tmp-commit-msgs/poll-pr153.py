#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Poll PR 153: all 9 required checks green -> READY."""
import subprocess, time, sys
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
deadline = time.time() + 35*60
while time.time() < deadline:
    rc, out = gh("pr","checks","153")
    snap = {}
    for l in out.strip().splitlines():
        p = l.split("\t")
        if len(p) >= 2:
            snap[p[0]] = p[1]
    present = [c for c in REQUIRED if c in snap]
    ok = all(snap[c] in ("pass","skipped","neutral") for c in present)
    failed = {c:snap[c] for c in present if snap[c] not in ("pass","skipped","neutral")}
    print(f"[{int(time.time())%1000000}s] {len(present)}/9 present, failed={list(failed)[:3]}", flush=True)
    if len(present)==9 and ok:
        print("READY: all 9 required green on PR 153", flush=True); sys.exit(0)
    if failed:
        print("FAIL:", failed, flush=True); sys.exit(1)
    time.sleep(40)
print("TIMEOUT", flush=True); sys.exit(2)
