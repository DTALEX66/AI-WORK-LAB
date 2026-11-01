#!/usr/bin/env python3
"""Generate and verify WORK-LAB's current canonical state.

The generator is repository-local and secret-free. It reads canonical registries,
repository-managed skill metadata, the Stage 3 graph/baseline, the root CI
workflow, and optional explicit CI evidence. It never reads Hermes Home, auth
stores, provider configuration, sessions, or prompt/response bodies.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import yaml


DEFAULT_CI_EVIDENCE = Path(".project-local/artifacts/current-state-ci.json")
DEFAULT_RUNTIME_ATTESTATION = Path(".project-local/artifacts/current-state-runtime-attestation.json")
CANONICAL_FILES = (
    "docs/decisions/PROJECT_POSITIONING.md",
    ".project/governance/projects.json",
    ".project/governance/module-ownership.json",
    ".project/governance/contracts/contract-catalog.json",
    ".project/governance/contracts/source-ledger.schema.json",
    ".project/governance/contracts/capability-conformance.schema.json",
    ".project/governance/source-ledger.json",
    ".project/governance/work-lab.project-profile.yaml",
    "README.md",
    "knowledge-staging/README.md",
    "packages/client-neutral-core/workflow-manifest.yaml",
    "config/capability-conformance.json",
    "packages/contracts/schemas/workflow/ci-observation.schema.json",
    "packages/contracts/schemas/workflow/model-policy.schema.json",
    "packages/contracts/schemas/workflow/memory-record.schema.json",
    "packages/contracts/schemas/workflow/rule-drift.schema.json",
    "packages/contracts/schemas/workflow/project-profile.schema.json",
    "packages/client-neutral-core/scripts/ci_watcher.py",
    "services/policy/model_policy.py",
    "packages/client-neutral-core/scripts/growth_candidates.py",
    "packages/client-neutral-core/scripts/growth_watcher.py",
    "packages/client-neutral-core/scripts/impact_planner.py",
    "services/orchestration/run_taskpack_agent.py",
    "packages/client-neutral-core/scripts/task_ledger.py",
    "apps/observer/schemas/observer-event.schema.json",
    "apps/observer/src/observer_runtime.py",
    "apps/observer/src/observer_evidence.py",
    "apps/observer/src/observer_store.py",
    "config/skill-provenance.yaml",
    ".github/workflows/work-lab-gate.yml",
)
SUPPORT_AREAS = (
    ("governance", ".project/governance"),
    ("knowledge", "knowledge-staging"),
    ("taskpacks", "taskpacks/current"),
    ("archive_manifests", "docs/history/archive-manifests"),
    ("root_delivery", ".github"),
)
STALE_WORKFLOW = "workflow-governance"


def _read_json(root: Path, relative: str) -> dict[str, Any]:
    value = json.loads((root / relative).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected object: {relative}")
    return value


def _read_yaml(root: Path, relative: str) -> dict[str, Any]:
    value = yaml.safe_load((root / relative).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected mapping: {relative}")
    return value


def _canonical_bytes(path: Path) -> bytes:
    return path.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _source_files(root: Path) -> list[tuple[str, Path]]:
    paths: dict[str, Path] = {}
    for relative in CANONICAL_FILES:
        path = root / relative
        if not path.is_file():
            raise ValueError(f"canonical source missing: {relative}")
        paths[relative] = path
    provenance = _read_yaml(root, "config/skill-provenance.yaml")
    for entry in provenance.get("entries", []):
        if not isinstance(entry, dict):
            raise ValueError("skill provenance entry must be a mapping")
        relative = entry.get("source")
        if not isinstance(relative, str):
            raise ValueError("skill provenance source must be a string")
        path = root / relative
        if not path.is_file():
            raise ValueError(f"skill source missing: {relative}")
        paths[relative] = path
    return sorted(paths.items())


def source_digest(root: Path) -> str:
    digest = hashlib.sha256()
    for relative, path in _source_files(root):
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(_canonical_bytes(path))
        digest.update(b"\0")
    return digest.hexdigest()


def _changed_sources(root: Path, projection: Path) -> list[str]:
    """Name the sources that moved since the projection was last committed.

    A single rolled digest over ~40 files cannot say which one moved, and "just regenerate it" is not a
    diagnosis when the mover is something nobody meant to fold into the current-state picture. Answered
    from git history rather than mtimes, so the verdict does not depend on which machine checked out
    the tree last.
    """
    try:
        relative = projection.relative_to(root).as_posix()
        commit = subprocess.run(["git", "log", "-1", "--format=%H", "--", relative], cwd=root,
                                capture_output=True, check=True).stdout.decode("utf-8", "replace").strip()
        if not commit:
            return []
        names = [relative_name for relative_name, _ in _source_files(root)]
        out = subprocess.run(["git", "diff", "--name-only", commit, "HEAD", "--", *names],
                             cwd=root, capture_output=True, check=True).stdout
        return [line.decode("utf-8", "replace").strip() for line in out.splitlines() if line.strip()][:10]
    except (OSError, ValueError, subprocess.CalledProcessError):
        return []


def content_digest(state: dict[str, Any]) -> str:
    payload = {key: value for key, value in state.items() if key != "generated_at"}
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return sha256_bytes(encoded)


def projection_digest(state: dict[str, Any]) -> str:
    """Digest deterministic tracked projection fields without recursive identity."""
    volatile = {"generated_at", "content_digest"}
    payload = {key: value for key, value in state.items() if key not in volatile}
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return sha256_bytes(encoded)


def _git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=root, text=True, encoding="utf-8", errors="replace", capture_output=True, check=False
    )
    if result.returncode:
        return "unknown"
    return result.stdout.strip()


def _registry_count(root: Path, relative: str, key: str) -> int:
    value = _read_json(root, relative).get(key)
    if not isinstance(value, (list, dict)):
        raise ValueError(f"registry key is not countable: {relative}#{key}")
    return len(value)


def _workflow_identity(root: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    workflow = _read_yaml(root, ".github/workflows/work-lab-gate.yml")
    jobs = workflow.get("jobs", {})
    if not isinstance(jobs, dict):
        raise ValueError("root workflow jobs must be a mapping")
    display_names: dict[str, str] = {}
    for key, value in jobs.items():
        if isinstance(value, dict):
            display_names[str(key)] = str(value.get("name", key))
    declared = manifest.get("delivery", {}).get("required_workflows", [])
    if not isinstance(declared, list):
        declared = []
    return {
        "workflow_file": ".github/workflows/work-lab-gate.yml",
        "workflow_name": str(workflow.get("name", "unknown")),
        "job_names": sorted(display_names),
        "job_display_names": display_names,
        "aggregate_job": "aggregate" if "aggregate" in jobs else None,
        "manifest_declared_required_workflows": [str(item) for item in declared],
    }


def _compact_ci(evidence: Path | None) -> dict[str, Any]:
    if evidence is None or not evidence.is_file():
        return {"status": "unknown", "evidence": "not-provided"}
    value = json.loads(evidence.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("CI evidence must be a JSON object")
    jobs = value.get("jobs", [])
    compact_jobs: list[dict[str, Any]] = []
    if isinstance(jobs, list):
        for job in jobs:
            if isinstance(job, dict):
                compact_jobs.append(
                    {
                        "name": str(job.get("name", "unknown")),
                        "status": str(job.get("status", "unknown")),
                        "conclusion": str(job.get("conclusion", "unknown")),
                    }
                )
    return {
        "run_id": value.get("databaseId", value.get("run_id")),
        "workflow_name": value.get("workflowName", value.get("workflow_name")),
        "status": value.get("status", "unknown"),
        "conclusion": value.get("conclusion", "unknown"),
        "head_sha": value.get("headSha", value.get("head_sha")),
        "url": value.get("url"),
        "attempt": value.get("attempt", value.get("runAttempt")),
        "jobs": sorted(compact_jobs, key=lambda item: item["name"]),
    }


def _compact_portable_readback(evidence: Path | None) -> dict[str, Any]:
    if evidence is None or not evidence.is_file():
        return {"status": "not-provided"}
    value = json.loads(evidence.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("portable readback evidence must be a JSON object")
    return {
        "status": str(value.get("status", "unknown")),
        "skill_count": value.get("skill_count"),
        "structural_checks": str(value.get("structural_checks", "unknown")),
        "runtime_compatibility": str(value.get("runtime_compatibility", "unknown")),
        "live_home_touched": bool(value.get("live_home_touched", False)),
    }


def _optional_read_json(root: Path, relative: str) -> dict[str, Any] | None:
    """Optional read for demoted historical inputs (Stage 3, P0-03).

    A missing file is NOT an error: the historical block degrades to
    role=historical_only with null values. When the file exists its content
    is digested into compatibility_history so --check-current recomputes
    deterministically (STALE/DRIFT semantics, never a hard error).
    """
    path = root / relative
    if not path.is_file():
        return None
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected object: {relative}")
    return value


def build_state(
    root: Path,
    *,
    ci_evidence: Path | None = None,
    portable_readback: Path | None = None,
) -> dict[str, Any]:
    root = root.resolve()
    projects = _read_json(root, ".project/governance/projects.json")
    ownership = _read_json(root, ".project/governance/module-ownership.json")
    catalog = _read_json(root, ".project/governance/contracts/contract-catalog.json")
    manifest = _read_yaml(root, "packages/client-neutral-core/workflow-manifest.yaml")
    provenance = _read_yaml(root, "config/skill-provenance.yaml")
    stage3_graph = _optional_read_json(root, "taskpacks/current/WORK-LAB-STAGE-3-TASK-GRAPH.json")
    stage3_baseline = _optional_read_json(root, ".project/governance/generated/STAGE3_BASELINE.json")
    modules = projects.get("modules", [])
    if not isinstance(modules, list):
        raise ValueError("projects.modules must be a list")
    skills = provenance.get("entries", [])
    if not isinstance(skills, list):
        raise ValueError("skill provenance entries must be a list")
    skill_items = []
    for entry in skills:
        if not isinstance(entry, dict):
            raise ValueError("skill provenance entry must be a mapping")
        source = str(entry["source"])
        skill_items.append(
            {
                "name": str(entry["name"]),
                "source": source,
                "version": str(entry.get("version", "unknown")),
                "source_sha256": sha256_bytes(_canonical_bytes(root / source)),
                "trust": str(entry.get("trust", "unknown")),
                "enabled": bool(entry.get("enabled", False)),
                "live_readback": "not-run",
            }
        )
    state: dict[str, Any] = {
        "schema_version": "work-lab-current-state/v1",
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "source_digest": source_digest(root),
        "checkout_attestation": {
            "status": "RUNTIME_REQUIRED",
            "tracked_projection": "NO_HEAD_OR_BRANCH_CLAIM",
            "ci_without_exact_runtime_evidence": "UNVERIFIED_MAIN_CI",
        },
        "modules": [
            {
                "id": str(item.get("id")),
                "path": str(item.get("path")),
                "role": str(item.get("role", "unknown")),
            }
            for item in modules
            if isinstance(item, dict)
        ],
        "module_ownership": {
            "single_writer": bool(ownership.get("singleWriter", False)),
            "cross_module_writes": ownership.get("crossModuleWrites", "unknown"),
        },
        "support_areas": [
            {"id": identifier, "path": path, "present": (root / path).is_dir()}
            for identifier, path in SUPPORT_AREAS
        ],
        "contracts": {
            "count": len(catalog.get("contracts", [])),
            "schema_version": catalog.get("schemaVersion", "unknown"),
        },
        "skills": {
            "count": len(skill_items),
            "items": sorted(skill_items, key=lambda item: item["name"]),
            "isolated_portable_readback": _compact_portable_readback(portable_readback),
        },

        "workflow_identity": _workflow_identity(root, manifest),
        # P0-03: historical Stage 3 data is NOT a current-identity source. It is
        # emitted under an explicit `compatibility_history` key so CURRENT_STATE
        # stops treating Stage 3 as who we are "now" — it only records what the
        # Stage 3 baseline historically was. Current identity comes from the
        # governance registries above (projects / module-ownership / contracts /
        # skills / workflow identity), not from this block.
        "compatibility_history": {
            "stage3_taskpack_id": stage3_graph.get("taskpackId", None) if stage3_graph is not None else None,
            "stage3_task_count": len(stage3_graph.get("tasks", [])) if stage3_graph is not None else None,
            "stage3_initial_state": stage3_graph.get("initialState", None) if stage3_graph is not None else None,
            "historical_baseline_source": ".project/governance/generated/STAGE3_BASELINE.json",
            "historical_baseline_present": stage3_baseline is not None,
            "historical_baseline_status": "HISTORICAL_ONLY",
            "role": "historical_only_not_current_identity",
        },
        "unverified_capabilities": [
            "hermes_live_apply",
            "paid_provider_smoke",
            "transferred_visual_calibration",
            "real_device_validation",
            "commercial_release",
        ],
    }
    state["content_digest"] = content_digest(state)
    return state


def build_runtime_attestation(
    root: Path,
    *,
    ci_evidence: Path | None = None,
) -> dict[str, Any]:
    """Bind the live checkout and optional exact-SHA CI outside tracked source."""

    root = root.resolve()
    status = _git(root, "status", "--short")
    dirty_lines = [line for line in status.splitlines() if line.strip() and line != "unknown"]
    return {
        "schema_version": "work-lab-runtime-attestation/v1",
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "git": {
            "head": _git(root, "rev-parse", "HEAD"),
            "branch": _git(root, "branch", "--show-current"),
            "head_tree": _git(root, "rev-parse", "HEAD^{tree}"),
            "remote_main": _git(root, "rev-parse", "origin/main"),
            "dirty_count": len(dirty_lines),
        },
        "writer": {"state": "UNIQUE"},
        "ci": _compact_ci(ci_evidence),
    }


def check_stale_references(paths: Iterable[Path]) -> list[str]:
    findings: list[str] = []
    for path in paths:
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        lowered = text.lower()
        if STALE_WORKFLOW in lowered:
            findings.append(f"{path}: stale-workflow-name={STALE_WORKFLOW}")
        if "not committed/pushed" in lowered or "not committed or pushed" in lowered:
            findings.append(f"{path}: stale-publication-status")
        if re.search(r"active module[^\n]*(minigame|fourth)", lowered):
            findings.append(f"{path}: fourth-active-module")
    return findings


def _canonical_doc_paths(root: Path) -> list[Path]:
    relative = [
        "docs/decisions/PROJECT_POSITIONING.md",
        ".project/governance/projects.json",
        ".project/governance/module-ownership.json",
        ".project/governance/contracts/contract-catalog.json",
        "README.md",
        "knowledge-staging/README.md",
        "packages/client-neutral-core/workflow-manifest.yaml",
        "packages/client-neutral-core/README.md",
    ]
    return [root / item for item in relative if (root / item).is_file()]


def render_markdown(state: dict[str, Any]) -> str:
    modules = "\n".join(f"- `{item['id']}` — `{item['path']}`" for item in state["modules"])
    unverified = "\n".join(f"- `{item}`" for item in state["unverified_capabilities"])
    return f"""# WORK-LAB current state

