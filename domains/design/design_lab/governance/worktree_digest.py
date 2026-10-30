# SPDX-License-Identifier: MIT
"""Unified content-bound worktree digest.

DL-AUDIT-20260914-01: the two historical digests (``governance/reporting``
``git_snapshot`` and the ``deepseek_authority_ledger`` / ``run_bound_test_suite``
``worktree_digest``) hashed only Git's porcelain *status string*. A file whose
path was unchanged but whose *content* moved therefore produced an identical
digest, and a recompute over the same bytes was only accidentally stable.

This module is the single shared implementation. Every entry is normalized to a
POSIX path and bound to its current SHA-256 content, so:

* same path, different content -> different digest;
* same content, recomputed     -> same digest (entries are sorted);
* a deletion is marked ``D`` (no content) and a new untracked file is bound by
  its content, so both are distinguishable from a no-op;
* generated / private / runtime roots are excluded by an *explicit* declared
  set, so writing a projection never changes the digest of the subject it
  describes.
"""
from __future__ import annotations

import hashlib
import os
import subprocess
from pathlib import Path, PurePosixPath

# Explicitly declared exclusion scope. Generated projections and private /
# runtime state never enter the digest, and they are never read as private
# data. The set is part of the public contract: changing it is a declared,
# versioned decision, not an implicit one.
EXCLUDED_PREFIXES = (
    "reports/current/",
    "design-lab/config/current-report-index.json",
    ".project-local/",
    ".git/",
    ".venv/",
    ".hermes/",
    ".openhuman/",
)
EXCLUDED_SUFFIXES = ("__pycache__",)


def _git(repo: Path, *args: str) -> str:
    env = {**os.environ, "GIT_OPTIONAL_LOCKS": "0"}
    result = subprocess.run(["git", "-c", "color.ui=false", "-C", str(repo), *args],
                            capture_output=True, text=True, encoding="utf-8",
                            errors="replace", env=env)
    if result.returncode != 0:
        raise ValueError(f"git inspection failed: {args[0]}")
    return result.stdout.rstrip("\r\n")


def _git_bytes(repo: Path, *args: str) -> bytes:
    """Raw-bytes git helper for NUL-delimited porcelain output (v2 -z)."""
    env = {**os.environ, "GIT_OPTIONAL_LOCKS": "0"}
    result = subprocess.run(["git", "-c", "color.ui=false", "-C", str(repo), *args],
                            capture_output=True, env=env)
    if result.returncode != 0:
        raise ValueError(f"git inspection failed: {args[0]}")
    return result.stdout


def _normalize(path: str) -> str:
    """Repository-relative POSIX path; rejects anything that escapes the root."""
    clean = path.replace("\\", "/")
    rel = PurePosixPath(clean)
    if rel.is_absolute() or ".." in rel.parts or str(rel) in {"", "."}:
        raise ValueError(f"worktree digest cannot normalize path: {path!r}")
    return str(rel)


def _excluded(posix: str) -> bool:
    if posix.startswith("."):
        return posix.startswith(".git/") or posix.startswith(".venv/")
    for prefix in EXCLUDED_PREFIXES:
        if posix == prefix.rstrip("/") or posix.startswith(prefix):
            return True
    name = posix.rsplit("/", 1)[-1]
    return any(name.endswith(suffix) or name == suffix for suffix in EXCLUDED_SUFFIXES) \
        or posix.endswith("/__pycache__")


def _file_sha256(repo: Path, posix: str):
    target = repo.joinpath(*PurePosixPath(posix).parts)
    try:
        if target.is_symlink() or not target.is_file():
            return None
        return "sha256:" + hashlib.sha256(target.read_bytes()).hexdigest()
    except OSError:
        return None


import re as _re

_BLOB40 = _re.compile(r"[0-9a-f]{40}")
_RENAME_SIM = _re.compile(r"R\d+ ")


def _core_kind(xy: str) -> str:
    """Normalize a two-char v2 status code to its change class.

    ``.M`` -> ``M`` (unstaged modify), `` D`` -> ``D`` (staged delete), ``MM`` -> ``M``,
    ``A `` -> ``A``.  Duplicate / ``.`` / space characters are dropped, so the result is
    one of ``M``/``D``/``A``/``C`` (or ``R`` handled by the caller).
    """
    out, seen = [], set()
    for c in xy:
        if c not in ". " and c not in seen:
            out.append(c)
            seen.add(c)
    return "".join(out) if out else "M"


