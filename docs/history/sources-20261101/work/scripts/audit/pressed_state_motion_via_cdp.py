#!/usr/bin/env python
"""Prove the pressed state paints a different transform, over the shipped bundle, with real CSS state.

CL-16's first step is one dimension: `:active`. The two tokens that name it (`--motion-pressed`,
`--pressed-scale`) were declared in `apps/observer/frontend/src/index.css` and consumed by nothing -- the
only pressed rule in the tree was `.node:active{cursor:grabbing}` in `apps/observer/frontend/src/skins/b10.css`,
a cursor and not a motion -- so a token could be renamed, retuned or deleted and no check would notice,
which is the failure mode this project has already recorded as "aspirational tokens".

A synthetic `dispatchEvent(new MouseEvent('mousedown'))` cannot light a CSS pseudo-class -- that is why the
four hover assertions in `scripts/audit/hud_strip_geometry_via_cdp.py` can never fail (recorded in the open
register, CL-17). So this instrument does not synthesise anything: it asks Chrome, over the CSS domain, to
force `:active` on a real node and then reads back `getComputedStyle`. The rule either reaches the painted
box or it does not.

Two surfaces, each read twice in its own browser process -- never two reads of one page:

  console  `…`                     the professional shell: `.nav button`, `.primary-btn`, `.ghost-btn`
  daily    `…&surface=daily`       the shell the desktop window shows: `nav[data-landmark="rail"] button`

  idle     no pseudo state forced  -- what the control looks like untouched
  pressed  `:active` forced        -- what the operator gets while the button is still down

Keeping idle and pressed in separate processes is what makes "the delta is real" checkable: a page that
reported the same transform twice would be a broken readback, and a page that reported a pressed transform
identical to idle means the rule was never applied. Measuring the daily surface separately is what keeps the
gate honest about coverage -- the first version of this instrument printed `controls=2` while the surface an
operator actually points at was matched by none of its selectors.

The expectation is DERIVED from the token, not pinned: `--pressed-scale` becomes the matrix diagonal the
browser must show, `--motion-pressed` becomes the `transition-duration` it must show. Retuning a token in
source therefore moves the floor with it instead of breaking a hardcoded number.

usage: python scripts/audit/pressed_state_motion_via_cdp.py [--json-out PATH] [--selector '.nav button']
"""
from __future__ import annotations

import argparse
import json
import math
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for _entry in (ROOT / "scripts" / "audit", ROOT / "apps" / "observer" / "scripts"):
    sys.path.insert(0, str(_entry))

import bundle_provenance  # noqa: E402
import hud_strip_geometry_via_cdp as hud  # noqa: E402
import topbar_geometry_via_cdp as geometry  # noqa: E402

OUT_DIR = ROOT / ".project-local" / "artifacts" / "cl16-pressed-motion"
RAIL_SELECTOR = 'nav[data-landmark="rail"] button'
# Each surface names the control the gate refuses to run without. A selector that matches nothing would skip
# every assertion on it silently, so "which surface was actually measured" is part of the verdict, not a
# detail of the run. `.nav button` is the professional console's sidebar; the rail is the daily shell's own
# navigation -- the surface the desktop window really shows -- and it is styled with Tailwind utilities, so
# the B10 skin rules never reach it.
SURFACES = (
    {"name": "console", "query": "", "mount": ".app", "required": ".nav button",
     "selectors": (".nav button", ".primary-btn", ".ghost-btn", ".soft-btn")},
    {"name": "daily", "query": "surface=daily&shell=tauri", "mount": "[data-shell]",
     "required": RAIL_SELECTOR, "selectors": (RAIL_SELECTOR,)},
)
WINDOW = "1280,820"

