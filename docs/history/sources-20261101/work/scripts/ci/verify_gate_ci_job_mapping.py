#!/usr/bin/env python3
"""W07 (2026-10-17): prove the CI-job <-> local-gate mapping, in both directions.

Why
---
The profile says which local gate a change requires. The workflows say which jobs actually run -- and their
job IDs are what branch protection aggregates. Before this checker, the two sides agreed by *resemblance*:
the five heavy gates happened to share their IDs with the workflow jobs, and four additional required jobs
(`schema-fixtures`, `observer-readonly`, `config-compiler`, `capsule-verify`) were covered by nothing at all,
invisibly. A rename on either side, or a new job, would have changed what CI requires without changing what a
writer's local run suggests -- and nothing would have said so.

What it enforces
----------------
1. every profile gate names a `ci_job` that exists as a job ID in one of the workflows;
2. every job ID in either workflow is accounted for -- claimed by a gate, or declared `structural_jobs` (the
   plan/aggregate machinery), or declared under `additional_required_jobs` (a required job with no gate);
3. no stale declarations: every declared job exists, and a declared `local_route` names a tracked file;
4. `local_route: null` is ALLOWED and is the point -- it makes a CI-only check visible. Silence is what this
   rejects, not a gap.
5. (CL-14, 2026-10-25) every stage in the canonical gate's `VERIFY_ORDER` is either invoked by name in a
   workflow step or declared under `ci.stage_coverage` with a reason. This direction did not exist, so 27 of
   the 50 stages a writer's `verify` run performs were simply absent from the CI picture: nobody could tell
   "CI does not require this" from "CI requires it under another name" -- and a stage whose CI absence is
   unstated is a coverage claim, not a gap disclosure.
"""
from __future__ import annotations

import argparse
import importlib.util
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[2]
PROFILE = ROOT / ".project" / "governance" / "work-lab.project-profile.yaml"
WORKFLOWS = (ROOT / ".github" / "workflows" / "work-lab-gate.yml",
             ROOT / ".github" / "workflows" / "wlr-060-gates.yml")
GATE_SCRIPT = ROOT / "services" / "orchestration" / "run_quality_gate.py"
STAGE_CALL = re.compile(r"run_quality_gate\.py\s+([a-z][a-z0-9-]*)")
# `verify` is the sequence and `plan`/`list` are read-only views of it, so they are called the way a stage is
# but are not stages. `governance` IS a stage -- the fail-closed batch of the mandatory workflow + nf* tests --
# and stays counted as one.
GATE_MODES = ("verify", "plan", "list")
STAGE_STATUSES = ("invoked_in_ci", "covered_by_ci_step", "needs_local_environment", "is_ci_verdict_itself")



def tracked_files(root: Path) -> set[str]:
    result = subprocess.run(["git", "ls-files"], cwd=root, capture_output=True, text=True,
                            encoding="utf-8", errors="replace", check=False)
    return {line.strip() for line in result.stdout.splitlines() if line.strip()}


