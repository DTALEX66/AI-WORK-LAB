# SPDX-License-Identifier: MIT
# Poll PR #141 (workbench UI real-data routes) to CLEAN, squash-merge, delete
# branch, sync local main. BEHIND -> update-branch and re-poll; DIRTY/UNSTABLE
# -> abort (do not force-merge). Uses forward-slash CWD (backslash paths get
# truncated by the tool layer).
import subprocess, time

CWD = "D:/All projects/DESIGN-LAB"
BRANCH = "feat/ui-realdata-routes"


def run(*args, shell=False):
    return subprocess.run(args, cwd=CWD, shell=shell,
                          capture_output=True, text=True, encoding="utf-8", errors="replace")


def gh_json(cmd):
    r = run("gh", "pr", "view", "141", "--json", cmd, "--jq", "{state: .state, merge: .mergeStateStatus}", shell=True)
    return r.stdout.strip(), r.returncode


def main():
    print("POLL-141 start", flush=True)
    for _ in range(120):
        out, rc = gh_json("state,mergeStateStatus")
        print(out, "rc=", rc, flush=True)
        if rc == 0:
            state = out.split("state: ")[1].split(",")[0]
            merge = out.split("merge: ")[1].split("}")[0].strip()
            if state == "CLOSED" or "MERGED" in out:
                print("POLL-141 ALREADY-MERGED", flush=True)
                break
            if merge == "CLEAN":
                m = run("gh", "pr", "merge", "141", "--squash",
                        "--delete-branch", "--admin", shell=True)
                print("MERGE rc=", m.returncode, m.stdout.strip(), m.stderr.strip(), flush=True)
                print("POLL-141 DONE" if m.returncode == 0 else "POLL-141 MERGE-FAILED", flush=True)
                return
            if merge == "BEHIND":
                run("gh", "pr", "update-branch", "141", shell=True)
                print("POLL-141 BEHIND -> re-updating", flush=True)
            else:
                print("POLL-141 DIRTY/UNSTABLE -> abort, not force-merging", flush=True)
                return
        time.sleep(45)
    print("POLL-141 TIMEOUT-NO-CLEAN", flush=True)


if __name__ == "__main__":
    main()
