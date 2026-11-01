"""Prove the defect ERR-126 records: the old gate accepted every one of the ten lies.

Swaps the committed verifier back in for the duration of the run, executes the same
falsification harness against it, then restores the new verifier and proves the
restore by digest. This is the reproducible "original failure" record the ledger
requires: same registry, same injections, exit code 1 because nothing turned red.
"""
from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
VERIFIER = ROOT / "scripts" / "ci" / "verify_future_candidate_registry.py"
HARNESS = ROOT / ".project-local" / "runs" / "convergence-20261007-d" / "falsify_candidate_decisions.py"
PY = ROOT / ".project-local" / "toolchains" / "wl-py311" / "Scripts" / "python.exe"


def run(cmd: list[str]) -> subprocess.CompletedText:
    return subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True,
                          encoding="utf-8", errors="replace")


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    new_bytes = VERIFIER.read_bytes()
    old = subprocess.run(["git", "show", f"HEAD:{VERIFIER.relative_to(ROOT).as_posix()}"],
                         cwd=ROOT, capture_output=True, text=True, encoding="utf-8")
    if old.returncode != 0:
        print("CANNOT-READ-OLD-VERIFIER", old.stderr[:200])
        return 2
    try:
        VERIFIER.write_text(old.stdout, encoding="utf-8", newline="\n")
        base = run([str(PY), str(VERIFIER)])
        print(f"old-gate-on-current-registry exit={base.returncode} {base.stdout.strip()[:110]}")
        harness = run([str(PY), str(HARNESS)])
        caught = harness.stdout.count("FALSIFIED")
        missed = harness.stdout.count("NOT-CAUGHT")
        print(f"old-gate falsification: FALSIFIED={caught} NOT-CAUGHT={missed} exit={harness.returncode}")
        for line in harness.stdout.splitlines():
            if "NOT-CAUGHT" in line:
                print("   uncaught:", line.strip()[:100])
        print(f"OLD_GATE_EXIT={harness.returncode}")
        return harness.returncode
    finally:
        VERIFIER.write_bytes(new_bytes)
        ok = hashlib.sha256(VERIFIER.read_bytes()).hexdigest() == hashlib.sha256(new_bytes).hexdigest()
        print("verifier-restored-by-digest", ok)


if __name__ == "__main__":
    sys.exit(main())
