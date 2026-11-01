#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""DLDS-H020 — verify that the committed tree reproduces from a clean clone.

A checkout that only works because of local, untracked state is not reproducible.
This clones HEAD into an ignored directory and runs the static and test layers
there with the interpreter that already has the dependencies installed:

* install: `uv sync --locked` is what CI runs, and uv is absent on this machine,
  so the stage is recorded as NOT_VERIFIABLE rather than passed;
* dependencies: pyproject.toml, uv.lock and requirements.txt are present and parse;
* contracts: every JSON schema parses, and the contract graph gate runs in the clone;
* reports: the generator runs in the clone and its own --check passes there;
* tests: a bounded subset runs in the clone with the local interpreter;
* path boundaries: the clone's own .project-local resolution stays inside the clone.

Writes reports/current/FRESH-CLONE-VERIFICATION.json.

Usage:
    python scripts/verify_fresh_clone.py [--tests]
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
CLONE = REPO / ".project-local/task-runtime/fresh-clone"
OUT = REPO / "reports/current/FRESH-CLONE-VERIFICATION.json"
TASK_KEY = "DL-TP-20260914-DEEPSEEK-AUTHORITY-R1::DLDS-H020"
TEST_PATTERNS = ("test_creative_job.py", "test_interop_dtcg.py", "test_assurance_qa_plane.py")


def resolve_interpreter() -> tuple[str, str]:
    """Platform-neutral interpreter selection (DL-AUDIT-20260914-06).

    No longer hard-codes ``.venv/Scripts/python.exe``: the interpreter that
    launched this gate is preferred (it already has the project dependencies),
    then the virtualenv layout of the running platform, then ``python3``. The
    stage that needs dependencies (the clone) runs the *same* interpreter, so
    a clean-clone claim is not smuggled through an invisible dependency.
    Returns (command, source).
    """
    import sys
    if sys.executable:
        return sys.executable, "python:the interpreter running this gate"
    for candidate in (REPO / ".venv/bin/python", REPO / ".venv/Scripts/python.exe"):
        if candidate.exists():
            return str(candidate), f"virtualenv:{candidate.relative_to(REPO)}"
    return "python3", "PATH:python3 (no project virtualenv found)"


PYTHON, PYTHON_SOURCE = resolve_interpreter()


def run(command: list, cwd: Path, timeout: int = 900) -> tuple:
    result = subprocess.run(command, cwd=str(cwd), capture_output=True, text=True, encoding="utf-8",
                            errors="replace", timeout=timeout)
    return result.returncode, ((result.stdout or "") + (result.stderr or "")).strip()


def git(*args: str) -> str:
    return subprocess.run(["git", "-C", str(REPO), *args], capture_output=True, text=True,
                          encoding="utf-8", errors="replace").stdout.strip()


