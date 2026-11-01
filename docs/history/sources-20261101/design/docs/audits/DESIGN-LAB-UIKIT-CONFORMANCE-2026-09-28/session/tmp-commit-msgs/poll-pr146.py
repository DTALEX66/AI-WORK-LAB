# SPDX-License-Identifier: MIT
# Poll PR #146 (branch disposition ledger) to CLEAN, squash-merge, delete branch.
# Robust JSON parsing of `gh pr view --json`; P1-2 tightened protection means
# BLOCKED while the 9 required checks run -> WAIT, not abort. Only DIRTY/
# UNSTABLE aborts. BEHIND -> update-branch then re-poll.
import subprocess, json, time, sys

CWD = "D:/All projects/DESIGN-LAB"
MAX_POLLS = 60   # 30 min at 30s

def gh(args):
    return subprocess.run(["gh", *args], cwd=CWD, capture_output=True, text=True, timeout=120)

n = 0
while n < MAX_POLLS:
    r = gh(["pr", "view", "146", "--json", "state,mergedAt,mergeStateStatus,mergeable", "--jq", "."])
    try:
        info = json.loads(r.stdout)
    except Exception:
        n += 1
        time.sleep(30)
        continue
    state = info.get("state")
    merge = info.get("mergeStateStatus")
    if state == "MERGED" or info.get("mergedAt"):
        print("PR 146 MERGED", flush=True)
        sys.exit(0)
    if merge == "BEHIND":
        u = gh(["pr", "update-branch", "146"])
        print("BEHIND -> update-branch rc=", u.returncode, flush=True)
        n += 1
        time.sleep(30)
        continue
    if merge == "CLEAN":
        m = gh(["pr", "merge", "146", "--squash", "--delete-branch"])
        print("merged rc=", m.returncode, m.stdout, m.stderr, flush=True)
        sys.exit(0)
    if merge in ("DIRTY", "UNSTABLE"):
        print("aborted mergeState=", merge, flush=True)
        sys.exit(1)
    # BLOCKED / UNKNOWN: CI running under P1-2's 9 required checks -> wait
    n += 1
    print(f"poll {n}: state={state} merge={merge}, waiting...", flush=True)
    time.sleep(30)
print("timeout after 30min")
sys.exit(1)
