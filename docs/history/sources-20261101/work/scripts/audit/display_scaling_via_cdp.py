#!/usr/bin/env python
"""WUI-14 display-scaling gate — what the shipped windows become at 100/125/150/200% display scaling.

The taskpack clause reads "2560×1440与100/125/150/200%DPI". Two halves hide in that one line, and this
instrument reports them separately because they are provable by different means:

  * the LAYOUT half is measurable in a browser. Windows scaling does not stretch a CSS layout: a maximised
    window on a 2560px screen at 150% hands the page a 1706px CSS viewport, which is a narrower layout,
    not a bigger one. So the honest emulation is the divided viewport, pinned through CDP device metrics,
    with deviceScaleFactor set so the raster and `window.devicePixelRatio` follow. `__dpr` is asserted
    against the asked scale: a sweep whose four runs all report dpr 1 measured one DPI four times.
  * the PHYSICAL half is arithmetic on what the shell declares. `minWidth`/`minHeight` and the HUD's fixed
    440x680 are logical pixels, so their physical footprint is the declared size times the scale, and
    whether that fits the screen is a property of the window the OS makes, not of the page. It is reported
    as derived-from-declaration, and the consequence is stated, because "fits at 100%" is not evidence
    about 200%.

What this does NOT claim: it is not a Per-Monitor v2 manifest check and it is not WebView2's own bitmap
path. The repo declares no DPI manifest of its own (`src-tauri/build.rs` is a bare `tauri_build::build()`),
so awareness comes from the framework, and the only readback that could confirm it on this machine is a
release `app.exe` — which the artifact gate says is absent. That gap is named in the JSON, never defaulted.

Exit: 0 DISPLAY_SCALING_GATE_PASS, 1 DISPLAY_SCALING_GATE_FAIL, 3 DISPLAY_SCALING_GATE_NOT_RUN.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "audit"))
import bundle_provenance  # noqa: E402  # the receipt has to name the bytes the browser loaded

GEOMETRY = ROOT / "scripts" / "audit" / "topbar_geometry_via_cdp.py"
OUT_DIR = ROOT / ".project-local" / "artifacts" / "wui-20261009"
TAURI_CONF = ROOT / "apps" / "observer" / "src-tauri" / "tauri.conf.json"

# The taskpack names one physical surface; the scales are the four Windows settings it names.
PHYSICAL = (2560, 1440)
SCALES = (1.0, 1.25, 1.5, 2.0)
# An outer window Chrome will actually make. The layout viewport comes from the device-metrics override,
# not from this number — asking for 2600 outer on a screen that reports 800x600 would clamp and measure
# a width that was never there.
OUTER_WINDOW = "1280,820"
DPR_TOLERANCE = 0.02


def load_geometry():
    path = GEOMETRY
    spec = importlib.util.spec_from_file_location("geometry", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[attr-defined]
    return module


def declared_windows() -> dict:
    """Read the window shapes the shipped shell declares, so the table is the product's, not ours."""
    conf = json.loads(TAURI_CONF.read_text(encoding="utf-8"))
    out = {}
    for win in conf["app"]["windows"]:
        out[win["label"]] = {
            "width": win.get("width"), "height": win.get("height"),
            "minWidth": win.get("minWidth"), "minHeight": win.get("minHeight"),
            "resizable": win.get("resizable", True),
        }
    return out


def css_viewport(scale: float, physical: tuple[int, int]) -> tuple[int, int]:
    # Floor, like Windows does: a fractional CSS width is not a thing a layout gets.
    return (math.floor(physical[0] / scale), math.floor(physical[1] / scale))


def physical_footprint(size: tuple[int, int], scale: float) -> tuple[int, int]:
    return (math.ceil(size[0] * scale), math.ceil(size[1] * scale))


