#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Validate a Domain Pack against Spec V2 (ODA4-0204).

A compliant pack must contain all ten required elements. Prompt-only packs fail.

Usage:
    python design-lab/scripts/verify_domain_pack_v2.py <pack-dir>
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SCHEMA = REPO / "schemas" / "domain-pack.schema.json"

REQUIRED_FILES = {
    "manifest": "manifest.json",
    "brief_schema": "schemas/brief.schema.json",
    "scenario": "scenario.md",
    "profile": "profile.json",
    "rubric": "rubric.json",
    "preflight": "preflight.json",
    "handoff_contract": "handoff-contract.json",
    "source_mapping": "sources.json",
    "benchmark_cases": "benchmarks/",
    "evidence_cards": "evidence/",
}
DIRECTORY_ELEMENTS = {"benchmark_cases", "evidence_cards"}

DEFAULT_BUDGET = 5_242_880  # 5 MiB


def contained_path(pack_dir: Path, declared: object) -> Path | None:
    """Resolve a declared element only when it stays inside the pack tree."""
    if not isinstance(declared, str) or not declared:
        return None
    candidate = (pack_dir / declared).resolve()
    try:
        candidate.relative_to(pack_dir.resolve())
    except ValueError:
        return None
    return candidate


def validate(pack_dir: Path) -> tuple[bool, list[str]]:
    errors: list[str] = []
    manifest_path = pack_dir / "manifest.json"
    if not manifest_path.exists():
        return False, [f"missing manifest.json in {pack_dir}"]

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        return False, [f"invalid manifest.json: {exc}"]

    # Schema validation
    try:
        import jsonschema
        schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
        jsonschema.validate(manifest, schema)
    except ImportError as exc:
        errors.append(f"schema validation unavailable: jsonschema is required ({exc})")
    except Exception as exc:  # noqa: BLE001
        errors.append(f"schema validation failed: {exc}")

    # Ten-element completeness: manifest MUST declare all ten; declared paths must exist.
    files_map = manifest.get("files") or {}
    for key, rel in REQUIRED_FILES.items():
        declared = files_map.get(key)
        if not declared:
            errors.append(f"manifest missing files.{key} declaration")
            continue
        resolved = contained_path(pack_dir, declared)
        if resolved is None:
            errors.append(f"declared path escapes pack: {declared} (for {key})")
            continue
        if key in DIRECTORY_ELEMENTS:
            if not resolved.is_dir():
                errors.append(f"declared directory missing: {declared} (for {key})")
            elif not any(path.is_file() for path in resolved.iterdir()):
                errors.append(f"declared directory empty: {declared} (for {key})")
        elif not resolved.is_file():
            errors.append(f"declared file missing: {declared} (for {key})")

    # Size budget
    budget = manifest.get("size_bytes_budget", DEFAULT_BUDGET)
    total = sum(p.stat().st_size for p in pack_dir.rglob("*") if p.is_file())
    if total > budget:
        errors.append(f"size {total} exceeds budget {budget}")

    return not errors, errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("pack_dir", help="Domain pack directory")
    args = parser.parse_args()
    ok, errors = validate(Path(args.pack_dir).resolve())
    for e in errors:
        print("ERROR", e)
    print(f"DOMAIN_PACK_V2={'PASS' if ok else 'FAIL'} pack={args.pack_dir}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
