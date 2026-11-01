#!/usr/bin/env python3
"""Unit tests for the pressed-state motion gate — the instrument, not the browser.

This gate had no test file at all, which is how it could go red on a CI runner (PR #220's `observer` job)
for a reason that had nothing to do with the product: `CSS.forcePseudoState` starts an 80ms transition, and
one computed-style read taken right after the force can land on the transition's FIRST frame
(`matrix(1, 0, 0, 1, 0, 0)`) instead of its end state (`matrix(0.99, ...)`). The runner read the frame and
convicted a correct render; the same command on the development host settles at 0.99.

These cases pin the two things that make that reading honest now: the sampler waits for the paint to stop
moving, and a value that is neither the untouched paint nor the token's end state is reported as
UNMEASURABLE rather than as a product failure.
"""
from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "audit" / "pressed_state_motion_via_cdp.py"

spec = importlib.util.spec_from_file_location("pressed_gate", str(SCRIPT))
gate = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = gate
spec.loader.exec_module(gate)


def page_state(transform: str, selector: str = ".nav button", count: int = 1) -> str:
    """The harvest expression's own shape, so the sampler is tested against what it really reads."""
    return json.dumps({"selectors": [{"selector": selector, "count": count,
                                      "transform": transform, "transitionDuration": "0.08s"}],
                       "tokens": {"pressedScale": ".99", "motionPressed": "80ms"},
                       "reducedMotion": False})


class FakeCdp:
    """A session whose animation either ticks or does not — the two CI outcomes."""

    def __init__(self, transforms: list[str]) -> None:
        self.transforms = transforms
        self.sent: list[tuple[str, dict]] = []

    def evaluate(self, expr: str) -> str:
        index = min(self.reads, len(self.transforms) - 1)
        self.reads += 1
        return page_state(self.transforms[index])

    def send(self, method: str, params: dict | None = None) -> dict:
        self.sent.append((method, params or {}))
        return {}

    @property
    def reads(self) -> int:
        return getattr(self, "_reads", 0)

    @reads.setter
    def reads(self, value: int) -> None:
        self._reads = value


class SettledSamplerTests(unittest.TestCase):
    def test_a_transition_that_ticks_is_read_at_its_end_value(self) -> None:
        cdp = FakeCdp(["matrix(1, 0, 0, 1, 0, 0)",        # t=0 frame, must not be the answer
                       "matrix(0.995, 0, 0, 0.995, 0, 0)",
                       "matrix(0.99, 0, 0, 0.99, 0, 0)",
                       "matrix(0.99, 0, 0, 0.99, 0, 0)"])
        cdp.reads = 0
        with mock.patch.object(gate.time, "sleep", lambda _s: None):
            transform, waited = gate.settled_transform(cdp, "EXPRESSION", budget_s=5.0, poll_s=0.01)
        self.assertEqual(transform, "matrix(0.99, 0, 0, 0.99, 0, 0)",
                         "the sampler has to return the state the operator sees, not the first frame")
        self.assertGreater(cdp.reads, 3, "it should have kept reading until two samples agreed")

    def test_a_frozen_animation_reports_the_value_it_kept_seeing(self) -> None:
        # The CI failure mode: the runner never advanced the transition, so every read is the identity.
        # Two identical samples means "stable", and stability at a non-end value is the verdict's problem
        # to classify — the sampler must not spin forever.
        cdp = FakeCdp(["matrix(1, 0, 0, 1, 0, 0)"])
        cdp.reads = 0
        with mock.patch.object(gate.time, "sleep", lambda _s: None):
            transform, waited = gate.settled_transform(cdp, "EXPRESSION", budget_s=1.0, poll_s=0.06)
        self.assertEqual(transform, "matrix(1, 0, 0, 1, 0, 0)")
        self.assertLessEqual(waited, 1.0, "the wait is bounded; a hung instrument must still answer")