def derived_checks(windows: dict, physical: tuple[int, int], work_area: tuple[int, int]) -> list[dict]:
    """Arithmetic on the declared logical sizes at each scale. No browser, and it says so."""
    checks: list[dict] = []
    for scale in SCALES:
        css = css_viewport(scale, physical)
        main = windows.get("main") or {}
        floor_css = (main.get("minWidth"), main.get("minHeight"))
        checks.append({
            "check": "maximised_main_window_css_viewport",
            "scale": scale,
            "detail": f"physical {physical[0]}x{physical[1]} -> css {css[0]}x{css[1]}",
        })
        if floor_css[0] and floor_css[1]:
            # The declared minimum window in physical px, against the work area the desktop really offers.
            fp = physical_footprint(floor_css, scale)
            fits = fp[0] <= work_area[0] and fp[1] <= work_area[1]
            checks.append({
                "check": "declared_minimum_window_fits",
                "scale": scale,
                "pass": fits,
                "basis": "derived-from-declaration",
                "detail": (f"main minWidth/minHeight {floor_css[0]}x{floor_css[1]} logical = "
                           f"{fp[0]}x{fp[1]} physical at {scale:g}x, work area {work_area[0]}x{work_area[1]}"
                           + ("" if fits else " — the smallest legal window does not fit this screen")),
            })
        panel = windows.get("panel") or {}
        if panel.get("width") and panel.get("height") and panel.get("resizable") is False:
            # A non-resizable window cannot shrink to fit, so its declared size IS the physical demand.
            fp = physical_footprint((panel["width"], panel["height"]), scale)
            fits = fp[0] <= work_area[0] and fp[1] <= work_area[1]
            checks.append({
                "check": "fixed_hud_window_fits",
                "scale": scale,
                "pass": fits,
                "basis": "derived-from-declaration",
                "detail": (f"panel {panel['width']}x{panel['height']} logical, resizable=false -> "
                           f"{fp[0]}x{fp[1]} physical at {scale:g}x, work area "
                           f"{work_area[0]}x{work_area[1]}"
                           + ("" if fits else " — this scale needs more screen than the surface offers")),
            })
    return checks


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=str(ROOT))
    ap.add_argument("--json-out", default=None)
    ap.add_argument("--physical", default=f"{PHYSICAL[0]},{PHYSICAL[1]}",
                    help="physical WxH of the screen the acceptance names")
    ap.add_argument("--work-area", default=None,
                    help="physical WxH minus taskbar/borders; defaults to the --physical value minus "
                         "48px of taskbar, and the assumption is printed rather than hidden")
    args = ap.parse_args()

    root = Path(args.root).resolve()
    dist = root / "apps" / "observer" / "frontend" / "dist" / "index.html"
    if not dist.is_file():
        print(f"DISPLAY_SCALING_GATE_NOT_RUN DIST_ABSENT {dist}")
        return 3
    try:
        pw, ph = (int(token) for token in args.physical.split(","))
    except ValueError:
        print(f"DISPLAY_SCALING_GATE_NOT_RUN BAD_PHYSICAL {args.physical!r}")
        return 3
    if args.work_area:
        try:
            ww, wh = (int(token) for token in args.work_area.split(","))
        except ValueError:
            print(f"DISPLAY_SCALING_GATE_NOT_RUN BAD_WORK_AREA {args.work_area!r}")
            return 3
        work_area_note = "taken from --work-area"
    else:
        ww, wh = pw, ph - 48
        work_area_note = (f"assumed: {pw}x{ph} minus a 48px taskbar. This machine reports a virtualised "
                          "screen to headless Chrome, so the real work area is an owner-level reading.")
    physical = (pw, ph)
    work_area = (ww, wh)

    geometry = load_geometry()
    browser = geometry.find_browser()
    if not browser:
        print("DISPLAY_SCALING_GATE_NOT_RUN BROWSER_NOT_FOUND set WL_CHROME to a Chrome/Edge binary")
        return 3
    u19 = geometry.load_u19()
    windows = declared_windows()

    report = {
        "instrument": "display_scaling_via_cdp",
        "physicalScreen": {"asked": list(physical), "workArea": list(work_area),
                           "workAreaBasis": work_area_note},
        "declaredWindows": windows,
        "dpiAwarenessReadback": {
            "status": "NOT_MEASURED",
            "reason": ("no release app.exe carries a readable manifest on this machine, and the repo declares "
                       "no DPI manifest of its own (src-tauri/build.rs is a bare tauri_build::build()), so "
                       "Per-Monitor v2 awareness is framework behaviour asserted by dependency, not read back "
                       "from a shipped artifact"),
        },
        "sweep": [],
        "derived": derived_checks(windows, physical, work_area),
    }

    failures: list[str] = []
    expr = geometry.EXPR.replace("SELECTORS", json.dumps(geometry.SELECTORS))
    for scale in SCALES:
        css = css_viewport(scale, physical)
        path = "/index.html?view=full&mode=UNKNOWN&theme=dark&shell=tauri"
        try:
            measured = geometry.serve_and_eval(root, path, OUTER_WINDOW, expr, browser, u19,
                                               None, viewport=css, scale_factor=scale)
        except Exception as exc:  # noqa: BLE001 — a launch that dies is a finding, not a stack trace
            report["sweep"].append({"scale": scale, "cssViewport": list(css),
                                    "error": f"{type(exc).__name__}: {exc}"})
            failures.append(f"scale {scale:g}x: browser did not answer")
            continue
        verdict = geometry.verdict(measured, "full")
        dpr = measured.get("__dpr")
        inner = measured.get("__innerWidth")
        viewport_ok = inner == css[0]
        dpr_ok = isinstance(dpr, (int, float)) and abs(dpr - scale) <= DPR_TOLERANCE
        if not viewport_ok:
            failures.append(f"scale {scale:g}x: asked css width {css[0]}, page reports {inner}")
        if not dpr_ok:
            failures.append(f"scale {scale:g}x: asked dpr {scale}, page reports {dpr} — the override "
                            "did not reach the page, so this row measured nothing about that scale")
        if not verdict["passed"]:
            failures.append(f"scale {scale:g}x: geometry verdict FAILED")
        report["sweep"].append({
            "scale": scale,
            "cssViewport": list(css),
            "reportedViewport": measured.get("__viewport"),
            "reportedDpr": dpr,
            "checksViewport": viewport_ok,
            "checksDpr": dpr_ok,
            "railWidth": (measured.get(".sidebar") or [{}])[0].get("width"),
            "topbarHeight": (measured.get(".topbar") or [{}])[0].get("height"),
            "verdict": verdict,
        })
        line = (f"SCALE {scale:g}x css={css[0]}x{css[1]} dpr={dpr} viewport_ok={viewport_ok} "
                f"geometry={'PASS' if verdict['passed'] else 'FAIL'}")
        print(line, flush=True)

    for row in report["derived"]:
        if "pass" in row and not row["pass"]:
            failures.append(f"derived {row['check']} at {row['scale']:g}x: {row['detail']}")
        print(f"DERIVED {row['check']} {row['scale']:g}x "
              f"{'ok' if row.get('pass', True) else 'FAIL'} {row['detail']}", flush=True)

    report["failures"] = failures
    report["servedBundle"] = bundle_provenance.describe(ROOT)
    report["verdictToken"] = "DISPLAY_SCALING_GATE_PASS" if not failures else "DISPLAY_SCALING_GATE_FAIL"
    out_path = Path(args.json_out) if args.json_out else OUT_DIR / "display-scaling.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    for failure in failures:
        print(f"FAIL {failure}")
    print(f"JSON_OUT {out_path}")
    print(report["verdictToken"])
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
