#!/usr/bin/env python
"""Desktop geometry gate — measure the shipped bundle in a real browser and PASS or FAIL.

This instrument existed as a one-off measurement: it printed numbers, returned None, and nothing in
CI or in a test ever referenced it. That is the G3 finding in the UI prompt pack — a geometry probe
that cannot fail is not a gate. It is now a gate with three deliberate properties:

  1. the verdict is a PURE function of the measured geometry, so it is unit-testable without a
     browser, and the assertions are reviewable as text rather than as a screenshot;
  2. the browser is DISCOVERED, never assumed (env WL_CHROME, then PATH, then the vendor default
     install dirs). If none is found the script exits 3 and prints `GEOMETRY_GATE_NOT_RUN
     BROWSER_NOT_FOUND` — a named category, not a silent zero;
  3. the project root is resolved from this file, not hardcoded to the author's machine.

Silent by design: headless Chromium over CDP against the built `dist`, so the numbers come from the
same bundle the release binary embeds, without putting a window on the owner's desktop.

Exit: 0 GEOMETRY_GATE_PASS, 1 GEOMETRY_GATE_FAIL, 2 bad input, 3 GEOMETRY_GATE_NOT_RUN.
"""
from __future__ import annotations

import argparse
import base64
import importlib.util
import json
import os
import re
import socket
import shutil
import subprocess
import sys
import time
import urllib.parse
from pathlib import Path

LISTEN_RE = re.compile(r"DevTools listening on ws://127\.0\.0\.1:(\d+)")

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "audit"))
import bundle_provenance  # noqa: E402  # every receipt names the bytes the browser loaded
OBS = ROOT / "apps" / "observer"
DIST = OBS / "frontend" / "dist"
OUT_DIR = ROOT / ".project-local" / "runs" / "geometry-gate"
# The shell root both this gate and the legibility probe measure, and the bound they will wait for it.
# 24 s, not 3.4 s: the budget is the runner's cold boot, not the development host's.
MOUNT_SELECTOR = ".app"
MOUNT_BUDGET_S = 24.0
MOUNT_POLL_S = 0.5

SELECTORS = [".app", ".topbar", ".search", ".top-actions", ".topbar-brand", ".winctl",
             ".winctl-btn", ".sidebar", ".main", ".kpi-grid", "body"]

