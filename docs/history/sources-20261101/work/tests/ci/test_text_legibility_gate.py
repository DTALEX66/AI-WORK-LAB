"""Gate: the legibility probe judges the measurement, and the maths behind it is testable without a browser.

DESIGN.md promises a 12px floor and AA contrast in both themes. This test pins the arithmetic that turns
that promise into a verdict — colour parsing, alpha compositing, the large-text exemption, and the
check list — against values derivable by hand. The browser only produces the raw computed styles; every
number is recomputed here, so a wrong instrument is caught by a failing test rather than by a screenshot.

Two planted faults are deliberate and are the reason this file exists:
  * translucent text must not be scored as opaque (the first version of this maths did, and reported
    21:1 for text that renders at 3.98:1);
  * a floor exception that matches nothing must fail, or the allowlist rots into a permanent excuse.
"""
from __future__ import annotations

import importlib.util
import json
import re
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "audit" / "text_legibility_via_cdp.py"

spec = importlib.util.spec_from_file_location("text_legibility", SCRIPT)
legibility = importlib.util.module_from_spec(spec)
spec.loader.exec_module(legibility)  # type: ignore[attr-defined]

WHITE = "rgb(255, 255, 255)"
BLACK = "rgb(0, 0, 0)"


def node(path="div.panel > span.body", text="hello", size=14.0, weight="400",
         color=BLACK, bg=None, opacity=1.0, gradient=False) -> dict:
    return {"text": text, "path": path, "size": size, "weight": weight, "color": color,
            "bg": bg if bg is not None else [WHITE, WHITE], "opacity": opacity,
            "gradient": gradient, "ariaHidden": None, "role": None, "rect": {"w": 80, "h": 18}}


def clean_harvest(count: int = 34, theme: str = "dark") -> dict:
    """A harvest shaped like the real `view=full` screen after the type-floor sweep: nothing sub-12px.

    It deliberately contains no below-floor node, because the shipped `FLOOR_EXCEPTIONS` is empty and
    `no_stale_floor_exception` reads that list against the measurement. A fixture that excused itself
    with a role the product no longer ships would hide the very check this file exists to prove.
    """
    nodes = [node(path=f"div.view{i % 3} > span.body", text=f"label {i}")
             for i in range(count)]
    return {"viewport": "1280x820", "theme": theme, "pageBackground": WHITE,
            "htmlBackground": WHITE, "nodes": nodes}


def checks_of(verdict: dict) -> dict:
    return {c["check"]: c for c in verdict["checks"]}


class ColourParsingTests(unittest.TestCase):
    def test_rgb_and_rgba_forms_are_read(self) -> None:
        self.assertEqual(legibility.parse_color("rgb(14, 171, 188)"), (14.0, 171.0, 188.0, 1.0))
        self.assertEqual(legibility.parse_color("rgb(14 171 188 / 0.5)"), (14.0, 171.0, 188.0, 0.5))
        self.assertEqual(legibility.parse_color("rgba(0, 0, 0, 0.25)"), (0.0, 0.0, 0.0, 0.25))

    def test_srgb_function_channels_are_fractions_not_bytes(self) -> None:
        """`color(srgb .957 .969 .98)` is #F4F7FA. Read as 0-255 it would be near-black, and every
        contrast on a skin-authored surface would be wrong in the safe-looking direction."""
        parsed = legibility.parse_color("color(srgb 0.957 0.969 0.98)")
        self.assertIsNotNone(parsed)
        self.assertAlmostEqual(parsed[0], 244.0, delta=0.6)
        self.assertAlmostEqual(parsed[2], 250.0, delta=0.6)
        self.assertEqual(parsed[3], 1.0)
        alpha = legibility.parse_color("color(srgb 0.5 0.5 0.5 / 0.72)")
        self.assertAlmostEqual(alpha[3], 0.72)

    def test_chromes_oklab_serialisations_are_not_unknowns(self) -> None:
        """Chrome hands back `oklab(...)` for some computed colours the source never wrote that way.
        Ten measurable nodes reported \"cannot compute\" until this was handled — and an UNKNOWN is a
        gate failure, so the census could not go green for reasons that had nothing to do with the UI."""
        black = legibility.parse_color("oklab(0 0 0)")
        white = legibility.parse_color("oklab(1 0 0)")
        dim = legibility.parse_color("oklab(0.3 0 0)")
        bright = legibility.parse_color("oklab(0.7 0 0)")
        assert black is not None and white is not None and dim is not None and bright is not None
        self.assertEqual(black[:3], (0.0, 0.0, 0.0))
        self.assertAlmostEqual(white[0], 255.0, delta=0.6)
        self.assertLess(legibility.relative_luminance(dim[:3]),
                        legibility.relative_luminance(bright[:3]))
        # The value the shipped page actually reported, as a dark translucent surface.
        surface = legibility.parse_color("oklab(0.217044 -0.0124847 -0.0339877 / 0.68)")
        assert surface is not None
        self.assertAlmostEqual(surface[3], 0.68)
        self.assertLess(legibility.relative_luminance(surface[:3]), 0.05)
        # `oklab(L 0 0)` is not a neutral grey — the LMS white point is not equal-channel — so no
        # "should be 128" assertion belongs here. Round-tripping oklch against oklab is the check
        # that the two share one inverse.
        warm = legibility.parse_color("oklab(0.6 0 0)")
        assert warm is not None
        self.assertGreater(warm[0], warm[1])

    def test_oklch_round_trips_to_the_same_grey_as_oklab(self) -> None:
        from_chroma = legibility.parse_color("oklch(0.6 0 0deg)")
        from_square = legibility.parse_color("oklab(0.6 0 0)")
        assert from_chroma is not None and from_square is not None
        for index in range(3):
            self.assertAlmostEqual(from_chroma[index], from_square[index], delta=0.6)

    def test_unreadable_values_return_none_instead_of_a_guess(self) -> None:
        self.assertIsNone(legibility.parse_color("hsl(12, 50%, 50%)"))
        self.assertIsNone(legibility.parse_color(""))
        self.assertIsNone(legibility.parse_color("rgb(1 2)"))
        self.assertEqual(legibility.parse_color("transparent"), (0.0, 0.0, 0.0, 0.0))


