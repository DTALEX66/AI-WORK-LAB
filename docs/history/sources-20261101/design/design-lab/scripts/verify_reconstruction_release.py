#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Validate a reconstruction release claim and optionally write its current projection."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


DESIGN_LAB = Path(__file__).resolve().parents[1]
PROJECT_ROOT = DESIGN_LAB.parent
sys.path.insert(0, str(DESIGN_LAB))
sys.path.insert(0, str(PROJECT_ROOT / "packages" / "capabilities"))

from reconstruction.release import EvidenceError, current_projection, validate_release  # noqa: E402


def _head() -> str:
    result = subprocess.run(["git", "-C", str(PROJECT_ROOT), "rev-parse", "HEAD"], check=True, capture_output=True, text=True, encoding="utf-8", errors="replace")
    return result.stdout.strip()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("evidence", type=Path)
    parser.add_argument("--write-projection", action="store_true")
    args = parser.parse_args()
    try:
        evidence = json.loads(args.evidence.read_text(encoding="utf-8"))
        head = _head()
        validate_release(evidence, head)
        projection = current_projection(evidence, head)
        if args.write_projection:
            target = PROJECT_ROOT / "reports" / "current" / "RECONSTRUCTION_CAPABILITY.json"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(json.dumps(projection, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    except (OSError, json.JSONDecodeError, subprocess.CalledProcessError, EvidenceError) as exc:
        print(f"RECONSTRUCTION_RELEASE=FAIL reason={exc}")
        return 1
    print(f"RECONSTRUCTION_RELEASE=PASS sha={head}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
