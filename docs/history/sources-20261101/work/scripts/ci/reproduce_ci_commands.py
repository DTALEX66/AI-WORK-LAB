"""Run every command the CI workflows invoke, locally, and report each exit code.

`ci_step_repro.py` reproduced one step of one job, and that is what let a
source-ledger schema break through: the integration job has its own verifier list and
a green workflow-assistance job said nothing about it (ERR-128). This tool reads both
workflow files with a YAML parser, takes every `run:` block, splits it into logical
commands (joining backslash continuations and multi-line quoted arguments the way a
shell would) and executes the ones that start with an interpreter, labelling each with
its job and step.

It reproduces commands, not actions: no fresh checkout, no clean environment, no
matrix, and steps built from `uses:` are not attempted. Anything excluded with --skip
prints as SKIPPED rather than disappearing.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import subprocess
import sys
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[2]
WORKFLOWS = (REPO / ".github" / "workflows" / "work-lab-gate.yml",
             REPO / ".github" / "workflows" / "wlr-060-gates.yml")
PY = REPO / ".project-local" / "toolchains" / "wl-py311" / "Scripts" / "python.exe"
INTERPRETERS = ("python", "node", "npm", "npx", "bash", "pytest", "cargo")


def logical_commands(block: str) -> list[list[str]]:
    """Split a shell `run:` block into argv lists, the way bash groups statements."""
    commands: list[list[str]] = []
    buffer: list[str] = []
    single = False
    double = False
    for raw in block.splitlines():
        line = raw.rstrip()
        if not line.strip() and not buffer:
            continue
        if line.lstrip().startswith("#") and not (single or double):
            continue
        buffer.append(line)
        for char in line:
            if char == "'" and not double:
                single = not single
            elif char == '"' and not single:
                double = not double
        joined = "\n".join(buffer)
        continued = joined.rstrip().endswith("\\") and not (single or double)
        if single or double or continued:
            continue
        stripped = joined.strip().rstrip("\\").strip()
        buffer = []
        if not stripped:
            continue
        try:
            argv = shlex.split(stripped, posix=True)
        except ValueError:
            argv = stripped.split()
        if argv:
            commands.append(argv)
    return commands


def workflow_commands(path: Path) -> list[tuple[str, str, list[str]]]:
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    default_cwd = str(((doc.get("defaults") or {}).get("run") or {}).get("working-directory") or ".")
    out = []
    for job_id, job in (doc.get("jobs") or {}).items():
        job_cwd = str(((job.get("defaults") or {}).get("run") or {})
                      .get("working-directory") or default_cwd)
        for step in job.get("steps") or []:
            name = str(step.get("name") or step.get("id") or "(unnamed step)")
            run = step.get("run")
            if not isinstance(run, str):
                continue
            step_cwd = str(((step.get("working-directory")) or job_cwd))
            # A step whose env comes from `github.*` / a previous job's output cannot be
            # reproduced here at all; saying so beats letting it die on a KeyError.
            env_context = any("${{" in str(value) for value in (step.get("env") or {}).values())
            for argv in logical_commands(run):
                out.append((job_id, name, argv, step_cwd, env_context))
    return out


def main(head_at_start: str | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skip", action="append", default=[],
                        help="substring of a command line to mark SKIPPED (repeatable)")
    parser.add_argument("--only", action="append", default=[],
                        help="substring required in job, step or command (repeatable)")
    parser.add_argument("--list", action="store_true", help="print coverage, run nothing")
    parser.add_argument("--receipt", type=Path,
                        default=REPO / ".project-local" / "runs" / "ci"
                        / "reproduce_ci_commands_receipt.json")
    args = parser.parse_args()
    if head_at_start is None:
        head_at_start = subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO,
                                        capture_output=True, text=True, encoding="utf-8", errors="replace").stdout.strip()
    if args.list:
        head_at_start = ""

    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    all_commands, non_interpreters = [], []
    for path in WORKFLOWS:
        if not path.is_file():
            print("MISSING-WORKFLOW", path)
            return 2
        for job, step, argv, cwd, env_context in workflow_commands(path):
            if argv and argv[0].split("/")[-1] in INTERPRETERS:
                all_commands.append((job, step, argv, cwd, env_context))
            else:
                non_interpreters.append((job, step, " ".join(argv[:6])))

    print(f"workflows={len(WORKFLOWS)} interpreter_commands={len(all_commands)} "
          f"other_shell_lines_not_reproduced={len(non_interpreters)}")
    if args.list:
        for job, step, argv, cwd, _ in all_commands:
            print(f"  {job} / {step[:40]} [cwd={cwd}] :: {' '.join(argv)[:80]}")
        return 0

    results, failures, skipped = [], [], []
    env = dict(os.environ)
    for extra in (REPO / ".project-local" / "toolchains" / "wl-py311" / "Scripts",
                  Path(r"D:\All projects\OS External Configuration\10-toolchains"
                       r"\scoop\apps\nodejs-lts\24.18.0")):
        if extra.is_dir():
            env["PATH"] = f"{extra}{os.pathsep}{env.get('PATH', '')}"
    for index, (job, step, argv, cwd, env_context) in enumerate(all_commands, 1):
        line = " ".join(argv)
        if args.only and not any(needle in f"{job} {step} {line}" for needle in args.only):
            continue
        if "${{" in line or env_context:
            skipped.append(f"CI_CONTEXT: {line[:70]}")
            print(f"[{index:>3}/{len(all_commands)}] CI_CONTEXT (a github.* expression or a "
                  f"runner-exported env map is required; not reproducible locally) "
                  f"{job}/{step[:30]}")
            continue
        if any(needle in line for needle in args.skip):
            skipped.append(line)
            print(f"[{index:>3}/{len(all_commands)}] SKIPPED {line[:80]}")
            continue
        invoked = [str(PY)] + argv[1:] if argv[0].split("/")[-1] == "python" else argv
        workdir = REPO / cwd if cwd and cwd != "." else REPO
        unbound = [tok for tok in argv if re.match(r"^\$[A-Za_]", tok)]
        if unbound and not all(tok[1:].split("{")[0] in env for tok in unbound):
            skipped.append(f"STEP_ENV: {line[:70]}")
            print(f"[{index:>3}/{len(all_commands)}] STEP_ENV ({', '.join(unbound)[:54]}) "
                  f"{job}/{step[:28]} — exported by the runner or an earlier step; not faked")
            continue
        try:
            proc = subprocess.run(invoked, cwd=workdir, capture_output=True, text=True,
                                  encoding="utf-8", errors="replace", env=env)
        except FileNotFoundError as exc:
            skipped.append(f"TOOL_NOT_ON_PATH: {line[:70]}")
            print(f"[{index:>3}/{len(all_commands)}] TOOL_NOT_ON_PATH {invoked[0]!r} "
                  f"({job}/{step[:30]}) — recorded, not passed off as a success")
            continue
        record = {"job": job, "step": step, "cmd": line, "exit": proc.returncode,
                  "tail": (proc.stdout + proc.stderr)[-500:]}
        results.append(record)
        print(f"[{index:>3}/{len(all_commands)}] exit={proc.returncode} "
              f"{'ok  ' if proc.returncode == 0 else 'FAIL'} {job}/{step[:32]} :: {line[:64]}",
              flush=True)
        if proc.returncode != 0:
            failures.append(record)
            print("     " + record["tail"].strip().replace("\n", "\n     ")[:900])

    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO, capture_output=True,
                          text=True, encoding="utf-8", errors="replace").stdout.strip()
    if args.list:
        return 0
    if head != head_at_start:
        # A receipt whose rows were measured across two commits describes neither, so the head field
        # would name a tree the failures did not see. Say which head the rows actually belong to and
        # exit non-zero with a named condition instead of publishing an ambiguous proof.
        print(f"CI_REPRO_HEAD_MOVED start={head_at_start[:9]} end={head[:9]} "
              f"ran={len(results)} failures={len(failures)} :: the rows describe the tree at "
              f"start={head_at_start[:9]}, not the head this receipt would otherwise claim")
    args.receipt.write_text(json.dumps(
        {"head": head, "headAtStart": head_at_start, "headAtEnd": head,
         "headMovedDuringRun": head != head_at_start,
         "interpreter_commands": len(all_commands), "ran": len(results),
         "not_reproduced_shell_lines": non_interpreters[:60], "skipped": skipped,
         "failures": failures, "results": results}, indent=2, ensure_ascii=False),
        encoding="utf-8")
    print(f"RESULT ran={len(results)} failures={len(failures)} skipped={len(skipped)} "
          f"receipt={args.receipt}")
    if head != head_at_start:
        return 3
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