class ContrastMathsTests(unittest.TestCase):
    def test_black_on_white_is_21_and_symmetric(self) -> None:
        self.assertEqual(legibility.contrast_ratio((0, 0, 0), (255, 255, 255)), 21.0)
        self.assertEqual(legibility.contrast_ratio((255, 255, 255), (0, 0, 0)), 21.0)

    def test_documented_reference_pair_reproduces(self) -> None:
        """DESIGN.md quotes #EEF6FC on #050D16 = 17.87:1, computed here independently of the browser."""
        self.assertEqual(legibility.contrast_ratio((238, 246, 252), (5, 13, 22)), 17.87)

    def test_translucent_text_is_composited_not_assumed_opaque(self) -> None:
        """The planted fault. 50% black on white paints #7F7F7F: 3.98:1, which fails AA. Scored as
        opaque black it reads 21:1 and passes — a green gate over text a user cannot read."""
        bg = legibility.composite_backdrop([WHITE], WHITE)[0]
        painted = legibility.over((0.0, 0.0, 0.0, 0.5), bg)
        self.assertAlmostEqual(painted[0], 127.5, delta=0.01)
        self.assertEqual(legibility.contrast_ratio(painted, bg), 3.98)
        scored = legibility.node_contrast(node(color="rgba(0, 0, 0, 0.5)"), WHITE)
        self.assertFalse(scored["pass"])
        self.assertEqual(scored["renderedRatio"], 3.98)

    def test_backdrop_stack_composites_root_first(self) -> None:
        """Element layer over ancestor layer over page: 50% red on opaque blue, then that on white."""
        rgb, ok = legibility.composite_backdrop(["rgba(255, 0, 0, 0.5)", WHITE], WHITE)
        self.assertTrue(ok)
        self.assertAlmostEqual(rgb[0], 255.0, delta=0.01)
        self.assertAlmostEqual(rgb[1], 127.5, delta=0.01)
        self.assertAlmostEqual(rgb[2], 127.5, delta=0.01)

    def test_transparent_layers_are_skipped_not_counted_as_paint(self) -> None:
        rgb, ok = legibility.composite_backdrop(["transparent", "rgba(0,0,0,0)"], "rgb(5, 13, 22)")
        self.assertTrue(ok)
        self.assertEqual(rgb, (5.0, 13.0, 22.0))

    def test_an_unparsable_layer_is_unknown_not_a_silent_base_colour(self) -> None:
        rgb, ok = legibility.composite_backdrop(["hsl(0,0%,50%)"], WHITE)
        self.assertFalse(ok)
        self.assertIsNone(rgb)

    def test_ancestor_opacity_reaches_the_measured_ratio(self) -> None:
        opaque = legibility.node_contrast(node(), WHITE)["renderedRatio"]
        faded = legibility.node_contrast(node(opacity=0.5), WHITE)["renderedRatio"]
        self.assertEqual(opaque, 21.0)
        self.assertLess(faded, opaque)
        self.assertEqual(faded, 3.98)

    def test_invisible_foreground_is_a_failure_not_a_zero_contrast_pass(self) -> None:
        scored = legibility.node_contrast(node(color="rgba(0, 0, 0, 0)"), WHITE)
        self.assertEqual(scored["status"], "invisible-foreground")
        self.assertFalse(scored["pass"])


class LargeTextExemptionTests(unittest.TestCase):
    def test_thresholds_follow_the_written_rule(self) -> None:
        self.assertEqual(legibility.required_ratio(14.0, "400"), 4.5)
        self.assertEqual(legibility.required_ratio(18.66, "600"), 4.5)
        self.assertEqual(legibility.required_ratio(18.66, "700"), 3.0)
        # 14pt bold is the floor of "large", so anything at least that size and bold stays exempt.
        self.assertEqual(legibility.required_ratio(23.9, "800"), 3.0)
        self.assertEqual(legibility.required_ratio(23.9, "400"), 4.5)
        self.assertEqual(legibility.required_ratio(24.0, "400"), 3.0)

    def test_a_large_node_in_the_exemption_band_is_accepted_while_a_small_one_is_not(self) -> None:
        """#787878 on white measures 4.42:1: under the 4.5 rule for body text, over the 3.0 rule the
        same colour earns once it is large. A gate that ignores the exemption fails real headings."""
        big = legibility.node_contrast(node(size=26.0, color="rgb(120, 120, 120)"), WHITE)
        small = legibility.node_contrast(node(size=14.0, color="rgb(120, 120, 120)"), WHITE)
        self.assertEqual(big["renderedRatio"], small["renderedRatio"])
        self.assertEqual(small["renderedRatio"], 4.42)
        self.assertTrue(big["pass"])
        self.assertFalse(small["pass"])


