# SPDX-License-Identifier: MIT
"""Background merge-poller for DESIGN-LAB PR #151 (G-5/B5).

Polls `gh pr view 151 --json state,mergeable,mergeStateStatus,headRefOid`
every 30s until mergeStateStatus settles at CLEAN (ready to merge) or the
PR leaves OPEN. BLOCKED/BEHIND/UNKNOWN are WAITING states under strict
9-check protection (recomputation after update-branch is asynchronous);
only DIRTY/UNSTABLE abort. The script NEVER merges -- it only reports;
the mainline performs the merge so the provenance stays on the mainline.

Run (project wrapper, single command):
    python "$HERMES_HOME/bin/hermes-project-data.py" --project . run -- \
        python .project-local/tmp-commit-msgs/poll-pr151.py
"""
import json
import subprocess
import sys
import time

ROOT = r"D:\All projects\DESIGN-LAB"
PR = "151"
POLL_S = 30
DEADLINE_S = 20 * 60


def gh(*args: str) -> tuple[int, str]:
    r = subprocess.run(["gh", *args], cwd=ROOT, capture_output=True, text=True, timeout=60)
    return r.returncode, (r.stdout + r.stderr).strip()


def main() -> int:
    deadline = time.time() + DEADLINE_S
    while time.time() < deadline:
        rc, out = gh("pr", "view", PR, "--json",
                     "state,mergeable,mergeStateStatus,headRefOid", "--jq", ".")
        if rc != 0:
            # transient gh/API error: retry, do not abort the wait
            print(f"[poll {PR}] gh rc={rc}: {out[:300]}", flush=True)
        else:
            try:
                st = json.loads(out)
            except json.JSONDecodeError:
                print(f"[poll {PR}] non-json stdout: {out[:300]}", flush=True)
                st = None
            if st is not None:
                status = st.get("mergeStateStatus")
                print(f"[poll {PR}] state={st.get('state')} mergeable={st.get('mergeable')} "
                      f"status={status} head={str(st.get('headRefOid'))[:12]}", flush=True)
                if st.get("state") != "OPEN":
                    print(f"[poll {PR}] PR left OPEN -> {st.get('state')}", flush=True)
                    return 0
                if status == "CLEAN":
                    print(f"[poll {PR}] READY_TO_MERGE (all required checks green on head)",
                          flush=True)
                    return 0
                if status in ("DIRTY", "UNSTABLE"):
                    print(f"[poll {PR}] ABORT {status}", flush=True)
                    return 1
                # BLOCKED / BEHIND / UNKNOWN: keep waiting (strict-protection wait states)
        time.sleep(POLL_S)
    print(f"[poll {PR}] TIMEOUT after {DEADLINE_S}s -- re-check manually", flush=True)
    return 2


if __name__ == "__main__":
    sys.exit(main())
