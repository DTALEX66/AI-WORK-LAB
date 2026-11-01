# SPDX-License-Identifier: MIT
"""The sidebar must stay pinned to the viewport, and a counter row must fill it.

Both rules were found by reading rendered pixels at 1280 (visual audit section 14),
which no overflow or contrast gate can express: a stretched grid item is not
overflowing, it is simply taller than the screen, and a 4-column track holding three
cards leaves a hole rather than a scrollbar. The assertions are pinned to the exact
forms that broke them so a future edit back to those forms fails here.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

CSS = (Path(__file__).resolve().parents[2] / "apps" / "workbench" / "style.css"
       ).read_text(encoding="utf-8")


def rules(selector: str) -> list[str]:
    """Every declaration block for `selector` written at column 0, in source order.

    Media-query copies are excluded on purpose: they are intended cascade. A class
    may legitimately be declared twice (test_workbench_css_single_definition.py
    sanctions some), and the *later* block wins, so a guard that reads only the
    first one protects a dead declaration.
    """
    return re.findall(r"^" + re.escape(selector) + r"\{(.*?)\}", CSS,
                      re.DOTALL | re.MULTILINE)


def effective(selector: str, prop: str) -> str:
    """The winning value of `prop` for `selector`: its last declaration in source order."""
    found = [m.group(1).strip()
             for block in rules(selector)
             for m in re.finditer(re.escape(prop) + r"\s*:\s*([^;]+)", block)]
    assert found, f"{selector} never declares {prop}"
    return found[-1]


class SidebarPinningTests(unittest.TestCase):
    def test_sidebar_is_pinned_to_the_viewport(self):
        rule = rules(".sidebar")[0]
        self.assertIn("position:sticky", rule)
        self.assertIn("height:100vh", rule)
        self.assertIn("overflow-y:auto", rule)

    def test_the_broken_form_is_rejected(self):
        # `position:relative` + min-height:100vh is what shipped until 2026-10-07: the
        # grid item stretched to the document height, so `.sidebar-footer`'s
        # margin-top:auto parked the identity readback below the fold on the four
        # routes taller than the viewport (dashboard, project detail, brand systems,
        # settings).
        self.assertNotIn("min-height:100vh", rules(".sidebar")[0])

    def test_the_mobile_drawer_stays_a_fixed_overlay(self):
        # <=840px the sidebar is an off-canvas drawer; making it sticky there would
        # leave it painted behind the opened panel.
        drawer = re.search(r"\.sidebar\{([^}]*position:fixed[^}]*)\}", CSS)
        self.assertIsNotNone(drawer, "the off-canvas drawer rule disappeared")
        self.assertIn("transform:translateX(-100%)", CSS)


class CounterRowTests(unittest.TestCase):
    def test_kpi_track_follows_the_card_count(self):
        # The B10 replica block already asked for auto-fit; a later block overrode it
        # with a fixed 4, which left a ~240px hole on the routes holding three
        # counters (brand systems, deliverables). Only the winning declaration can
        # carry this assertion.
        self.assertIn("auto-fit", effective(".kpi-grid", "grid-template-columns"))

    def test_no_kpi_definition_forces_four_columns(self):
        for block in rules(".kpi-grid"):
            self.assertNotIn("repeat(4", block)


class MobileNavCueTests(unittest.TestCase):
    """The legacy bottom nav's continuation cue must stay painted while it scrolls.

    `::after` on a scroll container is positioned against the *content* box, so an
    absolutely positioned cue travels with the items and disappears mid-scroll. That
    was measured, not assumed: arrow pixels at scrollLeft 0/300/600 came out
    13/0/0 with 670/370/70px of menu still off-screen, and 10/10/10 once the cue was
    a sticky flex item. A class- or aria-presence check goes green over both builds.
    """

    def cue_rule(self) -> str:
        match = re.search(r"\.app-nav\.has-scroll-more::after\{(.*?)\}", CSS, re.DOTALL)
        self.assertIsNotNone(match, "the continuation-cue rule was removed")
        return match.group(1)

    def test_cue_is_pinned_to_the_scrollport_not_the_content(self):
        rule = self.cue_rule()
        self.assertIn("position:sticky", rule)
        self.assertIn("right:0", rule)
        self.assertNotIn("position:absolute", rule)

    def test_cue_cannot_swallow_a_tap(self):
        # It overlays the last item, so it must stay out of the hit test.
        self.assertIn("pointer-events:none", self.cue_rule())


if __name__ == "__main__":
    unittest.main()
