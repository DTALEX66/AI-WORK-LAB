#!/usr/bin/env python
# SPDX-License-Identifier: MIT
"""Atomically: squash-merge PR #170 + delete source branch, then read back
mergedAt/mergeCommit/state + confirm origin/main advanced + remote branch gone."""
import subprocess, json, os
ROOT = r"D:/All projects/DESIGN-LAB"
def run(c):
    return subprocess.run(c, cwd=ROOT, capture_output=True, text=True,
                          encoding="utf-8", errors="replace")

before_main = run(["git","rev-parse","origin/main"]).stdout.strip()
print(f"origin/main BEFORE: {before_main}")

m = run(["gh","pr","merge","170","--squash","--delete-branch"])
print(f"merge rc={m.returncode}  stderr={m.stderr.strip()[:200]}")

info = json.loads(run(["gh","pr","view","170","--json",
    "state,mergedAt,mergeCommit,mergedBy"]).stdout)
print(f"#170 readback: state={info['state']} mergedAt={info.get('mergedAt')} "
      f"mergeCommit={str(info.get('mergeCommit'))[:12]} by={info.get('mergedBy')}")

run(["git","fetch","origin","main"])
run(["git","reset","--hard","origin/main"])
run(["git","remote","prune","origin"])
after_main = run(["git","rev-parse","main"]).stdout.strip()
print(f"main AFTER: {after_main}  (advanced={after_main!=before_main})")

branches = [x for x in run(["git","branch","-r","--format","%(refname:short)"]).stdout.split()
            if x != "origin/HEAD"]
print("remote branches now:", branches)
print(f"fix/no-overclaim-evidence-ref-2026-09-27 gone: "
      f"{'origin/fix/no-overclaim-evidence-ref-2026-09-27' not in branches}")

# clean scratch
for s in ["poll-pr170.py","check170.py","commit-msg-no-overclaim.txt","pr-body-no-overclaim.txt"]:
    p = os.path.join(ROOT, ".project-local", s)
    if os.path.exists(p):
        os.remove(p)
        print(f"cleaned .project-local/{s}")
print("worktree:", run(["git","status","--short"]).stdout.strip() or "(clean)")
print("open PRs:", run(["gh","pr","list","--state","open","--json","number"]).stdout.strip() or "(none)")
