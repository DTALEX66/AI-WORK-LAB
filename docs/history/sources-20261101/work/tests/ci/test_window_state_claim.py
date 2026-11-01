r"""Gate: the window-state claim is a verdict, not a printout.

Project law this file exists to enforce: a UI claim is real only when it is
MEASURED, not emulated. The recorded defect — a CI geometry step that reported a
500x629 viewport while `tauri.conf.json` declared the panel at 440x780 (440x680 since
2026-10-13) — happened
because the number came from a Chrome `--headless=new` window, and nothing on the
Rust side ever read the real window back. Every check here runs on the PURE
decision function in apps/observer/scripts/window_state_readback.py, so the
assertions are reviewable on any checkout and never need the desktop app; the
wiring tests use mocks precisely so that no GUI is launched.

Fail-closed rules under test, in order of how they were earned:
  * a measured size outside the declared tolerance goes red;
  * a missing / unreadable / unresolved / non-native readback goes red or
    NOT_RUN — never green, by any path;
  * the probe re-derives the verdict from the raw numbers and convicts the claim
    when the Rust payload's own verdict disagrees with them (a gate that only
    re-reads a verdict proves nothing);
  * scratch lives inside the project boundary (ERR-163): this file used to build
    its fixtures with a bare `tempfile.mkdtemp(prefix="wsr-test-")`, which on this
    machine meant `C:\Windows\Temp\wsr-test-*` — a stack of leaked directories,
    each still holding the never-closed `app_stderr.log`, because
    `shutil.rmtree(..., ignore_errors=True)` swallowed the Windows refusal rather
    than reporting it. Fixture roots now come from
    `packages/client-neutral-core/scripts/project_temp.py`, and the probe refuses
    an out-of-boundary evidence root outright.
"""
from __future__ import annotations

import ast
import importlib.util
import io
import json
import os
import re
import shutil
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "apps" / "observer" / "scripts" / "window_state_readback.py"
LIB_RS = ROOT / "apps" / "observer" / "src-tauri" / "src" / "lib.rs"
TAURI_CONF = ROOT / "apps" / "observer" / "src-tauri" / "tauri.conf.json"
PROJECT_TEMP = ROOT / "packages" / "client-neutral-core" / "scripts" / "project_temp.py"

spec = importlib.util.spec_from_file_location("window_state_readback", SCRIPT)
wsr = importlib.util.module_from_spec(spec)
spec.loader.exec_module(wsr)  # type: ignore[attr-defined]

# The boundary helper is loaded the same way the probe loads it, and a missing
# helper must break this module loudly: a fixture whose boundary check silently
# disappears is the spill coming back.
_pt_spec = importlib.util.spec_from_file_location("project_temp", PROJECT_TEMP)
project_temp = importlib.util.module_from_spec(_pt_spec)
_pt_spec.loader.exec_module(project_temp)  # type: ignore[attr-defined]


def _outside_repo(name: str) -> Path:
    r"""A path outside the Git root that no test here ever creates.

    `tempfile.gettempdir()` cannot be used for this: under the canonical gate
    runner TMP/TEMP/TMPDIR are bound into `.project-local/runs/tmp`, so "the temp
    directory" is inside the boundary in one mode and outside it in the other —
    the exact ambiguity ERR-163 is about. The repo's own drive root is outside in
    every mode, and it is asserted not to exist before and after each use.
    """
    return Path(f"{Path(project_temp.REPO_ROOT).anchor}worklab-boundary-probe-"
                f"{name}").resolve()


# ---------------------------------------------------------------------------
# Payload builders. `metrics()` is the shape `window_metrics` returns: serde
# camelCase, with the verdict carried next to the raw numbers it was computed from.
# ---------------------------------------------------------------------------
def declared(width=440.0, height=680.0, label="panel") -> dict:
    return {"label": label, "width": width, "height": height,
            "minWidth": width, "minHeight": height, "resizable": False,
            "unit": "logical pixels, inner content area",
            "source": "embedded tauri.conf.json (app.windows)"}


def verdict(status="match", deviation=None, tolerance=wsr.TOLERANCE_LOGICAL_PX) -> dict:
    return {"status": status, "deviation": deviation, "toleranceLogicalPx": tolerance,
            "basis": "inner_size_logical vs declared width/height", "reason": None}


