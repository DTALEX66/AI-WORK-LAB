#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""DL-GOV-130: fail-closed checks for active product drift."""
from __future__ import annotations

import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
ACTIVE_DOCS = (
    "README.md",
    "docs/current/PRODUCT_DEFINITION.md",
    "docs/current/PROJECT_DEFINITION.md",
    "docs/architecture/ARCHITECTURE.md",
    "docs/architecture/BOUNDARY_CONTRACT.md",
    "docs/current/ROADMAP.md",
    "design-lab/README.md",
    "design-lab/ARCHITECTURE_V3.md",
    "docs/decisions/NEUTRALITY_POLICY.md",
)
FORBIDDEN_DEFAULT_HOST = re.compile(
    r"(?:current reference host|当前参考宿主|默认宿主|Open Design 是主入口|宿主 Open Design 是主角)",
    re.IGNORECASE,
)
OVERSTATED_EARLY_EVIDENCE = re.compile(r"\b(?:stable|operable|production-ready)\b", re.IGNORECASE)


def text(path: str) -> str:
    return (REPO / path).read_text(encoding="utf-8")


def findings() -> list[str]:
    errors: list[str] = []
    for relative in ACTIVE_DOCS:
        path = REPO / relative
        if not path.exists():
            errors.append(f"missing active contract: {relative}")
            continue
        if FORBIDDEN_DEFAULT_HOST.search(text(relative)):
            errors.append(f"default-host language: {relative}")

    manifest = json.loads((REPO / "design-lab/config/product-manifest.json").read_text(encoding="utf-8"))
    product = manifest.get("product", {})
    for field in ("name", "positioning"):
        value = str(product.get(field, ""))
        if FORBIDDEN_DEFAULT_HOST.search(value):
            errors.append(f"default-host language in product manifest: {field}")

    registry = json.loads((REPO / "integrations/adapter-registry.json").read_text(encoding="utf-8"))
    for adapter in registry.get("adapters", []):
        level = str(adapter.get("evidence", {}).get("level", "E0"))
        note = str(adapter.get("evidence", {}).get("note", ""))
        if level in {"E0", "E1"} and OVERSTATED_EARLY_EVIDENCE.search(note):
            errors.append(f"overstated {level} adapter evidence: {adapter.get('adapter_id')}")
        if not all(isinstance(cap, dict) for cap in adapter.get("capabilities", [])):
            errors.append(f"noncanonical capabilities: {adapter.get('adapter_id')}")
    return errors


def main() -> int:
    errors = findings()
    for error in errors:
        print(f"FAIL {error}")
    print(f"PROJECT_DRIFT={'PASS' if not errors else 'FAIL'} findings={len(errors)}")
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
