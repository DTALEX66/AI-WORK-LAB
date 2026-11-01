#!/usr/bin/env python
# SPDX-License-Identifier: MIT
"""W01 — safely extract the DESIGN-LAB-specific B04/B07 originals and compare
their tokens against the current workbench implementation.

Only the single-project DESIGN-LAB archives are used. The three-project bundles
in the same folders mix ArcheAxis and WORK-LAB material and must NOT be used for
DESIGN-LAB 1:1 work.

Safety: validates every entry name before writing; refuses to overwrite.
Nothing is executed.
"""
from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path

ROOT = Path(r"D:\All projects\DESIGN-LAB")
UI = Path(r"D:\All projects\UI套件")
DEST = ROOT / ".project-local/task-artifacts/designlab-followup-taskpack-20260928/ui-originals"

SOURCES = {
    "B04": UI / "04_B04_组件系统与DesignTokens_L4/DESIGN-LAB_L4_组件系统_16张+Tokens.zip",
    "B07": UI / "07_B07_前端开发规范_L7/DESIGN-LAB_L7_前端开发规范工程包.zip",
    "B10": UI / "10_B10_最终版高保真可部署UI/design-lab_最终版_高保真可部署UI.zip",
}


def safe_extract(zp: Path, out: Path) -> list[dict]:
    out.mkdir(parents=True, exist_ok=True)
    written = []
    with zipfile.ZipFile(zp) as z:
        for info in z.infolist():
            name = info.filename
            posix = name.replace("\\", "/")
            parts = [p for p in posix.split("/") if p not in ("", ".")]
            if name.startswith(("/", "\\")) or ":" in name or ".." in parts:
                raise SystemExit(f"REJECT unsafe path: {name!r}")
            if info.is_dir():
                continue
            target = out.joinpath(*parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists():
                continue
            target.write_bytes(z.read(info))
            written.append({"path": str(target.relative_to(ROOT)).replace("\\", "/"),
                            "bytes": target.stat().st_size,
                            "sha256": hashlib.sha256(target.read_bytes()).hexdigest()})
    return written


manifest = {}
for tag, src in SOURCES.items():
    if not src.is_file():
        print(f"  {tag}: MISSING {src}")
        continue
    arch_sha = hashlib.sha256(src.read_bytes()).hexdigest()
    files = safe_extract(src, DEST / tag)
    manifest[tag] = {"archive": src.name, "archive_sha256": arch_sha, "files": files}
    print(f"  {tag}: {src.name}  sha256={arch_sha[:16]}  extracted={len(files)} files")

(DEST / "EXTRACTION-MANIFEST.json").write_text(
    json.dumps({"policy": "DESIGN-LAB single-project archives only; three-project bundles excluded",
                "sources": manifest}, ensure_ascii=False, indent=2), encoding="utf-8")

# ------------------------------------------------------------- token compare
print("\n" + "=" * 78)
print("W01  TOKEN COMPARISON  original (B04/B07)  vs  current workbench")
print("=" * 78)

b04_tokens = DEST / "B04/DESIGN-LAB_design_tokens.json"
if b04_tokens.is_file():
    print("\n--- B04 DESIGN-LAB_design_tokens.json ---")
    print(b04_tokens.read_text(encoding="utf-8"))

for rel in ("B07/theme/tokens.json", "B07/theme/tokens.css",
            "B07/shared-ui-core/base-tokens.css", "B07/shared-ui-core/breakpoints.css",
            "B07/shared-ui-core/motion.css"):
    p = DEST / rel
    if p.is_file():
        print(f"\n--- {rel} ---")
        print(p.read_text(encoding="utf-8").rstrip())

print("\n--- 当前实现 apps/workbench/style.css :root（前 25 行）---")
css = (ROOT / "apps/workbench/style.css").read_text(encoding="utf-8").splitlines()
print("\n".join(css[:25]))