POINTER_OK = {
    "mode": "cdp-mousePressed", "selector": ".nav button",
    # The three reads are the values measured live over CDP on 2026-10-28 with a dispatched press on
    # `.nav button`: idle `none`, held `matrix(0.99, 0, 0, 0.99, 3, 0)` with `:active` true, released
    # back to `none` with `:active` false and the cursor moved off the control.
    "before": {"found": True, "x": 120, "y": 60, "active": False, "transform": "none"},
    "during": {"found": True, "active": True, "transform": "matrix(0.99, 0, 0, 0.99, 3, 0)"},
    "after": {"found": True, "active": False, "transform": "none"},
    "pressedFirstSelector": "matrix(0.99, 0, 0, 0.99, 3, 0)", "pressedWaitedS": 0.06,
}


KEY_OK = {
    "selector": ".nav button", "tabs": 1, "reached": True,
    # Measured live on 2026-10-28 with dispatched Tab: the control's outline moves from its own unfocused
    # read to the focus ring, and `:focus-visible` goes true on the stop that focus lands on.
    "before": {"found": True, "isActive": False, "activeTag": "BODY",
               "focusVisible": False, "outline": "3px rgb(238, 246, 252)", "transform": "none"},
    "focused": {"found": True, "isActive": True, "activeTag": "BUTTON",
                "focusVisible": True, "outline": "2px rgb(42, 145, 255)", "transform": "none"},
}


def make_readings(pressed_transform: str, pointer: object = "default", key: object = "default") -> dict:
    """One console surface, its forced-pseudo-class pair of reads, and the pointer and keyboard branches.

    `pointer=None` deliberately leaves the key out: that is the state a run reaches when the press never
    happened, and the verdict has to fail it by name instead of scoring one fewer check.
    """
    row = {"selector": ".nav button", "count": 1, "transitionDuration": "0.08s",
           "transform": pressed_transform, "tag": "button", "label": "Projects"}
    idle = {"selectors": [dict(row, transform="none")],
            "tokens": {"pressedScale": ".99", "motionPressed": "80ms"}, "reducedMotion": False}
    pressed = {"selectors": [dict(row, transform=pressed_transform)],
               "tokens": idle["tokens"], "reducedMotion": False}
    surface: dict = {"required": ".nav button", "idle": idle, "pressed": pressed}
    if pointer != "default" and pointer is not None:
        surface["pointer"] = dict(pointer)  # type: ignore[arg-type]
    elif pointer == "default":
        surface["pointer"] = dict(POINTER_OK)
    if key != "default" and key is not None:
        surface["key"] = dict(key)  # type: ignore[arg-type]
    elif key == "default":
        surface["key"] = dict(KEY_OK)
    return {"console": surface}


def check_of(result: dict, name: str) -> dict:
    return next(c for c in result["checks"] if c["check"] == name)


class VerdictClassificationTests(unittest.TestCase):
    """A frame is not a state: the gate must call it unmeasurable instead of convicting the product."""

    def _check(self, result: dict, name: str) -> dict:
        return check_of(result, name)

    def test_a_first_frame_read_is_unmeasurable_not_a_product_failure(self) -> None:
        result = gate.verdict(make_readings("matrix(1, 0, 0, 1, 0, 0)"))
        self.assertEqual(result["unmeasurable"], ["console/.nav button"])
        self.assertFalse(self._check(result, "pressed-paint-read-was-settled[console:.nav button]")["pass"])
        detail = self._check(result, "active-transform-matches-token[console:.nav button]")["detail"]
        self.assertIn("settledRead=False", detail,
                      "the paint check must say the read was not a settled state, so a reader does not "
                      "conclude the stylesheet lost its pressed rule")

    def test_the_end_value_is_settled_and_passes(self) -> None:
        result = gate.verdict(make_readings("matrix(0.99, 0, 0, 0.99, 0, 0)"))
        self.assertEqual(result["unmeasurable"], [])
        self.assertTrue(self._check(result, "pressed-paint-read-was-settled[console:.nav button]")["pass"])
        self.assertTrue(self._check(result, "active-transform-matches-token[console:.nav button]")["pass"])

    def test_no_painted_change_is_still_a_real_failure(self) -> None:
        # If the rule stopped reaching the element altogether, the read is stable AT the idle value: that
        # is settled, and the paint-change check is the one that has to convict it.
        result = gate.verdict(make_readings("none"))
        self.assertEqual(result["unmeasurable"], [], "an unchanged paint is measurable, just wrong")
        self.assertFalse(self._check(result, "pressed-state-changes-the-paint[console:.nav button]")["pass"])


