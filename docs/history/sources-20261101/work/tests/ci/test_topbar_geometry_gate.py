"""Gate: the CDP geometry probe is a verdict, not a printout (UI prompt pack G3).

The probe shipped for a week as an instrument that could only produce numbers: `main()` returned
None, so it always exited 0, and no workflow step or test referenced it. Every check here is on the
PURE verdict function, so the assertions are reviewable and run on any checkout — the browser is
only needed to produce the measurement it judges.
"""
from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "audit" / "topbar_geometry_via_cdp.py"

spec = importlib.util.spec_from_file_location("topbar_geometry", SCRIPT)
geometry = importlib.util.module_from_spec(spec)
spec.loader.exec_module(geometry)  # type: ignore[attr-defined]


def element(left=0.0, width=280.0, height=40.0, gap=10.0, display="flex") -> dict:
    return {"left": left, "right": left + width, "top": 0.0, "bottom": height,
            "width": width, "height": height, "gapToViewportRight": gap, "display": display}


def good_measured(view="full") -> dict:
    data = {
        "__viewport": "1280x820", "__innerWidth": 1280, "__docScrollWidth": 1280,
        ".app": [element(0, 1280, 820, 0)],
        ".topbar": [element(280, 1000, 78, 280)],
        ".search": [element(300, 600, 40, 400)],
        ".top-actions": [element(950, 300, 40, 30)],
        ".topbar-brand": [element(290, 120, 22, 990)],
        ".winctl": [element(1150, 120, 32, 10)],
        ".winctl-btn": [element(1160, 32, 32, 88), element(1196, 32, 32, 52),
                        element(1232, 32, 32, 16)],
        ".main": [element(280, 1000, 742, 0)],
        ".kpi-grid": [element(300, 960, 120, 20)],
        "__elementsOverlappingRightEdge": [],
        "__actionsFit": {"children": 4, "rows": 1, "more": False},
        # The numbers below are the shipped ones (receipt
        # .project-local/artifacts/OFFLINE_VIEW_TEXT.json): the bar occupies 0→129 and `.content`
        # starts at 129 — touching, not overlapping — with a painted 1px edge.
        "__edges": {
            "topbar": {"top": 0.0, "bottom": 129.0, "borderBottomWidth": "1px",
                       "borderBottomStyle": "solid", "borderBottomColor": "rgb(23 67 93 / 0.6)",
                       "boxShadow": "none"},
            "content": {"top": 129.0, "bottom": 780.0, "borderBottomWidth": "0px",
                        "borderBottomStyle": "none", "borderBottomColor": "rgb(0, 0, 0)",
                        "boxShadow": "none"},
            "main": {"top": 0.0, "bottom": 820.0, "borderBottomWidth": "0px",
                     "borderBottomStyle": "none", "borderBottomColor": "rgb(0, 0, 0)",
                     "boxShadow": "none"},
        },
        "__focusObscured": [
            {"sel": '.search[role="button"], .search', "focused": True, "top": 12.0, "bottom": 62.0,
             "visible": True, "hitIsSelfOrChild": True},
            {"sel": ".top-actions button", "focused": True, "top": 70.0, "bottom": 116.0,
             "visible": True, "hitIsSelfOrChild": True},
            {"sel": ".winctl-btn", "focused": True, "top": 16.0, "bottom": 48.0,
             "visible": True, "hitIsSelfOrChild": True},
        ],
    }
    data["__mobileNav"] = []
    # The HUD's search label really is ellipsised (11px lost) and really is carried by the field's own
    # aria-label, so the healthy fixture models a clip that is allowed rather than an empty list.
    data["__clippedText"] = [{"tag": "SPAN", "cls": "truncate", "text": "搜索或命令",
                              "lostPx": 11, "fontSize": "16px", "carried": True}]
    data["__barTargets"] = [
        {"sel": ".top-actions button", "painted": True, "w": 62.0, "h": 32.0},
        {"sel": ".top-actions button", "painted": True, "w": 74.0, "h": 32.0},
        {"sel": ".winctl-btn", "painted": True, "w": 32.0, "h": 32.0},
        {"sel": ".search", "painted": True, "w": 600.0, "h": 40.0},
    ]
    if view in ("full", "floor"):
        lanes = 9 if view == "full" else 23
        data["__navReach"] = {
            "total": lanes, "atTop": lanes, "afterScroll": lanes, "overflow": False,
            "lastHitInside": True, "disclosures": 7, "clientH": 620, "scrollH": 620,
            "nameless": [],
            "labels": [f"车道{i}" for i in range(lanes)],
            "targets": [{"lane": f"lane{i}", "w": 228.0, "h": 40.0} for i in range(lanes)],
        }
    if view == "full":
        data[".sidebar"] = [element(0, 280, 820, 1000)]
        # The healthy shape: everything fits at the top, so no scrolling is required at all. The
        # scrollable-and-last-hit-testable branch is exercised separately below.
        data["__navReach"].update({"atTop": 9, "afterScroll": 9, "overflow": False})
    if view == "floor":
        # Measured 2026-10-08 at the pinned 900x600 layout viewport
        # (receipt .project-local/artifacts/GEOMETRY_FLOOR_1.json): the rail keeps its 210px text
        # width, the bar is 125px tall, and the 23-lane rail is a 345px scroll box over 1554px.
        data.update({"__viewport": "900x600", "__innerWidth": 900, "__docScrollWidth": 900})
        data[".app"] = [element(0, 900, 600, 0)]
        data[".sidebar"] = [element(0, 210, 600, 690)]
        data[".topbar"] = [element(210, 690, 125, 210)]
        data[".search"] = [element(230, 420, 40, 250)]
        data[".top-actions"] = [element(650, 200, 40, 50)]
        data[".topbar-brand"] = [element(220, 120, 22, 680)]
        data[".winctl"] = [element(770, 120, 32, 10)]
        data[".winctl-btn"] = [element(780, 32, 32, 88), element(816, 32, 32, 52),
                               element(852, 32, 32, 16)]
        data[".main"] = [element(210, 690, 475, 0)]
        data[".kpi-grid"] = [element(230, 650, 120, 20)]
        data["__navReach"].update({"atTop": 6, "afterScroll": 8, "overflow": True,
                                   "clientH": 345, "scrollH": 1554})
        data["__edges"]["topbar"]["bottom"] = 125.0
        data["__edges"]["content"]["top"] = 125.0
    return data


