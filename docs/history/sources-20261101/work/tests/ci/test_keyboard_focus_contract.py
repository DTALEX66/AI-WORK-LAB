"""Gate: keyboard operability in the real WebView2 is a verdict, not a printout.

`scripts/audit/u19_keyboard_focus_cdp.py` is the first `Input.dispatchKeyEvent` user in this
repository, so until it existed every "Tab reaches the lanes in order / a focus ring is visible /
Enter activates a lane / Escape is inert" sentence in the UI task card was unverified — and the
jsdom contracts in `frontend/src/keyboardFocus.contract.test.tsx` cannot cover it: jsdom does no
focus traversal and no layout.

Everything here runs on the PURE decision function, plus the probe's socket helpers against fake
peers. No browser and, above all, no desktop launch is started by any test in this file.
The negative controls exist because an instrument that cannot go red is not a gate (the G3 finding
on the geometry probe, ERR-140 on swallowing why a probe did not run, E5 on asserting against a
marker that does not exist): a truncated tab cycle, a missing focus ring, a stuck readback, an
identical lane after Enter and — the one that bites hardest — a blind write detector must each turn
the gate red on their own.
"""
from __future__ import annotations

import importlib.util
import json
import shutil
import socket
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "audit" / "u19_keyboard_focus_cdp.py"

spec = importlib.util.spec_from_file_location("keyboard_focus_cdp", SCRIPT)
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)  # type: ignore[attr-defined]

RING = {"style": "solid", "width": "2px", "color": "rgb(110, 180, 254)", "offset": "1px"}
OUTLINE_NONE = {"style": "none", "width": "0px", "color": "rgb(238, 246, 252)", "offset": "0px"}

# The rail alone is 22 consecutive stops, so a cycle has to clear it, leave the sidebar and come
# back. These numbers mirror what the instrument measured on this machine (22-23 lane buttons,
# 29-35 focusable stops, the rail reached only after the top bar).
TOPBAR = [f"div#root > div > main > header > button:nth-of-type({i + 1})" for i in range(6)]
LANES = [f'button[data-lane="{lane}"' + "]" for lane in
         ("overview", "work", "executions", "task-packs", "delivery", "execution-detail", "agents",
          "projects", "workflows", "rules-policy", "approvals", "audit", "trust", "integrations",
          "workflow-editor", "observer", "software", "models", "monitoring", "memory", "tools",
          "settings")]
CONTENT = ["div#content > button:nth-of-type(1)", "div#content > a:nth-of-type(1)"]
LANE_PREFIX = 'button[data-lane="'
PRESSED = "tools"


def lane_of(selector: str) -> str | None:
    if not selector.startswith(LANE_PREFIX):
        return None
    return selector[len(LANE_PREFIX):].removesuffix("]") or None


def step(selector: str, index: int) -> dict:
    lane = lane_of(selector)
    return {
        "index": index, "selector": selector, "tag": "button", "lane": lane,
        "insideSidebar": lane is not None, "insideNav": lane is not None,
        "focusVisible": True, "outline": dict(RING), "selectorUnique": 1,
        "selectorIsActive": True, "visible": True, "disabled": False, "tabIndex": 0,
        "label": lane or selector[-24:], "changedFromPrevious": True,
    }


def walk(selectors: list[str], count: int) -> list[dict]:
    """Shift+Tab retraces the recorded forward order: from the stop before the current one."""
    return [{"index": j, "selector": selectors[len(selectors) - 1 - j], "lane": None,
             "insideSidebar": False, "focusVisible": True, "outline": dict(RING)}
            for j in range(1, count + 1)]


def forward_order() -> list[str]:
    """Two full passes: the rail is only proven cyclic if focus leaves it and comes back."""
    return (TOPBAR + LANES + CONTENT) * 2


def page(view: str = "work", chars: int = 3520, sig: str = "3520:7d76edec") -> dict:
    return {"href": f"http://tauri.localhost/index.html?view={view}", "aboutBlank": False,
            "title": "WORK-LAB Observer · AI Agent Control Tower", "hasFocus": True,
            "rootChildren": 1, "laneButtons": 22, "focusables": 34, "viewParam": view,
            "ariaCurrentLane": view, "activeClassLane": view, "mainChars": chars,
            "mainSig": sig, "laneRegionFound": True, "laneChars": chars, "laneSig": sig,
            "laneHeading": "执行", "mainHead": "搜索 通知 工作区"}


