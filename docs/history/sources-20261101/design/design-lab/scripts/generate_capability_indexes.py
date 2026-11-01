#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""DL-MIG-011: generate_capability_indexes.py — capability index generator.

Deterministically scans design-lab capability directories (intelligence,
atoms, scenarios, bundles, domain-packs, quality, production, knowledge,
adapters) and emits design-lab/config/capability-index.json.
It is one of the two canonical activity entrypoints (with verify_design_lab.py).
"""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "config" / "capability-index.json"

# (scan root, relative dir, label) — capability containers that publish
# SKILL.md / manifest.  DL-DIR-MIG-R1: atoms/scenarios/bundles/plugins/quality
# moved to packages/capabilities; intelligence/knowledge/adapters were absorbed
# (research/candidates) and no longer publish capabilities from design-lab/.
REPO = ROOT.parent
CAPABILITY_DIRS = [
    (ROOT, "domain-packs", "domain-packs"),
    (ROOT, "production", "production"),
    (REPO / "packages" / "capabilities", "atoms", "atoms"),
    (REPO / "packages" / "capabilities", "scenarios", "scenarios"),
    (REPO / "packages" / "capabilities", "bundles", "bundles"),
    (REPO / "packages" / "capabilities", "plugins", "plugins"),
    (REPO / "packages" / "capabilities", "quality", "quality"),
]

ALLOW_FILES_SUFFIX = (".gitkeep",)


def collect_capabilities() -> list[dict]:
    caps: list[dict] = []
    for scan_root, rel_dir, label in CAPABILITY_DIRS:
        base = scan_root / rel_dir
        if not base.exists():
            continue
        for entry in sorted(base.rglob("*")):
            if not entry.is_file() or entry.name.endswith(ALLOW_FILES_SUFFIX):
                continue
            rel = entry.relative_to(REPO).as_posix()
            if any(part in rel.split("/") for part in (".git", "__pycache__", "node_modules")):
                continue
            try:
                data = entry.read_bytes()
            except OSError:
                continue
            caps.append(
                {
                    "path": rel,
                    "label": label,
                    "bytes": len(data),
                    "sha256": hashlib.sha256(data).hexdigest()[:16],
                }
            )
    return caps


def main() -> int:
    caps = collect_capabilities()
    caps.sort(key=lambda c: c["path"])
    index = {
        "$schema": "../../schemas/capability-index.schema.json",
        "version": "1.0.0",
        # deterministic: date-only timestamp so identical trees produce identical output
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "capability_count": len(caps),
        "capabilities": caps,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"CAPABILITY_INDEX=OK count={len(caps)} -> {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
