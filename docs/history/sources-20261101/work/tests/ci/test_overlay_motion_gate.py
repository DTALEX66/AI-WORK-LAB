#!/usr/bin/env python3
"""Unit tests for the overlay motion gate — the instrument, not the browser.

The gate exists because CL-16 step 2 asked for enter/exit sampling on both sides of an overlay. Two of its
clauses are real assertions (a real pointer opens it; it leaves through its own input path) and one is a
report (whether anything animated), so the tests below prove both halves: the assertions go red on planted
faults, and the report distinguishes an animated overlay from one that appears already finished.

The `FakeCdp` cases drive `measure_overlay` itself, so the click-and-sample choreography is tested too —
a verdict-only suite would happily score a probe that never clicked anything.
"""
from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "audit" / "overlay_motion_via_cdp.py"

spec = importlib.util.spec_from_file_location("overlay_gate", str(SCRIPT))
gate = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = gate
spec.loader.exec_module(gate)


def reading(**overrides) -> dict:
    """A measurement shaped like what `measure_overlay` writes for a healthy, non-animated overlay."""
    base = {
        "name": "drawer", "selector": "aside.drawer", "mode": "real-pointer",
        "trigger": {"found": True, "label": "工作区", "tag": "BUTTON", "x": 353, "y": 119},
        "opened": True, "enterSamples": 35, "presentFrames": 35, "mountedClass": "drawer",
        # The first painted frame carries no `.open` any more, and `right` runs through intermediate values:
        # that is what the skin's declared transition looks like when it actually runs.
        "enterValues": {"right": ["-540px", "-268.4px", "0px"], "transform": ["none"], "opacity": ["1"]},
        "settledWhileOpen": True,
        "exitSamples": 154, "exitFramesPresent": 0, "unmountedAtSample": 0,
        "unmountedDuringExit": True, "closePath": "escape",
        # The exit is sampled across a window too: the drawer slides back out through intermediate values
        # before it leaves the document (measured 2026-10-29: 14 distinct `right` values after Escape).
        "exitValues": {"right": ["0px", "-268.4px", "-540px"], "transform": ["none"], "opacity": ["1"]},
        "reducedMotion": False,
        # The same overlay under `prefers-reduced-motion: reduce`: pinned, opened, and arriving at the same
        # destination with no intermediate frames. Without this half the gate would only ever prove that
        # motion exists, which is how an accessibility floor gets pressured into being deleted.
        "reduce": {
            "reducedMotion": True, "mode": "real-pointer", "opened": True,
            "enterValues": {"right": ["0px"], "transform": ["none"], "opacity": ["1"]},
            "exitValues": {"right": ["0px"], "transform": ["none"], "opacity": ["1"]},
        },
    }
    base.update(overrides)
    return base


def checks_of(result: dict) -> dict:
    return {c["check"]: c for c in result["checks"]}


