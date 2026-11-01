#!/usr/bin/env python3
"""Read-only execution preflight for Git, Python and Markdown evidence.

The report deliberately separates the current branch, its upstream, and the
configured main reference. It never reads auth, private memory, prompts,
sessions, or response bodies and does not fetch or mutate the repository.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import unquote, urlsplit


ANSI_ESCAPE = re.compile(r"\x1b(?:\[[0-?]*[ -/]*[@-~]|\][^\x07]*(?:\x07|\x1b\\))")
MARKDOWN_LINK = re.compile(r"(?<!!)\[[^\]\n]*\]\(([^)\n]+)\)")


class ExecutionPreflightError(RuntimeError):
    """Raised when the requested preflight cannot produce reliable evidence."""


def strip_ansi(value: str) -> str:
    """Remove terminal colour/control sequences before machine parsing."""
    return ANSI_ESCAPE.sub("", value)


def _git(root: Path, *args: str, required: bool = True) -> str | None:
    result = subprocess.run(
        ["git", "-C", str(root), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    stdout = strip_ansi(result.stdout).strip()
    stderr = strip_ansi(result.stderr).strip()
    if result.returncode:
        if not required:
            return None
        detail = stderr or stdout or f"exit {result.returncode}"
        raise ExecutionPreflightError(f"git {' '.join(args)} failed: {detail}")
    return stdout


def _ref_state(root: Path, ref: str) -> dict[str, object]:
    sha = _git(root, "rev-parse", "--verify", ref, required=False)
    if not sha:
        return {"ref": ref, "exists": False, "sha": None, "tree": None}
    tree = _git(root, "rev-parse", f"{ref}^{{tree}}")
    return {"ref": ref, "exists": True, "sha": sha, "tree": tree}


def _divergence(root: Path, left: str, right: str) -> dict[str, int]:
    raw = _git(root, "rev-list", "--left-right", "--count", f"{left}...{right}")
    assert raw is not None
    fields = raw.split()
    if len(fields) != 2:
        raise ExecutionPreflightError(f"unexpected divergence output for {left}...{right}: {raw}")
    return {"current_only": int(fields[0]), "main_only": int(fields[1])}


def collect_git_state(
    project: Path | str,
    *,
    main_ref: str = "origin/main",
    compare_refs: list[str] | tuple[str, ...] = (),
) -> dict[str, object]:
    """Collect distinct local/upstream/main identities without fetching."""
    start = Path(project).resolve()
    raw_root = _git(start, "rev-parse", "--show-toplevel")
    assert raw_root is not None
    root = Path(raw_root).resolve()
    branch = _git(root, "branch", "--show-current") or "(detached)"
    head = _git(root, "rev-parse", "HEAD")
    tree = _git(root, "rev-parse", "HEAD^{tree}")
    status = _git(root, "status", "--porcelain=v1", "--untracked-files=all") or ""
    status_lines = [line for line in status.splitlines() if line]

    upstream_ref: str | None = None
    upstream_state: dict[str, object] = {
        "ref": None,
        "exists": False,
        "sha": None,
        "tree": None,
    }
    if branch != "(detached)":
        upstream_ref = _git(
            root,
            "for-each-ref",
            "--format=%(upstream:short)",
            f"refs/heads/{branch}",
        ) or None
        if upstream_ref:
            upstream_state = _ref_state(root, upstream_ref)

    main = _ref_state(root, main_ref)
    main_exists = bool(main["exists"])
    comparisons = [_ref_state(root, ref) for ref in compare_refs]
    for item in comparisons:
        if item["exists"]:
            item["divergence_from_current"] = _divergence(root, "HEAD", str(item["ref"]))

    return {
        "root": str(root),
        "branch": branch,
        "head": head,
        "tree": tree,
        "clean": not status_lines,
        "dirty_count": len(status_lines),
        "dirty_status_codes": sorted({line[:2] for line in status_lines}),
        "upstream": upstream_state,
        "head_equals_upstream": bool(upstream_ref and upstream_state["sha"] == head),
        "main": main,
        "head_equals_main": bool(main_exists and main["sha"] == head),
        "tree_equals_main": bool(main_exists and main["tree"] == tree),
        "divergence_from_main": _divergence(root, "HEAD", main_ref) if main_exists else None,
        "compare_refs": comparisons,
    }


def _module_available(name: str) -> bool:
    try:
        return importlib.util.find_spec(name) is not None
    except (ImportError, ModuleNotFoundError, ValueError):
        return False


def collect_python_state(required_modules: list[str] | tuple[str, ...]) -> dict[str, object]:
    """Report the exact interpreter and optional-module capabilities."""
    modules = {name: _module_available(name) for name in required_modules}
    return {
        "executable": sys.executable,
        "version": sys.version.split()[0],
        "prefix": sys.prefix,
        "base_prefix": sys.base_prefix,
        "is_virtual_environment": sys.prefix != sys.base_prefix,
        "modules": modules,
        "requirements_satisfied": all(modules.values()),
    }


def _extract_link_target(raw: str) -> str:
    value = raw.strip()
    if value.startswith("<") and ">" in value:
        return value[1 : value.index(">")]
    return value.split(maxsplit=1)[0] if value else ""


def check_markdown_links(project_root: Path | str, documents: list[Path | str]) -> dict[str, object]:
    """Resolve relative Markdown links from each document's own directory."""
    root = Path(project_root).resolve()
    issues: list[dict[str, str]] = []
    checked = 0
    for raw_document in documents:
        document = Path(raw_document)
        if not document.is_absolute():
            document = root / document
        document = document.resolve()
        if not document.is_relative_to(root):
            raise ExecutionPreflightError(f"Markdown document escapes project root: {document}")
        if not document.is_file():
            raise ExecutionPreflightError(f"Markdown document does not exist: {document}")
        text = document.read_text(encoding="utf-8-sig")
        for match in MARKDOWN_LINK.finditer(text):
            target = _extract_link_target(match.group(1))
            parsed = urlsplit(target)
            if (
                not target
                or target.startswith("#")
                or target.startswith("/")
                or parsed.scheme
                or parsed.netloc
            ):
                continue
            path_text = unquote(parsed.path)
            if not path_text:
                continue
            checked += 1
            resolved = (document.parent / path_text).resolve(strict=False)
            reason: str | None = None
            if not resolved.is_relative_to(root):
                reason = "outside-project"
            elif not resolved.exists():
                reason = "missing-target"
            if reason:
                issues.append(
                    {
                        "document": document.relative_to(root).as_posix(),
                        "target": target,
                        "reason": reason,
                    }
                )
    return {
        "documents": len(documents),
        "relative_links_checked": checked,
        "issues": issues,
        "passing": not issues,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", default=".", help="path inside the target Git repository")
    parser.add_argument("--main-ref", default="origin/main", help="explicit main reference")
    parser.add_argument("--compare-ref", action="append", default=[], help="additional ref to report")
    parser.add_argument("--require-module", action="append", default=[], help="Python module required by the selected tests")
    parser.add_argument("--markdown", action="append", default=[], help="Markdown file whose relative links must resolve")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        git_state = collect_git_state(
            args.project,
            main_ref=args.main_ref,
            compare_refs=args.compare_ref,
        )
        root = Path(str(git_state["root"]))
        python_state = collect_python_state(args.require_module)
        markdown_state = check_markdown_links(root, args.markdown)
        blockers: list[str] = []
        if not git_state["main"]["exists"]:
            blockers.append("main-ref-missing")
        if not python_state["requirements_satisfied"]:
            blockers.append("python-module-missing")
        if not markdown_state["passing"]:
            blockers.append("markdown-link-broken")
        payload = {
            "schemaVersion": "workflow/execution-preflight/v1",
            "repository": git_state,
            "python": python_state,
            "markdown": markdown_state,
            "blockers": blockers,
            "status": "PASS" if not blockers else "BLOCKED",
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0 if not blockers else 1
    except (ExecutionPreflightError, UnicodeError, OSError) as exc:
        print(f"execution-preflight: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