# `top-actions` is the control row a user must be able to reach; a rule that hides it below some
# width is exactly the phone behaviour this shell no longer ships.
EXPR = """JSON.stringify((()=>{
  const out = {};
  for (const sel of SELECTORS) {
    const els = [...document.querySelectorAll(sel)];
    if (!els.length) { out[sel] = {absent: true}; continue; }
    out[sel] = els.slice(0,6).map(el=>{
      const r = el.getBoundingClientRect();
      const cs = getComputedStyle(el);
      return {
        left: Math.round(r.left*10)/10, right: Math.round(r.right*10)/10,
        top: Math.round(r.top*10)/10, bottom: Math.round(r.bottom*10)/10,
        width: Math.round(r.width*10)/10, height: Math.round(r.height*10)/10,
        gapToViewportRight: Math.round((innerWidth - r.right)*10)/10,
        display: cs.display,
      };
    });
  }
  out.__viewport = innerWidth + 'x' + innerHeight;
  out.__innerWidth = innerWidth;
  // Read by the display-scaling instrument: the layout checks below would still pass at a scale the
  // browser never applied, and a sweep of four identical rasterisations looks like four DPIs.
  out.__dpr = window.devicePixelRatio;
  out.__docScrollWidth = document.documentElement.scrollWidth;
  out.__elementsOverlappingRightEdge = [...document.querySelectorAll('body *')]
      .filter(e=>{const r=e.getBoundingClientRect();
        return r.width>0 && r.right > innerWidth - 2 && r.left < innerWidth - 2;})
      .slice(0,12).map(e=>e.tagName+'.'+(typeof e.className==='string'?e.className:'')
        +' right='+Math.round(e.getBoundingClientRect().right));
  const nav = document.querySelector('.nav');
  if (nav) {
    // Reachability, not presence. A rail that declares `overflow:auto` but is as tall as its content
    // cannot scroll, so everything past the fold is unreachable by pointer, keyboard or wheel -- the
    // shape the shipped skin had for a week while every "is it in the DOM" check stayed green.
    const buttons = Array.from(nav.querySelectorAll('button[data-lane]'));
    const disclosures = nav.querySelectorAll('.nav-group-toggle[aria-expanded]');
    const inView = (list) => list.filter((b) => {
      const r = b.getBoundingClientRect();
      return r.top >= 0 && r.bottom <= innerHeight;
    }).length;
    const atTop = inView(buttons);
    const overflow = nav.scrollHeight > nav.clientHeight + 1;
    nav.scrollTop = nav.scrollHeight;
    const afterScroll = inView(buttons);
    let lastHitInside = false;
    const last = buttons[buttons.length - 1];
    if (last) {
      const r = last.getBoundingClientRect();
      const hit = document.elementFromPoint(r.x + r.width / 2, r.y + r.height / 2);
      lastHitInside = !!(hit && last.contains(hit)) && r.top >= 0 && r.bottom <= innerHeight;
    }
    nav.scrollTop = 0;
    // Three things a container-level check cannot see, per lane: whether it carries a name at all,
    // how big its target is, and what it actually spells. A rail of 23 identical labels is one button
    // short of navigation, and a 0x0 lane inside a collapsed group must not be convicted for a state
    // that renders nothing -- so the boxes go out raw and the floor is applied in Python.
    const nameless = buttons.filter((b) => {
      const text = (b.textContent || '').trim();
      const named = (b.getAttribute('aria-label') || '').trim() || (b.getAttribute('title') || '').trim();
      return !text && !named;
    }).map((b) => b.getAttribute('data-lane'));
    const labels = buttons.map((b) => (b.textContent || '').trim());
    const targets = buttons.map((b) => {
      const r = b.getBoundingClientRect();
      return { lane: b.getAttribute('data-lane'),
               w: Math.round(r.width * 10) / 10, h: Math.round(r.height * 10) / 10 };
    });
    out.__navReach = { total: buttons.length, atTop, afterScroll, overflow, lastHitInside,
                       disclosures: disclosures.length,
                       clientH: nav.clientHeight, scrollH: nav.scrollHeight,
                       nameless, labels, targets };
  }
  const actionsEl = document.querySelector('.top-actions');
  if (actionsEl) {
    // One band, one row. A wrapping action row is the shape that hid the fold entirely: the controls
    // were all present, all "visible", and stacked into a column nobody designed. The off-screen
    // measuring sizer is excluded — it lives at top:-9999px by design, and counting it invented a
    // second row on every measurement.
    const kids = Array.from(actionsEl.children).filter((c) => {
      if (c.classList.contains('action-sizer')) return false;
      const r = c.getBoundingClientRect();
      return r.width > 0 || r.height > 0;
    });
    const tops = new Set(kids.map((c) => Math.round(c.getBoundingClientRect().top)));
    out.__actionsFit = { children: kids.length, rows: tops.size,
                         more: !!actionsEl.querySelector('.action-more') };
  }
  // Region boundaries. `.main` is a full-height column by design and the bar floats over its first
  // rows, so "does main start below the bar" is the wrong question and would fail the intended
  // layout. What a user needs is (a) the first content region clearing the bar, and (b) the bar
  // actually drawing an edge — a boundary that is only implied by whitespace disappears the moment a
  // panel scrolls under it.
  const edgeOf = (sel) => {
    const el = document.querySelector(sel);
    if (!el) return { absent: true };
    const cs = getComputedStyle(el);
    const r = el.getBoundingClientRect();
    return { top: Math.round(r.top * 10) / 10, bottom: Math.round(r.bottom * 10) / 10,
             borderBottomWidth: cs.borderBottomWidth, borderBottomStyle: cs.borderBottomStyle,
             borderBottomColor: cs.borderBottomColor, boxShadow: cs.boxShadow };
  };
  out.__edges = { topbar: edgeOf('.topbar'), content: edgeOf('.content'), main: edgeOf('.main') };
  // Region A and B controls: SCREEN_SPEC's target rule is about these, and it has never been measured.
  const boxOf = (sel) => Array.from(document.querySelectorAll(sel)).map((e) => {
    const r = e.getBoundingClientRect();
    return { sel: sel, painted: e.getClientRects().length > 0,
             w: Math.round(r.width * 10) / 10, h: Math.round(r.height * 10) / 10 };
  });
  out.__barTargets = [...boxOf('.top-actions button'), ...boxOf('.winctl-btn'), ...boxOf('.search')];
  // The deleted phone surface, looked for by the names it used and the names a rewrite would pick.
  // This is the check that exists because I built the thing it forbids: an icon rail, then a drawer,
  // both chasing a standard row that contradicted an owner decision.
  // Every painted element that ellipsises its own text, with how much it loses and whether the whole
  // string survives somewhere a reader can reach. A rect check cannot see this class at all: the box
  // is present, sized and inside the viewport, it simply says less than it means.
  out.__clippedText = (() => {
    const list = [];
    for (const el of document.querySelectorAll('body *')) {
      if (!el.getClientRects().length) continue;
      const cs = getComputedStyle(el);
      if (cs.textOverflow !== 'ellipsis' || cs.overflow === 'visible') continue;
      const lost = el.scrollWidth - el.clientWidth;
      if (lost <= 1) continue;
      const raw = (el.textContent || '').trim().replace(/[….]+$/g, '').trim();
      let fallback = (el.getAttribute('title') || '').trim();
      for (let a = el.parentElement; a && !fallback; a = a.parentElement) {
        fallback = (a.getAttribute('aria-label') || a.getAttribute('title') || '').trim();
      }
      list.push({ tag: el.tagName, cls: String(el.className).slice(0, 60), text: raw.slice(0, 28),
                  lostPx: Math.round(lost), fontSize: cs.fontSize,
                  carried: !!fallback && fallback.indexOf(raw) >= 0 });
    }
    return list;
  })();
  out.__mobileNav = Array.from(document.querySelectorAll(
      '.mobile-nav, .topbar-mobile, .rail-toggle, .rail-scrim, .rail-close, [data-mobile-nav]'))
    .filter((e) => e.getClientRects().length > 0)
    .map((e) => String(e.className));
  // 2.4.11 Focus Not Obscured (Minimum): focus a control and hit-test its own centre. A control that
  // is visible but sits under an overlay fails "reachable" for a keyboard user, and no rect check on
  // the container can see that. The search field is an ARIA button (`role=button tabIndex=0`), not an
  // input — probing `.search input` found nothing and silently left the region's primary control out.
  // The disclosure toggle is probed because group collapse means `.nav button[data-lane]` may render
  // nothing at all at first paint, and an empty probe list must not read as "nothing obscured".
  const probes = ['.search[role="button"], .search', '.top-actions button', '.winctl-btn',
                  '.nav button[data-lane]', '.nav .nav-group-toggle'];
  out.__focusObscured = [];
  for (const sel of probes) {
    const el = document.querySelector(sel);
    if (!el) continue;
    el.focus();
    const r = el.getBoundingClientRect();
    const hit = document.elementFromPoint(r.x + r.width / 2, r.y + r.height / 2);
    out.__focusObscured.push({
      sel: sel, focused: document.activeElement === el,
      top: Math.round(r.top * 10) / 10, bottom: Math.round(r.bottom * 10) / 10,
      visible: r.width > 0 && r.height > 0,
      // Off-screen is not obscured. A lane below the rail's fold has nothing at its centre because the
      // centre is outside the window; calling that a focus violation would convict the one control
      // class `nav_items_reachable` exists to protect.
      inViewport: r.top >= 0 && r.bottom <= innerHeight && r.left >= 0 && r.right <= innerWidth,
      hitIsSelfOrChild: !!(hit && (hit === el || el.contains(hit))),
    });
  }
  return out;
})())"""

