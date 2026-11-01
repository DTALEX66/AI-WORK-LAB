#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""DL-CI-001: Identity-boundary gate.

Fail-closed: active product paths must not contain the legacy identity
(OPEN-DESIGN-Assistance / design-lab / Open Design Assistance)
unless in an explicit allowlist (history, host adapters, source references).
"""
from __future__ import annotations

import re
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# Legacy identity patterns
LEGACY = [
    r"OPEN[- ]DESIGN[- ]Assistance",
    r"opendesign[-_]assistance",
    r"Open Design Assistance",
]

# Allowlisted roots (history + host adapter projection + source refs)
ALLOW_ROOT_PREFIXES = (
    "docs/taskpacks/",  # external taskpacks with explanatory legacy-name refs
    "docs/history/",
    "docs/cross-project/",  # external federation taskpacks (explanatory legacy-name refs)
    "reports/history/",
    "fixtures/domains/game-visual/docs/history/",
    "integrations/hosts/open-design/",
    ".github/workflows-archive/",  # archived workflows, not active CI identity
)

# Files that may legitimately reference the legacy name
ALLOW_FILES_SUFFIX = (
    "DL-MIG-000-baseline.md",
    "migration",
    "MIGRATION",
)

EXCLUDED_NAMES = {
    '.git', '.project-local', '.hermes', '.venv', 'node_modules', '__pycache__',
    '.pytest_cache', '.mypy_cache', '.ruff_cache', '.codex', '.claude', '.openhuman',
    'auth.json', 'credentials.json', 'tokens.json', 'id_rsa', 'id_ed25519',
    'sessions.db', 'session.db', 'cookies', 'keychain',
}

# ZIP containers get their own treatment: the bytes are not UTF-8, but the member
# names are, and that is exactly where a legacy package name travels. A `.whl` was
# previously neither in the container branch nor in the binary-skip list, so every
# `uv build` in the working tree turned the gate red with a decode error that
# detected nothing (measured: dist/design_lab-0.1.0a0-py3-none-any.whl).
CONTAINER_SUFFIXES = {'.zip', '.whl'}


def _excluded(name):
    return name.casefold() in EXCLUDED_NAMES or name.casefold().startswith(('.env', '.hermes'))


def _active_files(hits):
    """Prune runtime/private trees before scandir; don't follow reparse points."""
    def walk_error(exc):
        hits.append(f'active directory unreadable: {exc}')
    for directory, names, files in os.walk(ROOT, topdown=True, followlinks=False, onerror=walk_error):
        parent = Path(directory)
        keep = []
        for name in sorted(names):
            path = parent/name
            relative = path.relative_to(ROOT).as_posix() + '/'
            if _excluded(name) or any(relative.startswith(p) for p in ALLOW_ROOT_PREFIXES):
                continue
            if path.is_symlink() or (hasattr(path, 'is_junction') and path.is_junction()):
                hits.append(f'{relative}: active reparse point not scanned')
                continue
            keep.append(name)
        names[:] = keep
        for name in sorted(files):
            if _excluded(name):
                continue
            path = parent/name
            if path.is_symlink():
                hits.append(f'{path.relative_to(ROOT).as_posix()}: active link not scanned')
                continue
            yield path


def _container_member_names(path, rel, hits) -> None:
    """Match the legacy identity against a ZIP container's member names."""
    import zipfile
    try:
        with zipfile.ZipFile(path) as archive:
            names = archive.namelist()
    except Exception as exc:
        # Fail-closed, the same rule that governs unreadable text: a container that
        # cannot be opened cannot be shown to be clean.
        hits.append(f'{rel}: container unreadable ({type(exc).__name__})')
        return
    for name in names:
        for pattern in LEGACY:
            if re.search(pattern, name, re.IGNORECASE):
                hits.append(f'{rel} :: member {name}: {pattern}')
                return


SCANNED = {'files': 0}