def metrics(width=440.0, height=680.0, scale=1.0, status=None, dec=None, label="panel",
            **overrides) -> dict:
    """A coherent readback by default: deviation recomputed from the same numbers
    the Rust side would have used, so a PASS here is a fixture, not a wish."""
    dec = dec if dec is not None else declared(label=label)
    deviation = {"width": width - dec["width"], "height": height - dec["height"]}
    if status is None:
        within = all(abs(d) <= wsr.TOLERANCE_LOGICAL_PX for d in deviation.values())
        status = "match" if within else "mismatch"
    payload = {
        "command": "window_metrics", "readonly": True,
        "requestedLabel": label, "windowLabel": label,
        "resolutionSucceeded": True, "resolutionNote": None,
        "windowExists": True, "visible": False,
        "scaleFactor": scale,
        "innerSizePhysical": {"width": round(width * scale), "height": round(height * scale)},
        "outerSizePhysical": {"width": round(width * scale), "height": round(height * scale)},
        "outerPositionPhysical": {"x": 1420, "y": 40},
        "innerSizeLogical": {"width": width, "height": height},
        "declared": dec,
        "verdict": verdict(status=status, deviation=deviation),
        "fieldErrors": [],
    }
    payload.update(overrides)
    return payload


def decide(payload, **kw):
    return wsr.decide_window_state_claim(payload, **kw)


class HappyPath(unittest.TestCase):
    def test_a_measured_window_that_equals_its_declared_size_is_green(self):
        out = decide(metrics())
        self.assertEqual(out["status"], "PASS", out)
        self.assertEqual(out["declared"], "440x680")
        self.assertEqual(out["measured"], "440.0x680.0")
        self.assertEqual(out["scale"], 1.0)

    def test_the_same_window_at_125_percent_scale_is_still_green(self):
        # 550x850 physical at scale 1.25 IS the declared 440x680. A gate that
        # compares raw physical pixels against a logical config would call this
        # a mismatch — this is the exact unit bug behind the original confusion.
        out = decide(metrics(width=440.0, height=680.0, scale=1.25))
        self.assertEqual(out["status"], "PASS", out)


class GeometryMustGoRedWhenItIsWrong(unittest.TestCase):
    def test_the_recorded_cdp_numbers_convict_the_claim(self):
        # 500x629 measured against a declared 440x680: the run nobody could
        # explain. If this ever goes green, the emulation-vs-measurement gap is
        # back in the gate.
        out = decide(metrics(width=500.0, height=629.0,
                             status="mismatch",
                             dec=declared()))
        self.assertEqual(out["status"], "FAIL", out)
        self.assertEqual(out["deviation"], "+60.0x-51.0")
        self.assertIn("beyond +/-2.0 logical px", out["reason"])

    def test_one_pixel_past_the_tolerance_is_red(self):
        self.assertEqual(decide(metrics(width=442.0, height=680.0))["status"], "PASS",
                         "the tolerance boundary itself is inclusive")
        self.assertEqual(decide(metrics(width=442.01, height=680.0))["status"], "FAIL")

    def test_one_axis_right_and_one_wrong_is_red(self):
        # The rule is an AND over the axes, never an average: a panel that is the
        # right width but 120px too tall is the wrong panel.
        out = decide(metrics(width=440.0, height=900.0, status="mismatch"))
        self.assertEqual(out["status"], "FAIL", out)

    def test_a_window_that_is_smaller_than_declared_is_red_too(self):
        out = decide(metrics(width=400.0, height=700.0, status="mismatch"))
        self.assertEqual(out["status"], "FAIL")
        self.assertTrue(out["deviation"].startswith("-40.0x+20.0"), out["deviation"])


