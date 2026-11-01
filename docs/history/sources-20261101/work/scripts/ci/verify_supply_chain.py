#!/usr/bin/env python3
"""Verify source-pinned GitHub Actions and safe dependency-source metadata."""
from __future__ import annotations

import os
import re
import shlex
from pathlib import Path

ACTION_RE = re.compile(r"^\s*-?\s*uses:\s*([^\s#]+)(?:\s+#\s*(v[^\s]+))?\s*$")
PINNED_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+@[0-9a-f]{40}$")
UNSAFE_PIPE_RE = re.compile(r"(?:curl|wget)[^\n|]*\|\s*(?:sh|bash)\b", re.IGNORECASE)
PIP_INSTALL_RE = re.compile(
    r"(?<![A-Za-z0-9_.-])(?:python(?:3(?:\.\d+)?)?\s+-m\s+pip|pip(?:3(?:\.\d+)?)?)\s+install\b"
)
PIP_LAUNCHER_RE = re.compile(r"^(?:python(?:3(?:\.\d+)?)?|pip(?:3(?:\.\d+)?)?)$")
SHELL_COMMAND_SEPARATOR_RE = re.compile(r"(?:&&|\|\||[;|])")
REQUIREMENTS_LOCK_REL = Path("packages/client-neutral-core/requirements.lock")


def verify(root: Path) -> list[str]:
    errors: list[str] = []
    requirements_lock = root / REQUIREMENTS_LOCK_REL
    if not requirements_lock.is_file():
        errors.append(f"missing hash-locked Python requirements: {REQUIREMENTS_LOCK_REL}")
    else:
        lock_text = requirements_lock.read_text(encoding="utf-8")
        if "--hash=sha256:" not in lock_text:
            errors.append(f"Python requirements lock has no hashes: {REQUIREMENTS_LOCK_REL}")
    workflows = _workflow_files(root)
    if not workflows:
        return ["no GitHub workflow files found"]
    action_count = 0
    for workflow in workflows:
        text = workflow.read_text(encoding="utf-8")
        if UNSAFE_PIPE_RE.search(text):
            errors.append(f"{workflow}: network installer pipe is forbidden")
        for line_number, command_line in _logical_shell_lines(text):
            # Validate every shell command rather than the whole YAML line: a safe
            # install followed by `; pip install -r unpinned.txt` must fail closed.
            for command in SHELL_COMMAND_SEPARATOR_RE.split(command_line):
                try:
                    tokens = shlex.split(command, comments=True, posix=True)
                except ValueError:
                    # A malformed shell command cannot be safely normalized. Keep
                    # the conservative fallback only for that parse-error case;
                    # otherwise comments and quoted data must not look executable.
                    if PIP_INSTALL_RE.search(command):
                        errors.append(
                            f"{workflow}:{line_number}: malformed Python installation command"
                        )
                    continue
                if _contains_indirect_install(tokens):
                    errors.append(
                        f"{workflow}:{line_number}: indirect installation command is forbidden"
                    )
                    continue
                if _contains_dynamic_shell_pip_install(command, tokens):
                    errors.append(
                        f"{workflow}:{line_number}: dynamically interpreted Python installation is forbidden"
                    )
                    continue
                if not _contains_pip_install(tokens):
                    continue
                if not _is_approved_pip_install(tokens):
                    errors.append(
                        f"{workflow}:{line_number}: Python installation must use --require-hashes and {REQUIREMENTS_LOCK_REL.as_posix()}"
                    )
        for line_number, line in enumerate(text.splitlines(), 1):
            if "uses:" not in line:
                continue
            match = ACTION_RE.match(line)
            if not match:
                errors.append(f"{workflow}:{line_number}: malformed uses metadata")
                continue
            action, version = match.groups()
            if not PINNED_RE.fullmatch(action):
                errors.append(f"{workflow}:{line_number}: action must use a full commit SHA: {action}")
            if not version or not version.startswith("v"):
                errors.append(f"{workflow}:{line_number}: pinned action needs a version comment")
            action_count += 1
    return errors if errors else []