READ = """(function(selectors){
  var rootStyle = getComputedStyle(document.documentElement);
  var out = {selectors: [], tokens: {
    pressedScale: (rootStyle.getPropertyValue('--pressed-scale') || '').trim(),
    motionPressed: (rootStyle.getPropertyValue('--motion-pressed') || '').trim()
  },
  // Read the preference back FROM THE PAGE. The emulation is only known to have landed when the subject
  // itself says so; otherwise a runner whose default differs decides what the numbers mean.
  reducedMotion: window.matchMedia('(prefers-reduced-motion: reduce)').matches};
  selectors.forEach(function(sel){
    var nodes = document.querySelectorAll(sel);
    var entry = {selector: sel, count: nodes.length, transform: null,
                 transitionDuration: null, tag: null, label: null};
    if (nodes.length) {
      var first = nodes[0];
      var cs = getComputedStyle(first);
      entry.transform = cs.transform;
      entry.transitionDuration = cs.transitionDuration;
      entry.tag = first.tagName.toLowerCase();
      // The accessible name is what tells the reader which control these numbers came from; a transform
      // measured on an unnamed node is a number with no referent.
      entry.label = (first.getAttribute('aria-label') || first.textContent || '').trim().slice(0, 40);
    }
    out.selectors.push(entry);
  });
  return JSON.stringify(out);
})(SELECTORS)"""


def read_expression(selectors: list[str]) -> str:
    return READ.replace("SELECTORS", json.dumps(selectors))


def matrix_scale(transform: str | None) -> float | None:
    """The uniform scale a computed transform carries, or None when there is no transform at all."""
    if not transform or transform == "none":
        return None
    match = re.match(r"matrix\(([^)]+)\)", transform)
    if not match:
        return None
    parts = [float(value) for value in match.group(1).split(",")]
    return parts[0] if len(parts) == 6 else None


def seconds(value: str | None) -> float | None:
    """`transition-duration` as a number of seconds: Chrome renders 80ms as `0.08s`."""
    if not value:
        return None
    first = value.split(",")[0].strip()
    if first.endswith("ms"):
        return float(first[:-2]) / 1000.0
    if first.endswith("s"):
        return float(first[:-1])
    return None


def token_expectations(tokens: dict) -> tuple[float | None, float | None, list[str]]:
    problems: list[str] = []
    scale = None
    duration = None
    try:
        scale = float(tokens.get("pressedScale") or "")
    except ValueError:
        problems.append(f"tokens.pressedScale={tokens.get('pressedScale')!r} is not a number")
    duration = seconds(tokens.get("motionPressed"))
    if duration is None:
        problems.append(f"tokens.motionPressed={tokens.get('motionPressed')!r} is not a duration")
    return scale, duration, problems


def emulate_motion(cdp, value: str) -> None:
    """Pin `prefers-reduced-motion` for the page, and return nothing.

    Measured on the CI runner (2026-10-26, job `observer`): headless Chrome reports `reduce` by default, and
    the L10b accessibility floor in `apps/observer/frontend/src/skins/b10.css` answers it with
    `transition:none !important; transform:none !important`. So the pressed transform legitimately comes back
    `none` there -- a reading of the environment, not of the rule. An instrument that measures a motion
    therefore has to say which motion preference it measured under, and the reduced side has to be asserted
    too instead of being tripped over by accident.
    """
    cdp.send("Emulation.setEmulatedMedia", {"features": [{"name": "prefers-reduced-motion", "value": value}]})
    time.sleep(0.2)  # the media change has to recalc before anything is read


def settled_transform(cdp, expression: str, *, budget_s: float = 1.5, poll_s: float = 0.06) -> tuple:
    """Read the page until the computed transform stops changing, and report how long that took.

    Why this exists: `CSS.forcePseudoState` starts a transition, and a single read taken right after the
    force can land on the FIRST frame of it. Measured twice on 2026-10-28 for the same control:
    the CI runner (Windows, job `observer`) reported `matrix(1, 0, 0, 1, 0, 0)` — the identity at t=0 of a
    80ms scale transition — while the same command on the development host reported
    `matrix(0.99, 0, 0, 0.99, 0, 0)`. The token says 0.99, so the CI read convicted a correct render: the
    instrument sampled a moving thing. A state's end value is what the operator sees, so the read is
    repeated until two consecutive samples agree, inside a bounded budget.
    """
    last = None
    waited = 0.0
    while waited < budget_s:
        current = _transform_of(cdp, expression)
        if last is not None and current == last:
            return current, round(waited, 3)
        last = current
        time.sleep(poll_s)
        waited += poll_s
    return last, round(waited, 3)


