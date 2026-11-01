#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""DL-DOM-110: enforce the three structural-only golden-contract baselines."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CASES = {
    "uiux-design": ("benchmarks/settings-accessibility-golden/brief.json", "failures/missing-accessibility-state-fails.json"),
    "ecommerce-design": ("benchmarks/ecommerce-hero-contract/brief.json", "failures/missing-rights-fails.json"),
    "brand-design": ("benchmarks/brand-system-contract/brief.json", "failures/protected-signature-fails.json"),
}


def main() -> int:
    errors: list[str] = []
    for domain, (brief_rel, failure_rel) in CASES.items():
        pack = ROOT / "domain-packs" / domain
        brief_path, failure_path = pack / brief_rel, pack / failure_rel
        for path in (brief_path, failure_path):
            if not path.is_file():
                errors.append(f"{domain}: missing {path.relative_to(pack)}")
        if brief_path.is_file():
            try:
                brief = json.loads(brief_path.read_text(encoding="utf-8"))
                if brief.get("constraints", {}).get("evidenceLevel") not in (None, "E1"):
                    errors.append(f"{domain}: structural brief must not exceed E1")
                if brief.get("constraints", {}).get("realToolExecution") is True:
                    errors.append(f"{domain}: structural brief must not claim real tool execution")
            except json.JSONDecodeError as exc:
                errors.append(f"{domain}: invalid brief JSON ({exc})")
        if failure_path.is_file():
            try:
                failure = json.loads(failure_path.read_text(encoding="utf-8"))
                if failure.get("expectedResult") != "FAIL":
                    errors.append(f"{domain}: failure case must expect FAIL")
            except json.JSONDecodeError as exc:
                errors.append(f"{domain}: invalid failure JSON ({exc})")
    for error in errors:
        print(f"FAIL {error}")
    print(f"GOLDEN_CONTRACTS={'PASS' if not errors else 'FAIL'} domains={len(CASES)}")
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
