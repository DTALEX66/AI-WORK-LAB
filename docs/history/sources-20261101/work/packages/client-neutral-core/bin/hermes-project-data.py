#!/usr/bin/env python
"""Fail-closed project-local runtime-data boundary for agent task commands.

The wrapper scopes standard temporary, cache, log, artifact, pip, and Python
bytecode paths to a git-ignored project-local runtime root. It intentionally
cannot sandbox a command that explicitly writes an arbitrary absolute path;
callers must use this wrapper and project rules must deny external output paths.

Root selection (WL-010/020/030 Runtime Boundary V2):
- Prefer ``.project-local/`` when it is git-ignored in the project.
- Fall back to ``.hermes/`` (legacy root) when ``.project-local/`` is NOT
  git-ignored, so existing projects keep working without a .gitignore change.
- Fail closed when neither root is git-ignored.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Mapping, Sequence


WINDOWS_REPARSE_POINT = 0x400
# Ceiling on a Git *metadata* answer, not on a user command. Every wrapper call makes these lookups, so an
# unbounded one puts the whole pre-tool hook behind a locked index or a credential prompt; 5s is far above the
# measured p95 (see tests/workflow-assistance/test_hooks_answer_within_a_bound_without_waking_a_model.py), so
# hitting it means Git is stuck rather than slow.
GIT_METADATA_TIMEOUT_SECONDS = 5.0


class ProjectDataBoundaryError(RuntimeError):
    """Raised when task runtime data cannot be safely contained."""


class RuntimeLayout:
    def __init__(self, project_root: Path, paths: dict[str, Path], env: dict[str, str]) -> None:
        self.project_root = project_root
        self.paths = paths
        self.env = env


def discover_project_root(start: Path | str = ".", *, timeout: float = GIT_METADATA_TIMEOUT_SECONDS) -> Path:
    """Ask Git where the project is, and refuse to guess when it does not answer.

    This runs on every wrapper call, so an unbounded ``git`` call would put the whole hook behind whatever
    the repository is doing (locked index, credential prompt, a huge working tree). A timeout is not a
    "not a project" verdict either: the two reasons are reported apart, because a caller that reads "not
    inside a Git project" from a stall would go looking for a defect that is not there.
    """
    start_path = Path(start).resolve()
    try:
        result = subprocess.run(
            ["git", "-C", str(start_path), "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True, encoding="utf-8", errors="replace",
            check=False, timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        raise ProjectDataBoundaryError(
            f"git rev-parse did not answer within {timeout:g}s for {start_path}; "
            "the project root is unresolved, which is not the same as absent"
        ) from exc
    if result.returncode:
        raise ProjectDataBoundaryError(f"not inside a Git project: {start_path}")
    return Path(result.stdout.strip()).resolve()


def require_contained(project_root: Path, candidate: Path) -> Path:
    root = project_root.resolve()
    _reject_reparse_components(root, candidate)
    resolved = candidate.resolve(strict=False)
    if not resolved.is_relative_to(root):
        raise ProjectDataBoundaryError(f"path escapes project root: {candidate}")
    return resolved


def _reject_reparse_components(root: Path, candidate: Path) -> None:
    """Reject junctions/reparse points before ``Path.resolve`` can follow them."""
    try:
        relative = candidate.absolute().relative_to(root.absolute())
    except ValueError as exc:
        raise ProjectDataBoundaryError(f"path escapes project root: {candidate}") from exc
    current = root
    for component in relative.parts:
        current /= component
        if not current.exists():
            continue
        try:
            attributes = getattr(current.stat(), "st_file_attributes", 0)
        except OSError as exc:
            raise ProjectDataBoundaryError(f"cannot inspect project path: {current}") from exc
        if attributes & WINDOWS_REPARSE_POINT:
            raise ProjectDataBoundaryError(
                f"reparse point is forbidden in project runtime path: {current}"
            )


def is_git_ignored(project_root: Path, relative_path: Path,
                   *, timeout: float = GIT_METADATA_TIMEOUT_SECONDS) -> bool:
    """Whether Git ignores this path. A timeout raises: "unproven" must not read as "not ignored".

    The caller's rule is that a runtime root has to be ignored *before* it is used, so returning False here on
    a stalled ``git`` would let an unignored directory through the boundary check -- the failure mode this
    whole wrapper exists to prevent.
    """
    try:
        result = subprocess.run(
            ["git", "-C", str(project_root), "check-ignore", "-q", "--no-index", relative_path.as_posix()],
            capture_output=True,
            text=True, encoding="utf-8", errors="replace",
            check=False, timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        raise ProjectDataBoundaryError(
            f"git check-ignore did not answer within {timeout:g}s for {relative_path.as_posix()}; "
            "ignore status is unproven, so the path is not usable as a runtime root"
        ) from exc
    return result.returncode == 0


def require_ignored(project_root: Path, relative_path: Path) -> None:
    if not is_git_ignored(project_root, relative_path):
        raise ProjectDataBoundaryError(
            f"project runtime root must be git-ignored before use: {relative_path.as_posix()}"
        )


def _select_runtime_root(project_root: Path) -> tuple[Path, str]:
    """Choose the git-ignored runtime root. Prefer .project-local, fall back to .hermes.

    Returns (runtime_root, root_name) where root_name is "project-local" or "hermes".
    """
    candidates = [
        ("project-local", project_root / ".project-local"),
        ("hermes", project_root / ".hermes"),
    ]
    for root_name, candidate in candidates:
        if is_git_ignored(project_root, candidate / "runs" if root_name == "project-local" else candidate / "task-runtime"):
            return candidate, root_name
    # Neither is ignored — fail closed
    raise ProjectDataBoundaryError(
        "project runtime root must be git-ignored before use: add `.project-local/` or `.hermes/` to .gitignore"
    )


def prepare_layout(start: Path | str = ".") -> RuntimeLayout:
    project_root = discover_project_root(start)
    root_base, root_name = _select_runtime_root(project_root)

    if root_name == "project-local":
        runtime_root = require_contained(project_root, root_base / "runs")
        require_ignored(project_root, (runtime_root / ".containment-probe").relative_to(project_root))
        paths = {
            "root": runtime_root,
            "tmp": runtime_root / "tmp",
            "cache": runtime_root / "cache",
            "logs": runtime_root / "logs",
            "artifacts": root_base / "artifacts",
            "pip-cache": runtime_root / "pip-cache",
            "pycache": runtime_root / "pycache",
        }
        kanban_home = root_base / "kanban"
    else:  # hermes (legacy fallback)
        runtime_root = require_contained(project_root, root_base / "task-runtime")
        require_ignored(project_root, (runtime_root / ".containment-probe").relative_to(project_root))
        paths = {
            "root": runtime_root,
            "tmp": runtime_root / "tmp",
            "cache": runtime_root / "cache",
            "logs": runtime_root / "logs",
            "artifacts": root_base / "task-artifacts",
            "pip-cache": runtime_root / "pip-cache",
            "pycache": runtime_root / "pycache",
        }
        kanban_home = root_base

    for path in paths.values():
        require_contained(project_root, path)
        path.mkdir(parents=True, exist_ok=True)
    env = {
        "TMP": str(paths["tmp"]),
        "TEMP": str(paths["tmp"]),
        "TMPDIR": str(paths["tmp"]),
        "XDG_CACHE_HOME": str(paths["cache"]),
        "PIP_CACHE_DIR": str(paths["pip-cache"]),
        "PYTHONPYCACHEPREFIX": str(paths["pycache"]),
        "UV_CACHE_DIR": str(paths["cache"] / "uv"),
        "NPM_CONFIG_CACHE": str(paths["cache"] / "npm"),
        "npm_config_cache": str(paths["cache"] / "npm"),
        "YARN_CACHE_FOLDER": str(paths["cache"] / "yarn"),
        "PLAYWRIGHT_BROWSERS_PATH": str(paths["cache"] / "playwright-browsers"),
        "RUSTUP_HOME": str(paths["cache"] / "rustup"),
        "CARGO_HOME": str(paths["cache"] / "cargo"),
        "CARGO_TARGET_DIR": str(paths["cache"] / "cargo-target"),
        "MYPY_CACHE_DIR": str(paths["cache"] / "mypy"),
        "RUFF_CACHE_DIR": str(paths["cache"] / "ruff"),
        "PRE_COMMIT_HOME": str(paths["cache"] / "pre-commit"),
        "HERMES_KANBAN_HOME": str(kanban_home),
        "HERMES_PROJECT_RUNTIME_ROOT": str(paths["root"]),
        "HERMES_PROJECT_ARTIFACTS": str(paths["artifacts"]),
        "HERMES_PROJECT_LOGS": str(paths["logs"]),
    }
    return RuntimeLayout(project_root, paths, env)


def write_task_data_policy(layout: RuntimeLayout) -> Path:
    """Write an ignored, project-local policy without touching source files."""
    # Determine which root was selected by checking which base exists under the runtime root
    runtime_root = layout.paths["root"]
    # .project-local/runs → root base is parent.parent; .hermes/task-runtime → parent
    if runtime_root.parent.name == "runs" and runtime_root.parent.parent.name == ".project-local":
        policy_path = layout.project_root / ".project-local" / "TASK_DATA_POLICY.md"
        content = """# Project-local task data policy (WL-010/020/030)

