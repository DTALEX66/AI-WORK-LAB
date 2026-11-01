#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""DL C3: verify experience corpus (fail-closed, stdlib only)."""
from __future__ import annotations

import json
from pathlib import Path

import jsonschema

ROOT = Path(__file__).resolve().parent.parent
SCHEMA = ROOT / "schemas" / "experience-record.schema.json"
SAMPLE = ROOT / "evals" / "experience-corpus" / "sample-hero.json"
MEMORY = ROOT / "memory" / "records.json"


def main() -> int:
    errors: list[str] = []
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator.check_schema(schema)
    sample = json.loads(SAMPLE.read_text(encoding="utf-8"))
    try:
        jsonschema.validate(sample, schema)
    except jsonschema.ValidationError as exc:
        errors.append(f"sample invalid: {exc.message}")
    bad = {k: v for k, v in sample.items() if k != "project_id"}
    try:
        jsonschema.validate(bad, schema)
        errors.append("missing project_id must fail")
    except jsonschema.ValidationError:
        pass
    mem_ids = {r.get("id") for r in json.loads(MEMORY.read_text(encoding="utf-8"))}
    for ref in sample.get("memory_refs", []):
        if ref not in mem_ids:
            errors.append(f"memory_ref {ref} not in memory/records.json")
    print(f"EXPERIENCE_CORPUS={'FAIL' if errors else 'PASS'}")
    for e in errors:
        print("ERROR:", e)
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