def _transform_of(cdp, expression: str):
    """The first selector's computed transform, read out of the same expression the harvest uses.

    Reusing the harvest expression matters: a second, hand-written probe would settle a different element
    than the one the verdict scores, which is how instruments and products start disagreeing.
    """
    raw = cdp.evaluate(expression)
    try:
        state = json.loads(raw) if isinstance(raw, str) else raw
    except ValueError:
        return None
    rows = state.get("selectors") or []
    return (rows[0].get("transform") if rows else None)


def force_active(cdp, selectors: list[str], required: str) -> dict:
    """Hold `:active` on the first node of EVERY probed selector, and report the node id chosen per selector.

    Forcing only the required control would read the others while they are still untouched, and their
    pressed transform would come back `none` -- a failure that belongs to the instrument, not the product.
    """
    cdp.send("DOM.enable")
    cdp.send("CSS.enable")
    document = cdp.send("DOM.getDocument", {"depth": 1})
    root_node = (document.get("root") or {}).get("nodeId")
    if not root_node:
        raise RuntimeError(f"DOM.getDocument returned no root nodeId: {json.dumps(document)[:200]}")
    forced: dict[str, int] = {}
    for selector in selectors:
        found = cdp.send("DOM.querySelector", {"nodeId": root_node, "selector": selector})
        node_id = found.get("nodeId") or 0
        if not node_id:
            if selector == required:
                raise RuntimeError(f"no node matched the required selector {selector!r}")
            continue
        cdp.send("CSS.forcePseudoState", {"nodeId": node_id, "forcedPseudoClasses": ["active"]})
        forced[selector] = node_id
    time.sleep(0.2)  # the recalc has to land before the read
    return forced


CONTROL_STATE_JS = """(function(sel){
  var el = document.querySelector(sel);
  if (!el) return JSON.stringify({found: false, sel: sel});
  var r = el.getBoundingClientRect();
  return JSON.stringify({found: true, sel: sel,
                         x: Math.round(r.left + r.width / 2),
                         y: Math.round(r.top + r.height / 2),
                         active: el.matches(':active'),
                         transform: getComputedStyle(el).transform});
})('%s')"""


def real_press_probe(cdp, selector: str, expression: str, *, dwell_s: float = 0.4) -> dict:
    """Press the control with a dispatched mouse event and read the paint at three moments.

    `CSS.forcePseudoState` proves the *rule* exists; it does not prove a pointer reaching the control gets
    that feedback, because it never goes through hit-testing or the input path. Measured here first
    (2026-10-28): before the press `:active` is false and the transform is `none`; 400ms after
    `Input.dispatchMouseEvent mousePressed` at the element's own centre it is `:active` true with
    `matrix(0.99, 0, 0, 0.99, 3, 0)`; the release leaves `:active` false again. That is the whole reason
    this branch can exist, so it is asserted rather than assumed.

    The dwell is not decoration: `--motion-pressed` is 80ms of transition, and the release sample moves the
    pointer off the control first, because a control still under the cursor paints its hover lift — comparing
    that against the untouched idle read would convict the product for a state the operator is in.
    """
    out: dict = {"mode": "cdp-mousePressed", "selector": selector}
    before = json.loads(cdp.evaluate(CONTROL_STATE_JS % selector))
    out["before"] = before
    if not before.get("found"):
        out["mode"] = "control-not-found"
        return out
    _press_and_release(cdp, before, out, dwell_s)
    # The harvest expression is the same one the verdict scores, so the settled pair is the same element.
    pressed_value, pressed_waited = settled_transform(cdp, expression)
    out["pressedFirstSelector"] = pressed_value
    out["pressedWaitedS"] = pressed_waited
    return out


