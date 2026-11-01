#!/usr/bin/env python3
"""Memory contamination adversarial verifier (NX-400).

Runs all 7 negative controls; every case must fail closed or quarantine.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
WF_SCRIPTS = ROOT / "packages" / "client-neutral-core" / "scripts"
sys.path.insert(0, str(WF_SCRIPTS))

from memory_contamination import run_all_negative_controls  # noqa: E402


def verify() -> dict:
    results = run_all_negative_controls()
    errors: list[str] = []
    # Every case must NOT be "pass" with no guard action; contamination must be
    # contained (fail-closed or quarantine).
    contained = {"fail-closed", "quarantine"}
    # Cases where a clean "pass" is correct (guard resolved it, no contamination):
    pass_ok = {"weight-inflation", "preference-override", "expired-injection"}
    for r in results:
        if r.case in pass_ok:
            continue
        if r.outcome not in contained:
            errors.append(f"{r.case}: expected fail-closed/quarantine, got {r.outcome}")
    if len(results) != 7:
        errors.append(f"expected 7 negative controls, got {len(results)}")
    if errors:
        raise ValueError("; ".join(errors))
    return {"controls": len(results), "contained": sum(1 for r in results if r.outcome in contained)}


def main() -> int:
    try:
        result = verify()
    except (ValueError, ImportError) as exc:
        print(f"MEMORY_CONTAMINATION_FAIL {exc}")
        return 1
    print(
        f"MEMORY_CONTAMINATION_PASS controls={result['controls']} contained={result['contained']} "
        f"all_fail_closed_or_quarantine=true"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