class VerdictTests(unittest.TestCase):
    def setUp(self) -> None:
        self.v = geometry.verdict(good_measured("full"), "full")

    def test_a_clean_desktop_measurement_passes_and_names_every_check(self) -> None:
        self.assertTrue(self.v["passed"], json.dumps(self.v["checks"], indent=1))
        self.assertEqual({c["check"] for c in self.v["checks"]},
                         {"no_horizontal_overflow", "topbar_measured", "topbar_not_stacked",
                          "brand_mark_present", "actions_visible", "window_controls_reachable",
                          "action_row_inside_viewport", "rail_always_present",
                          "rail_at_left_edge", "nav_items_reachable",
                          "nav_groups_are_disclosures", "action_row_does_not_stack",
                          "content_clears_topbar", "topbar_edge_is_painted",
                          "focused_control_is_not_obscured", "every_visible_probe_takes_focus",
                          "no_mobile_navigation_surface_is_painted", "every_lane_is_named",
                          "lane_labels_are_distinguishable", "lane_targets_meet_the_floor",
                          "no_text_is_clipped_without_a_fallback"})

    def test_the_rail_must_survive_every_width_the_main_window_can_take(self) -> None:
        # the desktop-only contract in geometry form: b10 used to hide `.sidebar` below 840px.
        measured = good_measured("full")
        del measured[".sidebar"]
        v = geometry.verdict(measured, "full")
        self.assertFalse(v["passed"])
        self.assertFalse([c for c in v["checks"] if c["check"] == "rail_always_present"][0]["pass"])

        measured = good_measured("full")
        measured[".sidebar"] = [element(0, 120, 820, 1160)]
        self.assertFalse([c for c in geometry.verdict(measured, "full")["checks"]
                          if c["check"] == "rail_always_present"][0]["pass"])

    def test_content_pushed_past_the_right_edge_fails(self) -> None:
        measured = good_measured("full")
        measured[".winctl-btn"][-1]["gapToViewportRight"] = -40.0
        v = geometry.verdict(measured, "full")
        self.assertFalse(v["passed"])
        self.assertIn("clipped", [c for c in v["checks"]
                                  if c["check"] == "window_controls_reachable"][0]["detail"])

    def test_a_hidden_action_row_is_a_failure_not_an_absence_of_problem(self) -> None:
        measured = good_measured("full")
        measured[".top-actions"] = [element(950, 300, 40, 30, display="none")]
        self.assertFalse([c for c in geometry.verdict(measured, "full")["checks"]
                          if c["check"] == "actions_visible"][0]["pass"])

    def test_an_unreadable_action_row_shape_fails_instead_of_taking_the_job_down(self) -> None:
        """Measured 2026-10-20 on the runner: the observer job died with `KeyError: 0` inside `verdict`,
        because the PASS detail interpolated `measured['.top-actions'][0]` while the harvest had returned
        something that is not a list of boxes. A gate that raises reports nothing about the surface it was
        sent to measure, so an unreadable shape has to come back as a named failure."""
        measured = good_measured("full")
        measured[".top-actions"] = {"display": "flex"}
        check = [c for c in geometry.verdict(measured, "full")["checks"]
                 if c["check"] == "action_row_inside_viewport"][0]
        self.assertFalse(check["pass"])
        self.assertIn("not a list of boxes", check["detail"])
        for shape in ([], [{"gapToViewportRight": -40}]):
            measured = good_measured("full")
            measured[".top-actions"] = shape
            verdict = geometry.verdict(measured, "full")
            row = [c for c in verdict["checks"] if c["check"] == "action_row_inside_viewport"][0]
            self.assertEqual(bool(shape), not row["pass"],
                             f"shape {shape!r} must {'fail' if shape else 'pass'} without raising")

    def test_a_stacked_topbar_fails_the_height_bound(self) -> None:
        # the measured phone-shape defect: four action buttons stacked one per row at 320px CSS.
        measured = good_measured("full")
        measured[".topbar"] = [element(280, 1000, 263, 280)]
        self.assertFalse([c for c in geometry.verdict(measured, "full")["checks"]
                          if c["check"] == "topbar_not_stacked"][0]["pass"])

    def test_a_passing_detail_says_what_was_measured(self) -> None:
        # On the runner the gate logged `topbar_measured PASS no .topbar element`, which reads as a missing
        # element while the next line reports a height. A PASS detail must name the quantity it passed on.
        detail = [c for c in self.v["checks"] if c["check"] == "topbar_measured"][0]["detail"]
        self.assertIn("height=", detail)
        self.assertIn("found", detail)
        self.assertNotIn("no .topbar element", detail)

        measured = good_measured("full")
        del measured[".topbar"]
        absent = [c for c in geometry.verdict(measured, "full")["checks"]
                  if c["check"] == "topbar_measured"][0]
        self.assertFalse(absent["pass"])
        self.assertIn("MISSING", absent["detail"])

    def test_horizontal_overflow_fails(self) -> None:
        measured = good_measured("full")
        measured["__docScrollWidth"] = 1400
        self.assertFalse(geometry.verdict(measured, "full")["passed"])

    def test_a_missing_brand_mark_fails(self) -> None:
        measured = good_measured("full")
        del measured[".topbar-brand"]
        self.assertFalse([c for c in geometry.verdict(measured, "full")["checks"]
                          if c["check"] == "brand_mark_present"][0]["pass"])

    def test_the_compact_view_asserts_the_opposite_rail_contract(self) -> None:
        measured = good_measured("compact")
        self.assertTrue(geometry.verdict(measured, "compact")["passed"])
        measured[".sidebar"] = [element(0, 280, 820, 1000)]
        self.assertFalse([c for c in geometry.verdict(measured, "compact")["checks"]
                          if c["check"] == "compact_has_no_rail"][0]["pass"])