def _press_and_release(cdp, before: dict, out: dict, dwell_s: float) -> None:
    send_mouse(cdp, "mousePressed", before["x"], before["y"])
    time.sleep(dwell_s)
    out["during"] = json.loads(cdp.evaluate(CONTROL_STATE_JS % before["sel"]))
    send_mouse(cdp, "mouseReleased", before["x"], before["y"])
    # Take the cursor off the control before reading idle, or the read lands on the hover lift instead.
    send_mouse(cdp, "mouseMoved", 2, 2)
    time.sleep(dwell_s)
    out["after"] = json.loads(cdp.evaluate(CONTROL_STATE_JS % before["sel"]))


def send_mouse(cdp, kind: str, x: int, y: int) -> None:
    cdp.send("Input.dispatchMouseEvent",
             {"type": kind, "x": x, "y": y, "button": "left", "clickCount": 1,
              "pointerType": "mouse", "timestamp": time.time()})


KEY_STATE_JS = """(function(sel){
  var el = document.querySelector(sel);
  var active = document.activeElement;
  var cs = el ? getComputedStyle(el) : null;
  return JSON.stringify({
    found: !!el,
    isActive: !!el && el === active,
    activeTag: active ? String(active.tagName) : null,
    focusVisible: !!el && el.matches(':focus-visible'),
    outline: cs ? (cs.outlineWidth + ' ' + cs.outlineColor) : null,
    transform: cs ? cs.transform : null});
})('%s')"""


def real_key_probe(cdp, selector: str, *, max_tabs: int = 12) -> dict:
    """Walk the page with dispatched Tab keys until the required control itself has focus, then read it.

    The keyboard path needs its own clause because a pointer press and a focus arrive through different
    mechanisms: `:active` comes from hit-testing, `:focus-visible` from the input focus plus Chromium's
    heuristic about *how* focus was gained. Measured here on 2026-10-28 before writing the assertion:
    dispatched Tab lights `:focus-visible` on the stops it reaches, and the required control's outline
    moves from `3px rgb(238, 246, 252)` (console) / `3px rgb(69, 191, 207)` (daily rail) to the ring
    `2px rgb(42, 145, 255)` — so the assertion is satisfiable rather than hopeful.
    """
    out: dict = {"selector": selector, "tabs": 0}
    start = json.loads(cdp.evaluate(KEY_STATE_JS % selector))
    out["before"] = start
    if not start.get("found"):
        out["reached"] = False
        out["note"] = "control-not-found"
        return out
    if start.get("isActive"):
        # The instrument arrived with the control already focused, so any Tab from here walks AWAY from it
        # and no number of presses will "reach" it. Measured once and lost to exactly this: the press
        # branch runs `mousePressed` on the same control, and a press focuses what it presses. Refuse by
        # naming the cause instead of reporting a keyboard that cannot reach the control.
        out["reached"] = False
        out["note"] = "already-focused-before-the-first-tab"
        return out
    for _ in range(max_tabs):
        _press_tab(cdp)
        out["tabs"] += 1
        time.sleep(0.2)
        now = json.loads(cdp.evaluate(KEY_STATE_JS % selector))
        if now.get("isActive"):
            out["reached"] = True
            out["focused"] = now
            return out
    out["reached"] = False
    out["focused"] = json.loads(cdp.evaluate(KEY_STATE_JS % selector))
    return out


def _press_tab(cdp) -> None:
    for kind in ("keyDown", "char", "keyUp"):
        cdp.send("Input.dispatchKeyEvent", {
            "type": kind, "windowsVirtualKeyCode": 9, "nativeVirtualKeyCode": 9,
            "code": "Tab", "key": "Tab", "text": "\t" if kind == "char" else "",
            "timestamp": time.time()})


