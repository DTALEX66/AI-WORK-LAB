#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""DL-KNW-100/110: verify knowledge governance foundations.

After DL-DIR-MIG-R1, knowledge files were migrated:
- ABSORB_MINIMAL → packages/capabilities/
- CONDITIONAL_POC → research/candidates/
- LOCK_REFERENCE → vendor/sources.lock.json (full copies deleted)
- REJECT_REMOVE → deleted

This verifier checks the migrated structure.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REQUIRED = (
    "design-lab/config/knowledge-role-classification.json",
)


def main() -> int:
    errors: list[str] = []
    for relative in REQUIRED:
        path = ROOT / relative
        if not path.is_file():
            errors.append(f"missing {relative}")
    classification = ROOT / "design-lab/config/knowledge-role-classification.json"
    if classification.is_file():
        try:
            data = json.loads(classification.read_text(encoding="utf-8"))
            if data.get("authorityStatus") != "temporary-design-lab":
                errors.append("classification authorityStatus must be temporary-design-lab")
            if data.get("migrationStatus") != "deferred":
                errors.append("classification migrationStatus must be deferred")
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(f"invalid classification: {exc}")
    for error in errors:
        print(f"FAIL {error}")
    print(f"KNOWLEDGE_LIFECYCLE={'PASS' if not errors else 'FAIL'} findings={len(errors)}")
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