All task-scoped state belongs under this repository's `.project-local/` directory.

## Required locations

- queues and durable task state: `.project-local/tasks/` or `.project-local/sleep-mode/`
- plans and handoffs: `.project-local/plans/` and `.project-local/handoffs/`
- temporary command data: `.project-local/runs/`
- durable verification evidence: `.project-local/artifacts/` or `.project-local/evidence/`
- Hermes project board: `.project-local/kanban/` (run through `hermes-project-data.py kanban`)

## Required launcher

Use `hermes-project-data.py --project . run -- <command>` for commands that can
write caches, logs, downloads, test output, or artifacts. It redirects temporary
and common tool caches to `.project-local/runs/` and pins `HERMES_KANBAN_HOME`
to this project.

## Prohibited locations

Do not create project task caches, reports, scratch files, Kanban boards, or
review artifacts under the user home, Windows temporary directories, Desktop,
another project, or the global Hermes home. Hermes credentials, installation,
global session database, and scheduler configuration remain global platform state.

## Cleanup

Remove confirmed regenerable files from `.project-local/runs/`; retain only
durable handoffs, task records, and evidence required for audit or recovery.
"""
    else:
        policy_path = layout.project_root / ".hermes" / "TASK_DATA_POLICY.md"
        content = """# Project-local task data policy

