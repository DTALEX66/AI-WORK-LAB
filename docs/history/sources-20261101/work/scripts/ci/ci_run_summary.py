#!/usr/bin/env python3
"""W10 (2026-10-17): assemble a small, redacted run summary that a CI job uploads as an artifact.

Why this exists
---------------
Measured 2026-10-16: the repository produced **no artifacts at all** for any run. Auditing a red run therefore
started by opening a log URL and grepping a few thousand lines, and the three facts an auditor needs first --
which stage failed, with what exit code, and whether the run was ever planned -- were the hardest to find.
The plan stage computes a plan that only ever lived in `$GITHUB_OUTPUT`, and the gate writes its per-stage
record to a file nobody uploads.

What this is NOT
----------------
It is not a second verdict. `GATE_EXIT` and the aggregate job remain the only authorities; this file exists to
be read. In particular **a missing input is never rendered as success**: every absent input becomes an explicit
`{"status": "MISSING"}` plus a top-level `incomplete` list, because "no JSON" defaulting to "passed" is exactly
the failure the plan named.

Redaction stance
----------------
Fields are **whitelisted**, not scrubbed: the summary carries identity (repo/sha/tree/ref/event/job), step
names and statuses, the plan's own enumerated keys, and the gate record's enumerated keys. No free text from
logs, no environment dump, no command lines -- so there is nothing for a scrubber to miss.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CI_DIR = ROOT / ".project-local" / "runs" / "ci"
PLAN_FILE = CI_DIR / "plan.json"
GATE_STAGES_FILE = CI_DIR / "gate-stages.json"
SCHEMA_VERSION = "work-lab/ci-run-summary/v1"

# Whitelists: a field that is not named here does not reach the artifact. Adding one is a deliberate act.
PLAN_KEYS = ("plan_id", "required_gates", "ci_jobs", "skipped_gates", "risk", "delivery_effect",
             "platform_scope", "unclassified_paths", "plan_digest", "changed_paths", "source_identity")
GATE_KEYS = ("schemaVersion", "source", "requested_gates", "full", "stages", "failed_gate", "exit")


def _git(*args: str) -> str:
    result = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True,
                            encoding="utf-8", errors="replace", check=False)
    return result.stdout.strip() if result.returncode == 0 else ""


def _read_json(path: Path) -> dict | None:
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def _slice(data: dict, keys: tuple[str, ...]) -> dict:
    return {key: data[key] for key in keys if key in data}


def build_summary(job: str, steps: list[tuple[str, str]]) -> dict:
    incomplete: list[str] = []

    # The plan is produced in a DIFFERENT job, on a different runner, so its file never reaches this one:
    # measured on the first CI run with artifacts (2026-10-16, run 38937961649), where `plan: MISSING`
    # appeared in a job whose plan was fine. An `incomplete` list that is always non-empty teaches readers to
    # ignore it, so the plan is taken from the workflow's own hand-off first (`needs.plan.outputs.plan_json`)
    # and only then from the file, which is what a single-job or local run has.
    plan = None
    handoff = os.environ.get("PLAN_JSON", "").strip()
    if handoff:
        try:
            parsed = json.loads(handoff)
            plan = parsed if isinstance(parsed, dict) else None
            if plan is None:
                incomplete.append("PLAN_JSON: the plan hand-off parsed to a non-object; treated as absent")
        except json.JSONDecodeError as exc:
            incomplete.append(f"PLAN_JSON: the plan hand-off is not JSON ({exc.msg}); treated as absent")
    if plan is None:
        plan = _read_json(PLAN_FILE)
    if plan is None:
        incomplete.append("plan.json: neither the plan hand-off (PLAN_JSON) nor "
                           ".project-local/runs/ci/plan.json carried a plan")
    gate_stages = _read_json(GATE_STAGES_FILE)
    if gate_stages is None:
        incomplete.append("gate-stages.json: no gate sequence wrote a stage record in this job")

    sha = os.environ.get("GITHUB_SHA") or _git("rev-parse", "HEAD")
    tree = os.environ.get("GITHUB_SHA") and _git("rev-parse", f"{sha}^{{tree}}") or _git("rev-parse", "HEAD^{tree}")
    return {
        "schemaVersion": SCHEMA_VERSION,
        "generatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "run": {
            "repository": os.environ.get("GITHUB_REPOSITORY") or "local",
            "runId": os.environ.get("GITHUB_RUN_ID") or "local",
            "job": job,
            "event": os.environ.get("GITHUB_EVENT_NAME") or "local",
            "ref": os.environ.get("GITHUB_REF") or _git("rev-parse", "--abbrev-ref", "HEAD"),
            "sha": sha,
            "tree": tree,
        },
        "steps": [{"name": name, "status": status} for name, status in steps],
        "plan": _slice(plan, PLAN_KEYS) if plan else {"status": "MISSING"},
        "gates": _slice(gate_stages, GATE_KEYS) if gate_stages else {"status": "MISSING"},
        # An auditor must be able to see, from the artifact alone, that something was not available. This is
        # the difference between "this run had no plan" and "this run's plan said nothing was required".
        "incomplete": incomplete,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Assemble the redacted CI run summary artifact.")
    parser.add_argument("--job", required=True, help="Job name this summary describes.")
    parser.add_argument("--step", action="append", default=[], metavar="NAME=STATUS",
                        help="Repeatable. A step name and its outcome as this job observed it.")
    parser.add_argument("--out", type=Path, help="Output path (default .project-local/runs/ci/ci-summary-<job>.json).")
    args = parser.parse_args()

    steps: list[tuple[str, str]] = []
    for entry in args.step:
        if "=" not in entry:
            print(f"CI_SUMMARY_BAD_STEP {entry!r} (expected NAME=STATUS)", file=sys.stderr)
            return 2
        name, _, status = entry.partition("=")
        steps.append((name.strip(), status.strip()))

    summary = build_summary(args.job, steps)
    out = args.out or (CI_DIR / f"ci-summary-{args.job}.json")
    if not out.is_absolute():
        out = ROOT / out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8",
                   newline="\n")
    print(f"CI_SUMMARY_WRITTEN {out.relative_to(ROOT).as_posix()} job={args.job} "
          f"steps={len(steps)} incomplete={len(summary['incomplete'])}")
    for entry in summary["incomplete"]:
        print(f"CI_SUMMARY_INCOMPLETE {entry}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