TOPBAR_MAX_HEIGHT = 140.0
# The two windows are different surfaces with different sizes, so each is measured at its own
# declared shape: the main window at its default 1280x820, the floating panel at the 440x680
# non-resizable size tauri.conf.json gives it. Measuring the compact layout at desktop width would
# have proved nothing about the panel — the first PASS this script produced did exactly that, and
# the per-view height bound below is what a 440px bar actually needs.
# 680, not the 780 this mirror carried until 2026-10-13: a non-resizable window's declared size IS
# its physical demand, so 780 logical needed 1560 physical at 200% scaling and did not fit a
# 2560x1392 work area. 680 needs 1360. The mirror follows the declaration; measuring the old shape
# would have measured a surface the product no longer ships.
WIN_SIZE = {"full": "1280,820", "compact": "440,680", "floor": "1280,820"}
MAX_HEIGHT = {"full": 140.0, "compact": 260.0, "floor": 140.0}
RAIL_MIN_WIDTH = 200.0
# `floor` is the MAIN shell at the smallest size the shipped product can be resized into. tauri.conf.json
# gives that window minWidth 900 / minHeight 600 and the 440x680 surface is the rail-less HUD, so there
# is no narrow rail state to design for: SCREEN_SPEC's old "< 760px: icon rail or drawer" row described
# a phone shape the owner deleted on 2026-10-07, and tests/ci/test_desktop_only_shell.py pins the floor.
SHELL_VIEW = {"full": "full", "compact": "compact", "floor": "full"}
# `--window-size` sizes the OUTER window, so the LAYOUT viewport is pinned through CDP device metrics.
VIEWPORT = {"full": None, "compact": None, "floor": (900, 600)}
# WCAG 2.5.8 Target Size (Minimum). The desktop product has no touch band, so 24x24 is the normative
# floor; the larger 44px figure SCREEN_SPEC once carried belonged to the deleted phone row.
MIN_TARGET_PX = 24.0
RESIDUE: list[str] = []
ANNOUNCED_MISMATCH: list[str] = []


