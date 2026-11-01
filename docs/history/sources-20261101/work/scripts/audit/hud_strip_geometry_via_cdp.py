#!/usr/bin/env python
"""HUD narrow-strip geometry gate — measure the declared 150x480 strip in a real browser, PASS or FAIL.

The strip's shape checks were written as `.project-local/runs/cl10/hud_narrow_probe.py`, in the
project's designated evidence area. That probe found real defects — a CJK label shattered one character
per line at 150px, and the hover state pushed the pinned footer to y=874 inside a 480px window — and it
went green again after each fix. Nothing in CI re-runs it, so the next commit may re-break either shape
silently. This file moves the load-bearing judgements into tracked, executed code.

Division of labour, the same as the topbar and legibility gates:
  * the browser harvests RAW facts only — boxes, per-line box widths, font sizes, painted strings;
  * `verdict()` holds every threshold and every judgement, so it is unit-testable without a browser and
    falsifiable with a planted fault (see `tests/ci/test_hud_strip_geometry_gate.py`). The evidence probe
    decided "this label is shattered" inside its own JS, and a judgement made in JS cannot be tested at
    all — that is the whole difference between an instrument and a gate.

What it does not judge: the 12px type floor and the AA contrast ratio. Both standards are owned by
`scripts/audit/text_legibility_via_cdp.py`, which since 2026-10-25 sweeps these same three shell surfaces
through `--shell-surfaces`. This file used to assert the floor itself; two gates reading one rule means two
exception lists and two thresholds to keep in step, which is how standards rot, so the duplicate is gone and
geometry is the single thing claimed here.

What it measures against: the built `dist`, served from ONE loopback origin that also answers
`GET /api/v1/snapshot` with the declared fixture below. A fixture is deliberate, not a shortcut: the
strip's geometry depends on how many tool rows the snapshot carries, so a gate bound to today's live
ledger reds when the data changes and greens when the layout breaks. The live-data desktop readback
stays where it belongs (real sidecar, real window); this gate answers one question — does the strip hold
its declared shape at a declared data shape — and says in every receipt which data shape that was.

`--snapshot-file` replaces the fixture payload with a captured real snapshot, so the same judgements can
be run over the bytes the machine actually produces without rewriting any threshold. The readiness marker
then comes from the served payload rather than from the fixture's first card, and the receipt reports
`data=captured-snapshot(sha256=…)` with the payload's real counts. The fixture stays the default and stays
what CI runs, because a deterministic shape is what makes a geometry gate re-runnable.

Exit: 0 HUD_STRIP_GATE_PASS, 1 HUD_STRIP_GATE_FAIL, 2 bad input, 3 HUD_STRIP_GATE_NOT_RUN.
"""
from __future__ import annotations

import argparse
import hashlib
import http.server
import importlib.util
import json
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "audit"))
import bundle_provenance  # noqa: E402  # every receipt names the bytes the browser loaded
# The 12px floor belongs to the legibility gate; this gate owns it only for the mini settings block, which
# no other surface ever renders (the block is React state behind the footer gear).
from text_legibility_via_cdp import FLOOR_PX as TYPE_FLOOR_PX  # noqa: E402

GEOMETRY_SCRIPT = ROOT / "scripts" / "audit" / "topbar_geometry_via_cdp.py"
DIST = ROOT / "apps" / "observer" / "frontend" / "dist"
OUT_DIR = ROOT / ".project-local" / "runs" / "hud-strip-gate"

# The declared window shapes, read from `apps/observer/src-tauri/tauri.conf.json` and bound to it by a
# test, never restated from memory. `--window-size` sizes the OUTER window and Chrome clamps a too-narrow
# one, so every surface is measured through a CDP device-metrics override at its own declared size.
STRIP = (150, 480)
PANEL = (440, 680)
DAILY = (1280, 820)

H01_SECTION = 'section[aria-label="工具额度窄面板"]'
SUMMARY = '[aria-label="悬停摘要"]'
# The gear in the strip footer opens the mini settings block, and the block is React state -- it is in no
# URL, so the only way a browser gate can see it is to press the button. Until 2026-10-28 no gate did,
# which meant the panel's geometry, its footer collision and its wrapping were judged by nobody: the strip
# fixtures counted the gear as a control and never opened what it controls.
SETTINGS_BUTTON = 'button[aria-label="HUD 设置"]'
SETTINGS_PANEL = '[data-landmark="hud-settings"]'
# The lit ring used to be identified by the literal amber attribute the strip painted (`AMBER =
# "#FBBF24"`). Since 2026-10-27 the strip takes its colours from the --daily-* theme tokens, so that
# string can never appear in the source again — and a gate that compared an attribute against a hex
# would convict a correct render. The judgement is unchanged ("the hovered row is the only one lit in
# the warning colour"), but it is now read two ways: the element states which ring ROLE it plays, and
# the RESOLVED stroke is compared against the idle rows' resolved stroke. Colour identity is therefore
# still measured in the browser, per theme, instead of being assumed from a literal.
ACTIVE_RING = "active"
IDLE_RING = "idle"

# The condition the page must satisfy before a harvest counts as measuring the populated surface. The
# frame mounts on the very first render, which happens while the snapshot is still in flight, so a probe
# that reads as soon as `[data-hud-frame]` exists can measure the pre-snapshot shape — with no adapter
# rows there is nothing to hover and H03 says 未连接工具, and every geometry claim would then be about a
# surface the product does not ship. This is the cold-runner failure the topbar gate already documents
# for its own first session; the budget is the runner's boot, not the development host's.
#
# The two probes differ because the two states paint different things. This one exists because the
# obvious choice was wrong: H01 renders initials (`CO`, `HE`) and 额度 UNKNOWN, never the tool name, so
# waiting for a name on the strip would time out on a perfectly healthy render — the same
# "names appear in the body" mistake the register already records once for this surface.
FIXTURE_MARKER = "Codex"
RING_ROW_PROBE = "document.querySelectorAll(H01 + ' li circle').length > 0"
MARKER_PROBE = "painted().indexOf(%s) !== -1" % json.dumps(FIXTURE_MARKER, ensure_ascii=False)


def marker_for(payload: dict) -> str:
    """The tool name the h03/h04 headers paint: the displayName of the first adapter card served.

    `FIXTURE_MARKER` above is only ever right for the fixture, because `Codex` is the fixture's first
    card. Run the same judgements over a real snapshot and the first card is whatever the live registry
    puts first — on the 2026-10-28 ledger that is Hermes — so a literal marker waits out the whole
    readiness budget for a name the header never paints, and convicts a healthy render. The literal stays
    as the fixture's declared shape (and is pinned against the fixture by a test); a served payload gets
    its own marker from here.
    """
    cards = payload.get("adapterCapabilities") or []
    return str(cards[0]["displayName"]) if cards else ""


def marker_probe_for(payload: dict) -> str:
    return "painted().indexOf(%s) !== -1" % json.dumps(marker_for(payload), ensure_ascii=False)
READY_BUDGET_MS = 24000
READY_POLL_MS = 400

# One entry per rendered surface. `kind` selects which assertion families apply; `state` is the HUD
# state the URL declares, which the render has to answer with (the state travels in the URL and in
# nothing else — web storage is forbidden in this product); `readyProbe` is the JS condition the surface
# must satisfy before being measured, or None when its claims do not depend on snapshot data.
SURFACES: list[dict] = [
    {"name": "strip-h01", "query": "surface=hud", "size": STRIP, "kind": "strip", "state": "h01",
     "readyProbe": RING_ROW_PROBE, "readyWhy": "an adapter ring row is painted"},
    {"name": "strip-h02", "query": "surface=hud", "size": STRIP, "kind": "strip", "state": "h01",
     "hover": True, "readyProbe": RING_ROW_PROBE, "readyWhy": "an adapter ring row is painted"},
    {"name": "strip-h03", "query": "surface=hud&hs=h03", "size": STRIP, "kind": "strip", "state": "h03",
     "readyProbe": MARKER_PROBE, "readyWhy": f"the fixture tool {FIXTURE_MARKER!r} is named in the header"},
    {"name": "strip-h04", "query": "surface=hud&hs=h04", "size": STRIP, "kind": "strip", "state": "h04",
     "readyProbe": MARKER_PROBE, "readyWhy": f"the fixture tool {FIXTURE_MARKER!r} is named in the header"},
    {"name": "strip-settings", "query": "surface=hud", "size": STRIP, "kind": "strip", "state": "h01",
     "openSettings": True, "readyProbe": RING_ROW_PROBE,
     "readyWhy": "an adapter ring row is painted (the gear lives in the footer of the same strip)"},
    {"name": "panel-h01", "query": "view=compact&layout=compact&shell=tauri&hud=daily",
     "size": PANEL, "kind": "panel", "state": "h01",
     "readyProbe": RING_ROW_PROBE, "readyWhy": "an adapter ring row is painted"},
    {"name": "daily-home", "query": "surface=daily&shell=tauri", "size": DAILY, "kind": "daily",
     "state": None, "readyProbe": None, "readyWhy": None},
    # D2's screen needs its own entry: `scripts/audit/text_legibility_via_cdp.py` enumerates the surfaces it
    # sweeps from this list, so a screen absent here gets no contrast or line-break measurement in either
    # theme. The rail label is five CJK glyphs and the five carried cards bring their own wrapping.
    {"name": "daily-governance", "query": "surface=daily&shell=tauri&dv=governance", "size": DAILY,
     "kind": "daily", "state": None, "readyProbe": None, "readyWhy": None},
]

_SURFACE_KINDS = {str(s["name"]): str(s["kind"]) for s in SURFACES}


def resolve_surfaces(payload: dict) -> list[dict]:
    """The declared surfaces, with the marker probes re-derived for the payload that will be served.

    Only the surfaces whose readiness condition is a tool name change; the ring-row and no-probe surfaces
    come back as they were. A new surface that needs a name has to join this rule, not grow a literal.
    """
    probe = marker_probe_for(payload)
    name = marker_for(payload)
    resolved: list[dict] = []
    for spec in SURFACES:
        if spec.get("readyProbe") == MARKER_PROBE:
            spec = {**spec, "readyProbe": probe,
                    "readyWhy": f"the served tool {name!r} is named in the header"}
        resolved.append(spec)
    return resolved

MOUNT_SELECTOR = {
    "strip": "[data-hud-frame]",
    "panel": ".app.app-compact [data-hud-frame]",
    "daily": "[data-shell]",
}

