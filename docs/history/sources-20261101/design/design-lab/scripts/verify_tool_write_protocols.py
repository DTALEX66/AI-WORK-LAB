#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""DL-ADP-110: ensure real-tool write protocols are explicit and inactive by default."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REQUIRED = (
    "integrations/hosts/adobe/E3_FIXTURE_PROTOCOL.md",
    "integrations/hosts/eagle/E2_TEST_LIBRARY_PROTOCOL.md",
    "design-lab/config/tool-write-authorization.schema.json",
)


def main() -> int:
    errors: list[str] = []
    for relative in REQUIRED:
        path = ROOT / relative
        if not path.is_file():
            errors.append(f"missing {relative}")
    adobe = ROOT / REQUIRED[0]
    eagle = ROOT / REQUIRED[1]
    if adobe.is_file() and "inactive until a user grants" not in adobe.read_text(encoding="utf-8"):
        errors.append("Adobe protocol must require explicit authorization")
    if eagle.is_file() and "active personal library" not in eagle.read_text(encoding="utf-8"):
        errors.append("Eagle protocol must prohibit personal-library writes")
    try:
        json.loads((ROOT / REQUIRED[2]).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"invalid authorization schema: {exc}")
    for error in errors:
        print(f"FAIL {error}")
    print(f"TOOL_WRITE_PROTOCOLS={'PASS' if not errors else 'FAIL'}")
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