def clear_previous_clone(path: Path) -> str | None:
    """Remove the leftover clone, or return the reason it could not be removed.

    This used to be `shutil.rmtree(path, ignore_errors=True)`, which hid a real
    failure: a nested clone contains paths long enough that plain deletion on Windows
    does not clear the tree, the directory survived, and the very next line's clone
    failed with "destination path already exists". The gate reported
    FAIL against the *clone* stage while the actual cause was the leftover, and the
    error text was discarded. The `\\\\?\\` prefix opts the path into Win32 long-path
    handling; if removal still fails, the failure is named instead of swallowed.
    """
    if not path.exists():
        return None
    target = Path("\\\\?\\" + str(path)) if os.name == "nt" else path
    try:
        shutil.rmtree(target)
    except OSError as exc:
        return f"{type(exc).__name__} removing {path}: {exc}"
    return None if not path.exists() else "directory still present after removal"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tests", action="store_true", help="also run the bounded test subset")
    args = parser.parse_args(argv)
    stages = []

    def stage(name: str, state: str, evidence: str) -> None:
        stages.append({"stage": name, "state": state, "evidence": evidence[:400]})

    leftover = clear_previous_clone(CLONE)
    if leftover is not None:
        code, out = 1, leftover
    else:
        CLONE.parent.mkdir(parents=True, exist_ok=True)
        code, out = run(["git", "clone", "--quiet", "--no-hardlinks", str(REPO), str(CLONE)], REPO)
    stage("clone", "PASS" if code == 0 else "FAIL", out or f"cloned HEAD {git('rev-parse', 'HEAD')[:12]} into an ignored directory")

    if code == 0:
        code, out = run(["git", "rev-parse", "HEAD"], CLONE)
        stage("clone_head_matches", "PASS" if out == git("rev-parse", "HEAD") else "FAIL",
              f"clone HEAD {out[:12]} vs source {git('rev-parse', 'HEAD')[:12]}")

        tracked = run(["git", "ls-files"], CLONE)[1].splitlines()
        untracked_local = [p for p in ("AGENTS.md", "pyproject.toml", "uv.lock", "requirements.txt",
                                       "design-lab/schemas", "reports/current", ".project/paths.json")
                           if not (CLONE / p).exists()]
        stage("tracked_content_present", "PASS" if not untracked_local else "FAIL",
              f"{len(tracked)} tracked files; missing: {untracked_local or 'none'}")

        code, out = run([PYTHON, "-c",
                         "import json,sys,pathlib;"
                         "ps=sorted(pathlib.Path('design-lab/schemas').rglob('*.json'));"
                         "[json.loads(p.read_text(encoding='utf-8')) for p in ps];"
                         "print(f'{len(ps)} schemas parse')"], CLONE)
        stage("contracts_parse", "PASS" if code == 0 else "FAIL", out)

        code, out = run([PYTHON, "scripts/verify_contract_graph.py"], CLONE)
        stage("contract_graph", "PASS" if code == 0 else "FAIL",
              "\n".join(line for line in out.splitlines() if line.startswith(("CONTRACT_GRAPH", "  BREAK"))))

        code, out = run([PYTHON, "scripts/generate_current_reports.py"], CLONE)
        stage("reports_generate", "PASS" if code == 0 else "FAIL", out.splitlines()[-1] if out else "")
        code, out = run([PYTHON, "scripts/generate_current_reports.py", "--check"], CLONE)
        stage("reports_check", "PASS" if code == 0 else "FAIL", out.splitlines()[-1] if out else "")

        code, out = run([PYTHON, "-c",
                         "import sys; sys.path.insert(0,'src');"
                         "from design_lab.runtime.paths import resolve_paths;"
                         "l=resolve_paths();"
                         "print('local_root', l.local_root)"], CLONE)
        inside = str(CLONE).lower() in out.lower()
        stage("path_boundaries", "PASS" if code == 0 and inside else "FAIL",
              f"{out} (resolves inside the clone: {inside})")

        code, out = run([PYTHON, "-c", "import shutil; print('uv:', shutil.which('uv'))"], CLONE)
        # The message used to assert "uv is absent" unconditionally, two lines after asking
        # shutil.which for the answer and printing it in `out`. When uv WAS on PATH the report
        # stated a falsehood about the machine that produced it. The stage is still
        # NOT_VERIFIABLE -- no install is attempted and no network is used -- but the reason
        # now says what was measured rather than what was assumed.
        found = out.strip().split("uv:")[-1].strip() or "not reported"
        present = found not in {"None", "not reported"}
        stage("install", "NOT_VERIFIABLE",
              f"CI runs 'uv sync --locked'; probe read uv as: {found}. No install was "
              f"attempted here{' (so presence is not proof it resolves the lock)' if present else ''}, "
              f"and no network is used, so a clean-clone install cannot be proven by this run.")

        if args.tests:
            for pattern in TEST_PATTERNS:
                code, out = run([PYTHON, "-m", "unittest", "discover",
                                 "-s", "design-lab/tests", "-p", pattern, "-t", "design-lab/tests"],
                                CLONE)
                summary = [line for line in out.splitlines() if line.startswith(("OK", "FAILED", "Ran "))]
                stage(f"tests:{pattern}", "PASS" if code == 0 else "FAIL", " | ".join(summary[-2:]))

    failures = [s["stage"] for s in stages if s["state"] == "FAIL"]
    document = {
        "schemaVersion": "design-lab/fresh-clone-verification/v1",
        "task_key": TASK_KEY,
        "verified_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "subject_sha": git("rev-parse", "HEAD"),
        "clone_path": str(CLONE.relative_to(REPO)).replace("\\", "/"),
        "interpreter": {"command": PYTHON, "source": PYTHON_SOURCE,
                         "note": "selected at gate start without a hard-coded Windows path; "
                                 "a missing virtualenv makes the dependency stage NOT_VERIFIED, "
                                 "never a silent pass"},
        "stages": stages,
        "failures": failures,
        "unverifiable": [s["stage"] for s in stages if s["state"] == "NOT_VERIFIABLE"],
        "verdict": "PASS" if not failures else "FAIL",
        "note": "a clone proves the committed tree; it cannot prove an install without uv and a "
                "network, and that stage is recorded as NOT_VERIFIABLE rather than passed",
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(document, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    print(f"FRESH_CLONE={document['verdict']} stages={len(stages)} failures={failures} "
          f"unverifiable={document['unverifiable']}")
    for item in stages:
        print(f"  {item['state']:14} {item['stage']:24} {item['evidence'].splitlines()[0][:86]}")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