class InstrumentTests(unittest.TestCase):
    def test_the_probe_is_not_bound_to_the_authors_machine(self) -> None:
        text = SCRIPT.read_text(encoding="utf-8")
        self.assertNotIn(r"D:\All projects", text)
        self.assertIn('Path(__file__).resolve().parents[2]', text)

    def test_browser_is_discovered_and_reported_as_a_named_category(self) -> None:
        real = Path(sys.executable)
        with mock.patch.dict(os.environ, {"WL_CHROME": str(real)}):
            self.assertEqual(geometry.find_browser(), str(real))
        # PATH discovery, with no env override and no vendor install dir on disk. `clear=True` matters:
        # the first block leaves WL_CHROME set in a developer's own environment, and an inherited
        # WL_CHROME short-circuits discovery, so this case passed on CI and failed on my shell.
        with mock.patch.dict(os.environ, {"PATH": "/usr/bin",
                                          "PROGRAMFILES": str(ROOT / "nope"),
                                          "PROGRAMFILES(X86)": str(ROOT / "nope")}, clear=True), \
                mock.patch.object(geometry.shutil, "which", return_value=str(real)):
            self.assertEqual(geometry.find_browser(), str(real))
        env = {"PATH": str(ROOT / "definitely-not-a-bin")}
        with mock.patch.dict(os.environ, env, clear=True), \
                mock.patch.object(geometry.shutil, "which", return_value=None):
            self.assertIsNone(geometry.find_browser())

    def test_a_tree_without_the_built_bundle_refuses_instead_of_passing(self) -> None:
        scratch = Path(tempfile.mkdtemp(prefix="geometry-gate-selftest-",
                                        dir=ROOT / ".project-local" / "runs"))
        try:
            proc = subprocess.run([sys.executable, str(SCRIPT), "--root", str(scratch)],
                                  capture_output=True, text=True, encoding="utf-8",
                                  errors="replace")
            self.assertEqual(proc.returncode, 3, proc.stdout + proc.stderr)
            self.assertIn("GEOMETRY_GATE_NOT_RUN DIST_ABSENT", proc.stdout)
        finally:
            shutil.rmtree(scratch, ignore_errors=False)

    def test_the_page_session_url_carries_the_port_that_was_asked_for(self) -> None:
        # Chrome builds webSocketDebuggerUrl from the request's Host header, so a portless Host —
        # the shape that gets a 200 from its HTTP endpoint at all — makes it echo a portless URL,
        # and connecting to that refuses. The gate must rebuild the URL from the port it was given.
        target = [{"type": "page",
                   "webSocketDebuggerUrl": "ws://127.0.0.1/devtools/page/ABC123",
                   "url": "http://x/index.html"}]
        with mock.patch.object(geometry, "cdp_list", return_value=target):
            self.assertEqual(geometry.discover_page_ws(59123, tries=1),
                             "ws://127.0.0.1:59123/devtools/page/ABC123")

    def test_each_surface_is_measured_at_its_own_declared_shape(self) -> None:
        # Measuring the compact layout at desktop width proved nothing about the panel.
        self.assertEqual(geometry.WIN_SIZE["full"], "1280,820")
        self.assertEqual(geometry.WIN_SIZE["compact"], "440,680")
        self.assertGreater(geometry.MAX_HEIGHT["compact"], geometry.MAX_HEIGHT["full"],
                           "the 440px panel wraps its bar into more rows than the desktop shell")

    def test_a_missing_evaluate_value_is_reported_not_crashed_on(self) -> None:
        client = geometry.ChromeCDP.__new__(geometry.ChromeCDP)
        with mock.patch.object(client, "send", return_value={"type": "string"}):
            with self.assertRaises(RuntimeError) as caught:
                client.evaluate("1+1")
        self.assertIn("produced no value", str(caught.exception))

    def test_the_chrome_port_is_read_from_the_browser_instead_of_assumed(self) -> None:
        # The gate asks Chrome for port 0 and parses the announced one; a socket reserved first is
        # free again by the time Chrome binds, and Chrome then picks a different port silently.
        line = ("DevTools listening on ws://127.0.0.1:54796/devtools/browser/"
                "5888c269-2647-43f4-9318-4b349e7a1bc8\n")
        self.assertEqual(geometry.LISTEN_RE.search(line).group(1), "54796")
        self.assertIsNone(geometry.LISTEN_RE.search("nothing here yet"))

    def test_refusal_to_run_is_not_reported_as_a_pass(self) -> None:
        # A gate that exits 0 while refusing to measure is the defect G3 records; exit 3 is the
        # only honest answer. The browser is absent by patch, not by launching one.
        scratch = ROOT / ".project-local" / "runs" / "geometry-gate-nobrowser"
        dist = scratch / "apps/observer/frontend/dist"
        dist.mkdir(parents=True, exist_ok=True)
        (dist / "index.html").write_text("<html></html>", encoding="utf-8")
        try:
            with mock.patch.object(geometry, "find_browser", return_value=None), \
                    mock.patch.object(sys, "argv", ["x", "--root", str(scratch)]), \
                    mock.patch("builtins.print") as printed:
                self.assertEqual(geometry.main(), 3)
            self.assertTrue(any("GEOMETRY_GATE_NOT_RUN" in str(c.args[0])
                                for c in printed.call_args_list), printed.call_args_list)
        finally:
            # The fixture is derived test data with no unique bytes; deleting it here is the
            # ERR-140 rule (never swallow the failure) applied to my own scratch root.
            shutil.rmtree(scratch)
            self.assertFalse(scratch.exists())