def _logical_shell_lines(text: str) -> list[tuple[int, str]]:
    """Join shell backslash continuations before inspecting pip invocations."""
    logical_lines: list[tuple[int, str]] = []
    pending = ""
    start_line = 0
    for line_number, line in enumerate(text.splitlines(), 1):
        stripped = line.rstrip()
        if not pending:
            start_line = line_number
        if stripped.endswith("\\"):
            # POSIX shells remove a backslash-newline pair without inserting a
            # separator, so preserve any authored whitespace but add none.
            pending += stripped[:-1]
            continue
        logical_lines.append((start_line, pending + line.lstrip() if pending else line))
        pending = ""
    if pending:
        logical_lines.append((start_line, pending))
    return logical_lines


def _is_approved_pip_install(tokens: list[str]) -> bool:
    """Accept only an actual hash flag plus the one reviewed requirements lock."""
    if "--require-hashes" not in tokens:
        return False

    required_path = REQUIREMENTS_LOCK_REL.as_posix()
    requirement_paths: list[str] = []
    for index, token in enumerate(tokens):
        if token in {"-r", "--requirement"}:
            if index + 1 >= len(tokens):
                return False
            requirement_paths.append(tokens[index + 1])
        elif token.startswith("--requirement=") and token.removeprefix("--requirement=") == required_path:
            requirement_paths.append(required_path)
        elif token.startswith("--requirement="):
            requirement_paths.append(token.removeprefix("--requirement="))
        elif token.startswith("-r") and token != "-r":
            requirement_paths.append(token[2:])
    return requirement_paths == [required_path]


def _contains_pip_install(tokens: list[str]) -> bool:
    """Recognize shell-normalized pip launchers, including escaped/quoted spelling."""
    for index, token in enumerate(tokens):
        if not PIP_LAUNCHER_RE.fullmatch(token):
            continue
        if token.startswith("pip"):
            if tokens[index + 1:index + 2] == ["install"]:
                return True
        elif tokens[index + 1:index + 4] == ["-m", "pip", "install"]:
            return True
    return False


def _contains_indirect_install(tokens: list[str]) -> bool:
    """Fail closed when a shell expansion selects an install command at runtime."""
    return any(
        token.startswith("$") and tokens[index + 1:index + 2] == ["install"]
        for index, token in enumerate(tokens)
    )


def _contains_dynamic_shell_pip_install(command: str, tokens: list[str]) -> bool:
    """Reject pip installs hidden in shell re-evaluation or command substitution.

    The verifier supports only direct shell invocations.  Re-evaluating a string
    with ``sh -c``/``bash -c`` or executing ``$(...)`` changes the command graph
    after tokenization, so any embedded pip install is deliberately fail-closed.
    """
    normalized = PIP_INSTALL_RE.search(command)
    if not normalized:
        return False
    return "$(" in command or any(
        token in {"sh", "bash"} and tokens[index + 1:index + 2] == ["-c"]
        for index, token in enumerate(tokens)
    )


def main() -> int:
    root = Path(__file__).resolve().parents[2]
    errors = verify(root)
    if errors:
        for error in errors:
            print(f"SUPPLY_CHAIN_FAIL {error}")
        return 1
    workflows = len(_workflow_files(root))
    actions = sum(
        1
        for workflow in _workflow_files(root)
        for line in workflow.read_text(encoding="utf-8").splitlines()
        if "uses:" in line
    )
    print(f"SUPPLY_CHAIN_PASS workflows={workflows} actions={actions} source=pinned-sha")
    return 0


def _workflow_files(root: Path) -> list[Path]:
    """Discover every project workflow while excluding Git and ignored runtime trees."""
    excluded = {".git", ".hermes", ".project-local", "node_modules"}
    found: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root):
        # Prune excluded trees before descending (avoids long-path scandir errors).
        dirnames[:] = [d for d in dirnames if d not in excluded]
        if dirpath == str(root):
            continue
        rel = Path(dirpath).relative_to(root)
        if rel.name == "workflows" and rel.parent.name == ".github":
            for fn in filenames:
                if fn.endswith((".yml", ".yaml")):
                    found.append(Path(dirpath) / fn)
    return sorted(found)


if __name__ == "__main__":
    raise SystemExit(main())