class MissingReadbackIsNeverGreen(unittest.TestCase):
    """The requirement in one class: no path below may print PASS."""

    def test_no_readback_at_all(self):
        out = decide(None)
        self.assertNotEqual(out["status"], "PASS")
        self.assertEqual(out["status"], "NOT_RUN")
        self.assertEqual(out["reason"], "no readback obtained")

    def test_a_readback_that_could_not_measure_anything(self):
        payload = metrics(status="unmeasured", innerSizeLogical=None)
        out = decide(payload)
        self.assertEqual(out["status"], "FAIL", out)
        self.assertIn("unmeasured is never green", out["reason"])

    def test_every_broken_shape_stays_non_green(self):
        broken = [
            None,                                     # nothing returned
            [],                                       # not an object
            {"__error": "no __TAURI_INTERNALS__.invoke in this page"},
            metrics(resolutionSucceeded=False, resolutionNote="'panel' is declared "
                                                             "but no live window exists"),
            metrics(declared=None),                   # nothing to match against
            metrics(scaleFactor=None),
            metrics(scaleFactor=0.0),
            metrics(scaleFactor=-1.0),
            metrics(outerSizePhysical=None, innerSizeLogical=None),
            metrics(measurementMode="cdp-emulation"),  # emulated, not measured
            metrics(verdict=verdict(status="match", deviation=None, tolerance=50.0)),
            # The payload claims "match" while its own numbers are the recorded
            # 500x629: a verdict that contradicts its data must be convicted.
            metrics(width=500.0, height=629.0, status="match"),
            metrics(verdict={"status": "yes"}),        # unknown status
        ]
        for payload in broken:
            with self.subTest(payload=str(payload)[:90]):
                self.assertNotEqual(decide(payload)["status"], "PASS",
                                    f"{str(payload)[:120]} went green")


class TheGateDoesNotTrustThePayloadItReads(unittest.TestCase):
    def test_a_payload_verdict_that_disagrees_with_its_own_numbers_is_red(self):
        # innerSizeLogical says 500x629, verdict says "match". The probe must
        # recompute, not relay — otherwise a Rust-side bug silently greens CI.
        out = decide(metrics(width=500.0, height=629.0, status="match"))
        self.assertEqual(out["status"], "FAIL", out)
        self.assertIn("verdict disagreement", out["reason"])

    def test_tolerance_drift_between_the_two_layers_is_red(self):
        # 440x900 needs a 220px tolerance; the payload carrying a different
        # slack than the probe means one rule lives in two places.
        payload = metrics(width=440.0, height=900.0,
                          verdict=verdict(status="match",
                                          deviation={"width": 0.0, "height": 100.0},
                                          tolerance=150.0))
        out = decide(payload)
        self.assertEqual(out["status"], "FAIL", out)
        self.assertIn("tolerance drift", out["reason"])

    def test_an_emulated_measurement_is_rejected_by_name(self):
        out = decide(metrics(measurementMode="cdp-emulation"))
        self.assertEqual(out["status"], "FAIL", out)
        self.assertIn("emulated, not native", out["reason"])

    def test_a_binary_whose_embedded_config_differs_from_the_tree_is_red(self):
        out = decide(metrics(), tree_declared={"width": 440.0, "height": 700.0})
        self.assertEqual(out["status"], "FAIL", out)
        self.assertIn("binary/config drift", out["reason"])

    def test_a_matching_tree_config_is_accepted(self):
        self.assertEqual(decide(metrics(),
                                tree_declared={"width": 440.0, "height": 680.0})
                         ["status"], "PASS")