class ActionRowFoldingTests(unittest.TestCase):
    """The action band must stay one row and fold, never wrap into a column."""

    def verdict_for(self, fit: dict) -> dict:
        measured = good_measured("full")
        measured["__actionsFit"] = fit
        return geometry.verdict(measured, "full")

    def check(self, verdict: dict) -> dict:
        return next(c for c in verdict["checks"] if c["check"] == "action_row_does_not_stack")

    def test_a_wrapped_action_row_fails_the_check(self) -> None:
        # Measured at 430px before the fold existed: four controls, two distinct rows.
        stacked = self.check(self.verdict_for({"children": 4, "rows": 2, "more": False}))
        self.assertFalse(stacked["pass"], stacked)
        self.assertIn("rows=2", stacked["detail"])

    def test_a_single_row_passes(self) -> None:
        flat = self.check(self.verdict_for({"children": 4, "rows": 1, "more": False}))
        self.assertTrue(flat["pass"], flat)

    def test_a_folded_row_that_hid_everything_still_fails(self) -> None:
        # Zero painted children is not "one row"; it is the pinned skin's `display:none` branch, and a
        # band that renders nothing cannot claim its controls are reachable.
        empty = self.check(self.verdict_for({"children": 0, "rows": 0, "more": False}))
        self.assertFalse(empty["pass"], empty)


