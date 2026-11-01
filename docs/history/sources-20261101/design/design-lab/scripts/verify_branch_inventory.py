#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Fail closed if the generated branch inventory authorizes destructive action."""
from __future__ import annotations

import json
from pathlib import Path

PATH = Path(__file__).resolve().parents[1] / "config" / "branch-cleanup-candidates.json"


def main() -> int:
    errors: list[str] = []
    try:
        data = json.loads(PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"BRANCH_INVENTORY=FAIL reason={exc}")
        return 1
    if data.get("deletionAuthorized") is not False:
        errors.append("deletionAuthorized must remain false")
    for branch in data.get("branches", []):
        if branch.get("action") != "review-only":
            errors.append(f"non-review action: {branch.get('ref')}")
    for error in errors:
        print(f"FAIL {error}")
    print(f"BRANCH_INVENTORY={'PASS' if not errors else 'FAIL'} branches={len(data.get('branches', []))}")
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
