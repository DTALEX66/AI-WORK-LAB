"""Re-run the regression commands of the unbound PASS records, so "still true today" is measured.

Ninety-four records claim PASS with no pinned cause. They cannot be bound honestly (86 were born inside the
cutover import), but one thing can be established without inventing a cause: whether the command each record
names still runs and still passes on this tree. That is the difference between a claim that is merely old and
a claim that is now false, and only the second one has to be retracted.

Rules the tool holds itself to:
  * it runs only interpreters that are declared - the CI venv python and the pinned node runtime - never a
    shell string, so a record cannot make the tool execute arbitrary text;
  * a command with a `cd <dir> &&` prefix runs with that working directory, exactly as the record states it;
  * every run is bounded by a timeout, and a timeout is reported as TIMEOUT, not as a failure or a pass;
  * nothing is written except the receipt, and every verdict carries its exit code and the interpreter used.
"""
from __future__ import annotations

import argparse
import os
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LEDGER = ROOT / "taskpacks/current/error-ledger.json"
TARGETS = ROOT / "docs/audits/LEDGER_REGRESSION_COMMAND_TARGETS_2026-10-07.json"
TRIAGE = ROOT / "docs/audits/LEDGER_UNBOUND_TRIAGE_2026-10-07.json"

PYTHON = Path(r"D:\All projects\OS External Configuration\ArcheAxis-Knowledge-OS-ci-venv\Scripts\python.exe")
NODE = Path(r"C:\Users\ALEX\AppData\Local\OpenHuman\node-runtime\node-v22.11.0-win-x64\node.exe")
TIMEOUT_SECONDS = 150


def split_parts(text: str) -> list[str]:
    """A record's command is often several checks joined in prose (`a.py && b.py`, `a.py and b.py`,
    `a.py + b.py`). Passing the connective to the interpreter produced `module '__main__' has no attribute
    'and'`, which is a harness defect, not a failing invariant - so the joins are split and run in order."""
    pieces = re.split(r"\s*(?:&&|\band\b|\+)\s*", text)
    return [p.strip() for p in pieces if p.strip()]


def failure_class(tail: str) -> str:
    """Separate "the recorded command cannot be run as written" from "the check itself now fails".

    Most legacy commands are not executable lines but prose with a `+`, a shell-quoted glob, or a PYTHONPATH
    that named the pre-cutover directory. Those say the record is stale, not that the invariant broke, and
    conflating the two would either retract good records or hide bad ones.
    """
    if "NO TESTS RAN" in tail:
        return "COMMAND_NOT_RUNNABLE_AS_WRITTEN_glob_quoted"
    if "ModuleNotFoundError" in tail:
        return "COMMAND_NOT_RUNNABLE_AS_WRITTEN_import_path_superseded"
    if "unrecognized arguments" in tail or "usage:" in tail.lower():
        return "COMMAND_NOT_RUNNABLE_AS_WRITTEN_not_a_command_line"
    return "CHECK_ACTUALLY_FAILS"


def compile_part(text: str, cwd: Path) -> tuple[str, list[str], dict[str, str]]:
    """Return (interpreter, argv, env) for one command, or raise for anything undeclared."""
    parts = text.split()
    # Records write their command the way they ran it, which includes literal `NAME=value` prefixes.
    # Those are passed as environment, not as argv, and PYTHONPATH segments are expanded against the
    # command's own working directory the way scripts/ci/failfast_group.py does - a step-relative value
    # is what masked the 2026-09-25 fake-green.
    env: dict[str, str] = {}
    while parts and re.fullmatch(r"[A-Z_][A-Z0-9_]*=.*", parts[0]):
        key, _, value = parts.pop(0).partition("=")
        if key == "PYTHONPATH":
            value = ";".join(str(cwd / seg) if not Path(seg).is_absolute() else seg
                             for seg in value.split(";") if seg)
        env[key] = value
    if not parts:
        raise ValueError("no command left after stripping environment assignments")
    head, rest = parts[0], parts[1:]
    # Records state their command in whatever shape was true when the error was found, so the head is
    # sometimes an interpreter, sometimes a script path, sometimes `pytest`. All three map onto the two
    # declared runtimes; anything else (a shell, a bare word) stays refused rather than being executed.
    if head in {"python", "pytest"}:
        prefix = [str(PYTHON), "-X", "utf8"] + (["-m", "pytest"] if head == "pytest" else [])
        return "python", prefix + rest, env
    if head.endswith(".py"):
        return "python", [str(PYTHON), "-X", "utf8", head] + rest, env
    if head.endswith((".js", ".mjs", ".cjs")):
        return "node", [str(NODE), head] + rest, env
    if head == "node":
        return "node", [str(NODE)] + rest, env
    raise ValueError(f"undeclared interpreter: {head!r}")