class NavReachabilityTests(unittest.TestCase):
    """The check that was missing while the rail was silently clipped 14 of its 23 items.

    Each case is a shape the shipped skin actually produced, so the guard cannot be satisfied by a
    fixture nobody ever renders: `overflow-y:auto` on a box as tall as its content is the dead
    container, and it is the only failure mode a "is the nav in the DOM" test would have passed.
    """

    def verdict_for(self, reach: dict) -> dict:
        measured = good_measured("full")
        measured["__navReach"] = reach
        return geometry.verdict(measured, "full")

    def check(self, verdict: dict) -> dict:
        return next(c for c in verdict["checks"] if c["check"] == "nav_items_reachable")

    def test_the_dead_container_that_shipped_fails_the_check(self) -> None:
        # Measured 2026-10-08 at 1386x807: clientH == scrollH == 1496 with 23 buttons and 9 visible.
        dead = self.check(self.verdict_for({"total": 23, "atTop": 9, "afterScroll": 9, "overflow": False,
                                            "lastHitInside": False, "disclosures": 7, "clientH": 1496, "scrollH": 1496}))
        self.assertFalse(dead["pass"], dead)
        self.assertIn("overflow=False", dead["detail"])

    def test_a_live_scroll_container_that_reveals_the_last_item_passes(self) -> None:
        # The shape after the fix: clientH 595 < scrollH 1505, and the last item is hit-testable once
        # the rail is scrolled to its end.
        live = self.check(self.verdict_for({"total": 23, "atTop": 9, "afterScroll": 11, "overflow": True,
                                            "lastHitInside": True, "disclosures": 7, "clientH": 595, "scrollH": 1505}))
        self.assertTrue(live["pass"], live)

    def test_scrolling_that_still_never_reveals_the_last_item_fails(self) -> None:
        # A box that reports overflow but whose last row cannot be brought under the pointer -- clipped
        # by an ancestor, or covered by the top bar -- is the failure the hit-test exists to catch.
        covered = self.check(self.verdict_for({"total": 23, "atTop": 9, "afterScroll": 11, "overflow": True,
                                              "lastHitInside": False, "disclosures": 7, "clientH": 595, "scrollH": 1505}))
        self.assertFalse(covered["pass"], covered)

    def test_captions_that_are_not_disclosures_fail_the_group_check(self) -> None:
        # The shipped shape before APG was applied: every group caption was a <span>, so the rail could
        # scroll but a short window still showed a third of it and nothing could shorten it.
        verdict = self.verdict_for({"total": 23, "atTop": 9, "afterScroll": 11, "overflow": True,
                                    "lastHitInside": True, "disclosures": 0,
                                    "clientH": 595, "scrollH": 1505})
        self.assertTrue(self.check(verdict)["pass"], "reachability itself is fine here; only the disclosure is missing")
        disclosure = next(c for c in verdict["checks"] if c["check"] == "nav_groups_are_disclosures")
        self.assertFalse(disclosure["pass"], disclosure)
        self.assertIn("disclosures=0", disclosure["detail"])

    def test_a_rail_that_renders_nothing_cannot_claim_reachability(self) -> None:
        empty = self.check(self.verdict_for({"total": 0, "atTop": 0, "afterScroll": 0, "overflow": False,
                                             "lastHitInside": False, "clientH": 0, "scrollH": 0}))
        self.assertFalse(empty["pass"], empty)
        self.assertIn("rendered nothing", empty["detail"])

    def test_a_short_rail_passes_without_needing_to_scroll(self) -> None:
        fits = self.check(self.verdict_for({"total": 4, "atTop": 4, "afterScroll": 4, "overflow": False,
                                            "lastHitInside": True, "disclosures": 4, "clientH": 300, "scrollH": 300}))
        self.assertTrue(fits["pass"], fits)