Generated at: `{state['generated_at']}`  \\
Source digest: `{state['source_digest']}`  \\
Content digest: `{state['content_digest']}`

## Git and CI attestation

- Checkout identity: `{state['checkout_attestation']['status']}`
- Tracked projection: `{state['checkout_attestation']['tracked_projection']}`
- CI without exact runtime evidence: `{state['checkout_attestation']['ci_without_exact_runtime_evidence']}`

## Active modules

{modules}

## Governance

- Contracts: `{state['contracts']['count']}`
- Repository skills: `{state['skills']['count']}`
- Single writer: `{state['module_ownership']['single_writer']}`
- Cross-module writes: `{state['module_ownership']['cross_module_writes']}`

## Workflow identity

- Workflow file: `{state['workflow_identity']['workflow_file']}`
- Workflow name: `{state['workflow_identity']['workflow_name']}`
- Aggregate job: `{state['workflow_identity']['aggregate_job']}`
- Manifest-declared required workflows: `{', '.join(state['workflow_identity']['manifest_declared_required_workflows']) or 'none'}`

## Compatibility history (Stage 3, historical only — NOT current identity)

- TaskPack: `{state['compatibility_history']['stage3_taskpack_id']}`
- Tasks: `{state['compatibility_history']['stage3_task_count']}`
- Initial state: `{state['compatibility_history']['stage3_initial_state']}`
- Historical baseline present: `{state['compatibility_history']['historical_baseline_present']}`
- Historical baseline source: `{state['compatibility_history']['historical_baseline_source']}`
- Historical baseline status: `{state['compatibility_history']['historical_baseline_status']}`

