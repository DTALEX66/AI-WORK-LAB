#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Verify license coverage (V42 Phase 11): source SPDX headers + binary sidecars.

Checks, over the tracked tree:
1. Every project Python/JS/MJS source file carries an SPDX-License-Identifier
   header (REUSE), excluding generated bundles / vendored / node_modules.
2. Every tracked binary asset has a REUSE `<name>.license` sidecar.
3. Emits a coverage report; non-zero exit on any gap.

Idempotent, read-only, matches the CI license-secret-gate semantics.
Scope: focuses on design-lab/ core and top-level LICENSE sources.
minigame-runtime generated bundles are excluded (product tree already split).
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SOURCE_EXT = (".py", ".mjs", ".js")
BINARY_EXT = (
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico",
    ".ttf", ".otf", ".woff", ".woff2",
    ".mp4", ".mp3", ".ogg", ".wav",
)
# Generated / vendored / split-out trees excluded from source-header coverage.
EXCLUDE_PREFIX = (
    "fixtures/domains/game-visual/",
    "fixtures/domains/game-visual/android-",
    "fixtures/domains/game-visual/wechat-",
    "fixtures/domains/game-visual/douyin-",
    "fixtures/domains/game-visual/webview-",
    "reports/",
    "design-lab/templates/",
    "design-lab/domain-packs/",
    "design-lab/design-systems/",
    "design-lab/evals/",
    # vendored third-party skill trees / external candidate POCs migrated to
    # research/candidates/: each carries its own LICENSE + SOURCE.md (REUSE: vendored
    # trees are excluded from project header coverage)
    "research/candidates/",
    # D003 Build Output Truth: apps/workbench/build is the committed Vite outDir
    # (generated bundle, no-drift-checked like the MiniGame committed bundles),
    # not hand-edited source — excluded from source-header coverage. The
    # TypeScript source it is built from (apps/workbench/*.ts) IS covered.
    "apps/workbench/build/",
)


def git_ls() -> list[str]:
    """Tracked paths through NUL-separated porcelain.

    `git ls-files` escapes and quotes any non-ASCII path, so a line-split read hands
    back literal "\"docs/…\345\225\206…\"" tokens: they fail the endswith(SOURCE_EXT)
    test and every such source file silently drops out of coverage. -z is never quoted.
    """
    out = subprocess.run(
        ["git", "ls-files", "-z"], cwd=REPO, capture_output=True, text=True,
        encoding="utf-8", errors="replace", check=True,
    ).stdout
    return [p for p in out.split("\0") if p]


IMPORT_MANIFEST = "docs/history/record-imports-2026-10-08/RECORD-IMPORT-MANIFEST.json"
TASKPACK_ARCHIVE_MANIFEST = "docs/history/taskpacks/20261009-inputs/ARCHIVE-MANIFEST.json"
# The R2 UI pack was archived the same way (owner-adopted input, byte-frozen originals with a
# per-member sha256), so it gets the same per-file rule rather than a path exemption.
R2_ARCHIVE_MANIFEST = "docs/history/taskpacks/20261009-r2-inputs/ui-r2/ARCHIVE-MANIFEST.json"


def is_excluded(rel: str) -> bool:
    if "/node_modules/" in rel:
        return True
    return rel.startswith(EXCLUDE_PREFIX)


def inert_imported_sources(files: list[str]) -> set[str]:
    """Imported originals that may stay header-free — but only while unmodified.

    A task-#29 import landed frozen task packages whose text members include 16
    historical .py/.mjs scripts. They are inert source blobs (AGENTS.md): rewriting
    them to add an SPDX header would violate the freeze that the import manifest
    hashes, so the REUSE source-header rule cannot apply to them. The exemption is
    not a path prefix that anything can hide behind: each file is exempt only while
    its bytes still equal the sha256 recorded for it in the manifest. Edit one and
    it becomes project source again, SPDX required.
    """
    import hashlib
    import json

    manifest = REPO / IMPORT_MANIFEST
    if not manifest.is_file():
        return set()
    try:
        data = json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return set()
    want = {e["target"]: e["sha256"] for e in data.get("entries", [])
            if e.get("action") == "LANDED" and e["target"].endswith(SOURCE_EXT)}
    # Owner-adopted inputs remain inert, byte-frozen originals. This extends the
    # same per-file hash rule, never a blanket exemption or runtime license grant.
    archive = REPO / TASKPACK_ARCHIVE_MANIFEST
    if archive.is_file():
        try:
            packages = json.loads(archive.read_text(encoding="utf-8"))["packages"]
            for package in packages:
                for member in package["members"]:
                    rel = member.get("repository_text")
                    if (rel and rel.startswith("docs/history/taskpacks/20261009-inputs/")
                            and rel.endswith(SOURCE_EXT)):
                        want[rel] = "sha256:" + member["sha256"]
        except (OSError, KeyError, TypeError, json.JSONDecodeError):
            pass  # No exemption for an unreadable or malformed archive manifest.
    r2 = REPO / R2_ARCHIVE_MANIFEST
    if r2.is_file():
        try:
            for package in json.loads(r2.read_text(encoding="utf-8"))["packages"]:
                for member in package["members"]:
                    rel = member.get("repository_text")
                    if (rel and rel.startswith("docs/history/taskpacks/20261009-r2-inputs/")
                            and rel.endswith(SOURCE_EXT)):
                        want[rel] = "sha256:" + member["sha256"]
        except (OSError, KeyError, TypeError, json.JSONDecodeError):
            pass  # Same rule: a manifest that cannot be read grants nothing.
    exempt: set[str] = set()
    for rel, digest in want.items():
        if rel not in files:
            continue
        p = REPO / rel
        try:
            actual = "sha256:" + hashlib.sha256(p.read_bytes()).hexdigest()
        except OSError:
            continue
        if actual == digest:
            exempt.add(rel)
    return exempt


def check_source() -> tuple[list[str], int]:
    files = git_ls()
    exempt = inert_imported_sources(files)
    missing = []
    for rel in files:
        if not rel.endswith(SOURCE_EXT) or is_excluded(rel) or rel in exempt:
            continue
        p = REPO / rel
        if not p.exists():
            continue
        head = p.read_text(encoding="utf-8", errors="replace")[:200]
        if "SPDX-License-Identifier" not in head:
            missing.append(rel)
    return missing, len(exempt)


def check_binary_sidecars() -> list[str]:
    missing = []
    for rel in git_ls():
        if not rel.lower().endswith(BINARY_EXT) or is_excluded(rel):
            continue
        if not (REPO / (rel + ".license")).exists():
            missing.append(rel)
    return missing


def main() -> int:
    src_missing, inert_exempted = check_source()
    bin_missing = check_binary_sidecars()
    if inert_exempted:
        print(f"Inert imported originals exempt from source headers (bytes still equal the "
              f"manifest sha256): {inert_exempted}")
    print(f"Source files missing SPDX header: {len(src_missing)}")
    for f in src_missing:
        print(f"  MISSING SPDX: {f}")
    print(f"Binary assets missing .license sidecar: {len(bin_missing)}")
    for f in bin_missing:
        print(f"  MISSING sidecar: {f}")
    ok = not src_missing and not bin_missing
    if ok:
        print("LICENSE_COVERAGE=OK (source headers + binary sidecars complete)")
        return 0
    print("LICENSE_COVERAGE=FAIL")
    return 1


if __name__ == "__main__":
    sys.exit(main())
