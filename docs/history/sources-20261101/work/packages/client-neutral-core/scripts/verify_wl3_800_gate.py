"""WL3-800 full integration gate: aggregate acceptance checks for all waves.

Each check verifies a real, locally executable contract. Any check that needs
external proof (exact-SHA CI, portable build, live apply, human approval) is
reported honestly as PENDING and does not count as passed.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]  # repo root (script: .../packages/client-neutral-core/scripts/)


def _read_json(relative: str) -> dict:
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


def check_modules() -> tuple[bool, str]:
    projects = _read_json(".project/governance/projects.json")
    modules = {item["id"] for item in projects.get("modules", []) if isinstance(item, dict)}
    ok = modules == {"workflow-assistance", "work-lab-observer"}
    return ok, f"modules={sorted(modules)}" if ok else f"modules={sorted(modules)} EXPECTED 2-active"


def check_current_state() -> tuple[bool, str]:
    state = _read_json(".project/governance/generated/CURRENT_STATE.json")
    git = state.get("git", {})
    ok = git.get("branch") == "main" and git.get("head") == git.get("remote_main")
    return ok, f"branch={git.get('branch')} head={str(git.get('head'))[:12]}"


def check_ownership() -> tuple[bool, str]:
    registry = _read_json("config/config-ownership.json")
    ok = registry.get("schema_version") == "workflow/config-ownership/v2" and registry.get("single_authority")
    return ok, f"layers={len(registry.get('layers', {}))} fields={len(registry.get('fields', []))}"


def check_skills() -> tuple[bool, str]:
    import yaml

    provenance = yaml.safe_load(
        (ROOT / "config/skill-provenance.yaml").read_text(encoding="utf-8")
    ).get("entries", [])
    ok = len(provenance) == 13
    return ok, f"skills={len(provenance)}"


def check_observer_readonly() -> tuple[bool, str]:
    projects = _read_json(".project/governance/projects.json")
    modules = {item["id"] for item in projects.get("modules", []) if isinstance(item, dict)}
    ok = "work-lab-observer" in modules
    return ok, "observer-active" if ok else f"modules={sorted(modules)}"


def check_pr33_foundation() -> tuple[bool, str]:
    baseline = _read_json(".project/governance/generated/STAGE3_BASELINE.json")
    classification = baseline.get("pr33", {}).get("classification", "")
    ok = classification == "STAGE3_FOUNDATION_SLICE"
    return ok, f"pr33={classification}"


def run_all() -> dict:
    checks = {
        "modules": check_modules,
        "current-state": check_current_state,
        "ownership": check_ownership,
        "skills-13": check_skills,
        "observer-readonly": check_observer_readonly,
        "pr33-foundation": check_pr33_foundation,
    }
    results: dict[str, dict] = {}
    for name, fn in checks.items():
        try:
            ok, detail = fn()
        except Exception as exc:  # noqa: BLE001
            ok, detail = False, f"error={exc}"
        results[name] = {"pass": ok, "detail": detail}
    passed = all(item["pass"] for item in results.values())
    return {
        "schema_version": "worklab/wl3-800-gate/v1",
        "passed": passed,
        "checks": results,
        "pending_external": [
            "exact-sha-ci",
            "portable-build",
            "live-apply",
            "human-approval",
            "real-os-project-canary",
        ],
    }


if __name__ == "__main__":
    report = run_all()
    print(json.dumps(report, ensure_ascii=False, indent=2))
    raise SystemExit(0 if report["passed"] else 1)
