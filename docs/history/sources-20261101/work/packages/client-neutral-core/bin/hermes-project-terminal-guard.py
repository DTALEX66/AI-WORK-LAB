#!/usr/bin/env python
"""Fail-closed Hermes pre-tool hook for project-scoped terminal execution.

The hook receives Hermes' JSON hook payload on stdin and only permits the
``terminal`` tool when the call declares a Git-project workdir and invokes the
installed ``hermes-project-data.py`` wrapper for that same workdir.  It is a
policy gate for normal Hermes tool calls, not an operating-system sandbox:
processes deliberately launched outside Hermes or programs that write hard-
coded absolute paths can still escape OS-level containment.
"""
from __future__ import annotations

import json
import ntpath
import os
import re
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any


BLOCK_PREFIX = "PROJECT DATA BOUNDARY BLOCKED:"
ABSOLUTE_PATH = re.compile(
    r"(?:(?:[A-Za-z]:[\\/](?!/))|(?:\\\\[^\s\"']+)|(?:^|(?<=[\s\"'=<>:([{]))/(?!/))[^\s\"']+"
)
RAW_UNC_PATH = re.compile(r"(?:^|(?<=[\s\"'=]))(\\\\[^\s\"']+)")
RAW_WINDOWS_ABSOLUTE_PATH = re.compile(
    r"(?:^|(?<=[\s\"'=<>:([{]))([A-Za-z]:[\\/](?!/)[^\s\"']+)"
)
RAW_POSIX_ABSOLUTE_PATH = re.compile(
    r"(?:^|(?<=[\s\"'=<>:([{]))(/(?!/)[^\s\"']+)"
)
RAW_PARENT_TRAVERSAL = re.compile(
    r"(?:^|(?<=[\s\"'=<>:([{/\\]))\.\.(?:[\\/]|(?=[\s\"'/\\]|$))"
)
RAW_RUN_SEPARATOR = re.compile(r"(?:^|\s)run\s+--\s+")

WRAPPER_NAME = "hermes-project-data.py"
# Ceiling on the guard's one Git lookup. This hook runs before *every* terminal tool call, so an unbounded
# git call would let a locked index or a credential prompt stall the whole client; the number sits far above
# the measured p95 recorded by
# tests/workflow-assistance/test_hooks_answer_within_a_bound_without_waking_a_model.py.
ROOT_CHECK_TIMEOUT_SECONDS = 5.0


class RootCheckUnresolved(RuntimeError):
    """Git did not answer. Refuse the call, and say that -- not "this is not a Git project"."""
SUBCOMMANDS = {"init", "check", "policy", "cleanup", "run", "kanban"}
LEGACY_EXTERNAL_SPILL_ROOTS = ("d:/a", "d:/d", "d:/dev", "d:/tmp")


def canonical_wrapper(raw: str) -> bool:
    normalized = raw.replace("\\", "/")
    if normalized in {"$HERMES_HOME/bin/hermes-project-data.py", "${HERMES_HOME}/bin/hermes-project-data.py"}:
        return True
    candidate = Path(raw).expanduser()
    if not candidate.is_absolute():
        return False
    home = os.environ.get("HERMES_HOME")
    if home:
        expected = (Path(home) / "bin" / WRAPPER_NAME).resolve()
        try:
            return candidate.resolve(strict=True) == expected
        except (OSError, RuntimeError):
            return False
    return False


def _quoted_full_path(text: str, start: int, end: int) -> str | None:
    """Recover a full quoted absolute path truncated by the regex.

    When text[start:end) is preceded by a quote, find the matching closing
    quote and return the complete path (spaces preserved). A path may also be
    matched twice by the regex (Windows drive branch + POSIX branch of the
    same C:/... path), so when the fragment does not directly follow a quote
    we scan backward for the enclosing opening quote. Returns None when no
    enclosing quote exists — unrecoverable, callers fail closed (BLOCK).
    """
    if start > 0 and text[start - 1] in ("'", '"'):
        quote = text[start - 1]
        close = text.find(quote, end)
        if close == -1:
            return None
        return text[start:close]
    for index in range(start - 1, -1, -1):
        if text[index] in ("'", '"'):
            quote = text[index]
            close = text.find(quote, end)
            if close == -1:
                return None
            return text[index + 1 : close]
    return None


