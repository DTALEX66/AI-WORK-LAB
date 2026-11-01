"""NX-500: design core contract adaptation tests.

RED-GREEN coverage:
- DTCG token round-trip is lossless.
- Token lint catches unknown types / duplicates.
- A structured brief passes contract check and completes readback.
- Brief without colors/methods fails closed.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WF_SCRIPTS = ROOT / "packages" / "client-neutral-core" / "scripts"
sys.path.insert(0, str(WF_SCRIPTS))

from design_contract import DesignContractChecker, DesignToken, DtcgRoundTrip  # noqa: E402


class DesignContractTest(unittest.TestCase):
    def test_dtcg_roundtrip_lossless(self) -> None:
        tokens = [
            DesignToken("color.primary", "color", "#0f172a"),
            DesignToken("size.md", "dimension", 16),
        ]
        d = DtcgRoundTrip(tokens)
        self.assertTrue(d.roundtrip_lossless())

    def test_lint_catches_unknown_type(self) -> None:
        d = DtcgRoundTrip([DesignToken("x", "notatype", 1)])
        self.assertTrue(any("unknown type" in e for e in d.lint()))

    def test_lint_catches_duplicate(self) -> None:
        d = DtcgRoundTrip([DesignToken("color.a", "color", "1"), DesignToken("color.a", "color", "2")])
        self.assertTrue(any("duplicate" in e for e in d.lint()))

    def test_brief_passes_contract_and_readback(self) -> None:
        brief = (
            "# colors\ncolors: #0f172a, #10b981\n"
            "# methods\nmethod: anti-slop\n"
            "# gates\ngate: accessibility\n"
        )
        r = DesignContractChecker().evaluate(brief)
        self.assertTrue(r["passed"], r["errors"])
        self.assertTrue(r["readback"]["lossless"])

    def test_brief_without_colors_fails(self) -> None:
        r = DesignContractChecker().evaluate("# methods\nmethod: anti-slop\n")
        self.assertFalse(r["passed"])
        self.assertTrue(any("no tokens" in e for e in r["errors"]))

    def test_brief_without_methods_fails(self) -> None:
        r = DesignContractChecker().evaluate("# colors\ncolors: #0f172a\n")
        self.assertFalse(r["passed"])
        self.assertTrue(any("no methods" in e for e in r["errors"]))

    def test_readback_digest_stable(self) -> None:
        brief = "# colors\ncolors: #0f172a\n"
        r1 = DesignContractChecker().evaluate(brief)
        r2 = DesignContractChecker().evaluate(brief)
        self.assertEqual(r1["readback"]["brief_digest"], r2["readback"]["brief_digest"])


if __name__ == "__main__":
    unittest.main()
