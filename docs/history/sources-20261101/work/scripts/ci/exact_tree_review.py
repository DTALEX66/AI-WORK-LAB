"""NX-720 exact-tree review primitives.

Read-only review of the current Git tree. It does not read credential contents,
perform network calls, mutate files, or make release decisions on behalf of a
human approver.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
ACTIVE_MODULES = {
    "packages/client-neutral-core",
    "apps/observer",
}
FORBIDDEN_PATH_MARKERS = (
    ".env", ".pem", ".key", "node_modules", "__pycache__", ".sqlite", ".db",
    "/dist/", "/build/", "/target/",
)
FORBIDDEN_EXTENSIONS = {".exe", ".dll", ".so", ".dylib", ".bin"}
REQUIRED_TASKS = (
    "NX-000", "NX-100", "NX-110", "NX-200", "NX-210", "NX-300", "NX-310",
    "NX-320", "NX-400", "NX-410", "NX-500", "NX-510", "NX-520", "NX-600",
    "NX-700", "NX-710",
)
REQUIRED_HANDOFFS = tuple(
    f"taskpacks/current/{task}-" for task in REQUIRED_TASKS if task != "NX-000"
)
REQUIRED_VERIFIERS = (
    "scripts/ci/verify_source_health.py",
    "scripts/ci/verify_offline_pilot.py",
    "scripts/ci/verify_regression_report.py",
    "packages/client-neutral-core/scripts/verify_standard_validators.py",
    "packages/client-neutral-core/scripts/verify_production_evidence.py",
    "packages/client-neutral-core/scripts/verify_design_contract.py",
    "packages/client-neutral-core/scripts/verify_task_ledger_replay.py",
    "packages/client-neutral-core/scripts/verify_usage_ingestion.py",
)


def _run(*args: str) -> str:
    return subprocess.run(args, cwd=ROOT, text=True, encoding="utf-8", errors="replace", capture_output=True, check=True).stdout.strip()


def tracked_paths() -> list[str]:
    return [line for line in _run("git", "ls-files").splitlines() if line]


def tree_digest(paths: list[str]) -> str:
    payload = "\n".join(paths).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def review_tree() -> dict[str, Any]:
    paths = tracked_paths()
    normalized = ["/" + path.replace("\\", "/") + "/" for path in paths]
    forbidden = []
    for path in paths:
        lower = path.replace("\\", "/").lower()
        # A tracked .env.template is a configuration template, not a credential
        # store; real .env/auth/key material remains forbidden.
        is_safe_template = lower.endswith("/.env.template")
        if any(marker in lower for marker in FORBIDDEN_PATH_MARKERS) and not is_safe_template:
            forbidden.append(path)
        if Path(path).suffix.lower() in FORBIDDEN_EXTENSIONS:
            forbidden.append(path)
    forbidden = sorted(set(forbidden))
    active_module_presence = {
        module: any(path == module or path.startswith(module + "/") for path in paths)
        for module in sorted(ACTIVE_MODULES)
    }
    absent_transferred = [
        path for path in paths
        if path.startswith("20-design/open-design/") or path.startswith("30-products/minigame/")
    ]
    ledger_path = ROOT / ".hermes/task-runtime/task-ledger/ledger.json"
    ledger = json.loads(ledger_path.read_text(encoding="utf-8")) if ledger_path.exists() else {}
    task_status = {task: ledger.get("tasks", {}).get(task, {}).get("status", "MISSING") for task in REQUIRED_TASKS}
    status = _run("git", "status", "--porcelain")
    current = _run("git", "rev-parse", "HEAD")
    origin = _run("git", "rev-parse", "origin/main")
    return {
        "schemaVersion": "work-lab/exact-tree-review/v1",
        "head": current,
        "originMain": origin,
        "worktreeClean": status == "",
        "trackedFiles": len(paths),
        "trackedTreeDigest": tree_digest(paths),
        "activeModulePresence": active_module_presence,
        "transferredScopeTracked": absent_transferred,
        "forbiddenTrackedPaths": forbidden,
        "taskStatus": task_status,
        "requiredHandoffsPresent": [
            next((path for path in paths if path.startswith(prefix)), None)
            for prefix in REQUIRED_HANDOFFS
        ],
        "requiredVerifiersPresent": {path: path in paths for path in REQUIRED_VERIFIERS},
        "ciWorkflowPresent": ".github/workflows/work-lab-gate.yml" in paths,
        "reviewerMode": "READ_ONLY",
        "credentialContentsRead": False,
        "externalWrites": False,
        "liveExecution": "UNKNOWN_NOT_RUN",
        "humanCalibration": "PENDING",
        "releaseApproval": "PENDING_HUMAN_APPROVAL",
    }