def load_u19():
    """Reuse the CDP client the release line already trusts, rather than a second websocket stack."""
    path = OBS / "scripts" / "u19_webview_e2e.py"
    spec = importlib.util.spec_from_file_location("u19", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[attr-defined]
    return module


def find_browser() -> str | None:
    env = os.environ.get("WL_CHROME") or os.environ.get("CHROME_PATH")
    candidates: list[str | None] = [env] if env else []
    candidates += [shutil.which(name) for name in
                   ("chrome", "chrome.exe", "msedge", "msedge.exe", "chromium", "chromium-browser")]
    for base in (os.environ.get("PROGRAMFILES"), os.environ.get("PROGRAMFILES(X86)")):
        if not base:
            continue
        candidates += [str(Path(base) / "Google/Chrome/Application/chrome.exe"),
                       str(Path(base) / "Microsoft/Edge/Application/msedge.exe")]
    for cand in candidates:
        if cand and Path(cand).is_file():
            return cand
    return None


def _send(ws: socket.socket, payload: bytes) -> None:
    """Client frames must be masked (RFC 6455); no padding, so every length fits 8 or 16 bytes."""
    header = bytearray([0x81])
    n = len(payload)
    if n < 126:
        header.append(0x80 | n)
    else:
        header.append(0x80 | 126)
        header += n.to_bytes(2, "big")
    mask = bytes([0x37, 0x7A, 0x51, 0x29])
    header += mask
    ws.sendall(bytes(header) + bytes(b ^ mask[i % 4] for i, b in enumerate(payload)))


def _recv_text(ws: socket.socket, wanted_id: int, timeout: float) -> str:
    """Read frames until the response for `wanted_id` arrives, skipping event frames."""
    deadline = time.time() + timeout
    buffer = bytearray()

    def one_frame() -> bytes | None:
        nonlocal buffer
        while len(buffer) < 2:
            chunk = ws.recv(4096)
            if not chunk:
                return None
            buffer += chunk
        b1, b2 = buffer[0], buffer[1]
        length = b2 & 0x7F
        offset = 2
        if length == 126:
            while len(buffer) < offset + 2:
                buffer += ws.recv(4096)
            length = int.from_bytes(buffer[offset:offset + 2], "big")
            offset += 2
        elif length == 127:
            while len(buffer) < offset + 8:
                buffer += ws.recv(4096)
            length = int.from_bytes(buffer[offset:offset + 8], "big")
            offset += 8
        while len(buffer) < offset + length:
            buffer += ws.recv(4096)
        payload = bytes(buffer[offset:offset + length])
        del buffer[:offset + length]
        return payload if (b1 & 0x0F) in (0x1, 0x2) else b""

    while time.time() < deadline:
        frame = one_frame()
        if frame is None:
            break
        if not frame:
            continue
        try:
            message = json.loads(frame.decode("utf-8", "replace"))
        except json.JSONDecodeError:
            continue
        if message.get("id") == wanted_id:
            if "error" in message:
                raise RuntimeError(f"CDP error: {message['error']}")
            return json.dumps(message)
    raise RuntimeError(f"no CDP response for id={wanted_id} before {timeout}s")


class ChromeCDP:
    """Minimal CDP-over-WebSocket client for the headless browser this gate drives.

    u19's client targets WebView2 through a proxy and is left alone (changing it would put the
    release line's desktop evidence at risk for a quirk that belongs to Chrome). Chrome 154 stalls
    any DevTools HTTP request without a User-Agent, or with a port in Host — measured side by side
    against one instance — so discovery uses `cdp_list`, and the websocket handshake below sends the
    headers a browser expects.
    """

    def __init__(self, ws_url: str, timeout: float = 60.0) -> None:
        parts = urllib.parse.urlsplit(ws_url)
        host, _, port = parts.netloc.partition(":")
        # The socket's per-read timeout IS the answer budget. It used to be a hardcoded 10 s while
        # `self.timeout` (the frame-skipping loop's deadline) was 60 s, so a caller could raise its budget
        # to 300 s and still die inside a single `recv`: a long expression that emits no websocket frame for
        # >10 s (the whole-rail sweep does this on a runner) produced `TimeoutError: timed out` from
        # `_recv_text`/`one_frame`, twice in a row and identically — a threshold, not a race.
        # Measured 2026-10-21 at ff3348bf (run 39668208804), where the traceback named those two frames.
        self.sock = socket.create_connection((host, int(port or 9222)), timeout=timeout)
        key = base64.b64encode(os.urandom(16)).decode()
        path = parts.path + ("?" + parts.query if parts.query else "")
        request = (f"GET {path} HTTP/1.1\r\nHost: {parts.netloc}\r\nUpgrade: websocket\r\n"
                   f"Connection: Upgrade\r\nSec-WebSocket-Key: {key}\r\n"
                   f"Sec-WebSocket-Version: 13\r\nUser-Agent: worklab-geometry-gate\r\n\r\n")
        self.sock.sendall(request.encode("latin-1"))
        handshake = b""
        while b"\r\n\r\n" not in handshake:
            piece = self.sock.recv(4096)
            if not piece:
                raise RuntimeError("websocket handshake closed")
            handshake += piece
        status = handshake.split(b"\r\n", 1)[0].decode("latin-1", "replace")
        if "101" not in status:
            raise RuntimeError(f"websocket handshake failed: {status}")
        self._id = 0
        self.timeout = timeout

    def send(self, method: str, params: dict | None = None) -> dict:
        self._id += 1
        _send(self.sock, json.dumps({"id": self._id, "method": method,
                                     "params": params or {}}).encode("utf-8"))
        return json.loads(_recv_text(self.sock, self._id, self.timeout)).get("result", {})

    def evaluate(self, expression: str) -> str:
        result = self.send("Runtime.evaluate",
                           {"expression": expression, "returnByValue": True, "awaitPromise": True})
        if result.get("exceptionDetails"):
            raise RuntimeError(f"evaluate threw: {json.dumps(result['exceptionDetails'])[:400]}")
        value = result.get("result", {}).get("value")
        if value is None:
            # A missing value is not an empty measurement: report what the debugger did return
            # rather than letting json.loads(None) become the error message.
            raise RuntimeError(f"evaluate produced no value: {json.dumps(result)[:400]}")
        return value

    def close(self) -> None:
        try:
            self.sock.close()
        except OSError:
            pass


def _first(measured: dict, selector: str) -> dict | None:
    value = measured.get(selector)
    if isinstance(value, list) and value:
        return value[0]
    return None


def _px(value: object) -> float:
    """`'1px'`/`'0.8px'`/`'calc(1px + 2px)'` to a number; anything unreadable is 0, never a silent pass."""
    match = re.search(r"[\d.]+", str(value or ""))
    return float(match.group(0)) if match else 0.0


def verdict(measured: dict, view: str) -> dict:
    """Pure: no browser, no filesystem. Every check is one line of the acceptance contract."""
    width = measured.get("__innerWidth") or 0
    checks: list[dict] = []

    def add(name: str, ok: bool, detail: str) -> None:
        checks.append({"check": name, "pass": bool(ok), "detail": detail})

    scroll = measured.get("__docScrollWidth") or 0
    add("no_horizontal_overflow", scroll <= width + 1, f"scrollWidth={scroll} innerWidth={width}")

    topbar = _first(measured, ".topbar")
    add("topbar_measured", topbar is not None,
        f"height={topbar['height'] if topbar else None} element={'found' if topbar else 'MISSING'}")
    if topbar:
        add("topbar_not_stacked", topbar["height"] <= MAX_HEIGHT[view],
            f"height={topbar['height']} limit={MAX_HEIGHT[view]}")

    brand = _first(measured, ".topbar-brand")
    add("brand_mark_present", bool(brand) and brand["width"] > 0,
        f"brand={brand and brand['width']}")

    actions = _first(measured, ".top-actions")
    add("actions_visible", bool(actions) and actions.get("display") != "none",
        f"display={actions.get('display') if actions else None}")

    clipped = [e for e in (measured.get(".winctl-btn") or []) if isinstance(e, dict)
               and e.get("gapToViewportRight", 0) < -1]
    add("window_controls_reachable", bool(measured.get(".winctl-btn")) and not clipped,
        f"clipped={json.dumps(clipped, ensure_ascii=False)[:200]}")

    raw_actions = measured.get(".top-actions")
    action_rows = [e for e in (raw_actions if isinstance(raw_actions, list) else [])
                   if isinstance(e, dict)]
    unexpected_actions = raw_actions is not None and not isinstance(raw_actions, list)
    clipped_actions = [e for e in action_rows if e.get("gapToViewportRight", 0) < -1]
    first_actions = _first(measured, ".top-actions")
    add("action_row_inside_viewport", not clipped_actions and not unexpected_actions,
        f"gap={first_actions and first_actions.get('gapToViewportRight')} "
        f"shape={type(raw_actions).__name__} rows={len(action_rows)}"
        + (" -- the harvest returned something that is not a list of boxes; the gate cannot read it and "
           "refuses to call an unreadable shape a pass" if unexpected_actions else ""))

    fit = measured.get("__actionsFit") or {}
    if fit:
        # A band that paints nothing is not "one row" — that is the pinned skin's `display:none` branch,
        # and an empty action band must not be reported as a folded one.
        add("action_row_does_not_stack", bool(fit.get("children")) and fit.get("rows") == 1,
            f"children={fit.get('children')} rows={fit.get('rows')} foldTrigger={fit.get('more')}")

    rail = _first(measured, ".sidebar")
    reach = measured.get("__navReach") or {}
    # Asserted for EVERY window including the 440px HUD — that is the width at which a phone
    # navigation surface would most plausibly come back.
    add("no_mobile_navigation_surface_is_painted",
        measured.get("__mobileNav") == [],
        f"view={view} painted={json.dumps(measured.get('__mobileNav') or [], ensure_ascii=False)[:220]}")
    if view == "compact":
        add("compact_has_no_rail", rail is None, f"rail={rail}")
    else:
        # The desktop-only contract, asserted at BOTH sizes the main window can take: the rail is the
        # only navigation surface, so it must survive the minimum window as a text rail.
        add("rail_always_present", bool(rail) and rail["width"] >= RAIL_MIN_WIDTH,
            f"rail={rail and rail['width']} min={RAIL_MIN_WIDTH}")
        add("rail_at_left_edge", bool(rail) and rail["left"] <= 1, f"left={rail and rail['left']}")
        total = reach.get("total") or 0
        if not total:
            add("nav_items_reachable", False, "no .nav button measured; the rail rendered nothing")
        else:
            fits = reach.get("atTop") == total
            scrolls = bool(reach.get("overflow"))
            last_reachable = reach.get("lastHitInside") is True
            add("nav_items_reachable", fits or (scrolls and last_reachable),
                f"total={total} atTop={reach.get('atTop')} afterScroll={reach.get('afterScroll')} "
                f"overflow={scrolls} clientH={reach.get('clientH')} scrollH={reach.get('scrollH')} "
                f"lastHitInside={last_reachable}")
            # A scroll box alone still leaves a 600px-tall window showing a third of the rail. APG
            # Disclosure Navigation is the other half: every group caption is a button that carries
            # aria-expanded, so the rail can be shortened as well as scrolled.
            add("nav_groups_are_disclosures", (reach.get("disclosures") or 0) > 0,
                f"disclosures={reach.get('disclosures')}")
            # Identity, per lane: a name in the accessibility tree, a string on screen that no other
            # lane spells, and a target the pointer can land on.
            add("every_lane_is_named", not reach.get("nameless"),
                f"total={total} nameless={json.dumps(reach.get('nameless'), ensure_ascii=False)}")
            labels = list(reach.get("labels") or [])
            blank = [i for i, s in enumerate(labels) if not s]
            dupes = sorted({s for s in labels if labels.count(s) > 1})
            add("lane_labels_are_distinguishable", bool(labels) and not blank and not dupes,
                f"lanes={len(labels)} blank={blank} "
                f"duplicated={json.dumps(dupes, ensure_ascii=False)}")
            boxes = [t for t in (reach.get("targets") or []) if t.get("w") and t.get("h")]
            small = [{"lane": t["lane"], "min": round(min(t["w"], t["h"]), 1)}
                     for t in boxes if min(t["w"], t["h"]) < MIN_TARGET_PX]
            add("lane_targets_meet_the_floor", bool(boxes) and not small,
                f"measured={len(boxes)} of {total} offenders="
                f"{json.dumps(small, ensure_ascii=False)} min={MIN_TARGET_PX}")
        if view == "floor":
            bar = [t for t in (measured.get("__barTargets") or []) if t.get("painted")]
            small_bar = [{"sel": t["sel"], "w": t["w"], "h": t["h"]} for t in bar
                         if min(t["w"], t["h"]) < MIN_TARGET_PX]
            add("top_bar_targets_meet_the_floor", bool(bar) and not small_bar,
                f"controls={len(bar)} offenders={json.dumps(small_bar, ensure_ascii=False)[:220]} "
                f"min={MIN_TARGET_PX}")

    # --- region boundaries: the last assertion family SCREEN_SPEC owed -------------------------
    edges = measured.get("__edges") or {}
    topbar_edge = edges.get("topbar") or {}
    content_edge = edges.get("content") or {}
    if not topbar_edge or topbar_edge.get("absent") or not content_edge or content_edge.get("absent"):
        add("content_clears_topbar", False,
            f"a region rendered nothing: topbar={json.dumps(topbar_edge)} content={json.dumps(content_edge)}")
        add("topbar_edge_is_painted", False, "the topbar was not measured, so its edge cannot be either")
    else:
        overlap = round(topbar_edge["bottom"] - content_edge["top"], 1)
        add("content_clears_topbar", overlap <= 1.0,
            f"topbarBottom={topbar_edge['bottom']} contentTop={content_edge['top']} overlap={overlap}")
        border = (_px(topbar_edge.get("borderBottomWidth")) > 0
                  and str(topbar_edge.get("borderBottomStyle")) not in ("none", "hidden", "None"))
        shadow = str(topbar_edge.get("boxShadow") or "none") not in ("none", "")
        add("topbar_edge_is_painted", border or shadow,
            f"border={topbar_edge.get('borderBottomWidth')} {topbar_edge.get('borderBottomStyle')} "
            f"color={topbar_edge.get('borderBottomColor')} shadow={shadow}")

    clipped_text = [c for c in (measured.get("__clippedText") or []) if not c.get("carried")]
    add("no_text_is_clipped_without_a_fallback", not clipped_text,
        f"clipped={json.dumps(clipped_text, ensure_ascii=False)[:300]}")

    probes = measured.get("__focusObscured") or []
    # A probe that never reported `inViewport` is treated as being in it: absence must convict, not
    # excuse, or an older harvest shape would silently disarm the whole check.
    obscured = [p for p in probes if p.get("visible") and p.get("inViewport", True) and p.get("focused")
                and not p.get("hitIsSelfOrChild")]
    unfocusable = [p for p in probes if p.get("visible") and not p.get("focused")]
    add("focused_control_is_not_obscured", bool(probes) and not obscured,
        f"probed={len(probes)} obscured={len(obscured)} "
        + json.dumps([p.get("sel") for p in obscured], ensure_ascii=False))
    # A visible control that refuses focus is the other half of the same claim: it is not obscured,
    # it is simply unreachable, and reporting only the hit-test would call that a pass.
    add("every_visible_probe_takes_focus", not unfocusable,
        f"refused_focus={json.dumps([p.get('sel') for p in unfocusable], ensure_ascii=False)}")

    return {"view": view, "viewport": measured.get("__viewport"),
            "passed": all(c["pass"] for c in checks), "checks": checks,
            "overlappingRightEdge": measured.get("__elementsOverlappingRightEdge") or []}


def cdp_list(port: int, path: str = "/json/list") -> list[dict]:
    """Chrome 154's DevTools HTTP endpoint stalls a request that carries no User-Agent, or that puts
    a port in Host: the socket accepts and never answers. Measured side by side against one running
    instance — u19's raw GET timed out while the same bytes plus `User-Agent`/`Accept` and a portless
    Host returned HTTP/1.1 200 at once. u19 keeps its own shape because WebView2 is served by it;
    the browser this gate drives is Chrome, so the gate speaks Chrome."""
    s = socket.create_connection(("127.0.0.1", port), timeout=6)
    try:
        s.sendall(f"GET {path} HTTP/1.1\r\nHost: 127.0.0.1\r\nUser-Agent: worklab-geometry-gate\r\n"
                  f"Accept: application/json\r\nConnection: close\r\n\r\n".encode("latin-1"))
        raw = b""
        head = None
        expected = None
        while True:
            piece = s.recv(65536)
            if not piece:
                break
            raw += piece
            if head is None:
                split = raw.find(b"\r\n\r\n")
                if split == -1:
                    continue
                head, body_start = raw[:split], split + 4
                match = re.search(rb"Content-Length:\s*(\d+)", head, re.IGNORECASE)
                expected = int(match.group(1)) if match else None
            if expected is not None and len(raw) - (raw.find(b"\r\n\r\n") + 4) >= expected:
                break
    finally:
        s.close()
    if head is None:
        raise RuntimeError(f"CDP {path}: no response head ({raw[:80]!r})")
    status_line = head.split(b"\r\n", 1)[0].decode("latin-1", "replace")
    parts = status_line.split()
    if len(parts) < 2 or parts[1] != "200":
        raise RuntimeError(f"CDP {path}: HTTP {status_line}")
    body = raw[len(head) + 4:]
    if expected is not None and len(body) < expected:
        # A short read is not a Chrome quirk to tolerate: a JSON document cut mid-list is exactly how
        # a `page` target silently disappears, which is the failure this function used to report.
        raise RuntimeError(f"CDP {path}: truncated body {len(body)} of {expected}")
    return json.loads(body.decode("utf-8", "replace"))


def discover_page_ws(port: int, tries: int = 20) -> str:
    last: Exception | None = None
    seen: list[str] = []
    for _ in range(tries):
        try:
            targets = cdp_list(port)
        except Exception as exc:  # noqa: BLE001 — retried, but the last reason is always reported
            last = exc
            time.sleep(0.5)
            continue
        seen = [f"{t.get('type')}:{(t.get('url') or '')[:40]}" for t in targets]
        for target in targets:
            url = target.get("webSocketDebuggerUrl") or ""
            if target.get("type") == "page" and url:
                # Chrome builds that URL from the request's Host header, so it echoes back whatever
                # authority was used — including a portless one, which refuses on connect (measured:
                # `ws://127.0.0.1/devtools/page/…`). The port this function was given is the truth.
                path = urllib.parse.urlsplit(url).path
                return f"ws://127.0.0.1:{port}{path}"
        time.sleep(0.5)
    raise RuntimeError(f"no CDP page target on 127.0.0.1:{port}; last_error={last!r}; "
                       f"targets_seen={seen[:6]}")


def connect_with_retry(port: int, attempts: int = 6, evaluate_timeout_s: float = 60.0):
    """Re-discover the page target before each websocket attempt.

    A refused connect after a successful /json/list is not contradiction: the target list is a
    snapshot, and a page target that has just been replaced (navigation, a crash-reload, or the
    first-run window settling) stops answering on its port while the browser endpoint keeps serving.
    Re-fetching is what makes that a retry rather than a refusal, and the last reason is reported
    rather than swallowed.

    `evaluate_timeout_s` is how long one expression may take to ANSWER. Callers that harvest a whole
    rail in a single session must widen it — see `serve_and_eval`.
    """
    last_ws: str | None = None
    last_exc: Exception | None = None
    for _ in range(attempts):
        try:
            ws = discover_page_ws(port, tries=6)
            last_ws = ws
            return ChromeCDP(ws, timeout=evaluate_timeout_s), ws
        except (ConnectionRefusedError, OSError, RuntimeError) as exc:
            last_exc = exc
            time.sleep(1.0)
    raise RuntimeError(f"no usable CDP page session on port {port}; last_target={last_ws}; "
                       f"last_error={last_exc!r}")


def wait_for_mount(cdp, selector: str, budget_s: float, poll_s: float) -> tuple[int, bool]:
    """Poll until the shell root exists, and report how long that took.

    Measured 2026-10-21 at `79f48a54` on windows-latest: the FIRST session of the geometry job returned every
    selector as `{"absent": true}` — topbar, brand, rail, content — while the two sessions that followed it on
    the same bundle measured normally, and the same bundle passes all three views locally. The fixed 2.0 s +
    0.4 s + 1.0 s wait was written against the development host's boot time; on a cold runner a 487 kB bundle
    had not mounted yet when the expression ran, so a runner-side race came back as a product red. The gate
    refused, which is the correct behaviour for an unreadable shape — the missing piece was waiting.

    The wait is bounded and a timeout still returns False, so this cannot turn a genuinely broken render
    green: the selectors stay absent and the gate still reds, only now it also says how long it waited.
    """
    started = time.monotonic()
    probe = f"!!document.querySelector({json.dumps(selector)})"
    while True:
        try:
            if cdp.evaluate(probe) is True:
                return int((time.monotonic() - started) * 1000), True
        except Exception:  # noqa: BLE001 -- a session that has not answered yet is still "not mounted"
            pass
        elapsed = time.monotonic() - started
        if elapsed >= budget_s:
            return int(elapsed * 1000), False
        time.sleep(poll_s)


def serve_and_eval(root: Path, path: str, window_size: str, expr: str, browser: str,
                   u19, shot: Path | None = None, viewport: tuple[int, int] | None = None,
                   scale_factor: float = 1.0, serve_url: str | None = None,
                   mount_selector: str = MOUNT_SELECTOR,
                   evaluate_timeout_s: float = 60.0,
                   after_mount=None) -> dict:
    """Serve the built `dist` and evaluate one expression in a headless Chrome.

    This is the browser bootstrap, not a topbar-specific step: a second instrument (the legibility
    probe) needs the same silent headless session over the same bundle, and copying forty lines of
    port-picking, log-parsing and profile-cleanup is how two instruments start disagreeing about
    when the browser was ready. `measure()` below is one call to this function.

    The caller passes a `path`, not a URL, because the port is chosen here — a caller that had to
    guess the port would be guessing the measurement.

    `viewport` pins the *layout* viewport through CDP device metrics. `--window-size` is the outer
    window: asking for 1280 yields an inner width of 1262, and asking for 430 yields 482, because
    Chrome clamps a too-narrow window instead of refusing. A measurement taken at a width the browser
    never had is not a measurement of that width.

    `scale_factor` is the device-scale half of the same override, for the display-scaling instrument.
    It only reaches the page when `viewport` is passed, because CDP has no "raster only" mode. What it
    changes is the raster density and `window.devicePixelRatio`; the CSS pixel grid a layout runs on is
    decided by `viewport`, so a caller emulating 150% display scaling on a 2560px screen passes
    width=1706 (the CSS width the OS actually gives the window), not 2560 with a hopeful comment.
    """
    port = u19.pick_free_port()
    srv = None
    if serve_url is not None:
        # The page comes from its own server. `path` is ignored: a caller that passes a full URL has
        # already decided which origin renders, and pretending to serve `dist` beside it would leave a
        # second, unused listener holding a port this instrument claims to have chosen.
        url = serve_url
    else:
        url = f"http://127.0.0.1:{port}{path}"
        srv = subprocess.Popen([sys.executable, "-m", "http.server", str(port), "--bind", "127.0.0.1"],
                               cwd=str(root / "apps/observer/frontend/dist"),
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    udf = OUT_DIR / f"udf-{int(time.time())}-{os.getpid()}"
    log_path = OUT_DIR / f"chrome-{int(time.time())}-{os.getpid()}.log"
    requested_cdp = u19.pick_free_port()
    # Request a specific port and then believe what Chrome announces. `--remote-debugging-port=0`
    # announces a websocket port but serves no /json HTTP endpoint there, so discovery times out;
    # a requested port can also be re-bound by Chrome if the reservation races, and then the
    # requested number is the wrong one to query. The log line is the only authority.
    with log_path.open("wb") as log:
        proc = subprocess.Popen(
            [browser, "--headless=new", "--disable-gpu", "--no-sandbox",
             # Without these the profile's first-run UI wins and no page target appears in time.
             "--no-first-run", "--no-default-browser-check", "--disable-extensions",
             f"--user-data-dir={udf}", f"--window-size={window_size}",
             f"--remote-debugging-port={requested_cdp}", "--remote-allow-origins=*", url],
            stdout=log, stderr=subprocess.STDOUT)
        cdp_port = None
        # 90 seconds, not 25 (measured 2026-10-16 on GitHub's windows-latest via PRs #166/#167): on a cold
        # runner Chrome can stay alive without ever announcing its line inside 25s, which made the gate report
        # MEASURE_FAILED on a tree that was fine -- and the operator's only recourse was re-running CI by hand.
        # The wait is bounded and the failure still names itself; what changed is the budget and the evidence.
        deadline = time.time() + 90
        while time.time() < deadline and cdp_port is None:
            time.sleep(0.5)
            match = LISTEN_RE.search(log_path.read_text(encoding="utf-8", errors="replace"))
            if match:
                cdp_port = int(match.group(1))
            if proc.poll() is not None:
                raise RuntimeError(f"chrome exited rc={proc.returncode}: "
                                   f"{log_path.read_text(encoding='utf-8', errors='replace')[:400]}")
        if cdp_port is None:
            # The old message carried no log content at all, so "Chrome never announced" and "Chrome announced
            # something we did not parse" were indistinguishable from the outside. The tail is the difference.
            tail = log_path.read_text(encoding="utf-8", errors="replace")[-600:]
            proc.kill()
            if srv is not None:
                srv.kill()
            raise RuntimeError(f"no `DevTools listening on` line within 90s; "
                               f"chrome rc={proc.returncode}; log tail: {tail!r}")
        if cdp_port != requested_cdp:
            ANNOUNCED_MISMATCH.append(f"requested {requested_cdp}, announced {cdp_port}")
        time.sleep(2.0)  # the page target appears once the document has loaded
        try:
            cdp, _ws = connect_with_retry(cdp_port, evaluate_timeout_s=evaluate_timeout_s)
            try:
                cdp.send("Page.enable")
                if viewport is not None:
                    cdp.send("Emulation.setDeviceMetricsOverride",
                             {"width": viewport[0], "height": viewport[1],
                              "deviceScaleFactor": scale_factor, "mobile": False})
                    time.sleep(0.4)   # the reflow has to land before anything is measured
                waited_ms, mounted = wait_for_mount(cdp, mount_selector,
                                                    MOUNT_BUDGET_S, MOUNT_POLL_S)
                if after_mount is not None:
                    # A caller that has to put the page into a state before reading it (forcing a pseudo
                    # class over the CSS domain, say) needs a command slot, not a second expression: the
                    # alternative is copying this launch, and two copies of the readiness wait is how two
                    # instruments start disagreeing about when the browser was ready.
                    after_mount(cdp)
                raw = cdp.evaluate(expr)
                if shot is not None:
                    data = cdp.send("Page.captureScreenshot", {"format": "png"}).get("data", "")
                    shot.write_bytes(base64.b64decode(data))
                parsed = json.loads(raw)
                if isinstance(parsed, dict):
                    # The wait travels with the numbers, so a later red can be told apart from a cold runner.
                    parsed["readyWait"] = {"ms": waited_ms, "mounted": mounted,
                                           "selector": mount_selector,
                                           "budgetMs": int(MOUNT_BUDGET_S * 1000),
                                           "evaluateTimeoutS": evaluate_timeout_s}
                return parsed
            finally:
                cdp.close()
        finally:
            proc.kill()
            if srv is not None:
                srv.kill()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                RESIDUE.append(f"{udf} chrome did not exit within 10s")
            _release_profile(udf)


def measure(root: Path, view: str, browser: str, u19, shot: Path | None) -> dict:
    return serve_and_eval(
        root, f"/index.html?view={SHELL_VIEW[view]}&mode=UNKNOWN&theme=dark&shell=tauri",
        WIN_SIZE[view], EXPR.replace("SELECTORS", json.dumps(SELECTORS)), browser, u19, shot,
        viewport=VIEWPORT[view])


def _release_profile(udf: Path, attempts: int = 12, pause: float = 0.5) -> None:
    """Remove the Chromium profile dir, waiting for the browser tree to actually let go.

    Measured 2026-10-08: a single `rmtree` right after `proc.kill()` failed with WinError 32 for BOTH
    views, because Chrome's child processes keep the `--user-data-dir` alive for a moment after the
    parent dies — every run left an undeletable directory behind. Retrying bounded is the fix; reporting
    what still cannot be removed is the discipline (ERR-140 exists for the habit of swallowing it).
    """
    last: OSError | None = None
    for _ in range(attempts):
        try:
            shutil.rmtree(udf)
            return
        except OSError as exc:
            last = exc
            time.sleep(pause)
    RESIDUE.append(f"{udf} {last!r}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=str(ROOT))
    ap.add_argument("--view", choices=("full", "compact", "floor"), action="append")
    ap.add_argument("--json-out", default=None)
    ap.add_argument("--screenshot", action="store_true")
    args = ap.parse_args()

    root = Path(args.root).resolve()
    if not (root / "apps/observer/frontend/dist/index.html").is_file():
        print(f"GEOMETRY_GATE_NOT_RUN DIST_ABSENT {root/'apps/observer/frontend/dist'}")
        return 3
    browser = find_browser()
    if not browser:
        print("GEOMETRY_GATE_NOT_RUN BROWSER_NOT_FOUND "
              "set WL_CHROME to a Chrome/Edge binary; a named category is not a pass")
        return 3

    views = args.view or ["full", "compact", "floor"]
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    u19 = load_u19()
    reports = []
    for view in views:
        shot = OUT_DIR / f"topbar-{view}.png" if args.screenshot else None
        try:
            measured = measure(root, view, browser, u19, shot)
        except Exception as exc:  # noqa: BLE001
            print(f"GEOMETRY_GATE_NOT_RUN MEASURE_FAILED {view} {exc!r}")
            return 3
        reports.append({"view": view, "verdict": verdict(measured, view),
                        "measured": measured, "browser": browser})

    out = Path(args.json_out) if args.json_out else (
        OUT_DIR / f"geometry_{int(time.time())}.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    # Name the bytes every row measured. `GATE_HEAD` binds a gate report to a commit; a render report has
    # no commit at all, so without this a receipt cannot tell "measured these bytes" from "measured bytes
    # that a later rebuild already replaced" (found 2026-10-10: every geometry receipt predated a rebuild).
    bundle = bundle_provenance.describe(ROOT)
    for row in reports:
        row["servedBundle"] = bundle
    out.write_text(json.dumps(reports, indent=2, ensure_ascii=False), encoding="utf-8")

    ok = all(r["verdict"]["passed"] for r in reports)
    for r in reports:
        v = r["verdict"]
        for c in v["checks"]:
            print(f"{v['view']:<8} {c['check']:<28} {'PASS' if c['pass'] else 'FAIL'} {c['detail']}")
        print(f"{v['view']:<8} viewport={v['viewport']}")
    print(("GEOMETRY_GATE_PASS " if ok else "GEOMETRY_GATE_FAIL ") + str(out))
    if ANNOUNCED_MISMATCH:
        print("GEOMETRY_GATE_PORT_MISMATCH " + json.dumps(ANNOUNCED_MISMATCH))
    if RESIDUE:
        print("GEOMETRY_GATE_RESIDUE " + json.dumps(RESIDUE, ensure_ascii=False))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