def _tail_path(body: str) -> str:
    """Extract the path tail from a v2 record body.

    A non-merge record body looks like
    ``N... <mode> <mode> <mode> <blob> <blob> [<R<sim> ]<path>``.  The path is everything
    *after the last 40-hex blob*, minus an optional ``R<sim>`` rename marker.  Under
    ``-z`` git emits paths as **raw UTF-8 bytes** (NUL-delimited), so the tail is taken
    verbatim — no C-escape / unicode_escape round-trip, which previously corrupted
    non-ASCII paths.
    """
    matches = list(_BLOB40.finditer(body))
    if not matches:
        # Standalone old-path field (no blob): the whole body is the path.
        tail = body.strip()
    else:
        tail = body[matches[-1].end():].lstrip(" ")
    sim = _RENAME_SIM.match(tail)
    if sim:
        tail = tail[sim.end():]
    return tail


def _parse_v2z(data: bytes) -> list:
    """Normalize `git status --porcelain=v2 -z --untracked-files=all` bytes.

    NUL-delimited records, first byte = class:
    * ``1`` / ``2``  non-merge / merge record: ``<XY> N... <mode>^3 <sha>^2 [<R<sim> ]<path>``;
      a rename record carries the *new* path in the record and the *old* path in the
      following NUL field.
    * ``?``          untracked: ``? <path>``.
    * ``u``          unmerged (conflict): bound by path, marked ``C``.
    * ``h`` / ``#``  header line: skipped.
    """
    fields = [f for f in data.split(b"\x00") if f]
    entries = []
    i = 0
    while i < len(fields):
        text = fields[i].decode("utf-8", "replace")
        head = text[:1]
        i += 1
        if head in ("h", "#"):
            continue
        if head == "?":
            path = text[2:] if len(text) > 2 and text[1] == " " else text[1:].lstrip()
            entries.append({"kind": "U", "path": _normalize(path)})
            continue
        if head in ("1", "2"):
            xy = text[2:4]
            if "R" in xy:
                new_path = _tail_path(text)
                old_path = ""
                if i < len(fields):
                    old_path = _tail_path(fields[i].decode("utf-8", "replace"))
                    i += 1
                entries.append({"kind": "R", "path": _normalize(new_path), "moved_from": _normalize(old_path)})
            else:
                entries.append({"kind": _core_kind(xy), "path": _normalize(_tail_path(text))})
            continue
        if head == "u":
            entries.append({"kind": "C", "path": _normalize(_tail_path(text))})
            continue
        # Unknown record class: skip defensively (never fabricate an entry).
    return entries


def analyze(repo: Path, *, base: str = "HEAD", exclude_generated: bool = True) -> dict:
    """Content-bound, deterministic worktree description.

    Returns the base commit, branch, clean flag, the normalized (and, for
    untracked/modified entries, content-hashed) change list, the explicit
    excluded scope that was skipped, and the single digest that binds it all.
    """
    repo = Path(repo)
    head = _git(repo, "rev-parse", base)
    branch = _git(repo, "rev-parse", "--abbrev-ref", "HEAD")
    status_bytes = _git_bytes(repo, "status", "--porcelain=v2", "-z", "--untracked-files=all")
    all_entries = _parse_v2z(status_bytes)
    kept, excluded = [], []
    for entry in all_entries:
        if exclude_generated and _excluded(entry["path"]):
            excluded.append(entry["path"])
            continue
        # Bind content for every non-deletion entry so a same-path,
        # different-content change is visible in the digest.
        if entry["kind"] != "D":
            entry["content"] = _file_sha256(repo, entry["path"])
        kept.append(entry)
    kept.sort(key=lambda e: (e["kind"], e["path"]))
    excluded.sort()
    lines = [head]
    for entry in kept:
        if entry["kind"] == "D":
            lines.append(f"D {entry['path']}")
        else:
            lines.append(f"{entry['kind']} {entry['path']} {entry.get('content') or 'missing'}")
    payload = "\n".join(lines)
    digest = "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return {
        "schema_version": "design-lab/worktree-digest/v2",
        "base": base,
        "head_sha": head,
        "branch": branch,
        "clean": not kept,
        "changes": kept,
        "excluded_generated": excluded,
        "excluded_scope": list(EXCLUDED_PREFIXES),
        "digest": digest,
    }


def worktree_digest(repo: Path, *, base: str = "HEAD", exclude_generated: bool = True) -> str:
    """The digest alone, for callers that only need the binding value."""
    return analyze(repo, base=base, exclude_generated=exclude_generated)["digest"]