def measurement(tab_count: int = 60, shift_count: int = 4) -> dict:
    order = forward_order()[:tab_count]
    before = page()
    return {
        "base": before,
        "instrumentControl": {"requested": LANE_PREFIX + 'settings"]',
                              "readBack": LANE_PREFIX + 'settings"]', "sameNode": True,
                              "unique": 1},
        "tabs": [step(sel, i) for i, sel in enumerate(order)],
        "shiftTabs": walk(order, shift_count),
        "enter": {"before": before, "pressedLane": PRESSED,
                  "focusedBeforeEnter": LANE_PREFIX + f'{PRESSED}"]', "seekTabPresses": 12,
                  "after": page(view=PRESSED, chars=90, sig="90:80455cb"),
                  "focusAfterEnterSelector": LANE_PREFIX + f'{PRESSED}"]',
                  "focusAfterEnterLane": PRESSED},
        "escape": {"detectorPresent": True,
                   "writes": [{"kind": "fetch", "method": "GET",
                               "url": "http://127.0.0.1:51882/api/v1/snapshot"}],
                   "invokes": [], "laneBefore": PRESSED, "laneAfter": PRESSED,
                   "mainSigBefore": "90:80455cb", "mainSigAfter": "90:80455cb"},
        "control": {"observedByPageHook": True, "observedByCdpNetwork": True,
                    "writes": [{"kind": "fetch", "method": "POST",
                                "url": "http://tauri.localhost" + gate.CONTROL_PATH}]},
    }


def check_of(verdict: dict, name: str) -> dict:
    return next(c for c in verdict["checks"] if c["check"] == name)


class CleanMeasurementPasses(unittest.TestCase):
    def setUp(self) -> None:
        self.v = gate.judge(measurement())

    def test_a_full_measurement_passes_and_names_every_check(self) -> None:
        self.assertTrue(self.v["passed"], json.dumps(self.v["checks"], indent=1,
                                                     ensure_ascii=False))
        self.assertEqual(self.v["failing"], [])
        self.assertEqual({c["check"] for c in self.v["checks"]},
                         {"surface_is_the_real_bundle", "instrument_reads_active_element",
                          "focus_moves_under_tab", "selectors_resolve_to_the_focused_node",
                          "tab_cycle_through_sidebar_completes", "focus_visible_ring_rendered",
                          "shift_tab_retraces_forward_order", "enter_activates_the_focused_lane",
                          "write_detector_is_proven", "escape_fires_no_write_action",
                          "focus_survives_activation", "escape_changes_no_visible_state",
                          "document_wraps_within_tab_budget"})

    def test_the_four_claims_of_the_task_card_are_each_decided(self) -> None:
        for name in ("focus_moves_under_tab", "tab_cycle_through_sidebar_completes",
                     "focus_visible_ring_rendered", "enter_activates_the_focused_lane",
                     "escape_fires_no_write_action"):
            self.assertTrue(check_of(self.v, name)["pass"], name)

    def test_a_passing_detail_names_the_quantity_it_passed_on(self) -> None:
        # The geometry gate once logged `topbar_measured PASS no .topbar element`; a PASS whose own
        # detail reads like an absence is how a green line hides an unmeasured claim.
        cycle = check_of(self.v, "tab_cycle_through_sidebar_completes")
        for token in ("enteredIdx=", "leftIdx=", "returnedIdx=", "laneButtonStops="):
            self.assertIn(token, cycle["detail"])
        self.assertIn("laneFocusStops=",
                      check_of(self.v, "focus_visible_ring_rendered")["detail"])

    def test_a_read_only_fetch_during_escape_is_not_a_write(self) -> None:
        # The app legitimately polls /api/v1/snapshot. Counting that as a write would red-gate the
        # observer for doing the one thing it is allowed to do.
        m = measurement()
        m["escape"]["writes"].append({"kind": "fetch", "method": "HEAD", "url": "x"})
        self.assertTrue(check_of(gate.judge(m), "escape_fires_no_write_action")["pass"])

    def test_the_gating_split_is_the_documented_one(self) -> None:
        reported = {"focus_survives_activation", "escape_changes_no_visible_state",
                    "document_wraps_within_tab_budget"}
        gating = {c["check"] for c in self.v["checks"] if c["gating"]}
        self.assertEqual(gating, {c["check"] for c in self.v["checks"]} - reported)
        for name in reported:
            self.assertTrue(check_of(self.v, name)["pass"], name)


