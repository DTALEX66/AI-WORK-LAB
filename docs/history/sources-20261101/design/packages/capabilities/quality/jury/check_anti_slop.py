#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""DL-QLT-001: Visual Quality Jury deterministic checks (E1 gate).

Runs automated anti-slop / layout / readability signals on a target
HTML/CSS artifact. Human review is still required for PASS (E3+).
"""
import argparse
import re
import sys
from pathlib import Path

AI_DEFAULTS = [
    r"linear-gradient\([^)]*purple",          # AI purple gradients
    r"#(7c3aed|8b5cf6|a78bfa)",               # AI purple hexes
    r"backdrop-filter:\s*blur",               # glassmorphism everywhere
    r"font-family:\s*['\"]?Inter",            # Inter default
    r"color:\s*#(0f172a|1e293b|0a0f1e)",      # slate-900 family
]

ANTI_PATTERNS = [
    (r"var\(--[a-z0-9-]+\)", "token-locked", True),
    (r"font-style:\s*italic[^;]*;[^}]*}[^}]*h[1-6]", "italic-header", False),
    (r"overflow-x:\s*hidden", "overflow-x-hidden-allowed", True),
]


def check_file(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8", errors="replace")
    findings = []
    # AI defaults present
    for pat in AI_DEFAULTS:
        if re.search(pat, text, re.IGNORECASE):
            findings.append(f"AI-DEFAULT: {pat}")
    # anti-patterns
    for pat, label, must_exist in ANTI_PATTERNS:
        found = bool(re.search(pat, text, re.IGNORECASE))
        if must_exist and not found:
            findings.append(f"MISSING: {label}")
        if not must_exist and found:
            findings.append(f"VIOLATION: {label}")
    return findings


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("target", type=Path)
    ap.add_argument("--skip-prefixes", default="",
                    help="comma-separated relative path prefixes to skip (vendored/templates)")
    args = ap.parse_args()

    skip = [p for p in args.skip_prefixes.split(",") if p]

    target = args.target.resolve()
    if target.is_dir():
        files = [p for p in target.rglob("*") if p.suffix in {".html", ".css"}]
    else:
        files = [target]

    all_findings = []
    for f in files:
        rel = f.relative_to(target).as_posix() if target.is_dir() else f.name
        if any(rel.startswith(s) or rel.startswith("/" + s.lstrip("/")) for s in skip):
            continue
        for finding in check_file(f):
            all_findings.append(f"{f.name}: {finding}")

    for finding in sorted(all_findings):
        print(f"  {finding}")
    if all_findings:
        print(f"\nJURY_DETERMINISTIC=FAIL findings={len(all_findings)}")
        return 1
    print("\nJURY_DETERMINISTIC=OK (human review still required)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