class ClippedTextTests(unittest.TestCase):
    """A box that ellipsises its own text is invisible to every rect check.

    Found by looking at the HUD: four KPI cards rendered `UNKNO…` because b10's 35px display size
    needs 193px and the 440px window leaves a two-up card 184px. The value was `UNKNOWN` — the token
    the product uses to say it will not guess — truncated into looking like the prefix of a number.
    """

    def test_a_clip_the_page_does_not_elsewhere_state_fails_by_name(self) -> None:
        measured = good_measured("compact")
        measured["__clippedText"] = [{"tag": "STRONG", "cls": "truncate text-[22px]",
                                      "text": "UNKNOWN", "lostPx": 9, "fontSize": "35px",
                                      "carried": False}]
        v = geometry.verdict(measured, "compact")
        bad = [c for c in v["checks"] if c["check"] == "no_text_is_clipped_without_a_fallback"][0]
        self.assertFalse(bad["pass"])
        self.assertIn("UNKNOWN", bad["detail"])
        self.assertIn("text-[22px]", bad["detail"])
        self.assertFalse(v["passed"])

    def test_a_clip_whole_string_survives_in_an_aria_label_is_allowed(self) -> None:
        # The search field loses 11px of its placeholder to the ellipsis and says the same words in
        # `aria-label`; that is a cosmetic truncation, not a lost fact, and failing it would push
        # toward widening boxes for the wrong reason.
        v = geometry.verdict(good_measured("compact"), "compact")
        ok = [c for c in v["checks"] if c["check"] == "no_text_is_clipped_without_a_fallback"][0]
        self.assertTrue(ok["pass"], ok["detail"])

    def test_the_desktop_shell_reports_no_clipped_text_at_all(self) -> None:
        measured = good_measured("full")
        measured["__clippedText"] = []
        ok = [c for c in geometry.verdict(measured, "full")["checks"]
              if c["check"] == "no_text_is_clipped_without_a_fallback"][0]
        self.assertTrue(ok["pass"])


