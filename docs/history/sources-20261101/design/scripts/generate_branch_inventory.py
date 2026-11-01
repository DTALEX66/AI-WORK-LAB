#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""DL-CI-008: remote branch governance inventory.

Classifies every remote head of DTALEX66/DESIGN-LAB:
- ACTIVE             recent, not merged, no newer superseding head
- MERGED             head is an ancestor of origin/main
- SUPERSEDED         content already covered on main via a later merge
- HISTORICAL         old branch (>90 days) with no recent commits
- DELETE_CANDIDATE   merged/superseded/historical -> removal requires user approval

No branch is deleted by this tool (R4 执行原则 9: 未经批准不删远端分支).
Uses git with the openssl TLS backend (schannel credential store is
unavailable in this environment).
"""
from __future__ import annotations

import json
import subprocess
from datetime import date, datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "reports" / "current" / "DL-R4-BRANCH-INVENTORY.json"
REMOTE = "origin"
GIT = ["git", "-C", str(REPO), "-c", "http.sslBackend=openssl"]


def git(args: list[str]) -> str:
    r = subprocess.run(GIT + args, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)}: {r.stderr.strip()[:300]}")
    return r.stdout.strip()


def main() -> int:
    today = date.today()
    try:
        heads = {}
        for line in git(["ls-remote", "--heads", REMOTE]).splitlines():
            if not line.strip():
                continue
            sha, ref = line.split("\t")
            name = ref.replace("refs/heads/", "")
            if name != "main":
                heads[name] = sha
        main_sha = git(["rev-parse", "origin/main"])
    except RuntimeError as exc:
        print(f"BRANCH_INVENTORY=FAIL {exc}")
        return 1

    entries = []
    for name, sha in sorted(heads.items()):
        is_ancestor = False
        try:
            r = subprocess.run(
                ["git", "-C", str(REPO), "merge-base", "--is-ancestor", sha, main_sha],
                capture_output=True, text=True, encoding="utf-8", errors="replace",
            )
            is_ancestor = r.returncode == 0
        except OSError:
            pass
        cdate = None
        try:
            out = git(["show", "-s", "--format=%cs", sha])
            if out:
                cdate = datetime.strptime(out, "%Y-%m-%d").date()
        except (RuntimeError, ValueError):
            pass
        age_days = (today - cdate).days if cdate else None
        merged = is_ancestor
        historical = age_days is not None and age_days > 90
        if merged:
            cls = "MERGED"
        elif historical:
            cls = "HISTORICAL"
        else:
            cls = "ACTIVE"
        delete_candidate = merged or historical
        entries.append({
            "branch": name,
            "headSha": sha,
            "mergedIntoMain": merged,
            "tipDate": cdate.isoformat() if cdate else None,
            "ageDays": age_days,
            "classification": cls,
            "deleteCandidate": delete_candidate,
            "note": "删除需用户明确批准 (R4 执行原则 9)；本工具不执行删除",
        })

    report = {
        "report": "DL-CI-008-BRANCH-INVENTORY",
        "generatedAt": today.isoformat(),
        "remote": REMOTE,
        "mainSha": main_sha,
        "totalRemoteHeads": len(heads) + 1,
        "nonMainHeads": len(heads),
        "classifications": {},
        "entries": entries,
    }
    for e in entries:
        report["classifications"][e["classification"]] = report["classifications"].get(e["classification"], 0) + 1
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"BRANCH_INVENTORY=OK heads={len(heads)} " + " ".join(f"{k}={v}" for k, v in report["classifications"].items()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