class VerdictTests(unittest.TestCase):
    def test_a_measured_overlay_passes_and_is_reported_as_animated(self) -> None:
        result = gate.verdict({"drawer": reading()})
        self.assertTrue(result["passed"], json.dumps(result["checks"], ensure_ascii=False))
        self.assertIn("animated:", result["motion"]["drawer"])
        self.assertTrue(self.checks(result)["overlay_enter_transitions[drawer]"]["pass"])
        self.assertEqual("drawer", reading()["mountedClass"],
                         "the closed first frame is what gives the browser something to transition from")

    def checks(self, result: dict) -> dict:
        return {c["check"]: c for c in result["checks"]}

    def test_an_overlay_that_appears_at_its_end_state_fails_the_enter_clause(self) -> None:
        # The shape measured on 2026-10-29 before the components were fixed: mounted with the open class
        # already applied, so every sampled property held one value and the declared slide never ran.
        planted = reading(mountedClass="drawer open",
                          enterValues={"right": ["0px"], "transform": ["none"], "opacity": ["1"]})
        result = gate.verdict({"drawer": planted})
        clause = self.checks(result)["overlay_enter_transitions[drawer]"]
        self.assertFalse(clause["pass"])
        self.assertIn('"right": ["0px"]', clause["detail"],
                      "the detail must show the flat enter sequence it is refusing")
        self.assertTrue(checks_of(result)["overlay_exit_transitions[drawer]"]["pass"],
                        "a fade-out must not excuse a jump-cut entrance — the two sides are counted apart")
        self.assertFalse(result["passed"])

    def test_a_real_click_that_opens_nothing_fails_instead_of_reporting_a_pass(self) -> None:
        planted = reading(opened=False, presentFrames=0, mode="click-did-not-open",
                          enterValues={}, exitValues={}, unmountedDuringExit=False,
                          unmountedAtSample=None)
        result = gate.verdict({"drawer": planted})
        clause = checks_of(result)["overlay_opens_from_a_real_click[drawer]"]
        self.assertFalse(clause["pass"])
        self.assertIn("mode='click-did-not-open'", clause["detail"])
        self.assertFalse(result["passed"])

    def test_a_missing_trigger_is_named_not_skipped(self) -> None:
        planted = reading(trigger={"found": False, "label": "工作区", "candidates": 41},
                          opened=False, presentFrames=0, mode="trigger-not-found",
                          enterValues={}, exitValues={}, unmountedDuringExit=False,
                          unmountedAtSample=None)
        result = gate.verdict({"drawer": planted})
        self.assertFalse(checks_of(result)["overlay_trigger_rendered[drawer]"]["pass"])
        self.assertIn('"candidates": 41', checks_of(result)["overlay_trigger_rendered[drawer]"]["detail"])

    def test_an_overlay_that_never_leaves_fails_the_close_clause(self) -> None:
        planted = reading(unmountedDuringExit=False, unmountedAtSample=None, exitFramesPresent=154)
        result = gate.verdict({"drawer": planted})
        clause = checks_of(result)["overlay_closes_through_its_input_path[drawer]"]
        self.assertFalse(clause["pass"])
        self.assertIn("unmountedAtSample=None", clause["detail"])

    def test_an_overlay_that_is_deleted_without_fading_fails_the_exit_clause(self) -> None:
        # The regression this guards: a list that removes its item in the same tick it drops the open class
        # paints no exit at all — one frame shown, then gone.
        planted = reading(exitValues={"right": ["0px"], "transform": ["none"], "opacity": ["1"]})
        result = gate.verdict({"drawer": planted})
        clause = checks_of(result)["overlay_exit_transitions[drawer]"]
        self.assertFalse(clause["pass"])
        self.assertIn("exitValues", clause["detail"])
        self.assertFalse(result["passed"])

    def test_an_overlay_that_never_leaves_fails_the_exit_clause_too(self) -> None:
        planted = reading(unmountedDuringExit=False, unmountedAtSample=None)
        result = gate.verdict({"drawer": planted})
        self.assertFalse(checks_of(result)["overlay_exit_transitions[drawer]"]["pass"])
        self.assertFalse(checks_of(result)["overlay_closes_through_its_input_path[drawer]"]["pass"])

    def test_an_unpinned_preference_refuses_both_readings(self) -> None:
        # Headless Chrome answers `prefers-reduced-motion` by itself; a gate that does not pin and read it
        # back is measuring the environment. Both branches must report the preference they were told to use.
        planted = reading(reducedMotion=True, reduce=dict(reading()["reduce"], reducedMotion=False))
        result = gate.verdict({"drawer": planted})
        clause = checks_of(result)["overlay_motion_preference_pinned[drawer]"]
        self.assertFalse(clause["pass"])
        self.assertIn("normal reducedMotion=True", clause["detail"])
        self.assertIn("reduce reducedMotion=False", clause["detail"])

    def test_the_reduced_branch_must_arrive_without_frames(self) -> None:
        planted = reading(reduce=dict(reading()["reduce"],
                                      enterValues={"right": ["-540px", "-268px", "0px"],
                                                   "transform": ["none"], "opacity": ["1"]}))
        result = gate.verdict({"drawer": planted})
        self.assertTrue(checks_of(result)["overlay_motion_preference_pinned[drawer]"]["pass"])
        self.assertFalse(
            checks_of(result)["overlay_reduced_motion_arrives_without_frames[drawer]"]["pass"],
            "frames under reduce mean the accessibility floor stopped answering")

    def test_two_values_under_reduce_is_the_correct_instant_shape(self) -> None:
        # Measured 2026-10-29: the reduced drawer holds `-540px` then `0px` — the closed frame and the end
        # frame, with nothing between. A criterion of "one value" would convict the correct behaviour, so
        # the clause counts intermediate frames, not distinct values.
        planted = reading(reduce=dict(reading()["reduce"],
                                      enterValues={"right": ["-540px", "0px"], "transform": ["none"],
                                                   "opacity": ["1"]}))
        result = gate.verdict({"drawer": planted})
        self.assertTrue(checks_of(result)["overlay_reduced_motion_arrives_without_frames[drawer]"]["pass"])
        self.assertTrue(result["passed"], json.dumps([c for c in result["checks"] if not c["pass"]]))

    def test_the_reduced_branch_must_reach_the_same_destination(self) -> None:
        planted = reading(reduce=dict(reading()["reduce"],
                                      enterValues={"right": ["-540px"], "transform": ["none"],
                                                   "opacity": ["1"]}))
        result = gate.verdict({"drawer": planted})
        clause = checks_of(result)["overlay_reduced_motion_arrives_without_frames[drawer]"]
        self.assertFalse(clause["pass"])
        self.assertIn("normal end=", clause["detail"],
                      "the detail shows both ends so a reader can see where the reduced branch stopped")

    def test_an_overlay_that_moves_is_reported_as_animated_on_both_sides(self) -> None:
        # The control that proves the report is not hard-wired to "NOT_ANIMATED": a step-3 overlay that
        # slides in and out must be distinguishable from today's, without the instrument changing.
        planted = reading(enterValues={"right": ["-540px", "-270px", "0px"], "transform": ["none"],
                                                 "opacity": ["1"]},
                          exitValues={"right": ["0px", "-540px"]})
        result = gate.verdict({"drawer": planted})
        self.assertTrue(result["passed"])
        self.assertIn("animated:", result["motion"]["drawer"])
        self.assertIn("exit:right", result["motion"]["drawer"])

    def test_no_measurements_at_all_fails_instead_of_passing_on_an_empty_list(self) -> None:
        result = gate.verdict({})
        clause = checks_of(result)["gate_measured_an_overlay"]
        self.assertFalse(clause["pass"])
        self.assertIn("nothing was measured", clause["detail"])
        self.assertFalse(result["passed"], "`all([])` is a pass by accident; this gate must not ship one")