class VerdictTests(unittest.TestCase):
    def setUp(self) -> None:
        self.v = legibility.verdict("dark", clean_harvest())
        self.checks = checks_of(self.v)

    def test_a_clean_harvest_passes_and_names_every_check(self) -> None:
        self.assertTrue(self.v["passed"], json.dumps(self.v["checks"], ensure_ascii=False))
        self.assertEqual(set(self.checks), {"harvest_is_dense_enough", "theme_actually_applied",
                                            "no_text_below_the_type_floor", "no_unparsable_colour",
                                            "every_text_node_meets_AA", "disabled_text_is_still_legible",
                                            "no_stale_floor_exception"})

    def test_a_sub_floor_paragraph_fails_the_floor_check_and_names_it(self) -> None:
        harvest = clean_harvest()
        harvest["nodes"][3] = node(path="p.token-panel", text="成本质量由后端投影", size=10.0)
        v = legibility.verdict("dark", harvest)
        failed = checks_of(v)["no_text_below_the_type_floor"]
        self.assertFalse(failed["pass"])
        self.assertIn("10.0px", failed["detail"])
        self.assertIn("成本质量", failed["detail"])

    def test_an_aa_failure_fails_with_the_measured_number(self) -> None:
        harvest = clean_harvest()
        harvest["nodes"][5] = node(path="span.brand-sub", text="WORK-LAB", color="rgb(120, 120, 120)")
        v = legibility.verdict("dark", harvest)
        failed = checks_of(v)["every_text_node_meets_AA"]
        self.assertFalse(failed["pass"])
        self.assertIn("4.42:1", failed["detail"])

    def test_a_thin_harvest_is_not_a_pass(self) -> None:
        v = legibility.verdict("dark", clean_harvest(count=4))
        self.assertFalse(checks_of(v)["harvest_is_dense_enough"]["pass"])

    def test_an_unapplied_theme_is_failing_not_green(self) -> None:
        """?theme=light that never reaches <html> would otherwise report a whole dark palette as light."""
        v = legibility.verdict("light", clean_harvest(theme="dark"))
        self.assertFalse(checks_of(v)["theme_actually_applied"]["pass"])

    def test_an_unparsable_computed_colour_is_unknown_and_red(self) -> None:
        harvest = clean_harvest()
        harvest["nodes"][7] = node(path="span.weird", text="x", color="hsl(0, 0%, 0%)")
        v = legibility.verdict("dark", harvest)
        self.assertFalse(checks_of(v)["no_unparsable_colour"]["pass"])

    def test_a_declared_role_is_permitted_below_the_floor_but_still_counted(self) -> None:
        harvest = clean_harvest()
        harvest["nodes"][2] = node(path="span.winctl-zoom", text="125%", size=10.0)
        with mock.patch.object(legibility, "FLOOR_EXCEPTIONS",
                               [(r"\.winctl-zoom\b", "zoom readout")]):
            v = legibility.verdict("dark", harvest)
        self.assertTrue(checks_of(v)["no_text_below_the_type_floor"]["pass"])
        # The exception lets the node pass the floor check; it never hides the node from the count
        # printed in the receipt, so a growing list of "decorative" roles stays visible in the diff.
        self.assertEqual(v["counts"]["belowFloor"], 1)
        self.assertEqual(v["counts"]["floorExceptions"], 1)
        self.assertEqual(v["counts"]["unexceptedBelowFloor"], 0)

    def test_an_exception_that_matches_nothing_is_reported_as_stale(self) -> None:
        """Without this, every entry ever added to the allowlist keeps working after the rule it
        excuses is fixed, and the next violation is waved through by a stranger's exception."""
        with mock.patch.object(legibility, "FLOOR_EXCEPTIONS",
                               [(r"\.gone-away\b", "nothing on screen matches this")]):
            v = legibility.verdict("dark", clean_harvest())
        self.assertFalse(checks_of(v)["no_stale_floor_exception"]["pass"])
        self.assertIn("gone-away", checks_of(v)["no_stale_floor_exception"]["detail"])

    def test_the_shipped_floor_allowlist_is_empty_and_stays_that_way_unless_challenged(self) -> None:
        """Every role that claimed a sub-12px exemption turned out to be text a user must read: the
        zoom readout is the only place the level appears, the strip is the only first-frame answer,
        the brand caption names the product. Adding an entry here is a deliberate act, so it is
        asserted rather than assumed — and any entry must carry a reason.
        """
        self.assertEqual(legibility.FLOOR_EXCEPTIONS, [],
                         "a floor exception now ships; it must name a decorative role that repeats "
                         "information available elsewhere, or come out")

    def test_a_stale_pattern_in_a_harvest_is_reported_even_when_the_floor_check_passes(self) -> None:
        """The two allowlist checks are different questions: this harvest breaks no rule, yet carries
        an excuse that no longer maps to anything — which is how an exception outlives its reason."""
        with mock.patch.object(legibility, "FLOOR_EXCEPTIONS",
                               [(r"\.gone-away\b", "nothing on screen matches this")]):
            v = legibility.verdict("dark", clean_harvest(count=31))
        self.assertTrue(checks_of(v)["no_text_below_the_type_floor"]["pass"])
        self.assertFalse(checks_of(v)["no_stale_floor_exception"]["pass"])


class ContractAgreementTests(unittest.TestCase):
    def test_the_gate_and_the_written_standard_share_one_number(self) -> None:
        """DESIGN.md declares the floor in its typography scale; the gate must enforce the same value.

        Two numbers for one rule is how a contract and its check drift apart while both stay green.
        """
        design = (ROOT / "apps" / "observer" / "frontend" / "DESIGN.md").read_text(encoding="utf-8")
        front = design.split("---")[1]
        sizes = [float(m) for m in re.findall(r"fontSize:\s*([\d.]+)px", front)]
        self.assertGreaterEqual(len(sizes), 5, f"no typography scale parsed out of DESIGN.md: {sizes}")
        self.assertGreaterEqual(min(sizes), legibility.FLOOR_PX,
                                f"DESIGN.md declares {min(sizes)}px while the gate floors at "
                                f"{legibility.FLOOR_PX}px")


class CrossfadeVerdictTests(unittest.TestCase):
    """The switch itself: a settled page that passes can still flash through an unreadable frame."""

    @staticmethod
    def sample(color: str = BLACK, instant: bool = True, duration: str = "0s") -> list:
        return [{"text": "label", "path": "button.nav", "size": 14.0, "weight": "400",
                 "color": color, "bg": [WHITE, WHITE], "opacity": 1, "gradient": False,
                 "instant": instant, "duration": duration}]

    @staticmethod
    def bundle(labels: list[tuple[str, str]]) -> dict:
        return {"pageBackground": WHITE, "themeAtStart": "dark",
                "samples": [[label, nodes] for label, nodes in labels]}

    def test_a_clean_switch_passes_and_reports_how_many_frames_it_saw(self) -> None:
        v = legibility.crossfade_verdict("dark->light", self.bundle([
            ("before", self.sample()), ("t+16ms", self.sample()),
            ("t+66ms", self.sample())]))
        self.assertTrue(v["passed"], json.dumps(v["checks"], ensure_ascii=False))
        self.assertEqual(v["counts"]["samples"], 3)

    def test_a_sub_aa_intermediate_frame_fails(self) -> None:
        """The planted fault this whole mode exists for: 1.22:1 for two frames reads as a finished,
        compliant page in a settled measurement taken a second later."""
        v = legibility.crossfade_verdict("dark->light", self.bundle([
            ("before", self.sample()),
            ("t+16ms", self.sample(color="rgb(180, 190, 200)")),
            ("t+66ms", self.sample())]))
        failed = checks_of(v)["theme_switch_has_no_sub_aa_frame"]
        self.assertFalse(failed["pass"])
        self.assertIn("t+16ms", failed["detail"])

    def test_a_leaking_transition_duration_fails_even_when_every_ratio_is_fine(self) -> None:
        """The mechanism and the effect are separate claims: b10's `transition:.2s ease` winning over
        `.theme-instant` would put the switch back on an eased path, and the next sample might happen
        to look fine. This check is what stops that from being reported as a pass."""
        v = legibility.crossfade_verdict("dark->light", self.bundle([
            ("before", self.sample()), ("t+16ms", self.sample(duration="0.2s"))]))
        self.assertFalse(checks_of(v)["transitions_are_held_off_while_switching"]["pass"])
        self.assertTrue(checks_of(v)["theme_switch_has_no_sub_aa_frame"]["pass"])

    def test_no_samples_is_not_a_pass(self) -> None:
        v = legibility.crossfade_verdict("dark->light", {"pageBackground": WHITE, "samples": []})
        self.assertFalse(v["passed"])
        self.assertFalse(checks_of(v)["switch_was_observed"]["pass"])


