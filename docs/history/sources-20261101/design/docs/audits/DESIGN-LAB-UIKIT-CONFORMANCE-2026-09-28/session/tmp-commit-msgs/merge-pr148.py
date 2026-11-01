# SPDX-License-Identifier: MIT
"""Wait for PR #148's CI (head 92a22f8) to settle green, then squash-merge and verify main advanced.

BLOCKED = transient (new head's checks not yet reported) -> keep polling.
UNSTABLE/DIRTY = hard stop.
exit 0 = merged + verified, 1 = hard fail, 2 = timeout.
"""
import json, subprocess, time

REPO = "DTALEX66/DESIGN-LAB"
PR = "148"
HEAD = "92a22f8d9c15a9457c9a1e5c7c9f9130956a52be"

def run(cmd, timeout=180):
    r = subprocess.run(cmd, cwd=r"D:\All projects\DESIGN-LAB",
                       capture_output=True, text=True, shell=False, timeout=timeout)
    return (r.stdout or "").strip(), (r.stderr or "").strip(), r.returncode

def merge_state():
    out, _, _ = run(["gh", "pr", "view", PR, "--json", "state,mergeable,mergeStateStatus,headRefOid"])
    return json.loads(out)

main_before = run(["git", "ls-remote", "origin", "main"])[0].split()[0]
print(f"[{time.strftime('%H:%M:%S')}] waiting for CI; main before = {main_before[:12]}")

deadline = time.time() + 1500
while time.time() < deadline:
    st = merge_state()
    ms = st.get("mergeStateStatus")
    head = st.get("headRefOid", "")[:12]
    print(f"[{time.strftime('%H:%M:%S')}] state={st.get('state')} merge={st.get('mergeable')} "
          f"ms={ms} head={head} (expect {HEAD[:12]})")
    if st.get("state") in ("MERGED", "CLOSED"):
        print("PR no longer open:", st)
        raise SystemExit(0 if st.get("state") == "MERGED" else 1)
    if head != HEAD[:12]:
        print("head moved — re-evaluate manually")
        raise SystemExit(2)
    if ms in ("UNSTABLE", "DIRTY", "UNKNOWN"):
        print(f"hard-stop: mergeStateStatus={ms}")
        raise SystemExit(1)
    if ms == "CLEAN":
        break
    # BLOCKED / BEHIND = transient: keep polling
    time.sleep(45)

if merge_state().get("mergeStateStatus") != "CLEAN":
    print("timed out before CLEAN")
    raise SystemExit(2)

print("CLEAN — merging (squash, per repo history) and deleting branch")
out, err, rc = run(["gh", "pr", "merge", PR, "--squash", "--delete-branch"])
print("merge rc:", rc, (out + err)[:300])
if rc != 0:
    raise SystemExit(1)

# verify main actually advanced (MERGED != advanced when protection blocks)
time.sleep(5)
main_after = run(["git", "ls-remote", "origin", "main"])[0].split()[0]
print(f"main: {main_before[:12]} -> {main_after[:12]}  advanced={main_before != main_after}")
mc = json.loads(run(["gh", "pr", "view", PR, "--json", "mergeCommit,mergedAt"])[0])
print("mergeCommit:", mc.get("mergeCommit", {}).get("oid", "")[:12], "mergedAt:", mc.get("mergedAt"))
raise SystemExit(0 if main_before != main_after else 1)
