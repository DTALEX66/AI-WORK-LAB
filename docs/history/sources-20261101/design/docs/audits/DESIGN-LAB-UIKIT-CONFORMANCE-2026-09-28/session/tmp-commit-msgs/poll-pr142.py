# SPDX-License-Identifier: MIT
# Poll PR #142 (P1-3 library index guard) to CLEAN, squash-merge, delete branch.
# Robust JSON parsing of `gh pr view --json` (the earlier text-split version
# crashed on JSON output). BEHIND -> update-branch then re-poll. DIRTY/UNSTABLE
# -> abort, never force-merge.
import subprocess, time, json

CWD = "D:/All projects/DESIGN-LAB"
PR = "142"


def run(*args, shell=False):
    return subprocess.run(args, cwd=CWD, shell=shell,
                          capture_output=True, text=True, encoding="utf-8", errors="replace")


def pr_fields():
    r = run("gh", "pr", "view", PR, "--json", "state,mergeStateStatus", shell=True)
    if r.returncode != 0:
        return None, None, r.stderr.strip()
    try:
        d = json.loads(r.stdout.strip())
    except Exception as exc:
        return None, None, f"json parse: {exc}"
    return d.get("state"), d.get("mergeStateStatus"), None


def main():
    print("POLL-142 start", flush=True)
    for i in range(160):
        state, merge, err = pr_fields()
        if err:
            print(f"[{i}] gh error: {err}", flush=True)
            time.sleep(45)
            continue
        print(f"[{i}] state={state} merge={merge}", flush=True)
        if state == "CLOSED":
            m = run("gh", "pr", "view", PR, "--json", "mergedAt", "--jq",
                    "(if .mergedAt then \"MERGED\" else \"CLOSED-UNMERGED\")", shell=True)
            print("POLL-142 " + m.stdout.strip(), flush=True)
            return
        if merge == "CLEAN":
            m = run("gh", "pr", "merge", PR, "--squash", "--delete-branch", shell=True)
            ok = m.returncode == 0
            print("MERGE rc=", m.returncode, m.stdout.strip(), m.stderr.strip(), flush=True)
            print("POLL-142 DONE" if ok else "POLL-142 MERGE-FAILED", flush=True)
            return
        if merge == "BEHIND":
            run("gh", "pr", "update-branch", PR, shell=True)
            print("POLL-142 BEHIND -> re-updating branch", flush=True)
            time.sleep(30)
        else:
            print(f"POLL-142 DIRTY/UNSTABLE ({merge}) -> abort, not force-merging", flush=True)
            return
        time.sleep(45)
    print("POLL-142 TIMEOUT-NO-CLEAN", flush=True)


if __name__ == "__main__":
    main()
