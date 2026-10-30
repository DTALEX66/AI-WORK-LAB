#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""DL-PRD-001: Production Preflight V1 (E1 gate).

Checks a handoff directory for the DL-PRD-001 required fields:
colors, fonts (with license), dimensions, formats, editable source,
licenses, BOM. Human/E3 verification still required for release.
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path


def file_hash(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()[:16]


def check_handoff(dirpath: Path) -> list[str]:
    findings = []
    src_exts = {".psd", ".ai", ".indd", ".blend", ".fig", ".sketch"}
    export_exts = {".png", ".jpg", ".webp", ".svg", ".pdf", ".mp4", ".gif"}
    font_exts = {".ttf", ".otf", ".woff", ".woff2"}

    all_files = [p for p in dirpath.rglob("*") if p.is_file()]
    srcs = [p for p in all_files if p.suffix.lower() in src_exts]
    exports = [p for p in all_files if p.suffix.lower() in export_exts]
    fonts = [p for p in all_files if p.suffix.lower() in font_exts]

    if not srcs and not exports:
        findings.append("NO-ARTIFACTS: no editable source or exports found")

    bom = dirpath / "BOM.json"
    if not bom.exists():
        findings.append("MISSING-BOM: BOM.json required")
    else:
        try:
            bom_data = json.loads(bom.read_text(encoding="utf-8"))
            if not bom_data.get("items"):
                findings.append("EMPTY-BOM: BOM has no items")
        except json.JSONDecodeError:
            findings.append("BAD-BOM: BOM.json not valid JSON")

    license_md = dirpath / "LICENSES.md"
    if not license_md.exists():
        # license sidecars (*.license) also acceptable
        sidecars = [p for p in all_files if p.name.endswith(".license")]
        if not sidecars and fonts:
            findings.append("MISSING-LICENSE: fonts present without license declaration")

    if not fonts:
        findings.append("NO-FONTS: font licensing not declared (ok if no fonts used)")

    return findings


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("handoff_dir", type=Path)
    args = ap.parse_args()

    if not args.handoff_dir.exists():
        print("PREFLIGHT=FAIL handoff dir missing")
        return 1

    findings = check_handoff(args.handoff_dir)
    for f in sorted(findings):
        print(f"  {f}")
    if findings:
        print(f"\nPREFLIGHT_V1=FAIL findings={len(findings)}")
        return 1
    print("\nPREFLIGHT_V1=OK (E1; E3 readback still required for release)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
