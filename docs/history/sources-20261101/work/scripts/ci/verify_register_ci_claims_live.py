"""Ask GitHub what actually ran at every SHA the register's CI claims name, and publish that as tracked evidence.

The register asserts things like "exact-SHA CI not run", "green at 5037dd2", "red at f9f38d6". Those are
claims about an external system, so the offline consistency gate can only check them against the ledger's
`verifiedCommit` -- which records a verdict only where a record was bound there. A green claim at an older
head with no bound record is true and unverifiable-by-the-ledger at the same time, and the answer is not to
loosen the gate: it is to commit the measurement.

This tool writes `docs/audits/REGISTER_CI_CLAIMS_<date>.json`: for every pinned SHA named in a CI-shaped row
token, the check-runs GitHub reports (status, conclusion, name). The offline gate
`tests/workflow-assistance/test_register_ci_claims_agree_with_ledger.py` reads that file as the second
evidence source, so a claim can be backed either by a ledger `verifiedCommit` or by a published measurement,
and a claim that contradicts either one goes red.

It REFUSES (exit 2) when it cannot reach GitHub -- CI has no business calling the network, and a gate that
silently skips would let a stale claim pass as a verified one. The refusal is a named token, not an empty run.

Usage:
    python scripts/ci/verify_register_ci_claims_live.py [--out docs/audits/REGISTER_CI_CLAIMS_YYYY-MM-DD.json]
Exit: 0 published; 1 a register claim contradicts what GitHub says; 2 refused (no network or no credentials).
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "taskpacks/current" / "OPEN-TASK-REGISTER.md"
CELL = re.compile(r"(?<!\\)\|")
SHA = re.compile(r"\b[0-9a-f]{7,40}\b")
CLAIM = re.compile(r"EXACT_SHA_CI_GREEN_AT_([0-9a-f]{7,40})|EXACT_SHA_CI_RED_AT_([0-9a-f]{7,40})")
REPO = "DTALEX66/WORK-LAB"


def claim_rows() -> list[dict]:
    rows = []
    for number, line in enumerate(REGISTER.read_text(encoding="utf-8").splitlines(), 1):
        if not line.startswith("| ") or line.startswith("| ID |"):
            continue
        cells = [c.strip() for c in CELL.split(line)]
        if len(cells) < 5:
            continue
        text = " ".join(cells[2:])
        pins = [(m.group(1) or m.group(2), "green" if m.group(1) else "red")
                for m in CLAIM.finditer(text)]
        if pins:
            rows.append({"line": number, "rowId": cells[1], "pins": pins})
    return rows


def gh(*args: str) -> tuple[int, str, str]:
    done = subprocess.run(["gh", *args], cwd=ROOT, capture_output=True, text=True,
                          encoding="utf-8", errors="replace")
    return done.returncode, done.stdout or "", done.stderr or ""


# A job that never got a runner reports conclusion=failure, which is indistinguishable from "the code
# is red" if only the rollup is read. The annotation text is the only signal that separates them, and
# conflating the two sends a reader hunting a defect that does not exist (measured 2026-10-08: all 19
# check-runs at 6c500d66 were skipped or never started, with zero jobs executed).
BILLING_PHRASES = ("was not started because", "spending limit", "payments have failed")


def failure_annotations(run_id: str) -> str:
    code, out, _err = gh("api", f"repos/{REPO}/check-runs/{run_id}/annotations",
                         "--jq", '[.[] | select(.annotation_level == "failure") | .message] | join("\n")')
    return out if code == 0 else ""


def never_started(runs: list[dict]) -> int:
    """How many of the failed runs were never executed? Only called when nothing succeeded."""
    return sum(1 for r in runs
               if r.get("conclusion") in ("failure", "cancelled", "timed_out")
               and any(phrase in failure_annotations(str(r.get("id"))) for phrase in BILLING_PHRASES))


def resolve(abbrev: str) -> str | None:
    # `git`, not the `gh` wrapper above: an abbreviation is resolved locally, and a tool that asked GitHub
    # to expand a SHA would be slow, rate-limited and wrong offline.
    done = subprocess.run(["git", "rev-parse", "--verify", "-q", abbrev + "^{commit}"],
                          cwd=ROOT, capture_output=True, text=True,
                          encoding="utf-8", errors="replace")
    sha = (done.stdout or "").strip()
    return sha if done.returncode == 0 and re.fullmatch(r"[0-9a-f]{40}", sha) else None


def check_runs(sha: str) -> dict | None:
    code, out, err = gh("api", f"repos/{REPO}/commits/{sha}/check-runs?per_page=100",
                        "--jq", '.check_runs[] | {status, conclusion, name, id}')
    if code != 0:
        print(f"LIVE_CI_REFUSED api_error {err.strip()[:140]}")
        return None
    runs = [json.loads(line) for line in out.splitlines() if line.strip()]
    success = sum(1 for r in runs if r.get("conclusion") == "success")
    failure = sum(1 for r in runs if r.get("conclusion") in ("failure", "timed_out", "cancelled"))
    # The annotation fetch is one API call per failed run, so it is only spent where it can change the
    # answer: a head with any success has genuinely run and is a real partial red, not a runner outage.
    blocked = never_started(runs) if failure and not success else 0
    return {
        "runs": len(runs),
        "success": success,
        "failure": failure,
        "notStarted": blocked,
        "pending": sum(1 for r in runs if r.get("status") in ("queued", "in_progress")),
        "byName": [{"name": r.get("name"), "status": r.get("status"),
                    "conclusion": r.get("conclusion")} for r in runs],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", default=None)
    args = parser.parse_args(argv)

    rows = claim_rows()
    if not rows:
        print(f"LIVE_CI_FAIL no register row carries a green/red CI claim -- nothing was measured "
              f"(rows scanned from {REGISTER.relative_to(ROOT)})")
        return 1

    code, _out, err = gh("api", f"repos/{REPO}/commits/{resolve('HEAD') or 'HEAD'}", "--jq", ".sha")
    if code != 0:
        print(f"LIVE_CI_REFUSED cannot reach GitHub: {err.strip()[:140]}")
        return 2

    measured: dict[str, dict] = {}
    problems: list[str] = []
    for row in rows:
        for pin, claim in row["pins"]:
            sha = resolve(pin)
            if sha is None:
                problems.append(f"line {row['line']} {row['rowId']}: pin {pin} is not a commit in this repo")
                continue
            if sha not in measured:
                verdict = check_runs(sha)
                if verdict is None:
                    return 2
                measured[sha] = verdict
                time.sleep(0.2)
            verdict = measured[sha]
            if verdict.get("notStarted") and verdict["notStarted"] == verdict["failure"]:
                print(f"LIVE_CI_REFUSED CI_BILLING_BLOCKED head={pin} runs={verdict['runs']} "
                      f"success=0 not_started={verdict['notStarted']} — no job was executed at this "
                      f"head, so it is neither green nor red; the account's Actions runner is "
                      f"unavailable and no code change can move this verdict")
                return 4
            if claim == "green" and (verdict["runs"] == 0 or verdict["success"] != verdict["runs"]):
                problems.append(f"line {row['line']} {row['rowId']}: claims green at {pin[:7]} but GitHub "
                                f"reports runs={verdict['runs']} success={verdict['success']} "
                                f"failure={verdict['failure']} pending={verdict['pending']}")
            if claim == "red" and verdict["failure"] == 0 and verdict["runs"]:
                problems.append(f"line {row['line']} {row['rowId']}: claims red at {pin[:7]} but GitHub "
                                f"reports failure=0 of runs={verdict['runs']}")

    stamp = time.strftime("%Y-%m-%d", time.gmtime())
    out_path = ROOT / (args.out or f"docs/audits/REGISTER_CI_CLAIMS_{stamp}.json")
    payload = {
        "schemaVersion": "work-lab/register-ci-claims/v1",
        "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "tool": "scripts/ci/verify_register_ci_claims_live.py",
        "scope": ("every SHA named by an EXACT_SHA_CI_GREEN_AT_/EXACT_SHA_CI_RED_AT_ token in "
                  "taskpacks/current/OPEN-TASK-REGISTER.md; `runs` are GitHub check-runs at that exact SHA, "
                  "which include both push and pull_request trigger jobs"),
        "rows": rows,
        "bySha": measured,
        "problems": problems,
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    # `--out` accepts any path, so the display must not assume it lies inside the repo: a ValueError
    # here would destroy an otherwise valid verdict.
    try:
        shown = str(out_path.relative_to(ROOT))
    except ValueError:
        shown = str(out_path)
    print(f"LIVE_CI_PUBLISH file={shown} shas={len(measured)} rows={len(rows)} "
          f"problems={len(problems)}")
    for problem in problems:
        print(f"  LIVE_CI_CONTRADICTION {problem}")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
