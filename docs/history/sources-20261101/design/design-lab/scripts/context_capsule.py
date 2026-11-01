#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""GENERATED context capsule + session receipt for anti-amnesia sessions.

Cloud audit 2026-09-25 Prompt F. The capsule is GENERATED CONTEXT, explicitly
non-authoritative: it never overrides live main / the authority index, and it
is regenerated on every session start. A capsule whose hashes no longer match
the live tree is STALE and must be shown as such -- never silently continued.

Two artifacts (both machine-generated, both schema-validated by the CI gate):

* ``context-capsule``  -- written at session start; binds authority / live
  main / current TaskPack / task-ledger / open-PR / CI / environment hashes so
  a fresh agent (or a compacted one) can re-anchor without chat history.
* ``session-receipt``  -- written at session end; binds input capsule hash,
  files changed, commands, tests, evidence ids, blockers, rollback and the
  next atomic task. A Handoff may only *reference* a receipt; it never is
  an authority of its own.

Fail-closed semantics:

* a field that cannot be observed is recorded ``absent`` with a reason --
  it is NEVER guessed from chat, memory, or stale docs;
* the capsule records the observed tree/commit SHAs; the gate compares them
  against live git and reports STALE on mismatch instead of proceeding.
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Mapping, Optional

CAPSULE_SCHEMA_VERSION = "design-lab/context-capsule/v1"
RECEIPT_SCHEMA_VERSION = "design-lab/session-receipt/v1"

# The runtime location for generated context. ``.project-local`` is gitignored
# (generated context is never committed; committing it would make it look
# authoritative).
CAPSULE_REL = Path(".project-local") / "context-capsule.json"
RECEIPT_DIR = Path(".project-local") / "task-artifacts" / "session-receipts"

# Fields a capsule must carry; each is either a real value or {"absent": reason}.
CAPSULE_FIELDS = (
    "authority_id", "authority_sha256", "authority_index_sha256",
    "live_main_sha", "live_main_tree_sha",
    "current_taskpack_id", "current_taskpack_sha256",
    "task_ledger_sha256", "reports_current_subject_sha",
    "open_pr_snapshot", "latest_ci_run", "project_id",
    "environment_snapshot_sha256", "resolved_host_tool_summary",
    "generated_at",
)


def _now_iso() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _sha256_file(path: Path) -> Optional[str]:
    if not path.exists():
        return None
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None


def _git(root: Path, *args: str) -> str:
    try:
        r = subprocess.run(["git", "-C", str(root), *args], capture_output=True,
                           text=True, encoding="utf-8", errors="replace", timeout=60)
        return r.stdout.strip() if r.returncode == 0 else ""
    except (OSError, subprocess.SubprocessError):
        return ""


def _rev_parse(root: Path, rev: str) -> str:
    return _git(root, "rev-parse", f"refs/remotes/origin/{rev}") or _git(root, "rev-parse", f"{rev}^{{commit}}")


def build_capsule(repo_root: Path, project_id: str = "DESIGN-LAB") -> dict:
    """Build the capsule deterministically from the repo. Injectable so tests
    can assert the STALE/absent branches without a live remote."""
    root = Path(repo_root)
    head_sha = _git(root, "rev-parse", "HEAD")
    tree_sha = _git(root, "rev-parse", "HEAD^{tree}")
    live_main = _rev_parse(root, "main")

    cap: dict = {}

    def put(field: str, value: Optional[str], absent_reason: str) -> None:
        cap[field] = value if value not in (None, "") else {"absent": absent_reason}

    # authority chain (files, not guesses). The authority id comes from the
    # machine ledger (authority-index.json) -- the file that actually names it --
    # not from a fragile parse of the authority document's prose.
    authority_index = root / ".project" / "governance" / "authority-index.json"
    authority_id = None
    if authority_index.exists():
        try:
            idx = json.loads(authority_index.read_text(encoding="utf-8"))
            authority_id = str(idx.get("authorityId") or idx.get("authority_id") or idx.get("id") or "") or None
        except (OSError, ValueError):
            authority_id = None
    put("authority_id", authority_id, "authority-index.json does not name an authority id")
    put("authority_sha256", _sha256_file(root / "AUTHORITY.md"), "AUTHORITY.md missing")
    put("authority_index_sha256",
        _sha256_file(root / ".project" / "governance" / "authority-index.json"),
        "authority-index.json missing")
    put("live_main_sha", live_main, "origin/main or main not resolvable in this checkout")
    put("live_main_tree_sha", tree_sha, "HEAD^{tree} unreadable")

    # current integrated TaskPack (from AGENTS.md's single current pointer)
    taskpack_sha = None
    taskpack_id = None
    agents = (root / "AGENTS.md").read_text(encoding="utf-8", errors="replace") if (root / "AGENTS.md").exists() else ""
    import re as _re
    m = _re.search(r"docs/taskpacks/([A-Z0-9\-]+)\.md", agents)
    if m and (root / "docs" / "taskpacks" / f"{m.group(1)}.md").exists():
        taskpack_id = m.group(1)
        taskpack_sha = _sha256_file(root / "docs" / "taskpacks" / f"{taskpack_id}.md")
    put("current_taskpack_id", taskpack_id, "AGENTS.md current-TaskPack pointer not found")
    put("current_taskpack_sha256", taskpack_sha, "current TaskPack file missing")
    put("task_ledger_sha256",
        _sha256_file(root / "design-lab" / "config" / "task-ledger-r3.json"),
        "task-ledger-r3.json missing")
    reports = root / "reports" / "current" / "PROJECT_STATUS.md"
    put("reports_current_subject_sha",
        _sha256_file(reports), "reports/current projection missing")

    # open-PR / CI facts are fetched by the caller when a GitHub token is
    # present; without one they are absent -- never guessed.
    cap.setdefault("open_pr_snapshot", {"absent": "no GitHub token in this context (never guessed)"})
    cap.setdefault("latest_ci_run", {"absent": "no GitHub token in this context (never guessed)"})
    cap["project_id"] = project_id

    paths_doc = _sha256_file(root / ".project" / "paths.json")
    cap["environment_snapshot_sha256"] = (
        {"absent": ".project/paths.json missing"} if paths_doc is None else paths_doc
    )
    cap["resolved_host_tool_summary"] = {
        "absent": "resolved via the fail-closed tool locator at launch; not baked into the capsule"
    }
    cap["generated_at"] = _now_iso()
    cap["schema_version"] = CAPSULE_SCHEMA_VERSION
    cap["non_authoritative"] = True
    return cap