class NegativeControls(unittest.TestCase):
    """Each mutation breaks exactly one claim; a mutation that stays green is decoration."""

    @staticmethod
    def failing(mutated: dict) -> list[str]:
        return gate.judge(mutated)["failing"]

    def test_a_truncated_tab_cycle_turns_the_gate_red(self) -> None:
        # Focus entered the rail and the run stopped inside it: entered but never left, so nothing
        # was returned to — a partial walk, not a cycle.
        m = measurement(tab_count=len(TOPBAR) + len(LANES) - 4)
        self.assertIn("tab_cycle_through_sidebar_completes", self.failing(m))
        self.assertFalse(gate.judge(m)["passed"])

    def test_focus_that_never_enters_the_rail_turns_the_gate_red(self) -> None:
        m = measurement()
        for s in m["tabs"]:
            s["insideSidebar"] = False
            s["lane"] = None
        self.assertIn("tab_cycle_through_sidebar_completes", self.failing(m))

    def test_a_missing_focus_ring_turns_the_gate_red(self) -> None:
        # The whole point of reading getComputedStyle instead of CSS text: the rule can exist and
        # still not paint on the element that holds focus.
        for break_it in ("outline-none", "not-focus-visible", "transparent-colour"):
            m = measurement()
            victim = next(s for s in m["tabs"] if s.get("lane"))
            if break_it == "outline-none":
                victim["outline"] = dict(OUTLINE_NONE)
            elif break_it == "not-focus-visible":
                victim["focusVisible"] = False
            else:
                victim["outline"] = dict(RING, color="rgba(0, 0, 0, 0)")
            self.assertIn("focus_visible_ring_rendered", self.failing(m), break_it)

    def test_an_instrument_that_never_moved_is_red_not_green(self) -> None:
        # This repository has already been bitten by a probe whose number never changed. A stuck
        # activeElement readback would otherwise satisfy "focus order measured".
        m = measurement()
        for s in m["tabs"]:
            s["selector"] = LANE_PREFIX + 'overview"]'
            s["lane"] = "overview"
            s["insideSidebar"] = True
        self.assertIn("focus_moves_under_tab", self.failing(m))

    def test_a_selector_that_does_not_resolve_back_is_red(self) -> None:
        # Two different elements reporting the same string looks identical to a stuck probe, so every
        # generated selector has to resolve back to the node that held focus.
        m = measurement()
        m["tabs"][12]["selectorIsActive"] = False
        self.assertIn("selectors_resolve_to_the_focused_node", self.failing(m))

    def test_enter_that_moves_routing_but_no_visible_lane_is_red(self) -> None:
        # aria-current and ?view= can both update while the lane renders the same bytes — exactly the
        # "two different views report identical values" pattern that means suspect the instrument.
        m = measurement()
        before = m["enter"]["before"]
        m["enter"]["after"] = page(view=PRESSED, chars=before["laneChars"], sig=before["laneSig"])
        self.assertIn("enter_activates_the_focused_lane", self.failing(m))

    def test_enter_on_the_already_active_lane_is_red(self) -> None:
        # Pressing Enter on the lane that is already current changes nothing and proves nothing.
        m = measurement()
        m["enter"]["pressedLane"] = "work"
        m["enter"]["after"] = page()
        self.assertIn("enter_activates_the_focused_lane", self.failing(m))

    def test_enter_that_activates_the_wrong_lane_is_red(self) -> None:
        m = measurement()
        m["enter"]["after"]["activeClassLane"] = "monitoring"
        self.assertIn("enter_activates_the_focused_lane", self.failing(m))

    def test_a_blind_write_detector_voids_the_escape_claim(self) -> None:
        # "Saw no write" and "cannot see writes" must never share a verdict: the control POST has to
        # be observed before the silence on Escape means anything.
        m = measurement()
        m["control"]["observedByPageHook"] = False
        self.assertIn("write_detector_is_proven", self.failing(m))

    def test_escape_that_fires_a_write_is_red(self) -> None:
        for write in ({"kind": "fetch", "method": "POST", "url": "/api/v1/approve"},
                      {"kind": "xhr", "method": "PUT", "url": "/api/v1/state"},
                      {"kind": "fetch", "method": "DELETE", "url": "/api/v1/task/1"}):
            m = measurement()
            m["escape"]["writes"] = [write]
            self.assertIn("escape_fires_no_write_action", self.failing(m), write["method"])

    def test_escape_that_reaches_the_native_command_layer_is_red(self) -> None:
        m = measurement()
        m["escape"]["invokes"] = [{"cmd": "approve_execution"}]
        self.assertIn("escape_fires_no_write_action", self.failing(m))

    def test_a_detector_that_is_not_installed_cannot_claim_inertness(self) -> None:
        m = measurement()
        m["escape"]["detectorPresent"] = False
        self.assertIn("escape_fires_no_write_action", self.failing(m))

    def test_shift_tab_that_keeps_going_forward_is_red(self) -> None:
        m = measurement()
        m["shiftTabs"] = walk(m["tabs"] and forward_order(), 3)[:-1] + \
            [dict(step(CONTENT[1], 3))]
        self.assertIn("shift_tab_retraces_forward_order", self.failing(m))

    def test_a_page_that_is_not_the_built_bundle_is_red(self) -> None:
        # A CDP target that answers is not proof of the shipped surface: about:blank and a rail-less
        # DOM both serve HTTP 200.
        for broken in ({"aboutBlank": True}, {"laneButtons": 0}, {"rootChildren": 0}):
            m = measurement()
            m["base"].update(broken)
            self.assertIn("surface_is_the_real_bundle", self.failing(m), str(broken))

    def test_a_programmatic_focus_that_is_not_read_back_voids_everything_below_it(self) -> None:
        m = measurement()
        m["instrumentControl"]["sameNode"] = False
        self.assertIn("instrument_reads_active_element", self.failing(m))

    def test_an_ambiguous_readback_selector_is_red_even_with_good_numbers(self) -> None:
        # unique != 1 means the thing I focused is not identifiable, so the cycle below it could be
        # any element's order.
        m = measurement()
        m["instrumentControl"]["unique"] = 3
        self.assertIn("instrument_reads_active_element", self.failing(m))