def external_child_path(argv: list[str], separator_index: int, root: Path) -> str | None:
    """Reject explicit child paths outside the declared Git project."""
    child = argv[separator_index + 1 :]
    for token in child:
        raw_token = token.strip('"\'')
        path_token = Path(raw_token)
        if path_token.is_absolute() or ntpath.isabs(raw_token):
            if os.name != "nt" and ntpath.isabs(raw_token) and not path_token.is_absolute():
                return raw_token
            try:
                if not path_token.resolve(strict=False).is_relative_to(root):
                    return raw_token
            except (OSError, RuntimeError):
                return raw_token
            continue
        for match in ABSOLUTE_PATH.finditer(token):
            candidate = match.group(0)
            raw = candidate.strip('"\'')
            path = Path(raw)
            windows_absolute = ntpath.isabs(raw)
            if not (path.is_absolute() or windows_absolute):
                continue
            if os.name != "nt" and windows_absolute and not path.is_absolute():
                return candidate
            try:
                resolved = path.resolve(strict=False)
                root_str = ntpath.normcase(ntpath.normpath(str(root)))
                res_str = ntpath.normcase(ntpath.normpath(str(resolved)))
                if root_str.startswith(res_str):
                    # P0-8: a character prefix is BOTH a truncated space-path
                    # and an external sibling/ancestor path — indistinguishable
                    # at fragment level. Recover the full quoted path and
                    # decide precisely; unrecoverable -> fail closed.
                    full = _quoted_full_path(token, match.start(), match.end())
                    if full is None:
                        if not resolved.is_relative_to(root):
                            return candidate
                        continue
                    try:
                        full_resolved = Path(full).resolve(strict=False)
                    except (OSError, RuntimeError):
                        return candidate
                    if not full_resolved.is_relative_to(root):
                        return full
                    continue
                if not resolved.is_relative_to(root):
                    return candidate
            except (OSError, RuntimeError):
                return candidate
    return None


def external_raw_unc(command: str, root: Path) -> str | None:
    """Check UNC paths before POSIX shlex parsing can strip backslashes."""
    for index in range(len(command) - 1):
        if command[index : index + 2] != "\\\\":
            continue
        end = index + 2
        while end < len(command) and command[end] not in " \t\"'":
            end += 1
        candidate = command[index:end]
        if os.name != "nt":
            return candidate
        raw = ntpath.normcase(ntpath.normpath(candidate))
        project = ntpath.normcase(ntpath.normpath(str(root)))
        if project.startswith(raw):
            # P0-8: character prefix is ambiguous (truncated space-path vs
            # external sibling). Recover the full quoted path; else fail closed.
            full = _quoted_full_path(command, index, end)
            if full is None:
                return candidate
            full_raw = ntpath.normcase(ntpath.normpath(full))
            if full_raw != project and not full_raw.startswith(project.rstrip("\\") + "\\"):
                return full
            continue
        if raw != project and not raw.startswith(project.rstrip("\\") + "\\"):
            return candidate
    return None


def external_raw_windows_path(command: str, root: Path) -> str | None:
    """Check drive-qualified paths before POSIX shlex can strip backslashes."""
    for match in RAW_WINDOWS_ABSOLUTE_PATH.finditer(command):
        candidate = match.group(1)
        if os.name != "nt":
            return candidate
        raw = ntpath.normcase(ntpath.normpath(candidate))
        project = ntpath.normcase(ntpath.normpath(str(root)))
        if project.startswith(raw):
            # P0-8: recover the full quoted path; unrecoverable -> fail closed.
            full = _quoted_full_path(command, match.start(), match.end())
            if full is None:
                return candidate
            full_raw = ntpath.normcase(ntpath.normpath(full))
            if full_raw != project and not full_raw.startswith(project.rstrip("\\") + "\\"):
                return full
            continue
        if raw != project and not raw.startswith(project.rstrip("\\") + "\\"):
            return candidate
    return None


