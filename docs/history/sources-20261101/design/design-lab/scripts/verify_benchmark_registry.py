#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Fail-closed verification for repeatable Open Design benchmarks."""
from __future__ import annotations

import json
from pathlib import Path

EXPECTED_DISCIPLINES = {
    "layout", "typography", "color", "material", "lighting", "spatial",
    "motion", "interaction", "accessibility", "cross-format", "originality", "production",
}
REQUIRED_ENTRY = {"id", "discipline", "brief", "rubric", "evidence"}


def verify(path: Path) -> list[str]:
    errors: list[str] = []
    try:
        registry = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return [f"registry unreadable: {exc}"]
    if registry.get("schema_version") != "design-lab/benchmark-registry/v1":
        errors.append("wrong registry schema_version")
    if registry.get("repeatability", {}).get("human_calibration_required_for_promotion") is not True:
        errors.append("human calibration must be required before promotion")
    entries = registry.get("benchmarks")
    if not isinstance(entries, list) or len(entries) != 12:
        errors.append("registry must contain exactly 12 benchmarks")
        entries = entries if isinstance(entries, list) else []
    ids: set[str] = set()
    disciplines: set[str] = set()
    base = path.parent.parent.parent
    for entry in entries:
        missing = REQUIRED_ENTRY - set(entry) if isinstance(entry, dict) else REQUIRED_ENTRY
        if missing:
            errors.append(f"entry missing fields: {sorted(missing)}")
            continue
        if entry["id"] in ids:
            errors.append(f"duplicate benchmark id: {entry['id']}")
        ids.add(entry["id"])
        disciplines.add(entry["discipline"])
        for field in ("brief", "rubric", "evidence"):
            target = base / entry[field]
            if not target.is_file():
                errors.append(f"{entry['id']}: missing {field} {entry[field]}")
        brief = base / entry["brief"]
        if brief.is_file():
            try:
                data = json.loads(brief.read_text(encoding="utf-8"))
                if data.get("benchmark_id") != entry["id"] or data.get("discipline") != entry["discipline"]:
                    errors.append(f"{entry['id']}: brief metadata mismatch")
                if not data.get("seed") or not data.get("viewport"):
                    errors.append(f"{entry['id']}: missing repeatability controls")
            except (OSError, UnicodeError, json.JSONDecodeError) as exc:
                errors.append(f"{entry['id']}: invalid brief: {exc}")
    if disciplines != EXPECTED_DISCIPLINES:
        errors.append(f"discipline set mismatch: {sorted(disciplines)}")
    return errors


def main() -> int:
    path = Path(__file__).resolve().parents[1] / "evals" / "benchmarks" / "benchmark-registry.json"
    errors = verify(path)
    if errors:
        for error in errors:
            print(f"BENCHMARK_REGISTRY_FAIL {error}")
        return 1
    print("BENCHMARK_REGISTRY_PASS benchmarks=12 human_calibration_required=true")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
