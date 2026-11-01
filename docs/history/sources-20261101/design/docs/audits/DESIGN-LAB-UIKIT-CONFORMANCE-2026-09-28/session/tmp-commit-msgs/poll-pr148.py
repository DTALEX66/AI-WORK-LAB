# SPDX-License-Identifier: MIT
"""Poll PR #148 until all required status checks resolve. exit 0=clean, 1=fail, 2=timeout."""
import json, subprocess, time

def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True, shell=False, timeout=120)
    return r.stdout.strip()

head = "poll #148 start"
deadline = time.time() + 1500
while time.time() < deadline:
    out = run(["gh", "pr", "checks", "148"])
    pending = out.count("pending") + out.count("in_progress")
    failed  = out.count("fail")
    total_known = out.count("pass") + pending + failed
    print(f"[poll] pass≈{out.count('pass')} pending={pending} fail={failed}")
    if out and "pending" not in out and "in_progress" not in out:
        print("=== FINAL ===")
        print(out)
        raise SystemExit(1 if "fail" in out else 0)
    time.sleep(45)
print("timeout after 25min — still pending")
raise SystemExit(2)
