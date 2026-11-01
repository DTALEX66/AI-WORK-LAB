#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
r"""DL-REC-29 verification: re-prove that every landed import equals its source.

Reads the committed manifest and, for each row, compares NAME + SIZE + CRC32 + sha256:

  source   -> the member bytes as they are in Record right now (needs the volume)
  worktree -> the bytes on disk under this repository
  blob     -> the bytes git would commit (index) or has committed (HEAD)

The blob comparison is what catches an otherwise invisible mutation: a line-ending
normalisation rule rewriting a byte-frozen original at add time — it caught
06_AUDIT_COVERAGE.csv already normalised into the index.

`--offline` drops only the external-volume leg, so a CI checkout without
`D:\All projects\Record` still proves the archived bytes equal the hashes recorded
for them. The volume leg is skipped automatically (and said out loud) when the volume
is absent, because a verification that silently checks less is worse than one that
reports what it could not reach.

Exit code 0 only when every row of every reachable kind reconciles.

Usage:
    python scripts/record_import_verify.py                 # source vs worktree vs index
    python scripts/record_import_verify.py --head          # ... and vs HEAD blobs
    python scripts/record_import_verify.py --offline       # no external volume needed
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import subprocess
import sys
import zipfile
import zlib
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
MANIFEST = REPO / "docs/history/record-imports-2026-10-08/RECORD-IMPORT-MANIFEST.json"
RECORD = Path(r"D:\All projects\Record")
CHECKED_ACTIONS = ("LANDED", "ALREADY-IN-REPO", "EXTERNAL-ONLY", "NESTED-CONTAINER-VERIFIED")


def deep(path: str) -> str:
    """Extended-length form on Windows only.

    `\\\\?\\` is a Win32 namespace prefix: it defeats the 260-character limit that the
    imported atlas paths really hit (longest 216 characters here, plus the source volume's
    own nesting). On POSIX the same prefix is literally part of the filename, so prepending
    it makes every path "not found" -- which is how this verifier failed CI while passing
    locally.
    """
    s = os.path.abspath(path)
    if os.name == "nt" and not s.startswith("\\\\?\\"):
        s = "\\\\?\\" + s
    return s


def crc(data: bytes) -> str:
    return f"{zlib.crc32(data) & 0xFFFFFFFF:08x}"


def sha(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def git_blob(rel: str, use_head: bool) -> bytes | None:
    ref = f"HEAD:{rel}" if use_head else f":{rel}"
    r = subprocess.run(["git", "cat-file", "blob", ref], cwd=REPO, capture_output=True)
    if r.returncode != 0:
        return None
    return r.stdout


def source_bytes(row: dict) -> bytes | None:
    container = row["source_container"]
    member = row["source_member"]
    if member == "(loose file)":
        p = RECORD / container
        if not p.is_file():
            return None
        with open(deep(str(p)), "rb") as fh:
            return fh.read()
    if "::" in container:
        outer_name, inner_name = container.split("::", 1)
        outer = RECORD / outer_name
        if not outer.is_file():
            return None
        with zipfile.ZipFile(outer) as zf:
            raw = zf.read(inner_name)
        with zipfile.ZipFile(io.BytesIO(raw)) as inner:
            return inner.read(member)
    p = RECORD / container
    if not p.is_file():
        return None
    with zipfile.ZipFile(p) as zf:
        return zf.read(member)


def equals_record(data: bytes, row: dict) -> bool:
    return (crc(data) == row["crc32"] and len(data) == row["bytes"]
            and sha(data) == row["sha256"])


def archive_moves() -> dict[str, str]:
    """`recorded path -> current path` proven by an archive-pass MANIFEST.json.

    An import row seals where bytes landed. When a later archive pass relocates the file
    without touching it, the honest record is a pointer to the move, not a rewrite of the
    sealed row -- and the pointer must be checkable against the manifest that measured the
    move, or any dead row could be 'repaired' by inventing a path.
    """
    table: dict[str, str] = {}
    for manifest in sorted((REPO / "docs/history").glob("archive-*/MANIFEST.json")):
        try:
            data = json.loads(manifest.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        for group in data.get("groups", []):
            for entry in group.get("files", []):
                if entry.get("from") and entry.get("to"):
                    table[entry["from"]] = entry["to"]
    return table


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--head", action="store_true", help="compare blobs against HEAD, not the index")
    ap.add_argument("--offline", action="store_true",
                    help="skip the external-volume leg (a CI checkout has no Record volume)")
    args = ap.parse_args()

    if not MANIFEST.is_file():
        print(f"VERIFY ABORT: manifest missing: {MANIFEST}")
        return 2
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    rows = manifest["entries"]

    volume = RECORD.is_dir() and not args.offline
    if not volume and not args.offline:
        print(f"NOTE: source volume absent ({RECORD}); checking recorded bytes against the "
              f"repository only")

    counters = {"rows": len(rows), "source_verified": 0, "source_unreachable": 0,
                "worktree_verified": 0, "mapped_copies_verified": 0, "blob_verified": 0,
                "blob_eol_only": 0, "blob_absent": 0, "moved_rows": 0, "skipped": 0}
    failures: list[str] = []
    moves = archive_moves()

    for row in rows:
        action = row["action"]
        if action not in CHECKED_ACTIONS:
            counters["skipped"] += 1
            continue

        # leg 1 — the external source still equals what the manifest recorded
        if volume:
            src = source_bytes(row)
            if src is None:
                failures.append(f"SOURCE-MISSING {row['source_container']}::{row['source_member']}")
                continue
            if not equals_record(src, row):
                failures.append(f"SOURCE-DRIFT {row['source_container']}::{row['source_member']} "
                                f"recorded crc={row['crc32']} size={row['bytes']:,} "
                                f"now crc={crc(src)} size={len(src):,}")
                continue
            counters["source_verified"] += 1
        else:
            counters["source_unreachable"] += 1

        # leg 2 — the repository copy equals the recorded bytes. A mapped
        # "already in repo" row makes the same claim about a pre-existing file,
        # so it gets checked rather than trusted.
        if action not in ("LANDED", "ALREADY-IN-REPO"):
            continue
        rel = row["target"]
        # A relocation declaration is checked against the archive manifest that measured the
        # move, then the sealed digests are re-verified at the new location. The row keeps its
        # original `target` so the import record stays readable as what actually happened.
        move = row.get("movedTo")
        if move is not None:
            declared = move.get("path")
            if not declared or moves.get(rel) != declared:
                failures.append(f"MOVE-UNPROVEN {rel}: declares {declared!r}, which no "
                                "docs/history/archive-*/MANIFEST.json records as a move")
                continue
            if not (move.get("reason") or "").strip() or not (move.get("by") or {}).get("commit"):
                failures.append(f"MOVE-UNEXPLAINED {rel}: declares a move without a reason "
                                "or the commit that performed it")
                continue
            rel = declared
            counters["moved_rows"] += 1
        dest = REPO / rel
        if not dest.is_file():
            failures.append(f"WORKTREE-MISSING {rel}"
                            + (" (mapped pre-existing copy)" if action == "ALREADY-IN-REPO" else ""))
            continue
        with open(deep(str(dest)), "rb") as fh:
            wt = fh.read()
        # A row may declare that the repository copy was deliberately rewritten after the
        # import, and carry the post-import digests plus the commit that did it. Leg 1 still
        # verified the ARCHIVE against the ZIP above; this only changes which digest the
        # repository file is held to. The declaration is not a waiver: a row that carries
        # post-import digests without saying which commit changed the file, or whose file
        # matches neither the archived nor the declared bytes, still fails.
        evolved = row.get("repoSha256AfterImport") is not None
        if evolved and not (row.get("evolvedBy") or {}).get("commit"):
            failures.append(f"WORKTREE-EVOLVED-UNDECLARED {rel} declares post-import digests "
                            "but names no commit that changed the file")
            continue
        if evolved and not (row.get("evolution") or "").strip():
            failures.append(f"WORKTREE-EVOLVED-UNEXPLAINED {rel} declares post-import digests "
                            "but carries no evolution note")
            continue
        if evolved and not equals_record(wt, {**row, "sha256": row["repoSha256AfterImport"],
                                              "crc32": row["repoCrc32AfterImport"],
                                              "bytes": row["repoBytesAfterImport"]}):
            failures.append(f"WORKTREE-MISMATCH {rel} is declared evolved to "
                            f"crc={row['repoCrc32AfterImport']} size={row['repoBytesAfterImport']} "
                            f"by {(row.get('evolvedBy') or {}).get('commit')} but the file is "
                            f"crc={crc(wt)} size={len(wt):,}")
            continue
        if not evolved and not equals_record(wt, row):
            failures.append(f"WORKTREE-MISMATCH {rel} expected crc={row['crc32']} "
                            f"size={row['bytes']:,} got crc={crc(wt)} size={len(wt):,}")
            continue
        counters["worktree_verified"] += 1
        if action == "ALREADY-IN-REPO":
            counters["mapped_copies_verified"] += 1

        # leg 3 — what git holds was not rewritten on the way in.
        # A LANDED row is a frozen original this task wrote, so its blob must equal the
        # recorded bytes exactly; that is the leg that caught 06_AUDIT_COVERAGE.csv.
        # An ALREADY-IN-REPO row names a file the repository already had, and the repo's
        # own attribute policy may normalise its line endings in the blob while the
        # working copy still equals the source (measured: the two B09/B10 `.bat` files
        # under `*.bat text eol=crlf`, 50 -> 48 bytes). That difference is reported, not
        # hidden, and any other blob difference is a failure.
        blob = git_blob(rel.replace("\\", "/"), args.head)
        if blob is None:
            counters["blob_absent"] += 1
            continue
        if crc(blob) == row["crc32"] and sha(blob) == row["sha256"]:
            counters["blob_verified"] += 1
            continue
        normalised = sha(blob) == sha(wt.replace(b"\r\n", b"\n"))
        if action == "ALREADY-IN-REPO" and normalised:
            counters["blob_eol_only"] += 1
            print(f"NOTE: blob line endings normalised for mapped copy {rel} "
                  f"(record {row['bytes']:,} B CRLF -> blob {len(blob):,} B LF)")
            continue
        failures.append(f"BLOB-MISMATCH {rel} worktree crc={crc(wt)} blob crc={crc(blob)} "
                        + ("(line endings differ — no attribute explains this for a landed "
                           "frozen original)" if normalised else
                           "(content differs, not only line endings)"))

    print(f"RECORD_VERIFY scope={'source+repo' if volume else 'repo-only'} "
          + " ".join(f"{k}={v:,}" for k, v in counters.items()))
    for f in failures[:40]:
        print("FAIL:", f)
    if len(failures) > 40:
        print(f"FAIL: ... {len(failures) - 40} more")
    verdict = "OK" if not failures else "FAIL"
    print(f"RECORD_VERIFY={verdict} blobs={'HEAD' if args.head else 'INDEX'}")
    return 0 if verdict == "OK" else 1


if __name__ == "__main__":
    sys.exit(main())
