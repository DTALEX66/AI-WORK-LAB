#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Static safety verifier for the bounded Illustrator JSX reconstruction adapter."""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_JSX = PROJECT_ROOT / "integrations" / "hosts" / "adobe" / "illustrator" / "reconstruction-assemble.jsx"
REQUIRED_OPERATIONS = (
    "createDocument", "createLayer", "placePath", "placeText", "placeRaster", "applyMask",
    "saveAI", "exportSVG", "reopen", "readback", "exportPNG",
)
FORBIDDEN = ("executeMenu" + "Command", "system.call" + "System")


@dataclass(frozen=True)
class StructuralResult:
    ok: bool
    required_operations: tuple[str, ...]
    errors: tuple[str, ...]


def verify_structural(path: Path = DEFAULT_JSX) -> StructuralResult:
    try:
        source = path.read_text(encoding="utf-8")
    except OSError as exc:
        return StructuralResult(False, REQUIRED_OPERATIONS, (str(exc),))
    errors: list[str] = []
    for token in FORBIDDEN:
        if token in source:
            errors.append(f"forbidden JSX token: {token}")
    for token in ("function assertInside", "app.documents.add", *REQUIRED_OPERATIONS):
        if token not in source:
            errors.append(f"required JSX token missing: {token}")
    return StructuralResult(not errors, REQUIRED_OPERATIONS, tuple(errors))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--structural", action="store_true")
    parser.add_argument("--jsx", type=Path, default=DEFAULT_JSX)
    args = parser.parse_args()
    result = verify_structural(args.jsx)
    print(f"ILLUSTRATOR_RECONSTRUCTION_ADAPTER={'PASS' if result.ok else 'FAIL'} errors={len(result.errors)}")
    for error in result.errors:
        print(f"ERROR {error}")
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