# A leaf label of 2-8 characters whose widest line box is no bigger than this multiple of its own font
# size is not "wrapped", it is shattered: CJK breaks between any two characters, so a squeezed row puts
# one glyph on each line. 1.6 keeps a genuine two-word wrap (which is what flex-wrap is for) passing
# while convicting 更/新/时/间 on four lines.
CHAR_WRAP_LINE_MULTIPLE = 1.6
QUOTA_ROW_COUNT = 3           # the reference H03 panel's three quota dimensions
QUOTA_TRACK_MIN_W = 8.0       # a progress track, as opposed to the 6px status dot beside it
QUOTA_TRACK_MAX_H = 6.0
CONTROL_EDGE_TOLERANCE_PX = 2.0
VIEWPORT_TOLERANCE_PX = 1.0

# --------------------------------------------------------------------------- measurement (facts only)

MEASURE_JS = r"""
(async () => {
  const HOVER = __HOVER__;
  const READY = () => (__READY_PROBE__);
  const BUDGET_MS = __BUDGET_MS__;
  const POLL_MS = __POLL_MS__;
  const H01 = __H01__;
  const SUMMARY = __SUMMARY__;
  const OPEN_SETTINGS = __OPEN_SETTINGS__;
  const SETTINGS_BUTTON = __SETTINGS_BUTTON__;
  const SETTINGS_PANEL = __SETTINGS_PANEL__;
  // What the driver actually did before this expression ran: null when nothing was placed, else the facts
  // `place_real_pointer` stashed on the page (mode, coordinates, the idle styles it measured). Read from
  // the page rather than substituted, because the harvest expression is built BEFORE the pointer lands —
  // substituting it would freeze a null in place of what the session really did.
  const POINTER = window.__HUD_POINTER_FACTS__ || null;
  const r1 = (n) => Math.round(n * 10) / 10;
  const painted = () => (document.body && document.body.innerText) || '';
  // Wait for the snapshot to reach the surface BEFORE anything is measured, and before the hover is
  // dispatched: dispatching on the pre-snapshot row finds a `li` with no handlers, which then reads as
  // a successful dispatch that revealed nothing.
  let readyWaitMs = 0;
  if (!READY()) {
    const t0 = performance.now();
    while (!READY()) {
      if (performance.now() - t0 > BUDGET_MS) break;
      await new Promise((res) => setTimeout(res, POLL_MS));
    }
    readyWaitMs = Math.round(performance.now() - t0);
  }
  const ready = READY();
  const box = (el) => {
    const r = el.getBoundingClientRect();
    return {left: r1(r.left), right: r1(r.right), top: r1(r.top), bottom: r1(r.bottom),
            width: r1(r.width), height: r1(r.height)};
  };
  const de = document.documentElement;
  let hoverDispatch = 'not-requested';
  if (HOVER) {
    // The pointer is placed by the DRIVER, from here: a synthetic `li.dispatchEvent(new
    // MouseEvent('mouseover'))` reaches React's onMouseEnter but cannot light a CSS pseudo-class, so the
    // whole hover language of the stylesheet stayed unmeasured while a JS-only affordance looked green.
    // `place_real_pointer` sends CDP `Input.dispatchMouseEvent` before this expression runs, and the row
    // styles read below are whatever the real pointer produced. If the driver placed nothing, this
    // surface reports 'no-pointer' and the hover checks fail instead of describing an untested page.
    hoverDispatch = (POINTER && POINTER.mode === 'mouseMoved') ? 'cdp-mouseMoved' : 'no-pointer';
    if (hoverDispatch === 'cdp-mouseMoved') {
      await new Promise((res) => setTimeout(
        () => requestAnimationFrame(() => setTimeout(res, 150)), 60));
    }
  }

  let settingsDispatch = 'not-requested';
  const PRESS = window.__HUD_SETTINGS_PRESS__ || null;
  if (OPEN_SETTINGS) {
    const gear = document.querySelector(SETTINGS_BUTTON);
    if (!gear) settingsDispatch = 'no-gear-button';
    else if (!PRESS || PRESS.mode !== 'mousePressed') {
      // The probe could not press it (covered, or outside the window). Say which, rather than falling back
      // to a synthetic click that would succeed for the wrong reason.
      settingsDispatch = (PRESS && PRESS.mode) || 'no-real-press';
    } else {
      settingsDispatch = 'cdp-mousePressed';
      await new Promise((res) => requestAnimationFrame(() => setTimeout(res, 120)));
    }
  }

  const out = {
    hoverDispatch,
    pointer: POINTER,
    settingsDispatch,
    settingsPress: PRESS,
    settings: (() => {
      const el = document.querySelector(SETTINGS_PANEL);
      if (!el) return null;
      const gear = document.querySelector(SETTINGS_BUTTON);
      const close = [...el.querySelectorAll('button')][0];
      const texts = [...el.querySelectorAll('p,button,span')].filter((n) => (n.innerText || '').trim());
      return {...box(el),
              text: (el.innerText || '').slice(0, 300),
              expanded: gear ? gear.getAttribute('aria-expanded') : null,
              insideFrame: !!el.closest('[data-hud-frame]'),
              closeText: close ? (close.innerText || '').trim() : null,
              closeRect: close ? box(close) : null,
              fontSizes: texts.map((n) => parseFloat(getComputedStyle(n).fontSize) || 0),
              controlCount: el.querySelectorAll('button').length};
    })(),
    ready, readyWaitMs,
    readyProbe: __READY_WHY__,
    readyBudgetMs: BUDGET_MS,
    viewport: {clientW: de.clientWidth, clientH: de.clientHeight,
               scrollW: de.scrollWidth, scrollH: de.scrollHeight,
               innerW: window.innerWidth, innerH: window.innerHeight, dpr: window.devicePixelRatio},
    hudFrame: document.querySelector('[data-hud-frame]')?.getAttribute('data-hud-frame') ?? null,
    hudState: document.querySelector('[data-hud-state]')?.getAttribute('data-hud-state') ?? null,
    shell: document.querySelector('[data-shell]')?.getAttribute('data-shell') ?? null,
    // Every interactive element with its raw box and its raw visibility. Which of these a user can
    // actually reach is decided in Python: the action band keeps an off-screen `.action-sizer`
    // (visibility:hidden, pointer-events:none) whose boxes would otherwise be convicted as controls
    // pushed to x=-9999, and that distinction is a judgement, not a measurement.
    controls: [...document.querySelectorAll('button,a,input,select')].map((el) => {
      const b = box(el);
      const cs = getComputedStyle(el);
      return {name: ((el.getAttribute('aria-label') || el.textContent || el.className || '')
                     .trim().slice(0, 28)),
              visibility: cs.visibility, display: cs.display, ...b};
    }).slice(0, 80),
    // Short leaf labels that occupy more than one line box, with the text and width OF EACH LINE.
    // Line widths alone cannot tell a shattered CJK label from a legitimate break after a number, so
    // the harvest keeps which characters landed on which line and Python does the convicting.
    // The LINE BOXES are the platform's own (a Range over the whole label); a single character's rect
    // is only used to decide which box it fell in. Grouping by character top instead would split one
    // line into several, because a digit's glyph box sits higher than the CJK beside it — and a label
    // then looks shattered when nothing is. Characters are located through their own text node, since
    // JSX turns `{n} 个已注册项目` into TWO text nodes and reading only `firstChild` drops every
    // interpolated count from the census.
    labelLines: (() => {
      const found = [];
      for (const el of document.querySelectorAll('dt, dd, span, button, p, h2')) {
        if (el.children.length) continue;
        if (!el.getClientRects().length) continue;
        const nodes = [...el.childNodes].filter((n) => n.nodeType === 3 && n.textContent);
        if (!nodes.length) continue;
        const chars = [];
        for (const node of nodes) {
          for (let i = 0; i < node.textContent.length; i++) chars.push({node, offset: i});
        }
        const txt = chars.map((c) => c.node.textContent[c.offset]).join('').trim();
        if (txt.length < 2 || txt.length > 8) continue;
        const whole = document.createRange();
        whole.selectNodeContents(el);
        const lineBoxes = [...whole.getClientRects()].filter((r) => r.width > 0 && r.height > 0);
        if (lineBoxes.length < 2) continue;
        const lineOf = (r) => {
          const centre = r.top + r.height / 2;
          const i = lineBoxes.findIndex((b) => centre >= b.top - 1 && centre <= b.bottom + 1);
          return i === -1 ? lineBoxes.length : i;
        };
        const groups = [];
        chars.forEach((c, i) => {
          const rg = document.createRange();
          rg.setStart(c.node, c.offset);
          rg.setEnd(c.node, c.offset + 1);
          const last = groups[groups.length - 1];
          const index = lineOf(rg.getBoundingClientRect());
          if (!last || last.line !== index) groups.push({line: index, from: i, to: i});
          else last.to = i;
        });
        found.push({
          text: txt, fontSize: parseFloat(getComputedStyle(el).fontSize) || 0,
          lines: groups.map((g) => {
            // Measure the group's glyphs, not its trailing whitespace: 「认 」 would otherwise report
            // a wider line than the character that actually sits on it.
            let from = g.from, to = g.to;
            while (from <= to && /\s/.test(chars[from].node.textContent[chars[from].offset])) from += 1;
            while (to >= from && /\s/.test(chars[to].node.textContent[chars[to].offset])) to -= 1;
            if (from > to) return {text: '', width: 0};
            const a = chars[from], b = chars[to];
            const rg = document.createRange();
            rg.setStart(a.node, a.offset);
            rg.setEnd(b.node, b.offset + 1);
            return {text: chars.slice(from, to + 1).map((c) =>
                      c.node.textContent[c.offset]).join(''),
                    width: r1(rg.getBoundingClientRect().width)};
          }),
        });
      }
      return found.slice(0, 40);
    })(),
    h01: (() => {
      const el = document.querySelector(H01);
      return el ? {rect: box(el), text: (el.innerText || '').slice(0, 600)} : null;
    })(),
    // Which clients the panel actually drew, read off the rows themselves, plus the whole painted string.
    // The fixture puts a `vcs_host` card second in the list, so if the strip ever maps over every card
    // again that name appears here rather than being hidden behind the row cap.
    agentMarks: [...document.querySelectorAll('[data-hud-agent]')]
      .map((n) => n.getAttribute('data-hud-agent')),
    // Strip rows as painted: which carry a ring, which ring colour, which one holds the summary.
    // `stroke` is the RESOLVED paint (an attribute holding var(--daily-…) is not a colour, and the
    // whole point of the token pass is that the colour a user sees depends on the live theme), and
    // `ringRole` is the element's own statement of which role that ring plays.
    rows: [...document.querySelectorAll(H01 + ' li')].map((li) => {
      const c = li.querySelector('circle');
      const cs = getComputedStyle(li);
      return {hasRing: !!c,
              stroke: c ? (getComputedStyle(c).stroke || c.getAttribute('stroke')) : null,
              ringRole: c ? c.getAttribute('data-ring-role') : null,
              strokeWidth: c ? c.getAttribute('stroke-width') : null,
              hasSummary: !!li.querySelector(SUMMARY),
              // The pseudo-class state the real pointer produced, read from the element itself. This is
              // the gate proving its own input path: a synthetic dispatch leaves it false forever, and a
              // pointer that missed the row leaves it false too, so neither can pass silently.
              isHovered: li.matches(':hover'),
              // The stylesheet's own hover language, reported whether or not this surface has one. The
              // 2026-10-28 measurement is that the narrow strip ships NO CSS `:hover` rule on these rows
              // (idle transform `none` stays `none` under a pointer that demonstrably lights an injected
              // rule), so the numbers are evidence of that gap rather than a passing claim.
              style: {transform: cs.transform, borderTopColor: cs.borderTopColor,
                      backgroundColor: cs.backgroundColor}};
    }),
    summary: (() => {
      const el = document.querySelector(SUMMARY);
      if (!el) return null;
      return {...box(el),
              insideLi: !!el.closest('li'),
              insideH01Row: !!el.closest(H01),
              // The nearest scrollable ancestor, so "below the fold" can be told apart from
              // "reachable by scrolling" in Python rather than in this script.
              scrollerOverflow: (() => {
                for (let a = el; a; a = a.parentElement) {
                  if (/(auto|scroll)/.test(getComputedStyle(a).overflowY)) {
                    return Math.round(a.scrollHeight - a.clientHeight);
                  }
                }
                return null;
              })()};
    })(),
    switcherButtons: document.querySelectorAll('[aria-label="HUD 状态切换"] button').length,
    switcherRect: (() => {
      const el = document.querySelector('[aria-label="HUD 状态切换"]');
      return el ? box(el) : null;
    })(),
    dragRegions: document.querySelectorAll('[data-tauri-drag-region]').length,
    footer: (() => {
      const el = document.querySelector('[data-landmark="hud-footer"]');
      return el ? box(el) : null;
    })(),
    // H03's three quota rows, raw: painted text plus every aria-hidden box in the row. Which box is a
    // progress track and which is a status dot is decided by geometry in Python.
    quotaRows: (() => {
      const box_ = document.querySelector('[data-landmark="h03-quota-rows"]');
      if (!box_) return null;
      return [...box_.children].map((row) => ({
        text: (row.textContent || '').trim(),
        boxes: [...row.querySelectorAll('[aria-hidden="true"]')].map((s) => {
          const b = s.getBoundingClientRect();
          return {w: r1(b.width), h: r1(b.height)};
        }),
      }));
    })(),
    nav: [...document.querySelectorAll('nav[aria-label="主导航"] button')].map((b) => ({
      label: (b.innerText || '').trim(), rect: box(b),
    })),
    bodyText: (document.body.innerText || '').slice(0, 1500),
    // D2: the daily screen mounts professional views, and a professional view brings its own page-level
    // header. Which title is on top is a painted-size question, not a markup question -- jsdom reports no
    // cascade for a bundled stylesheet -- so it is measured here, off the rendered boxes.
    carriedHeadings: (() => {
      const root = document.querySelector('[data-landmark="daily-governance"]');
      if (!root) return null;
      const size = (el) => parseFloat(getComputedStyle(el).fontSize) || 0;
      const shown = (el) => {
        const r = el.getBoundingClientRect();
        return r.height > 0 && r.width > 0 && getComputedStyle(el).display !== 'none';
      };
      const page = root.querySelector('h1');
      return {
        page: page ? {text: (page.innerText || '').trim(), size: size(page)} : null,
        cards: [...root.querySelectorAll('[data-carried]')].map((card) => ({
          id: card.getAttribute('data-carried'),
          headings: [...card.querySelectorAll('h1,h2,h3,h4')].filter(shown).map((h) => ({
            tag: h.tagName.toLowerCase(), size: size(h),
            text: (h.innerText || '').trim().slice(0, 24),
          })),
        })),
      };
    })(),
  };
  return JSON.stringify(out);
})()
"""


