# SPDX-License-Identifier: MIT
"""Declare (or re-declare) that a landed Record copy was deliberately rewritten.

`record_import_verify.py` holds every `LANDED` / `ALREADY-IN-REPO` row to a recorded digest:
leg 1 against the archived bytes (verified against the source ZIP), leg 2 against the
repository copy. When a later batch intentionally rewrites such a file, leg 2 has no way to
say so -- it can only report WORKTREE-MISMATCH, which makes honest evolution look exactly
like silent corruption. This writes the post-import state onto the row so leg 2 can hold the
file to the truth instead.

What it does NOT do, and why that matters:

* it never touches the archived `sha256` / `crc32` / `bytes` -- those describe the ZIP and
  leg 1 keeps verifying them against the ZIP;
* it never invents a commit. `evolvedBy.commit` is read from `git log` for that exact path,
  so the row names a real commit that really changed the file;
* it never rewrites the gate or lowers a criterion. `verify_record_import_verify.py` still
  refuses the file if it matches neither the archived nor the declared bytes, and still
  refuses a row that declares post-import digests without naming a commit.

Run it with `--check` first to see what would move; nothing is written unless it prints
`UPDATED`.

    python scripts/declare_record_evolution.py [--check] [path ...]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "docs/history/record-imports-2026-10-08/RECORD-IMPORT-MANIFEST.json"
#: The three repository state keys this script writes. Kept explicit so a future edit that
#: touches anything else in the manifest has to be a deliberate act, not a side effect.
POST_IMPORT_KEYS = ("repoBytesAfterImport", "repoCrc32AfterImport", "repoSha256AfterImport")


def git(*args: str) -> str:
    return subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True,
                          text=True, encoding="utf-8", errors="replace").stdout.strip()


def digests(raw: bytes) -> dict:
    return {
        "repoBytesAfterImport": len(raw),
        "repoCrc32AfterImport": format(zlib.crc32(raw) & 0xFFFFFFFF, "08x"),
        "repoSha256AfterImport": "sha256:" + hashlib.sha256(raw).hexdigest(),
    }


def matches_archive(raw: bytes, row: dict) -> bool:
    """True when the repository copy still equals the archived bytes for this row.

    Mirrors what the gate compares, so "has this diverged?" is answered by the same
    rule the gate will use -- not by a second, looser notion of equality.
    """
    return (len(raw) == row.get("bytes")
            and format(zlib.crc32(raw) & 0xFFFFFFFF, "08x") == row.get("crc32")
            and "sha256:" + hashlib.sha256(raw).hexdigest() == row.get("sha256"))


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="*", help="tracked paths to (re)declare; default: every "
                                                 "row whose repository copy no longer matches")
    parser.add_argument("--check", action="store_true", help="report only; write nothing")
    parser.add_argument("--why", default="", help="why the copy diverged from the archive")
    args = parser.parse_args(argv)

    if not MANIFEST.is_file():
        print(f"DECLARE-EVOLUTION=FAIL manifest missing: {MANIFEST}")
        return 1
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    wanted = set(args.paths)

    touched, skipped = [], []
    for row in manifest.get("entries", []):
        rel = row.get("target")
        if not rel or row.get("action") not in ("LANDED", "ALREADY-IN-REPO"):
            continue
        if wanted and rel not in wanted:
            continue
        dest = ROOT / rel
        if not dest.is_file():
            skipped.append(f"{rel} (absent)")
            continue
        raw = dest.read_bytes()
        new = digests(raw)
        current = {key: row.get(key) for key in POST_IMPORT_KEYS}
        if current == new and row.get("evolvedBy", {}).get("commit"):
            continue
        # Without an explicit path list, only rows whose repository copy has actually
        # diverged from the ARCHIVE are candidates. A row that still equals its archived
        # bytes needs no declaration, and blanket-declaring every row would be exactly the
        # "make it true by rewriting the record" move this script exists to avoid.
        if not wanted and matches_archive(raw, row):
            continue
        commit = git("log", "-1", "--format=%h", "--", rel)
        subject = git("log", "-1", "--format=%s", "--", rel)
        if not commit:
            skipped.append(f"{rel} (untracked: no commit changed it)")
            continue
        why = args.why.strip() or (
            "The archive bytes recorded above are unchanged and still verify against the "
            "source ZIP (leg 1). This row is held to the repository copy's post-import "
            f"digests instead, because commit {commit[:8]} deliberately rewrote that file "
            "after the import. Leg 2 still refuses the file if it matches neither the "
            "archived nor the declared bytes.")
        row.update(new)
        row["evolvedBy"] = {"commit": commit, "subject": subject}
        row["evolution"] = why
        touched.append((rel, commit[:8], new["repoCrc32AfterImport"]))

    for rel in skipped:
        print(f"  skipped {rel}")
    if not touched:
        print("DECLARE-EVOLUTION=OK nothing-to-declare")
        return 0
    for rel, commit, crc in touched:
        print(f"  {rel} -> {commit} crc={crc}")
    if args.check:
        print(f"DECLARE-EVOLUTION=CHECK would-declare={len(touched)}")
        return 0
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"UPDATED {len(touched)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())