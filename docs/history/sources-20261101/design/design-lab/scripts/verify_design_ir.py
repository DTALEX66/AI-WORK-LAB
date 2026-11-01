#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""DL C1: verify Design IR (fail-closed, stdlib only)."""
from __future__ import annotations

import json
from pathlib import Path

import jsonschema

ROOT = Path(__file__).resolve().parent.parent
SCHEMA = ROOT / "schemas" / "design-ir.schema.json"
SAMPLE = ROOT / "evals" / "design-ir" / "sample-hero.json"


def main() -> int:
    errors: list[str] = []
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator.check_schema(schema)
    sample = json.loads(SAMPLE.read_text(encoding="utf-8"))
    try:
        jsonschema.validate(sample, schema)
    except jsonschema.ValidationError as exc:
        errors.append(f"sample invalid: {exc.message}")
    bad1 = {k: v for k, v in sample.items() if k != "canvas"}
    try:
        jsonschema.validate(bad1, schema)
        errors.append("missing canvas must fail")
    except jsonschema.ValidationError:
        pass
    bad2 = dict(sample)
    bad2["layers"] = [{"id": "x", "type": "movie", "name": "x"}]
    try:
        jsonschema.validate(bad2, schema)
        errors.append("invalid layer type must fail")
    except jsonschema.ValidationError:
        pass

    def walk(layers):
        for l in layers:
            if l.get("type") == "image" and not l.get("image", {}).get("src_ref", "").startswith("artifact://"):
                errors.append(f"image layer {l['id']}: src_ref must be artifact://")
            walk(l.get("children", []))
    walk(sample.get("layers", []))

    print(f"DESIGN_IR={'FAIL' if errors else 'PASS'}")
    for e in errors:
        print("ERROR:", e)
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