def expression_for(surface: dict) -> str:
    """Substitute the selectors, the hover flag and the readiness probe, so the JS holds no product
    knowledge of its own.

    `ensure_ascii=False` keeps the Chinese aria labels readable in the expression that is actually sent
    to the page; the escaped form works but nobody reviewing a failure can read it.
    """
    probe = surface.get("readyProbe")
    return (MEASURE_JS
            .replace("__HOVER__", "true" if surface.get("hover") else "false")
            .replace("__READY_PROBE__", probe if probe else "true")
            .replace("__READY_WHY__", json.dumps(surface.get("readyWhy") or "no data condition",
                                                 ensure_ascii=False))
            .replace("__BUDGET_MS__", str(READY_BUDGET_MS))
            .replace("__POLL_MS__", str(READY_POLL_MS))
            .replace("__H01__", json.dumps(H01_SECTION, ensure_ascii=False))
            .replace("__SUMMARY__", json.dumps(SUMMARY, ensure_ascii=False))
            .replace("__OPEN_SETTINGS__", "true" if surface.get("openSettings") else "false")
            .replace("__SETTINGS_BUTTON__", json.dumps(SETTINGS_BUTTON, ensure_ascii=False))
            .replace("__SETTINGS_PANEL__", json.dumps(SETTINGS_PANEL, ensure_ascii=False)))


# --------------------------------------------------------------------------- the real pointer (CL-16 step 2)
#
# Why this exists at all: `li.dispatchEvent(new MouseEvent('mouseover'))` is what the hover surfaces used
# to do, and React's onMouseEnter answers it — so the JS half of the affordance was measured while the CSS
# half (`:hover` rules in the shipped skins) was never reachable by the instrument at all. A stylesheet
# regression that removed every hover rule would have kept this gate green. A CDP `Input.dispatchMouseEvent`
# is a real pointer to the browser: it lights the pseudo-class, and it also drives the React handler, so
# one path now covers both.

POINTER_ARM_JS = """
(async () => {
  const READY = () => (__READY_PROBE__);
  const BUDGET_MS = __BUDGET_MS__;
  const POLL_MS = __POLL_MS__;
  const H01 = __H01__;
  let waitedMs = 0;
  if (!READY()) {
    const t0 = performance.now();
    while (!READY()) {
      if (performance.now() - t0 > BUDGET_MS) break;
      await new Promise((res) => setTimeout(res, POLL_MS));
    }
    waitedMs = Math.round(performance.now() - t0);
  }
  const rows = [...document.querySelectorAll(H01 + ' li')];
  const styleOf = (el) => {
    const cs = getComputedStyle(el);
    return {transform: cs.transform, borderTopColor: cs.borderTopColor,
            backgroundColor: cs.backgroundColor};
  };
  if (rows.length === 0) {
    return JSON.stringify({ready: READY(), waitedMs, mode: 'no-row', idle: [], target: null});
  }
  const r = rows[0].getBoundingClientRect();
  if (r.width < 2 || r.height < 2) {
    return JSON.stringify({ready: READY(), waitedMs, mode: 'row-unpainted',
                           idle: rows.map(styleOf), target: null});
  }
  return JSON.stringify({ready: READY(), waitedMs, mode: 'row-found',
    target: {x: Math.round(r.left + r.width / 2), y: Math.round(r.top + r.height / 2),
             width: Math.round(r.width), height: Math.round(r.height)},
    idle: rows.map(styleOf)});
})()
"""


def arm_expression_for(surface: dict) -> str:
    """The same substitutions as the harvest, minus anything the pointer itself has to decide."""
    probe = surface.get("readyProbe")
    return (POINTER_ARM_JS
            .replace("__READY_PROBE__", probe if probe else "true")
            .replace("__BUDGET_MS__", str(READY_BUDGET_MS))
            .replace("__POLL_MS__", str(READY_POLL_MS))
            .replace("__H01__", json.dumps(H01_SECTION, ensure_ascii=False)))


def place_real_pointer(cdp, arm_js: str, surface: dict,
                       facts: dict | None = None) -> dict:
    """Emulate the motion preference if the surface asks, wait for the snapshot, then move a real pointer
    onto the first declared row. Returns the facts and stashes them on the page for the harvest to read.

    The pointer is placed at the row's own centre, which is the position a user's cursor occupies when the
    summary they are shown belongs to that row; a pointer placed on a sibling would light a different row
    and the gate would convict the wrong element.
    """
    facts = {} if facts is None else facts
    if surface.get("emulateReducedMotion"):
        cdp.send("Emulation.setEmulatedMedia",
                 {"features": [{"name": "prefers-reduced-motion", "value": "reduce"}]})
        facts["reducedMotionEmulated"] = True
    armed = json.loads(cdp.evaluate(arm_js))
    facts["armed"] = {"ready": armed.get("ready"), "waitedMs": armed.get("waitedMs"),
                      "mode": armed.get("mode"), "target": armed.get("target")}
    if armed.get("mode") != "row-found":
        facts["mode"] = armed.get("mode") or 'arm-failed'
        # The client refuses an evaluate that produces no value, so the stash returns a token rather than
        # the assignment's own null.
        cdp.evaluate(f"window.__HUD_POINTER_FACTS__ = {json.dumps(facts)}; 'stashed';")
        return facts
    target = armed["target"]
    cdp.send("Input.dispatchMouseEvent", {
        "type": "mouseMoved", "x": target["x"], "y": target["y"],
        "button": "none", "clickCount": 0, "buttons": 0})
    facts.update({"mode": "mouseMoved", "x": target["x"], "y": target["y"],
                  "idle": armed.get("idle") or []})
    cdp.evaluate(f"window.__HUD_POINTER_FACTS__ = {json.dumps(facts, ensure_ascii=False)}; 'stashed';")
    return facts


GEAR_ARM_JS = """(() => {
  const SETTINGS_BUTTON = __SETTINGS_BUTTON__;
  const el = document.querySelector(SETTINGS_BUTTON);
  if (!el) return JSON.stringify({found: false, sel: SETTINGS_BUTTON});
  const r = el.getBoundingClientRect();
  const x = Math.round(r.left + r.width / 2), y = Math.round(r.top + r.height / 2);
  const top = document.elementFromPoint(x, y);
  return JSON.stringify({found: true, sel: SETTINGS_BUTTON, x, y,
                         width: Math.round(r.width), height: Math.round(r.height),
                         inViewport: r.top >= 0 && r.bottom <= window.innerHeight
                           && r.left >= 0 && r.right <= window.innerWidth,
                         hitIsGearOrInside: !!top && (top === el || el.contains(top) || top.contains(el)),
                         hitTag: top ? top.tagName : null,
                         hitLabel: top ? (top.getAttribute('aria-label') || '') : null});
})()
"""


def gear_arm_expression_for(surface: dict) -> str:
    return GEAR_ARM_JS.replace("__SETTINGS_BUTTON__", json.dumps(SETTINGS_BUTTON, ensure_ascii=False))


