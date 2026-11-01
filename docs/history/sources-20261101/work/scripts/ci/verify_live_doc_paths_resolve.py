#!/usr/bin/env python3
"""Live documentation may not cite repository paths that do not exist.

Why this exists
---------------
Measured 2026-10-18: 383 stale `path` citations in tracked documents. Splitting them by *kind* is the whole
insight, and it changes the answer completely:

  * 376 sit in historical / audit documents (`docs/history/**`, `docs/audits/**`, `reports/**`,
    `knowledge-staging/**`, `taskpacks/history/**`). A record of what was true in September must keep naming
    the September path -- rewriting it would falsify the record. They are FROZEN, not broken.
  * 7 sat in live documents, and three of those were load-bearing: an authority document naming a binary path
    that no longer exists, a census naming a module without its extension, and a guide whose backticks made an
    external product's directory look like a repository path.

The recurring "old path" complaint was therefore never "the archive is dirty". It was: **live documents were
never checked**. The authority index resolves 51 targets; everything else was unverified, so a renamed file left
a citation behind that only a human reading that paragraph would ever notice.

Scope
-----
Live = root Markdown whose disposition is not `historical-non-normative` (the disposition registry decides that,
so demoting a document silences its citations in one place instead of two), plus `docs/current/`, `docs/decisions/`
and `docs/future/`. Frozen roots are named below, once, with the reason.

Exceptions must carry a reason and a date, and a stale exception (the path exists again) is itself a finding --
otherwise the exception list becomes the next place where old facts hide.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DISPOSITIONS = ROOT / ".project/governance/root-document-dispositions.json"
EXCEPTIONS = ROOT / ".project/governance/live-doc-path-exceptions.json"

LIVE_PREFIXES = ("docs/current/", "docs/decisions/", "docs/future/")
FROZEN_PREFIXES = ("docs/history/", "docs/audits/", "reports/", "90-archive/", "knowledge-staging/",
                   "taskpacks/history/")
# Individually frozen documents: the authority index declares these FROZEN_ARCHIVED / NO_EXECUTION_AUTHORITY, so
# their prose is a record too -- the same reasoning as the frozen prefixes, applied to one file.
FROZEN_DOCS = {"docs/future/WORK-LAB-BLUEPRINT-20261006.md": "FROZEN_ARCHIVED in the authority index"}
# A backticked token that starts with a repo directory is being presented as a repository path. Anything else
# (a URL, a version, a product's own directory) is not this gate's business.
PATH_RE = re.compile(
    r"`((?:docs|scripts|services|packages|apps|tests|config|taskpacks|integrations)/[A-Za-z0-9_./-]+)`"
)


def tracked(root: Path) -> list[str]:
    out = subprocess.run(["git", "ls-files", "-z"], cwd=root, capture_output=True).stdout
    return [name for name in out.decode("utf-8", "replace").split("\0") if name]


def historical_root_docs(root: Path) -> set[str]:
    data = json.loads(DISPOSITIONS.read_text(encoding="utf-8"))
    rows = data.get("authority") or data.get("documents") or []
    out: set[str] = set()
    for row in rows:
        if isinstance(row, dict) and row.get("disposition") == "historical-non-normative":
            out.add(str(row.get("path")))
    return out


def live_documents(root: Path, names: list[str]) -> list[str]:
    historical = historical_root_docs(root)
    docs: list[str] = []
    for name in names:
        if not name.endswith((".md", ".csv")):
            continue
        if name in historical:
            continue
        if name.startswith(FROZEN_PREFIXES) or name in FROZEN_DOCS:
            continue
        if "/" not in name or name.startswith(LIVE_PREFIXES):
            docs.append(name)
    return docs


def exceptions(root: Path) -> dict[str, dict]:
    if not EXCEPTIONS.is_file():
        return {}
    data = json.loads(EXCEPTIONS.read_text(encoding="utf-8"))
    return {str(k): v for k, v in (data.get("exceptions") or {}).items()}


def audit(root: Path, names: list[str] | None = None) -> tuple[list[str], list[str], int]:
    """Audit live documents under `root`. `names` is injectable so the rule can be tested without a git repo --
    a rule that can only be exercised by committing to the real repository is a rule nobody falsifies."""
    names = names if names is not None else tracked(root)
    if not names:
        raise RuntimeError("git ls-files returned nothing; the checker cannot see the corpus")
    declared = exceptions(root)
    problems: list[str] = []
    stale: list[str] = []
    checked = 0
    for doc in live_documents(root, names):
        try:
            text = (root / doc).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for match in PATH_RE.finditer(text):
            target = match.group(1).rstrip(".")
            checked += 1
            exists = (root / target).exists()
            if exists and target in declared:
                stale.append(f"{target}: declared as missing but exists now (remove the exception)")
            elif not exists and target not in declared:
                problems.append(f"{doc} cites `{target}`, which does not exist")
    return problems, stale, checked


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args(argv)
    try:
        problems, stale, checked = audit(args.root)
    except Exception as exc:  # noqa: BLE001 - a checker that cannot run must say so, not pass
        print(f"LIVE_DOC_PATHS_FAIL cannot audit: {type(exc).__name__}: {exc}")
        return 1
    print(f"LIVE_DOC_PATHS citations={checked} missing={len(problems)} stale_exceptions={len(stale)}")
    for problem in problems:
        print(f"  {problem}")
    for entry in stale:
        print(f"  {entry}")
    if problems or stale:
        print("LIVE_DOC_PATHS_FAIL live documents must not cite paths that do not exist; historical roots "
              "are excluded on purpose (a record of September keeps September's paths)")
        return 1
    print("LIVE_DOC_PATHS_PASS every live citation resolves")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
