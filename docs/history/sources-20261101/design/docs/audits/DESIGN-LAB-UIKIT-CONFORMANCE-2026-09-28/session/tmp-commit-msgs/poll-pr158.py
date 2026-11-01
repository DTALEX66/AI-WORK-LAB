# SPDX-License-Identifier: MIT

import subprocess, time, sys
ROOT = r"D:\All projects\DESIGN-LAB"
def sh(args):
    return subprocess.run(args, cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=90)
REQ = ["Python gate (V3 verifiers + unit tests)","MiniGame node gate (+ drift check)","Generated-artifact clean-tree gate","License & secret hygiene gate","Open Design host adapter gate","Top-level Authority consistency gate (DL-AUTHORITY-2026-09-18-R2)","Workbench strict-TS product gate (taskpack 12.2/12.3/12.4/12.5)","Workbench browser E2E (exact-SHA controlled-runtime, no-skip)","DeepSeek authority gate chain (DLDS-H010 / DL-AUDIT-20260914-07)"]
GREEN = {"pass","skipped","neutral","success"}
deadline = time.time() + 1500
while time.time() < deadline:
    out = sh(["gh","pr","checks","158"]).stdout
    snap = {}
    for l in out.strip().splitlines():
        p = l.split("\t")
        if len(p) >= 2: snap[p[0]] = p[1]
    ng = {c: snap.get(c, "MISSING") for c in REQ if snap.get(c) not in GREEN}
    fails = {c: v for c, v in ng.items() if v in ("fail", "failure", "error", "cancelled", "timing_out")}
    print(f"[{int(time.time()) % 100000}] green={9-len(ng)}/9 pending={len(ng)-len(fails)}", flush=True)
    if fails:
        print("FAIL:", fails); sys.exit(1)
    if not ng:
        print("READY: all 9 required green on PR 158"); sys.exit(0)
    time.sleep(30)
print("TIMEOUT"); sys.exit(2)