class FailClosed(unittest.TestCase):
    def test_an_empty_or_partial_measurement_never_passes(self) -> None:
        # No run means no gate. main() reports NOT_RUN for this; judge() must still refuse to call a
        # missing measurement a pass.
        whole = measurement()
        partials = [{}, {"tabs": []}, {"tabs": whole["tabs"]}, {"base": page()},
                    {"base": page(), "tabs": whole["tabs"]},
                    {"tabs": [step("BODY", 0)], "base": page()},
                    {k: v for k, v in whole.items() if k != "control"},
                    {k: v for k, v in whole.items() if k != "escape"},
                    {k: v for k, v in whole.items() if k != "instrumentControl"}]
        for m in partials:
            v = gate.judge(m)
            self.assertFalse(v["passed"], str(m)[:80])
            self.assertTrue(v["failing"], "a passing verdict needs every check present")

    def test_judge_does_not_crash_on_stray_types(self) -> None:
        m = measurement()
        m["tabs"][3]["outline"] = None
        m["escape"]["writes"] = None
        m["control"]["writes"] = [{}]
        m["shiftTabs"] = [{}]
        v = gate.judge(m)
        self.assertIsInstance(v["passed"], bool)

    def test_side_findings_are_reported_without_flipping_the_verdict(self) -> None:
        # Focus stranded after Enter is a real keyboard defect, but it is not one of the four claims
        # this gate exists for, so it is reported rather than gating — and it must stay visible.
        m = measurement()
        m["enter"]["focusAfterEnterLane"] = None
        m["enter"]["focusAfterEnterSelector"] = "BODY"
        v = gate.judge(m)
        self.assertTrue(v["passed"], json.dumps(v["failing"]))
        self.assertIn("focus_survives_activation", v["sideFindings"])

    def test_the_survival_check_compares_the_lane_not_the_selector(self) -> None:
        # `button[data-lane="tools"]` never equals `tools`; the first cut compared exactly those two
        # and read red on a run where focus had in fact stayed on the pressed lane.
        self.assertTrue(check_of(gate.judge(measurement()), "focus_survives_activation")["pass"])

    def test_wrap_is_reported_without_gating_the_verdict(self) -> None:
        # "Tab came back around the whole document" is an extra fact, not one of the four claims.
        # Here every stop is made unique, so the wrap check goes red while the sidebar cycle, the
        # ring, Enter and Escape all stay green.
        m = measurement()
        for i, s in enumerate(m["tabs"]):
            s["selector"] = f"{s['selector']}@{i}"
        sels = [s["selector"] for s in m["tabs"]]
        m["shiftTabs"] = walk(sels, len(m["shiftTabs"]))
        v = gate.judge(m)
        self.assertIn("document_wraps_within_tab_budget", v["sideFindings"])
        self.assertTrue(v["passed"], json.dumps(v["failing"]))
        self.assertFalse(check_of(v, "document_wraps_within_tab_budget")["gating"])


