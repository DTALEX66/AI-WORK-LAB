#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Generate a non-destructive branch-cleanup candidate index from fetched refs."""
from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "design-lab" / "config" / "branch-cleanup-candidates.json"


def git(*args: str) -> tuple[int, str]:
    result = subprocess.run(["git", "-C", str(REPO), *args], capture_output=True, text=True, encoding="utf-8", errors="replace")
    return result.returncode, result.stdout.strip()


def main() -> int:
    code, main_sha = git("rev-parse", "origin/main")
    if code or not main_sha:
        print("BRANCH_CLEANUP_CANDIDATES=FAIL reason=origin/main-unavailable")
        return 1
    _, raw = git("for-each-ref", "--format=%(refname:short)", "refs/remotes/origin")
    branches = []
    for ref in sorted(line for line in raw.splitlines() if line and line not in {"origin/HEAD", "origin/main"}):
        ancestor, _ = git("merge-base", "--is-ancestor", ref, "origin/main")
        _, ahead = git("rev-list", "--count", f"origin/main..{ref}")
        _, behind = git("rev-list", "--count", f"{ref}..origin/main")
        branches.append({"ref": ref, "mergedIntoOriginMain": ancestor == 0, "aheadOfOriginMain": int(ahead or "0"), "behindOriginMain": int(behind or "0"), "action": "review-only"})
    payload = {"schemaVersion": "design-lab/branch-inventory/v1", "subjectSha": main_sha, "generatedAt": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"), "deletionAuthorized": False, "branches": branches, "note": "Candidates are informational only. No branch was deleted, pushed, or modified."}
    OUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"BRANCH_CLEANUP_CANDIDATES=PASS branches={len(branches)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