def press_settings_gear(cdp, ready_arm_js: str, gear_arm_js: str,
                        facts: dict | None = None) -> dict:
    """Press the footer gear with a dispatched mouse event, at the point a cursor would land on it.

    Why not `gear.click()` inside the page, which is what this check used to do: a synthetic click fires the
    React handler whatever the geometry says. It succeeds on a button an overlay is covering, on one pushed
    outside the 150x480 window, and on one whose hit area belongs to a different element — and this strip has
    already shipped a settings block that opened outside the viewport, which only a screenshot caught.
    `elementFromPoint` at the gear's own centre is the hit test the user's cursor performs, so reachability
    and the state change are now both measured rather than assumed.

    The readiness wait runs first and on purpose: opening the block replaces the row list, so a press issued
    before the snapshot lands would leave the surface's own readiness claim waiting on rows that the press
    itself removed. The armed expression only measures — no pointer is moved — so nothing hovers here.
    """
    facts = {} if facts is None else facts
    ready = json.loads(cdp.evaluate(ready_arm_js))
    facts["readyBeforePress"] = {"ready": ready.get("ready"), "waitedMs": ready.get("waitedMs"),
                                 "mode": ready.get("mode")}
    armed = json.loads(cdp.evaluate(gear_arm_js))
    facts.update(armed)
    if not armed.get("found"):
        facts["mode"] = "no-gear-button"
    elif not armed.get("inViewport") or not armed.get("hitIsGearOrInside"):
        facts["mode"] = "gear-unreachable"
    else:
        for kind, buttons in (("mousePressed", 1), ("mouseReleased", 0)):
            cdp.send("Input.dispatchMouseEvent", {
                "type": kind, "x": armed["x"], "y": armed["y"], "button": "left",
                "clickCount": 1, "buttons": buttons, "pointerType": "mouse"})
        facts["mode"] = "mousePressed"
    cdp.evaluate(f"window.__HUD_SETTINGS_PRESS__ = {json.dumps(facts, ensure_ascii=False)}; 'stashed';")
    return facts


# --------------------------------------------------------------------------- the declared data shape
# A fixture, declared as one. Eight of the nine adapters declare a role, six of them
# `agent_runtime`, so the strip's row cap and its honest "另有 N 个工具未在此列出" remainder line are
# both exercised; one project pair so 关联项目 carries real names instead of a
# null; one waiting execution so 待审 is a counted fact rather than a padded zero. No field here is a
# quota, a balance, or a reset time, because the snapshot contract carries none — which is exactly the
# state the strip must render as UNKNOWN.
FIXTURE_SNAPSHOT: dict = {
    "schemaVersion": "workflow/snapshot/v3",
    "revision": 1,
    "generatedAt": "2026-10-25T09:00:00+08:00",
    "sourceWatermark": "2026-10-25T09:00:00+08:00",
    "transport": {"transportState": "LIVE", "lastEventId": None, "resyncRequired": False},
    "coverage": {"projects": 2, "executions": 2, "note": "fixture"},
    "governance": {"authority": "WORK-LAB-AUTHORITY.md", "state": "FROZEN_FOR_GATE"},
    "git": {"branch": "gate-fixture", "sha": "0" * 40, "dirty": False},
    "workspace": {"root": "fixture"},
    "tasks": {},
    "tokenSummary": {},
    "ci": [],
    "sourceRefs": [],
    "projects": [
        {"projectId": "work-lab", "displayName": "WORK-LAB", "agentPlatform": "Hermes",
         "identityState": "VERIFIED", "activityState": "ACTIVE", "attentionState": "NORMAL",
         "activeExecutionCount": 1, "workingAreas": ["observer"], "visibility": "PRIVATE",
         "quality": "UNKNOWN", "lastStrongEvidenceAt": None, "repositories": [],
         "git": {}, "token": {}, "ci": [], "executionIds": ["exec-1"], "sourceRefs": []},
        {"projectId": "design-lab", "displayName": "DESIGN-LAB 界面与资产", "agentPlatform": None,
         "identityState": "DECLARED", "activityState": "IDLE", "attentionState": "NORMAL",
         "activeExecutionCount": 0, "workingAreas": [], "visibility": "PRIVATE",
         "quality": "UNKNOWN", "lastStrongEvidenceAt": None, "repositories": [],
         "git": {}, "token": {}, "ci": [], "executionIds": [], "sourceRefs": []},
    ],
    "executions": [
        {"executionId": "exec-1", "anchorProjectId": "work-lab", "workingArea": "observer",
         "state": "WAITING_APPROVAL", "stateQuality": "OBSERVED", "agent": "Hermes",
         "sessionId": None, "sourceRef": None},
        {"executionId": "exec-2", "anchorProjectId": "design-lab", "workingArea": None,
         "state": "SUCCEEDED", "stateQuality": "OBSERVED", "agent": "Codex",
         "sessionId": None, "sourceRef": None},
    ],
    "adapterCapabilities": [
        {"clientId": "codex", "displayName": "Codex", "supportLevel": "MANAGE",
         "declaredOperations": [], "matrixOperations": [], "operationsDrift": False,
         "registryStatus": "DECLARED", "writePolicy": "none", "risk": "LOW",
         "runtimeAdapter": None, "configOwnershipDefault": None, "declaredVersion": "0.22.2",
         "versionReadbackMethod": None, "versionObservedAt": None, "versionSource": None,
         "detectionMode": None, "detectionEvidenceState": "UNKNOWN", "protocolConformance": {},
         "observedAt": "2026-10-25T09:00:00+08:00", "layers": [], "nativeStatus": "NOT_PROBED",
         "role": "agent_runtime"},
        {"clientId": "github", "displayName": "GitHub", "supportLevel": "MANAGE",
         "declaredOperations": [], "matrixOperations": [], "operationsDrift": False,
         "registryStatus": "DECLARED", "writePolicy": "none", "risk": "LOW",
         "runtimeAdapter": None, "configOwnershipDefault": None, "declaredVersion": None,
         "versionReadbackMethod": None, "versionObservedAt": None, "versionSource": None,
         "detectionMode": None, "detectionEvidenceState": "UNKNOWN", "protocolConformance": {},
         "role": "vcs_host",
         "observedAt": "2026-10-25T09:00:00+08:00", "layers": [], "nativeStatus": "NOT_PROBED"},
        {"clientId": "hermes", "displayName": "Hermes", "supportLevel": "MANAGE",
         "declaredOperations": [], "matrixOperations": [], "operationsDrift": False,
         "registryStatus": "DECLARED", "writePolicy": "none", "risk": "LOW",
         "runtimeAdapter": None, "configOwnershipDefault": None, "declaredVersion": "0.22.2",
         "versionReadbackMethod": None, "versionObservedAt": None, "versionSource": None,
         "detectionMode": None, "detectionEvidenceState": "UNKNOWN", "protocolConformance": {},
         "observedAt": "2026-10-25T09:00:00+08:00", "layers": [], "nativeStatus": "NOT_PROBED",
         "role": "agent_runtime"},
        {"clientId": "deepseek-harness", "displayName": "DeepSeek Harness", "supportLevel": "OBSERVE",
         "declaredOperations": [], "matrixOperations": [], "operationsDrift": False,
         "registryStatus": "DECLARED", "writePolicy": "none", "risk": "LOW",
         "runtimeAdapter": None, "configOwnershipDefault": None, "declaredVersion": "0.2.1-rc.2",
         "versionReadbackMethod": None, "versionObservedAt": None, "versionSource": None,
         "detectionMode": None, "detectionEvidenceState": "UNKNOWN", "protocolConformance": {},
         "observedAt": "2026-10-25T09:00:00+08:00", "layers": [], "nativeStatus": "NOT_PROBED",
         "role": "agent_runtime"},
        {"clientId": "qoder", "displayName": "Qoder", "supportLevel": "OBSERVE",
         "declaredOperations": [], "matrixOperations": [], "operationsDrift": False,
         "registryStatus": "DECLARED", "writePolicy": "none", "risk": "LOW",
         "runtimeAdapter": None, "configOwnershipDefault": None, "declaredVersion": "0.4.11",
         "versionReadbackMethod": None, "versionObservedAt": None, "versionSource": None,
         "detectionMode": None, "detectionEvidenceState": "UNKNOWN", "protocolConformance": {},
         "observedAt": "2026-10-25T09:00:00+08:00", "layers": [], "nativeStatus": "NOT_PROBED",
         "role": "agent_runtime"},
        {"clientId": "open-design", "displayName": "Open Design", "supportLevel": "MANAGE",
         "declaredOperations": [], "matrixOperations": [], "operationsDrift": False,
         "registryStatus": "DECLARED", "writePolicy": "none", "risk": "MEDIUM",
         "runtimeAdapter": None, "configOwnershipDefault": None, "declaredVersion": None,
         "versionReadbackMethod": None, "versionObservedAt": None, "versionSource": None,
         "detectionMode": None, "detectionEvidenceState": "UNKNOWN", "protocolConformance": {},
         "observedAt": "2026-10-25T09:00:00+08:00", "layers": [], "nativeStatus": "NOT_IMPLEMENTED",
         "role": "design_client"},
        {"clientId": "openhuman", "displayName": "OpenHuman", "supportLevel": "OBSERVE",
         "declaredOperations": [], "matrixOperations": [], "operationsDrift": False,
         "registryStatus": "DECLARED", "writePolicy": "none", "risk": "LOW",
         "runtimeAdapter": None, "configOwnershipDefault": None, "declaredVersion": None,
         "versionReadbackMethod": None, "versionObservedAt": None, "versionSource": None,
         "detectionMode": None, "detectionEvidenceState": "UNKNOWN", "protocolConformance": {},
         "observedAt": "2026-10-25T09:00:00+08:00", "layers": [], "nativeStatus": "NOT_PROBED"},
        {"clientId": "fixture-agent-a", "displayName": "Fixture Agent A", "supportLevel": "MANAGE",
         "declaredOperations": [], "matrixOperations": [], "operationsDrift": False,
         "registryStatus": "DECLARED", "writePolicy": "none", "risk": "LOW",
         "runtimeAdapter": None, "configOwnershipDefault": None, "declaredVersion": None,
         "versionReadbackMethod": None, "versionObservedAt": None, "versionSource": None,
         "detectionMode": None, "detectionEvidenceState": "UNKNOWN", "protocolConformance": {},
         "role": "agent_runtime",
         "observedAt": "2026-10-25T09:00:00+08:00", "layers": [], "nativeStatus": "NOT_PROBED"},
        {"clientId": "fixture-agent-b", "displayName": "Fixture Agent B", "supportLevel": "MANAGE",
         "declaredOperations": [], "matrixOperations": [], "operationsDrift": False,
         "registryStatus": "DECLARED", "writePolicy": "none", "risk": "LOW",
         "runtimeAdapter": None, "configOwnershipDefault": None, "declaredVersion": None,
         "versionReadbackMethod": None, "versionObservedAt": None, "versionSource": None,
         "detectionMode": None, "detectionEvidenceState": "UNKNOWN", "protocolConformance": {},
         "role": "agent_runtime",
         "observedAt": "2026-10-25T09:00:00+08:00", "layers": [], "nativeStatus": "NOT_PROBED"},
    ],
}