def capsule_is_stale(capsule: Mapping[str, object], repo_root: Path) -> list[str]:
    """Compare the capsule against live git; return STALE reasons (empty = fresh)."""
    stale: list[str] = []
    root = Path(repo_root)
    head_sha = _git(root, "rev-parse", "HEAD")
    live_main = _rev_parse(root, "main")
    got_main = str(capsule.get("live_main_sha") or "")
    got_main = got_main if got_main else ""
    if isinstance(capsule.get("live_main_sha"), str) and live_main and got_main != live_main:
        stale.append(f"live_main advanced: capsule={got_main[:12]} live={live_main[:12]}")
    got_tree = str(capsule.get("live_main_tree_sha") or "")
    tree_now = _git(root, "rev-parse", "HEAD^{tree}")
    if got_tree and tree_now and got_tree != tree_now:
        stale.append(f"tree advanced: capsule={got_tree[:12]} live={tree_now[:12]}")
    for field in CAPSULE_FIELDS:
        if field not in capsule:
            stale.append(f"capsule missing field {field} (must be a value or {{absent: reason}})")
    return stale


def build_receipt(
    *,
    capsule: Mapping[str, object],
    task_id: str,
    files_changed: list[str],
    commands: list[str],
    tests: list[str],
    evidence_ids: list[str],
    host_receipts: list[str],
    blockers: list[str],
    rollback: str,
    next_atomic_task: str,
) -> dict:
    """A session receipt. It may *reference* the input capsule by hash; it
    never re-claims authority."""
    rec: dict = {
        "schema_version": RECEIPT_SCHEMA_VERSION,
        "non_authoritative": True,
        "task_id": task_id,
        "files_changed": list(files_changed),
        "commands": list(commands),
        "tests": list(tests),
        "evidence_ids": list(evidence_ids),
        "host_receipts": list(host_receipts),
        "blockers": list(blockers),
        "rollback": rollback,
        "next_atomic_task": next_atomic_task,
        "generated_at": _now_iso(),
    }
    cap_hash = _sha256_bytes(json.dumps(dict(capsule), sort_keys=True).encode("utf-8"))
    rec["input_capsule_sha256"] = cap_hash if cap_hash else {"absent": "no input capsule"}
    return rec


def _sha256_bytes(b: bytes) -> Optional[str]:
    return hashlib.sha256(b).hexdigest()


def write_capsule(repo_root: Path, project_id: str = "DESIGN-LAB") -> str:
    cap = build_capsule(repo_root, project_id)
    path = Path(repo_root) / CAPSULE_REL
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cap, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return str(path)


def write_receipt(repo_root: Path, receipt: Mapping[str, object]) -> str:
    path = Path(repo_root) / RECEIPT_DIR / f"{receipt.get('task_id', 'task')}-{_now_iso()[:10]}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(dict(receipt), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return str(path)


if __name__ == "__main__":
    import sys
    root = Path(__file__).resolve().parent.parent.parent
    p = write_capsule(root)
    print(f"CONTEXT_CAPSULE_WRITTEN={p}")
    cap = json.loads(Path(p).read_text(encoding="utf-8"))
    stale = capsule_is_stale(cap, root)
    print(f"CONTEXT_CAPSULE={'STALE' if stale else 'FRESH'} {json.dumps(stale, ensure_ascii=False)}")
    raise SystemExit(0)
