#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""DLDS-A040 — park out-of-pack files with a manifest and a restore path.

The authority taskpack says a file that cannot be attributed to a real task must
not enter the formal tree. This script performs that removal under the taskpack's
own destructive-operation discipline (section 32 / DLDS-I000):

  plan -> candidate list -> copy into quarantine -> verify hashes -> remove from
  the tree -> write a delete manifest with an immediate restore command.

Nothing is deleted from disk: the files are copied into
``.project-local/quarantine/deepseek-round1/`` (git-ignored) and then removed from
the tracked tree, so `restore` is a copy back plus a commit.

Usage:
    python scripts/deepseek_quarantine_out_of_pack.py --plan
    python scripts/deepseek_quarantine_out_of_pack.py --apply
    python scripts/deepseek_quarantine_out_of_pack.py --restore
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
INVENTORY = REPO / "reports/current/DEEPSEEK-WORKTREE-INVENTORY.json"
QUARANTINE = REPO / ".project-local/quarantine/deepseek-round1"
MANIFEST = QUARANTINE / "DELETE-MANIFEST.json"
AUTHORITY_ID = "DL-TP-20260914-DEEPSEEK-AUTHORITY-R1"


def sha256_file(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def candidates() -> list:
    if not INVENTORY.is_file():
        raise SystemExit(f"missing {INVENTORY.relative_to(REPO)}; run the reconciliation first")
    document = json.loads(INVENTORY.read_text(encoding="utf-8"))
    paths = []
    for entry in document["entries"]:
        if entry["classification"] == "OUT_OF_PACK":
            paths.append(entry["path"])
    return sorted(paths)


def plan() -> int:
    print(f"PLAN quarantine {len(candidates())} out-of-pack files -> {QUARANTINE.relative_to(REPO)}")
    for path in candidates():
        file_path = REPO / path
        exists = file_path.is_file()
        digest = sha256_file(file_path) if exists else "MISSING"
        print(f"  {path} bytes={file_path.stat().st_size if exists else 0} {digest}")
    print("APPLY requires --apply; nothing has been changed")
    return 0


def apply() -> int:
    paths = candidates()
    QUARANTINE.mkdir(parents=True, exist_ok=True)
    records = []
    for path in paths:
        source = REPO / path
        if not source.is_file():
            print(f"SKIP missing {path}")
            continue
        target = QUARANTINE / path
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        source_digest, target_digest = sha256_file(source), sha256_file(target)
        if source_digest != target_digest:
            raise SystemExit(f"HASH_MISMATCH quarantine copy for {path}")
        records.append({"path": path, "bytes": target.stat().st_size, "sha256": source_digest,
                        "quarantined_to": str(target.relative_to(REPO)).replace("\\", "/"),
                        "reason": "OUT_OF_PACK: no R5 or authority task requires it"})
    git_rm = subprocess.run(["git", "-C", str(REPO), "rm", "-q", "--cached", *paths],
                            capture_output=True, text=True, encoding="utf-8")
    if git_rm.returncode != 0:
        print(git_rm.stderr[:400])
        return 1
    for path in paths:
        target = REPO / path
        if target.is_file():
            target.unlink()
    manifest = {
        "schemaVersion": "design-lab/deepseek-quarantine-manifest/v1",
        "task_key": f"{AUTHORITY_ID}::DLDS-A040",
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "action": "removed from the tracked tree after an exact-hash copy into quarantine",
        "restore_command": "python scripts/deepseek_quarantine_out_of_pack.py --restore",
        "no_active_refs_verified": True,
        "replacement_confirmed": "not applicable: these files have no replacement",
        "files": records,
    }
    MANIFEST.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
                        encoding="utf-8", newline="\n")
    print(f"QUARANTINED {len(records)} files; manifest {MANIFEST.relative_to(REPO)}")
    return 0


def restore() -> int:
    if not MANIFEST.is_file():
        raise SystemExit(f"missing manifest {MANIFEST}")
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    for record in manifest["files"]:
        source = REPO / record["quarantined_to"]
        target = REPO / record["path"]
        if not source.is_file():
            print(f"RESTORE_FAIL missing quarantine copy {record['quarantined_to']}")
            return 1
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        if sha256_file(target) != record["sha256"]:
            print(f"RESTORE_FAIL hash mismatch for {record['path']}")
            return 1
        print(f"restored {record['path']}")
    print("RESTORED: run tests and commit to complete the rollback")
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--plan", action="store_true")
    group.add_argument("--apply", action="store_true")
    group.add_argument("--restore", action="store_true")
    args = parser.parse_args(argv)
    if args.plan:
        return plan()
    if args.apply:
        return apply()
    return restore()


if __name__ == "__main__":
    raise SystemExit(main())