# Two cards are in the fixture only to be kept out. `GitHub` is the delivery platform (its real client
# declares `vcs_host` in config/capability-matrix.json) and is deliberately the SECOND adapter: if the
# strip ever maps over every card again, its name lands inside the five visible rows and the gate can see
# it. `OpenHuman` declares no role at all, which is the source-gap case and must be counted separately.
AGENT_ROLE = "agent_runtime"
# Read off the fixture rather than restated, so adding an adapter cannot make the expectation disagree with
# the input it is supposed to describe.
AGENT_FIXTURE_IDS = frozenset(
    str(c["clientId"]) for c in FIXTURE_SNAPSHOT["adapterCapabilities"] if c.get("role") == AGENT_ROLE)
EXCLUDED_FIXTURE_NAMES = tuple(
    str(c["displayName"]) for c in FIXTURE_SNAPSHOT["adapterCapabilities"]
    if str(c["clientId"]) not in AGENT_FIXTURE_IDS)

# The rail's declared population plus the bottom-pinned 设置. The CI test
# `tests/ci/test_daily_nav_population_is_the_declared_table.py` pins this tuple against DAILY_NAV in
# `apps/observer/frontend/src/daily/DailyChrome.tsx`, so the gate cannot keep asserting an old nav after
# the table grows.
DAILY_ENTRY_LABELS = ("项目", "问题与经验", "我的工具", "治理与诊断", "设置")
# The five cards the governance screen mounts, in the sign-off pack's order, as (card id, declared label).
# Hand-copied like the nav tuple above it, and pinned the same way: DailyCarriedCardLabelTests reads the
# source table back, so a sixth carried view cannot join the screen without joining this list.
CARRIED_CARDS = (("trust", "数据可信度"),
                 ("monitoring", "传输真值与状态矩阵"),
                 ("collectors", "采集器交付与拒绝"),
                 ("privacy", "只读与隐私边界"),
                 ("audit", "审计追踪"))


# --------------------------------------------------------------------------- the browser, reused

def load_geometry():
    """Reuse the CDP client and the headless launcher the geometry gate already proved out."""
    spec = importlib.util.spec_from_file_location("topbar_geometry_via_cdp", GEOMETRY_SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)  # type: ignore[attr-defined]
    return module


def load_u19(geometry):
    return geometry.load_u19()


class SnapshotFixture:
    """One loopback origin that serves the built bundle AND answers the snapshot GET.

    Same-origin on purpose: the front refuses an untrusted `?api=` endpoint unless it is loopback http
    on `/api/v1/snapshot`, and a second port would be a second origin the browser then blocks with CORS.
    The events stream is held open with a `retry:` field so `EventSource` reports `open` and does not
    reconnect-storm the gate; nothing is replayed, because the fixture has no revision history.
    """

    def __init__(self, dist: Path, payload: dict | None = None) -> None:
        self.dist = dist
        self.payload = FIXTURE_SNAPSHOT if payload is None else payload
        self.stop = threading.Event()
        holder = self

        class Handler(http.server.SimpleHTTPRequestHandler):
            def __init__(self, *a, **kw):
                super().__init__(*a, directory=str(holder.dist), **kw)

            def log_message(self, *a):  # noqa: ANN002 — the gate's stdout is the verdict, not request noise
                pass

            def do_GET(self):  # noqa: N802 — http.server naming
                if self.path.split("?")[0] == "/api/v1/snapshot":
                    body = json.dumps(holder.payload, ensure_ascii=False).encode("utf-8")
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json; charset=utf-8")
                    self.send_header("Content-Length", str(len(body)))
                    self.send_header("Cache-Control", "no-store")
                    self.end_headers()
                    self.wfile.write(body)
                    return
                if self.path.split("?")[0] == "/api/v1/events":
                    self.send_response(200)
                    self.send_header("Content-Type", "text/event-stream")
                    self.send_header("Cache-Control", "no-store")
                    self.end_headers()
                    self.wfile.write(b"retry: 30000\n\n")
                    self.wfile.flush()
                    holder.stop.wait(timeout=600.0)
                    return
                return super().do_GET()

        self.httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.httpd.daemon_threads = True
        self.httpd.block_on_close = False
        self.port = self.httpd.server_port
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)

    def url_for(self, query: str, theme: str = "dark") -> str:
        api = f"api=http%3A%2F%2F127.0.0.1%3A{self.port}%2Fapi%2Fv1%2Fsnapshot"
        return (f"http://127.0.0.1:{self.port}/index.html?{query}"
                f"&mode=UNKNOWN&theme={theme}&{api}")

    def start(self) -> None:
        self.thread.start()

    def stop_server(self) -> None:
        self.stop.set()
        self.httpd.shutdown()
        self.httpd.server_close()


# --------------------------------------------------------------------------- the verdict (pure)

def _check(checks: list[dict], name: str, ok: bool, detail: str) -> None:
    checks.append({"check": name, "pass": bool(ok), "detail": detail})


def _slug(name: str) -> str:
    return name.replace("-", "_")


def _line_texts(label_lines: list) -> list[dict]:
    """Leaf labels measured on more than one line, with each line's own text and width."""
    out = []
    for item in label_lines or []:
        lines = [l for l in (item.get("lines") or [])
                 if isinstance(l, dict) and isinstance(l.get("width"), (int, float))
                 and str(l.get("text") or "")]
        size = item.get("fontSize") or 0
        if len(lines) >= 2 and size:
            out.append({**item, "lines": lines, "fontSize": size})
    return out


def _shattered(labels: list[dict]) -> list[dict]:
    """Labels whose widest line is no wider than one glyph: the row is broken, not wrapped."""
    return [{**item, "widestLine": max(l["width"] for l in item["lines"])} for item in labels
            if max(l["width"] for l in item["lines"]) <= item["fontSize"] * CHAR_WRAP_LINE_MULTIPLE]


def _orphan_glyph_lines(labels: list[dict]) -> list[dict]:
    """Labels that leave exactly one CJK glyph alone on a line.

    A number landing on a line by itself is a legitimate break; an ideograph is how a squeezed row
    finishes shattering. Measured 2026-10-25: the H03 reset label broke as 「重置时间 待确」+「认」 in
    the 85px the strip's quota row has left — one line box, one character, and every width check green.
    """
    offenders = []
    for item in labels:
        lonely = [l for l in item["lines"]
                  if len(l.get("text") or "") == 1 and not str(l["text"]).isascii()]
        if lonely:
            offenders.append({**item, "lonelyLines": [l["text"] for l in lonely]})
    return offenders


def _surface_checks(checks: list[dict], name: str, spec: dict, surface: dict | None) -> dict | None:
    """The geometry claims every measured surface owes, and the surface's harvest for the families below
    that need it. Returns None when the surface was never measured — which fails closed."""
    slug = _slug(name)
    families = ["no_horizontal_overflow", "no_unreachable_control",
                "no_label_shatters_to_one_character", "no_label_leaves_a_single_glyph_alone"]
    if spec.get("readyProbe"):
        families.append("fixture_snapshot_reached_the_surface")
    if not isinstance(surface, dict):
        _check(checks, f"{slug}_measured", False,
               f"surface {name!r} is in the declared SURFACES list but the harvest has no entry for it; "
               "an unmeasured surface is not a passing one")
        for family in families:
            _check(checks, f"{slug}_{family}", False, "not measured: the surface produced no harvest")
        return None
    vp = surface.get("viewport") or {}
    want_w, want_h = spec["size"]
    got = (vp.get("clientW"), vp.get("clientH"))
    _check(checks, f"{slug}_measured", got == (want_w, want_h),
           f"layout viewport={got[0]}x{got[1]} declared={want_w}x{want_h} "
           f"scroll={vp.get('scrollW')}x{vp.get('scrollH')} dpr={vp.get('dpr')} "
           f"mountWait={json.dumps(surface.get('readyWait'))}")
    if got != (want_w, want_h):
        # Everything below would be measured at a size the product does not declare, so saying
        # "overflow-free" about it would be a lie about a surface nobody ships.
        for family in families:
            _check(checks, f"{slug}_{family}", False,
                   f"not judged: measured at {got[0]}x{got[1]}, not the declared {want_w}x{want_h}")
        return surface

    if spec.get("readyProbe"):
        # The settings surface is pressed before the harvest reads it, and opening the block replaces the row
        # list, so a post-press harvest can never see the rows again. Its readiness is therefore proven by the
        # probe's own wait, which ran while nothing was open — and the detail says which of the two measured.
        before = (surface.get("settingsPress") or {}).get("readyBeforePress") or {}
        ready = before.get("ready") if before else surface.get("ready")
        waited = before.get("waitedMs") if before else surface.get("readyWaitMs")
        _check(checks, f"{slug}_fixture_snapshot_reached_the_surface",
               ready is True,
               f"condition={spec['readyWhy']!r} ready={ready} waitedMs={waited} "
               f"budgetMs={surface.get('readyBudgetMs')} "
               f"measuredAt={'probe-before-the-press' if before else 'harvest'} "
               "(a surface harvested before the snapshot lands has no rows to hover and no values to "
               "hold at UNKNOWN, so every claim below it would be about a shape the product does not ship)")

    client_w = vp.get("clientW") or 0
    scroll_w = vp.get("scrollW")
    _check(checks, f"{slug}_no_horizontal_overflow",
           isinstance(scroll_w, (int, float)) and scroll_w <= client_w + VIEWPORT_TOLERANCE_PX,
           f"scrollWidth={scroll_w} clientWidth={client_w}")

    controls = surface.get("controls")
    if not isinstance(controls, list):
        _check(checks, f"{slug}_no_unreachable_control", False,
               f"the harvest returned controls as {type(controls).__name__}; the gate cannot read it "
               "and refuses to call an unreadable shape a pass")
        unreachable = []
        painted = []
    else:
        # "painted" is a real box that is actually shown. `.app` clips with overflow:hidden, so
        # scrollWidth stays at the window width while a control is pushed past the edge: reachability
        # is a rect question, and the sizer scaffold that paints nothing is not a control.
        painted = [c for c in controls
                   if c.get("visibility") == "visible" and c.get("display") != "none"
                   and (c.get("width") or 0) > 0 and (c.get("height") or 0) > 0]
        # Horizontal only, on purpose. A control below the fold inside a scroll region is reachable by
        # scrolling, so the vertical claims are carried by the footer and summary checks below, which
        # name the box they measured. The strip's own defect class was a control pushed past 150px.
        unreachable = [c for c in painted
                       if c.get("right", 0) > client_w + CONTROL_EDGE_TOLERANCE_PX
                       or c.get("left", 0) < -CONTROL_EDGE_TOLERANCE_PX]
        _check(checks, f"{slug}_no_unreachable_control", bool(painted) and not unreachable,
               f"painted={len(painted)} of={len(controls)} outside="
               f"{json.dumps(unreachable, ensure_ascii=False)[:320]}"
               + (" -- nothing painted a clickable box: a surface with no control to reach is not "
                  "a reachable one" if not painted else ""))

    label_lines = surface.get("labelLines")
    if not isinstance(label_lines, list):
        _check(checks, f"{slug}_no_label_shatters_to_one_character", False,
               f"labelLines came back as {type(label_lines).__name__}, not a list of measurements")
        _check(checks, f"{slug}_no_label_leaves_a_single_glyph_alone", False,
               f"labelLines came back as {type(label_lines).__name__}, not a list of measurements")
    else:
        labels = _line_texts(label_lines)
        shattered = _shattered(labels)
        shattered_named = json.dumps([{"text": s["text"], "lines": len(s["lines"]),
                                       "widestLine": s["widestLine"], "fontSize": s["fontSize"]}
                                      for s in shattered], ensure_ascii=False)[:320]
        _check(checks, f"{slug}_no_label_shatters_to_one_character", not shattered,
               f"candidates={len(labels)} shattered={shattered_named} "
               f"limit=widest line <= fontSize*{CHAR_WRAP_LINE_MULTIPLE}")
        orphans = _orphan_glyph_lines(labels)
        orphans_named = json.dumps([{"text": o["text"], "lonely": o["lonelyLines"],
                                     "lines": [l["text"] for l in o["lines"]]}
                                    for o in orphans], ensure_ascii=False)[:320]
        _check(checks, f"{slug}_no_label_leaves_a_single_glyph_alone", not orphans,
               f"candidates={len(labels)} lonely_cjk_line={orphans_named} "
               "(a lone number is a legitimate break; a lone ideograph is a row that has finished "
               "shattering)")

    return surface