class WindowFloorTests(unittest.TestCase):
    """The third pass measures the smallest window the shipped product can be resized into.

    It exists because the standard once promised a "< 760px: icon rail or drawer" band. That band is
    unreachable: tauri.conf.json floors the main window at 900x600 and the 440x680 surface renders no
    rail at all. Building for the invented row produced first an icon rail whose 23 lanes measured as
    23 identical dots, then a drawer — both of which the owner decision of 2026-10-07 had already
    deleted. So the gate now measures the real floor and refuses any phone surface.
    """

    def setUp(self) -> None:
        self.v = geometry.verdict(good_measured("floor"), "floor")

    def test_the_floor_measurement_passes_and_adds_the_bar_target_check(self) -> None:
        self.assertTrue(self.v["passed"], json.dumps(self.v["checks"], indent=1))
        names = {c["check"] for c in self.v["checks"]}
        self.assertIn("top_bar_targets_meet_the_floor", names)
        self.assertIn("rail_always_present", names)
        self.assertNotIn("compact_has_no_rail", names)

    def test_the_floor_the_gate_measures_is_the_floor_the_window_config_declares(self) -> None:
        # Bound to the machine authority rather than restated: if tauri.conf.json ever lowers the main
        # window below 900x600, this fails and the band question gets re-opened on purpose instead of
        # silently re-appearing as a CSS media query.
        conf = json.loads((ROOT / "apps/observer/src-tauri/tauri.conf.json")
                          .read_text(encoding="utf-8"))
        main = {w["label"]: w for w in conf["app"]["windows"]}["main"]
        self.assertEqual(geometry.VIEWPORT["floor"], (main["minWidth"], main["minHeight"]))
        self.assertGreaterEqual(main["minWidth"], 900, "the phone shape this gate forbids is back")

    def test_a_rail_that_collapses_at_the_floor_fails(self) -> None:
        measured = good_measured("floor")
        measured[".sidebar"] = [element(0, 60, 600, 1000)]
        v = geometry.verdict(measured, "floor")
        self.assertFalse(v["passed"])
        self.assertFalse([c for c in v["checks"] if c["check"] == "rail_always_present"][0]["pass"])

    def test_a_painted_mobile_surface_fails_every_window_including_the_hud(self) -> None:
        for view in ("full", "compact", "floor"):
            measured = good_measured(view)
            measured["__mobileNav"] = ["rail-toggle"]
            v = geometry.verdict(measured, view)
            bad = [c for c in v["checks"] if c["check"] == "no_mobile_navigation_surface_is_painted"]
            self.assertTrue(bad, f"{view} did not assert the mobile sweep at all")
            self.assertFalse(bad[0]["pass"], view)
            self.assertFalse(v["passed"])

    def test_two_lanes_spelling_the_same_thing_are_reported_by_name(self) -> None:
        measured = good_measured("floor")
        measured["__navReach"]["labels"][7] = measured["__navReach"]["labels"][6]
        v = geometry.verdict(measured, "floor")
        bad = [c for c in v["checks"] if c["check"] == "lane_labels_are_distinguishable"][0]
        self.assertFalse(bad["pass"])
        self.assertIn("车道6", bad["detail"])

    def test_an_unnamed_lane_is_convicted_by_its_lane_id(self) -> None:
        measured = good_measured("floor")
        measured["__navReach"]["nameless"] = ["evidence"]
        bad = [c for c in geometry.verdict(measured, "floor")["checks"]
               if c["check"] == "every_lane_is_named"][0]
        self.assertFalse(bad["pass"])
        self.assertIn("evidence", bad["detail"])

    def test_a_lane_target_below_the_floor_names_the_lane_and_keeps_hidden_lanes_out(self) -> None:
        measured = good_measured("floor")
        measured["__navReach"]["targets"][3] = {"lane": "lane3", "w": 240.0, "h": 18.0}
        bad = [c for c in geometry.verdict(measured, "floor")["checks"]
               if c["check"] == "lane_targets_meet_the_floor"][0]
        self.assertFalse(bad["pass"])
        self.assertIn("lane3", bad["detail"])

        # A lane inside a collapsed group measures 0x0: it renders nothing, so it cannot be an offender.
        measured = good_measured("floor")
        measured["__navReach"]["targets"][3] = {"lane": "lane3", "w": 0, "h": 0}
        self.assertTrue([c for c in geometry.verdict(measured, "floor")["checks"]
                         if c["check"] == "lane_targets_meet_the_floor"][0]["pass"])

    def test_a_bar_control_below_the_floor_is_named_by_selector(self) -> None:
        measured = good_measured("floor")
        measured["__barTargets"][0] = {"sel": ".top-actions button", "painted": True,
                                       "w": 22.0, "h": 30.0}
        bad = [c for c in geometry.verdict(measured, "floor")["checks"]
               if c["check"] == "top_bar_targets_meet_the_floor"][0]
        self.assertFalse(bad["pass"])
        self.assertIn(".top-actions button", bad["detail"])

    def test_a_bar_that_painted_nothing_cannot_report_a_clean_target_bill(self) -> None:
        measured = good_measured("floor")
        measured["__barTargets"] = []
        self.assertFalse([c for c in geometry.verdict(measured, "floor")["checks"]
                          if c["check"] == "top_bar_targets_meet_the_floor"][0]["pass"])

    def test_off_screen_is_not_reported_as_obscured_but_a_covered_control_still_is(self) -> None:
        measured = good_measured("floor")
        measured["__focusObscured"].append(
            {"sel": ".nav button[data-lane]", "focused": True, "visible": True,
             "inViewport": False, "top": 640.0, "bottom": 690.0, "hitIsSelfOrChild": False})
        self.assertTrue([c for c in geometry.verdict(measured, "floor")["checks"]
                         if c["check"] == "focused_control_is_not_obscured"][0]["pass"])

        measured["__focusObscured"][0].update({"inViewport": True, "hitIsSelfOrChild": False})
        self.assertFalse([c for c in geometry.verdict(measured, "floor")["checks"]
                          if c["check"] == "focused_control_is_not_obscured"][0]["pass"])


