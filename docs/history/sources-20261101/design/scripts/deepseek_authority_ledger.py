#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Machine ledger for DL-TP-20260914-DEEPSEEK-AUTHORITY-R1.

The authority taskpack requires every task record to carry the taskpack id, the
taskpack hash, the task key, the run id, the executor, base sha, branch, worktree
digest and status. Hand-editing that is how ledgers drift, so this script is the
only writer.

Usage:
    python scripts/deepseek_authority_ledger.py init
    python scripts/deepseek_authority_ledger.py set DLDS-A000 DONE --evidence <path> [--note TEXT]
    python scripts/deepseek_authority_ledger.py show
    python scripts/deepseek_authority_ledger.py verify
"""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
TASKPACK_PATH = "docs/taskpacks/DESIGN-LAB-DEEPSEEK-AUTHORITY-TASKPACK-2026-09-14.md"
LEDGER_PATH = "reports/current/DEEPSEEK-AUTHORITY-LEDGER-2026-09-14.json"
TASKPACK_ID = "DL-TP-20260914-DEEPSEEK-AUTHORITY-R1"
TASKPACK_VERSION = "R1"
EXECUTOR = "DEEPSEEK/DSH"
SCHEMA_VERSION = "design-lab/deepseek-authority-ledger/v1"
STATUSES = ("NOT_STARTED", "IN_PROGRESS", "DONE", "BLOCKED", "DEFERRED_TO_CODEX")

# Waves as defined by the taskpack itself; task keys are DLDS-<wave><number>.
WAVES = {
    "A": ("Authority Activation Gate", ["A000", "A010", "A020", "A030", "A040"]),
    "B": ("Wave 1 - Repository Normalization",
          ["B000", "B010", "B020", "B030", "B040", "B050"]),
    "C": ("Wave 2 - Language Governance",
          ["C000", "C010", "C020", "C030", "C040", "C050"]),
    "D": ("Wave 3 - Repository Slimming",
          ["D000", "D010", "D020", "D030", "D040", "D050"]),
    "E": ("Wave 4 - Spill Data Tracking",
          ["E000", "E010", "E020", "E030", "E040", "E050"]),
    "F": ("Wave 5 - Contract / State Closeout",
          ["F000", "F010", "F020", "F030", "F040", "F050", "F060", "F070", "F080"]),
    "G": ("Wave 6 - Third-party Governance",
          ["G000", "G010", "G020", "G030", "G040"]),
    "H": ("Wave 7 - Tests / CI / Evidence",
          ["H000", "H010", "H020", "H030", "H040", "H050"]),
    "I": ("Wave 8 - Security / Failure Recovery", ["I000", "I010", "I020"]),
    "J": ("Wave 9 - Codex Preparation", ["J000"]),
    "K": ("Wave 10 - Final DeepSeek Closeout",
          ["K000", "K010", "K020", "K030", "K040"]),
}


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def sha256_file(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def git(*args: str) -> str:
    result = subprocess.run(["git", "-C", str(REPO), *args], capture_output=True, text=True,
                            encoding="utf-8", errors="replace")
    return result.stdout.strip()


def head_sha() -> str:
    return git("rev-parse", "HEAD")


def branch() -> str:
    return git("rev-parse", "--abbrev-ref", "HEAD")


def worktree_digest() -> str:
    """Content-bound worktree digest (DL-AUDIT-20260914-01).

    Unifies the ledger with the governance/reporting digest: the value now
    binds HEAD plus every normalized change to its SHA-256 content, so a
    same-path content change changes the digest and a recompute over the same
    bytes is stable. Generated / private / runtime roots are excluded by the
    module's declared scope.
    """
    from design_lab.governance.worktree_digest import worktree_digest as unified
    return unified(REPO)


def worktree_clean() -> bool:
    return git("status", "--porcelain=v1") == ""


def environment_fingerprint() -> dict:
    return {"python": platform.python_version(), "platform": platform.platform(),
            "machine": platform.machine(), "executor": EXECUTOR}


def load() -> dict:
    path = REPO / LEDGER_PATH
    if not path.is_file():
        raise SystemExit(f"ledger not found: {LEDGER_PATH}; run init first")
    return json.loads(path.read_text(encoding="utf-8"))


def save(ledger: dict) -> None:
    ledger["updated_at"] = now()
    path = REPO / LEDGER_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(ledger, indent=2, ensure_ascii=False, sort_keys=False) + "\n",
                    encoding="utf-8", newline="\n")


def init(args) -> int:
    path = REPO / LEDGER_PATH
    if path.exists() and not args.force:
        print(f"LEDGER_EXISTS {LEDGER_PATH}")
        return 1
    taskpack_file = REPO / TASKPACK_PATH
    if not taskpack_file.is_file():
        print(f"TASKPACK_MISSING {TASKPACK_PATH}")
        return 2
    tasks = []
    for wave in sorted(WAVES):
        title, keys = WAVES[wave]
        for key in keys:
            tasks.append({
                "task_key": f"DLDS-{key}",
                "full_id": f"{TASKPACK_ID}::DLDS-{key}",
                "wave": wave,
                "wave_title": title,
                "status": "NOT_STARTED",
                "evidence": [],
                "notes": [],
            })
    ledger = {
        "schemaVersion": SCHEMA_VERSION,
        "taskpack": {
            "taskpack_id": TASKPACK_ID,
            "taskpack_version": TASKPACK_VERSION,
            "taskpack_path": TASKPACK_PATH,
            "taskpack_sha256": sha256_file(taskpack_file),
            "created_at": now(),
            "authoritative": True,
            "landed_by": EXECUTOR,
            "provenance": "transcribed from the owner's message in the authority session; the "
                           "landed file's sha256 is the authority for every later reference",
        },
        "run": {
            "run_id": "dsh-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
            "executor": EXECUTOR,
            "base_sha": head_sha(),
            "branch": branch(),
            "worktree": worktree_digest(),
            "worktree_clean": worktree_clean(),
        },
        "authority": {
            "current_deepseek_taskpack": TASKPACK_ID,
            "non_authoritative_sources": ["CHAT SUMMARY", "MEMORY SUMMARY", "COMPRESSED CONTEXT",
                                          "HANDOFF SUMMARY"],
            "stop_line": {
                "handoff": "docs/history/archive-2026-10-19/handoffs/SESSION-RESTART-2026-09-12.md",
                "handoffState": "REMOVED-2026-10-19: bytes recoverable via docs/history/archive-2026-10-19/REMOVALS.json",
                "state": "EXPLICIT_SCOPE_SUPERSESSION",
                "scope": "only the DeepSeek tasks listed in this taskpack",
                "still_frozen": ["Real Host", "Design validation", "GPU inference", "Human Gate"],
            },
        },
        "environment_fingerprint": environment_fingerprint(),
        "task_count": len(tasks),
        "tasks": tasks,
        "updated_at": now(),
    }
    save(ledger)
    print(f"LEDGER_INITIALISED {LEDGER_PATH} tasks={len(tasks)} "
          f"taskpack_sha256={ledger['taskpack']['taskpack_sha256']}")
    return 0


def resolve_task(ledger: dict, key: str) -> dict:
    wanted = key if key.startswith("DLDS-") else f"DLDS-{key}"
    for task in ledger["tasks"]:
        if task["task_key"] == wanted:
            return task
    raise SystemExit(f"unknown task key: {key}")


def set_status(args) -> int:
    if args.status not in STATUSES:
        raise SystemExit(f"status must be one of {', '.join(STATUSES)}")
    ledger = load()
    task = resolve_task(ledger, args.task_key)
    task["status"] = args.status
    for item in args.evidence or ():
        if item not in task["evidence"]:
            task["evidence"].append(item)
    if args.note:
        task["notes"].append({"at": now(), "note": args.note})
    ledger["run"]["worktree"] = worktree_digest()
    ledger["run"]["worktree_clean"] = worktree_clean()
    save(ledger)
    print(f"{task['full_id']} = {args.status}")
    return 0


def show(args) -> int:
    ledger = load()
    counts = {}
    for task in ledger["tasks"]:
        counts[task["status"]] = counts.get(task["status"], 0) + 1
    print(f"taskpack: {ledger['taskpack']['taskpack_id']} "
          f"{ledger['taskpack']['taskpack_sha256'][:23]}...")
    print(f"branch: {ledger['run']['branch']} base: {ledger['run']['base_sha'][:12]} "
          f"worktree_clean: {ledger['run']['worktree_clean']}")
    print("status: " + ", ".join(f"{k}={v}" for k, v in sorted(counts.items())))
    for wave in sorted(WAVES):
        keys = [t for t in ledger["tasks"] if t["wave"] == wave]
        done = sum(1 for t in keys if t["status"] in {"DONE", "DEFERRED_TO_CODEX"})
        print(f"  {wave}: {done}/{len(keys)} closed - {WAVES[wave][0]}")
    return 0


def verify(args) -> int:
    ledger = load()
    errors = []
    taskpack_file = REPO / TASKPACK_PATH
    if not taskpack_file.is_file():
        errors.append("taskpack file missing")
    elif sha256_file(taskpack_file) != ledger["taskpack"]["taskpack_sha256"]:
        errors.append("taskpack sha256 changed since the ledger was written")
    keys = {t["task_key"] for t in ledger["tasks"]}
    expected = {f"DLDS-{k}" for _, keys_ in WAVES.values() for k in keys_}
    if keys != expected:
        errors.append(f"task key set mismatch: {sorted(keys ^ expected)}")
    for task in ledger["tasks"]:
        if task["status"] not in STATUSES:
            errors.append(f"invalid status on {task['task_key']}")
        if task["status"] == "DONE" and not task["evidence"]:
            errors.append(f"DONE without evidence: {task['task_key']}")
    if errors:
        print("LEDGER=FAIL")
        for error in errors:
            print(" - " + error)
        return 1
    print(f"LEDGER=PASS tasks={len(ledger['tasks'])} taskpack_sha256_ok=true")
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    p_init = sub.add_parser("init")
    p_init.add_argument("--force", action="store_true")
    p_init.set_defaults(func=init)
    p_set = sub.add_parser("set")
    p_set.add_argument("task_key")
    p_set.add_argument("status")
    p_set.add_argument("--evidence", action="append")
    p_set.add_argument("--note")
    p_set.set_defaults(func=set_status)
    sub.add_parser("show").set_defaults(func=show)
    sub.add_parser("verify").set_defaults(func=verify)
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