def verdict(measured: dict, resolved_surfaces: list[dict] | None = None,
            payload: dict | None = None, data: dict | None = None) -> dict:
    """Pure: no browser, no filesystem. `measured` maps a declared surface name to its harvest.

    Every threshold lives here, so a planted fault is a line of data, not a rebuilt bundle.

    `payload`/`data` only shape the receipt's data block, never a judgement: the counts the reader sees
    must be the counts of the bytes that were actually served, and the source must say whether those bytes
    were the declared fixture or a live snapshot. A receipt that labelled real ledger bytes "fixture" would
    tell the reader the run tested something it did not test.
    """
    measured = measured if isinstance(measured, dict) else {}
    checks: list[dict] = []
    harvests: dict[str, dict] = {}

    for spec in (SURFACES if resolved_surfaces is None else resolved_surfaces):
        surface = _surface_checks(checks, spec["name"], spec, measured.get(spec["name"]))
        if surface is not None:
            harvests[spec["name"]] = surface

    strip_names = [s["name"] for s in SURFACES if s["kind"] == "strip"]
    strips = {n: harvests[n] for n in strip_names if n in harvests}

    # --- claims that are about the strip as a surface, not about one state -------------------
    frames = {n: s.get("hudFrame") for n, s in strips.items()}
    _check(checks, "strip_frame_is_the_native_strip_not_the_panel",
           bool(strips) and all(f == "native-strip" for f in frames.values()),
           f"data-hud-frame={json.dumps(frames, ensure_ascii=False)}")

    for name in strip_names:
        slug = _slug(name)
        surface = strips.get(name)
        if not surface:
            _check(checks, f"{slug}_footer_pinned_in_viewport", False, "not measured")
            _check(checks, f"{slug}_state_renders_as_declared", False, "not measured")
            _check(checks, f"{slug}_state_switcher_is_not_painted", False, "not measured")
            continue
        client_h = (surface.get("viewport") or {}).get("clientH") or 0
        footer = surface.get("footer")
        if not isinstance(footer, dict):
            _check(checks, f"{slug}_footer_pinned_in_viewport", False,
                   f"no [data-landmark=\"hud-footer\"] painted in a {client_h}px window: the reference "
                   "keeps the footer resident, so its absence is a failure, not an absence of problem")
        else:
            _check(checks, f"{slug}_footer_pinned_in_viewport",
                   footer.get("height", 0) > 0 and footer.get("top", -1) >= -VIEWPORT_TOLERANCE_PX
                   and footer.get("bottom", 1e9) <= client_h + VIEWPORT_TOLERANCE_PX,
                   f"footer top={footer.get('top')} bottom={footer.get('bottom')} "
                   f"height={footer.get('height')} viewportHeight={client_h}")
        want_state = next(s["state"] for s in SURFACES if s["name"] == name)
        _check(checks, f"{slug}_state_renders_as_declared", surface.get("hudState") == want_state,
               f"data-hud-state={surface.get('hudState')!r} declared={want_state!r}")
        _check(checks, f"{slug}_state_switcher_is_not_painted", surface.get("switcherButtons") == 0,
               f"switcherButtons={surface.get('switcherButtons')} "
               "(the four-state switcher is the 440px panel's affordance; the strip switches by drag "
               "and by deep link)")

    _check(checks, "strip_has_a_drag_surface",
           bool(strips) and all((s.get("dragRegions") or 0) >= 1 for s in strips.values()),
           f"dragRegions={json.dumps({n: s.get('dragRegions') for n, s in strips.items()})} "
           "min=1 (a decorations:false window is moved only by its drag handle)")

    # --- who the monitor is allowed to draw ---------------------------------------------------------
    # H03 and H04 replace the row list with a detail card and a reminder, so "no rows" is the right shape
    # there. The requirement is made against the surfaces that paint the H01 card, which the harvest already
    # reports as absent rather than empty -- the same absent-is-not-zero distinction the product draws.
    hud_surfaces = {n: s for n, s in harvests.items()
                    if _SURFACE_KINDS.get(n) in ("strip", "panel")}
    rowed = {n: s for n, s in hud_surfaces.items() if (s.get("h01") or {}).get("rect")}
    strays = {n: sorted(set(s.get("agentMarks") or []) - AGENT_FIXTURE_IDS) for n, s in hud_surfaces.items()}
    painted_excluded = {n: [name for name in EXCLUDED_FIXTURE_NAMES if name in (s.get("bodyText") or "")]
                        for n, s in hud_surfaces.items()}
    _check(checks, "hud_monitors_only_declared_agent_runtimes",
           bool(rowed) and all(s.get("agentMarks") for s in rowed.values())
           and not any(strays.values()) and not any(painted_excluded.values()),
           f"surfaces={json.dumps(sorted(hud_surfaces))} surfacesWithRowList={json.dumps(sorted(rowed))} "
           f"rows={json.dumps({n: s.get('agentMarks') for n, s in hud_surfaces.items()})} "
           f"rowsOutsideTheDeclaration={json.dumps(strays, ensure_ascii=False)} "
           f"excludedNamesStillPainted={json.dumps(painted_excluded, ensure_ascii=False)} "
           f"declaredAgentIds={sorted(AGENT_FIXTURE_IDS)} "
           "(the strip is an agent monitor; a card whose declared role is not an agent runtime, or none at "
           "all, belongs to the count in the exclusion note and not to a row)")

    h01_surfaces = {n: s for n, s in strips.items() if (s.get("h01") or {}).get("rect")}
    _check(checks, "h01_card_stays_inside_the_declared_strip_width",
           bool(h01_surfaces) and all(
               0 <= (s["h01"]["rect"].get("left") or -1)
               and (s["h01"]["rect"].get("width") or 0) > 0
               and (s["h01"]["rect"].get("width") or 9e9) <= STRIP[0]
               and (s["h01"]["rect"].get("right") or 9e9)
               <= (s.get("viewport") or {}).get("clientW", 0) + VIEWPORT_TOLERANCE_PX
               for s in h01_surfaces.values()),
           f"rects={json.dumps({n: s['h01']['rect'] for n, s in h01_surfaces.items()})} "
           f"declaredWidth={STRIP[0]}")

    # --- H02: the hover summary is an inline capsule in the hovered row, with the ring lit -------
    hover_spec = next((s for s in SURFACES if s.get("hover")), None)
    hover = harvests.get(hover_spec["name"]) if hover_spec else None
    if not hover:
        _check(checks, "hover_reveals_the_summary_inside_the_row", False, "no hover surface measured")
        _check(checks, "hover_summary_is_readable_without_scrolling", False, "no hover surface measured")
        _check(checks, "hover_row_is_the_one_highlighted_amberly", False, "no hover surface measured")
        _check(checks, "hover_keeps_h01_mounted", False, "no hover surface measured")
        _check(checks, "hover_uses_a_real_pointer_not_a_synthetic_event", False,
               "no hover surface measured")
        _check(checks, "real_pointer_is_over_exactly_one_row", False, "no hover surface measured")
    else:
        pointer = hover.get("pointer") or {}
        _check(checks, "hover_uses_a_real_pointer_not_a_synthetic_event",
               hover.get("hoverDispatch") == "cdp-mouseMoved" and pointer.get("mode") == "mouseMoved",
               f"hoverDispatch={hover.get('hoverDispatch')!r} pointerMode={pointer.get('mode')!r} "
               f"pointer={json.dumps(pointer.get('armed'), ensure_ascii=False, default=str)} "
               "(CL-16 step 2: `dispatchEvent(new MouseEvent(...))` reaches React but never lights a CSS "
               "pseudo-class, so the hover language of the stylesheet was unmeasured while a JS-only "
               "affordance looked green. A real CDP pointer drives both.)")
        rows_read = hover.get("rows") or []
        hovered_indexes = [i for i, r in enumerate(rows_read) if r.get("isHovered")]
        idle_styles = pointer.get("idle") or []
        moved = {}
        if idle_styles and rows_read:
            before, after = idle_styles[0], (rows_read[0].get("style") or {})
            moved = {k: [before.get(k), after.get(k)] for k in after if before.get(k) != after.get(k)}
        _check(checks, "real_pointer_is_over_exactly_one_row",
               len(hovered_indexes) == 1,
               f"hoveredIndexes={hovered_indexes} of rows={len(rows_read)} "
               f"pointerAt={json.dumps({k: pointer.get(k) for k in ('x', 'y')}, ensure_ascii=False)} "
               f"rowStyleChangedUnderPointer={json.dumps(moved, ensure_ascii=False)} "
               "(one hovered row is what a pointer at a declared position produces; zero means the pointer "
               "never landed — including when the driver placed it but the page was rebuilt under it — and "
               "more than one means the strip is not keyed per row. Measured 2026-10-28: these rows carry "
               "no CSS `:hover` rule at all, so the style diff above is reported as the gap, not asserted "
               "as a pass.)")
        summary = hover.get("summary")
        _check(checks, "hover_reveals_the_summary_inside_the_row",
               isinstance(summary, dict) and summary.get("insideLi") is True
               and summary.get("insideH01Row") is True,
               f"dispatch={hover.get('hoverDispatch')!r} summary="
               f"{json.dumps(summary, ensure_ascii=False)}")
        client_h = (hover.get("viewport") or {}).get("clientH") or 0
        _check(checks, "hover_summary_is_readable_without_scrolling",
               isinstance(summary, dict)
               and summary.get("top", -1) >= -VIEWPORT_TOLERANCE_PX
               and summary.get("bottom", 1e9) <= client_h + VIEWPORT_TOLERANCE_PX,
               f"summary top={summary and summary.get('top')} bottom={summary and summary.get('bottom')} "
               f"viewportHeight={client_h} nearestScrollerOverflow="
               f"{summary and summary.get('scrollerOverflow')} "
               "(below the fold inside a scroll box would be reported here as pxBelowFold)")
        rows = hover.get("rows")
        ringed = [r for r in (rows or []) if r.get("hasRing")]
        lit = [i for i, r in enumerate(rows or [])
               if r.get("hasRing") and r.get("ringRole") == ACTIVE_RING]
        idle = [i for i, r in enumerate(rows or [])
                if r.get("hasRing") and r.get("ringRole") == IDLE_RING]
        unlabelled = [i for i, r in enumerate(rows or [])
                      if r.get("hasRing") and r.get("ringRole") not in (ACTIVE_RING, IDLE_RING)]
        with_summary = [i for i, r in enumerate(rows or []) if r.get("hasSummary")]
        # The lit row must also be a DIFFERENT PAINTED COLOUR from the idle rows in the theme that is
        # live. Role alone would stay green if --daily-warn-mark and --daily-line were ever set to one
        # value, which is exactly the "wired but colourless" regression this gate exists to catch.
        lit_strokes = {rows[i].get("stroke") for i in lit} if rows else set()
        idle_strokes = {rows[i].get("stroke") for i in idle} if rows else set()
        painted_apart = bool(lit_strokes) and not (lit_strokes & idle_strokes)
        _check(checks, "hover_row_is_the_one_highlighted_amberly",
               bool(ringed) and not unlabelled and len(with_summary) == 1
               and len(lit) == 1 and lit == with_summary and painted_apart,
               f"rows={json.dumps(rows, ensure_ascii=False)[:300]} litRows={lit} "
               f"summaryRows={with_summary} unlabelled={unlabelled} "
               f"litStroke={sorted(lit_strokes)} idleStroke={sorted(idle_strokes)} "
               f"colourDiffersFromIdle={painted_apart} expectedRoles={(ACTIVE_RING, IDLE_RING)!r}")
        _check(checks, "hover_keeps_h01_mounted", bool((hover.get("h01") or {}).get("rect")),
               f"h01={json.dumps(hover.get('h01') and hover['h01']['rect'])}")

    # --- the mini settings block: reached only by pressing the footer gear ------------------------
    for name in [str(s["name"]) for s in SURFACES if s.get("openSettings")]:
        slug = _slug(name)
        surface = harvests.get(name)
        if not surface:
            _check(checks, f"{slug}_gear_is_reachable_by_a_real_pointer", False, "not measured")
            _check(checks, f"{slug}_gear_opens_the_settings_block", False, "not measured")
            _check(checks, f"{slug}_settings_block_is_readable_and_dismissible", False, "not measured")
            continue
        settings = surface.get("settings")
        press = surface.get("settingsPress") or {}
        client_h = (surface.get("viewport") or {}).get("clientH") or 0
        painted = isinstance(settings, dict) and (settings.get("height") or 0) > 0
        # Reachability first, and by name: a gear that no cursor can land on is unusable whether or not the
        # block would have opened for a synthetic click, and this is the only place that distinction exists.
        _check(checks, f"{slug}_gear_is_reachable_by_a_real_pointer",
               press.get("found") is True and press.get("inViewport") is True
               and press.get("hitIsGearOrInside") is True,
               f"found={press.get('found')} inViewport={press.get('inViewport')} "
               f"hitIsGearOrInside={press.get('hitIsGearOrInside')} "
               f"at=({press.get('x')},{press.get('y')}) size={press.get('width')}x{press.get('height')} "
               f"topElement={press.get('hitTag')!r}/{press.get('hitLabel')!r} "
               "(elementFromPoint at the gear's own centre is the hit test a cursor performs)")
        _check(checks, f"{slug}_gear_opens_the_settings_block",
               surface.get("settingsDispatch") == "cdp-mousePressed" and painted
               and settings.get("expanded") == "true" and settings.get("insideFrame") is True,
               f"dispatch={surface.get('settingsDispatch')!r} painted={painted} "
               f"ariaExpanded={settings and settings.get('expanded')!r} "
               f"insideFrame={settings and settings.get('insideFrame')} "
               "(the block is React state and travels in no URL: if a real press on the gear does not open "
               "it here, nothing in this project ever renders it in a browser)")
        sizes = [v for v in ((settings or {}).get("fontSizes") or []) if v]
        close_rect = (settings or {}).get("closeRect") or {}
        _check(checks, f"{slug}_settings_block_is_readable_and_dismissible",
               painted and bool(sizes) and min(sizes) >= TYPE_FLOOR_PX
               and (settings or {}).get("bottom", 1e9) <= client_h + VIEWPORT_TOLERANCE_PX
               and bool((settings or {}).get("closeText"))
               and close_rect.get("width", 0) > 0 and close_rect.get("height", 0) > 0,
               f"rect={settings and [settings.get('top'), settings.get('bottom'), settings.get('height')]} "
               f"viewportHeight={client_h} minFontSize={min(sizes) if sizes else None} "
               f"floor={TYPE_FLOOR_PX} closeText={(settings or {}).get('closeText')!r} "
               f"closeRect={json.dumps(close_rect)} controls={(settings or {}).get('controlCount')}")

    # --- H03: the reference's three quota rows, painted as slots and valued as UNKNOWN -------------
    h03 = harvests.get("strip-h03")
    quota = (h03 or {}).get("quotaRows")
    if not isinstance(quota, list):
        _check(checks, "h03_quota_rows_are_three_slots_and_honest", False,
               f"[data-landmark=\"h03-quota-rows\"] came back as {type(quota).__name__}: the row block "
               "the reference draws is missing, so nothing can be claimed about it")
    else:
        tracks = []
        for row in quota:
            boxes = row.get("boxes") or []
            tracks.append(any(b.get("w", 0) >= QUOTA_TRACK_MIN_W
                              and 0 < b.get("h", 0) <= QUOTA_TRACK_MAX_H for b in boxes))
        all_text = " ".join(str(r.get("text") or "") for r in quota)
        problems = []
        if len(quota) != QUOTA_ROW_COUNT:
            problems.append(f"rows={len(quota)} expected={QUOTA_ROW_COUNT}")
        if any("UNKNOWN" not in str(r.get("text") or "") for r in quota):
            problems.append("a row states a value instead of UNKNOWN")
        if any("待确认" not in str(r.get("text") or "") for r in quota):
            problems.append("a row states a reset time instead of 待确认")
        if not all(tracks):
            problems.append(f"empty tracks missing={json.dumps(tracks)}")
        if "%" in all_text:
            problems.append(f"a fabricated percentage is painted: {all_text[:120]!r}")
        _check(checks, "h03_quota_rows_are_three_slots_and_honest", not problems,
               f"rows={json.dumps(quota, ensure_ascii=False)[:420]} problems="
               f"{json.dumps(problems, ensure_ascii=False)}")

    # --- the truth rule, asserted on painted strings rather than on the source --------------------
    painted: dict[str, str] = {}
    unpainted: list[str] = []
    for name, surface in strips.items():
        text = surface.get("bodyText")
        if not isinstance(text, str) or not text.strip():
            unpainted.append(name)
            text = ""
        painted[name] = text
    with_percent = {n: text for n, text in painted.items() if "%" in text}
    percent_context = json.dumps({n: t[max(0, t.index("%") - 24):t.index("%") + 8]
                                  for n, t in with_percent.items()}, ensure_ascii=False)[:300]
    _check(checks, "strip_never_fabricates_a_percentage",
           bool(strips) and not unpainted and not with_percent,
           f"no_painted_text_harvested={json.dumps(unpainted, ensure_ascii=False)} "
           f"surfaces_with_percent={percent_context}")
    missing_unknown = [n for n, s in h01_surfaces.items()
                       if "额度 UNKNOWN" not in str((s.get("h01") or {}).get("text") or "")]
    _check(checks, "strip_keeps_quota_unknown_instead_of_zero",
           bool(h01_surfaces) and not missing_unknown,
           f"surfaces_without_the_unknown_quota_line={json.dumps(missing_unknown, ensure_ascii=False)} "
           f"h01PaintedOn={json.dumps(sorted(h01_surfaces), ensure_ascii=False)}")

    # --- the 440px panel keeps what the strip deliberately does not paint -------------------------
    panel = harvests.get("panel-h01")
    if not panel:
        _check(checks, "panel_keeps_the_four_state_switcher", False, "no panel surface measured")
    else:
        rect = panel.get("switcherRect") or {}
        client_w = (panel.get("viewport") or {}).get("clientW") or 0
        _check(checks, "panel_keeps_the_four_state_switcher",
               panel.get("switcherButtons") == 4 and panel.get("hudFrame") == "panel"
               and rect.get("width", 0) > 0 and rect.get("right", 9e9) <= client_w + VIEWPORT_TOLERANCE_PX,
               f"switcherButtons={panel.get('switcherButtons')} hudFrame={panel.get('hudFrame')} "
               f"switcher={json.dumps(rect)} clientWidth={client_w}")

    # --- CL-08's default entry, whose bottom-pinned 设置 was only ever an evidence-area claim ------
    daily = harvests.get("daily-home")
    labels = {b.get("label"): (b.get("rect") or {}).get("top") for b in (daily or {}).get("nav") or []}
    entry_tops = {label: labels.get(label) for label in DAILY_ENTRY_LABELS}
    _check(checks, "daily_renders_the_declared_entries",
           daily is not None and daily.get("shell") == "daily"
           and all(t is not None for t in entry_tops.values()),
           f"shell={daily and daily.get('shell')!r} entries="
           f"{json.dumps(entry_tops, ensure_ascii=False)}")
    settings_top = entry_tops.get("设置")
    others = [t for label, t in entry_tops.items() if label != "设置" and t is not None]
    _check(checks, "daily_settings_sits_below_the_declared_entries",
           bool(others) and settings_top is not None and settings_top > max(others),
           f"设置top={settings_top} others={json.dumps(others)} (底置 is a geometry claim: a nav that "
           "lists 设置 in reading order but paints it first fails here, not in prose)")

    # --- D2: a mounted view must not out-title the card, or the screen, that mounts it -------------
    carried_data = (harvests.get("daily-governance") or {}).get("carriedHeadings")
    if not isinstance(carried_data, dict):
        _check(checks, "carried_card_labels_outrank_the_mounted_view_titles", False,
               f"carriedHeadings came back as {type(carried_data).__name__}: the governance screen was "
               "never measured, so no claim about its heading order can be made")
    else:
        page_size = (carried_data.get("page") or {}).get("size") or 0
        painted = {c.get("id"): c.get("headings") or [] for c in carried_data.get("cards") or []}
        problems = []
        for cid, label in CARRIED_CARDS:
            heads = painted.get(cid)
            if heads is None:
                problems.append(f"{cid}: card absent")
                continue
            titled = [h for h in heads if h.get("text") == label]
            if not titled:
                problems.append(f"{cid}: label {label!r} not painted "
                                f"(headings={json.dumps([h.get('text') for h in heads], ensure_ascii=False)})")
                continue
            label_size = titled[0].get("size") or 0
            loudest = max((h.get("size") or 0) for h in heads)
            if label_size != loudest:
                problems.append(f"{cid}: a mounted view title ({loudest}px) is larger than the card "
                                f"label ({label_size}px)")
            if page_size and loudest >= page_size:
                problems.append(f"{cid}: {loudest}px reaches the page title ({page_size}px)")
        _check(checks, "carried_card_labels_outrank_the_mounted_view_titles", not problems,
               f"page={page_size}px cards={json.dumps({k: [h.get('size') for h in v] for k, v in painted.items()})} "
               + ("; ".join(problems) if problems else
                  "each card's declared label is its own loudest title, and none reaches the screen title"))

    served = FIXTURE_SNAPSHOT if payload is None else payload
    data_block = dict(data or {"source": "fixture"})
    data_block.update({
        "revision": served.get("revision"),
        "adapters": len(served.get("adapterCapabilities") or []),
        "projects": len(served.get("projects") or []),
        "executions": len(served.get("executions") or []),
    })
    return {"passed": all(c["pass"] for c in checks), "checks": checks,
            "surfaces": sorted(measured), "data": data_block}


