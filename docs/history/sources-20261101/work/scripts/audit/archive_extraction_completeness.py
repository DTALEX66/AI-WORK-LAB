"""Decide whether a downloaded archive is redundant with its extracted tree, byte for byte.

Used before releasing any archive under the ignored runtime root: "the directory looks right" is not
a completeness check. This compares every zip member against the file on disk by name, size and
CRC-32, and reports members missing from the tree, tree files the archive does not explain, and any
byte-level disagreement. Only a clean two-way match makes the archive a redundant copy — and only a
recorded identity (SHA-256 of the archive plus the release it names) keeps the deletion reversible in
the sense that matters: the content is retained, and the copy can be re-fetched and verified.

Usage:
    python scripts/audit/archive_extraction_completeness.py ARCHIVE.zip [--root DIR]
            [--out PATH] [--emit-json]
Exit codes: 0 complete match (archive redundant), 1 NOT redundant (tree incomplete or holds more),
2 archive or root missing.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
import zipfile
import zlib
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 24), b""):
            h.update(chunk)
    return h.hexdigest()


def crc32_of(path: Path) -> tuple[int, int]:
    crc, size = 0, 0
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 22), b""):
            size += len(chunk)
            crc = zlib.crc32(chunk, crc)
    return crc & 0xFFFFFFFF, size


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("archive")
    ap.add_argument("--root", default=None, help="extraction root; default = archive's directory")
    ap.add_argument("--out", default=None, help="write the JSON report here")
    ap.add_argument("--hash-archive", action="store_true", help="also SHA-256 the archive")
    args = ap.parse_args()

    zp = Path(args.archive)
    if not zp.is_absolute():
        zp = REPO / zp
    root = (Path(args.root) if args.root else zp.parent)
    if not root.is_absolute():
        root = REPO / root
    if not zp.is_file():
        print(f"ARCHIVE_ABSENT {zp.relative_to(REPO) if zp.is_relative_to(REPO) else zp}")
        return 2
    if not root.is_dir():
        print(f"ROOT_ABSENT {root}")
        return 2

    zf = zipfile.ZipFile(zp)
    members = [i for i in zf.infolist() if not i.is_dir()]
    matched, details = 0, []
    tree_files = {p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()}
    names = {i.filename.replace("\\", "/") for i in members}
    for info in members:
        name = info.filename.replace("\\", "/")
        on_disk = root / name
        if not on_disk.is_file():
            details.append({"member": name, "state": "MISSING_FROM_TREE",
                            "bytesInArchive": info.file_size})
            continue
        crc, size = crc32_of(on_disk)
        if size != info.file_size or crc != (info.CRC & 0xFFFFFFFF):
            details.append({"member": name, "state": "CRC_OR_SIZE_DISAGREE",
                            "archive": {"bytes": info.file_size, "crc32": f"{info.CRC & 0xFFFFFFFF:08x}"},
                            "tree": {"bytes": size, "crc32": f"{crc:08x}"}})
        else:
            matched += 1
    archive_rel = zp.relative_to(root).as_posix()
    unexplained = sorted(tree_files - names - {archive_rel})
    missing = sum(1 for d in details if d["state"] == "MISSING_FROM_TREE")
    disagree = sum(1 for d in details if d["state"] == "CRC_OR_SIZE_DISAGREE")
    redundant = matched == len(members) and not unexplained

    report = {
        "schemaVersion": "work-lab/archive-extraction-completeness/v1",
        "checkedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "tool": "scripts/audit/archive_extraction_completeness.py",
        "archive": zp.relative_to(REPO).as_posix(),
        "archiveBytes": zp.stat().st_size,
        "archiveSha256": sha256_of(zp) if args.hash_archive else None,
        "extractionRoot": root.relative_to(REPO).as_posix(),
        "members": len(members),
        "memberBytesTotal": sum(i.file_size for i in members),
        "matchedByteIdentical": matched,
        "missingFromTree": missing,
        "crcOrSizeDisagree": disagree,
        "treeFilesNotExplainedByArchive": len(unexplained),
        "sampleTreeFilesNotExplained": unexplained[:10],
        "disagreements": details[:20],
        "verdict": ("EXTRACTION_COMPLETE_ARCHIVE_REDUNDANT" if redundant
                    else "EXTRACTION_INCOMPLETE_OR_TREE_HAS_MORE_ARCHIVE_MUST_STAY"),
    }
    if args.out:
        out = Path(args.out)
        out = out if out.is_absolute() else REPO / out
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"{report['archive']}: members={matched}/{len(members)} matched byte-identical, "
          f"missing={missing}, disagree={disagree}, treeOnly={len(unexplained)}")
    print(f"  archive={report['archiveBytes']:,} B  extractedContent={report['memberBytesTotal']:,} B"
          + (f"  sha256={report['archiveSha256']}" if report["archiveSha256"] else ""))
    print(f"VERDICT {report['verdict']}")
    if not redundant and report["sampleTreeFilesNotExplained"]:
        print("  tree holds files the archive does not explain (not a defect of the archive — "
              "it means the root is not a pure extraction): "
              f"{report['sampleTreeFilesNotExplained'][:5]}")
    return 0 if redundant else 1


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    raise SystemExit(main())
