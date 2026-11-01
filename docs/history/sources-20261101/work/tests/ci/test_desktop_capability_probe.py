"""W04 (2026-10-17): the desktop capability probe, and the layer arithmetic that must never add up to PASS.

The recorded failure this guards against is not a crash: it is a *green tick for a check that did not run*
(`SKIPPED_HEADLESS` exiting 0). So the interesting assertions here are the arithmetic ones -- a layer that is
NOT_AVAILABLE, NOT_RUN or NOT_APPLICABLE must leave the summary INCOMPLETE, never PASS -- plus the evidence
requirements that stop a layer from reporting a boolean where a measurement is the point.
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "audit" / "desktop_capability_probe.py"


def load_module():
    spec = importlib.util.spec_from_file_location("desktop_capability_probe", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class LayerArithmeticTests(unittest.TestCase):
    def _run_with(self, module, overrides: dict, deadline: float = 90.0):
        original = dict(module.PROBES)
        try:
            module.PROBES.update(overrides)
            return module.run(deadline)
        finally:
            module.PROBES.clear()
            module.PROBES.update(original)

    def test_a_pass_requires_every_required_layer(self) -> None:
        module = load_module()
        report = self._run_with(module, {layer: (lambda: ("PASS", {"probe": "stub"}))
                                         for layer in module.LAYERS})
        self.assertEqual("PASS", report["verdict"], report)

    def test_not_available_never_adds_up_to_a_pass(self) -> None:
        """The whole point: an unavailable layer is information, and information is not a pass."""
        module = load_module()
        report = self._run_with(module, {
            **{layer: (lambda: ("PASS", {"probe": "stub"})) for layer in module.LAYERS},
            "draw": lambda: ("NOT_AVAILABLE", {"reason": "no graphics path in this session"}),
        })
        self.assertEqual("INCOMPLETE", report["verdict"], report)
        self.assertIn("draw", report["unresolved"])

    def test_a_failure_names_the_layer(self) -> None:
        module = load_module()
        report = self._run_with(module, {
            **{layer: (lambda: ("PASS", {"probe": "stub"})) for layer in module.LAYERS},
            "webview2": lambda: ("FAIL", {"reason": "no runtime registered"}),
        })
        self.assertEqual("FAIL", report["verdict"])
        self.assertEqual(["webview2"], report["failing"])

    def test_an_expired_deadline_leaves_layers_not_run_and_the_verdict_incomplete(self) -> None:
        module = load_module()
        report = module.run(deadline_seconds=0.0)
        self.assertTrue(all(layer["verdict"] == "NOT_RUN" for layer in report["layers"]), report)
        self.assertEqual("INCOMPLETE", report["verdict"])
        self.assertTrue(all("deadline" in layer["evidence"]["reason"] for layer in report["layers"]))

    def test_off_windows_the_verdict_is_incomplete_not_pass(self) -> None:
        """A Linux runner must not be able to report a desktop capability pass by simply not applying."""
        module = load_module()
        original = module._windows
        try:
            module._windows = lambda: False
            report = module.run()
        finally:
            module._windows = original
        self.assertNotEqual("PASS", report["verdict"], report)

    def test_the_draw_layer_reports_a_measurement_not_a_boolean(self) -> None:
        """A capability flag can be wrong; a read-back pixel cannot (it is either the value we painted or it
        is not). This is the layer the plan asks for by name, so its evidence shape is pinned."""
        module = load_module()
        verdict, evidence = module.probe_draw()
        if verdict == "NOT_APPLICABLE":
            self.skipTest("not a Windows host")
        self.assertEqual("PASS", verdict, evidence)
        self.assertEqual(hex(0x00FF00), evidence["painted_pixel"])
        self.assertEqual(hex(0x00FF00), evidence["expected"])

    def test_the_cli_writes_the_report_and_exits_by_verdict(self) -> None:
        proc = subprocess.run([sys.executable, str(SCRIPT), "--json-out",
                               str(Path(".project-local/runs/tmp/desktop-capability-test.json"))],
                              cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace")
        out = proc.stdout + proc.stderr
        self.assertIn("DESKTOP_CAPABILITY_", out, out)
        # 0 = PASS, 1 = FAIL, 3 = INCOMPLETE. The CLI must not collapse INCOMPLETE into 0.
        self.assertIn(proc.returncode, (0, 1, 3), out)
        if proc.returncode == 3:
            self.assertIn("INCOMPLETE", out)
        else:
            self.assertNotIn("INCOMPLETE", out)


if __name__ == "__main__":
    unittest.main(verbosity=2)
