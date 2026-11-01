#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Validate the external assets index (共用库项目资产指向).

Checks the index is schema-valid and every asset references a declared
shared_root. Path-existence is intentionally NOT checked here (shared roots
live outside the repo and differ per machine); that is a local inventory task.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from jsonschema import validate

REPO = Path(__file__).resolve().parents[1]
SCHEMA = REPO / "schemas" / "external-assets-index.schema.json"
INDEX = REPO / "config" / "external-assets-index.json"


def main() -> int:
    errors: list[str] = []
    try:
        schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"ERROR schema read: {e}")
        return 1
    try:
        index = json.loads(INDEX.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"ERROR index read: {e}")
        return 1

    try:
        validate(instance=index, schema=schema)
    except Exception as e:
        errors.append(f"schema: {e}")

    shared_roots = index.get("shared_roots", {})
    for a in index.get("assets", []):
        if a.get("shared_root") not in shared_roots:
            errors.append(f"{a.get('id')}: shared_root '{a.get('shared_root')}' not declared")

    for e in errors:
        print("ERROR", e)
    print(f"VERIFY_EXTERNAL_ASSETS_INDEX={'PASS' if not errors else 'FAIL'} assets={len(index.get('assets', []))}")
    return 0 if not errors else 1


if __name__ == "__main__":
    sys.exit(main())