class RailPolling(unittest.TestCase):
    """The rail is polled, because one read of a loading page is not a refusal."""

    @staticmethod
    def fake(sequence: list[object]) -> tuple[type, list[int]]:
        calls: list[int] = []

        class FakeCDP:
            def eval_json(self, expr: str, label: str) -> dict:
                calls.append(1)
                item = sequence[min(len(calls) - 1, len(sequence) - 1)]
                if isinstance(item, Exception):
                    raise item
                return dict(item)  # type: ignore[arg-type]

        return FakeCDP, calls

    def test_a_transient_empty_document_is_awaited_not_reported_as_no_rail(self) -> None:
        # Measured 2026-10-08 against this bundle: a read that saw 23 lane buttons was followed
        # milliseconds later by one seeing an empty document — the shell rewrites its own deep-link
        # URL and the page settles underneath the probe.
        client, calls = self.fake([{"page": {"laneButtons": 0}, "shape": {"laneButtons": 0}},
                                   {"page": {"laneButtons": 0}, "shape": {"laneButtons": 0}},
                                   {"page": {"laneButtons": 23}, "shape": {"laneButtons": 23}}])
        out = gate.read_rail(client(), samples=6, pause=0.001)  # type: ignore[arg-type]
        self.assertEqual(out["page"]["laneButtons"], 23)
        self.assertEqual(out["sample"], 3)
        self.assertNotIn("exhausted", out)
        self.assertEqual(len(calls), 3)

    def test_a_rail_that_never_answers_is_reported_as_exhausted(self) -> None:
        client, calls = self.fake([{"page": {"laneButtons": 0},
                                    "shape": {"navButtons": 9, "laneButtons": 0}}])
        out = gate.read_rail(client(), samples=4, pause=0.001)  # type: ignore[arg-type]
        self.assertTrue(out["exhausted"])
        self.assertEqual(out["sample"], 4)
        self.assertEqual(len(calls), 4)

    def test_a_broken_expression_does_not_end_the_poll_early(self) -> None:
        client, _calls = self.fake([gate.ProbeError("rail-shape: refused this expression"),
                                    {"page": {"laneButtons": 22}, "shape": {}}])
        out = gate.read_rail(client(), samples=5, pause=0.001)  # type: ignore[arg-type]
        self.assertEqual(out["page"]["laneButtons"], 22)


class KeyProtocol(unittest.TestCase):
    """The dispatch shape is what the protocol requires; pinned without a browser."""

    @staticmethod
    def press(name: str) -> list[dict]:
        sent: list[tuple[str, dict]] = []

        class Sock:
            def settimeout(self, _t):
                pass

        class FakeBaseCDP:
            _sock = Sock()

            def _send_cmd(self, method, params=None):
                sent.append((method, dict(params or {})))
                return {}

        client = gate.KeyedCDP.__new__(gate.KeyedCDP)
        client._cdp = FakeBaseCDP()
        client.events = []
        client.press(name)
        assert all(m == "Input.dispatchKeyEvent" for m, _ in sent), sent
        return [p for _, p in sent]

    def test_tab_is_a_raw_keydown_and_keyup_with_no_text(self) -> None:
        events = self.press("Tab")
        self.assertEqual([e["type"] for e in events], ["rawKeyDown", "keyUp"])
        for e in events:
            self.assertEqual(e["key"], "Tab")
            self.assertEqual(e["code"], "Tab")
            self.assertEqual(e["windowsVirtualKeyCode"], 9)
            self.assertNotIn("text", e)
        self.assertEqual(events[0]["modifiers"], 0)

    def test_shift_tab_carries_the_shift_bit(self) -> None:
        events = self.press("ShiftTab")
        self.assertEqual([e["type"] for e in events], ["rawKeyDown", "keyUp"])
        for e in events:
            self.assertEqual(e["modifiers"], gate.MOD_SHIFT)
            self.assertEqual(e["key"], "Tab")

    def test_enter_is_rawkeydown_char_keyup_because_activation_reads_the_text_event(self) -> None:
        events = self.press("Enter")
        self.assertEqual([e["type"] for e in events], ["rawKeyDown", "char", "keyUp"])
        self.assertNotIn("text", events[0])
        self.assertEqual(events[1]["text"], "\r")
        self.assertEqual(events[1]["unmodifiedText"], "\r")
        self.assertEqual(events[1]["windowsVirtualKeyCode"], 13)
        self.assertNotIn("text", events[2])

    def test_escape_sends_no_text_and_no_modifier(self) -> None:
        events = self.press("Escape")
        self.assertEqual([e["type"] for e in events], ["rawKeyDown", "keyUp"])
        self.assertEqual(events[0]["windowsVirtualKeyCode"], 27)
        self.assertEqual(events[0]["modifiers"], 0)

    def test_the_cdp_cross_check_counts_only_non_read_requests(self) -> None:
        client = gate.KeyedCDP.__new__(gate.KeyedCDP)
        client.events = [
            {"method": "Network.requestWillBeSent",
             "params": {"request": {"method": "GET", "url": "/api/v1/snapshot"}}},
            {"method": "Network.requestWillBeSent",
             "params": {"request": {"method": "POST", "url": "/api/v1/whatever"}}},
            {"method": "Page.loadEventFired", "params": {}},
        ]
        self.assertEqual(client.non_get_requests(),
                         [{"method": "POST", "url": "/api/v1/whatever"}])

    def test_ring_renders_under_the_units_the_browser_actually_reports(self) -> None:
        self.assertTrue(gate.ring_renders({"focusVisible": True, "outline": dict(RING)}))
        self.assertFalse(gate.ring_renders({"focusVisible": False, "outline": dict(RING)}))
        self.assertTrue(gate.ring_renders({"focusVisible": True,
                                           "outline": dict(RING, width="medium")}))
        self.assertFalse(gate.ring_renders({"focusVisible": True, "outline": {}}))
        self.assertFalse(gate.ring_renders({"focusVisible": "unsupported:SyntaxError",
                                            "outline": dict(RING)}))


