#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""DL-KNW-007: controlled external asset intake (Collection Manifest only).

Pipeline stage implemented here:
    External Source Candidate
    -> Collection Manifest (human-authored, DL-KNW-006)
    -> Manifest validation (fail-closed; root scans rejected)
    -> Hash Readback (sha256 of selected paths when library root available)
    -> SourceRecord draft (quarantine; rights/review facts are NEVER fabricated)
    -> Rights Gate (rightsReviewRequired=true blocks Safe Extraction)
    -> Safe Extraction policy check (denylist of copy-forbidden artifact types)
    -> dedup keys (content sha256, sourceId, derivedArtifactId)

Nothing is written into the Git tree by this tool: runtime intake state goes to
`.project-local/task-runtime/intake/` (gitignored). A dry run validates without
touching disk state.

Usage:
    python design-lab/scripts/external_asset_intake.py \
        --manifest design-lab/config/collection-manifests/example.collection.json \
        [--root <external-library-root>] [--dry-run]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT.parent / 'src'))
from design_lab.runtime.paths import resolve_paths
MANIFEST_SCHEMA = ROOT / "schemas" / "collection-manifest.schema.json"
RUNTIME_OUT = resolve_paths().category_dir('runtime', 'intake')

# DL-KNW-007: copying these artifact types into Git is forbidden.
# (reference-only citation is allowed; full copies are not)
COPY_FORBIDDEN_SUFFIXES = {
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".tiff", ".svg",
    ".mp4", ".mov", ".mkv", ".webm", ".avi",
    ".mp3", ".wav", ".flac", ".ogg", ".m4a",
    ".safetensors", ".gguf", ".ckpt", ".pt", ".pth", ".bin", ".onnx",
    ".ttf", ".otf", ".woff", ".woff2",
    ".psd", ".ai", ".fig", ".sketch", ".xd", ".afdesign", ".afphoto",
    ".zip", ".rar", ".7z",
}

# DL-KNW-006: root-scan / glob-sweep patterns are rejected outright
ROOT_SCAN_PATTERNS = {"", ".", "/", "**", "/*", "./**", "**/*"}


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_manifest(manifest: dict) -> list[str]:
    """Return a list of manifest errors (empty == valid, fail-closed)."""
    errors: list[str] = []
    schema = load_json(MANIFEST_SCHEMA)
    validator = jsonschema.Draft202012Validator(schema)
    for verr in sorted(validator.iter_errors(manifest), key=lambda e: list(e.path)):
        where = "/".join(str(p) for p in verr.path) or "$"
        errors.append(f"manifest {where}: {verr.message}")
    for sp in manifest.get("selectedPaths", []):
        norm = sp.strip().replace("\\", "/")
        if norm in ROOT_SCAN_PATTERNS or "**" in norm or norm.startswith(("/", ".:", "C:", "D:")):
            errors.append(f"root-scan rejected: selectedPath={sp!r} (DL-KNW-006 forbids full-library default scans)")
    return errors


def hash_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser(description="Controlled external asset intake (DL-KNW-007)")
    ap.add_argument("--manifest", required=True, help="Path to a Collection Manifest (DL-KNW-006)")
    ap.add_argument("--root", default=None, help="External library root (from local-profile). Optional: hash readback requires it.")
    ap.add_argument("--dry-run", action="store_true", help="Validate and hash only; do not write runtime state")
    args = ap.parse_args()

    manifest_path = Path(args.manifest).resolve()
    try:
        manifest = load_json(manifest_path)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"INTAKE=FAIL manifest unreadable: {exc}")
        return 1

    errors = validate_manifest(manifest)
    if errors:
        for e in errors:
            print("ERROR:", e)
        print(f"INTAKE=FAIL manifest_errors={len(errors)}")
        return 1

    cid = manifest["collectionId"]
    root = Path(args.root).resolve() if args.root else None

    # ---- Hash Readback ----
    hashes: dict[str, str] = {}
    missing: list[str] = []
    for sp in manifest["selectedPaths"]:
        if root is None:
            continue  # reference-only; hashes require the local library root
        p = root / sp
        if not p.exists():
            missing.append(sp)
            continue
        if p.is_dir():
            # only explicit files are hashed; directories must be expanded by the human in the manifest
            errors.append(f"selectedPath is a directory (expand explicitly): {sp}")
            continue
        hashes[sp] = "sha256:" + hash_file(p)
    if errors:
        for e in errors:
            print("ERROR:", e)
        print(f"INTAKE=FAIL manifest_errors={len(errors)}")
        return 1
    if missing:
        print(f"INTAKE=FAIL missing_paths={len(missing)} ({missing[:3]})")
        return 1

    # ---- Safe Extraction policy ----
    blocked = [sp for sp in manifest["selectedPaths"] if Path(sp).suffix.lower() in COPY_FORBIDDEN_SUFFIXES]
    if manifest.get("rightsReviewRequired") is True:
        extraction = "BLOCKED (rightsReviewRequired=true; human rights review is the hard gate)"
    elif blocked:
        extraction = f"BLOCKED (copy-forbidden types selected for extraction: {blocked[:5]})"
    else:
        extraction = "OK (reference-only extraction permitted; derived results must be human-reviewed)"

    # ---- dedup keys ----
    dedup = []
    for sp, h in hashes.items():
        dedup.append({"sourceId": "ext:" + cid, "contentSha256": h, "derivedArtifactId": None, "path": sp})
    for sp in manifest["selectedPaths"]:
        if sp not in hashes:
            dedup.append({"sourceId": "ext:" + cid, "contentSha256": None, "derivedArtifactId": None, "path": sp, "note": "hash requires local library root"})

    print(f"INTAKE_MANIFEST=PASS collection={cid}")
    print(f"ROOT_SCAN=REJECTED_IF_PRESENT selected_paths={len(manifest['selectedPaths'])}")
    print(f"HASH_READBACK={len(hashes)} paths (root={'provided' if root else 'absent: reference-only'})")
    print(f"SAFE_EXTRACTION={extraction}")
    print(f"RIGHTS_GATE={'BLOCKED' if manifest.get('rightsReviewRequired') is True else 'OPEN'}")
    print(f"DEDUP_KEYS={len(dedup)}")
    for d in dedup[:5]:
        print("  dedup:", json.dumps(d, ensure_ascii=False))

    # ---- runtime state (never in git) ----
    if not args.dry_run:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        out = RUNTIME_OUT / f"{cid}-{stamp}.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps({
            "manifest": manifest,
            "hashes": hashes,
            "extraction": extraction,
            "dedup": dedup,
            "capturedAt": datetime.now(timezone.utc).isoformat(),
        }, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"RUNTIME_STATE={out}")

    print("INTAKE=OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
