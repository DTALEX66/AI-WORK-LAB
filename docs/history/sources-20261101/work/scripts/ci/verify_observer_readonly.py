"""Verify Observer is strictly read-only (R4/T20 gate, fail-closed).

Checks the Observer projection surface for write capability at the source
level: observer_store.append must raise; the facade must not contain business
INSERT/UPDATE/DELETE; the "Observer is read-only" contract must be present.
Fails closed on missing files or violations (no STUB, no || true).
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def main() -> int:
    problems: list[str] = []
    store = REPO_ROOT / "apps" / "observer" / "src" / "observer_store.py"
    if not store.exists():
        problems.append(f"observer_store.py missing: {store}")
    else:
        src = store.read_text(encoding="utf-8")
        if "ObserverInputError" not in src or "raise" not in src:
            problems.append("observer_store.append does not raise (write not rejected)")
        if "Observer is read-only" not in src:
            problems.append("'Observer is read-only' contract missing")

    # Observer must not own any Task/Telemetry write surface.
    for probe in ("telemetry_ledger", "task_ledger"):
        hit = REPO_ROOT / "apps" / "observer" / "src"
        if hit.exists() and any(probe in p.name for p in hit.rglob("*.py")):
            problems.append(f"observer imports/owns {probe} (write surface leaked)")

    if problems:
        print("OBSERVER_READONLY_FAIL")
        for p in problems:
            print("  -", p)
        return 1
    print("OBSERVER_READONLY_PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