class ReadbackDiagnostics(unittest.TestCase):
    def test_a_refused_expression_is_named_not_reported_as_an_empty_readback(self) -> None:
        # This one is mine: a broken expression of my own came back as "returned no value", which is
        # the sentence a dead instrument produces. `exceptionDetails` has to be surfaced.
        client = gate.KeyedCDP.__new__(gate.KeyedCDP)

        class Refusing:
            def _send_cmd(self, method, params=None):
                return {"exceptionDetails": {"text": "TypeError: q is not a function"}}

        client._cdp = Refusing()
        with self.assertRaises(gate.ProbeError) as caught:
            client.eval_json("1+1", "rail-shape")
        self.assertIn("refused this expression", str(caught.exception))
        self.assertIn("q is not a function", str(caught.exception))

    def test_a_truly_absent_value_is_still_reported_as_a_dead_readback(self) -> None:
        client = gate.KeyedCDP.__new__(gate.KeyedCDP)

        class Silent:
            def _send_cmd(self, method, params=None):
                return {"result": {"type": "undefined"}}

        client._cdp = Silent()
        with self.assertRaises(gate.ProbeError) as caught:
            client.eval_json("1+1", "x")
        self.assertIn("dead, not empty", str(caught.exception))


class DevtoolsDiscovery(unittest.TestCase):
    """Two request shapes, because this machine's runtimes disagree about the DevTools endpoint."""

    @staticmethod
    def serve_once(response: bytes) -> int:
        srv = socket.socket()
        srv.bind(("127.0.0.1", 0))
        srv.listen(1)
        port = srv.getsockname()[1]

        def once():
            try:
                conn, _ = srv.accept()
            except OSError:
                return
            try:
                conn.recv(4096)
                conn.sendall(response)
            finally:
                conn.close()
                srv.close()

        threading.Thread(target=once, daemon=True).start()
        return port

    def test_a_refused_port_is_named_not_blank(self) -> None:
        self.assertTrue(gate.devtools_get("/json/version", 1, "u19").startswith("ERR connect"))

    def test_a_non_200_is_reported_as_http_status(self) -> None:
        port = self.serve_once(b"HTTP/1.1 500 Internal\r\nContent-Length: 2\r\n\r\nno")
        self.assertEqual(gate.devtools_get("/x", port, "blink"),
                         "ERR http HTTP/1.1 500 Internal")

    def test_a_body_shorter_than_its_content_length_is_refused(self) -> None:
        # A /json/list cut mid-document is how a page target vanishes while the gate still reads 200.
        port = self.serve_once(b"HTTP/1.1 200 OK\r\nContent-Length: 50\r\n\r\nshort")
        self.assertIn("truncated body 5 of 50", gate.devtools_get("/x", port, "blink"))

    def test_a_complete_body_is_returned(self) -> None:
        port = self.serve_once(b"HTTP/1.1 200 OK\r\nContent-Length: 4\r\n\r\nok!!")
        self.assertEqual(gate.devtools_get("/x", port, "blink"), "ok!!")

    def test_the_two_shapes_differ_exactly_where_the_runtimes_differ(self) -> None:
        # u19: Host carries the port and no User-Agent. blink: portless Host + UA + Accept.
        seen: list[bytes] = []
        srv = socket.socket()
        srv.bind(("127.0.0.1", 0))
        srv.listen(2)
        port = srv.getsockname()[1]

        def capture():
            for _ in range(2):
                try:
                    conn, _ = srv.accept()
                except OSError:
                    return
                seen.append(conn.recv(4096))
                conn.close()

        threading.Thread(target=capture, daemon=True).start()
        gate.devtools_get("/json/version", port, "u19")
        gate.devtools_get("/json/version", port, "blink")
        srv.close()
        time.sleep(0.4)
        self.assertEqual(len(seen), 2, seen)
        self.assertIn(f"Host: localhost:{port}".encode(), seen[0])
        self.assertNotIn(b"User-Agent", seen[0])
        self.assertIn(b"Host: 127.0.0.1\r\n", seen[1])
        self.assertIn(b"User-Agent:", seen[1])


