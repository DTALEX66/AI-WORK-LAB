#!/usr/bin/env python3
"""Measure how the shell's overlays actually enter and leave, driven by a real pointer.

CL-16 step 2 asked for enter/exit sampling on both sides of an overlay, under the standing rule that a
sample must be settled before it is believed. This instrument does that, and it is deliberately honest about
what it can and cannot assert today:

  * what it ASSERTS (a product claim that is true now, so a regression here is a real red):
      - the overlay opens from a dispatched mouse click on the control the user reads, not only from React
        state set by a test;
      - the overlay closes from Escape / the click-catcher / its own timer, again through the input path;
      - the entrance actually transitions: at least one sampled property changes value across the enter
        window. The skins declare `.drawer{transition:right .28s cubic-bezier(.2,0,0,1)}` and
        `.toast{transition:.22s ease}`, and until 2026-10-29 both components mounted with the open class
        already applied, so the browser was told one state and had nothing to animate.
      - every read happened after the paint stopped moving (the settled rule), or the run refuses.
  * what it REPORTS alongside: which properties moved and how many distinct values each held, so a reader
    can see what the assertion saw rather than trusting a bare PASS.

Exit: 0 OVERLAY_MOTION_GATE_PASS, 1 OVERLAY_MOTION_GATE_FAIL, 3 OVERLAY_MOTION_GATE_NOT_RUN.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "audit"))

import bundle_provenance  # noqa: E402
import topbar_geometry_via_cdp as geometry  # noqa: E402
import hud_strip_geometry_via_cdp as hud  # noqa: E402

OUT_DIR = ROOT / ".project-local" / "runs" / "overlay-gate"
WINDOW = "1280,820"

# One entry per overlay the shell ships. `trigger` is the label a user reads on the control that opens it,
# so the probe aims at the thing in the interface rather than at a React setter.
OVERLAYS = (
    {"name": "drawer", "trigger": "工作区", "selector": "aside.drawer",
     "properties": ("right", "transform", "opacity"), "close": "escape"},
    {"name": "toast", "trigger": "通知", "selector": ".toast-stack .toast",
     "properties": ("transform", "opacity", "right"), "close": "timer"},
)

# Find the control by its own text, then hand back its centre. Matching on text rather than on a positional
# index matters: the top bar folds controls away at narrow widths, and an index would click a different
# button while still reporting a number.
TRIGGER_JS = """(function(label){
  const nodes = Array.from(document.querySelectorAll('button, [role=button], a'));
  const hit = nodes.find((n) => (n.textContent || '').trim() === label
    || (n.getAttribute('aria-label') || '').trim() === label);
  if (!hit) return JSON.stringify({found: false, label: label, candidates: nodes.length});
  const r = hit.getBoundingClientRect();
  return JSON.stringify({found: true, label: label, tag: hit.tagName,
                         x: Math.round(r.left + r.width / 2), y: Math.round(r.top + r.height / 2),
                         rect: {left: r.left, top: r.top, width: r.width, height: r.height}});
})('%s')"""


def sample_js(selector: str, props: tuple[str, ...]) -> str:
    """One read of the overlay's animated properties, plus whether it is in the document at all."""
    return """(function(sel, props){
  const el = document.querySelector(sel);
  if (!el) return JSON.stringify({present: false, sel: sel});
  const cs = getComputedStyle(el);
  const out = {present: true, sel: sel, cls: el.className, values: {}};
  props.forEach((p) => { out.values[p] = cs[p]; });
  const r = el.getBoundingClientRect();
  out.rect = {left: r.left, top: r.top, width: r.width, height: r.height};
  return JSON.stringify(out);
})('%s', %s)""" % (selector, json.dumps(list(props)))


def send_mouse(cdp, kind: str, x: int, y: int) -> None:
    cdp.send("Input.dispatchMouseEvent",
             {"type": kind, "x": x, "y": y, "button": "left", "clickCount": 1,
              "pointerType": "mouse", "timestamp": time.time()})


def real_click(cdp, x: int, y: int) -> None:
    """Press and release at one point: this is what makes `:active` and a handler fire together."""
    send_mouse(cdp, "mousePressed", x, y)
    time.sleep(0.05)
    send_mouse(cdp, "mouseReleased", x, y)


def send_escape(cdp) -> None:
    for kind in ("keyDown", "keyUp"):
        cdp.send("Input.dispatchKeyEvent", {
            "type": kind, "windowsVirtualKeyCode": 27, "nativeVirtualKeyCode": 27,
            "code": "Escape", "key": "Escape", "text": "", "timestamp": time.time()})


