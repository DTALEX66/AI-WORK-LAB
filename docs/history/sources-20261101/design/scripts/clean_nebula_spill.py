# SPDX-License-Identifier: MIT
"""Remove the confirmed nebula spill from the ComfyUI tool root, reversibly.

Nothing here deletes on sight. The script:
  1. re-proves byte identity between each spill file and its Git-tracked mirror,
  2. writes a manifest carrying the hash, the blob path, and a copy-pasteable restore
     command, and only then
  3. deletes the exact eight paths it just verified -- never the directory, never a
     glob the owner did not approve.

`--apply` is required; without it this is a report. Recovery after the fact is
`git show main:<blob>` because the surviving copy is committed content, not a copy
this machine made.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(r"D:/All projects/DESIGN-LAB")
SPILL_DIR = Path(r"D:/All projects/Design External Configuration/toolchains/comfyui/"
                 "ComfyUI_windows_portable/ComfyUI/output")
MIRROR_REL = "docs/projects/nebula-tech-culture-wall/assets"
MIRROR = ROOT / MIRROR_REL
MANIFEST = ROOT / ".project-local" / "task-artifacts" / "spill-cleanup-20261007" / "nebula-comfyui-output.json"
EXPECTED = 8


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_only() -> int:
    """Prove the recorded deletion held: nothing left in the tool root, everything
    intact in Git. This is the branch a re-run takes, and it is the one that makes
    the manifest useful after the fact."""
    if not MANIFEST.is_file():
        sys.exit("REFUSING: tool root is empty but no manifest proves these bytes went anywhere")
    records = json.loads(MANIFEST.read_text(encoding="utf-8"))["files"]
    for record in records:
        twin = Path(record["gitBlob"]).name
        if sha256(MIRROR / twin) != record["sha256"]:
            sys.exit(f"REFUSING: {twin} no longer matches the recorded sha256")
    print(f"SPILL_CLEAN_VERIFIED={len(records)} bytes_reclaimed="
          f"{sum(r['size'] for r in records):,} committed_copies_intact=True")
    return 0


def main(apply: bool) -> int:
    if not SPILL_DIR.is_dir():
        print("SPILL_ROOT_ABSENT", SPILL_DIR)
        return 0
    spill = sorted(p for p in SPILL_DIR.glob("nebula_*.png") if p.is_file())
    if not spill:
        # Re-running after the cleanup must prove the deletion held and the committed
        # copies are untouched, not refuse because there is nothing left to delete.
        return verify_only()
    if len(spill) != EXPECTED:
        sys.exit(f"REFUSING: expected {EXPECTED} spill files, found {len(spill)} at {SPILL_DIR}")
    tracked = subprocess.run(["git", "-C", str(ROOT), "ls-files", MIRROR_REL],
                             capture_output=True, text=True).stdout.split()
    blobs = {Path(t).name: t for t in tracked}

    records = []
    for path in spill:
        digest = sha256(path)
        # the mirror drops ComfyUI's `_00001_` frame suffix; match on that convention
        # and then prove identity by hash rather than trusting the name.
        twin = path.name.replace("_00001_", "")
        blob = blobs.get(twin)
        if blob is None:
            sys.exit(f"REFUSING: {path.name} has no committed mirror candidate ({twin})")
        if sha256(MIRROR / twin) != digest:
            sys.exit(f"REFUSING: {path.name} and {blob} differ by content hash")
        if twin + ".license" not in blobs:
            sys.exit(f"REFUSING: {twin} has bytes in Git but no rights sidecar")
        records.append({
            "spillPath": str(path),
            "size": path.stat().st_size,
            "sha256": digest,
            "gitBlob": blob,
            "licenseSidecar": blobs[twin + ".license"],
            "restore": f"git -C \"{ROOT.as_posix()}\" show main:{blob} > \"{path}\"",
            "identityProof": "sha256(spill) == sha256(committed blob), re-run at delete time",
        })

    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps({
        "schemaVersion": "design-lab/spill-cleanup/v1",
        "decidedAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "subject": "DESIGN-LAB ComfyUI generation output left in a shared tool root",
        "governance": "AGENTS.md 执行规范: 设计产物留在本项目内，不外溢到其他项目/共享库",
        "reversibility": "every deleted byte is committed content at the same sha256",
        "deleted": apply,
        "files": records,
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(f"MANIFEST={MANIFEST}")
    print(f"verified identical pairs: {len(records)}/{EXPECTED}  "
          f"bytes: {sum(r['size'] for r in records):,}")

    if not apply:
        print("DRY_RUN: nothing deleted; re-run with --apply")
        return 0
    for record in records:
        path = Path(record["spillPath"])
        if sha256(path) != record["sha256"]:
            sys.exit(f"REFUSING: {path} changed between verify and delete")
        path.unlink()
    left = sorted(p.name for p in SPILL_DIR.glob("nebula_*.png"))
    print(f"DELETED={len(records)} remaining_nebula_in_tool_root={len(left)}")
    mirror_after = {p.name: sha256(p) for p in MIRROR.glob("nebula_*") if p.is_file()}
    print(f"mirror untouched: {len(mirror_after)} files still present, "
          f"hashes match manifest: "
          f"{all(sha256(MIRROR / Path(r['gitBlob']).name) == r['sha256'] for r in records)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main("--apply" in sys.argv[1:]))