All task-scoped state belongs under this repository's `.hermes/` directory.

## Required locations

- queues and durable task state: `.hermes/tasks/` or `.hermes/sleep-mode/`
- plans and handoffs: `.hermes/plans/` and `.hermes/handoffs/`
- temporary command data: `.hermes/task-runtime/`
- durable verification evidence: `.hermes/task-artifacts/` or `.hermes/evidence/`
- Hermes project board: `.hermes/kanban/` (run through `hermes-project-data.py kanban`)

## Required launcher

Use `hermes-project-data.py --project . run -- <command>` for commands that can
write caches, logs, downloads, test output, or artifacts. It redirects temporary
and common tool caches to `.hermes/task-runtime/` and pins `HERMES_KANBAN_HOME`
to this project.

## Prohibited locations

Do not create project task caches, reports, scratch files, Kanban boards, or
review artifacts under the user home, Windows temporary directories, Desktop,
another project, or the global Hermes home. Hermes credentials, installation,
global session database, and scheduler configuration remain global platform state.

## Cleanup

Remove confirmed regenerable files from `.hermes/task-runtime/`; retain only
durable handoffs, task records, and evidence required for audit or recovery.
"""
    require_contained(layout.project_root, policy_path)
    policy_path.write_text(content, encoding="utf-8")
    return policy_path


def prepare_command(
    layout: RuntimeLayout,
    command: Sequence[str],
    *,
    windows: bool | None = None,
    limit: int = 30_000,
) -> list[str]:
    """Keep known long Python inline commands below Windows CreateProcess limits.

    Generic executables have incompatible response-file syntaxes, so they fail
    closed with actionable guidance rather than silently retrying a broken command.
    """

    prepared = list(command)
    if not prepared:
        raise ProjectDataBoundaryError("run requires a command after --")
    on_windows = os.name == "nt" if windows is None else windows
    if not on_windows or len(subprocess.list2cmdline(prepared)) <= limit:
        return prepared
    executable = Path(prepared[0]).name.lower()
    if len(prepared) >= 3 and prepared[1] == "-c" and executable.startswith("python"):
        source = prepared[2]
        digest = hashlib.sha256(source.encode("utf-8")).hexdigest()[:16]
        script = layout.paths["tmp"] / f"inline-command-{digest}.py"
        require_contained(layout.project_root, script)
        script.write_text(source, encoding="utf-8")
        return [prepared[0], str(script), *prepared[3:]]
    # Dynamic message: refer to the actual runtime root
    runtime_root = layout.paths["root"]
    raise ProjectDataBoundaryError(
        "Windows command line exceeds safe limit; use the tool's response file/input-file option "
        f"or place the payload under {runtime_root}"
    )


def run_command(
    layout: RuntimeLayout,
    command: Sequence[str],
    *,
    windows: bool | None = None,
    limit: int = 30_000,
) -> subprocess.CompletedProcess[str]:
    prepared = prepare_command(layout, command, windows=windows, limit=limit)
    env = os.environ.copy()
    env.update(layout.env)
    return subprocess.run(
        prepared,
        cwd=layout.project_root,
        env=env,
        capture_output=True,
        text=True, encoding="utf-8", errors="replace",
        check=False,
    )


def run_kanban_command(layout: RuntimeLayout, command: Sequence[str]) -> subprocess.CompletedProcess[str]:
    """Run the native Kanban CLI with its board root pinned to this project."""
    if not command:
        raise ProjectDataBoundaryError(
            "kanban requires arguments after --, for example: -- boards list"
        )
    hermes = shutil.which("hermes")
    if hermes is None:
        raise ProjectDataBoundaryError("native Hermes CLI is not available on PATH")
    env = os.environ.copy()
    env.update(layout.env)
    return subprocess.run(
        [hermes, "kanban", *command],
        cwd=layout.project_root,
        env=env,
        capture_output=True,
        text=True, encoding="utf-8", errors="replace",
        check=False,
    )


def cleanup_runtime(layout: RuntimeLayout, *, include_caches: bool = False) -> dict[str, int]:
    """Remove only confirmed-regenerable project-local runtime data.

    Durable handoffs and verification evidence belong in the artifacts dir
    and are intentionally outside this cleanup scope. By default dependency caches
    stay available for the next task; callers may explicitly include them.
    """
    names = ["tmp", "logs", "artifacts", "pycache"]
    if include_caches:
        names.extend(["cache", "pip-cache"])
    removed: dict[str, int] = {}
    for name in names:
        result = cleanup_runtime_path(layout, name)
        removed[name] = int(result["bytes"])
        path = layout.paths[name]
        path.mkdir(parents=True, exist_ok=True)
    return removed


def cleanup_runtime_path(layout: RuntimeLayout, relative_path: str) -> dict[str, object]:
    """Remove one exact path below the runtime root and verify absence.

    The path is relative by contract so a caller cannot turn an audit cleanup
    into an arbitrary filesystem delete. Permission/lock failures remain
    blockers; this function never elevates, changes ACLs, kills processes, or
    retries a destructive operation blindly.
    """
    raw = Path(relative_path)
    if not relative_path or raw.is_absolute() or raw.anchor:
        raise ProjectDataBoundaryError(
            f"cleanup-path requires a relative runtime path: {relative_path!r}"
        )
    runtime_root = layout.paths["root"].resolve()
    target = require_contained(layout.project_root, runtime_root / raw)
    if target == runtime_root or not target.is_relative_to(runtime_root):
        raise ProjectDataBoundaryError(
            f"cleanup-path requires a relative runtime path below the runtime root: {relative_path!r}"
        )
    if not target.exists():
        return {"target": relative_path, "bytes": 0, "status": "ABSENT"}
    try:
        size = sum(item.stat().st_size for item in target.rglob("*") if item.is_file())
        if target.is_dir():
            shutil.rmtree(target)
        else:
            size = target.stat().st_size
            target.unlink()
    except OSError as exc:
        raise ProjectDataBoundaryError(
            "BLOCKED_RUNTIME_CLEANUP "
            f"target={relative_path!r}; inspect lock, ACL, or process ownership; "
            "do not elevate or retry recursively without a new diagnosis"
        ) from exc
    if target.exists():
        raise ProjectDataBoundaryError(
            f"cleanup postcondition failed; target still exists: {relative_path!r}"
        )
    return {"target": relative_path, "bytes": size, "status": "REMOVED"}


def layout_payload(layout: RuntimeLayout) -> Mapping[str, object]:
    return {
        "project_root": str(layout.project_root),
        "runtime_root": str(layout.paths["root"]),
        "paths": {name: str(path) for name, path in layout.paths.items()},
        "environment": layout.env,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", default=".", help="any path inside the target Git project")
    parser.add_argument("--json", action="store_true", help="emit the contained layout as JSON")
    subparsers = parser.add_subparsers(dest="command", required=True)
    for name in ("init", "check", "policy", "cleanup"):
        subparsers.add_parser(name, help="prepare/verify the project-local runtime root")
    subparsers.choices["cleanup"].add_argument(
        "--all-regenerable",
        action="store_true",
        help="also remove dependency/tool caches under the runtime root",
    )
    cleanup_path_parser = subparsers.add_parser(
        "cleanup-path",
        help="remove one exact relative path below the runtime root",
    )
    cleanup_path_parser.add_argument(
        "target",
        help="relative path below the runtime root; absolute and parent paths are rejected",
    )
    run_parser = subparsers.add_parser("run", help="run a command with local temporary/cache paths")
    run_parser.add_argument("args", nargs=argparse.REMAINDER, help="command to run; prefix with --")
    kanban_parser = subparsers.add_parser("kanban", help="run Hermes Kanban with project-local board storage")
    kanban_parser.add_argument("args", nargs=argparse.REMAINDER, help="Kanban arguments; prefix with --")
    args = parser.parse_args()
    try:
        layout = prepare_layout(args.project)
        if args.command == "init":
            write_task_data_policy(layout)
        if args.command in {"init", "check"}:
            payload = layout_payload(layout)
            print(json.dumps(payload, ensure_ascii=False, indent=2) if args.json else payload["runtime_root"])
            return 0
        if args.command == "policy":
            print(write_task_data_policy(layout))
            return 0
        if args.command == "cleanup":
            print(json.dumps(cleanup_runtime(layout, include_caches=args.all_regenerable), ensure_ascii=False))
            return 0
        if args.command == "cleanup-path":
            print(json.dumps(cleanup_runtime_path(layout, args.target), ensure_ascii=False))
            return 0
        command = args.args[1:] if args.args[:1] == ["--"] else args.args
        result = run_kanban_command(layout, command) if args.command == "kanban" else run_command(layout, command)
        if result.stdout:
            print(result.stdout, end="")
        if result.stderr:
            print(result.stderr, end="", file=sys.stderr)
        return result.returncode
    except ProjectDataBoundaryError as exc:
        print(f"project-data-boundary: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())