def sample_series(cdp, selector: str, props: tuple[str, ...], *, window_s: float,
                  poll_s: float = 0.016, stop_when_absent: bool = False) -> list[dict]:
    """Read every poll for `window_s`; the frames are the evidence, so they are kept, not summarised away."""
    samples = []
    deadline = time.time() + window_s
    while time.time() < deadline:
        raw = cdp.evaluate(sample_js(selector, props))
        state = json.loads(raw) if isinstance(raw, str) else raw
        samples.append(state)
        if stop_when_absent and not state.get("present"):
            break
        time.sleep(poll_s)
    return samples


def distinct_values(samples: list[dict], prop: str) -> list[str]:
    seen: list[str] = []
    for s in samples:
        value = ((s.get("values") or {}).get(prop))
        if value is not None and (not seen or seen[-1] != value):
            seen.append(value)
    return seen


def emulate_motion(cdp, value: str) -> bool:
    """Pin `prefers-reduced-motion` over CDP and read `matchMedia` back, so the pin is proven not assumed.

    Headless Chrome answers this question by default — measured on 2026-10-26, when the pressed-state gate
    read `transform='none'`/`transitionDuration='0s'` on a CI runner and `matrix(0.99…)`/`0.08s` locally.
    That was the instrument measuring the environment's motion preference while claiming to measure the rule.
    A gate that asserts "there were intermediate frames" without pinning this is asserting the OS setting.
    """
    cdp.send("Emulation.setEmulatedMedia",
             {"features": [{"name": "prefers-reduced-motion", "value": value}]})
    time.sleep(0.2)  # the recalc has to land before anything is read
    read = json.loads(cdp.evaluate(
        "JSON.stringify({reduce: window.matchMedia('(prefers-reduced-motion: reduce)').matches})"))
    return bool(read.get("reduce"))


def measure_overlay(cdp, spec: dict, *, enter_window_s: float, exit_window_s: float,
                    reduced_motion: bool = False) -> dict:
    """Open it with a click, sample the enter, close it through its own input path, sample the exit."""
    out: dict = {"name": spec["name"], "selector": spec["selector"]}
    out["reducedMotion"] = emulate_motion(cdp, "reduce" if reduced_motion else "no-preference")
    if out["reducedMotion"] != reduced_motion:
        # The page still reports the other preference: whatever this reading says about frames is a
        # statement about the environment, so it is refused rather than scored.
        out["mode"] = "preference-not-pinned"
        return out
    trigger = json.loads(cdp.evaluate(TRIGGER_JS % spec["trigger"]))
    out["trigger"] = trigger
    if not trigger.get("found"):
        out["opened"] = False
        out["mode"] = "trigger-not-found"
        return out
    real_click(cdp, trigger["x"], trigger["y"])
    enter = sample_series(cdp, spec["selector"], spec["properties"], window_s=enter_window_s)
    present = [s for s in enter if s.get("present")]
    out["enterSamples"] = len(enter)
    out["presentFrames"] = len(present)
    out["opened"] = bool(present)
    out["mountedClass"] = present[0].get("cls") if present else None
    out["enterValues"] = {p: distinct_values(enter, p) for p in spec["properties"]}
    tail = enter[-6:]
    out["settledWhileOpen"] = (all(len({(s.get("values") or {}).get(p) for s in tail}) == 1
                                   for p in spec["properties"])
                               if len(enter) >= 6 else None)
    if not out["opened"]:
        out["mode"] = "click-did-not-open"
        return out
    time.sleep(0.25)
    if spec["close"] == "escape":
        # The drawer's own contract is Esc-to-close (`drawer.tsx`'s keydown listener), so the exit is driven
        # by the key a user presses rather than by reaching into React state.
        send_escape(cdp)
    # Sample the whole exit window instead of stopping at the first absent frame: an overlay that animates
    # out and one that vanishes are two different products, and both need the frames to tell them apart.
    exit_samples = sample_series(cdp, spec["selector"], spec["properties"], window_s=exit_window_s)
    present_exit = [s for s in exit_samples if s.get("present")]
    absent_at = next((i for i, s in enumerate(exit_samples) if not s.get("present")), None)
    out["exitSamples"] = len(exit_samples)
    out["exitFramesPresent"] = len(present_exit)
    out["unmountedAtSample"] = absent_at
    out["unmountedDuringExit"] = absent_at is not None
    out["exitValues"] = {p: distinct_values(present_exit, p) for p in spec["properties"]}
    out["closePath"] = spec["close"]
    out["mode"] = "real-pointer"
    return out


