"""Contract verification for the single config-ownership registry (WL3-200)."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
REGISTRY = ROOT / "config/config-ownership.json"
EXPECTED_LAYERS = {
    "UPSTREAM_OFFICIAL", "USER_OVERLAY", "PROJECT_OVERLAY", "TASK_EPHEMERAL",
    "PLATFORM_INTERNAL", "RUNTIME_EPHEMERAL", "SECRET", "COSMETIC",
}
EXPECTED_MODES = {"MANAGE", "OBSERVE", "IGNORE", "FORBIDDEN"}


def classify(field: dict[str, Any]) -> dict[str, Any]:
    layer = str(field.get("layer", ""))
    mode = str(field.get("mode", ""))
    if mode not in EXPECTED_MODES or layer not in EXPECTED_LAYERS:
        return {"field": field.get("path"), "mode": "OBSERVE", "quarantine": True, "reason": "unknown-layer-or-mode"}
    if layer == "SECRET":
        return {"field": field.get("path"), "mode": "FORBIDDEN", "quarantine": True, "reason": "secret-layer"}
    return {"field": field.get("path"), "mode": mode, "quarantine": False, "reason": None}


def verify() -> int:
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    if registry.get("schema_version") != "workflow/config-ownership/v2":
        print("CONFIG_OWNERSHIP_FAIL schema-version")
        return 1
    if not registry.get("single_authority"):
        print("CONFIG_OWNERSHIP_FAIL not-single-authority")
        return 1
    layers = set(registry.get("layers", {}))
    if layers != EXPECTED_LAYERS:
        print("CONFIG_OWNERSHIP_FAIL layers", sorted(EXPECTED_LAYERS - layers))
        return 1
    modes = set(registry.get("operation_modes", []))
    if modes != EXPECTED_MODES:
        print("CONFIG_OWNERSHIP_FAIL modes")
        return 1
    unknown_default = registry.get("default_unknown", {})
    if unknown_default.get("mode") != "OBSERVE" or not unknown_default.get("quarantine"):
        print("CONFIG_OWNERSHIP_FAIL unknown-default-not-quarantine")
        return 1
    fields = registry.get("fields", [])
    if not fields:
        print("CONFIG_OWNERSHIP_FAIL no-fields")
        return 1
    forbidden = sum(1 for field in fields if field.get("layer") == "SECRET")
    if not forbidden:
        print("CONFIG_OWNERSHIP_FAIL no-secret-fields")
        return 1
    paths = [field.get("path") for field in fields]
    if len(paths) != len(set(paths)):
        print("CONFIG_OWNERSHIP_FAIL duplicate-paths")
        return 1
    print(
        f"CONFIG_OWNERSHIP_PASS layers={len(layers)} modes={len(modes)} "
        f"fields={len(fields)} forbidden={forbidden}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(verify())
