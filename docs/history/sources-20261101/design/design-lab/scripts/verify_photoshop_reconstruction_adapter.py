#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Static verifier for the no-network Photoshop UXP reconstruction adapter."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ROOT = PROJECT_ROOT / "integrations" / "hosts" / "adobe" / "photoshop-reconstruction"


@dataclass(frozen=True)
class StructuralResult:
    ok: bool
    errors: tuple[str, ...]


def verify_structural(root: Path = DEFAULT_ROOT) -> StructuralResult:
    errors: list[str] = []
    try:
        manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
        source = (root / "index.js").read_text(encoding="utf-8")
    except (OSError, ValueError) as exc:
        return StructuralResult(False, (str(exc),))
    if manifest.get("manifestVersion") != 5:
        errors.append("UXP manifest version must be 5")
    if "https://*" in json.dumps(manifest, sort_keys=True):
        errors.append("UXP manifest has unrestricted network permission")
    for token in ("executeAsModal", "executionContext.isCancelled", "prepareRunRelativeLayers"):
        if token not in source:
            errors.append(f"required UXP token missing: {token}")
    return StructuralResult(not errors, tuple(errors))
