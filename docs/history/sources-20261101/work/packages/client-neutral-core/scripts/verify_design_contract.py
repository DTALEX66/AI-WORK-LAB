#!/usr/bin/env python3
"""Design core contract verifier (NX-500).

Verifies DTCG token round-trip and DESIGN.md-style brief contract check with
readback. A structured brief must pass contract checks and complete a lossless
readback after delivery.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
WF_SCRIPTS = ROOT / "packages" / "client-neutral-core" / "scripts"
sys.path.insert(0, str(WF_SCRIPTS))

from design_contract import DesignContractChecker, DesignToken, DtcgRoundTrip  # noqa: E402


def verify() -> dict:
    errors: list[str] = []

    # 1. DTCG token round-trip is lossless.
    tokens = [
        DesignToken("color.primary", "color", "#0f172a"),
        DesignToken("color.accent", "color", "#10b981"),
        DesignToken("size.md", "dimension", 16),
    ]
    dtcg = DtcgRoundTrip(tokens)
    lint_errors = dtcg.lint()
    if lint_errors:
        errors.append(f"token lint failed: {lint_errors}")
    if not dtcg.roundtrip_lossless():
        errors.append("DTCG round-trip not lossless")

    # 2. A structured brief passes contract check + readback.
    brief = (
        "# colors\ncolors: #0f172a, #10b981\n"
        "# methods\nmethod: anti-slop critique\n"
        "# gates\ngate: responsive, gate: accessibility\n"
    )
    result = DesignContractChecker().evaluate(brief)
    if not result["passed"]:
        errors.append(f"brief contract check failed: {result['errors']}")
    if not result["readback"]["lossless"]:
        errors.append("brief readback not lossless")
    if not result["tokens"]:
        errors.append("brief produced no tokens")
    if not result["methods"]:
        errors.append("brief produced no methods")

    if errors:
        raise ValueError("; ".join(errors))
    return {"tokens": len(result["tokens"]), "methods": len(result["methods"]),
            "gates": len(result["quality_gates"]), "readback": True}


def main() -> int:
    try:
        result = verify()
    except (ValueError, ImportError) as exc:
        print(f"DESIGN_CONTRACT_FAIL {exc}")
        return 1
    print(
        f"DESIGN_CONTRACT_PASS tokens={result['tokens']} methods={result['methods']} "
        f"gates={result['gates']} readback=lossless dtcg=roundtrip"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
