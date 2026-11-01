#!/usr/bin/env python
# SPDX-License-Identifier: MIT
"""Diagnose why #170 squash-merge is blocked despite 9/9 gates green."""
import subprocess, json
ROOT = r"D:/All projects/DESIGN-LAB"
def run(c):
    return subprocess.run(c, cwd=ROOT, capture_output=True, text=True,
                          encoding="utf-8", errors="replace")

# full PR state
info = json.loads(run(["gh","pr","view","170","--json",
    "headRefOid,baseRefOid,mergeStateStatus,mergeable,state,mergeCommit,createdAt,updatedAt"]).stdout)
print("#170:", json.dumps(info, indent=2))

# branch protection
bp = json.loads(run(["gh","api","repos/DTALEX66/DESIGN-LAB/branches/main/protection"]).stdout)
print("\nbranch protection summary:")
print("  required_status_checks:", bp.get("required_status_checks"))
print("  strict:", bp.get("required_status_checks",{}).get("strict") if isinstance(bp.get("required_status_checks"),dict) else None)

# how many commits ahead/behind
ahead = run(["gh","pr","view","170","--json","commits"]).stdout
commits = json.loads(ahead)
print(f"\ncommits in #170: {len(commits)}")
for c in commits:
    print(f"  {c['oid'][:12]} {c['message'].splitlines()[0][:80]}")

# compare base main vs head
main_sha = run(["git","rev-parse","main"]).stdout.strip()
print(f"\nlocal main={main_sha[:12]}  origin/main=" + run(["git","rev-parse","origin/main"]).stdout.strip()[:12])