def external_raw_posix_path(command: str, root: Path) -> str | None:
    """Check rooted POSIX paths before Windows ``Path`` resolution changes them."""
    for match in RAW_POSIX_ABSOLUTE_PATH.finditer(command):
        candidate = match.group(1)
        if os.name == "nt":
            drive = root.drive or Path.cwd().drive
            path = Path(f"{drive}{candidate}")
        else:
            path = Path(candidate)
        try:
            resolved = path.resolve(strict=False)
            root_str = ntpath.normcase(ntpath.normpath(str(root)))
            res_str = ntpath.normcase(ntpath.normpath(str(resolved)))
            if root_str.startswith(res_str):
                # P0-8: recover the full quoted POSIX path; unrecoverable ->
                # fail closed. On Windows, POSIX paths (e.g. MSYS /tmp/...)
                # cannot be reliably drive-mapped, so compare normalized text
                # with a separator boundary instead of resolving.
                full = _quoted_full_path(command, match.start(), match.end())
                if full is None:
                    if not resolved.is_relative_to(root):
                        return candidate
                    continue
                if os.name == "nt":
                    full_norm = ntpath.normcase(ntpath.normpath(full.replace("/", "\\")))
                    root_norm = ntpath.normcase(ntpath.normpath(str(root).replace("/", "\\")))
                    if full_norm != root_norm and not full_norm.startswith(root_norm.rstrip("\\") + "\\"):
                        return full
                    continue
                try:
                    full_resolved = Path(full).resolve(strict=False)
                except (OSError, RuntimeError):
                    return candidate
                if not full_resolved.is_relative_to(root):
                    return full
                continue
            if not resolved.is_relative_to(root):
                return candidate
        except (OSError, RuntimeError):
            return candidate
    return None


def external_spill_path_needing_project_redirect(command: str) -> str | None:
    """Catch explicit legacy spill paths that bypass project env injection."""
    for match in RAW_WINDOWS_ABSOLUTE_PATH.finditer(command):
        candidate = ntpath.normcase(ntpath.normpath(match.group(1))).replace("\\", "/")
        if any(
            candidate == root or candidate.startswith(root + "/")
            for root in LEGACY_EXTERNAL_SPILL_ROOTS
        ):
            return match.group(1)
    return None


def has_raw_parent_traversal(command: str) -> bool:
    """Reject path traversal in the shell source before argument parsing."""
    return RAW_PARENT_TRAVERSAL.search(command) is not None


def has_shell_control(command: str) -> bool:
    """Detect shell control operators only when they are not shell-quoted."""
    quote: str | None = None
    escaped = False
    for char in command:
        if char in {"\n", "\r"}:
            return True
        if escaped:
            escaped = False
            continue
        if char == "\\" and quote != "'":
            escaped = True
            continue
        if char in {"'", '"'}:
            quote = None if quote == char else char if quote is None else quote
            continue
        if quote is None and char in {";", "|", "&", "<", ">"}:
            return True
    return False


def has_shell_expansion(command: str) -> bool:
    """Reject child shell expansions while permitting literal single-quoted text."""
    quote: str | None = None
    escaped = False
    for char in command:
        if escaped:
            escaped = False
            continue
        if char == "\\" and quote != "'":
            escaped = True
            continue
        if char in {"'", '"'}:
            quote = None if quote == char else char if quote is None else quote
            continue
        if quote != "'" and char in {"$", "`"}:
            return True
    return False


def has_unsafe_wrapper_expansion(command: str) -> bool:
    """Allow only the wrapper's exact HERMES_HOME expansion before ``run --``."""
    quote: str | None = None
    escaped = False
    index = 0
    while index < len(command):
        char = command[index]
        if escaped:
            escaped = False
            index += 1
            continue
        if char == "\\" and quote != "'":
            escaped = True
            index += 1
            continue
        if char in {"'", '"'}:
            quote = None if quote == char else char if quote is None else quote
            index += 1
            continue
        if quote != "'" and char == "`":
            return True
        if quote != "'" and char == "$":
            if command.startswith("${HERMES_HOME}", index):
                index += len("${HERMES_HOME}")
                continue
            if command.startswith("$HERMES_HOME", index):
                end = index + len("$HERMES_HOME")
                if end == len(command) or not (command[end].isalnum() or command[end] == "_"):
                    index = end
                    continue
                return True
            return True
        index += 1
    return False


def raw_child_command(command: str) -> str:
    """Return source text after the wrapper's ``run --`` separator."""
    match = RAW_RUN_SEPARATOR.search(command)
    return command[match.end() :] if match else ""


def block(reason: str) -> int:
    print(json.dumps({"action": "block", "message": f"{BLOCK_PREFIX} {reason}"}))
    return 0


