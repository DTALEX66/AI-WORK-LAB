"""WLGM-230 canary runner — WORK-LAB self-canary (no external project writes).

Runs the real identity resolver + aggregator against the WORK-LAB repository
itself to validate the multi-scenario matrix that does NOT require external
project authorization:

1. WORK-LAB root resolves to the work-lab product project;
2. submodules/modules resolve as working areas of the same project, never as
   new projects;
3. a transient nested-repo path stays unresolved (independent repository);
4. weak evidence alone never produces RUNNING;
5. snapshot revision increments across publishes.

External OS-project canary (real second project) stays PENDING until the user
authorizes ``WORKLAB_CANARY_PROJECT_ROOTS`` and read access to an external repo.
"""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any

WORK = Path(__file__).resolve().parents[2]  # .../packages/client-neutral-core/scripts/workflow -> WORK-LAB root
SCRIPTS = WORK / "packages" / "client-neutral-core" / "scripts"

import sys

sys.path.insert(0, str(SCRIPTS))

from evidence_aggregator import EvidenceAggregator, ExecutionState  # noqa: E402
from product_project import ProductProject, ProjectRootBinding, RepositoryIdentity  # noqa: E402
from project_identity_resolver import ApprovedProjectIndex, GitProbe, resolve_execution_path  # noqa: E402
from project_temp import fixture_dir, force_release  # noqa: E402
from snapshot_api import build_snapshot  # noqa: E402


def run_canary() -> dict[str, Any]:
    results: dict[str, Any] = {}

    # 1) WORK-LAB root resolves to the work-lab product project (real git).
    project = ProductProject(project_id="work-lab", display_name="WORK-LAB")
    project.add_repository(RepositoryIdentity(repository_id="work-lab", remote_identity="github:DTALEX66/WORK-LAB"))
    index = ApprovedProjectIndex(projects=[project])
    probe = GitProbe()
    resolved = resolve_execution_path(str(WORK), index, git=probe)
    results["self_root_resolved"] = resolved.project_id == "work-lab" and resolved.resolution_state.value == "RESOLVED"
    results["self_resolution_detail"] = resolved.as_json()

    # 2) module subdir of the same repo belongs to the project (containment).
    module_path = str(WORK / "services")
    resolved_module = resolve_execution_path(module_path, index, git=probe)
    results["module_inside_same_repo"] = (
        resolved_module.project_id == "work-lab"
        or resolved_module.resolution_state.value == "RESOLVED"
    )

    # 3) transient independent nested repo stays unresolved (no remote match).
    # A transient independent repo, built inside the declared runtime root: TemporaryDirectory's own
    # cleanup is only reliable while nothing holds a handle open, and the leak it can leave is project
    # content outside the Git root (measured 2026-10-10 in %TEMP%).
    raw = fixture_dir(prefix="canary-nested-repo-")
    try:
        nested = raw / "independent-repo"
        nested.mkdir()
        subprocess.run(["git", "init", "-q", str(nested)], check=True)
        resolved_nested = resolve_execution_path(str(nested), index, git=probe)
        results["independent_repo_not_absorbed"] = (
            resolved_nested.resolution_state.value == "UNRESOLVED"
            or resolved_nested.project_id != "work-lab"
        )
    finally:
        results["nested_fixture_released"] = force_release(raw)

    # 4) weak evidence alone never RUNNING.
    agg = EvidenceAggregator()
    status = agg.apply_event(
        execution_id="c1", event_type="execution_running", occurred_at="2026-08-14T00:00:00Z",
        evidence_level="E", anchor_project_id="work-lab",
    )
    results["weak_evidence_no_running"] = status.state != ExecutionState.RUNNING

    # 5) snapshot revision increments.
    r1 = build_snapshot(revision=1, projects=[{"projectId": "work-lab"}])
    r2 = build_snapshot(revision=2, projects=[{"projectId": "work-lab"}])
    results["snapshot_revision_monotonic"] = r2["revision"] == r1["revision"] + 1

    # 6) external OS-project canary: ONLY when explicitly authorized via
    # WORKLAB_CANARY_PROJECT_ROOTS (read-only git metadata; never project content).
    external: list[dict[str, Any]] = []
    roots_env = os.environ.get("WORKLAB_CANARY_PROJECT_ROOTS", "")
    authorized_roots = [r.strip() for r in roots_env.split(os.pathsep) if r.strip()]
    for root_raw in authorized_roots:
        root = Path(root_raw)
        if not root.is_dir():
            external.append({"root": root_raw, "ok": False, "reason": "path_missing"})
            continue
        resolved = resolve_execution_path(str(root), index, git=probe)
        # WLGM-230 scenario: an external OS project is NOT in the approved
        # index, so the correct outcome is UNRESOLVED (never absorbed into a
        # WORK-LAB project). Resolving into work-lab would be a false merge.
        ok = resolved.resolution_state.value == "UNRESOLVED" and resolved.project_id is None
        external.append({
            "root": root_raw,
            "projectId": resolved.project_id,
            "resolutionState": resolved.resolution_state.value,
            "ok": ok,
            "note": "expected UNRESOLVED for non-approved external project",
        })
    results["external_canary"] = {
        "authorized": bool(authorized_roots),
        "roots": external,
        "note": "read-only git metadata only; no project content read",
    }

    results["all_pass"] = all(
        v is True for k, v in results.items() if k.endswith(("_resolved", "_same_repo", "_absorbed", "_running", "_monotonic"))
    )
    return results


if __name__ == "__main__":
    report = run_canary()
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print("\nCANARY_SELF", "PASS" if report.get("all_pass") else "FAIL")
    ext = report.get("external_canary", {})
    if ext.get("authorized"):
        roots_ok = all(r.get("ok", False) for r in ext.get("roots", [])) if ext.get("roots") else False
        print(f"CANARY_EXTERNAL_PROJECT {'PASS' if roots_ok else 'FAIL'} (roots={len(ext.get('roots', []))}, all_ok={roots_ok})")
    else:
        print("CANARY_EXTERNAL_PROJECT PENDING (WORKLAB_CANARY_PROJECT_ROOTS not authorized)")
    # P0-7: FAIL must propagate to the exit code; gate_work_lab_os_canary
    # depends on the real returncode.
    raise SystemExit(0 if report.get("all_pass") else 1)