class EmbeddedBundleResolution(unittest.TestCase):
    """Which binary the one desktop launch is spent on.

    Measured 2026-10-08: the newest `app.exe` on this machine was a dev-configured build that baked
    `http://localhost:1420` and carried no embedded bundle at all, so the gate attached two page
    targets with `rootChildren: 0`, spent its single launch on a blank surface, and reported
    `rail_never_painted` — a symptom of the wrong binary, not a finding about the product. The
    ranking that fixes it is decided on the bytes, before anything is started.
    """

    def setUp(self) -> None:
        self.scratch = Path(tempfile.mkdtemp(prefix="keyboard-focus-bundle-",
                                            dir=ROOT / ".project-local" / "runs"))

    def tearDown(self) -> None:
        shutil.rmtree(self.scratch, ignore_errors=True)

    def test_a_build_that_carries_a_bundle_reports_its_asset_names(self) -> None:
        exe = self.scratch / "app.exe"
        exe.write_bytes(b"junk" + b"index-C99dNGGi.js" + b"\x00" + b"index-CrlRBjCJ.css"
                        + b"padding")
        out = gate.carries_embedded_bundle(exe)
        self.assertTrue(out["embeddedBundle"], out)
        self.assertIn("index-C99dNGGi.js", out["assetNames"])

    def test_a_dev_configured_build_is_caught_before_the_launch(self) -> None:
        exe = self.scratch / "dev.exe"
        exe.write_bytes(b"http://localhost:1420/index.html" + b"\x00" * 32)
        out = gate.carries_embedded_bundle(exe)
        self.assertFalse(out["embeddedBundle"], out)
        self.assertEqual(out["assetNames"], [])

    def test_a_binary_that_cannot_be_read_is_reported_not_assumed_current(self) -> None:
        # A directory is not a launch candidate, and "unreadable" must never default to "fine".
        out = gate.carries_embedded_bundle(self.scratch)
        self.assertFalse(out.get("embeddedBundle", False), out)

    def test_the_bundle_check_gates_the_launch_instead_of_following_it(self) -> None:
        # Text order, same convention as the verdict-vocabulary test: if the check ran after the
        # launch it could not keep the single desktop window off a blank surface.
        text = SCRIPT.read_text(encoding="utf-8")
        check = text.index("embedded = carries_embedded_bundle(exe)")
        launched = text.index("app = subprocess.Popen(")
        self.assertLess(check, launched)
        self.assertIn('if not embedded.get("embeddedBundle"):', text)
        self.assertIn("no_embedded_bundle:", text)