## Explicitly unverified

{unverified}
"""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--json-out", type=Path, default=Path(".project/governance/generated/CURRENT_STATE.json"))
    parser.add_argument("--markdown-out", type=Path, default=Path(".project/governance/generated/CURRENT_STATE.md"))
    parser.add_argument("--ci-evidence", type=Path)
    parser.add_argument("--portable-readback", type=Path)
    parser.add_argument("--runtime-attestation-out", type=Path)
    parser.add_argument("--check-stale", action="store_true")
    parser.add_argument("--check-current", action="store_true")
    args = parser.parse_args(argv)
    root = args.root.resolve()
    if args.check_stale:
        findings = check_stale_references(_canonical_doc_paths(root))
        if findings:
            print("CURRENT_STATE_STALE_DOC_FAIL")
            print("\n".join(findings))
            return 1
        projects = _read_json(root, ".project/governance/projects.json")
        modules = {str(item.get("id")) for item in projects.get("modules", []) if isinstance(item, dict)}
        if modules != {"workflow-assistance", "work-lab-observer"}:
            print("CURRENT_STATE_STALE_DOC_FAIL fourth-active-module")
            return 1
        print("CURRENT_STATE_STALE_DOC_PASS")
        return 0
    if args.check_current:
        json_path = args.json_out if args.json_out.is_absolute() else root / args.json_out
        markdown_path = args.markdown_out if args.markdown_out.is_absolute() else root / args.markdown_out
        if not json_path.is_file() or not markdown_path.is_file():
            print("CURRENT_STATE_FRESHNESS_FAIL projection-missing")
            return 1
        try:
            tracked = json.loads(json_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            print("CURRENT_STATE_FRESHNESS_FAIL projection-invalid")
            return 1
        default_ci = root / DEFAULT_CI_EVIDENCE
        ci_evidence = default_ci.resolve() if default_ci.is_file() else None
        expected = build_state(root, ci_evidence=ci_evidence)
        if tracked.get("source_digest") != expected["source_digest"]:
            print("CURRENT_STATE_FRESHNESS_FAIL source-digest-mismatch: "
                  f"recorded={str(tracked.get('source_digest'))[:12]} "
                  f"recomputed={expected['source_digest'][:12]}")
            for name in _changed_sources(root, markdown_path):
                print(f"  changed since the projection was last written: {name}")
            return 1
        if projection_digest(tracked) != projection_digest(expected):
            print("CURRENT_STATE_FRESHNESS_FAIL projection-digest-mismatch")
            return 1
        try:
            markdown = markdown_path.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            print("CURRENT_STATE_FRESHNESS_FAIL markdown-invalid")
            return 1
        if markdown != render_markdown(tracked):
            print("CURRENT_STATE_FRESHNESS_FAIL markdown-json-mismatch")
            return 1
        print(f"CURRENT_STATE_FRESHNESS_PASS source_digest={expected['source_digest']}")
        return 0
    ci_evidence = args.ci_evidence.resolve() if args.ci_evidence else None
    portable_readback = args.portable_readback.resolve() if args.portable_readback else None
    if ci_evidence is None:
        default_ci = root / DEFAULT_CI_EVIDENCE
        if default_ci.is_file():
            ci_evidence = default_ci.resolve()
    state = build_state(root, ci_evidence=ci_evidence, portable_readback=portable_readback)
    json_out = args.json_out if args.json_out.is_absolute() else root / args.json_out
    markdown_out = args.markdown_out if args.markdown_out.is_absolute() else root / args.markdown_out
    json_out.parent.mkdir(parents=True, exist_ok=True)
    markdown_out.parent.mkdir(parents=True, exist_ok=True)
    # newline="\n" is required, not cosmetic: these two artifacts are tracked and
    # .gitattributes declares eol=lf for *.json and *.md. Path.write_text() opens in
    # text mode, so on Windows every "\n" became "\r\n" and each regeneration put the
    # worktree back in violation of the declared policy.
    json_out.write_text(
        json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    markdown_out.write_text(render_markdown(state), encoding="utf-8", newline="\n")
    runtime_out = args.runtime_attestation_out
    if runtime_out is not None:
        runtime_out = runtime_out if runtime_out.is_absolute() else root / runtime_out
        allowed_root = (root / ".project-local" / "artifacts").resolve()
        runtime_out = runtime_out.resolve()
        if not runtime_out.is_relative_to(allowed_root):
            raise SystemExit("runtime attestation output must stay under .project-local/artifacts")
        runtime_out.parent.mkdir(parents=True, exist_ok=True)
        runtime_out.write_text(
            json.dumps(build_runtime_attestation(root, ci_evidence=ci_evidence), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
            newline="\n",
        )
    print(
        f"CURRENT_STATE_PASS projection={state['checkout_attestation']['tracked_projection']} "
        f"modules={len(state['modules'])} "
        f"skills={state['skills']['count']} contracts={state['contracts']['count']} "
        f"source_digest={state['source_digest']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())