def split_command(command: str, record_cwd: Path) -> tuple[Path, list[tuple[str, list[str]]], dict[str, str]]:
    """Return (working directory, [(interpreter, argv), ...], env); a record may name several checks."""
    text = command.strip()
    cwd = record_cwd
    m = re.match(r"^cd\s+(?P<dir>[^\s&]+)\s*&&\s*(?P<rest>.*)$", text, re.DOTALL)
    if m:
        rel = m.group("dir").replace("\\", "/")
        text = m.group("rest").strip()
        candidate = (ROOT / rel).resolve() if not rel.isabs() and not rel.startswith("/") else Path(rel)
        if not str(candidate).startswith(str(ROOT)):
            raise ValueError(f"cd escapes the repository: {rel}")
        cwd = candidate
    plan, env, seen = [], {}, {}
    for piece in split_parts(text):
        interpreter, argv, piece_env = compile_part(piece, cwd)
        seen.update(piece_env)
        plan.append((interpreter, argv))
    return cwd, plan, seen


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "docs/audits/LEDGER_UNBOUND_RERUN_2026-10-07.json"))
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--only", default="", help="comma-separated error ids")
    args = ap.parse_args()

    ledger = {e["error_id"]: e for e in json.loads(LEDGER.read_text(encoding="utf-8"))["errors"]}
    targets = {r["errorId"]: r for r in json.loads(TARGETS.read_text(encoding="utf-8"))["rows"]}
    triage = json.loads(TRIAGE.read_text(encoding="utf-8"))
    wanted = set(args.only.split(",")) if args.only else set(triage["bindableByBirthCommit"]) | {
        r["errorId"] for r in triage["rows"] if r["state"] == "RESOLVES"}

    env = {"PYTHONUTF8": "1", "PYTHONDONTWRITEBYTECODE": "1"}
    results = []
    for eid in sorted(wanted):
        if args.limit and len(results) >= args.limit:
            break
        record = ledger.get(eid)
        if not record:
            continue
        command = targets.get(eid, {}).get("command") or record.get("command") or ""
        if not command:
            results.append({"errorId": eid, "verdict": "NO_COMMAND_RECORDED"})
            continue
        try:
            cwd, plan, extra_env = split_command(command, ROOT)
        except ValueError as exc:
            results.append({"errorId": eid, "verdict": "REFUSED", "reason": str(exc),
                            "command": command[:160]})
            continue
        try:
            parts_out, code, full = [], 0, ""
            for interpreter, argv in plan:
                proc = subprocess.run(argv, cwd=cwd, capture_output=True, text=True,
                                      timeout=TIMEOUT_SECONDS, encoding="utf-8", errors="replace",
                                      env={**os.environ, **env, **extra_env})
                full += (proc.stdout or "") + (proc.stderr or "")
                parts_out.append({"interpreter": interpreter, "argv0": argv[-1] if argv else "",
                                  "exitCode": proc.returncode})
                if proc.returncode and not code:
                    code = proc.returncode
            tail_lines = full.strip().splitlines()[-3:]
            tail_text = " | ".join(tail_lines)[:300]
            # The cause is usually not in the last three lines: unittest prints the ModuleNotFoundError in
            # the traceback body and closes with "FAILED (errors=3)", so classifying on the tail relabelled
            # import-path failures as real ones. Keep the matched line in the receipt so the class is auditable.
            cause = next((line.strip()[:200] for line in full.splitlines()
                          if re.search(r"(Error|Exception|NO TESTS RAN|unrecognized arguments)", line)), "")
            row = {"errorId": eid, "command": command[:160],
                   "cwd": str(cwd).replace(str(ROOT), "."), "exitCode": code,
                   "verdict": "PASS" if code == 0 else "FAIL",
                   "partsRun": parts_out, "tail": tail_text}
            if code != 0:
                row["failureClass"] = failure_class(full)
                row["causeLine"] = cause
            results.append(row)
        except subprocess.TimeoutExpired:
            results.append({"errorId": eid, "command": command[:160], "interpreter": interpreter,
                            "verdict": "TIMEOUT", "timeoutSeconds": TIMEOUT_SECONDS})
        except FileNotFoundError as exc:
            results.append({"errorId": eid, "command": command[:160],
                            "verdict": "INTERPRETER_OR_FILE_MISSING", "reason": str(exc)[:200]})

    counts: dict[str, int] = {}
    by_failure: dict[str, int] = {}
    for r in results:
        counts[r["verdict"]] = counts.get(r["verdict"], 0) + 1
        if r.get("failureClass"):
            by_failure[r["failureClass"]] = by_failure.get(r["failureClass"], 0) + 1
    doc = {"schemaVersion": "work-lab/ledger-unbound-rerun/v1",
           "tool": "scripts/audit/rerun_unbound_pass_checks.py",
           "ranAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
           "scope": "unbound PASS records whose recorded command names a file that still resolves",
           "interpretersDeclared": [str(PYTHON), str(NODE)],
           "shellUsed": False,
           "counts": counts,
           "byFailureClass": by_failure,
           "results": results}
    Path(args.out).write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(counts, ensure_ascii=False))
    for r in results:
        print(f"  {r['errorId']:9s} {r['verdict']:28s} exit={r.get('exitCode')} {r.get('reason', '')[:60]}")
    print("receipt ->", args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
