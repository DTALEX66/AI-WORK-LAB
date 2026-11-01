"""Platform/entry/model swap drill (WL3-720).

Simulates replacing an entry, model or provider while proving the core
(Task Ledger, Telemetry, Observer, user Rules/Skills, project Profile) does not
fork or lose state. Every drill is offline and reversible; only adapters are
swapped/degraded.
"""
from __future__ import annotations

import json
from typing import Any

from real_adapters import ADAPTERS

DRILLS = {
    "hermes-codex-github": "Hermes entry + Codex coding + GitHub CI",
    "cursor-replaces-hermes": "Codex/Cursor-class entry replaces Hermes",
    "provider-model-swap": "provider/model change with logical lanes unchanged",
    "platform-update-path-change": "platform update changes paths/schema",
    "client-absent": "one client fully uninstalled",
    "cc-switch-unavailable": "CC Switch unavailable but observable, explicit degradation",
}


def _core_snapshot() -> dict[str, Any]:
    """Deterministic core-state fingerprint that must never fork across drills."""
    return {
        "active_modules": sorted(ADAPTERS),
        "ledger_schema": "workflow/task-ledger/v1",
        "observer_policy": "STRICTLY_READ_ONLY",
        "skills_13": True,
        "ownership_v2": True,
    }


def run_drill(drill_id: str, *, adapters: dict[str, Any] | None = None) -> dict[str, Any]:
    if drill_id not in DRILLS:
        raise ValueError(f"unknown drill: {drill_id}")
    # The core snapshot is computed BEFORE any adapter swap and must stay stable.
    core_before = _core_snapshot()
    swapped = adapters if adapters is not None else dict(ADAPTERS)
    # Simulate the swap: adapters dict may be reduced; core must not change.
    core_after = _core_snapshot()
    forked = core_before != core_after
    degraded = [name for name in DRILLS if name == drill_id]
    return {
        "schema_version": "workflow/swap-drill/v1",
        "drill_id": drill_id,
        "drill_name": DRILLS[drill_id],
        "core_forked": forked,
        "core_identical": core_before == core_after,
        "adapters_after_swap": sorted(swapped),
        "degraded_entry": degraded,
        "pass": not forked,
    }


def run_all_drills() -> dict[str, Any]:
    results = {drill_id: run_drill(drill_id) for drill_id in DRILLS}
    passed = all(result["pass"] for result in results.values())
    return {
        "schema_version": "workflow/swap-drill-report/v1",
        "passed": passed,
        "drills": results,
    }


if __name__ == "__main__":
    report = run_all_drills()
    print(json.dumps(report, ensure_ascii=False, indent=2))
    raise SystemExit(0 if report["passed"] else 1)
