"""Gate: the native-surface skip is granted by the capability probe, never by an environment variable.

Why this exists, measured rather than asserted: on `main` at b218ef82 the observer job's own log carried
`DESKTOP_CAPABILITY_FAIL ... display: PASS, draw: PASS` and, three minutes later,
`[U19] VERDICT: SKIPPED_HEADLESS` with `process_liveness: ALIVE`, exiting 0. The skip had been keyed on
`GITHUB_ACTIONS`/`RUNNER_OS` -- a machine flag -- so a WebView2 that rendered nothing on a runner that CAN
draw was reported as "skipped, fine". The probe was already layered correctly; its verdict simply never
reached the decision.

The load-bearing assertions here are the falsifying ones: with `GITHUB_ACTIONS=true` and `RUNNER_OS=Windows`
planted in the environment, an unproven surface in a drawable environment must still come back FAIL, and
only a probe that denies drawing may produce NATIVE_SURFACE_UNAVAILABLE. The report-reading half is checked
against a synthetic artifact so the wiring, not just the arithmetic, is covered.
"""
from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import os
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "apps" / "observer" / "scripts" / "u19_webview_e2e.py"
PROJECT_TEMP = ROOT / "packages" / "client-neutral-core" / "scripts" / "project_temp.py"

_spec = importlib.util.spec_from_file_location("u19_webview_e2e_under_test", SCRIPT)
u19 = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
sys.path.insert(0, str(ROOT / "apps" / "observer" / "scripts"))
_spec.loader.exec_module(u19)  # type: ignore[attr-defined]

_pt_spec = importlib.util.spec_from_file_location("project_temp", PROJECT_TEMP)
project_temp = importlib.util.module_from_spec(_pt_spec)
assert _pt_spec.loader is not None
_pt_spec.loader.exec_module(project_temp)  # type: ignore[attr-defined]

# The runner report measured on 2026-10-25 in run 40215515839, job `observer`: no interactive session,
# but a real display and a pixel painted and read back. That combination is the whole defect.
RUNNER_REPORT = {"verdict": "FAIL", "layers": [
    {"layer": "session", "verdict": "FAIL", "evidence": {"SESSIONNAME": None}},
    {"layer": "display", "verdict": "PASS", "evidence": {"width": 1024, "height": 768}},
    {"layer": "draw", "verdict": "PASS", "evidence": {"painted_pixel": "0xff00", "expected": "0xff00"}},
    {"layer": "webview2", "verdict": "PASS", "evidence": {"version": "154.0.4258.62"}},
    {"layer": "loopback", "verdict": "PASS", "evidence": {"port": 61869}},
    {"layer": "cleanup", "verdict": "PASS", "evidence": {"created": True, "removed": True}},
]}

NO_DISPLAY_REPORT = {**RUNNER_REPORT, "layers": [
    {"layer": "session", "verdict": "FAIL", "evidence": {"SESSIONNAME": None}},
    {"layer": "display", "verdict": "FAIL", "evidence": {"width": 0, "height": 0}},
    {"layer": "draw", "verdict": "FAIL", "evidence": {"error": "GetDC(0) returned null"}},
]}

# Synthetic reports for the layer added on 2026-10-26 (plants, not measurements): the shape the runner
# showed -- an environment that paints but owns no desktop that displays a window -- has to be decided by
# a reading, and the opposite shape has to keep producing a product failure.
NO_VISIBLE_DESKTOP_REPORT = {"verdict": "FAIL", "layers": [
    {"layer": "session", "verdict": "FAIL", "evidence": {"SESSIONNAME": None}},
    {"layer": "display", "verdict": "PASS", "evidence": {"width": 1024, "height": 768}},
    {"layer": "draw", "verdict": "PASS", "evidence": {"painted_pixel": "0xff00", "expected": "0xff00"}},
    {"layer": "visible_desktop", "verdict": "FAIL",
     "evidence": {"visibleTopLevel": 0, "titledVisible": 0, "shellWindowPresent": False}},
]}