class ProbeContract(unittest.TestCase):
    def test_the_probe_is_not_bound_to_the_authors_machine(self) -> None:
        text = SCRIPT.read_text(encoding="utf-8")
        self.assertNotIn(r"D:\All projects", text)
        self.assertIn("Path(__file__).resolve().parents[2]", text)

    def test_the_verdict_vocabulary_is_exactly_three_and_pass_needs_a_verdict(self) -> None:
        text = SCRIPT.read_text(encoding="utf-8")
        for token in ("KEYBOARD_FOCUS_GATE_PASS", "KEYBOARD_FOCUS_GATE_FAIL reason=",
                      "KEYBOARD_FOCUS_GATE_NOT_RUN reason="):
            self.assertIn(token, text)
        # The default is a refusal, not a pass: whatever else goes wrong, `verdict_line` starts as
        # NOT_RUN, so an abort cannot leave a green string in place.
        self.assertIn('verdict_line = "KEYBOARD_FOCUS_GATE_NOT_RUN reason=unknown"', text)
        # and the PASS line exists only inside the branch that judged a measurement
        self.assertLess(text.index('if verdict["passed"]:'), text.index('"KEYBOARD_FOCUS_GATE_PASS'))
        self.assertEqual(1, text.count('"KEYBOARD_FOCUS_GATE_PASS'),
                         "a second place that can print PASS is a second way to lie")

    def test_only_reads_are_exempt_from_the_write_detector(self) -> None:
        # The exemption list is the difference between "the observer polled" and "the observer
        # wrote"; widening it silently would un-gate the claim.
        self.assertEqual(gate.READ_METHODS, {"GET", "HEAD", "OPTIONS"})
        for method in ("POST", "PUT", "PATCH", "DELETE"):
            self.assertNotIn(method, gate.READ_METHODS)
        self.assertTrue(gate.CONTROL_PATH.startswith("/__"))
        self.assertNotIn("/api/v1", gate.CONTROL_PATH,
                         "the control write must not target a real endpoint")

    def test_the_control_write_expression_carries_the_same_path_the_verdict_checks(self) -> None:
        # A control that posts somewhere other than where the detector looks is a blind detector
        # wearing a green "proven" line.
        self.assertIn(gate.CONTROL_PATH, gate.JS_ISSUE_CONTROL_WRITE)

    def test_the_profile_release_path_waits_retries_and_names_the_dir(self) -> None:
        # ERR-165: killing the WebView2 browser tree leaves `--user-data-dir` held for a moment
        # (WinError 32), so a single rmtree both fails and hides the failure. The teardown must
        # wait, retry a bounded number of times, and report the directory BY NAME — and the report
        # must reach stdout, not only the JSON file nobody reads.
        text = SCRIPT.read_text(encoding="utf-8")
        self.assertIn("for _ in range(12):", text)
        self.assertIn("shutil.rmtree(udf)", text)
        self.assertIn('report["residue"].append(f"{udf} {last!r}")', text)
        self.assertIn('print("KEYBOARD_FOCUS_RESIDUE "', text)
        # and the retry loop is tried before anything is declared residue
        self.assertLess(text.index("for _ in range(12):"),
                        text.index('report["residue"].append(f"{udf}'))

    def test_scratch_and_evidence_both_stay_inside_the_repository(self) -> None:
        # The browser profile, the sidecar runtime root and the verdict document have separate
        # homes and neither may leave the repo: a `--user-data-dir` outside the project is the
        # spill ERR-165/ERR-140 are about, and the handoff binds evidence to
        # `.project-local/artifacts/qoder-handoff-20261007`.
        self.assertTrue(gate.OUT.is_relative_to(ROOT / ".project-local" / "runs"), str(gate.OUT))
        self.assertTrue(gate.EVIDENCE.is_relative_to(ROOT / ".project-local" / "artifacts"),
                        str(gate.EVIDENCE))
        self.assertNotEqual(gate.OUT, gate.EVIDENCE)

    def test_judge_reads_every_section_the_probe_writes(self) -> None:
        # A section measure() produces and judge() never looks at is a claim nobody decided.
        text = SCRIPT.read_text(encoding="utf-8")
        sections = ("base", "instrumentControl", "tabs", "shiftTabs", "enter", "escape", "control")
        for section in sections:
            self.assertIn(f'm["{section}"]', text, f"probe never writes {section}")
            self.assertIn(section, measurement(), f"fixture lacks {section}")
        self.assertEqual(set(measurement()), set(sections))

    def test_a_tree_without_the_built_bundle_refuses_instead_of_passing(self) -> None:
        # No browser, no desktop launch: the dist check happens before anything is started, and the
        # answer is exit 3 with a named reason — never exit 0.
        scratch = Path(tempfile.mkdtemp(prefix="keyboard-focus-selftest-",
                                        dir=ROOT / ".project-local" / "runs"))
        try:
            missing = scratch / "no-dist"
            with mock.patch.object(gate, "DIST", missing), \
                    mock.patch.object(gate, "OUT", scratch), \
                    mock.patch.object(gate, "EVIDENCE", scratch / "evidence"), \
                    mock.patch.object(sys, "argv", ["u19_keyboard_focus_cdp.py"]), \
                    mock.patch("builtins.print") as printed:
                self.assertEqual(gate.main(), 3, json.dumps(
                    [str(c.args[0]) for c in printed.call_args_list if c.args]))
            lines = [str(c.args[0]) for c in printed.call_args_list if c.args]
            self.assertTrue(any(l.startswith("KEYBOARD_FOCUS_GATE_NOT_RUN reason=no_dist_bundle")
                                for l in lines), lines[-3:])
            self.assertFalse(any(l.startswith("KEYBOARD_FOCUS_GATE_PASS") for l in lines), lines)
            # the machine-readable verdict is the LAST line, so `tail -1` is the answer
            self.assertTrue(lines[-1].startswith("KEYBOARD_FOCUS_GATE_NOT_RUN"), lines[-1])
        finally:
            # derived fixture with no unique bytes: leaving it behind is the spill ERR-140 is about
            shutil.rmtree(scratch, ignore_errors=True)
            self.assertFalse(scratch.exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