def verify_order_stages() -> tuple[str, ...]:
    """The canonical gate's own `VERIFY_ORDER`, read from the script that defines it.

    Not copied into this file: a second list would drift the moment a stage is added, and the drift would look
    like coverage. `run_quality_gate.py` imports only the standard library at module scope, so this exec is
    cheap and has no dependency on a project virtualenv.
    """
    spec = importlib.util.spec_from_file_location("run_quality_gate_for_stages", GATE_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {GATE_SCRIPT} to read VERIFY_ORDER")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return tuple(module.VERIFY_ORDER)


def workflow_run_commands(paths: tuple[Path, ...]) -> dict[str, list[str]]:
    """Every runnable line in both workflows, keyed by the workflow that holds it.

    Parsed from the YAML rather than searched as text, and comment lines are dropped from the bodies: a step's
    `run: |` block explains itself in shell comments, and one that quotes `run_quality_gate.py <stage>` as a
    historical note would otherwise be read as CI running that stage. This function decides what CI is claimed
    to execute, so it reads only what the shell would execute.
    """
    commands: dict[str, list[str]] = {}
    for path in paths:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        found: list[str] = []
        for job in (data.get("jobs") or {}).values():
            for step in (job or {}).get("steps") or []:
                body = (step or {}).get("run")
                if isinstance(body, str):
                    found.append("\n".join(line for line in body.splitlines()
                                           if not line.lstrip().startswith("#")))
        commands[path.name] = found
    return commands


def invoked_stages(commands: dict[str, list[str]]) -> dict[str, str]:
    """stage name -> the workflow that invokes it, from the `run:` bodies only."""
    invoked: dict[str, str] = {}
    for workflow, bodies in commands.items():
        for body in bodies:
            for match in STAGE_CALL.finditer(body):
                name = match.group(1)
                if name not in GATE_MODES:
                    invoked.setdefault(name, workflow)
    return invoked


def workflow_jobs(paths: tuple[Path, ...]) -> dict[str, str]:
    """job id -> the workflow file it lives in. The id is what `needs:` and branch protection use; the
    display `name:` is deliberately ignored -- `workflow` is displayed as "workflow-assistance", and a
    mapping written against the display name would look right and match nothing."""
    jobs: dict[str, str] = {}
    for path in paths:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        for job_id in (data.get("jobs") or {}):
            jobs[str(job_id)] = path.name
    return jobs


def stage_coverage_audit(profile: dict[str, Any], stages: tuple[str, ...],
                         invoked: dict[str, str], jobs: dict[str, str]) -> list[str]:
    """Direction five (CL-14): a canonical-gate stage is either invoked by CI or its absence is declared."""
    problems: list[str] = []
    coverage = (profile.get("ci") or {}).get("stage_coverage") or {}
    stage_set = set(stages)

    for name in sorted(coverage):
        if name not in stage_set:
            problems.append(f"ci.stage_coverage declares {name!r}, which is not a stage in VERIFY_ORDER "
                            f"(a stale declaration would keep covering nothing after the stage is renamed away)")

    for stage in stages:
        entry = coverage.get(stage)
        if stage in invoked:
            if entry and (entry or {}).get("status") not in (None, "invoked_in_ci"):
                problems.append(f"stage {stage!r} is invoked in {invoked[stage]} but declared as "
                                f"{(entry or {}).get('status')!r}; a declaration must not hide an invocation")
            continue
        if not entry:
            problems.append(f"stage {stage!r} is not invoked by any workflow step and declared nowhere; "
                            f"an unstated absence reads as coverage, not as a gap")
            continue
        entry = entry or {}
        status = entry.get("status")
        if status not in STAGE_STATUSES or status == "invoked_in_ci":
            problems.append(f"stage {stage!r} declares status {status!r}; a non-invoked stage needs one of "
                            f"{[s for s in STAGE_STATUSES if s != 'invoked_in_ci']}")
            continue
        if not entry.get("reason"):
            problems.append(f"stage {stage!r} declares {status} without a reason; the reason is the disclosure")
        if status == "covered_by_ci_step":
            ref = entry.get("covered_by")
            if not ref:
                problems.append(f"stage {stage!r} claims coverage by a CI step but names none")
            elif ref not in invoked and ref not in jobs:
                problems.append(f"stage {stage!r} claims coverage by {ref!r}, which is neither a stage any "
                                f"workflow invokes nor a job ID")
    return problems


def audit(profile: dict[str, Any], jobs: dict[str, str], tracked: set[str]) -> list[str]:
    problems: list[str] = []
    gates = profile.get("gates") or {}
    ci = profile.get("ci") or {}
    structural = ci.get("structural_jobs") or {}
    additional = ci.get("additional_required_jobs") or {}

    claimed: dict[str, str] = {}
    for gate_id, gate in gates.items():
        job = (gate or {}).get("ci_job")
        if not job:
            problems.append(f"gate {gate_id!r} names no ci_job; the CI side of this gate is unstated")
            continue
        if job not in jobs:
            problems.append(f"gate {gate_id!r} claims ci_job {job!r}, which is not a job in any workflow")
            continue
        if job in claimed and claimed[job] != gate_id:
            problems.append(f"ci_job {job!r} is claimed by both {claimed[job]!r} and {gate_id!r}")
        claimed[job] = gate_id

    for job_id in sorted(jobs):
        if job_id in claimed or job_id in structural or job_id in additional:
            continue
        problems.append(f"workflow job {job_id!r} ({jobs[job_id]}) is claimed by no gate and declared nowhere; "
                        f"a required job a writer cannot see from a local run")

    for job_id in sorted(list(structural) + list(additional)):
        if job_id not in jobs:
            problems.append(f"profile declares job {job_id!r}, which no workflow defines (stale declaration)")

    for job_id, entry in sorted(additional.items()):
        entry = entry or {}
        route = entry.get("local_route", "MISSING")
        if route == "MISSING":
            problems.append(f"additional job {job_id!r} declares no local_route; use null with a reason "
                            f"instead of omitting the field, so 'CI-only' is a statement and not a gap")
            continue
        if route is None:
            if not entry.get("note"):
                problems.append(f"additional job {job_id!r} declares local_route: null without a note")
            continue
        # A route is a command; the first token that looks like a repo path decides whether it is tracked.
        candidates = [token for token in str(route).split() if "/" in token]
        if not candidates:
            problems.append(f"additional job {job_id!r} local_route {route!r} names no repo path")
            continue
        target = candidates[0].lstrip("./")
        if target not in tracked:
            problems.append(f"additional job {job_id!r} local_route points at {target!r}, which is not tracked")
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args(argv)

    profile = yaml.safe_load(PROFILE.read_text(encoding="utf-8")) or {}
    jobs = workflow_jobs(WORKFLOWS)
    if not jobs:
        print("GATE_CI_JOB_MAPPING_FAIL no jobs found in the workflows; a checker that sees nothing "
              "reports nothing")
        return 1
    stages = verify_order_stages()
    invoked = invoked_stages(workflow_run_commands(WORKFLOWS))
    if not stages:
        print("GATE_CI_JOB_MAPPING_FAIL VERIFY_ORDER read as empty; the fifth direction would pass by sight")
        return 1
    problems = audit(profile, jobs, tracked_files(args.root))
    problems += stage_coverage_audit(profile, stages, invoked, jobs)
    declared = (profile.get("ci") or {}).get("stage_coverage") or {}
    print(f"GATE_CI_JOB_MAPPING jobs={len(jobs)} gates={len(profile.get('gates') or {})} "
          f"structural={len((profile.get('ci') or {}).get('structural_jobs') or {})} "
          f"additional={len((profile.get('ci') or {}).get('additional_required_jobs') or {})}")
    print(f"GATE_CI_JOB_MAPPING stages={len(stages)} invoked={len(invoked)} declared={len(declared)} "
          f"undeclared={len([s for s in stages if s not in invoked and s not in declared])}")
    for problem in problems:
        print(f"  {problem}")
    if problems:
        print(f"GATE_CI_JOB_MAPPING_FAIL problems={len(problems)}")
        return 1
    print("GATE_CI_JOB_MAPPING_PASS every job is claimed or declared, every gate names a real job, "
          "every canonical stage is invoked or its absence declared")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