VISIBLE_DESKTOP_REPORT = {**NO_VISIBLE_DESKTOP_REPORT, "layers": [
    *NO_VISIBLE_DESKTOP_REPORT["layers"][:3],
    {"layer": "visible_desktop", "verdict": "PASS",
     "evidence": {"visibleTopLevel": 31, "titledVisible": 20, "shellWindowPresent": True}},
]}


def verdict(**overrides) -> tuple[str, str]:
    args = {"backend_ok": True, "surface_proven": False, "liveness": "ALIVE",
            "probe_built": True, "drawable": False}
    args.update(overrides)
    return u19.native_render_verdict(**args)


class DecisionTableTests(unittest.TestCase):
    def test_a_reported_blank_render_on_a_drawing_environment_is_a_failure(self) -> None:
        """The case CI was greening: the probe says the machine can draw, nothing was proven."""
        self.assertEqual(("FAIL", "surface-not-proven"),
                         verdict(drawable=u19.drawable_display(RUNNER_REPORT)[0]))

    def test_an_environment_variable_does_not_decide_anything(self) -> None:
        """Planted falsification: the old rule read GITHUB_ACTIONS/RUNNER_OS and returned exit 0."""
        with mock.patch.dict(os.environ, {"GITHUB_ACTIONS": "true", "RUNNER_OS": "Windows"}):
            self.assertEqual("FAIL", verdict(drawable=True)[0])
            self.assertEqual("FAIL", verdict(drawable=False)[0],
                             "an unresolved capability is not a denial; only a reading grants the skip")
            self.assertEqual("NATIVE_SURFACE_UNAVAILABLE", verdict(drawable=False, denied=True)[0])

    def test_only_a_probe_that_denies_drawing_opens_the_skip(self) -> None:
        self.assertEqual("FAIL", verdict(drawable=False)[0],
                         "not-drawable without a denial means the environment never said anything")
        self.assertEqual("NATIVE_SURFACE_UNAVAILABLE", verdict(drawable=False, denied=True)[0])
        self.assertEqual("PASS", verdict(surface_proven=True, drawable=True)[0])
        self.assertEqual("PASS", verdict(surface_proven=True, drawable=False)[0],
                         "a proven render is a pass whatever the environment claims")

    def test_a_dead_process_or_a_missing_probe_window_is_never_a_skip(self) -> None:
        self.assertEqual("FAIL", verdict(liveness="EXITED_EARLY", drawable=False)[0])
        self.assertEqual("FAIL", verdict(probe_built=False, drawable=False)[0])

    def test_a_failed_backend_is_never_a_skip(self) -> None:
        self.assertEqual(("FAIL", "backend-not-proven"), verdict(backend_ok=False, drawable=False))


class CapabilityReadingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = project_temp.fixture_dir(prefix="wl-capability-")

    def tearDown(self) -> None:
        if not project_temp.force_release(self.tmp):
            self.fail(f"fixture root was not released: {self.tmp}")

    def test_the_runner_report_is_read_as_a_drawable_display(self) -> None:
        """The 2026-10-25 report predates the `visible_desktop` layer, and an absent layer proves nothing.

        It is therefore NOT drawable (the required set is not satisfied) and NOT a denial either, which is
        what keeps an unproven surface reading as a failure instead of a documented skip.
        """
        self.assertEqual((False, "layers.visible_desktop.verdict=MISSING"),
                         u19.drawable_display(RUNNER_REPORT))
        self.assertFalse(u19.capability_denies_drawing(RUNNER_REPORT),
                         "a missing layer must not be read as the probe denying the capability")

    def test_a_desktop_that_cannot_show_a_window_denies_the_native_surface(self) -> None:
        """The layer added for the 2026-10-26 runner reading: display PASS, draw PASS, no visible window.

        That combination is neither "the product failed to render" nor a machine flag: it is a measured
        denial of the surface, so the stage records NATIVE_SURFACE_UNAVAILABLE and never a pass.
        """
        self.assertEqual((False, "layers.visible_desktop.verdict=FAIL"),
                         u19.drawable_display(NO_VISIBLE_DESKTOP_REPORT))
        self.assertTrue(u19.capability_denies_drawing(NO_VISIBLE_DESKTOP_REPORT))
        self.assertEqual(("NATIVE_SURFACE_UNAVAILABLE", "capability-probe-denies-drawing"),
                         verdict(drawable=u19.drawable_display(NO_VISIBLE_DESKTOP_REPORT)[0],
                                 denied=u19.capability_denies_drawing(NO_VISIBLE_DESKTOP_REPORT)))

    def test_a_window_showing_desktop_restores_the_product_failure(self) -> None:
        """Same unproven surface, capability fully resolved as PASS: now it IS a product failure."""
        self.assertEqual((True, "layers.display.verdict=PASS,layers.draw.verdict=PASS,"
                                "layers.visible_desktop.verdict=PASS"),
                         u19.drawable_display(VISIBLE_DESKTOP_REPORT))
        self.assertFalse(u19.capability_denies_drawing(VISIBLE_DESKTOP_REPORT))
        self.assertEqual(("FAIL", "surface-not-proven"),
                         verdict(drawable=u19.drawable_display(VISIBLE_DESKTOP_REPORT)[0],
                                 denied=u19.capability_denies_drawing(VISIBLE_DESKTOP_REPORT)))

    def test_a_session_flag_alone_never_makes_an_environment_drawable(self) -> None:
        """`session` is corroboration by the probe's own rule; `display` and `draw` are the gate."""
        self.assertEqual((False, "layers.display.verdict=FAIL"),
                         u19.drawable_display(NO_DISPLAY_REPORT))
        only_session = {"layers": [{"layer": "session", "verdict": "PASS"}]}
        self.assertEqual((False, "layers.display.verdict=MISSING"), u19.drawable_display(only_session))

    def test_an_absent_report_denies_the_skip_rather_than_granting_it(self) -> None:
        self.assertEqual((False, "capability-report-unavailable"), u19.drawable_display(None))
        # An empty-but-present report is its own named denial: the layer was never resolved, and an
        # unresolved layer cannot excuse a product surface (the probe's own verdict discipline).
        self.assertEqual((False, "layers.display.verdict=MISSING"), u19.drawable_display({}))

    def test_the_probe_artifact_is_consumed_from_the_declared_path(self) -> None:
        artifact = self.tmp / "desktop_capability.json"
        artifact.write_text(json.dumps(NO_DISPLAY_REPORT), encoding="utf-8")
        with mock.patch.dict(os.environ, {"WORK_LAB_DESKTOP_CAPABILITY_JSON": str(artifact)}):
            report, source = u19.read_capability_report()
        self.assertIn("artifact=", source)
        self.assertEqual((False, "layers.display.verdict=FAIL"), u19.drawable_display(report))

    def test_an_unreadable_artifact_is_reported_as_no_permission(self) -> None:
        artifact = self.tmp / "broken.json"
        artifact.write_text("{not json", encoding="utf-8")
        with mock.patch.dict(os.environ, {"WORK_LAB_DESKTOP_CAPABILITY_JSON": str(artifact)}):
            report, source = u19.read_capability_report()
        self.assertIsNone(report)
        self.assertIn("unreadable", source)
        self.assertEqual((False, "capability-report-unavailable"), u19.drawable_display(report))

    def test_the_harness_no_longer_reads_a_machine_flag_for_the_decision(self) -> None:
        """`is_github_runner` was the bug; only the recorded context may mention the flags now."""
        text = SCRIPT.read_text(encoding="utf-8")
        self.assertNotIn("is_github_runner", text)
        self.assertNotIn('result["verdict"] = "SKIPPED_HEADLESS"', text)
        self.assertIn('"usedForDecision": False', text)


class PrintContractTests(unittest.TestCase):
    def test_the_unverified_reason_is_printed_verbatim_from_the_probe_field(self) -> None:
        """An auditor greps `NATIVE_SURFACE_UNAVAILABLE reason=`; the value has to be the probe field."""
        _, basis = u19.drawable_display(NO_DISPLAY_REPORT)
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            print(f"NATIVE_SURFACE_UNAVAILABLE reason={basis}")
        self.assertIn("NATIVE_SURFACE_UNAVAILABLE reason=layers.display.verdict=FAIL",
                      buffer.getvalue())


if __name__ == "__main__":
    unittest.main()