def scan() -> list[str]:
    hits: list[str] = []
    for p in _active_files(hits):
        if not p.is_file():
            continue
        SCANNED['files'] += 1
        rel = p.relative_to(ROOT).as_posix()
        if any(rel.startswith(prefix) for prefix in ALLOW_ROOT_PREFIXES):
            continue
        if any(rel.endswith(sfx) for sfx in ALLOW_FILES_SUFFIX):
            continue
        if rel == "design-lab/scripts/verify_identity_gate.py":
            continue  # self (pattern definitions)
        if rel == '.gitignore':
            continue  # exclusion patterns may name legacy directories; not product branding
        # Host-adapter projection scripts keep legacy-derived filenames (F1 allowance)
        if rel in (
            "design-lab/scripts/scaffold_open_design_plugin.py",
            "design-lab/scripts/doctor_open_design_windows.py",
        ):
            continue
        # Terminology policy documents declare legacy names as denylist entries (DL-MIG-002)
        if rel in (
            "docs/DL-MIG-002-terminology.md",
        ):
            continue
        # Test files asserting the gate's detection logic legitimately embed
        # the legacy patterns as fixtures (semantic requirement, not violation).
        if rel.startswith("design-lab/tests/") and rel.endswith(".py"):
            continue
        # A ZIP container (including a built wheel) is matched by member name, which
        # is where a package identity actually travels. This runs before the binary
        # skip so `.zip`/`.whl` can never be waved through unexamined.
        if Path(rel).suffix.lower() in CONTAINER_SUFFIXES:
            _container_member_names(p, rel, hits)
            continue
        # Binary assets are not text; identity patterns cannot appear in them.
        # Skipping them is not fail-open (patterns are text-only by definition).
        if Path(rel).suffix.lower() in {
            ".png", ".jpg", ".jpeg", ".gif", ".webp", ".mp4", ".mp3", ".wav", ".flac",
            ".pdf", ".zip", ".gz", ".7z", ".ttf", ".otf", ".woff", ".woff2",
            ".exe", ".dll", ".so", ".dylib", ".bin", ".model", ".onnx", ".pb",
            ".fig", ".sketch", ".psd", ".ai", ".ico", ".cur", ".svgz",
        }:
            continue
        try:
            text = p.read_text(encoding="utf-8")
        except Exception as exc:
            # Fail-closed: an unreadable text file must not bypass the
            # identity scan (Codex review finding 3).
            hits.append(f"{rel}: unreadable ({exc})")
            continue
        # Exempt lines that declare the legacy name retired (prohibition/history context)
        exempt_lines = []
        for line in text.splitlines():
            if any(w in line for w in ["退出活动", "历史归档", "不再作为活动", "仅允许出现在", "retired", "denylist", "Denylist", "allowlist"]):
                exempt_lines.append(line)
        for exempt in exempt_lines:
            text = text.replace(exempt, "")
        for pattern in LEGACY:
            if re.search(pattern, text, re.IGNORECASE):
                hits.append(f"{rel}: {pattern}")
                break
    return hits


def main() -> int:
    hits = scan()
    scanned = SCANNED['files']
    if hits:
        print(f"IDENTITY_GATE=FAIL total={len(hits)} scanned={scanned}")
        for h in hits[:30]:
            print(f"  {h}")
        return 1
    # A liveness floor, not an inventory: the tree holds ~3.0k files and adding or
    # removing one is never a failure, but a walk that saw almost nothing would print
    # the same OK total=0 as a genuinely clean repository. Measured on the binding
    # environment rather than the convenient one: a CLEAN detached worktree of HEAD --
    # what CI checks out, no dist/, no untracked scratch -- walks 2838 files; this dirty
    # tree walked 3012. Unreadable directories and skipped reparse points already arrive
    # as hits, so this catches the remaining case of a scan that examined nothing.
    if scanned < 2000:
        print(f"IDENTITY_GATE=FAIL scanned={scanned} total=0 "
              f"reason=the walk examined too few files to be a check at all")
        return 1
    print(f"IDENTITY_GATE=OK total=0 scanned={scanned}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
