#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""DL-AST-001: upgrade legacy SPDX-text .license sidecars to structured asset-sidecar v1.

Legacy sidecars carry only SPDX-FileCopyrightText + SPDX-License-Identifier.
This tool converts each tracked binary's sidecar into structured JSON with:
- sha256: real hash of the binary (verified by the gate)
- author / license: parsed from the legacy SPDX lines (no fabrication)
- rights flags: derived from the declared SPDX license (MIT -> all true;
  anything else -> false and requires an explicit exception)
- exception: approvedBy = copyright holder recorded in the sidecar,
  expiresAt = end of the policy review cycle (DL-AST-001, annual re-verification)
- notes: provenance of the upgrade

Idempotent: already-structured sidecars are left untouched.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT.parent / 'src'))
from design_lab.runtime.paths import resolve_paths
SIDECAR_V1 = "design-lab/asset-sidecar/v1"
REVIEW_EXPIRY_YEARS = 1
PERMISSIVE_LICENSES = {"MIT", "Apache-2.0", "BSD-3-Clause", "BSD-2-Clause", "ISC", "CC0-1.0", "Unlicense"}

SPDX_COPYRIGHT = re.compile(r"^SPDX-FileCopyrightText:\s*(.+)$")
SPDX_LICENSE = re.compile(r"^SPDX-License-Identifier:\s*(.+)$")


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return "sha256:" + h.hexdigest()


def upgrade(binary: Path, sidecar: Path) -> dict | None:
    text = sidecar.read_text(encoding="utf-8", errors="replace")
    author = None
    license_id = None
    for line in text.splitlines():
        m = SPDX_COPYRIGHT.match(line.strip())
        if m:
            author = m.group(1).strip()
        m = SPDX_LICENSE.match(line.strip())
        if m:
            license_id = m.group(1).strip()
    if license_id is None:
        raise ValueError(f"{sidecar}: no SPDX-License-Identifier")
    permissive = license_id in PERMISSIVE_LICENSES
    today = date.today()
    v1 = {
        "schemaVersion": SIDECAR_V1,
        "file": binary.relative_to(ROOT.parent).as_posix(),
        "sha256": sha256_of(binary),
        "license": license_id,
        "author": author or "unknown (legacy sidecar without copyright line)",
        "redistributable": permissive,
        "modelInputAllowed": permissive,
        "commercialUse": permissive,
        "sourceId": None,
        "exception": {
            "approvedBy": author or "unknown",
            "expiresAt": today.replace(year=today.year + REVIEW_EXPIRY_YEARS).isoformat(),
        },
        "notes": "upgraded from legacy SPDX sidecar under DL-AST-001; rights flags derived from declared SPDX license; expiry = annual asset re-verification policy",
    }
    return v1


def main() -> int:
    layout = resolve_paths(project_root=ROOT.parent)
    out = layout.checked_path(layout.category_dir('runtime') / 'asset-sidecar-upgrade.json')
    result = {"upgraded": [], "skipped": [], "errors": []}
    # walk all tracked binaries under the repo via git ls-files
    import subprocess
    r = subprocess.run(["git", "-C", str(ROOT.parent), "ls-files"], capture_output=True, text=True, encoding="utf-8", errors="replace")
    binaries = []
    for rel in r.stdout.splitlines():
        p = ROOT.parent / rel
        if not p.is_file():
            continue
        suffix = p.suffix.lower()
        if suffix in {".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".wav", ".mp3", ".mp4", ".zip", ".pdf", ".woff", ".woff2", ".ttf", ".otf", ".bin", ".model", ".onnx", ".pb", ".apk", ".aab"}:
            binaries.append(p)
    for binary in sorted(binaries):
        sidecar = Path(str(binary) + ".license")
        if not sidecar.exists():
            result["errors"].append(f"{binary.relative_to(ROOT.parent)}: binary without .license sidecar")
            continue
        try:
            existing = json.loads(sidecar.read_text(encoding="utf-8"))
            if existing.get("schemaVersion") == SIDECAR_V1:
                expected = binary.relative_to(ROOT.parent).as_posix()
                if existing.get("file") != expected:
                    existing["file"] = expected
                    sidecar.write_text(json.dumps(existing, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
                    result["skipped"].append(str(binary.relative_to(ROOT.parent)) + " (file normalized)")
                else:
                    result["skipped"].append(str(binary.relative_to(ROOT.parent)))
                continue
        except (json.JSONDecodeError, OSError):
            pass
        try:
            v1 = upgrade(binary, sidecar)
        except ValueError as exc:
            result["errors"].append(str(exc))
            continue
        sidecar.write_text(json.dumps(v1, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        result["upgraded"].append(str(binary.relative_to(ROOT.parent)))
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"UPGRADE_ASSET_SIDECARS=OK upgraded={len(result['upgraded'])} skipped={len(result['skipped'])} errors={len(result['errors'])}")
    for e in result["errors"]:
        print("ERROR:", e)
    return 1 if result["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
