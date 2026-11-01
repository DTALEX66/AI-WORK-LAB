#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Read a governance document that the tree no longer holds at its recorded path.

Records name paths. A document may have been archived (path changed, bytes untouched) and then
removed on owner order (bytes left out of the tree, still reachable from a commit). Both events are
recorded, so a check that needs the document's content can still get it — and can still fail if the
record is missing or the object is gone. Returning nothing is only allowed after both records and
the object database have been consulted.

Used by the DeepSeek chain scripts, which bind a stop-line hash to a document that no longer
exists in the working tree. It is deliberately not a fallback that makes a broken record look fine:
an absent record, a path not listed in it, or an unreadable object all raise.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


class RecordUnavailable(RuntimeError):
    pass


def _manifest_paths(kind: str) -> list[Path]:
    return sorted((REPO / "docs/history").glob(f"archive-*/{kind}"))


def archive_moves() -> dict[str, str]:
    table: dict[str, str] = {}
    for manifest in _manifest_paths("MANIFEST.json"):
        try:
            data = json.loads(manifest.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        for group in data.get("groups", []):
            for entry in group.get("files", []):
                if entry.get("from") and entry.get("to"):
                    table[entry["from"]] = entry["to"]
    return table


def removals() -> dict[str, dict]:
    table: dict[str, dict] = {}
    for manifest in _manifest_paths("REMOVALS.json"):
        try:
            data = json.loads(manifest.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        for entry in data.get("entries", []):
            if entry.get("path"):
                table[entry["path"]] = entry
    return table


def _git_show(rev: str, rel: str) -> bytes:
    done = subprocess.run(["git", "-C", str(REPO), "show", f"{rev}:{rel}"], capture_output=True)
    if done.returncode != 0:
        raise RecordUnavailable(f"{rel} is not readable at {rev}")
    return done.stdout


def read_record(rel: str) -> tuple[bytes, str]:
    """(bytes, where-from) for a document named by a record.

    Tries the working tree, then the path an archive pass moved it to, then the commit a removal
    manifest says can still produce it. The provenance string is returned so callers can publish
    where the bytes actually came from instead of implying they are live files.
    """
    path = REPO / rel
    if path.is_file():
        return path.read_bytes(), "worktree"
    moved = archive_moves().get(rel)
    if moved:
        target = REPO / moved
        if target.is_file():
            return target.read_bytes(), f"archive-move:{moved}"
        entry = removals().get(moved)
        if entry:
            return _git_show(entry["restoreAt"], moved), f"removed-at:{entry['restoreAt']}"
        raise RecordUnavailable(f"{rel} moved to {moved}, which is neither tracked nor removable-recorded")
    entry = removals().get(rel)
    if entry:
        return _git_show(entry["restoreAt"], rel), f"removed-at:{entry['restoreAt']}"
    raise RecordUnavailable(f"{rel} is absent from the tree and named by no archive or removal manifest")