# --------------------------------------------------------------------------- the run (impure)

def measure_all(geometry, u19, browser: str, fixture: SnapshotFixture,
                names: list[str], resolved_surfaces: list[dict] | None = None) -> dict[str, dict]:
    """One browser per surface, deliberately.

    A fresh document is what makes the measurement reproducible: this project's own evidence logs show a
    reused tab whose websocket dropped between creation and capture, and the fix there was a retry loop.
    `--window-size` cannot express a 150px window (Chrome clamps it), so the layout viewport is pinned
    through CDP device metrics, exactly as the floor view of the topbar gate is.
    """
    harvests: dict[str, dict] = {}
    for spec in (SURFACES if resolved_surfaces is None else resolved_surfaces):
        if spec["name"] not in names:
            continue
        url = fixture.url_for(spec["query"])
        width, height = spec["size"]
        # The pointer has to be placed inside the same session as the harvest: a second launch would be a
        # second document, and `:hover` lives on the element the live pointer is over.
        hover_arm = arm_expression_for(spec) if spec.get("hover") else None
        gear_ready = arm_expression_for(spec) if spec.get("openSettings") else None
        gear_arm = gear_arm_expression_for(spec) if spec.get("openSettings") else None
        if hover_arm or gear_arm:
            def after_mount(cdp, hover_arm=hover_arm, gear_ready=gear_ready, gear_arm=gear_arm,
                            spec=spec):
                if hover_arm:
                    place_real_pointer(cdp, hover_arm, spec)
                if gear_arm:
                    press_settings_gear(cdp, gear_ready, gear_arm)
        else:
            after_mount = None
        last: Exception | None = None
        for attempt in range(2):
            try:
                harvest = geometry.serve_and_eval(
                    ROOT, "/index.html", "1280,820", expression_for(spec), browser, u19, None,
                    viewport=(width, height), serve_url=url,
                    mount_selector=MOUNT_SELECTOR[spec["kind"]], after_mount=after_mount)
                harvest["_url"] = url
                harvests[spec["name"]] = harvest
                last = None
                break
            except Exception as exc:  # noqa: BLE001 — retried once, then reported by name
                last = exc
                time.sleep(1.0)
        if last is not None:
            raise RuntimeError(f"{spec['name']}: measure failed after retry: {last!r}")
    return harvests


