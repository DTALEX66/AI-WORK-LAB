#!/usr/bin/env python
# SPDX-License-Identifier: MIT
"""Ownership-correct cleanup of .project-local root residue.

Rule applied: "位置合规 != 归属正确" — classify by DATA OWNERSHIP before moving.

MOVED to task-artifacts/external-recovery-2026-09-27/ (agent session staging):
  check170-h001.py, diagnose-170.py, merge-170.py   (#170 gate poll/diagnose/merge scripts)
  topics-payload.json                               (agent-composed GitHub topics payload)

KEPT at .project-local root, with the contract that dictates the location:
  context-capsule.json        -> CAPSULE_REL in design-lab/scripts/context_capsule.py:42
  prune-manifest-2026-09-2*.json -> cited audit evidence (AGENTS.md + closeout ledger)
  stash-backup-2026-09-26.json   -> cited evidence in reports/history closeout ledger

REMOVED:
  .project-local/.project-local/  (nested path-join residue; verified empty)

Verified with sha256 before AND after each move.
"""
from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(r"D:\All projects\DESIGN-LAB")
PL = ROOT / ".project-local"
DEST = PL / "task-artifacts" / "external-recovery-2026-09-27"

MOVE = ["check170-h001.py", "diagnose-170.py", "merge-170.py", "topics-payload.json"]
KEEP = {
    "context-capsule.json": "CAPSULE_REL contract: design-lab/scripts/context_capsule.py:42",
    "prune-manifest-2026-09-26.json": "cited audit evidence (AGENTS.md / closeout ledger)",
    "prune-manifest-2026-09-27.json": "cited audit evidence (AGENTS.md / closeout ledger)",
    "stash-backup-2026-09-26.json": "cited evidence in reports/history closeout ledger",
}


def sha(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def section(t: str) -> None:
    print(f"\n{'=' * 74}\n{t}\n{'=' * 74}")


section("1. 移动（agent 会话暂存 -> external-recovery）")
moved = []
for name in MOVE:
    src = PL / name
    if not src.is_file():
        print(f"  {name:<26} SKIP (absent)")
        continue
    before = sha(src)
    dst = DEST / name
    if dst.exists():
        print(f"  {name:<26} SKIP (dest exists, refusing to overwrite)")
        continue
    shutil.move(str(src), str(dst))
    after = sha(dst)
    ok = before == after
    print(f"  {name:<26} {before[:16]} -> {after[:16]}  {'OK' if ok else 'MISMATCH'}")
    moved.append({"name": name, "sha256": after, "bytes": dst.stat().st_size, "verified": ok})
    assert ok, f"sha mismatch for {name}"

section("2. 保留（位置由契约/引用决定）")
for name, why in KEEP.items():
    p = PL / name
    print(f"  {name:<28} {'present' if p.exists() else 'ABSENT':<8} {why}")

section("3. 删除嵌套残留")
nested = PL / ".project-local"
if nested.exists():
    inner = list(nested.rglob("*"))
    files = [p for p in inner if p.is_file()]
    print(f"  {nested.relative_to(ROOT)}  entries={len(inner)} files={len(files)}")
    if files:
        print("  REFUSING to delete: contains files ->", [str(f) for f in files][:5])
    else:
        shutil.rmtree(nested)
        print(f"  deleted (was empty of files). exists now = {nested.exists()}")
else:
    print("  already absent")

section("4. 清理后 .project-local 顶层")
for e in sorted(PL.iterdir(), key=lambda e: (e.is_file(), e.name)):
    print(f"  {'DIR ' if e.is_dir() else 'FILE'} {e.name}")

section("5. 追加 MANIFEST 记录")
man = DEST / "MANIFEST.json"
data = json.loads(man.read_text(encoding="utf-8"))
data.setdefault("followups", []).append({
    "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
    "action": "root-residue-ownership-cleanup",
    "moved_in": moved,
    "kept_in_place": KEEP,
    "removed": [".project-local/.project-local/ (empty nested path-join residue)"],
    "rationale": "agent session scripts/payloads are workflow infrastructure -> external-recovery; "
                 "context-capsule.json stays because a tracked script owns that path; "
                 "prune-manifest/stash-backup stay because tracked docs cite them",
})
man.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
print(f"  MANIFEST updated: {man.relative_to(ROOT)}  followups={len(data['followups'])}")
print("\nDONE")