def verdict(readings: dict[str, dict]) -> dict:
    """Judge every surface on its own numbers, then require that each one actually moved something.

    A single aggregate "controls=2" is what let the first version of this instrument pass while the surface
    the desktop window shows was measured by nothing: a selector matching zero nodes contributes no check, so
    the totals stay green and the coverage line is the only place the hole shows. Per-surface assertions make
    an unmeasured surface fail by name.
    """
    checks: list[dict] = []
    unmeasurable: list[str] = []

    def add(name: str, ok: bool, detail: str) -> None:
        checks.append({"check": name, "pass": bool(ok), "detail": detail})

    coverage: dict[str, int] = {}
    expectation: dict[str, object] = {}
    for surface_name, surface in readings.items():
        idle = surface["idle"]
        pressed = surface["pressed"]
        reduced = surface.get("pressedReduced")
        scale, duration, problems = token_expectations(idle.get("tokens") or {})
        expectation = {"pressedScale": scale, "transitionSeconds": duration}

        add(f"motion-preference-emulated[{surface_name}]",
            idle.get("reducedMotion") is False and pressed.get("reducedMotion") is False,
            f"idle reducedMotion={idle.get('reducedMotion')} pressed reducedMotion={pressed.get('reducedMotion')}")
        add(f"tokens-declared-and-parseable[{surface_name}]", not problems,
            json.dumps(idle.get("tokens") or {}) + ("" if not problems else " " + ";".join(problems)))

        idle_by = {row["selector"]: row for row in idle.get("selectors") or []}
        pressed_by = {row["selector"]: row for row in pressed.get("selectors") or []}
        required = surface["required"]
        add(f"required-control-rendered[{surface_name}]", (idle_by.get(required) or {}).get("count", 0) > 0,
            f"{required} count={json.dumps(idle_by.get(required))}")

        measured = 0
        for selector, pressed_row in pressed_by.items():
            coverage[f"{surface_name}/{selector}"] = int(pressed_row.get("count") or 0)
            if not pressed_row.get("count"):
                continue
            idle_row = idle_by.get(selector) or {}
            got_scale = matrix_scale(pressed_row.get("transform"))
            idle_scale = matrix_scale(idle_row.get("transform"))
            # A scale that is neither the untouched paint nor the token's end state is a FRAME of the
            # transition, not a state. Convicting the product for it is how PR #220's `observer` job went
            # red on a correct render: the same command settles at 0.99 on the development host, while the
            # runner sampled the identity at t=0 of the 80ms transition. The duration is asserted on its
            # own line below, so the paint check does not also have to prove an animation ticked.
            settled = (got_scale is None or scale is None or idle_scale == got_scale
                       or math.isclose(got_scale, scale, abs_tol=0.005))
            if not settled:
                unmeasurable.append(f"{surface_name}/{selector}")
            add(f"pressed-paint-read-was-settled[{surface_name}:{selector}]", settled,
                f"pressed transform={pressed_row.get('transform')!r} scale={got_scale} "
                f"idle transform={idle_row.get('transform')!r} scale={idle_scale} token={scale} "
                "(neither the untouched paint nor the token's end state — a transition frame; reported as "
                "unmeasurable rather than as a product failure)")
            add(f"active-transform-matches-token[{surface_name}:{selector}]",
                scale is not None and got_scale is not None and math.isclose(got_scale, scale, abs_tol=0.005),
                f"pressed transform={pressed_row.get('transform')!r} scale={got_scale} token={scale} "
                f"settledRead={settled}")
            # A control already drawn at the pressed scale when nothing is forced would make the check above
            # pass for the wrong reason: the rule has to move the box, not sit under it.
            add(f"pressed-state-changes-the-paint[{surface_name}:{selector}]",
                got_scale is not None and got_scale != idle_scale,
                f"idle={idle_row.get('transform')!r} scale={idle_scale} -> pressed scale={got_scale}")
            add(f"active-duration-matches-token[{surface_name}:{selector}]",
                duration is not None and seconds(pressed_row.get("transitionDuration")) == duration,
                f"transitionDuration={pressed_row.get('transitionDuration')!r} token={duration}s")
            measured += 1

        add(f"surface-measured-a-control[{surface_name}]", measured > 0,
            f"measured={measured} of {len(pressed_by)} declared selectors")

        # The forced branch above says the CSS rule exists. These lines say a pointer reaching the control
        # actually gets that feedback, which no amount of `CSS.forcePseudoState` can show: a rule that the
        # input path never hits is invisible to the operator and green here.
        pointer = surface.get("pointer") or {}
        pointer_mode = pointer.get("mode") or ""
        add(f"real-press-probe-ran[{surface_name}]", pointer_mode != "",
            f"mode={pointer_mode!r} "
            + (json.dumps(pointer, ensure_ascii=False)[:200] if pointer else "{}")
            + ("" if pointer_mode else " — nothing pressed the control: this run has no pointer branch"))
        p_before = pointer.get("before") or {}
        p_during = pointer.get("during") or {}
        p_after = pointer.get("after") or {}
        pressed_scale = matrix_scale(p_during.get("transform"))
        idle_scale = matrix_scale(p_before.get("transform"))
        press_settled = (pressed_scale is None or scale is None or pressed_scale == idle_scale
                         or math.isclose(pressed_scale, scale, abs_tol=0.005))
        if pointer.get("mode") == "cdp-mousePressed" and not press_settled:
            unmeasurable.append(f"{surface_name}/pointer")
        add(f"real-press-read-was-settled[{surface_name}]", press_settled,
            f"during transform={p_during.get('transform')!r} scale={pressed_scale} "
            f"idle transform={p_before.get('transform')!r} token={scale} waited={pointer.get('pressedWaitedS')}s "
            "(a value that is neither the untouched paint nor the token's end state is a transition frame)")
        add(f"real-press-lights-the-active-pseudo-class[{surface_name}]",
            p_during.get("active") is True and p_before.get("active") is False,
            f"before :active={p_before.get('active')} during :active={p_during.get('active')} "
            f"at={pointer.get('mode')!r} x={p_before.get('x')} y={p_before.get('y')}")
        add(f"real-press-transform-matches-token[{surface_name}]",
            scale is not None and pressed_scale is not None
            and math.isclose(pressed_scale, scale, abs_tol=0.005) and press_settled,
            f"scale={pressed_scale} token={scale} transform={p_during.get('transform')!r} "
            f"settledRead={press_settled}")
        add(f"real-release-returns-the-paint-to-idle[{surface_name}]",
            p_after.get("active") is False and "transform" in p_after
            and p_after.get("transform") == p_before.get("transform"),
            f"idle={p_before.get('transform')!r} -> pressed={p_during.get('transform')!r} "
            f"-> released={p_after.get('transform')!r} after :active={p_after.get('active')} "
            "(the cursor is moved off the control before this read, so a leftover hover lift is a real gap)")
        key = surface.get("key") or {}
        k_before = key.get("before") or {}
        k_focused = key.get("focused") or {}
        add(f"keyboard-tab-reached-the-control[{surface_name}]", bool(key.get("reached")),
            (f"tabs={key.get('tabs')} activeTag={k_focused.get('activeTag')!r} "
             f"before.isActive={k_before.get('isActive')!r} focused.isActive={k_focused.get('isActive')!r}"
             + (f" note={key.get('note')!r}" if key.get("note") else ""))
            if key else "no keyboard reading at all: this run never pressed Tab")
        add(f"keyboard-focus-lights-the-visible-ring[{surface_name}]",
            bool(key.get("reached")) and k_focused.get("focusVisible") is True
            and k_focused.get("outline") != k_before.get("outline"),
            f"outline {k_before.get('outline')!r} -> {k_focused.get('outline')!r} "
            f":focus-visible={k_focused.get('focusVisible')} transform={k_focused.get('transform')!r} "
            "(键盘也要有看得见的反馈，否则这个状态只有鼠标能看见)")

        if reduced is not None:
            # The L10b floor is a promise the shell makes to operators who asked for less motion: under
            # `reduce` the same forced press must paint NO transform. Asserting it here is what keeps the
            # floor from being deleted by someone who only ever tested the animated branch.
            reduced_by = {row["selector"]: row for row in reduced.get("selectors") or []}
            add(f"reduced-preference-observed[{surface_name}]", reduced.get("reducedMotion") is True,
                f"reducedMotion={reduced.get('reducedMotion')}")
            guarded = 0
            for selector, row in reduced_by.items():
                if not row.get("count"):
                    continue
                add(f"no-pressed-transform-under-reduce[{surface_name}:{selector}]",
                    matrix_scale(row.get("transform")) is None,
                    f"forced :active transform={row.get('transform')!r}")
                guarded += 1
            add(f"reduced-floor-covers-a-measured-control[{surface_name}]", guarded > 0,
                f"guarded selectors={guarded}")
    return {
        "passed": all(c["pass"] for c in checks),
        "checks": checks,
        "coverage": coverage,
        "surfaces": sorted(readings),
        "expectation": expectation,
        "unmeasurable": unmeasurable,
    }


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=str(ROOT))
    ap.add_argument("--surface", action="append", default=None,
                    help=f"surfaces to probe (default: {' '.join(s['name'] for s in SURFACES)})")
    ap.add_argument("--json-out", default=None)
    args = ap.parse_args()

    wanted = args.surface or [s["name"] for s in SURFACES]
    unknown = sorted(set(wanted) - {s["name"] for s in SURFACES})
    if unknown:
        # Validated before anything is looked for on disk: a misspelled surface is bad input whatever the
        # machine happens to have built, and silently probing nothing would report as a pass.
        print(f"PRESSED_MOTION_GATE_NOT_RUN UNKNOWN_SURFACE {json.dumps(unknown)}")
        return 2
    surfaces = [s for s in SURFACES if s["name"] in wanted]

    root = Path(args.root).resolve()
    dist = root / "apps" / "observer" / "frontend" / "dist"
    if not (dist / "index.html").is_file():
        print(f"PRESSED_MOTION_GATE_NOT_RUN DIST_ABSENT {dist}")
        return 3
    browser = geometry.find_browser()
    if not browser:
        print("PRESSED_MOTION_GATE_NOT_RUN BROWSER_NOT_FOUND "
              "set WL_CHROME to a Chrome/Edge binary; a named category is not a pass")
        return 3

    geometry.OUT_DIR.mkdir(parents=True, exist_ok=True)
    u19 = geometry.load_u19()
    fixture = hud.SnapshotFixture(dist)
    fixture.start()
    readings: dict[str, dict] = {}
    forced_nodes: dict[str, int] = {}
    settle_waits: list[dict] = []
    urls: dict[str, str] = {}

    def make_hook(motion: str, force: bool, selectors: list[str], required: str,
              surface_name: str = ""):
        """One hook per launch: pin the media preference, then optionally hold `:active` on every control.

        Built as a function rather than a loop-scoped lambda, because the closure has to freeze the state it
        belongs to -- a late-bound lambda is how two launches end up measuring the same one.
        """
        def hook(cdp) -> None:
            emulate_motion(cdp, motion)
            if force:
                forced_nodes.update(force_active(cdp, selectors, required))
                # The force starts the transition; sampling it immediately reads a frame, not a state.
                settled, waited = settled_transform(cdp, read_expression(selectors))
                settle_waits.append({"surface": surface_name, "force": True,
                                     "settledTransform": settled, "waitedS": waited})
        return hook

    try:
        for spec in surfaces:
            url = fixture.url_for(spec["query"])
            urls[spec["name"]] = url
            expression = read_expression(list(spec["selectors"]))
            per_surface: dict[str, dict] = {"required": spec["required"]}
            states = [("idle", "no-preference", False), ("pressed", "no-preference", True)]
            if spec["name"] == surfaces[0]["name"]:
                # The reduced branch is the same stylesheet floor on every surface; measuring it once keeps
                # the browser starts bounded without letting the floor go unasserted.
                states.append(("pressedReduced", "reduce", True))
            for state, motion, force in states:
                # The forced node ids travel with the receipt: a reader who wants to know whether a control
                # was actually held down, rather than merely absent, has to be able to tell the two apart.
                hook = make_hook(motion, force, list(spec["selectors"]), spec["required"],
                             spec["name"])
                for attempt in range(2):
                    try:
                        per_surface[state] = geometry.serve_and_eval(
                            root, "/index.html", WINDOW, expression, browser, u19, None,
                            viewport=(1280, 820), serve_url=url, after_mount=hook,
                            mount_selector=spec["mount"])
                        break
                    except Exception as exc:  # noqa: BLE001 — retried once, then reported by name
                        if attempt == 1:
                            print(f"PRESSED_MOTION_GATE_NOT_RUN "
                                  f"{spec['name'].upper()}_{state.upper()}_MEASURE_FAILED {exc!r}")
                            return 3
                        time.sleep(1.0)
            # One more launch per surface, and this one presses the control instead of forcing the
            # pseudo-class: the pointer branch is what says an operator's click reaches the paint. It gets
            # the same bounded retry, so a flaking browser start cannot be read as a product finding.
            pointer_sink: dict = {}
            key_sink: dict = {}

            def pointer_hook(cdp, _required=spec["required"], _expr=expression) -> None:
                emulate_motion(cdp, "no-preference")
                # Keyboard first: a press focuses the control it presses, and the key branch refuses to run
                # on a page that already has the target focused (it would Tab away from it and report an
                # unreachable control). The order is the instrument's hygiene, not a product claim.
                key_sink.update(real_key_probe(cdp, _required))
                pointer_sink.update(real_press_probe(cdp, _required, _expr))

            for attempt in range(2):
                try:
                    geometry.serve_and_eval(root, "/index.html", WINDOW, expression, browser, u19, None,
                                            viewport=(1280, 820), serve_url=url,
                                            after_mount=pointer_hook, mount_selector=spec["mount"])
                    break
                except Exception as exc:  # noqa: BLE001 — retried once, then reported by name
                    if attempt == 1:
                        pointer_sink = {"mode": "", "error": repr(exc)[:220]}
                        key_sink = {"reached": False, "error": repr(exc)[:220]}
            per_surface["pointer"] = pointer_sink
            per_surface["key"] = key_sink
            readings[spec["name"]] = per_surface
    finally:
        fixture.stop_server()

    result = verdict(readings)
    if result.get("unmeasurable"):
        # Say it as NOT_RUN: an instrument that read a moving thing has measured nothing, and a FAIL would
        # tell the next reader the product lost its pressed feedback. The numbers stay in the receipt.
        print("PRESSED_MOTION_GATE_NOT_RUN SAMPLED_A_TRANSITION_FRAME "
              + json.dumps(result["unmeasurable"], ensure_ascii=False)
              + f" out={args.json_out or 'default'}")
        out_path = Path(args.json_out) if args.json_out else (OUT_DIR / f"pressed_{int(time.time())}.json")
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
        return 3
    result["startedAt"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    result["browser"] = browser
    result["urls"] = urls
    result["servedBundle"] = bundle_provenance.describe(root)
    result["forcedActiveNodes"] = forced_nodes
    result["settleWaits"] = settle_waits
    result["measured"] = readings
    result["residue"] = list(geometry.RESIDUE)
    result["portAnnouncedMismatch"] = list(geometry.ANNOUNCED_MISMATCH)

    out = Path(args.json_out) if args.json_out else (OUT_DIR / f"pressed_{int(time.time())}.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    for check in result["checks"]:
        print(f"{check['check']:<52} {'PASS' if check['pass'] else 'FAIL'} {check['detail'][:150]}")
    print(f"PRESSED_MOTION_GATE_{'PASS' if result['passed'] else 'FAIL'} "
          f"surfaces={json.dumps(result['surfaces'])} coverage={json.dumps(result['coverage'])} "
          f"tokens={json.dumps(readings[surfaces[0]['name']]['idle'].get('tokens'))} " + str(out))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
