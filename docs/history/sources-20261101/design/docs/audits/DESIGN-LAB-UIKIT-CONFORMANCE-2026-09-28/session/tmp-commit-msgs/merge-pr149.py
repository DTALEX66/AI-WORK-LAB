# SPDX-License-Identifier: MIT
"""Wait for PR #149's CI to settle green, then squash-merge and verify main advanced.

BLOCKED = transient (checks not yet reported / strict-behind) -> keep polling.
UNSTABLE/DIRTY/other mergeStates = hard stop (report and let the next turn adjudicate).
exit 0 = merged + main advanced; 1 = bad mergeState; 2 = timeout.
"""
import json, subprocess, time, sys

BASE_SHA = "a6aeccf"
MAX_WAIT = 40 * 60


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True, shell=False, timeout=180,
                       cwd=r"D:\All projects\DESIGN-LAB")
    return (r.stdout or "").strip(), (r.stderr or "").strip(), r.returncode


def main():
    start = time.time()
    while time.time() - start < MAX_WAIT:
        out, err, rc = run(["gh", "pr", "status", "149", "--json", "mergeState", "headRefOid", "mergeable"])
        if rc == 0:
            d = json.loads(out)
            state = d.get("mergeState")
            print(f"[{int(time.time()-start)}s] #149 mergeState={state} head={d.get('headRefOid')} mergeable={d.get('mergeable')}", flush=True)
            if state == "CLEAN":
                mout, merr, mrc = run(["gh", "pr", "merge", "149", "--squash", "--delete-branch"])
                if mrc != 0:
                    print(f"MERGE FAILED rc={mrc}: {merr}", flush=True)
                    return 1
                print(f"MERGED: {mout}", flush=True)
                time.sleep(5)
                _, _, rc2 = run(["gh", "pr", "view", "149", "--json", "state"])
                so, se, _ = run(["git", "ls-remote", "origin", "main"])
                print(f"main now: {so.splitlines()[0] if so else 'UNKNOWN'}", flush=True)
                if so and BASE_SHA not in so:
                    print("PR149=MERGED main advanced past B3 base", flush=True)
                    return 0
                print("PR149=MERGE-UNVERIFIED main did not advance as expected", flush=True)
                return 1
            if state == "BLOCKED":
                time.sleep(60)
                continue
            print(f"BAD MERGE STATE {state}; stopping for adjudication", flush=True)
            return 1
        else:
            print(f"status probe failed rc={rc}: {err[:200]}; retry", flush=True)
            time.sleep(30)
    print("TIMEOUT waiting for #149 CI", flush=True)
    return 2


if __name__ == "__main__":
    sys.exit(main())
