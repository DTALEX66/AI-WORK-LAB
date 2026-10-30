"""Read approved repository evidence once for the read-only Observer composition.

This module deliberately separates three non-live evidence classes from runtime
telemetry:

- PLAN: tracked TaskPack and approval-package declarations;
- STATIC_BASELINE: generated governance/current-state projections;
- HISTORY: the sanitized tracked error ledger.

The sidecar loads this bounded allow-list at startup. It does not recursively
scan the repository and never writes to the canonical store or source files.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import re
from typing import Any

# The projection needs the approval package's original table (statuses, WL3-… task ids, approvals).
# That text survives only in the byte-frozen 2026-10-09 cutover copy; `taskpacks/current/` held it until
# 2026-10-19, and the archived stub at taskpacks/history/pre-convergence-20261019/ is a 671 B pointer,
# not the document. Reading the frozen copy keeps the evidence real instead of silently dropping the source.
PLAN_PATH = Path("taskpacks/history/UI-PRIORITY-CUTOVER-20261009/original-tree/taskpacks/current/WORK-LAB-MASTER-2.0-APPROVAL-PACKAGE.md")
R2_STATUS_PATH = Path("taskpacks/history/WORK-LAB-OBSERVER-VISUAL-ASSETS-R2-STATUS.md")
CURRENT_STATE_PATH = Path(".project/governance/generated/CURRENT_STATE.json")
ERROR_LEDGER_PATH = Path("taskpacks/current/error-ledger.json")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _read_text(root: Path, relative: Path) -> str | None:
    path = root / relative
    try:
        if not path.is_file():
            return None
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return None


def _read_json(root: Path, relative: Path) -> dict[str, Any] | None:
    text = _read_text(root, relative)
    if text is None:
        return None
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        return None
    return value if isinstance(value, dict) else None


def _first_int(pattern: str, text: str) -> int | None:
    match = re.search(pattern, text, flags=re.MULTILINE)
    return int(match.group(1)) if match else None


def _historical_stage3(current: dict[str, Any] | None) -> dict[str, Any]:
    """Normalise the historical Stage 3 block regardless of projection vintage.

    P0-03 demoted the top-level `stage3` key to `compatibility_history` so
    CURRENT_STATE no longer treats Stage 3 as a current-identity source. This
    reader accepts the new `compatibility_history` projection first and falls
    back to the legacy `stage3` key, so both old and new projections keep
    working. The returned dict always exposes `taskpack_id` / `task_count`.
    """
    if not current:
        return {}
    block = current.get("compatibility_history")
    if isinstance(block, dict):
        return {
            "taskpack_id": block.get("stage3_taskpack_id", block.get("taskpack_id", "unknown")),
            "task_count": block.get("stage3_task_count", block.get("task_count")),
            "initial_state": block.get("stage3_initial_state", block.get("initial_state", "unknown")),
            "raw": block,
        }
    legacy = current.get("stage3")
    if isinstance(legacy, dict):
        return dict(legacy)
    return {}


def _status(text: str) -> str | None:
    match = re.search(r"^>\s*Status:\s*`([^`]+)`", text, flags=re.MULTILINE)
    return match.group(1).strip() if match else None


def _task_rows(text: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for line in text.splitlines():
        match = re.match(r"^\|\s*(WL3-[0-9/]+)\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|$", line)
        if not match:
            continue
        rows.append(
            {
                "taskId": match.group(1).strip(),
                "status": match.group(2).strip(),
                "evidence": match.group(3).strip(),
            }
        )
    return rows


def _approval_rows(text: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for line in text.splitlines():
        match = re.match(r"^\d+\.\s+\*\*(.+?)\*\*\s+—\s+(.+)$", line)
        if not match:
            continue
        detail = match.group(2).strip()
        if detail.startswith("✅") and re.search(r"未动|未执行|跳过|未登录", detail):
            state = "PARTIAL"
        elif detail.startswith("✅"):
            state = "COMPLETED"
        elif detail.startswith("⏸"):
            state = "DEFERRED"
        elif detail.startswith("❌"):
            state = "NOT_EXECUTED"
        else:
            state = "PENDING"
        rows.append({"label": match.group(1).strip(), "state": state, "detail": detail})
    return rows


def _plan_projection(text: str, current: dict[str, Any] | None) -> dict[str, Any]:
    stage3 = _historical_stage3(current)
    total = _first_int(r"^(\d+)\s+个\s+WL3\s+任务", text)
    return {
        "taskpackId": stage3.get("taskpack_id") or "WORK-LAB-MASTER-2.0",
        "status": _status(text),
        "counts": {
            "total": total if total is not None else stage3.get("task_count"),
            "verifiedLocal": _first_int(r"^\s*VERIFIED_LOCAL:\s*(\d+)", text),
            "blocked": _first_int(r"^\s*BLOCKED(?:\([^)]*\))?:\s*(\d+)", text),
            "reconcileRequired": _first_int(r"^\s*RECONCILE_REQUIRED:\s*(\d+)", text),
        },
        "tasks": _task_rows(text),
        "approvals": _approval_rows(text),
        "evidenceKind": "PLAN",
        "sourcePath": PLAN_PATH.as_posix(),
    }


def _governance_projection(current: dict[str, Any]) -> dict[str, Any]:
    return {
        "generatedAt": current.get("generated_at"),
        "modules": current.get("modules") if isinstance(current.get("modules"), list) else [],
        "supportAreas": current.get("support_areas") if isinstance(current.get("support_areas"), list) else [],
        "contracts": (current.get("contracts") or {}).get("count"),
        "skills": (current.get("skills") or {}).get("count"),
        "singleWriter": (current.get("module_ownership") or {}).get("single_writer"),
        "crossModuleWrites": (current.get("module_ownership") or {}).get("cross_module_writes"),
        # P0-03: the historical Stage 3 block is surfaced as compatibility
        # history (normalised across new/legacy projections), not as identity.
        "historicalStage3": _historical_stage3(current),
        "unverifiedCapabilities": current.get("unverified_capabilities") if isinstance(current.get("unverified_capabilities"), list) else [],
        "checkoutAttestation": current.get("checkout_attestation") or {},
        "evidenceKind": "STATIC_BASELINE",
        "sourcePath": CURRENT_STATE_PATH.as_posix(),
    }


def _history_projection(ledger: dict[str, Any]) -> dict[str, Any]:
    summary = ledger.get("summary") or {}
    errors = ledger.get("errors") if isinstance(ledger.get("errors"), list) else []
    recent: list[dict[str, Any]] = []
    for item in errors[-6:]:
        if not isinstance(item, dict):
            continue
        recent.append(
            {
                "errorId": item.get("error_id"),
                "taskId": item.get("task_id"),
                "title": item.get("title") or item.get("observed_error"),
                "classification": item.get("classification"),
                "statusAfter": item.get("status_after"),
                "remainingBoundary": item.get("remaining_boundary"),
            }
        )
    return {
        "generatedAt": ledger.get("generated_at"),
        "totalErrors": summary.get("total"),
        "byClassification": summary.get("by_classification") or {},
        "repeatPreventionRequired": summary.get("repeat_prevention_required"),
        "recentErrors": recent,
        "evidenceKind": "HISTORY",
        "sourcePath": ERROR_LEDGER_PATH.as_posix(),
    }


def load_workspace_evidence(project_root: Path) -> dict[str, Any]:
    """Load the bounded repository evidence allow-list for one sidecar lifetime."""
    root = project_root.resolve()
    loaded_at = _now()
    plan_text = _read_text(root, PLAN_PATH)
    r2_text = _read_text(root, R2_STATUS_PATH)
    current = _read_json(root, CURRENT_STATE_PATH)
    ledger = _read_json(root, ERROR_LEDGER_PATH)

    result: dict[str, Any] = {"loadedAt": loaded_at, "sources": []}
    if plan_text is not None:
        result["plan"] = _plan_projection(plan_text, current)
        result["sources"].append(
            {"path": PLAN_PATH.as_posix(), "evidenceKind": "PLAN", "loadedAt": loaded_at}
        )
    if current is not None:
        result["governance"] = _governance_projection(current)
        result["sources"].append(
            {
                "path": CURRENT_STATE_PATH.as_posix(),
                "evidenceKind": "STATIC_BASELINE",
                "generatedAt": current.get("generated_at"),
                "loadedAt": loaded_at,
            }
        )
    if ledger is not None:
        result["history"] = _history_projection(ledger)
        result["sources"].append(
            {
                "path": ERROR_LEDGER_PATH.as_posix(),
                "evidenceKind": "HISTORY",
                "generatedAt": ledger.get("generated_at"),
                "loadedAt": loaded_at,
            }
        )
    if r2_text is not None:
        result["designBaseline"] = {
            "status": _status(r2_text),
            "surface": "portable desktop component",
            "readOnly": True,
            "evidenceKind": "HISTORICAL_STATUS",
            "sourcePath": R2_STATUS_PATH.as_posix(),
        }
        result["sources"].append(
            {"path": R2_STATUS_PATH.as_posix(), "evidenceKind": "HISTORICAL_STATUS", "loadedAt": loaded_at}
        )
    return result