def browser_leftovers(geometry) -> dict:
    """What the shared browser bootstrap could not clean up, and whether Chrome answered on a port
    other than the one it was asked for.

    Both travel with the receipt and get printed, never swallowed: ERR-140 exists for the habit of
    ignoring undeletable residue, and an undeleted `udf-*` profile from an earlier geometry run is still
    sitting in `.project-local/runs/geometry-gate` on the machine this gate was written on. A gate that
    leaves a browser profile behind and says nothing has told the reader less than it knows.
    """
    return {"residue": list(geometry.RESIDUE), "portAnnouncedMismatch": list(geometry.ANNOUNCED_MISMATCH)}


def main() -> int:
    # The details quote CJK labels, and a runner whose console code page cannot encode them would die
    # in the print, not in the product. (Precedent: half the tracked readback scripts already do this.)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=str(ROOT))
    ap.add_argument("--surface", action="append", default=None,
                    help="restrict to these surface names (default: every declared one)")
    ap.add_argument("--json-out", default=None)
    ap.add_argument("--snapshot-file", default=None,
                    help="serve this captured snapshot JSON instead of the declared fixture; the receipt "
                         "then names the real source and hashes the real bytes")
    args = ap.parse_args()
    names = args.surface or [s["name"] for s in SURFACES]
    unknown = sorted(set(names) - {s["name"] for s in SURFACES})
    if unknown:
        # Validated before anything is looked for on disk: a misspelled surface is bad input whatever
        # the machine happens to have built. Found on the runner, where the workflow-assistance job has
        # no `dist` at all and this check used to be reached only after the DIST_ABSENT refusal.
        print(f"HUD_STRIP_GATE_NOT_RUN UNKNOWN_SURFACE {json.dumps(unknown)}")
        return 2

    # Resolved before the browser is looked for: a snapshot that cannot be read is bad input whether or
    # not this machine has Chrome, and refusing here keeps the refusal from being mistaken for a missing
    # tool. The bytes are hashed so the receipt can bind its claims to the payload it actually served.
    payload = FIXTURE_SNAPSHOT
    data_block = {"source": "fixture"}
    if args.snapshot_file:
        snapshot_path = Path(args.snapshot_file)
        try:
            raw = snapshot_path.read_bytes()
            payload = json.loads(raw.decode("utf-8"))
        except (OSError, ValueError, UnicodeDecodeError) as exc:
            print(f"HUD_STRIP_GATE_NOT_RUN SNAPSHOT_UNREADABLE {type(exc).__name__} {exc}")
            return 2
        if not isinstance(payload, dict) or not (payload.get("adapterCapabilities") or []):
            print(f"HUD_STRIP_GATE_NOT_RUN SNAPSHOT_NO_ADAPTERS "
                  f"schemaVersion={payload.get('schemaVersion') if isinstance(payload, dict) else None!r} "
                  "(a payload with no adapter cards measures an empty strip, which no surface of this "
                  "product ships)")
            return 2
        data_block = {"source": "captured-snapshot", "path": str(snapshot_path.resolve()),
                      "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)}

    root = Path(args.root).resolve()
    if not (root / "apps" / "observer" / "frontend" / "dist" / "index.html").is_file():
        print(f"HUD_STRIP_GATE_NOT_RUN DIST_ABSENT {root / 'apps/observer/frontend/dist'}")
        return 3
    geometry = load_geometry()
    browser = geometry.find_browser()
    if not browser:
        print("HUD_STRIP_GATE_NOT_RUN BROWSER_NOT_FOUND "
              "set WL_CHROME to a Chrome/Edge binary; a named category is not a pass")
        return 3

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    # `serve_and_eval` writes each Chrome profile and its log under the geometry gate's own output dir;
    # asking it to open a log there without the dir existing fails as MEASURE_FAILED, which would look
    # like a product defect and is only this script having run on its own.
    geometry.OUT_DIR.mkdir(parents=True, exist_ok=True)
    u19 = load_u19(geometry)
    surfaces = resolve_surfaces(payload)
    fixture = SnapshotFixture(root / "apps" / "observer" / "frontend" / "dist", payload)
    fixture.start()
    try:
        try:
            harvests = measure_all(geometry, u19, browser, fixture, names, surfaces)
        except Exception as exc:  # noqa: BLE001
            print(f"HUD_STRIP_GATE_NOT_RUN MEASURE_FAILED {exc!r}")
            return 3
        result = verdict(harvests, surfaces, payload, data_block)
        result["startedAt"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
        result["browser"] = browser
        result["servedBundle"] = bundle_provenance.describe(root)
        result["fixturePort"] = fixture.port
        result["measured"] = harvests
        result.update(browser_leftovers(geometry))
        out = Path(args.json_out) if args.json_out else (
            OUT_DIR / f"hud_strip_{int(time.time())}.json")
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
        for c in result["checks"]:
            print(f"{c['check']:<52} {'PASS' if c['pass'] else 'FAIL'} {c['detail']}")
        served = result["data"]
        identity = f"sha256={served['sha256'][:12]}," if served.get("sha256") else ""
        print(f"HUD_STRIP_GATE_{'PASS' if result['passed'] else 'FAIL'} "
              f"checks={sum(1 for c in result['checks'] if c['pass'])}/{len(result['checks'])} "
              f"data={served['source']}({identity}"
              f"adapters={served['adapters']},"
              f"projects={served['projects']},executions={served['executions']}) "
              + str(out))
        for label, items in (("RESIDUE", result["residue"]),
                             ("PORT_MISMATCH", result["portAnnouncedMismatch"])):
            if items:
                print(f"HUD_STRIP_GATE_{label} " + json.dumps(items, ensure_ascii=False))
        return 0 if result["passed"] else 1
    finally:
        fixture.stop_server()


if __name__ == "__main__":
    sys.exit(main())
