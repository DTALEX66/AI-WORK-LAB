#!/usr/bin/env python
# SPDX-License-Identifier: MIT
"""Gather the live facts a cloud-GPT audit must be given, in one auditable dump.

Read-only. Uses git + gh only. Never reads credentials or session bodies.
Writes nothing unless --out is passed.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(r"D:\All projects\DESIGN-LAB")
GH = r"C:\Program Files\GitHub CLI\gh.exe"


def run(args: list[str]) -> str:
    r = subprocess.run(args, cwd=ROOT, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    return r.stdout.strip()


def git(*args: str) -> str:
    return run(["git", *args])


def gh_json(args: list[str]):
    raw = run([GH, *args])
    try:
        return json.loads(raw) if raw else None
    except json.JSONDecodeError:
        return {"_raw": raw[:400]}


def main() -> int:
    out: dict = {}

    out["git"] = {
        "head": git("rev-parse", "HEAD"),
        "local_main": git("rev-parse", "main"),
        "origin_main": git("rev-parse", "origin/main"),
        "branch": git("branch", "--show-current"),
        "ahead_behind": git("rev-list", "--left-right", "--count", "main...origin/main"),
        "status_porcelain": git("status", "--porcelain"),
        "stash_count": len([l for l in git("stash", "list").splitlines() if l.strip()]),
        "worktree_count": len([l for l in git("worktree", "list").splitlines() if l.strip()]),
        "unpushed": git("log", "origin/main..HEAD", "--oneline"),
        "remote_heads": git("ls-remote", "--heads", "origin"),
        "remote_tag_count": len([l for l in git("ls-remote", "--tags", "origin").splitlines() if l.strip()]),
    }

    prot = gh_json(["api", "/repos/DTALEX66/DESIGN-LAB/branches/main/protection"])
    out["branch_protection"] = {
        "required_checks": (prot or {}).get("required_status_checks", {}).get("contexts", []),
        "enforce_admins": (prot or {}).get("enforce_admins", {}).get("enabled"),
        "strict": (prot or {}).get("required_status_checks", {}).get("strict"),
    }

    out["open_prs"] = gh_json(["pr", "list", "--state", "open",
                               "--json", "number,title,headRefName,createdAt"])
    merged = gh_json(["pr", "list", "--state", "merged", "--limit", "15",
                      "--json", "number,title,mergedAt,mergeCommit"])
    out["merged_prs"] = merged

    runs = gh_json(["run", "list", "--branch", "main", "--limit", "8",
                    "--json", "databaseId,headSha,status,conclusion,workflowName,createdAt"])
    out["main_runs"] = runs
    if runs:
        rid = runs[0]["databaseId"]
        arts = gh_json(["api", f"/repos/DTALEX66/DESIGN-LAB/actions/runs/{rid}/artifacts"])
        out["latest_main_run"] = {"run_id": rid, "head_sha": runs[0]["headSha"],
                                  "conclusion": runs[0]["conclusion"],
                                  "artifacts_total": (arts or {}).get("total_count"),
                                  "artifacts": [{"name": a["name"], "bytes": a["size_in_bytes"],
                                                 "expired": a["expired"]}
                                                for a in (arts or {}).get("artifacts", [])]}

    print("=" * 78)
    print("LIVE FACTS FOR CLOUD AUDIT")
    print("=" * 78)
    g = out["git"]
    print(f"\n[git]")
    print(f"  HEAD            : {g['head']}")
    print(f"  local main      : {g['local_main']}")
    print(f"  origin/main     : {g['origin_main']}")
    print(f"  HEAD == origin  : {g['head'] == g['origin_main']}")
    print(f"  ahead/behind    : {g['ahead_behind']}")
    print(f"  branch          : {g['branch']}")
    print(f"  dirty files     : {g['status_porcelain'] or '(none)'}")
    print(f"  stashes         : {g['stash_count']}   worktrees: {g['worktree_count']}")
    print(f"  unpushed commits: {g['unpushed'] or '(none)'}")
    print(f"  remote heads    : {g['remote_heads']}")
    print(f"  remote tags     : {g['remote_tag_count']}")

    bp = out["branch_protection"]
    print(f"\n[branch protection]")
    print(f"  enforce_admins  : {bp['enforce_admins']}   strict: {bp['strict']}")
    print(f"  required checks : {len(bp['required_checks'])}")
    for c in bp["required_checks"]:
        print(f"    - {c}")

    print(f"\n[open PRs] {len(out['open_prs'] or [])}")
    for p in out["open_prs"] or []:
        print(f"    #{p['number']} {p['title']}  head={p['headRefName']}")

    print(f"\n[merged PRs, latest 15]")
    for p in merged or []:
        mc = (p.get("mergeCommit") or {}).get("oid", "")[:12]
        print(f"    #{p['number']:<4} {p['mergedAt']}  {mc}  {p['title'][:70]}")

    print(f"\n[main CI runs, latest 8]")
    for r in runs or []:
        print(f"    {r['databaseId']}  {r['headSha'][:12]}  {str(r['conclusion']):<10} "
              f"{r['workflowName'][:32]:<32} {r['createdAt']}")

    lm = out.get("latest_main_run")
    if lm:
        print(f"\n[latest main run {lm['run_id']} @ {lm['head_sha'][:12]} conclusion={lm['conclusion']}]")
        print(f"  artifacts total : {lm['artifacts_total']}")
        for a in lm["artifacts"]:
            print(f"    {a['name']}  {a['bytes']}B  expired={a['expired']}")

    if "--out" in sys.argv:
        dst = ROOT / ".project-local/task-artifacts/project-survey-2026-09-27/audit-live-facts.json"
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\nwrote {dst}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
