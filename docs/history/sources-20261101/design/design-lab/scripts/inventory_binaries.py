#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""DL-AST-002: binary inventory generator.

Scans every tracked binary and classifies it:
- KEEP                      - small reference fixture / doc asset with valid structured sidecar
- REGENERATE                - regenerable from runtime (e.g. game renders), still within caps
- EXTERNALIZE               - recommended move to the shared external library (informational)
- QUARANTINE                - sidecar missing/invalid (no runtime/capability use)
- REMOVE_PENDING_APPROVAL   - listed only; removal requires explicit user confirmation

Output: reports/current/DL-AST-002-BINARY-INVENTORY.json
"""
from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "reports" / "current" / "DL-AST-002-BINARY-INVENTORY.json"
SIDECAR_V1 = "design-lab/asset-sidecar/v1"

BINARY_SUFFIXES = {
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".wav", ".mp3", ".mp4",
    ".pdf", ".zip", ".gz", ".7z", ".ttf", ".otf", ".woff", ".woff2",
    ".exe", ".dll", ".so", ".dylib", ".bin", ".model", ".onnx", ".pb",
    ".apk", ".aab",
}
REGENERATE_HINTS = ("cctv", "texture-", "overlay-", "generated/")


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return "sha256:" + h.hexdigest()


def classify(rel: str, size: int, sidecar_ok: bool) -> tuple[str, str]:
    if not sidecar_ok:
        return "QUARANTINE", "sidecar missing or invalid; not usable as governed asset"
    low = rel.lower()
    if any(h in low for h in REGENERATE_HINTS):
        return "REGENERATE", "regenerable from runtime/generator; candidate to externalize or regenerate; removal requires user approval"
    if size > 1024 * 1024:
        return "REGENERATE", f"large ({size/1048576:.2f} MiB) but within cap; regenerable preferred"
    return "KEEP", "small reference fixture / doc asset with structured sidecar"


def main() -> int:
    r = subprocess.run(["git", "-C", str(REPO), "ls-files"], capture_output=True, text=True, encoding="utf-8", errors="replace")
    items = []
    total_bytes = 0
    for rel in r.stdout.splitlines():
        p = REPO / rel
        if not p.is_file() or Path(rel).suffix.lower() not in BINARY_SUFFIXES:
            continue
        size = p.stat().st_size
        total_bytes += size
        sidecar = Path(str(p) + ".license")
        sidecar_ok = False
        author = None
        license_id = None
        if sidecar.exists():
            try:
                sc = json.loads(sidecar.read_text(encoding="utf-8"))
                sidecar_ok = sc.get("schemaVersion") == SIDECAR_V1
                author = sc.get("author")
                license_id = sc.get("license")
            except (OSError, json.JSONDecodeError):
                pass
        cls, reason = classify(rel, size, sidecar_ok)
        items.append({
            "path": rel,
            "sizeBytes": size,
            "sizeMiB": round(size / 1048576, 3),
            "sha256": sha256_of(p) if sidecar_ok else None,
            "license": license_id,
            "author": author,
            "sidecarValid": sidecar_ok,
            "classification": cls,
            "reason": reason,
        })
    items.sort(key=lambda i: (-i["sizeBytes"], i["path"]))
    counts = {}
    for it in items:
        counts[it["classification"]] = counts.get(it["classification"], 0) + 1
    report = {
        "report": "DL-AST-002-BINARY-INVENTORY",
        "generated_at": date.today().isoformat(),
        "totalBinaries": len(items),
        "totalBytes": total_bytes,
        "totalMiB": round(total_bytes / 1048576, 2),
        "counts": counts,
        "note": "REMOVE_PENDING_APPROVAL 不自动执行；任何删除需用户明确确认 (R4 执行原则 9)。",
        "entries": items,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"DL_AST_002=OK binaries={len(items)} total_mib={report['totalMiB']} counts={json.dumps(counts)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