class RealPointerBranchTests(unittest.TestCase):
    """`CSS.forcePseudoState` proves a rule exists; only a dispatched press proves a hand reaches it.

    These clauses are why the gate now sends `Input.dispatchMouseEvent`: before it, a pressed style wired
    to a selector the input path never hits (a wrapper that swallows the hit, a `pointer-events:none`
    layer, a control that only paints on `:focus-visible`) would have stayed green forever, because the
    force bypasses every one of those. The live reading on 2026-10-28 — idle `none`, held `:active` true at
    `matrix(0.99, …)`, released back — is what a passing branch has to look like.
    """

    def _check(self, result: dict, name: str) -> dict:
        return check_of(result, name)

    def test_a_real_press_passes_every_pointer_clause(self) -> None:
        result = gate.verdict(make_readings("matrix(0.99, 0, 0, 0.99, 3, 0)"))
        for name in ("real-press-probe-ran[console]",
                     "real-press-read-was-settled[console]",
                     "real-press-lights-the-active-pseudo-class[console]",
                     "real-press-transform-matches-token[console]",
                     "real-release-returns-the-paint-to-idle[console]",
                     "keyboard-tab-reached-the-control[console]",
                     "keyboard-focus-lights-the-visible-ring[console]"):
            self.assertTrue(self._check(result, name)["pass"], self._check(result, name))

    def test_a_tab_that_never_lands_on_the_control_fails_by_name(self) -> None:
        planted = dict(KEY_OK, reached=False, tabs=12,
                       focused={"found": True, "isActive": False, "activeTag": "DIV",
                                "focusVisible": False, "outline": "3px rgb(238, 246, 252)"})
        result = gate.verdict(make_readings("matrix(0.99, 0, 0, 0.99, 3, 0)", key=planted))
        self.assertFalse(self._check(result, "keyboard-tab-reached-the-control[console]")["pass"])
        self.assertFalse(self._check(result, "keyboard-focus-lights-the-visible-ring[console]")["pass"])

    def test_a_page_arriving_with_the_control_focused_refuses_by_naming_the_cause(self) -> None:
        # Found the hard way: the press branch focuses the control it presses, so a keyboard branch that
        # ran afterwards would Tab AWAY from the target and report an unreachable control — an instrument
        # order defect wearing a product failure's clothes. The probe now refuses and says why.
        planted = dict(KEY_OK, reached=False, tabs=0, note="already-focused-before-the-first-tab",
                       before=dict(KEY_OK["before"], isActive=True),
                       focused=dict(KEY_OK["before"], isActive=True))
        result = gate.verdict(make_readings("matrix(0.99, 0, 0, 0.99, 3, 0)", key=planted))
        clause = self._check(result, "keyboard-tab-reached-the-control[console]")
        self.assertFalse(clause["pass"])
        self.assertIn("note='already-focused-before-the-first-tab'", clause["detail"],
                      "the detail must name the ordering, so a reader does not go looking for a missing "
                      "focus ring in the product")

    def test_a_focus_that_changes_nothing_painted_is_a_real_failure(self) -> None:
        # Reachable, focused, `:focus-visible` true — but the same outline as when unfocused: a keyboard
        # user is told nothing. This is the clause that keeps `:focus-visible` from being claimed by a rule
        # that the shell never ships, the same way the press clause keeps `:active` from being assumed.
        planted = dict(KEY_OK, focused=dict(KEY_OK["focused"], outline=KEY_OK["before"]["outline"]))
        result = gate.verdict(make_readings("matrix(0.99, 0, 0, 0.99, 3, 0)", key=planted))
        failed = self._check(result, "keyboard-focus-lights-the-visible-ring[console]")
        self.assertTrue(self._check(result, "keyboard-tab-reached-the-control[console]")["pass"])
        self.assertFalse(failed["pass"])
        self.assertIn("outline '3px rgb(238, 246, 252)' -> '3px rgb(238, 246, 252)'", failed["detail"])

    def test_a_press_that_never_lights_active_fails_instead_of_being_skipped(self) -> None:
        planted = dict(POINTER_OK,
                       during={"found": True, "active": False, "transform": "none"},
                       after={"found": True, "active": False, "transform": "none"})
        result = gate.verdict(make_readings("matrix(0.99, 0, 0, 0.99, 3, 0)", pointer=planted))
        self.assertFalse(self._check(result, "real-press-lights-the-active-pseudo-class[console]")["pass"])
        self.assertIn("during :active=False",
                      self._check(result, "real-press-lights-the-active-pseudo-class[console]")["detail"])
        self.assertFalse(self._check(result, "real-press-transform-matches-token[console]")["pass"])
        self.assertFalse(result["passed"],
                         "a pointer that reaches no feedback is a product failure, not a thinner report")

    def test_a_missing_pointer_branch_is_refused_by_name(self) -> None:
        result = gate.verdict(make_readings("matrix(0.99, 0, 0, 0.99, 3, 0)", pointer=None))
        ran = self._check(result, "real-press-probe-ran[console]")
        self.assertFalse(ran["pass"])
        self.assertIn("nothing pressed the control", ran["detail"])
        self.assertFalse(result["passed"])

    def test_a_press_sampled_inside_the_transition_is_unmeasurable(self) -> None:
        planted = dict(POINTER_OK,
                       during={"found": True, "active": True,
                               "transform": "matrix(0.997, 0, 0, 0.997, 2, 0)"})
        result = gate.verdict(make_readings("matrix(0.99, 0, 0, 0.99, 3, 0)", pointer=planted))
        self.assertEqual(result["unmeasurable"], ["console/pointer"])
        self.assertFalse(self._check(result, "real-press-read-was-settled[console]")["pass"])
        self.assertIn("settledRead=False",
                      self._check(result, "real-press-transform-matches-token[console]")["detail"],
                      "the paint line must say the read was a frame, so a reader does not conclude the "
                      "stylesheet lost the rule")

    def test_a_release_that_leaves_the_paint_moved_is_a_failure(self) -> None:
        # The cursor is moved off the control before the release read precisely because a control still
        # under it paints its hover lift (measured: `matrix(1, 0, 0, 1, 3, 0)`). Comparing that against the
        # untouched idle value would convict the product for a state the operator is still in; comparing
        # against itself is what catches a press that never let go.
        planted = dict(POINTER_OK,
                       after={"found": True, "active": True,
                              "transform": "matrix(0.99, 0, 0, 0.99, 3, 0)"})
        result = gate.verdict(make_readings("matrix(0.99, 0, 0, 0.99, 3, 0)", pointer=planted))
        failed = self._check(result, "real-release-returns-the-paint-to-idle[console]")
        self.assertFalse(failed["pass"])
        self.assertIn("-> released='matrix(0.99", failed["detail"])


class TokenExpectationTests(unittest.TestCase):
    def test_the_expected_scale_comes_from_the_token_not_a_literal(self) -> None:
        scale, duration, problems = gate.token_expectations(
            {"pressedScale": ".99", "motionPressed": "80ms"})
        self.assertEqual((scale, duration), (0.99, 0.08))
        self.assertEqual(problems, [])

    def test_an_unparseable_token_is_named_instead_of_defaulting(self) -> None:
        scale, _duration, problems = gate.token_expectations({"pressedScale": "auto", "motionPressed": "80ms"})
        self.assertIsNone(scale)
        self.assertTrue(any("pressedScale" in p for p in problems), problems)

    def test_a_missing_token_is_not_silently_zero(self) -> None:
        scale, duration, problems = gate.token_expectations({})
        self.assertIsNone(scale)
        self.assertIsNone(duration)
        self.assertEqual(len(problems), 2, "both tokens must be reported missing, not assumed")


if __name__ == "__main__":
    unittest.main(verbosity=2)