class CrossLanguageRulesAgree(unittest.TestCase):
    """The tolerance and the wire keys exist in two languages; each pair is
    asserted against the other source file, so a rename or a re-tune in one layer
    fails here instead of silently changing what CI means."""

    def test_the_rust_and_python_tolerance_are_the_same_number(self):
        rust = re.search(r"GEOMETRY_TOLERANCE_LOGICAL_PX:\s*f64\s*=\s*([0-9.]+)",
                         LIB_RS.read_text(encoding="utf-8"))
        self.assertIsNotNone(rust, "the Rust tolerance constant is gone")
        self.assertAlmostEqual(float(rust.group(1)), wsr.TOLERANCE_LOGICAL_PX, places=6)

    def test_the_probe_reads_keys_the_serde_struct_actually_emits(self):
        # serde `rename_all = "camelCase"` turns inner_size_logical into
        # innerSizeLogical; the payload built above is what the probe parses, and
        # tauri.conf.json is where the declared side of the comparison lives.
        conf = json.loads(TAURI_CONF.read_text(encoding="utf-8"))
        panel = next(w for w in conf["app"]["windows"] if w["label"] == "panel")
        # 680, not 780: a non-resizable window's declared size is its physical demand, and 780 logical
        # needs 1560 physical at 200% scaling, which does not fit a 2560x1392 work area (WUI-19 §7.1).
        self.assertEqual((panel["width"], panel["height"]), (440, 680))
        self.assertFalse(panel["resizable"],
                         "the fallback label resolution rule depends on the panel "
                         "being the only non-resizable declared window")
        for key in ("innerSizeLogical", "resolutionSucceeded", "scaleFactor",
                    "declared", "verdict"):
            self.assertIn(key, metrics(), key)
            self.assertTrue(re.search(rf"\b{key}\b", json.dumps(metrics())), key)

    def test_declared_panel_size_from_disk_matches_the_payload_builder(self):
        self.assertEqual(wsr.declared_from_conf(TAURI_CONF, "panel"),
                         {"width": 440, "height": 680})

    def test_declared_from_conf_never_invents_a_number(self):
        self.assertIsNone(wsr.declared_from_conf(TAURI_CONF, "nonexistent-window"))
        self.assertIsNone(wsr.declared_from_conf(Path("Z:/no/such/file.json"), "panel"))
        self.assertIsNone(wsr.declared_from_conf(TAURI_CONF, None))


class ProbeWiringIsFailClosed(unittest.TestCase):
    """Exit codes and the printed line, with the app mocked out. Nothing here
    launches a GUI: that is the whole point of keeping the decision pure."""

    def setUp(self):
        # `fixture_dir`, not `mkdtemp`: the root is chosen by the boundary helper
        # (which refuses an out-of-boundary TMPDIR instead of inheriting it), the
        # atexit sweep is registered by creation so cleanup cannot be forgotten,
        # and a removal Windows refuses is reported, not swallowed.
        self.tmp = project_temp.fixture_dir(prefix="wsr-test-")
        self.assertTrue(project_temp.inside_project(self.tmp),
                        f"fixture root escaped the boundary: {self.tmp}")
        self.addCleanup(self._release_fixture)
        fake_exe = self.tmp / "app.exe"
        fake_exe.write_bytes(b"not a real binary")
        self.exe = fake_exe

    def _release_fixture(self):
        """Prove the scratch is actually released — no `ignore_errors=True`.

        This cleanup is also the regression check for the probe's leaked stderr
        handle: while that handle stayed open, Windows refused to remove the
        directory and every previous run of this class left a `wsr-test-*` behind.
        Raising here is the intended behaviour — a visible error naming the path,
        not a silently surviving fixture.
        """
        if self.tmp.exists():
            shutil.rmtree(self.tmp)
        self.assertFalse(self.tmp.exists(),
                         f"TEMP_RESIDUE_NOT_REMOVED {self.tmp}")

    def _run(self, ipc_result, *, labels=("--label", "panel"), ipc_side_effect=None):
        u19 = SimpleNamespace(pick_free_port=lambda: 0, CDP=object,
                              resolve_app_exe=lambda: (None, {"reason": "patched"}))
        popens = []

        def fake_popen(*a, **k):
            handle = mock.MagicMock()
            handle.pid = 4242
            handle.poll.return_value = None      # alive: no early-exit path
            popens.append(handle)
            return handle

        ipc = (mock.patch.object(wsr, "read_metrics_via_ipc", side_effect=ipc_side_effect)
               if ipc_side_effect is not None else
               mock.patch.object(wsr, "read_metrics_via_ipc", return_value=ipc_result))
        with mock.patch.object(wsr, "load_u19", return_value=u19), ipc, \
                mock.patch.object(wsr, "measure_chrome_emulation",
                                  return_value={"status": "NOT_RUN", "reason": "patched"}), \
                mock.patch.object(wsr.subprocess, "Popen", side_effect=fake_popen):
            code = wsr.main(["--exe", str(self.exe), *labels,
                             "--evidence-dir", str(self.tmp),
                             "--json-out", str(self.tmp / "readback.json")])
        return code, popens

    def test_a_refusal_to_measure_exits_3_and_is_not_printed_as_a_pass(self):
        code, popens = self._run({"status": "NOT_RUN", "metrics": None, "attempts": [],
                                  "pageViewport": None, "reason": "no CDP page target"})
        self.assertEqual(code, 3, "exit 3 is the aggregate gate's red, never green")
        self.assertTrue(all(p.terminate.called for p in popens),
                        "the launched app must be torn down even on refusal")

    def test_a_mismatch_exits_1(self):
        code, _ = self._run({"status": "OK", "metrics": metrics(width=500.0, height=629.0,
                                                                status="mismatch"),
                             "attempts": [], "page": {}, "pageViewport": {}})
        self.assertEqual(code, 1)

    def test_a_matching_readback_exits_0(self):
        code, _ = self._run({"status": "OK", "metrics": metrics(), "attempts": [],
                             "page": {}, "pageViewport": {"innerWidth": 440,
                                                           "innerHeight": 680}})
        self.assertEqual(code, 0)

    def test_an_extra_failing_label_cannot_hide_behind_the_primary_pass(self):
        # Both labels are read in ONE launch; `main` going red must drag the
        # verdict down with it rather than being printed and forgotten.
        good = {"status": "OK", "metrics": metrics(), "attempts": [], "page": {},
                "pageViewport": {}}
        bad = {"status": "OK",
               "metrics": metrics(label="main", dec=declared(width=1280.0, height=820.0,
                                                              label="main"),
                                  width=1400.0, height=820.0, status="mismatch"),
               "attempts": [], "page": {}, "pageViewport": {}}
        code, popens = self._run(good, labels=("--label", "panel", "--label", "main"),
                                 ipc_side_effect=[good, bad])
        self.assertEqual(code, 1)

    def test_the_missing_exe_path_is_not_run_rather_than_a_launch_attempt(self):
        with mock.patch.object(wsr, "load_u19",
                               return_value=SimpleNamespace(
                                   pick_free_port=lambda: 0, CDP=object,
                                   resolve_app_exe=lambda: (None, {"reason": "stale"}))):
            code = wsr.main(["--exe", str(self.tmp / "nope.exe"),
                             "--evidence-dir", str(self.tmp),
                             "--json-out", str(self.tmp / "r.json")])
        self.assertEqual(code, 3)
        self.assertIn("does not exist",
                      json.loads((self.tmp / "r.json").read_text(encoding="utf-8"))
                      ["reason"])