def project_root(workdir: str, *, timeout: float = ROOT_CHECK_TIMEOUT_SECONDS) -> Path | None:
    """Locate the Git root of a declared workdir, or answer None when it genuinely is not one.

    A stall is reported apart from a negative answer (``RootCheckUnresolved``) because the guard's whole job is
    to say *why* a call is refused. Returning None on a timeout would tell the user "this workdir is not a Git
    project", which is a claim about their repository that a hung ``git`` has no authority to make -- and it is
    also the claim that would send them looking for a project that isn't there.
    """
    try:
        candidate = Path(workdir).expanduser().resolve(strict=True)
    except (OSError, RuntimeError):
        return None
    try:
        result = subprocess.run(
            ["git", "-C", str(candidate), "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True, encoding="utf-8", errors="replace",
            check=False, timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        raise RootCheckUnresolved(
            f"git rev-parse did not answer within {timeout:g}s for {candidate}") from exc
    if result.returncode:
        return None
    try:
        return Path(result.stdout.strip()).resolve(strict=True)
    except (OSError, RuntimeError):
        return None


def validate(payload: dict[str, Any]) -> str | None:
    if payload.get("tool_name") != "terminal":
        return None
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        return "terminal input is missing."

    workdir = tool_input.get("workdir")
    if not isinstance(workdir, str) or not workdir.strip():
        return "terminal calls must declare an explicit Git-project workdir."
    try:
        root = project_root(workdir.strip())
    except RootCheckUnresolved as exc:
        return f"project root is unresolved ({exc}); the call is refused rather than assumed safe."
    if root is None:
        return "workdir must resolve inside an existing Git project."

    command = tool_input.get("command")
    if not isinstance(command, str) or not command.strip():
        return "terminal command is missing."
    if has_shell_control(command):
        return "shell chaining/redirection is forbidden; invoke one wrapper command only."
    if has_unsafe_wrapper_expansion(command):
        return "shell expansion before wrapper execution is forbidden."
    try:
        argv = shlex.split(command, posix=True)
    except ValueError:
        return "terminal command quoting is invalid."
    if len(argv) < 4:
        return "invoke hermes-project-data.py with the wrapper executable and arguments."
    if Path(argv[0]).name.lower() not in {"python", "python3", "python.exe", "python3.exe"}:
        return "the wrapper executable must be invoked by Python."
    wrapper = Path(argv[1]).name.lower()
    if wrapper != WRAPPER_NAME:
        return "the command executable must be hermes-project-data.py, not a textual mention."
    if not canonical_wrapper(argv[1]):
        return "the wrapper path must be the canonical deployed Hermes wrapper, not a fake same-name executable."
    if "--project" not in argv or argv[argv.index("--project") + 1 : argv.index("--project") + 2] != ["."]:
        return "the wrapper must use --project . so it is pinned to terminal.workdir."
    project_index = argv.index("--project")
    subcommand_index = project_index + 2
    if len(argv) <= subcommand_index or argv[subcommand_index] not in SUBCOMMANDS:
        return "the wrapper subcommand must be init, check, policy, cleanup, run, or kanban."
    if argv[subcommand_index] == "run" and (len(argv) <= subcommand_index + 1 or argv[subcommand_index + 1] != "--"):
        return "wrapper run requires -- before the child command."
    if argv[subcommand_index] == "run":
        child_source = raw_child_command(command)
        if has_shell_expansion(child_source):
            return "child command contains shell expansion before wrapper execution."
        external_spill = external_spill_path_needing_project_redirect(child_source)
        if external_spill:
            return (
                "child command bypasses project-local cache/temp redirection; "
                f"move the output under .project-local/runs instead of {external_spill}"
            )
        external_unc = external_raw_unc(child_source, root)
        if external_unc:
            return f"child command contains an absolute UNC path outside the Git project: {external_unc}"
        external_windows = external_raw_windows_path(child_source, root)
        if external_windows:
            return f"child command contains an absolute Windows path outside the Git project: {external_windows}"
        external_posix = external_raw_posix_path(child_source, root)
        if external_posix:
            return f"child command contains an absolute POSIX path outside the Git project: {external_posix}"
        if has_raw_parent_traversal(child_source):
            return "child command contains parent-directory traversal outside the Git project."
        external = external_child_path(argv, subcommand_index + 1, root)
        if external:
            return f"child command contains an absolute path outside the Git project: {external}"
    return None


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, TypeError):
        return block("hook payload is not valid JSON.")
    if not isinstance(payload, dict):
        return block("hook payload is not an object.")
    reason = validate(payload)
    return block(reason) if reason else 0


if __name__ == "__main__":
    raise SystemExit(main())
