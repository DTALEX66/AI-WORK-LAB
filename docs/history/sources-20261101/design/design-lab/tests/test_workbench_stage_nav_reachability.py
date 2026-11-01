# SPDX-License-Identifier: MIT
"""The stage navigation must show every stage, not make it scroll-searchable.

`design-lab/tests/e2e/audit_workbench_overflow.mjs` counts anything inside an
`overflow-x:auto` ancestor as reachable (`scrollOk++`, line 66), which is correct for
`.table-wrap` and the mobile `.app-nav` and wrong for primary navigation: nine stages
overflowed the row at 1280 and the last two sat past the right edge with no scrollbar
and no fade, so the gate reported clean while the rendered page hid its own tail.
That is recorded in `docs/audits/DESIGN-LAB-WORKBENCH-VISUAL-AUDIT-20261006.md`.

These tests close the gap structurally, because "reachable by hunting" is not the
property that matters for navigation -- "visible on arrival" is.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STYLE = ROOT / "apps" / "workbench" / "style.css"

HIDDEN_BY_SCROLL = re.compile(r"overflow-x\s*:\s*(?:auto|scroll)")
FORCED_ONE_LINE = re.compile(r"flex-wrap\s*:\s*nowrap")
WRAPS = re.compile(r"flex-wrap\s*:\s*wrap")
COMMENT = re.compile(r"/\*.*?\*/", re.S)


def strip_comments(css: str) -> str:
    """A rule's selector text includes whatever comment precedes it, so matching
    without this finds zero blocks and every assertion below passes vacuously."""
    return COMMENT.sub("", css)


def rule_body(css: str, selector: str) -> list[str]:
    """Every declaration block whose selector list contains `selector` exactly."""
    blocks = []
    for match in re.finditer(r"([^{}]+)\{([^{}]*)\}", strip_comments(css), re.S):
        names = [n.strip() for n in match.group(1).split(",")]
        if selector in names:
            blocks.append(match.group(2))
    return blocks


def violations(body: str) -> list[str]:
    found = []
    if HIDDEN_BY_SCROLL.search(body):
        found.append("overflow-x:auto|scroll puts stages behind a scroll with no affordance")
    if FORCED_ONE_LINE.search(body):
        found.append("flex-wrap:nowrap forces one line that nine stages cannot fit")
    if not WRAPS.search(body):
        found.append("no flex-wrap:wrap, so nothing brings the tail back into view")
    return found


class StageNavRuleIsFound(unittest.TestCase):
    """Positive control: an assertion over zero matches proves nothing."""

    def setUp(self) -> None:
        self.css = STYLE.read_text(encoding="utf-8")
        self.bodies = rule_body(self.css, ".stage-nav")

    def test_the_nav_is_styled_by_exactly_one_block(self) -> None:
        self.assertEqual(len(self.bodies), 1,
                         "the selector moved or duplicated; this gate is no longer watching "
                         "the rule that decides whether stages are reachable")

    def test_the_block_actually_declares_a_flex_row(self) -> None:
        self.assertTrue(self.bodies, "no rule matched, so the checks below are vacuous")
        self.assertIn("display:flex", self.bodies[0].replace(" ", ""))


class StageNavStaysVisible(unittest.TestCase):
    def test_no_violation_shape_in_the_shipped_rule(self) -> None:
        bodies = rule_body(STYLE.read_text(encoding="utf-8"), ".stage-nav")
        self.assertEqual(len(bodies), 1)
        self.assertEqual(violations(bodies[0]), [],
                         "the stage nav can hide its tail again")

    def test_the_violation_shape_is_detected(self) -> None:
        """Falsification: the exact bytes that shipped broken must be rejected, or the
        test above is asserting nothing about a rule that could regress."""
        before_fix = ("display:flex;gap:6px;list-style:none;padding:0;margin:16px 0 0;"
                      "overflow-x:auto;flex-wrap:nowrap;min-height:38px;")
        self.assertEqual(len(violations(before_fix)), 3,
                         "the matcher no longer recognises the shipped-broken rule")

    def test_a_scrollable_nav_without_wrap_is_still_a_violation(self) -> None:
        self.assertTrue(violations("display:flex;overflow-x:auto"))
        self.assertEqual(violations("display:flex;flex-wrap:wrap"), [])


if __name__ == "__main__":
    unittest.main()