class AllViewsVerdictTests(unittest.TestCase):
    """Driving the rail is what turns "0 AA failures" from a claim about one screen into a claim about
    all of them (ERR-218). These cases exist because a per-view loop can fail by measuring nothing."""

    @staticmethod
    def view(lane: str, count: int = 14, extra: dict | None = None) -> dict:
        nodes = [node(path=f"div.view-{lane} > span.body", text=f"{lane} label {i}")
                 for i in range(count)]
        if extra is not None:
            nodes.append(extra)
        # Coverage is part of the harvest contract now: the scroll sweep and the overflow reading are the
        # only things that prove the below-the-fold population was measured. The default here is a lane that
        # scrolled and gained text, which is what a healthy lane reports.
        return {"lane": lane, "error": None, "theme": "dark", "pageBackground": WHITE, "nodes": nodes,
                "coverage": {"atTop": max(1, len(nodes) // 2), "afterScroll": len(nodes),
                             "scrolledRegions": 1, "scrollWidth": 900, "innerWidth": 900,
                             "presentNodes": len(nodes) + 6, "sweepStopsUsed": 1, "sweepStopsNeeded": 2,
                             "scrollRangeCovered": 100,
                             "scrollHeight": 2400, "innerHeight": 820}}

    @staticmethod
    def collected(lanes: list[str], **overrides) -> dict:
        views = overrides.pop("views", None) or [AllViewsVerdictTests.view(lane) for lane in lanes]
        return {"pageBackground": WHITE, "views": views, **overrides}

    def test_every_view_clean_passes_and_reports_reach(self) -> None:
        lanes = [f"lane{i}" for i in range(legibility.MIN_VIEWS)]
        v = legibility.views_verdict("dark", self.collected(lanes))
        self.assertTrue(v["passed"], json.dumps(v["checks"], ensure_ascii=False))
        self.assertEqual(v["counts"]["views"], legibility.MIN_VIEWS)

    def test_a_lane_that_reports_no_coverage_is_not_treated_as_scanned(self) -> None:
        """The scroll sweep and the overflow reading share one harvest script; if it stops reporting, the
        two coverage checks would pass by measuring nothing -- which is how the handle rows stayed invisible."""
        lanes = [f"lane{i}" for i in range(legibility.MIN_VIEWS)]
        views = [self.view(lane) for lane in lanes]
        del views[4]["coverage"]
        v = legibility.views_verdict("dark", self.collected(lanes, views=views))
        check = checks_of(v)["coverage_was_reported"]
        self.assertFalse(check["pass"])
        self.assertIn("lane4", check["detail"])
        self.assertFalse(v["passed"])

    def test_a_lane_that_omits_the_population_is_not_a_scanned_lane_either(self) -> None:
        """`presentNodes` is the denominator of every sampled count on this rail. Without it, "2,933 nodes
        measured, 0 below the floor" reads as full coverage even when a 23,031px list was sampled for 143
        nodes, which is exactly what the evidence lane looked like on 2026-10-19."""
        lanes = [f"lane{i}" for i in range(legibility.MIN_VIEWS)]
        views = [self.view(lane) for lane in lanes]
        del views[6]["coverage"]["presentNodes"]
        v = legibility.views_verdict("dark", self.collected(lanes, views=views))
        check = checks_of(v)["coverage_was_reported"]
        self.assertFalse(check["pass"])
        self.assertIn("lane6", check["detail"])

    def test_sampling_more_text_than_the_page_contains_convicts_the_harvest(self) -> None:
        """A lane cannot hold fewer leaf texts than the sweep measured: a merge or dedup that double-counts
        surfaces here instead of as a suspiciously large node count."""
        lanes = [f"lane{i}" for i in range(legibility.MIN_VIEWS)]
        views = [self.view(lane) for lane in lanes]
        views[3]["coverage"] = {**views[3]["coverage"], "presentNodes": 3}
        v = legibility.views_verdict("dark", self.collected(lanes, views=views))
        check = checks_of(v)["sampled_nodes_stay_within_the_measured_population"]
        self.assertFalse(check["pass"])
        self.assertIn("lane3", check["detail"])
        self.assertFalse(v["passed"])

    def test_a_clean_sweep_still_says_what_it_sampled_versus_what_exists(self) -> None:
        lanes = [f"lane{i}" for i in range(legibility.MIN_VIEWS)]
        v = legibility.views_verdict("dark", self.collected(lanes))
        check = checks_of(v)["sampled_nodes_stay_within_the_measured_population"]
        self.assertTrue(check["pass"], json.dumps(v["checks"], ensure_ascii=False))
        for token in ("sampled=", "present=", "not a row count"):
            self.assertIn(token, check["detail"])
        self.assertTrue(checks_of(v)["every_scrollable_range_was_traversed"]["pass"])

    def test_a_lane_whose_scroll_range_was_not_walked_is_a_failure_not_a_smaller_sample(self) -> None:
        """Sampling budget that runs out mid-list leaves text nobody measured; that is the same class of
        hole the floor and AA checks exist to catch, so it is convicted by name rather than disclosed."""
        lanes = [f"lane{i}" for i in range(legibility.MIN_VIEWS)]
        views = [self.view(lane) for lane in lanes]
        views[11]["coverage"] = {**views[11]["coverage"], "scrollRangeCovered": 62}
        v = legibility.views_verdict("dark", self.collected(lanes, views=views))
        check = checks_of(v)["every_scrollable_range_was_traversed"]
        self.assertFalse(check["pass"])
        self.assertIn("lane11=62%", check["detail"])
        self.assertFalse(v["passed"])

    def test_horizontal_overflow_is_named_per_lane_at_this_width(self) -> None:
        lanes = [f"lane{i}" for i in range(legibility.MIN_VIEWS)]
        views = [self.view(lane) for lane in lanes]
        views[2]["coverage"] = {**views[2]["coverage"], "scrollWidth": 941, "innerWidth": 900}
        v = legibility.views_verdict("dark", self.collected(lanes, views=views), size=900)
        check = checks_of(v)["no_horizontal_overflow_at_this_width"]
        self.assertFalse(check["pass"])
        self.assertIn("lane2=41px", check["detail"])

    def test_a_scrollable_lane_that_yielded_no_new_text_is_reported_as_unsampled(self) -> None:
        lanes = [f"lane{i}" for i in range(legibility.MIN_VIEWS)]
        views = [self.view(lane) for lane in lanes]
        views[9]["coverage"] = {**views[9]["coverage"], "atTop": 14, "afterScroll": 14,
                                "scrolledRegions": 2}
        v = legibility.views_verdict("dark", self.collected(lanes, views=views), backend="live")
        check = checks_of(v)["scrollable_lanes_gained_nodes_after_scrolling"]
        self.assertFalse(check["pass"])
        self.assertIn("lane9", check["detail"])

    def test_the_scroll_rule_is_scoped_to_a_live_backend_and_says_so(self) -> None:
        """Under the static preview every lane collapses to the offline panel by design, so demanding a
        scroll there would fail `scripts/audit/reseal_wui_evidence.py`'s shell-typography runs for a reason
        that is not a defect. The scoping is itself asserted, not merely convenient."""
        lanes = [f"lane{i}" for i in range(legibility.MIN_VIEWS)]
        views = [self.view(lane) for lane in lanes]
        views[9]["coverage"] = {**views[9]["coverage"], "atTop": 14, "afterScroll": 14,
                                "scrolledRegions": 2}
        checks = checks_of(legibility.views_verdict("dark", self.collected(lanes, views=views)))
        self.assertNotIn("scrollable_lanes_gained_nodes_after_scrolling", checks)
        self.assertTrue(checks["scrollable_lanes_scanned"]["pass"])
        self.assertIn("lane9", checks["scrollable_lanes_scanned"]["detail"])

    def test_a_view_that_renders_almost_nothing_is_a_failure_not_a_small_average(self) -> None:
        lanes = [f"lane{i}" for i in range(legibility.MIN_VIEWS)]
        views = [self.view(lane) for lane in lanes]
        views[7] = self.view(views[7]["lane"], count=2)
        v = legibility.views_verdict("dark", self.collected(lanes, views=views))
        failed = checks_of(v)["every_view_rendered_readable_text"]
        self.assertFalse(failed["pass"])
        self.assertIn("lane7=2", failed["detail"])

    def test_an_offender_names_the_view_it_belongs_to(self) -> None:
        lanes = [f"lane{i}" for i in range(legibility.MIN_VIEWS)]
        views = [self.view(lane) for lane in lanes]
        views[3] = self.view(views[3]["lane"], extra=node(path="p.copy", text="成本质量说明", size=10.0))
        views[5] = self.view(views[5]["lane"], extra=node(path="span.tag", text="DELAYED",
                                                          color="rgb(120, 120, 120)"))
        v = legibility.views_verdict("dark", self.collected(lanes, views=views))
        floor = checks_of(v)["no_text_below_the_type_floor"]
        aa = checks_of(v)["every_text_node_meets_AA"]
        self.assertFalse(floor["pass"])
        self.assertIn("lane3", floor["detail"])
        self.assertFalse(aa["pass"])
        self.assertIn("lane5", aa["detail"])

    def test_a_lane_with_no_rail_button_is_reported_as_unreachable(self) -> None:
        lanes = [f"lane{i}" for i in range(legibility.MIN_VIEWS)]
        views = [self.view(lane) for lane in lanes]
        views[1] = {"lane": "lane1", "error": "NO_RAIL_BUTTON", "nodes": []}
        v = legibility.views_verdict("dark", self.collected(lanes, views=views))
        self.assertFalse(checks_of(v)["every_lane_is_reachable_from_the_rail"]["pass"])

    def test_a_short_run_is_not_the_whole_rail(self) -> None:
        v = legibility.views_verdict("dark", self.collected(["a", "b", "c"]))
        self.assertFalse(checks_of(v)["registered_views_were_all_attempted"]["pass"])

    def test_no_views_at_all_cannot_pass(self) -> None:
        v = legibility.views_verdict("dark", {"pageBackground": WHITE, "views": []})
        self.assertFalse(v["passed"])
        self.assertFalse(checks_of(v)["registered_views_were_all_attempted"]["pass"])

    def test_a_disabled_offender_is_reported_by_the_disabled_check(self) -> None:
        lanes = [f"lane{i}" for i in range(legibility.MIN_VIEWS)]
        views = [self.view(lane) for lane in lanes]
        views[2] = self.view(views[2]["lane"], extra={**node(path="button.primary-btn", text="新建执行",
                                                            color="rgb(210, 210, 210)"), "disabled": True})
        v = legibility.views_verdict("dark", self.collected(lanes, views=views))
        self.assertTrue(checks_of(v)["every_text_node_meets_AA"]["pass"])
        self.assertFalse(checks_of(v)["disabled_text_is_still_legible"]["pass"])

    def test_the_expression_reads_its_lane_list_from_the_rail(self) -> None:
        """Hardcoded lane names would let the product gain or lose a view and the census quietly not
        notice; the count is then checked against MIN_VIEWS by the verdict instead."""
        expr = legibility.views_expression("430px")
        self.assertIn("querySelectorAll('.nav button[data-lane]')", expr)
        self.assertIn("button.click()", expr)
        self.assertLessEqual(legibility.MIN_VIEWS, 23)

    def test_a_width_the_browser_did_not_honour_is_reported(self) -> None:
        """Chrome clamps a nonsense `--window-size` instead of refusing it, so a typo in the sweep
        would otherwise produce confident measurements of a window that never existed."""
        lanes = [f"lane{i}" for i in range(legibility.MIN_VIEWS)]
        collected = self.collected(lanes)
        collected["sizes"] = {"430px": 500}
        v = legibility.views_verdict("dark", collected, size=430)
        failed = checks_of(v)["window_is_the_width_asked"]
        self.assertFalse(failed["pass"])
        self.assertIn("innerWidth=500", failed["detail"])
        self.assertTrue(legibility.views_verdict(
            "dark", {**collected, "sizes": {"430px": 430}}, size=430)["passed"])


class HarvestShapeTests(unittest.TestCase):
    """The JS half is a dumb harvester, but its selection rules decide what is invisible to the gate."""

    def test_the_offscreen_measuring_sizer_cannot_be_counted_as_text(self) -> None:
        """`.action-sizer` lives at top:-9999px on purpose. It holds a copy of every control label, so
        harvesting it would double the census and invent failures at coordinates nobody renders."""
        self.assertIn("r.top >= innerHeight", legibility.HARVEST)
        self.assertIn("r.bottom <= 0 || r.top >= innerHeight", legibility.HARVEST)

    def test_only_leaf_text_is_judged(self) -> None:
        self.assertIn("n.nodeType === 3", legibility.HARVEST)

    def test_the_instrument_shares_the_geometry_probe_launcher(self) -> None:
        """Two browser bootstraps is two definitions of "the page was ready". One is kept."""
        self.assertIn("serve_and_eval", legibility.load_geometry().__dict__)


class GradientBackdropTests(unittest.TestCase):
    """The populated screen is where this model earned its keep: b10 paints pills and filled buttons
    with two-stop gradients, and the solid-only composite scored white text on a green pill against
    the page behind it. The first failure this found was real; the second was the instrument's own."""

    PILL = {"text": "OK", "path": "span.tag.ok", "size": 12.0, "weight": "700",
            "color": "rgb(255, 255, 255)", "opacity": 1, "gradient": True,
            "bg": ["rgba(0, 0, 0, 0)", "rgb(244, 247, 250)"],
            "bgImage": ["linear-gradient(135deg, rgb(39, 200, 106), rgb(17, 167, 77))", "none"]}

    def test_a_gradient_is_judged_at_its_least_favourable_stop(self) -> None:
        scored = legibility.node_contrast(self.PILL, "rgb(244, 247, 250)")
        self.assertEqual(scored["renderedRatio"], 2.2)      # white on #27c86a
        self.assertFalse(scored["pass"])

    def test_the_page_colour_is_not_offered_when_a_gradient_decides(self) -> None:
        """The planted regression: if the solid stack is listed as a candidate again, this node reads
        1.04:1 "on white" — a number that looks like a failure but describes a backdrop the glyph
        never touches, and it sends the fix to the wrong file."""
        candidates, ok = legibility.backdrop_candidates(
            self.PILL["bg"], "rgb(244, 247, 250)", self.PILL["bgImage"])
        self.assertTrue(ok)
        self.assertNotIn((244.0, 247.0, 250.0), candidates)
        self.assertEqual(len(candidates), 2)

    def test_a_translucent_layer_between_text_and_an_opaque_decider_still_tints_it(self) -> None:
        candidates, _ = legibility.backdrop_candidates(
            ["rgba(255, 0, 0, 0.5)", "rgb(255, 255, 255)"], "rgb(255, 255, 255)")
        self.assertAlmostEqual(candidates[0][0], 255.0, delta=0.01)
        self.assertAlmostEqual(candidates[0][1], 127.5, delta=0.01)

    def test_a_translucent_gradient_wash_is_not_read_as_an_opaque_fill(self) -> None:
        """The false finding this guard caught. `.nav button.active` is 26% primary over a 68% surface2
        row, and with the stop's alpha dropped it scored as solid #2A91FF — a 2.92:1 AA failure on a
        selected row that really measures ~11:1. An instrument that loses alpha in one place and keeps
        it in another is worse than one that has no gradient support at all."""
        candidates, ok = legibility.backdrop_candidates(
            ["rgba(0, 0, 0, 0)", "rgba(0, 0, 0, 0)", "rgb(7, 17, 28)"], "rgb(5, 13, 22)",
            ["linear-gradient(180deg, rgba(42, 145, 255, 0.26), rgba(42, 145, 255, 0.16))",
             "none", "none"])
        self.assertTrue(ok)
        self.assertEqual(len(candidates), 2)
        self.assertLess(max(candidate[2] for candidate in candidates), 120.0)
        worst = min(candidates, key=legibility.relative_luminance)
        self.assertGreater(legibility.contrast_ratio((238, 246, 252), worst), 8.0)

    def test_gradient_stops_are_read_from_the_forms_css_actually_returns(self) -> None:
        stops = legibility.parse_gradient_stops(
            "linear-gradient(135deg, color(srgb 0.15 0.78 0.42), rgb(17, 167, 77))")
        self.assertEqual(len(stops), 2)
        self.assertAlmostEqual(stops[0][1], 198.9, delta=0.6)
        self.assertEqual(legibility.parse_gradient_stops("none"), [])


class DisabledControlTests(unittest.TestCase):
    """WCAG exempts inactive text from 1.4.3. This product does not, because a disabled button is how
    the read-only shell explains a refusal — an unreadable explanation is not an explanation."""

    def test_a_disabled_label_below_three_to_one_fails_the_disabled_rule(self) -> None:
        faded = {**node(color="rgb(210, 210, 210)"), "disabled": True}
        scored = legibility.node_contrast(faded, WHITE)
        self.assertEqual(scored["requiredRatio"], legibility.AA_DISABLED)
        self.assertFalse(scored["pass"])
        # Planted into a clean harvest: the AA check must stay quiet about it and the disabled check
        # must be the one that goes red. Two claims, two checks, no silent exemption.
        harvest = clean_harvest()
        harvest["nodes"][4] = faded
        verdict = legibility.verdict("dark", harvest)
        self.assertTrue(checks_of(verdict)["every_text_node_meets_AA"]["pass"])
        self.assertFalse(checks_of(verdict)["disabled_text_is_still_legible"]["pass"])

    def test_a_disabled_label_at_3_15_is_accepted(self) -> None:
        harvest = clean_harvest()
        harvest["nodes"][4] = {**node(color="rgb(145, 145, 145)"), "disabled": True}
        scored = legibility.node_contrast(harvest["nodes"][4], WHITE)
        self.assertAlmostEqual(scored["renderedRatio"], 3.15, delta=0.02)
        self.assertTrue(scored["pass"])
        self.assertTrue(legibility.verdict("dark", harvest)["passed"])



class ShellSurfaceTests(unittest.TestCase):
    """The 150x480 strip, the 440x680 panel and the 1280x820 daily entry joined this sweep on
    2026-10-25. Before that the gate read only `view=full`/`view=overview`, so the two surfaces an owner
    actually looks at had no 12px floor and no AA ratio judged by any tracked gate.

    Measured on the shipped bundle with the declared fixture snapshot: the strip paints 16 readable text
    nodes, the panel 24, the daily shell 38. A single shell-wide floor of 30 would convict the strip for
    being 150px wide, so the floor is per surface — and each case below proves the smaller floor still
    refuses an empty render rather than excusing one.
    """

    def setUp(self) -> None:
        self.strip = legibility.load_strip_gate()
        self.surfaces = {s["label"]: s for s in legibility.shell_surfaces(self.strip)}

    def test_the_density_floor_is_per_surface_and_not_a_blanket_loosening(self) -> None:
        strip_floor = self.surfaces["strip-h01"]["minNodes"]
        asked_without_a_floor = legibility.verdict("dark", clean_harvest(16), surface="strip-h01")
        self.assertFalse(checks_of(asked_without_a_floor)["harvest_is_dense_enough"]["pass"],
                         "the shell floor must still apply when the caller forgets to narrow it")
        sparse = checks_of(legibility.verdict("dark", clean_harvest(9),
                                              strip_floor, "strip-h01"))["harvest_is_dense_enough"]
        self.assertTrue(sparse["pass"], sparse)
        self.assertIn(f"floor={strip_floor} surface=strip-h01", sparse["detail"])
        empty = checks_of(legibility.verdict("dark", clean_harvest(strip_floor - 1),
                                             strip_floor, "strip-h01"))["harvest_is_dense_enough"]
        self.assertFalse(empty["pass"], "a floor that refuses nothing is a comment, not a guard")

    def test_the_strip_floor_is_chrome_not_a_populations_node_total(self) -> None:
        """2026-10-28, the same shipped bundle read from both sides: the declared fixture paints 12
        text nodes on `strip-h01` (5 agent rows) and the live ledger paints 9 (3 rows). The old floor of
        12 was the fixture's total, so it convicted a healthy strip for holding fewer agents than the
        fixture declares. The 6 is what the strip paints whatever the ledger holds; 0 is what an empty
        page measures.
        """
        self.assertEqual(legibility.MIN_STRIP_NODES, 6)
        self.assertEqual(self.surfaces["strip-h01"]["minNodes"], legibility.MIN_STRIP_NODES)
        self.assertLess(legibility.MIN_STRIP_NODES, 9, "the sparse real render must clear its own floor")
        self.assertLess(legibility.MIN_STRIP_NODES, 12, "the fixture total is not the floor")
        self.assertLessEqual(legibility.MIN_SHELL_NODES, 13, "panel-h01 chrome measures 13")

    def test_a_low_contrast_label_on_the_strip_fails_the_same_rule_as_the_shell(self) -> None:
        # The planted footer grey this round measured at 2.44:1 on the strip's own #10141A card. The
        # judgement must be the shell's, not a softer one for small surfaces.
        harvest = clean_harvest(16)
        harvest["pageBackground"] = "rgb(16, 20, 26)"
        for n in harvest["nodes"]:
            n["bg"] = ["rgba(0, 0, 0, 0)", "rgb(16, 20, 26)"]
            n["color"] = "rgb(75, 85, 99)"
        bad = checks_of(legibility.verdict("dark", harvest, self.surfaces["strip-h01"]["minNodes"],
                                          "strip-h01"))["every_text_node_meets_AA"]
        self.assertFalse(bad["pass"], bad)
        self.assertIn("2.44:1", bad["detail"])

    def test_the_surfaces_come_from_the_strip_gate_not_a_second_copy(self) -> None:
        declared = {s["name"]: s for s in self.strip.SURFACES}
        self.assertEqual(set(self.surfaces), set(legibility.SHELL_SURFACE_KINDS))
        for label, surface in self.surfaces.items():
            self.assertEqual(surface["size"], declared[label]["size"], label)
            self.assertEqual(surface["query"], declared[label]["query"], label)
            self.assertEqual(surface["mount"], self.strip.MOUNT_SELECTOR[declared[label]["kind"]], label)

    def test_a_surface_the_strip_gate_stops_declaring_refuses_the_sweep(self) -> None:
        class Narrowed:
            SURFACES = [s for s in self.strip.SURFACES if s["name"] != "panel-h01"]
            MOUNT_SELECTOR = self.strip.MOUNT_SELECTOR

        with self.assertRaises(RuntimeError) as caught:
            legibility.shell_surfaces(Narrowed())
        self.assertIn("SHELL_SURFACE_MISSING", str(caught.exception))

    def test_the_shell_harvest_asks_the_fixture_origin_for_the_theme_it_was_given(self) -> None:
        class Fixture:
            def __init__(self) -> None:
                self.calls: list = []

            def url_for(self, query, theme):
                self.calls.append((query, theme))
                return f"http://127.0.0.1:9/{query}&theme={theme}"

        class Geometry:
            def __init__(self, harvest) -> None:
                self.harvest, self.calls = harvest, []

            def serve_and_eval(self, root, path, window, expr, browser, u19, shot, **kw):
                self.calls.append(kw)
                return dict(self.harvest)

        surface = self.surfaces["strip-h01"]
        fixture, geom = Fixture(), Geometry(clean_harvest(16))
        out = legibility.harvest_shell_surface(self.strip, geom, ROOT, "browser", "u19",
                                               fixture, "light", surface)
        self.assertEqual(fixture.calls, [(surface["query"], "light")])
        self.assertEqual(len(geom.calls), 2, "the settled-pair rule still needs two samples")
        self.assertEqual(geom.calls[0]["viewport"], (150, 480))
        self.assertEqual(geom.calls[0]["mount_selector"], surface["mount"])
        for call in geom.calls:
            self.assertEqual(call["serve_url"],
                             f"http://127.0.0.1:9/{surface['query']}&theme=light")
        self.assertEqual(out["backend"], "declared-fixture")

    def test_a_shell_surface_that_renders_nothing_is_refused_before_it_is_judged(self) -> None:
        class Fixture:
            def url_for(self, query, theme):
                return "http://127.0.0.1:9/x"

        class Geometry:
            def serve_and_eval(self, root, path, window, expr, browser, u19, shot, **kw):
                return clean_harvest(4)

        with self.assertRaises(RuntimeError) as caught:
            legibility.harvest_shell_surface(self.strip, Geometry(), ROOT, "b", "u", Fixture(),
                                             "dark", self.surfaces["strip-h01"])
        self.assertIn("THIN_HARVEST", str(caught.exception))

    def test_the_floor_and_ratio_standards_have_one_owner_for_these_surfaces(self) -> None:
        # The narrow-strip gate used to assert the 12px floor as well. Two gates reading one standard
        # means two thresholds and two exception lists; the geometry gate now keeps geometry, and the
        # type/colour rules live here for every surface including the shell.
        strip_source = (ROOT / "scripts" / "audit" / "hud_strip_geometry_via_cdp.py"
                        ).read_text(encoding="utf-8")
        self.assertNotIn("text_meets_the_12px_floor", strip_source)
        self.assertIn("--shell-surfaces", (ROOT / ".github" / "workflows" / "work-lab-gate.yml"
                                           ).read_text(encoding="utf-8"))

class _FakeResponse:
    """`urlopen` used as a context manager, returning fixed bytes."""

    def __init__(self, payload: bytes) -> None:
        self.payload = payload

    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, *exc) -> None:
        return None

    def read(self) -> bytes:
        return self.payload


