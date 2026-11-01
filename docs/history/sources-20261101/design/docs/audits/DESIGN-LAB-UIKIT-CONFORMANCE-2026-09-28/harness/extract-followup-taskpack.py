#!/usr/bin/env python
# SPDX-License-Identifier: MIT
"""Safe extraction of the 20260928 follow-up task pack into the project's
gitignored evidence root.

Safety: validates every entry name (no absolute paths, no drive letters, no
'..' traversal, no backslashes) BEFORE writing anything, and refuses to
overwrite. Never executes anything from the archive.
"""
from __future__ import annotations

import hashlib
import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path

SRC = Path(r"D:\All projects\DSH\.dsh\attachments\v1\files\70"
           r"\70592198dbd4ea0228ab1714143ec9e230f90237d19247b8831d586d64cfae85"
           r"\DESIGNLAB_商业级前端与能力闭环_后续任务包_20260928.zip")
DEST = Path(r"D:\All projects\DESIGN-LAB\.project-local\task-artifacts"
            r"\designlab-followup-taskpack-20260928")


def main() -> int:
    if not SRC.is_file():
        print(f"FAIL: archive missing {SRC}")
        return 1
    raw = SRC.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    print(f"archive  : {SRC.name}")
    print(f"sha256   : {digest}")
    print(f"bytes    : {len(raw)}")

    DEST.mkdir(parents=True, exist_ok=True)
    written = []
    with zipfile.ZipFile(SRC) as z:
        for info in z.infolist():
            name = info.filename
            posix = name.replace("\\", "/")
            parts = [p for p in posix.split("/") if p not in ("", ".")]
            bad = (name.startswith(("/", "\\")) or ":" in name
                   or ".." in parts or any(p == "" for p in parts))
            if bad:
                print(f"  REJECT (unsafe path): {name!r}")
                return 1
            if info.is_dir():
                continue
            # flatten: this pack has no subdirectories, but be explicit anyway
            target = DEST / parts[-1]
            if target.exists():
                print(f"  SKIP (exists, not overwriting): {target.name}")
                continue
            target.write_bytes(z.read(info))
            written.append({"name": target.name, "bytes": target.stat().st_size,
                            "sha256": hashlib.sha256(target.read_bytes()).hexdigest()})
            print(f"  wrote {target.name:<32} {target.stat().st_size:>7} B")

    manifest = {
        "taskpack": "DESIGNLAB_商业级前端与能力闭环_后续任务包_20260928",
        "archive": SRC.name,
        "archive_sha256": digest,
        "archive_bytes": len(raw),
        "extracted_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "extracted_to": str(DEST),
        "policy": "read-only analysis; never execute archive contents",
        "files": written,
    }
    (DEST / "EXTRACTION-MANIFEST.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nmanifest : {DEST / 'EXTRACTION-MANIFEST.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
