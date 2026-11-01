# SPDX-License-Identifier: MIT
# Poll PR #143 to CLEAN, squash-merge, delete branch. Forward-slash CWD.
import subprocess, json, time, sys

CWD = "D:/All projects/DESIGN-LAB"

def gh(args):
    r = subprocess.run(["gh"] + args, cwd=CWD, capture_output=True, text=True, timeout=120)
    return r

n = 0
while n < 60:
    r = gh(["pr", "view", "143", "--json", "state,mergedAt,mergeStateStatus,mergeable", "--jq", "."])
    try:
        info = json.loads(r.stdout)
    except Exception:
        n += 1
        time.sleep(30)
        continue
    state = info.get("state")
    merge = info.get("mergeStateStatus")
    if state == "MERGED" or info.get("mergedAt"):
        print("PR 143 MERGED", flush=True)
        sys.exit(0)
    if merge == "CLEAN":
        m = gh(["pr", "merge", "143", "--squash", "--delete-branch"])
        print("merged rc=", m.returncode, m.stdout, m.stderr, flush=True)
        sys.exit(0)
    if merge in ("DIRTY", "UNSTABLE", "UNKNOWN"):
        print("aborted mergeState=", merge, flush=True)
        sys.exit(1)
    # BEHIND/BLOCKED: wait for CI
    n += 1
    print(f"poll {n}: state={state} merge={merge}, waiting...", flush=True)
    time.sleep(30)
print("timeout after 30min")
