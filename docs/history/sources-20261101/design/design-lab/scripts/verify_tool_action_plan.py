#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""DL-INT-130: validate a tool-neutral action plan and fail closed on omissions."""
from __future__ import annotations

import json
from pathlib import Path

import jsonschema

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "schemas" / "tool-action-plan.schema.json"
SAMPLE = ROOT / "evals" / "tool-action-plan" / "sample-hero.json"


def valid(value: object, schema: object) -> bool:
    try:
        jsonschema.validate(value, schema)
        return True
    except jsonschema.ValidationError:
        return False


def main() -> int:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    sample = json.loads(SAMPLE.read_text(encoding="utf-8"))
    errors: list[str] = []
    try:
        jsonschema.Draft202012Validator.check_schema(schema)
    except jsonschema.SchemaError as exc:
        errors.append(f"invalid schema: {exc.message}")
    if not valid(sample, schema):
        errors.append("sample plan invalid")
    broken = dict(sample)
    broken.pop("rollback", None)
    if valid(broken, schema):
        errors.append("missing rollback must fail")
    broken_action = dict(sample)
    broken_action["actions"] = [dict(sample["actions"][0])]
    broken_action["actions"][0].pop("expectedReadback", None)
    if valid(broken_action, schema):
        errors.append("missing expectedReadback must fail")
    for error in errors:
        print(f"ERROR {error}")
    print(f"TOOL_ACTION_PLAN={'PASS' if not errors else 'FAIL'}")
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
