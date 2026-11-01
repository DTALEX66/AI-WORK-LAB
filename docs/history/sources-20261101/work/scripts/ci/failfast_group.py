#!/usr/bin/env python3
"""Fail-fast required-command group runner for WORK-LAB CI (P0-01 CI Truth Repair).

Root cause fixed here: GitHub Actions on windows-latest uses PowerShell as the
default step shell; a multi-line step keeps running after a failed command and
the step exit code becomes the LAST command's status. Required-command
failures were therefore masked (2026-09-25 observer fake-green: three python
tests crashed with ModuleNotFoundError: jsonschema while the step, the job and
the aggregate all reported SUCCESS).

This runner executes one named group from required_groups.json strictly in
sequence, without a shell for argv commands:

  * every command's exit code is printed (CI evidence requirement)
  * the first non-zero command stops the group; remaining commands are skipped
  * the group exits with the failing command's code, so a later successful
    command can never mask an earlier failure

Manifest: scripts/ci/required_groups.json (sibling of this runner).
Command forms:
  ["npm", "run", "typecheck"]                     -> argv, no shell
  {"glob": "web/scripts/*.js",
   "argv_template": ["node", "--check", "{path}"]} -> one argv command per
                                                         sorted glob match

Usage (paths in the manifest are repository-root relative):
  python scripts/ci/failfast_group.py --group observer-python-skeleton
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MANIFEST = REPO_ROOT / "scripts" / "ci" / "required_groups.json"


def load_groups(manifest_path: Path) -> dict:
    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"FAILFAST_GROUP_ERROR manifest={manifest_path} unreadable: {exc}")
        raise SystemExit(2)
    groups = data.get("groups")
    if not isinstance(groups, dict) or not groups:
        print(f"FAILFAST_GROUP_ERROR manifest={manifest_path} has no groups")
        raise SystemExit(2)
    return groups


def expand_commands(group: dict) -> list[list[str]]:
    name = group.get("name", "?")
    out: list[list[str]] = []
    for entry in group.get("commands", []):
        if isinstance(entry, list):
            if not entry or not all(isinstance(part, str) and part for part in entry):
                print(f"FAILFAST_GROUP_ERROR group={name} command must be a non-empty list of strings")
                raise SystemExit(2)
            out.append(list(entry))
        elif isinstance(entry, dict):
            pattern = entry.get("glob")
            template = entry.get("argv_template")
            if not isinstance(pattern, str) or not isinstance(template, list):
                print(f"FAILFAST_GROUP_ERROR group={name} malformed glob entry: {entry!r}")
                raise SystemExit(2)
            base = REPO_ROOT / group.get("working_dir", ".")
            matches = sorted(glob.glob(str(base / pattern)))
            if not matches:
                print(f"FAILFAST_GROUP_ERROR group={name} glob matched nothing: {pattern}")
                raise SystemExit(2)
            for match in matches:
                out.append([part.replace("{path}", match) for part in template])
        else:
            print(f"FAILFAST_GROUP_ERROR group={name} unknown command form: {entry!r}")
            raise SystemExit(2)
    if not out:
        print(f"FAILFAST_GROUP_ERROR group={name} has no commands")
        raise SystemExit(2)
    return out


def resolve_executable(argv: list[str]) -> list[str]:
    """Resolve a bare executable name via PATH (PATHEXT-aware on Windows,
    e.g. npm.cmd / cargo.exe). Relative-path or absolute executables pass
    through unchanged."""
    head = argv[0]
    if "/" in head or "\\" in head:
        return list(argv)
    resolved = shutil.which(head)
    if resolved is None:
        print(f"FAILFAST_GROUP_ERROR executable not found in PATH: {head}")
        raise SystemExit(127)
    return [resolved, *argv[1:]]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--group", required=True)
    args = parser.parse_args()

    groups = load_groups(args.manifest)
    if args.group not in groups:
        print(f"FAILFAST_GROUP_ERROR unknown_group={args.group} available={sorted(groups)}")
        return 2

    group = dict(groups[args.group])
    group["name"] = args.group
    commands = expand_commands(group)
    cwd = REPO_ROOT / group.get("working_dir", ".")
    if not cwd.is_dir():
        print(f"FAILFAST_GROUP_ERROR group={args.group} working_dir missing: {cwd}")
        return 2

    env = dict(os.environ)
    env.update({key: str(value) for key, value in group.get("env", {}).items()})
    # Dependency/path truth: a manifest may declare a path-list value such as
    # PYTHONPATH='src:scripts' in module-relative form. Relative entries drift
    # with the launching step's working directory (the 2026-09-25 masking
    # class of bug); expand them against this group's working_dir into
    # absolute paths, joined with the platform path separator, so the
    # environment is pinned regardless of which step launched the runner.
    # Absolute entries pass through unchanged; non-path-like values (no ':'
    # or ';' separator) pass through unchanged.
    for key, value in dict(group.get("env", {})).items():
        text = str(value)
        if ":" not in text and ";" not in text:
            continue
        if text and text[0] not in "./" and Path(text).is_absolute():
            continue
        segments = [s for s in re.split(r"[:;]", text) if s.strip()]
        if len(segments) < 2:
            continue
        expanded = []
        for segment in segments:
            segment = segment.strip()
            if not Path(segment).is_absolute():
                segment = str((cwd / segment).resolve())
            expanded.append(segment)
        if expanded:
            env[key] = os.pathsep.join(expanded)

    print(f"FAILFAST_GROUP_START group={args.group} commands={len(commands)} cwd={cwd}")
    for index, argv in enumerate(commands, start=1):
        try:
            argv = resolve_executable(argv)
        except SystemExit:
            return 127
        proc = subprocess.run(argv, cwd=str(cwd), env=env)
        print(f"FAILFAST_GROUP_CMD group={args.group} {index}/{len(commands)} exit={proc.returncode} :: {' '.join(argv)}")
        if proc.returncode != 0:
            skipped = len(commands) - index
            print(f"FAILFAST_GROUP_FAIL group={args.group} failed_cmd={index} exit={proc.returncode} skipped={skipped}")
            return proc.returncode if proc.returncode > 0 else 1
    print(f"FAILFAST_GROUP_PASS group={args.group} commands={len(commands)} all_exit_0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