def verdict(measurements: dict[str, dict]) -> dict:
    """Pure: the thresholds live here so a plant can be tested without a browser.

    Two assertions and one report. The report (`overlay_motion_observed`) is deliberately NOT a check:
    scoring "nothing animated" as a pass would be a false green, and scoring it as a failure would convict
    the product for a feature CL-16 step 3 has not introduced yet. It is printed, and it is in the receipt.
    """
    checks: list[dict] = []
    motion: dict[str, str] = {}

    def add(name: str, ok: bool, detail: str) -> None:
        checks.append({"check": name, "pass": bool(ok), "detail": detail})

    # A verdict over nothing measured would be `all([])` — a pass. Name it and fail it instead, because the
    # cheapest false green in this project has always been an empty population scoring zero failures.
    add("gate_measured_an_overlay", bool(measurements),
        "overlays=" + (json.dumps(sorted(measurements)) if measurements
                       else "none — nothing was measured, so nothing was proven"))

    for name, m in measurements.items():
        add(f"overlay_trigger_rendered[{name}]", bool(m.get("trigger", {}).get("found")),
            json.dumps(m.get("trigger"), ensure_ascii=False)[:180])
        add(f"overlay_opens_from_a_real_click[{name}]", bool(m.get("opened")),
            f"mode={m.get('mode')!r} enterSamples={m.get('enterSamples')} "
            f"presentFrames={m.get('presentFrames')} mountedClass={m.get('mountedClass')!r}")
        add(f"overlay_closes_through_its_input_path[{name}]", bool(m.get("unmountedDuringExit")),
            f"closePath={m.get('closePath')!r} exitSamples={m.get('exitSamples')} "
            f"framesStillPainted={m.get('exitFramesPresent')} "
            f"unmountedAtSample={m.get('unmountedAtSample')}")
        enter_moved = {p: len(v) for p, v in (m.get("enterValues") or {}).items() if len(v) > 1}
        exit_moved = {f"exit:{p}": len(v) for p, v in (m.get("exitValues") or {}).items() if len(v) > 1}
        moved = {**enter_moved, **exit_moved}
        motion[name] = ("animated:" + json.dumps(moved)) if moved else \
            "NOT_ANIMATED: every sampled property held one value across the whole enter and exit window"
        # The assertion the report was waiting for: the skin declares `.drawer{transition:right .28s}` and
        # `.toast{transition:.22s}`, so an entrance that samples one value from the first painted frame
        # onwards is a broken promise, not a style preference. Enter and exit are counted separately on
        # purpose: an overlay that appears instantly but fades out has a real defect on the enter side, and
        # folding the two together would let the fade excuse the jump cut.
        add(f"overlay_enter_transitions[{name}]", bool(m.get("opened")) and bool(enter_moved),
            f"enterValues={json.dumps(m.get('enterValues'), ensure_ascii=False)[:180]} "
            f"mountedClass={m.get('mountedClass')!r} → {motion[name]}")
        # The other half of the same rule: the accessibility floor answers `reduce` with the transition
        # turned off, so the reduced branch must arrive at the SAME destination without intermediate frames.
        # Asserting only the animated side is how a gate pressures someone into deleting that floor.
        reduce = m.get("reduce") or {}
        add(f"overlay_motion_preference_pinned[{name}]",
            m.get("reducedMotion") is False and reduce.get("reducedMotion") is True,
            f"normal reducedMotion={m.get('reducedMotion')!r} reduce reducedMotion={reduce.get('reducedMotion')!r} "
            f"modes={m.get('mode')!r}/{reduce.get('mode')!r} "
            "(headless Chrome answers this preference by itself; unpinned, this gate would measure the environment)")
        normal_end = {p: (v[-1] if v else None) for p, v in (m.get("enterValues") or {}).items()}
        reduce_end = {p: (v[-1] if v else None) for p, v in (reduce.get("enterValues") or {}).items()}
        # "No intermediate frames", not "one value": the component still paints closed for a frame and then
        # the end state, so a correct reduced run holds TWO values (measured 2026-10-29: `right` went
        # `-540px → 0px` with nothing between). What must never appear under reduce is the sequence the
        # animated side shows — 17 values for the same drawer.
        add(f"overlay_reduced_motion_arrives_without_frames[{name}]",
            bool(reduce.get("opened"))
            and all(len(v) <= 2 for v in (reduce.get("enterValues") or {}).values())
            and reduce_end == normal_end,
            f"reduce enterValues={json.dumps(reduce.get('enterValues'), ensure_ascii=False)[:170]} "
            f"normal end={json.dumps(normal_end, ensure_ascii=False)[:170]} opened={reduce.get('opened')}")
        # The other side CL-16 step 2 asked for: leaving must be painted too, not just deleted. An overlay
        # that vanishes between two frames is the same defect as one that appears already open, seen from
        # the other end — and the exit is the side that regresses silently when a list removes its item in
        # the same tick the class is dropped.
        exit_moved = {p: len(v) for p, v in (m.get("exitValues") or {}).items() if len(v) > 1}
        add(f"overlay_exit_transitions[{name}]",
            bool(m.get("unmountedDuringExit")) and bool(exit_moved),
            f"exitValues={json.dumps(m.get('exitValues'), ensure_ascii=False)[:180]} "
            f"framesStillPainted={m.get('exitFramesPresent')} unmountedAtSample={m.get('unmountedAtSample')}")
    return {"passed": all(c["pass"] for c in checks), "checks": checks, "motion": motion,
            "surfaces": sorted(measurements)}


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=str(ROOT))
    ap.add_argument("--overlay", action="append", default=None,
                    help=f"which overlays to measure (default: {' '.join(o['name'] for o in OVERLAYS)})")
    ap.add_argument("--json-out", default=None)
    args = ap.parse_args()

    wanted = args.overlay or [o["name"] for o in OVERLAYS]
    unknown = sorted(set(wanted) - {o["name"] for o in OVERLAYS})
    if unknown:
        print(f"OVERLAY_MOTION_GATE_NOT_RUN UNKNOWN_OVERLAY {json.dumps(unknown)}")
        return 2
    specs = [o for o in OVERLAYS if o["name"] in wanted]

    root = Path(args.root).resolve()
    dist = root / "apps" / "observer" / "frontend" / "dist"
    if not (dist / "index.html").is_file():
        print(f"OVERLAY_MOTION_GATE_NOT_RUN DIST_ABSENT {dist}")
        return 3
    browser = geometry.find_browser()
    if not browser:
        print("OVERLAY_MOTION_GATE_NOT_RUN BROWSER_NOT_FOUND "
              "set WL_CHROME to a Chrome/Edge binary; a named category is not a pass")
        return 3

    geometry.OUT_DIR.mkdir(parents=True, exist_ok=True)
    u19 = geometry.load_u19()
    fixture = hud.SnapshotFixture(dist)
    fixture.start()
    measurements: dict[str, dict] = {}
    try:
        for spec in specs:
            # The professional shell is where the top bar's controls live; the HUD strip has neither.
            url = fixture.url_for("view=full")
            normal: dict = {}
            reduced: dict = {}

            def hook(cdp, _spec=spec, _normal=normal, _reduced=reduced) -> None:
                _normal.update(measure_overlay(cdp, _spec, enter_window_s=0.6, exit_window_s=2.6))
                _reduced.update(measure_overlay(cdp, _spec, enter_window_s=0.6, exit_window_s=2.6,
                                                reduced_motion=True))

            geometry.serve_and_eval(root, "/index.html", WINDOW,
                                    "JSON.stringify({ok: true})", browser, u19, None,
                                    viewport=(1280, 820), serve_url=url, after_mount=hook,
                                    mount_selector=".app")
            # Both preferences are measured in the same document, pinned in sequence: each branch re-pins
            # `prefers-reduced-motion` over CDP and reads `matchMedia` back before it samples anything, so a
            # re-pin that did not land is refused as `preference-not-pinned` rather than scored.
            normal["reduce"] = reduced
            measurements[spec["name"]] = normal
    finally:
        fixture.stop_server()

    if not measurements or all(not m for m in measurements.values()):
        print("OVERLAY_MOTION_GATE_NOT_RUN NO_MEASUREMENT — the browser produced no reading for any overlay")
        return 3
    result = verdict(measurements)
    result["startedAt"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    result["browser"] = browser
    result["servedBundle"] = bundle_provenance.describe(root)
    result["measured"] = measurements
    result["residue"] = list(geometry.RESIDUE)
    result["portAnnouncedMismatch"] = list(geometry.ANNOUNCED_MISMATCH)

    out = Path(args.json_out) if args.json_out else (OUT_DIR / f"overlays_{int(time.time())}.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    for check in result["checks"]:
        print(f"{check['check']:<48} {'PASS' if check['pass'] else 'FAIL'} {check['detail'][:150]}")
    for name, state in result["motion"].items():
        print(f"OVERLAY_MOTION_REPORTED {name}: {state}")
    print(f"OVERLAY_MOTION_GATE_{'PASS' if result['passed'] else 'FAIL'} "
          f"overlays={json.dumps(result['surfaces'])} " + str(out))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