class FakeCdp:
    """Answers the gate's three expression shapes and records the input events it was sent."""

    def __init__(self, *, trigger: dict, samples: list[dict]) -> None:
        self.trigger = trigger
        self.samples = samples
        self.sent: list[tuple[str, dict]] = []
        self.reads = 0

    def evaluate(self, expr: str) -> str:
        if "querySelectorAll" in expr:
            return json.dumps(self.trigger)
        if "getComputedStyle" in expr:
            index = min(self.reads, len(self.samples) - 1)
            self.reads += 1
            return json.dumps(self.samples[index])
        return json.dumps({"ok": True})

    def send(self, method: str, params: dict | None = None) -> dict:
        self.sent.append((method, params or {}))
        return {}


class MeasureOverlayTests(unittest.TestCase):
    SPEC = gate.OVERLAYS[0]

    def _run(self, cdp) -> dict:
        with mock.patch.object(gate.time, "sleep", lambda _s: None):
            return gate.measure_overlay(cdp, self.SPEC, enter_window_s=0.05, exit_window_s=0.05)

    def test_a_click_is_sent_to_the_control_the_user_reads_and_the_frames_are_kept(self) -> None:
        present = {"present": True, "cls": "drawer open", "sel": "aside.drawer",
                   "values": {"right": "0px", "transform": "none", "opacity": "1"}}
        cdp = FakeCdp(trigger={"found": True, "label": "工作区", "x": 353, "y": 119},
                      samples=[present, present])
        out = self._run(cdp)
        kinds = [p.get("type") for m, p in cdp.sent if m == "Input.dispatchMouseEvent"]
        self.assertEqual(["mousePressed", "mouseReleased"], kinds[:2],
                         "the overlay must be opened by a press and release, not by a React setter")
        self.assertTrue(out["opened"])
        self.assertGreater(out["enterSamples"], 1, "the frames are the evidence; one read proves nothing")
        self.assertEqual("0px", out["enterValues"]["right"][0])

    def test_a_trigger_that_is_not_on_the_page_stops_before_any_click(self) -> None:
        cdp = FakeCdp(trigger={"found": False, "label": "工作区", "candidates": 12}, samples=[])
        out = self._run(cdp)
        self.assertEqual("trigger-not-found", out["mode"])
        self.assertFalse(out["opened"])
        self.assertEqual([], [m for m, _p in cdp.sent if m == "Input.dispatchMouseEvent"],
                         "no control means no click — a probe that clicks blind reports a false open")

    def test_an_escape_is_sent_and_the_exit_window_keeps_sampling_after_the_element_gone(self) -> None:
        present = {"present": True, "cls": "drawer open", "sel": "aside.drawer",
                   "values": {"right": "0px", "transform": "none", "opacity": "1"}}
        gone = {"present": False, "sel": "aside.drawer"}
        cdp = FakeCdp(trigger={"found": True, "label": "工作区", "x": 1, "y": 2},
                      samples=[present, present, gone])
        out = self._run(cdp)
        keys = [p.get("key") for m, p in cdp.sent if m == "Input.dispatchKeyEvent"]
        self.assertIn("Escape", keys, "the drawer's own contract is Esc-to-close, so the gate uses Esc")
        self.assertTrue(out["unmountedDuringExit"])
        self.assertEqual(0, out["unmountedAtSample"])
        self.assertGreater(out["exitSamples"], 1, "the exit is sampled across a window, not at one instant")


class DistinctValueTests(unittest.TestCase):
    def test_repeats_collapse_and_order_survives(self) -> None:
        samples = [{"values": {"right": "-540px"}}, {"values": {"right": "-540px"}},
                   {"values": {"right": "-270px"}}, {"values": {"right": "0px"}},
                   {"values": {"right": "0px"}}, {"present": False}]
        self.assertEqual(["-540px", "-270px", "0px"], gate.distinct_values(samples, "right"),
                         "a transition is a sequence; collapsing repeats keeps the sequence and the count")

    def test_absent_frames_contribute_nothing(self) -> None:
        self.assertEqual([], gate.distinct_values([{"present": False}], "right"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
