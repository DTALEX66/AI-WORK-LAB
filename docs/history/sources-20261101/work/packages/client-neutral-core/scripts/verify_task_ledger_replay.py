#!/usr/bin/env python3
"""Task Ledger replay + side-effect consistency verifier (NX-410).

Runs all 8 failure scenarios; every scenario must be PASS (idempotent, no
duplicate side effect) or FAIL_CLOSED (never silently mis-runs).
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
WF_SCRIPTS = ROOT / "packages" / "client-neutral-core" / "scripts"
sys.path.insert(0, str(WF_SCRIPTS))

from task_ledger_replay import run_all_scenarios  # noqa: E402


def verify() -> dict:
    results = run_all_scenarios()["scenarios"]
    errors: list[str] = []
    if len(results) != 8:
        errors.append(f"expected 8 scenarios, got {len(results)}")
    for r in results:
        if r["outcome"] not in ("PASS", "FAIL_CLOSED"):
            errors.append(f"{r['scenario']}: unexpected outcome {r['outcome']}")
        if r["outcome"] == "PASS" and r.get("duplicate_side_effect"):
            errors.append(f"{r['scenario']}: duplicate side effect detected")
    if errors:
        raise ValueError("; ".join(errors))
    return {"scenarios": len(results),
            "pass": sum(1 for r in results if r["outcome"] == "PASS"),
            "fail_closed": sum(1 for r in results if r["outcome"] == "FAIL_CLOSED")}


def main() -> int:
    try:
        result = verify()
    except (ValueError, ImportError) as exc:
        print(f"TASK_LEDGER_REPLAY_FAIL {exc}")
        return 1
    print(
        f"TASK_LEDGER_REPLAY_PASS scenarios={result['scenarios']} pass={result['pass']} "
        f"fail_closed={result['fail_closed']} no_duplicate_side_effect=true"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