def _fake_response(payload: bytes) -> _FakeResponse:
    return _FakeResponse(payload)


class LiveApiTests(unittest.TestCase):
    """`--api` measures the shipped bundle over a real v3 backend, and must refuse a fake one.

    The hole this closes is the quiet green: a page pointed at a backend that does not answer falls back
    to the offline card, and an offline card is perfectly legible — every floor would pass while nothing
    product-shaped had been measured. So the backend is probed before any browser starts, and the
    population it serves is reported.
    """

    def test_a_non_loopback_backend_is_refused_without_reaching_the_network(self) -> None:
        with mock.patch.object(legibility.urllib.request, "urlopen",
                               side_effect=AssertionError("the probe must not open a socket")) as opened:
            with self.assertRaises(ValueError) as caught:
                legibility.probe_live_api("https://example.invalid")
            self.assertIn("LIVE_API_NOT_LOOPBACK", str(caught.exception))
            opened.assert_not_called()

    def test_a_backend_that_is_not_the_v3_contract_is_refused(self) -> None:
        payload = json.dumps({"schemaVersion": "workflow/snapshot/v2"}).encode("utf-8")
        with mock.patch.object(legibility.urllib.request, "urlopen",
                               return_value=_fake_response(payload)):
            with self.assertRaises(ValueError) as caught:
                legibility.probe_live_api("http://127.0.0.1:55999")
            self.assertIn("LIVE_API_NOT_V3", str(caught.exception))

    def test_the_probe_reports_the_population_it_found(self) -> None:
        served = {"schemaVersion": "workflow/snapshot/v3", "revision": 4433,
                  "adapterCapabilities": [{"clientId": f"c{i}"} for i in range(10)],
                  "projects": [1], "executions": []}
        with mock.patch.object(legibility.urllib.request, "urlopen",
                               return_value=_fake_response(json.dumps(served).encode("utf-8"))):
            found = legibility.probe_live_api("http://127.0.0.1:55999")
        self.assertEqual(found, {"api": "http://127.0.0.1:55999",
                                 "schemaVersion": "workflow/snapshot/v3", "revision": 4433,
                                 "adapters": 10, "projects": 1, "executions": 0},
                         "a live run that cannot say what data it measured is indistinguishable from "
                         "the fixture run in the log")

    def test_the_live_url_is_built_the_way_the_fixture_origin_builds_it(self) -> None:
        url = legibility.live_api_url("http://127.0.0.1:55999/", "surface=daily&shell=tauri", "light")
        encoded = legibility.urllib.parse.quote("http://127.0.0.1:55999/api/v1/snapshot", safe="")
        self.assertTrue(url.startswith("http://127.0.0.1:55999/index.html?surface=daily&shell=tauri"), url)
        self.assertIn(f"&mode=UNKNOWN&theme=light&api={encoded}", url)

    def test_main_refuses_a_live_backend_it_cannot_trust_before_touching_the_disk(self) -> None:
        proc = subprocess.run([sys.executable, str(SCRIPT), "--shell-surfaces",
                               "--api", "https://example.invalid"],
                              capture_output=True, text=True, encoding="utf-8", errors="replace")
        self.assertEqual(proc.returncode, 2, proc.stdout + proc.stderr)
        self.assertIn("LEGIBILITY_GATE_NOT_RUN LIVE_API", proc.stdout)


if __name__ == "__main__":
    unittest.main()
