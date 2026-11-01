#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Validate the tool adapter registry (ODA4-0206).

Checks every adapter declares capabilities with truthful status; large tools
require process isolation; missing capabilities are not presented as available.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
REGISTRY = REPO.parent / "integrations" / "adapter-registry.json"

LARGE_TOOLS = {"Blender", "FFmpeg", "3D", "video"}


def main() -> int:
    data = json.loads(REGISTRY.read_text(encoding="utf-8"))
    errors: list[str] = []
    for ad in data["adapters"]:
        tool = ad.get("tool", "")
        if ad.get("status") == "available":
            for cap in ad.get("capabilities", []):
                if not cap.get("supported"):
                    errors.append(f"{tool}: status=available but capability {cap.get('name')} unsupported")
        # large tools must be process-isolated
        if any(t in tool for t in LARGE_TOOLS):
            if ad.get("mode") != "process-isolated":
                errors.append(f"{tool}: large tool requires process-isolated mode")
            if ad.get("status") == "available":
                errors.append(f"{tool}: large tool not yet proven available (must be honest)")
    for e in errors:
        print("ERROR", e)
    print(f"ADAPTER_REGISTRY={'PASS' if not errors else 'FAIL'} adapters={len(data['adapters'])}")
    return 0 if not errors else 1


if __name__ == "__main__":
    sys.exit(main())
