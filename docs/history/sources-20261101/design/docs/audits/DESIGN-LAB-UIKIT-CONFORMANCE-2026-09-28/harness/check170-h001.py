#!/usr/bin/env python
# SPDX-License-Identifier: MIT
"""Re-snapshot #170 gates + H001 advisory + any other PR-event failures."""
import subprocess, json
ROOT = r"D:/All projects/DESIGN-LAB"
def run(c):
    return subprocess.run(c, cwd=ROOT, capture_output=True, text=True,
                          encoding="utf-8", errors="replace")
info = json.loads(run(["gh","pr","view","170","--json",
    "headRefOid,baseRefOid,mergeStateStatus,mergeable,state"]).stdout)
print("#170:", info)

checks = json.loads(run(["gh","pr","checks","170","--json","name,state,event,run,runId"]).stdout or "[]")
print("\nAll PR-event checks on #170 head (event=pull_request):")
for c in checks:
    if c.get("event") == "pull_request":
        run_id = c.get("run", {}).get("id", "?")
        print(f"  {c['state']:>10}  {c['name']}  (run {run_id})")
print("\nNon-PR-event checks (main push / other):")
for c in checks:
    if c.get("event") != "pull_request":
        print(f"  {c['state']:>10}  {c['name']}  event={c.get('event')}")

# also fetch H001 advisory if present
h001 = [c for c in checks if "H001" in c["name"] or "artifact proof" in c["name"]]
if h001:
    print("\nH001 advisory entries:")
    for c in h001:
        print(f"  {c['state']:>10}  {c['name']}  event={c.get('event')}")