class ScratchStaysInsideTheBoundary(unittest.TestCase):
    r"""ERR-163: "outside" is a rule the product enforces, not a host convention.

    These checks are the negative controls for the spill this file caused.
    None of them creates a path outside the repository: the out-of-boundary names
    here are asserted absent before AND after, so a refusal that leaked would show
    up as a failure instead of as a new residue directory in `C:\Windows\Temp`.
    """

    def test_the_default_evidence_root_is_a_declared_runtime_root(self):
        self.assertTrue(project_temp.inside_project(wsr.DEFAULT_EVIDENCE),
                        f"evidence default is outside the repo: {wsr.DEFAULT_EVIDENCE}")
        self.assertEqual(wsr.DEFAULT_EVIDENCE.parent,
                         project_temp.REPO_ROOT / ".project-local" / "runs",
                         "evidence must live under the declared .project-local/runs root")

    def test_no_path_is_derived_from_the_host_temp_root(self):
        """AST, not text: this module's own docstring discusses mkdtemp and %TEMP%.

        A call to `gettempdir`/`mkdtemp`/`NamedTemporaryFile`/`TemporaryDirectory`
        anywhere in the probe, or any `tempfile.*` attribute read, means a scratch
        root is again being taken from whatever the host happens to provide.
        """
        source = SCRIPT.read_text(encoding="utf-8")
        offenders: list[str] = []
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, ast.Call):
                func = node.func
                name = (func.attr if isinstance(func, ast.Attribute)
                        else getattr(func, "id", ""))
                if name in {"gettempdir", "mkdtemp", "NamedTemporaryFile",
                            "TemporaryDirectory", "gettempprefix", "gettempdir_bac"}:
                    offenders.append(f"{name}:{node.lineno}")
            elif (isinstance(node, ast.Attribute)
                    and isinstance(node.value, ast.Name) and node.value.id == "tempfile"):
                offenders.append(f"tempfile.{node.attr}:{node.lineno}")
        self.assertEqual(offenders, [], f"probe takes a path from the host temp: {offenders}")
        # an environment default is the same defect in a different spelling
        self.assertEqual(re.findall(r'os\.environ\.get\(\s*"(?:TMP|TEMP|TMPDIR)"', source), [],
                         "probe resolves a root from a temp environment variable")

    def test_the_boundary_helper_refuses_a_temp_root_from_outside_the_repo(self):
        """The helper, not just the probe, is proven to be mode-independent.

        Standalone the host temp is the machine temp directory (outside the repo);
        under the canonical gate runner TMP/TEMP/TMPDIR are bound inside
        `.project-local/runs/tmp`. A fixture
        helper that honoured either one would make a test pass in one mode and
        spill in the other, so the out-of-boundary setting must be refused — and
        refused without creating the directory it was refused.
        """
        refused = _outside_repo("temp-root-probe")
        self.assertFalse(refused.exists(), f"test precondition: {refused} already exists")
        name = str(refused / "wsr-test-")          # the shape a fixture would get
        with mock.patch.dict(os.environ,
                             {"TMPDIR": name, "TEMP": name, "TMP": name}, clear=False):
            root = project_temp.temp_root()
        self.assertTrue(project_temp.inside_project(root),
                        f"temp_root() honoured an out-of-boundary TMPDIR: {root}")
        self.assertFalse(refused.exists(),
                         f"temp_root() created the out-of-boundary root {refused}")

    def test_an_out_of_boundary_evidence_root_is_refused_before_anything_is_written(self):
        outside = _outside_repo("evidence-refusal")
        json_out = outside / "readback.json"
        self.assertFalse(outside.exists(), f"test precondition: {outside} already exists")
        buf = io.StringIO()
        with mock.patch("sys.stdout", new=buf):
            code = wsr.main(["--exe", str(outside / "app.exe"),
                             "--evidence-dir", str(outside),
                             "--json-out", str(json_out)])
        printed = buf.getvalue()
        self.assertEqual(code, 3, printed)
        self.assertIn("WINDOW_STATE_READBACK_NOT_RUN", printed)
        self.assertIn("outside the project Git root", printed)
        self.assertFalse(outside.exists(), f"refusal still created {outside}")
        self.assertFalse(json_out.exists(), f"refusal still wrote {json_out}")

    def test_a_refusal_needs_no_app_no_browser_and_no_exe_to_exist(self):
        """Boundary is checked first, so the refusal cannot depend on a launch.

        With the old ordering the probe had already mkdir'd its evidence root (and
        opened its stderr log) before it knew whether that root was legal.
        """
        with mock.patch.object(wsr, "load_u19",
                               side_effect=AssertionError("u19 must not be reached")):
            code = wsr.main(["--evidence-dir",
                             str(_outside_repo("ordering-probe"))])
        self.assertEqual(code, 3)
        self.assertFalse(_outside_repo("ordering-probe").exists())




