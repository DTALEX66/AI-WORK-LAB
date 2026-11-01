"""Reproduce the original failure ERR-127 records: the committed gate caught none of the lies."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
VERIFIER = ROOT / "scripts" / "ci" / "verify_model_registry_integrity.py"
HARNESS = ROOT / ".project-local" / "runs" / "convergence-20261007-d" / "falsify_model_claims.py"
PY = ROOT / ".project-local" / "toolchains" / "wl-py311" / "Scripts" / "python.exe"


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    new_bytes = VERIFIER.read_bytes()
    old = subprocess.run(["git", "show", f"HEAD:{VERIFIER.relative_to(ROOT).as_posix()}"],
                         cwd=ROOT, capture_output=True, text=True, encoding="utf-8")
    if old.returncode != 0:
        print("CANNOT-READ-COMMITTED-VERIFIER", old.stderr[:200])
        return 2
    try:
        VERIFIER.write_text(old.stdout, encoding="utf-8", newline="\n")
        base = subprocess.run([str(PY), str(VERIFIER)], cwd=ROOT, capture_output=True,
                              text=True, encoding="utf-8", errors="replace")
        print(f"committed-gate-on-bound-registry exit={base.returncode} "
              f"{base.stdout.strip().splitlines()[-1][:110]}")
        harness = subprocess.run([str(PY), str(HARNESS)], cwd=ROOT, capture_output=True,
                                 text=True, encoding="utf-8", errors="replace")
        print(f"committed-gate falsification: FALSIFIED={harness.stdout.count('FALSIFIED')} "
              f"NOT-CAUGHT={harness.stdout.count('NOT-CAUGHT')} exit={harness.returncode}")
        return harness.returncode
    finally:
        VERIFIER.write_bytes(new_bytes)
        print("verifier-restored", VERIFIER.read_bytes() == new_bytes)


if __name__ == "__main__":
    sys.exit(main())
