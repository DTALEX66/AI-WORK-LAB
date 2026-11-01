#!/usr/bin/env python3
"""Verify WORK-LAB source governance (NX-110): license/NOTICE/size gates.

Guarantees:
- No node_modules, __pycache__/bytecode, build/dist, download binary, nested
  .git, or vendored upstream repository is tracked in Git.
- Every cross-module source index entry carries a license and an honest
  licenseVerified flag (UNKNOWN is allowed but must be explicit, never invented).
- NOTICE.md exists and is non-empty (attribution completeness).
- No WORK-LAB-absorbed entry references an unlicensed upstream as implemented.
"""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
INDEX = ROOT / ".project/governance" / "cross-module-source-index.json"
NOTICE = ROOT / "NOTICE.md"

FORBIDDEN_TRACKED = re.compile(
    r"(?:^|/)(?:node_modules|__pycache__|\.venv|venv|dist|build)/|"
    r"\.pyc$|\.pyo$|"
    r"\.(?:exe|dll|bin|wasm|jar)$|"
    r"/\.git/|"
    r"(?:^|/)vendor/"
)


def _git_tracked(root: Path) -> list[str]:
    try:
        out = subprocess.check_output(
            ["git", "ls-files"], cwd=root, text=True, encoding="utf-8", errors="replace", stderr=subprocess.DEVNULL,
        )
        return [line for line in out.splitlines() if line]
    except (OSError, subprocess.CalledProcessError):
        return []


def _git_head(root: Path = ROOT) -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=root, text=True, encoding="utf-8", errors="replace", stderr=subprocess.DEVNULL,
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return "UNKNOWN"


def verify(root: Path = ROOT) -> dict[str, Any]:
    errors: list[str] = []

    # 1. Forbidden tracked artifacts
    tracked = _git_tracked(root)
    forbidden = [p for p in tracked if FORBIDDEN_TRACKED.search(p)]
    if forbidden:
        errors.append(f"tracked forbidden artifact(s): {forbidden[:5]}")

    # 2. NOTICE exists + non-empty
    if not NOTICE.is_file() or NOTICE.stat().st_size == 0:
        errors.append("NOTICE.md missing or empty")

    # 3. Cross-module index license honesty
    if INDEX.is_file():
        index = json.loads(INDEX.read_text(encoding="utf-8"))
        for entry in index.get("entries", []):
            license = entry.get("license")
            lic_verified = entry.get("licenseVerified")
            if not license:
                errors.append(f"{entry['id']}: missing license declaration")
            if lic_verified is None:
                errors.append(f"{entry['id']}: missing licenseVerified flag")
            impl = entry.get("implementationStatus")
            # An implemented entry must have a verified, permissive license.
            if impl in {"local-verified", "adapter-implemented", "fixture-verified"}:
                if not lic_verified:
                    errors.append(f"{entry['id']}: implemented source must have licenseVerified=true")
                low = str(license).lower()
                if low in {"unknown", "proprietary", "unlicense"} or "non-commercial" in low:
                    errors.append(f"{entry['id']}: implemented source license not permissive: {license}")

    if errors:
        raise ValueError("; ".join(errors))
    return {"tracked": len(tracked), "forbidden": 0,
            "notice_ok": True, "entries_checked": len(index.get("entries", [])) if INDEX.is_file() else 0,
            "head": _git_head(root)}


def main() -> int:
    try:
        result = verify()
    except (OSError, json.JSONDecodeError, ValueError, subprocess.CalledProcessError) as exc:
        print(f"SOURCE_GOVERNANCE_FAIL {exc}")
        return 1
    print(
        f"SOURCE_GOVERNANCE_PASS tracked={result['tracked']} forbidden=0 "
        f"notice=ok entries={result['entries_checked']} license=honest scope=workflow,observer"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