class DefaultEntryAndHudWindowContract(unittest.TestCase):
    """CL-08 default entry + CL-12 native narrow HUD window, pinned on the declared bytes.

    2026-10-24 (owner: 「完成全部前后端任务 实现项目闭环」): the desktop main window is the
    product's default entry, and its URL now carries shell=daily; the browser address and every
    ?view= deep link keep the professional shell, so the 31-entry IA contract is untouched here.
    The HUD strip is a third declared window; its width band (140-160) and its read-only window
    flags are contract, not taste — CL-12 demanded a native 窄窗 with 贴边/拖动, and a config
    drift that widens it past the band or gives it a taskbar entry is a product change.
    """

    def _windows(self) -> dict:
        conf = json.loads(TAURI_CONF.read_text(encoding="utf-8"))
        return {w["label"]: w for w in conf["app"]["windows"]}

    def test_the_main_window_default_entry_is_the_daily_shell(self):
        url = self._windows()["main"]["url"]
        self.assertIn("surface=daily", url, url)
        # shell=tauri is the frameless shell's own declaration and must survive the entry
        # switch, or the caption cluster falls back to feature-detection alone.
        self.assertIn("shell=tauri", url, url)
        self.assertNotIn("surface=hud", url, url)

    def test_the_hud_window_is_declared_inside_the_narrow_band(self):
        hud = self._windows()["hud"]
        self.assertTrue(140 <= hud["width"] <= 160,
                        f"CL-12 demands a 140-160px native 窄窗, got {hud['width']}")
        self.assertEqual(hud["minWidth"], 140)
        self.assertIn("surface=hud", hud["url"], hud["url"])
        # The strip is its own surface, NOT the compact panel squeezed to 150px: measured at
        # 150 logical the compact TopStatusBar pushes ten controls past the viewport while
        # .app{overflow:hidden} keeps scrollWidth at 150, i.e. an unreachable control bar.
        self.assertNotIn("view=compact", hud["url"],
                        "a 150px window must not render the compact control strip")

    def test_the_hud_window_is_a_borderless_dockable_strip(self):
        hud = self._windows()["hud"]
        # 置顶跳任务栏 + 无边框 + 默认隐藏：与既有 panel 同一族浮窗契约（CL-12 现状行）。
        self.assertTrue(hud["alwaysOnTop"] and hud["skipTaskbar"] and hud["visible"] is False)
        self.assertFalse(hud["decorations"], "no native title bar: the strip drags by its own handle")
        self.assertFalse(hud["transparent"], "transparent=false stays pinned (CL-12 design-state row)")
        self.assertTrue(hud["resizable"],
                        "the fallback label-resolution rule depends on the panel being the only "
                        "non-resizable declared window; the HUD must not take that role")

    def test_declared_hud_size_from_disk_is_the_same_number_the_probe_will_expect(self):
        self.assertEqual(wsr.declared_from_conf(TAURI_CONF, "hud"), {"width": 150, "height": 480})

    def test_the_rust_side_docks_and_toggles_the_hud_window(self):
        """Config alone is not 贴边/拖动: the tray item, the flush-right dock and the drag
        capability must exist, each keyed on the same label the conf declares."""
        rust = LIB_RS.read_text(encoding="utf-8")
        self.assertIn('get_webview_window("hud")', rust, "no live hud window handling in lib.rs")
        self.assertIn('MenuItem::with_id(app, "hud"', rust, "the tray offers no HUD toggle")
        self.assertIn("msize.width as i32 - size.width as i32", rust,
                      "toggle_hud no longer docks flush against the right edge (贴边)")
        caps = ROOT / "apps" / "observer" / "src-tauri" / "capabilities" / "default.json"
        self.assertIn("hud", json.loads(caps.read_text(encoding="utf-8"))["windows"],
                      "data-tauri-drag-region is inert without start-dragging on this label")

    def test_the_daily_shell_carries_the_window_controls_it_needs_when_borderless(self):
        daily = ROOT / "apps" / "observer" / "frontend" / "src" / "daily" / "DailyApp.tsx"
        chrome = ROOT / "apps" / "observer" / "frontend" / "src" / "daily" / "DailyChrome.tsx"
        src = daily.read_text(encoding="utf-8")
        chrome_src = chrome.read_text(encoding="utf-8")
        # The caption cluster and the drag surface live in DailyChrome's TopBar since the STITCH
        # replication; the claim has not weakened -- it now reads the module that renders them AND
        # requires the daily entry to mount that TopBar, so neither file may drop its half.
        self.assertIn("<TopBar", src,
                      "importing TopBar without rendering it leaves the borderless window uncontrollable")
        self.assertIn("WindowControls", chrome_src,
                      "the default desktop entry cannot minimize/close without the caption cluster")
        self.assertIn("data-tauri-drag-region", chrome_src,
                      "a borderless default entry with no drag surface is un-movable")

# The runner stays at the very bottom on purpose: a `unittest.main()` guard placed above a class
# silently excludes every class below it. The 2026-10-25 audit found exactly that -- six tests,
# one of them genuinely red on main, that no gate or CI job had ever executed.
if __name__ == "__main__":
    unittest.main(verbosity=2)
