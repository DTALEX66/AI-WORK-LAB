"""Stamp a record's verifiedCommit from a run's measured verdict, and refuse to invent one.

Every binding round needs the same three facts proved before a SHA can be written into a record: the
commit exists, the fix commit is an ancestor of it, and the CI verdict at that exact head is actually
green. Doing that inline by hand is how a plausible SHA ends up in a traceability field, so the check
lives here instead.

Usage:
    python scripts/audit/stamp_record_verification.py ERR-148 07082ed
    python scripts/audit/stamp_record_verification.py --all-eligible      # resolve verdicts per head
    python scripts/audit/stamp_record_verification.py --ledger <path> ERR-149 <head>
`--ledger` exists for the negative controls: they must hand the tool an unstamped record to refuse, and
pointing them at the shipped ledger means the day a record is legitimately stamped, the check that proves
the tool refuses becomes unable to fail.
Exit: 0 stamped or already stamped; 1 refused (no such commit, not an ancestor, or the head is not
green); 2 the ledger could not be read.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
LEDGER = REPO / "taskpacks/current/error-ledger.json"
BRANCH = "task-decomposition/atlas-gap-archive-20261001"


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=REPO, capture_output=True, text=True,
                          encoding="utf-8", errors="replace").stdout.strip()


def head_of(short: str) -> str:
    sha = git("rev-parse", "--verify", "--quiet", f"{short}^{{commit}}")
    return sha if len(sha) == 40 else ""


def ci_verdict(sha: str) -> dict:
    """Ask Actions for the run of THIS exact head. An empty answer is UNKNOWN, never green."""
    listing = subprocess.run(
        ["gh", "run", "list", "--repo", "DTALEX66/WORK-LAB", "--branch", BRANCH, "--limit", "50",
         "--json", "databaseId,headSha,workflowName,status,conclusion"],
        cwd=REPO, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if listing.returncode != 0:
        return {"known": False, "reason": f"GH_QUERY_FAILED {listing.stderr.strip()[:120]}"}
    try:
        runs = json.loads(listing.stdout or "[]")
    except json.JSONDecodeError as exc:
        return {"known": False, "reason": f"GH_QUERY_UNPARSEABLE {exc!r}"}
    mine = [r for r in runs if r.get("headSha") == sha]
    if not mine:
        return {"known": False, "reason": "NO_RUN_FOR_THIS_HEAD on the branch (it may predate the "
                                          "branch tip or the listing window)"}
    grouped: dict[str, list[dict]] = {}
    for run in mine:
        grouped.setdefault(run["workflowName"], []).append(run)
    worst = "success"
    for name, entries in grouped.items():
        best = None
        for entry in entries:
            if entry.get("status") != "completed":
                return {"known": False, "reason": f"{name} is still {entry.get('status')}"}
            if entry.get("conclusion") == "success":
                best = "success"
                break
            best = best or entry.get("conclusion")
        if best != "success":
            worst = best or "unknown"
    return {"known": True, "verdict": worst, "workflows": sorted(grouped)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("error_id", nargs="?")
    ap.add_argument("head", nargs="?")
    ap.add_argument("--all-eligible", action="store_true")
    ap.add_argument("--ledger", default=str(LEDGER))
    args = ap.parse_args()

    ledger = Path(args.ledger)
    try:
        doc = json.loads(ledger.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"STAMP_LEDGER_UNREADABLE {ledger}: {exc}")
        return 2
    targets = []
    if args.all_eligible:
        targets = [(e["error_id"], (e["lifecycle"] or {}).get("pendingHead") or "")
                   for e in doc["errors"]
                   if not (e["lifecycle"] or {}).get("verifiedCommit")
                   and (e["lifecycle"] or {}).get("fixedCommit")]
        if not targets:
            print("STAMP_NONE every bound record already has a verifiedCommit")
            return 0
    else:
        if not args.error_id or not args.head:
            print("usage: stamp_record_verification.py ERR-<n> <head-sha> | --all-eligible")
            return 2
        targets = [(args.error_id, args.head)]

    stamped, refused = [], []
    for eid, head in targets:
        row = next((e for e in doc["errors"] if e["error_id"] == eid), None)
        if row is None:
            refused.append((eid, "no such record"))
            continue
        lc = row["lifecycle"]
        if lc.get("verifiedCommit"):
            stamped.append((eid, lc["verifiedCommit"], "already stamped"))
            continue
        sha = head_of(head)
        if not sha:
            refused.append((eid, f"{head} does not resolve to a commit"))
            continue
        if not lc.get("fixedCommit") or subprocess.run(
                ["git", "merge-base", "--is-ancestor", lc["fixedCommit"], sha],
                cwd=REPO, capture_output=True).returncode != 0:
            # `git()` above returns stdout, and an ancestry test prints nothing: comparing its output
            # to zero refuses every stamp, which is the safe direction but still a bug — the first
            # version of this script rejected a legitimately green head for exactly that reason.
            refused.append((eid, f"{sha[:7]} is not a descendant of fixedCommit "
                                 f"{(lc.get('fixedCommit') or '-')[:7]}"))
            continue
        if subprocess.run(["git", "cat-file", "-e", f"{sha}:taskpacks/current/error-ledger.json"],
                          cwd=REPO, capture_output=True).returncode != 0:
            refused.append((eid, "the head has no ledger to verify"))
            continue
        present = subprocess.run(["git", "show", f"{sha}:taskpacks/current/error-ledger.json"],
                                 cwd=REPO, capture_output=True, text=True,
                                 encoding="utf-8", errors="replace").stdout
        if f'"{eid}"' not in present:
            refused.append((eid, f"{sha[:7]} does not contain the record; a readback of a head "
                                 "without the record proves nothing about it"))
            continue
        verdict = ci_verdict(sha)
        if not verdict.get("known"):
            refused.append((eid, verdict.get("reason") or "verdict unknown"))
            continue
        if verdict["verdict"] != "success":
            refused.append((eid, f"CI at {sha[:7]} is {verdict['verdict']}"))
            continue
        lc["verifiedCommit"] = sha
        lc["verifiedCommitNote"] = (
            f"exact-SHA Actions readback at {sha}: every workflow on this head "
            f"({', '.join(verdict['workflows'])}) completed success, and this head contains the "
            "record itself, so the verdict covers it rather than an ancestor")
        stamped.append((eid, sha, "stamped"))

    if stamped:
        ledger.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        back = json.loads(ledger.read_text(encoding="utf-8"))
        for eid, sha, how in stamped:
            if how != "already stamped":
                row = next(e for e in back["errors"] if e["error_id"] == eid)
                assert row["lifecycle"]["verifiedCommit"] == sha, eid
    for eid, sha, how in stamped:
        print(f"STAMPED {eid} -> {sha[:7]} ({how})")
    for eid, why in refused:
        print(f"REFUSED {eid}: {why}")
    return 1 if refused and not stamped else 0


if __name__ == "__main__":
    sys.exit(main())
