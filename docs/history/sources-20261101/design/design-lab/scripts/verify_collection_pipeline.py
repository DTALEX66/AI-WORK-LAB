#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""DL-V2 P2-H: verify controlled intake pipeline (fail-closed).

Collection Manifests 必须：受控摄取、权利未验证项 quarantine、禁止整库复制。
"""
from __future__ import annotations

import json
from pathlib import Path

import jsonschema

ROOT = Path(__file__).resolve().parent.parent
SCHEMA = ROOT / "schemas" / "collection-manifest.schema.json"
COLLECTIONS = ROOT / "external-assets" / "collections"


def main() -> int:
    errors: list[str] = []
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator.check_schema(schema)
    manifests = sorted(COLLECTIONS.glob("*.json"))
    if not manifests:
        errors.append("no collection manifests")
    for m in manifests:
        data = json.loads(m.read_text(encoding="utf-8"))
        try:
            jsonschema.validate(data, schema)
        except jsonschema.ValidationError as exc:
            errors.append(f"{m.name}: {exc.message}")
            continue
        for item in data.get("items", []):
            if item.get("license") == "unverified" and item.get("intake_status") != "quarantined":
                errors.append(f"{m.name}/{item['asset_id']}: unverified license must be quarantined")
        if "禁止整库" not in (data.get("notes", "") or ""):
            errors.append(f"{m.name}: must forbid bulk-copy into GitHub")

    print(f"COLLECTION_PIPELINE={'FAIL' if errors else 'PASS'} manifests={len(manifests)}")
    for e in errors:
        print("ERROR:", e)
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