class RegionBoundaryTests(unittest.TestCase):
    """The last assertion family SCREEN_SPEC owed: where one region ends and the next begins, and
    whether a keyboard user can actually reach what they can see."""

    def _check(self, name: str, measured=None):
        v = geometry.verdict(measured if measured is not None else good_measured("full"), "full")
        return [c for c in v["checks"] if c["check"] == name][0]

    def test_the_shipped_shape_passes_both_boundary_checks(self) -> None:
        self.assertTrue(self._check("content_clears_topbar")["pass"])
        self.assertTrue(self._check("topbar_edge_is_painted")["pass"])

    def test_content_starting_under_the_bar_fails(self) -> None:
        # The 128px overlap this project measured once: content scrolled beneath an opaque bar, and
        # every container-level check stayed green because the containers were all "present".
        measured = good_measured("full")
        measured["__edges"]["content"]["top"] = 40.0
        failed = self._check("content_clears_topbar", measured)
        self.assertFalse(failed["pass"])
        self.assertIn("overlap=89.0", failed["detail"])

    def test_an_unpainted_and_unshadowed_edge_fails(self) -> None:
        measured = good_measured("full")
        measured["__edges"]["topbar"]["borderBottomWidth"] = "0px"
        measured["__edges"]["topbar"]["boxShadow"] = "none"
        self.assertFalse(self._check("topbar_edge_is_painted", measured)["pass"])

    def test_a_shadow_alone_is_enough_to_count_as_an_edge(self) -> None:
        # Not a loophole: the standard allows either, and a hairline at 60% alpha can be invisible on
        # some panels while a shadow is not. What must fail is a boundary carried by nothing.
        measured = good_measured("full")
        measured["__edges"]["topbar"]["borderBottomWidth"] = "0px"
        measured["__edges"]["topbar"]["boxShadow"] = "0 1px 0 rgb(23 67 93)"
        self.assertTrue(self._check("topbar_edge_is_painted", measured)["pass"])

    def test_a_focused_control_under_an_overlay_is_reported_obscured(self) -> None:
        measured = good_measured("full")
        measured["__focusObscured"][1]["hitIsSelfOrChild"] = False
        failed = self._check("focused_control_is_not_obscured", measured)
        self.assertFalse(failed["pass"])
        self.assertIn(".top-actions button", failed["detail"])

    def test_a_visible_control_that_refuses_focus_is_not_a_pass(self) -> None:
        # The other way to be unreachable: nothing covers it, it simply never takes focus.
        measured = good_measured("full")
        measured["__focusObscured"][0]["focused"] = False
        self.assertFalse(self._check("every_visible_probe_takes_focus", measured)["pass"])

    def test_a_harvest_without_the_edge_data_fails_instead_of_passing(self) -> None:
        """A key the page stopped producing must not read as "no problems found"."""
        measured = good_measured("full")
        del measured["__edges"]
        measured["__focusObscured"] = []
        self.assertFalse(self._check("content_clears_topbar", measured)["pass"])
        self.assertFalse(self._check("topbar_edge_is_painted", measured)["pass"])
        self.assertFalse(self._check("focused_control_is_not_obscured", measured)["pass"])

    def test_px_parsing_handles_the_shapes_css_actually_returns(self) -> None:
        self.assertEqual(geometry._px("1px"), 1.0)
        self.assertEqual(geometry._px("0.8px"), 0.8)
        self.assertEqual(geometry._px("calc(1px + 0.5px)"), 1.0)
        self.assertEqual(geometry._px(None), 0.0)
        self.assertEqual(geometry._px("none"), 0.0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
