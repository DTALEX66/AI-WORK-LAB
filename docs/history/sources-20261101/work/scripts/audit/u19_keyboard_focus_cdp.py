#!/usr/bin/env python
"""Keyboard operability + focus order in the REAL shipped WebView2 (KEYBOARD_FOCUS_GATE).

What the release line already proved: the shipped binary renders and CDP can drive its mouse
(`scripts/audit/u19_verify_once.py`, `apps/observer/scripts/u19_webview_e2e.py`). What it had never
proved: the keyboard. Until this file the repository contained zero `Input.dispatchKeyEvent`
calls, so every "Tab reaches the lanes in order / a focus ring is visible / Enter activates a lane /
Escape is inert" sentence in the UI task card was an assumption — and the jsdom contracts in
`frontend/src/keyboardFocus.contract.test.tsx` cannot cover it: jsdom has no focus traversal and no
layout.

Design rules, all borrowed from the harnesses above rather than invented:

  * discovery/launch/teardown reuse the release line's own machinery (`load_u19()` for the CDP
    client, the artifact-freshness gate and the port picker). ONE desktop launch; every measurement
    is batched inside that single attached session;
  * the verdict is a PURE function of one measurement dict (`judge()`), so the decision logic is
    unit-testable without a browser and reviewable as text
    (`tests/ci/test_keyboard_focus_contract.py`);
  * nothing is inferred from CSS text — the ring is read from `getComputedStyle` of the element that
    actually holds `document.activeElement` after a real key event;
  * the instrument checks ITSELF before its numbers mean anything: a focus set on purpose must be
    readable back (a dead readback would make a live traversal look stuck), every generated
    selector must resolve back to the node it names, reverse traversal is compared against the
    recorded forward order, and the "Escape wrote nothing" claim is only trusted once a deliberately
    issued POST is seen by that same detector — otherwise zero writes and a blind detector are the
    same picture (ERR-140, and the E5 finding about asserting on a marker that does not exist);
  * a superseded binary is never certified as current. The artifact gate is asked first; if it
    refuses, the gate exits 3 even when every measurement below it succeeded.

Exit: 0 measured PASS, 1 measured FAIL, 3 cannot run (reason named).
The LAST line of stdout is the single machine-readable verdict:
  KEYBOARD_FOCUS_GATE_PASS ... / KEYBOARD_FOCUS_GATE_FAIL reason=... /
  KEYBOARD_FOCUS_GATE_NOT_RUN reason=...
`--measure-superseded-binary` still exits 3 (the artifact finding stands); it launches the newest
`app.exe` on this machine whose own bytes carry a frontend bundle, so this instrument's machinery
can be exercised without spending the single desktop launch on a shell that has nothing to render,
and reports that as evidence about the probe, never as a gate.
"""
from __future__ import annotations

import argparse
import ctypes
import ctypes.wintypes as wt
import hashlib
import importlib.util
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import threading
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OBS = ROOT / "apps" / "observer"
DIST = OBS / "frontend" / "dist"
# Scratch (the browser profile, the app's stderr, this run's sidecar runtime root) and the evidence
# document are separate on purpose: scratch is this run's and may be thrown away, evidence is the
# record the handoff is judged on. Both stay inside the repository.
OUT = ROOT / ".project-local" / "runs" / "qoder-kb"
EVIDENCE = ROOT / ".project-local" / "artifacts" / "qoder-handoff-20261007"

# CDP `Input.dispatchKeyEvent` modifiers bitfield.
MOD_SHIFT = 8

# key/code/windowsVirtualKeyCode per pressed key. Enter also carries text "\r" on its own `char`
# event: Chromium activates a focused control off the keypress/text event, and the protocol
# separates the raw key event from the text input (`rawKeyDown` deliberately carries no text).
KEYS: dict[str, dict] = {
    "Tab": {"key": "Tab", "code": "Tab", "vk": 9, "text": None},
    "ShiftTab": {"key": "Tab", "code": "Tab", "vk": 9, "text": None, "modifiers": MOD_SHIFT},
    "Enter": {"key": "Enter", "code": "Enter", "vk": 13, "text": "\r"},
    "Escape": {"key": "Escape", "code": "Escape", "vk": 27, "text": None},
}

READ_METHODS = {"GET", "HEAD", "OPTIONS"}
CONTROL_PATH = "/__keyboard_focus_gate_probe_control__"
_CL_RE = re.compile(rb"Content-Length:\s*(\d+)", re.IGNORECASE)

# ---------------------------------------------------------------------------
# Page-side JavaScript. Each expression is self-contained (the only state that persists between
# calls is the write detector, and its presence is verified on every read) so a page reload can
# only surface as a named failure, never as a quietly empty measurement.
# ---------------------------------------------------------------------------
JS_HELPERS = r"""
  const kbSeg = (node) => {
    const p = node.parentElement;
    if (!p) return 1;
    let i = 0;
    for (const c of p.children) {
      if (c.tagName === node.tagName) { i++; if (c === node) return i; }
    }
    return 1;
  };
  const kbSelector = (el) => {
    if (!el || el.nodeType !== 1) return null;
    if (el === document.body) return 'BODY';
    if (el === document.documentElement) return 'HTML';
    const seg = [];
    let n = el;
    while (n && n.nodeType === 1 && n !== document.documentElement) {
      const s = n.tagName.toLowerCase();
      if (n.id) { seg.unshift(s + '#' + n.id); break; }
      if (n.dataset && n.dataset.lane !== undefined) {
        seg.unshift(s + '[data-lane="' + n.dataset.lane + '"]'); break;
      }
      const al = n.getAttribute && n.getAttribute('aria-label');
      if (al) { seg.unshift(s + '[aria-label="' + al + '"]'); break; }
      seg.unshift(s + ':nth-of-type(' + kbSeg(n) + ')');
      n = n.parentElement;
    }
    return seg.join(' > ');
  };
  const kbDjb2 = (str) => {
    let h = 5381;
    for (let i = 0; i < str.length; i++) { h = (((h << 5) + h) + str.charCodeAt(i)) | 0; }
    return (h >>> 0).toString(16);
  };
  const kbPage = () => {
    const main = document.querySelector('main.main') || document.querySelector('main')
      || document.getElementById('root') || document.body;
    // The lane itself is what a lane switch must change. `main.main` also carries the top bar,
    // whose text is the same on every lane, so a shell-wide signature could stay constant while
    // the lane swapped, and a lane-wide one cannot.
    const lane = document.getElementById('content') || document.querySelector('section.content')
      || main;
    const text = ((main && main.innerText) || '').replace(/\s+/g, ' ').trim();
    const laneText = ((lane && lane.innerText) || '').replace(/\s+/g, ' ').trim();
    const heading = lane && lane.querySelector
      ? (lane.querySelector('h1, h2, .page-title, [class*="title"]') || {}).innerText : null;
    const cur = document.querySelector('[aria-current="page"]');
    const act = document.querySelector('.nav button.active');
    const laneOf = (el) => (el && el.getAttribute ? el.getAttribute('data-lane') : null);
    let viewParam = 'URL_ERROR';
    try { viewParam = new URLSearchParams(location.search).get('view'); } catch (e) {}
    return {
      href: location.href,
      aboutBlank: String(location.href).startsWith('about:'),
      title: document.title,
      hasFocus: document.hasFocus(),
      rootChildren: (document.getElementById('root') || { children: [] }).children.length,
      laneButtons: document.querySelectorAll('.nav button[data-lane]').length,
      focusables: document.querySelectorAll(
        'a[href],button:not([disabled]),input,select,textarea,[tabindex]').length,
      viewParam: viewParam,
      ariaCurrentLane: laneOf(cur),
      activeClassLane: laneOf(act),
      mainChars: text.length,
      mainSig: text.length + ':' + kbDjb2(text),
      laneRegionFound: !!(document.getElementById('content')
                          || document.querySelector('section.content')),
      laneChars: laneText.length,
      laneSig: laneText.length + ':' + kbDjb2(laneText),
      laneHeading: String(heading || '').replace(/\s+/g, ' ').trim().slice(0, 40),
      mainHead: text.slice(0, 80)
    };
  };
  const kbActive = () => {
    const el = document.activeElement;
    if (!el || el.nodeType !== 1) return { present: false, selector: null };
    const cs = getComputedStyle(el);
    let focusVisible;
    try { focusVisible = el.matches(':focus-visible'); }
    catch (e) { focusVisible = 'unsupported:' + e.name; }
    const sel = kbSelector(el);
    let uniq;
    try { uniq = document.querySelectorAll(sel).length; } catch (e) { uniq = -1; }
    const r = el.getBoundingClientRect();
    let label = el.getAttribute('aria-label') || el.getAttribute('title') || '';
    if (!label) { label = String(el.innerText || '').replace(/\s+/g, ' ').trim().slice(0, 40); }
    return {
      present: true,
      selector: sel,
      tag: el.tagName.toLowerCase(),
      lane: (el.dataset && el.dataset.lane !== undefined) ? el.dataset.lane : null,
      insideSidebar: !!(el.closest && el.closest('aside.sidebar')),
      insideNav: !!(el.closest && el.closest('nav.nav')),
      focusVisible: focusVisible,
      outline: { style: cs.outlineStyle, width: cs.outlineWidth,
                 color: cs.outlineColor, offset: cs.outlineOffset },
      boxShadowChars: String(cs.boxShadow || 'none').length,
      selectorUnique: uniq,
      selectorIsActive: uniq === 1 ? (document.querySelector(sel) === el) : false,
      visible: r.width > 0 && r.height > 0 && cs.visibility !== 'hidden' && cs.display !== 'none',
      disabled: !!el.disabled,
      tabIndex: el.tabIndex,
      label: label
    };
  };
"""

def js(body: str) -> str:
    return "JSON.stringify((()=>{" + JS_HELPERS + body + "})())"


JS_READ_STEP = js("return {page: kbPage(), active: kbActive()};")
JS_RAIL_SHAPE = js("""
  // Why a rail reads as empty is decided here rather than assumed: shell, nav, its buttons and the
  // lane attribute are counted separately, because "0 lane buttons" from a superseded bundle and
  // "0 lane buttons" from a page that never painted are different findings, and only one of them
  // belongs to the product.
  const q = (s) => { try { return document.querySelectorAll(s).length; } catch (e) { return -1; } };
  let names;
  try {
    names = Array.from(document.querySelectorAll('button')).slice(0, 8).map(b => String(
      b.getAttribute('data-lane') || b.getAttribute('aria-label') || b.className
      || b.tagName).slice(0, 26));
  } catch (e) { names = ['enum-error']; }
  return {shape: {asideSidebar: q('aside.sidebar'), nav: q('nav'), navButtons: q('nav button'),
                  classNavButtons: q('.nav button'), laneButtons: q('.nav button[data-lane]'),
                  allButtons: q('button'), bodyChars: (document.body.innerText || '').length,
                  rootChildren: (document.getElementById('root') || {children: []}).children.length,
                  buttonNames: names},
          page: kbPage(), active: kbActive()};
""")
JS_CONTROL_FOCUS = js("""
  const el = document.querySelector('[data-lane="settings"]')
    || document.querySelector('.nav button[data-lane]');
  if (!el) return {control: {skipped: 'no lane button exists to focus'}};
  const wanted = kbSelector(el);
  el.focus();
  const got = document.activeElement;
  let uniq;
  try { uniq = document.querySelectorAll(wanted).length; } catch (e) { uniq = -1; }
  return {control: {requested: wanted, readBack: kbSelector(got), sameNode: got === el,
                    unique: uniq}};
""")
JS_RESET_FOCUS = js("""
  const ae = document.activeElement;
  if (ae && ae.blur) ae.blur();
  return {reset: {active: kbSelector(document.activeElement)}};
""")
JS_INSTALL_DETECTOR = js("""
  const w = window;
  if (!w.__wlProbe) {
    const p = {writes: [], invokes: [], installedAt: Date.now()};
    const mark = (kind, method, url) => {
      try {
        p.writes.push({kind: kind, method: String(method || 'GET').toUpperCase(),
                       url: String(url).slice(0, 180), n: p.writes.length});
      } catch (e) { /* a detector must never break the page it watches */ }
    };
    try {
      const f = w.fetch;
      w.fetch = function (input, init) {
        try {
          const m = (init && init.method) || (input && input.method) || 'GET';
          const u = (typeof input === 'string') ? input
            : (input instanceof URL ? String(input)
               : ((input && input.url) || String(location.href)));
          mark('fetch', m, u);
        } catch (e) {}
        return f.apply(this, arguments);
      };
    } catch (e) {}
    try {
      const xo = w.XMLHttpRequest.prototype.open;
      w.XMLHttpRequest.prototype.open = function (method, url) {
        mark('xhr', method, url);
        return xo.apply(this, arguments);
      };
    } catch (e) {}
    w.__wlProbe = p;
  }
  const p = w.__wlProbe;
  p.invokes = [];
  let wrapped = false;
  try {
    const t = w.__TAURI_INTERNALS__;
    if (t && typeof t.invoke === 'function' && !t.__wlWrapped) {
      const inner = t.invoke;
      t.invoke = function (cmd) {
        try { p.invokes.push({cmd: String(cmd)}); } catch (e) {}
        return inner.apply(this, arguments);
      };
      t.__wlWrapped = true;
    }
    wrapped = !!(w.__TAURI_INTERNALS__ && w.__TAURI_INTERNALS__.__wlWrapped);
  } catch (e) {}
  return {detector: {present: true, writesTotal: p.writes.length, invokeTotal: 0,
                     tauriInternals: !!w.__TAURI_INTERNALS__, invokeWrapped: wrapped}};
""")
JS_READ_DETECTOR = js("""
  if (typeof window.__wlProbe !== 'object') return {detector: {present: false}};
  const p = window.__wlProbe;
  return {detector: {present: true, writesTotal: p.writes.length, invokeTotal: p.invokes.length,
                     writes: p.writes.slice(-30).map(x => ({kind: x.kind, method: x.method,
                                                            url: x.url})),
                     invokes: p.invokes.slice(-10).map(x => ({cmd: x.cmd}))}};
""")
JS_ISSUE_CONTROL_WRITE = js("""
  const url = String(location.origin) + '@@CONTROL_PATH@@';
  let threw = null;
  try {
    window.fetch(url, {method: 'POST', headers: {'X-Probe': 'keyboard-focus-gate'}});
  } catch (e) { threw = String(e).slice(0, 140); }
  return {control: {url: url, issued: threw === null, threw: threw}};
""").replace("@@CONTROL_PATH@@", CONTROL_PATH)


class ProbeError(Exception):
    """A named 'cannot run' reason. Exit 3 — never a green verdict."""


def carries_embedded_bundle(path: Path) -> dict:
    """Does this binary's own bytes carry a built frontend bundle?

    Decided before the desktop launch, because the launch is the one this run is allowed. Vite
    hashes every emitted asset into its file name, and a Tauri build that embeds `frontend/dist`
    carries those names in the clear while the asset bodies stay compressed, so the names say
    which bundle a binary carries — and their absence says it carries none.

    Measured 2026-10-08 on this machine: `u19-msvc-20261006/target/release/app.exe` carries
    `index-CZu0T7Uh.js` / `index-CvdAPEOU.css` and renders the product shell; the newest binary,
    `qoder-agent-win/cargo-target-msvc/release/app.exe`, carries no asset names at all and attached
    two `http://localhost:1420/...` page targets with `rootChildren: 0` — a shell whose loader
    points at a dev server that is not running. Both binaries contain the `localhost:1420` string
    (it is `build.devUrl` in `tauri.conf.json`), so `devUrlBaked` is recorded as context only: the
    asset names are the discriminator. Launching the second one cost this run a window and
    produced `rail_never_painted`, which is a symptom of the wrong binary, not a finding about the
    product.
    """
    try:
        blob = path.read_bytes()
    except OSError as exc:
        return {"readable": False, "error": repr(exc)[:120], "assetNames": []}
    names = sorted(set(m.decode() for m in re.findall(
        rb"(?:index|webview|window)-[A-Za-z0-9_-]{8}\.(?:js|css)", blob)))
    return {"readable": True, "assetNames": names[:8], "embeddedBundle": bool(names),
            "devUrlBaked": b"//localhost:1420" in blob}


def load_u19():
    """Reuse the CDP client and the artifact-freshness gate the release line already trusts."""
    path = OBS / "scripts" / "u19_webview_e2e.py"
    spec = importlib.util.spec_from_file_location("u19_for_keyboard", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[attr-defined]
    return module


def make_client(u19):
    """u19's client plus the headers this machine's Blink answers on a websocket.

    Measured 2026-10-08 against the shipped binary: the release line's headerless discovery GET was
    accepted and never answered (`recv TimeoutError` every round while the app stayed alive with a
    visible 1600x1025 window) — the same stall `scripts/audit/topbar_geometry_via_cdp.py` recorded
    for Chrome 154, now reached on the auto-updated WebView2 runtime. u19's own shape is still tried
    first by the discovery loop, and the shape that answered is recorded rather than assumed.
    """
    import uuid

    class Client(u19.CDP):
        def __init__(self, ws_url: str) -> None:
            super().__init__(ws_url)
            # u19's `_send_cmd` throws away any frame that is not the reply it is waiting for, so
            # CDP events are captured at the single choke point every frame passes through. Without
            # this the Network cross-check silently under-reports — a "saw no write" that is really
            # "the reply to my next command ate the event".
            self.collected: list[dict] = []

        def _recv_frame(self, mask_len: bytes = b"") -> bytes:
            raw = super()._recv_frame(mask_len)
            try:
                obj = json.loads(raw.decode("utf-8"))
            except Exception:  # noqa: BLE001 — a partial read is a lost event, not a crash
                return raw
            if obj.get("method"):
                self.collected.append(obj)
            return raw

        def _send_handshake(self, host: str, port: int, path: str) -> None:
            key = uuid.uuid4().hex
            self._sock.sendall((f"GET {path} HTTP/1.1\r\nHost: {host}:{port}\r\n"
                                "Upgrade: websocket\r\nConnection: Upgrade\r\n"
                                f"Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n"
                                "User-Agent: worklab-keyboard-focus-gate\r\n"
                                "Accept: application/json\r\n\r\n").encode("latin-1"))
            buf = b""
            while b"\r\n\r\n" not in buf:
                chunk = self._sock.recv(4096)
                if not chunk:
                    raise RuntimeError("CDP handshake: connection closed")
                buf += chunk
            head = buf.split(b"\r\n\r\n", 1)[0].decode("latin-1", "replace")
            if "101" not in head.split("\r\n")[0]:
                raise RuntimeError("CDP handshake rejected: " + head[:160])

    return Client


def devtools_get(path: str, port: int, shape: str = "u19", timeout: float = 8.0) -> str:
    """Raw-socket loopback GET of a DevTools endpoint.

    urllib is deliberately not used: any http_proxy state would steer a loopback request off the
    machine and turn a working port into a confusing 400.

    `shape='u19'` is the release line's own byte-for-byte request (`_cdp_http_get`). `shape='blink'`
    is the shape current Blink engines answer: a portless `Host`, plus `User-Agent`/`Accept` — the
    finding `scripts/audit/topbar_geometry_via_cdp.py` recorded for Chrome 154 and this gate
    reproduced against the shipped binary on 2026-10-08. The answer decides the shape; neither is
    assumed. A 200 whose body is shorter than its own Content-Length is refused rather than parsed,
    because a list cut mid-document is exactly how a page target goes missing while everything
    still reports success.
    """
    if shape == "u19":
        request = (f"GET {path} HTTP/1.1\r\nHost: localhost:{port}\r\n"
                   "Connection: close\r\n\r\n")
    else:
        request = (f"GET {path} HTTP/1.1\r\nHost: 127.0.0.1\r\n"
                   "User-Agent: worklab-keyboard-focus-gate\r\n"
                   "Accept: application/json\r\nConnection: close\r\n\r\n")
    try:
        s = socket.create_connection(("127.0.0.1", port), timeout=timeout)
    except Exception as exc:  # noqa: BLE001
        return f"ERR connect {exc!r}"[:170]
    try:
        s.sendall(request.encode("latin-1"))
        s.settimeout(timeout)
        raw = b""
        head = None
        expected: int | None = None
        while True:
            chunk = s.recv(65536)
            if not chunk:
                break
            raw += chunk
            if head is None:
                split = raw.find(b"\r\n\r\n")
                if split == -1:
                    continue
                head = raw[:split]
                match = _CL_RE.search(head)
                expected = int(match.group(1)) if match else None
            if expected is not None and len(raw) - (len(head) + 4) >= expected:
                break
    except Exception as exc:  # noqa: BLE001
        return f"ERR recv {exc!r}"[:170]
    finally:
        s.close()
    if head is None:
        return f"ERR no response head ({raw[:80]!r})"[:180]
    status = head.split(b"\r\n", 1)[0].decode("latin-1", "replace")
    parts = status.split()
    if len(parts) < 2 or parts[1] != "200":
        return f"ERR http {status[:120]}"
    body = raw[len(head) + 4:]
    if expected is not None and len(body) < expected:
        return f"ERR truncated body {len(body)} of {expected}"
    return body.decode("utf-8", "replace")


class KeyedCDP:
    """u19.CDP plus real key dispatch and event draining.

    `u19.CDP._send_cmd` discards interleaved event frames it is not waiting for, so CDP events are
    collected by draining while nothing is pending — the approach `u19_verify_once.RecordingCDP`
    uses, and the reason the Network domain is only a cross-check here while the page-side hook is
    the primary write detector.
    """

    def __init__(self, ws_url: str, base, client: type | None = None) -> None:
        self._cdp = (client or base.CDP)(ws_url)
        collected = getattr(self._cdp, "collected", None)
        # With `make_client` the events are captured inside the client (nothing is lost between
        # commands); with a plain u19.CDP this list is only ever as complete as what `drain` catches
        # between in-flight commands, which is why it cross-checks and never gates.
        self.events: list[dict] = collected if isinstance(collected, list) else []
    def cmd(self, method: str, params: dict | None = None) -> dict:
        return self._cdp._send_cmd(method, params)

    def eval_json(self, expr: str, label: str) -> dict:
        # u19's own `evaluate` drops `exceptionDetails`, so a broken expression on MY side arrives as
        # "no value" and reads like a dead readback. Ask for the whole result and name the exception.
        res = self._cdp._send_cmd("Runtime.evaluate", {
            "expression": expr, "returnByValue": True, "awaitPromise": False})
        details = res.get("exceptionDetails")
        if details:
            raise ProbeError(f"{label}: the page refused this expression: "
                             f"{json.dumps(details, ensure_ascii=False)[:340]}")
        raw = (res.get("result") or {}).get("value")
        if not isinstance(raw, str):
            raise ProbeError(f"{label}: Runtime.evaluate returned no value "
                             f"(type={type(raw).__name__}); the readback is dead, not empty")
        try:
            return json.loads(raw)
        except Exception as exc:  # noqa: BLE001
            raise ProbeError(f"{label}: readback is not JSON: {exc!r} head={raw[:160]!r}") from exc

    def press(self, name: str) -> None:
        spec = KEYS[name]
        mods = spec.get("modifiers", 0)
        ident = {"key": spec["key"], "code": spec["code"],
                 "windowsVirtualKeyCode": spec["vk"], "nativeVirtualKeyCode": spec["vk"],
                 "modifiers": mods, "location": 0}
        self.cmd("Input.dispatchKeyEvent", dict(type="rawKeyDown", **ident))
        if spec["text"]:
            self.cmd("Input.dispatchKeyEvent", dict(type="char", text=spec["text"],
                                                    unmodifiedText=spec["text"], **ident))
        self.cmd("Input.dispatchKeyEvent", dict(type="keyUp", **ident))

    def drain(self, seconds: float) -> list[dict]:
        """Keep pumping frames so events arrive; the client records them if it can."""
        self._cdp._sock.settimeout(seconds)
        try:
            while True:
                try:
                    raw = self._cdp._recv_frame()
                except (socket.timeout, OSError):
                    break
                if hasattr(self._cdp, "collected"):
                    continue  # already recorded at the frame choke point
                try:
                    obj = json.loads(raw.decode("utf-8"))
                except Exception:  # noqa: BLE001
                    continue
                if obj.get("method"):
                    self.events.append(obj)
        finally:
            self._cdp._sock.settimeout(None)
        return self.events

    def non_get_requests(self) -> list[dict]:
        out = []
        for e in self.events:
            if e.get("method") != "Network.requestWillBeSent":
                continue
            req = (e.get("params") or {}).get("request") or {}
            method = str(req.get("method", "GET")).upper()
            if method not in READ_METHODS:
                out.append({"method": method, "url": str(req.get("url", ""))[:180]})
        return out

    def close(self) -> None:
        self._cdp.close()


# ---------------------------------------------------------------------------
# Window state, read from Win32 (same shapes u19_verify_once proved on this machine)
# ---------------------------------------------------------------------------
def window_state(pid: int) -> dict:
    u = ctypes.windll.user32
    found: list[dict] = []
    cb = ctypes.WINFUNCTYPE(ctypes.c_bool, wt.HWND, wt.LPARAM)

    def each(hwnd, _l):
        pidout = wt.DWORD()
        u.GetWindowThreadProcessId(hwnd, ctypes.byref(pidout))
        if pidout.value != pid:
            return True
        cr = wt.RECT()
        u.GetClientRect(hwnd, ctypes.byref(cr))
        w, h = cr.right - cr.left, cr.bottom - cr.top
        title = ctypes.create_unicode_buffer(256)
        u.GetWindowTextW(hwnd, title, 256)
        found.append({"hwnd": int(hwnd), "title": title.value, "w": w, "h": h,
                      "visible": bool(u.IsWindowVisible(hwnd)), "area": max(0, w) * max(0, h)})
        return True

    u.EnumWindows(cb(each), 0)
    if not found:
        return {"hwnd": None, "windows": [], "raised": False}
    pool = [x for x in found if x["visible"] and x["area"] > 0] or found
    big = max(pool, key=lambda x: x["area"])
    raised: object = False
    foreground = None
    try:
        u.SetWindowPos.argtypes = [wt.HWND, wt.HWND, ctypes.c_int, ctypes.c_int,
                                   ctypes.c_int, ctypes.c_int, wt.UINT]
        u.SetWindowPos.restype = ctypes.c_bool
        u.GetForegroundWindow.restype = wt.HWND
        # SWP_NOSIZE|SWP_NOMOVE|SWP_NOACTIVATE onto HWND_TOP: z-order is the only lever this
        # process can pull positively, and Chromium's focus-visible modality is the one thing a
        # keyboard gate depends on, so the state is recorded rather than assumed.
        raised = bool(u.SetWindowPos(wt.HWND(big["hwnd"]), wt.HWND(-1), 0, 0, 0, 0,
                                     0x0001 | 0x0002 | 0x0010))
        foreground = int(u.GetForegroundWindow() or 0)
    except Exception as exc:  # noqa: BLE001
        raised = f"error {exc!r}"[:120]
    return {"hwnd": big["hwnd"], "title": big["title"], "size": [big["w"], big["h"]],
            "visible": big["visible"], "raised": raised,
            "foregroundHwnd": foreground,
            "isForeground": foreground == big["hwnd"] if isinstance(foreground, int) else None,
            "windows": found}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


# ---------------------------------------------------------------------------
# THE DECISION — pure: no browser, no filesystem, no globals. Pinned by
# tests/ci/test_keyboard_focus_contract.py.
# ---------------------------------------------------------------------------
def ring_renders(step: dict) -> bool:
    """The focus cue is what the element actually computes, not what CSS text says."""
    outline = step.get("outline") or {}
    raw = str(outline.get("width", "")).strip().lower()
    named = {"thin": 1.0, "medium": 3.0, "thick": 5.0}
    if raw in named:
        width = named[raw]
    else:
        try:
            width = float(raw.replace("px", ""))
        except ValueError:
            width = 0.0
    style = str(outline.get("style", "none")).strip().lower()
    color = str(outline.get("color", ""))
    transparent = color.startswith("rgba(0, 0, 0, 0)") or color == "transparent"
    return (step.get("focusVisible") is True and style not in ("none", "")
            and width > 0 and not transparent)


def judge(measurement: dict) -> dict:
    """Turn one measurement dict into a verdict. Every check is one line of the claim."""
    checks: list[dict] = []

    def add(name: str, ok: object, detail: str, gating: bool = True) -> None:
        checks.append({"check": name, "pass": bool(ok), "gating": bool(gating),
                       "detail": str(detail)[:500]})

    m = measurement or {}
    base = m.get("base") or {}
    steps = m.get("tabs") or []
    rsteps = m.get("shiftTabs") or []
    enter = m.get("enter") or {}
    esc = m.get("escape") or {}
    ctl = m.get("control") or {}
    selectors = [str(s.get("selector")) for s in steps]
    distinct = {s for s in selectors if s and s != "None"}
    lane_stops = [s for s in steps if s.get("lane")]

    add("surface_is_the_real_bundle",
        base.get("rootChildren", 0) > 0 and base.get("laneButtons", 0) >= 10
        and not base.get("aboutBlank"),
        f"rootChildren={base.get('rootChildren')} laneButtons={base.get('laneButtons')} "
        f"aboutBlank={base.get('aboutBlank')} href={str(base.get('href'))[:70]}")

    control = m.get("instrumentControl") or {}
    add("instrument_reads_active_element",
        control.get("sameNode") is True and bool(control.get("readBack"))
        and control.get("requested") == control.get("readBack")
        and control.get("unique") == 1,
        f"requested={control.get('requested')} readBack={control.get('readBack')} "
        f"sameNode={control.get('sameNode')} unique={control.get('unique')} "
        f"skipped={control.get('skipped')}")

    moved = sum(1 for i in range(1, len(selectors)) if selectors[i] != selectors[i - 1])
    add("focus_moves_under_tab", bool(steps) and len(distinct) >= 4 and moved >= 3,
        f"tabStops={len(selectors)} distinct={len(distinct)} changedOn={moved} "
        f"documentHasFocus={base.get('hasFocus')} focusablesReported={base.get('focusables')}")

    # A selector that does not resolve back to its own node can make two different elements look
    # identical — which is exactly how a live traversal reads as a stuck one.
    unresolved = [s.get("selector") for s in steps if s.get("selectorIsActive") is not True]
    add("selectors_resolve_to_the_focused_node", bool(steps) and not unresolved,
        f"nonResolving={json.dumps(unresolved[:4], ensure_ascii=False)}")

    inside = [bool(s.get("insideSidebar")) for s in steps]
    entered = next((i for i, v in enumerate(inside) if v), None)
    left = next((i for i in range(entered + 1, len(inside)) if not inside[i]), None) \
        if entered is not None else None
    returned = next((i for i in range(left + 1, len(inside)) if inside[i]), None) \
        if left is not None else None
    add("tab_cycle_through_sidebar_completes",
        entered is not None and left is not None and returned is not None
        and len(lane_stops) >= 2,
        f"enteredIdx={entered} leftIdx={left} returnedIdx={returned} "
        f"sidebarStops={sum(1 for v in inside if v)} laneButtonStops={len(lane_stops)} "
        f"tabBudget={len(selectors)} (raised by --tabs)")

    without_ring = [{"selector": s.get("selector"), "outline": s.get("outline"),
                     "focusVisible": s.get("focusVisible")}
                    for s in lane_stops if not ring_renders(s)]
    add("focus_visible_ring_rendered", bool(lane_stops) and not without_ring,
        f"laneFocusStops={len(lane_stops)} withoutRing="
        f"{json.dumps(without_ring[:3], ensure_ascii=False)}")

    # Reverse traversal must retrace the recorded forward order, not merely be different.
    forward = list(selectors)
    expected = [forward[len(forward) - 1 - j] for j in range(1, len(rsteps) + 1)] if forward else []
    got = [str(s.get("selector")) for s in rsteps]
    add("shift_tab_retraces_forward_order", bool(got) and got == expected,
        f"got={json.dumps(got[:5], ensure_ascii=False)} "
        f"expected={json.dumps(expected[:5], ensure_ascii=False)}")

    before = enter.get("before") or {}
    after = enter.get("after") or {}
    pressed = enter.get("pressedLane")
    # laneSig is the region a lane switch must change; mainSig covers the whole shell (its top bar
    # is the same on every lane) and is kept as the wider cross-check.
    lane_sig_changed = bool(before.get("laneSig")) and before.get("laneSig") != after.get("laneSig")
    shell_sig_changed = bool(before.get("mainSig")) and before.get("mainSig") != after.get("mainSig")
    routing_moved = (bool(pressed) and pressed != before.get("activeClassLane")
                     and after.get("activeClassLane") == pressed
                     and after.get("ariaCurrentLane") == pressed
                     and after.get("viewParam") == pressed)
    add("enter_activates_the_focused_lane", routing_moved and lane_sig_changed,
        f"pressed={pressed} activeBefore={before.get('activeClassLane')} "
        f"activeAfter={after.get('activeClassLane')} ariaCurrentAfter={after.get('ariaCurrentLane')} "
        f"viewParam={before.get('viewParam')}->{after.get('viewParam')} routingMoved={routing_moved} "
        f"laneSig={before.get('laneSig')}->{after.get('laneSig')} chars="
        f"{before.get('laneChars')}->{after.get('laneChars')} "
        f"laneHeading={before.get('laneHeading')!r}->{after.get('laneHeading')!r} "
        f"shellSigChanged={shell_sig_changed} laneRegionFound={after.get('laneRegionFound')} "
        f"skipped={enter.get('skipped')}")

    # Without this, "the detector saw no write" and "the detector is blind" are one picture.
    add("write_detector_is_proven", ctl.get("observedByPageHook") is True,
        f"controlPOST seenByPageHook={ctl.get('observedByPageHook')} "
        f"seenByCdpNetwork={ctl.get('observedByCdpNetwork')} "
        f"entries={json.dumps(ctl.get('writes', [])[-2:], ensure_ascii=False)}")

    esc_writes = [w for w in (esc.get("writes") or [])
                  if str(w.get("method", "GET")).upper() not in READ_METHODS]
    add("escape_fires_no_write_action",
        esc.get("detectorPresent") is True and not esc_writes and not (esc.get("invokes") or []),
        f"detectorPresent={esc.get('detectorPresent')} "
        f"nonGetDuringEscape={json.dumps(esc_writes, ensure_ascii=False)[:200]} "
        f"invokesDuringEscape={json.dumps(esc.get('invokes') or [], ensure_ascii=False)[:160]}")

    # Reported, deliberately not gating: real, but outside the four claims this gate exists for.
    add("focus_survives_activation",
        pressed is not None and enter.get("focusAfterEnterLane") == pressed,
        f"focusedLaneAfterEnter={enter.get('focusAfterEnterLane')} pressed={pressed} "
        f"selector={enter.get('focusAfterEnterSelector')} — a red here means the keyboard user is "
        f"stranded after Enter even though the lane switched",
        gating=False)
    add("escape_changes_no_visible_state",
        esc.get("laneBefore") == esc.get("laneAfter")
        and esc.get("mainSigBefore") == esc.get("mainSigAfter"),
        f"lane={esc.get('laneBefore')}->{esc.get('laneAfter')} "
        f"mainSigChanged={esc.get('mainSigBefore') != esc.get('mainSigAfter')}", gating=False)
    add("document_wraps_within_tab_budget", len(selectors) - len(distinct) >= 1,
        f"tabStops={len(selectors)} distinct={len(distinct)} — a repeat means Tab came back around "
        f"instead of parking; raise --tabs if this is red for budget", gating=False)

    failing = [c["check"] for c in checks if c["gating"] and not c["pass"]]
    reason = ""
    if failing:
        first = next(c for c in checks if c["check"] == failing[0])
        reason = f"{failing[0]}: {first['detail']}"
    return {"passed": not failing, "failing": failing, "checks": checks, "reason": reason,
            "sideFindings": [c["check"] for c in checks if not c["gating"] and not c["pass"]]}


# ---------------------------------------------------------------------------
# Measurement — everything happens inside ONE attached session
# ---------------------------------------------------------------------------
def read_rail(cdp: KeyedCDP, samples: int = 10, pause: float = 0.6) -> dict:
    """Poll the rail shape until lane items answer, or the sample budget runs out.

    One read is not evidence. Measured 2026-10-08 against this very bundle in Chromium: a read that
    reported 23 lane buttons was followed 200ms later by one reporting an all-but-empty document —
    the app rewrote its own deep-link URL and the page reloaded underneath the probe. A single
    sample would have turned that into "the rail never painted".
    """
    last: dict = {}
    for i in range(samples):
        try:
            last = cdp.eval_json(JS_RAIL_SHAPE, "rail-shape")
        except ProbeError as exc:
            last = {"readError": str(exc)[:220]}
        if (last.get("page") or {}).get("laneButtons"):
            last["sample"] = i + 1
            return last
        time.sleep(pause)
    last["sample"] = samples
    last["exhausted"] = True
    return last


def measure(cdp: KeyedCDP, cfg: dict, report: dict) -> dict:
    m: dict = {}

    rail = read_rail(cdp)
    report["baseRailRead"] = {"sample": rail.get("sample"), "shape": rail.get("shape")}
    read = {"page": rail.get("page") or {}, "active": rail.get("active") or {}}
    m["base"] = read["page"]
    m["base"]["activeAtStart"] = read["active"]
    report["baseRead"] = read
    if not read["page"]["laneButtons"]:
        raise ProbeError("no_lane_identity_in_attached_bundle: the attached page carries no "
                         f".nav button[data-lane] items (rootChildren="
                         f"{read['page'].get('rootChildren')} focusables="
                         f"{read['page'].get('focusables')} href="
                         f"{str(read['page'].get('href'))[:80]}) — there is nothing to tab through, "
                         f"and no lane identity to assert Enter against")

    # A full cycle needs two complete passes, so the budget is a function of what the page actually
    # holds rather than one number for every lane: the rail alone is `laneButtons` consecutive
    # stops, and a data-loaded lane adds its own controls.
    if cfg["tabs"] <= 0:
        passes = 3
        cfg["tabs"] = max(60, min(200, passes * (int(read["page"].get("focusables") or 30) + 2)))
        report["tabBudgetAuto"] = {"passes": passes,
                                   "focusables": read["page"].get("focusables"),
                                   "laneButtons": read["page"].get("laneButtons"),
                                   "chosen": cfg["tabs"]}
    report["tabBudget"] = cfg["tabs"]

    # instrument self-check: a focus set on purpose must be readable back
    control = cdp.eval_json(JS_CONTROL_FOCUS, "instrument-control")
    m["instrumentControl"] = control.get("control") or {}
    report["instrumentControl"] = control

    report["focusReset"] = cdp.eval_json(JS_RESET_FOCUS, "reset-focus")
    time.sleep(cfg["key_pause"])

    steps: list[dict] = []
    previous = None
    for i in range(cfg["tabs"]):
        cdp.press("Tab")
        time.sleep(cfg["key_pause"])
        active = cdp.eval_json(JS_READ_STEP, f"tab-step-{i}")["active"]
        active["index"] = i
        active["changedFromPrevious"] = previous is not None and active.get("selector") != previous
        steps.append(active)
        previous = active.get("selector")
    m["tabs"] = steps
    report["tabSequence"] = [{"i": s["index"], "sidebar": bool(s.get("insideSidebar")),
                              "lane": s.get("lane"), "fv": s.get("focusVisible"),
                              "outline": s.get("outline"), "selector": s.get("selector")}
                             for s in steps]

    shift: list[dict] = []
    for i in range(cfg["shift_tabs"]):
        cdp.press("ShiftTab")
        time.sleep(cfg["key_pause"])
        active = cdp.eval_json(JS_READ_STEP, f"shifttab-step-{i}")["active"]
        active["index"] = i
        shift.append(active)
    m["shiftTabs"] = shift
    report["shiftTabSequence"] = [{"i": s["index"], "selector": s.get("selector")} for s in shift]

    # ---- Enter on a focused lane item, reached by Tab only (no programmatic focus) ----
    current = cdp.eval_json(JS_READ_STEP, "pre-enter")
    before = current["page"]
    active_lane = current["active"].get("lane")
    wanted = cfg.get("target_lane")
    pressed = None
    seek_steps = 0
    for _ in range(cfg["max_tabs_to_lane"]):
        if (active_lane and active_lane != before.get("activeClassLane")
                and (wanted is None or active_lane == wanted)):
            pressed = active_lane
            break
        cdp.press("Tab")
        seek_steps += 1
        time.sleep(cfg["key_pause"])
        active_lane = cdp.eval_json(JS_READ_STEP, "seek-lane")["active"].get("lane")
    m["enter"] = {"before": before, "pressedLane": pressed,
                  "focusedBeforeEnter": current["active"].get("selector"),
                  "seekTabPresses": seek_steps}
    if pressed:
        cdp.press("Enter")
        time.sleep(cfg["settle"])
        after = cdp.eval_json(JS_READ_STEP, "post-enter")
        m["enter"]["after"] = after["page"]
        m["enter"]["focusAfterEnterSelector"] = after["active"].get("selector")
        # Compared against the lane id, not the selector string: `button[data-lane="work"]` is never
        # equal to `work`, and a first cut of this check compared exactly those two, so it read red
        # on a run where focus had in fact stayed on the lane that was pressed.
        m["enter"]["focusAfterEnterLane"] = after["active"].get("lane")
    else:
        m["enter"]["after"] = {}
        m["enter"]["skipped"] = (f"Tab never landed on an inactive lane button within "
                                 f"{cfg['max_tabs_to_lane']} presses (target={wanted})")

    # ---- Escape must fire no write: install detector, baseline, press, read the delta ----
    report["detectorInstall"] = cdp.eval_json(JS_INSTALL_DETECTOR, "install-detector")
    cdp.cmd("Network.enable")
    cdp.drain(0.3)
    network_non_get_before = len(cdp.non_get_requests())
    pre = cdp.eval_json(JS_READ_DETECTOR, "detector-before-escape")
    pre_page = cdp.eval_json(JS_READ_STEP, "pre-escape")["page"]
    writes_before = (pre.get("detector") or {}).get("writesTotal")
    cdp.press("Escape")
    time.sleep(cfg["settle"])
    post = cdp.eval_json(JS_READ_DETECTOR, "detector-after-escape")
    cdp.drain(0.6)
    post_page = cdp.eval_json(JS_READ_STEP, "post-escape-page")["page"]
    grew = int((post.get("detector") or {}).get("writesTotal") or 0) - int(writes_before or 0)
    recent = (post.get("detector") or {}).get("writes") or []
    m["escape"] = {
        "detectorPresent": (post.get("detector") or {}).get("present") is True,
        "writes": recent[-grew:] if grew > 0 else [],
        "invokes": (post.get("detector") or {}).get("invokes") or [],
        "laneBefore": pre_page["activeClassLane"], "laneAfter": post_page["activeClassLane"],
        "mainSigBefore": pre_page["mainSig"], "mainSigAfter": post_page["mainSig"],
    }
    report["escapeCdpNetworkNonGetDelta"] = len(cdp.non_get_requests()) - network_non_get_before

    # ---- positive control for that very detector: one POST that MUST be seen ----
    report["controlWriteIssued"] = cdp.eval_json(JS_ISSUE_CONTROL_WRITE, "issue-control-write")
    time.sleep(cfg["settle"])
    ctl_read = cdp.eval_json(JS_READ_DETECTOR, "detector-after-control")
    cdp.drain(0.8)
    ctl_writes = (ctl_read.get("detector") or {}).get("writes") or []
    matched = [w for w in ctl_writes if CONTROL_PATH in str(w.get("url", ""))]
    m["control"] = {
        "observedByPageHook": bool(matched),
        "observedByCdpNetwork": CONTROL_PATH in json.dumps(cdp.non_get_requests(),
                                                           ensure_ascii=False),
        "writes": matched,
        "detectorPresentAfterControl": (ctl_read.get("detector") or {}).get("present"),
        "cdpNetworkNonGetTotal": len(cdp.non_get_requests()),
    }
    return m


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--tabs", type=int, default=48, help="Tab presses used to map the focus order")
    ap.add_argument("--shift-tabs", type=int, default=4)
    ap.add_argument("--max-tabs-to-lane", type=int, default=44)
    ap.add_argument("--target-lane", default=None,
                    help="lane id Enter must activate (default: first inactive lane Tab lands on)")
    ap.add_argument("--key-pause", type=float, default=0.12)
    ap.add_argument("--settle", type=float, default=0.6)
    ap.add_argument("--boot-wait", type=float, default=10.0)
    ap.add_argument("--cdp-wait", type=float, default=90.0)
    ap.add_argument("--json-out", default=None)
    ap.add_argument("--measure-superseded-binary", action="store_true",
                    help="launch the newest app.exe on disk to exercise this instrument; the gate "
                         "still exits 3 because those bytes are not current for this tree")
    args = ap.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)
    stamp = int(time.time())
    json_out = Path(args.json_out) if args.json_out else EVIDENCE / f"keyboard_focus_{stamp}.json"
    report: dict = {"startedAt": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                    "config": {"tabs": args.tabs, "shiftTabs": args.shift_tabs,
                               "targetLane": args.target_lane,
                               "measureSupersededBinary": args.measure_superseded_binary},
                    "residue": []}
    verdict_line = "KEYBOARD_FOCUS_GATE_NOT_RUN reason=unknown"
    exit_code = 3
    cdp: KeyedCDP | None = None
    app = None
    udf: Path | None = None
    server = None

    try:
        # ---- stage 0: the built frontend this gate is about ----
        index = DIST / "index.html"
        if not index.is_file():
            raise ProbeError(f"no_dist_bundle: {index} is absent — run `npm run build` in "
                             f"apps/observer/frontend; there is no built frontend to tab through")
        report["distBundle"] = {"path": str(index), "bytes": index.stat().st_size,
                               "sha256": sha256(index),
                               "assets": sorted(p.name for p in (DIST / "assets").glob("*"))}

        # ---- stage 1: the binary must be the one this tree built ----
        u19 = load_u19()
        exe, artifact = u19.resolve_app_exe()
        report["artifactGate"] = {"status": artifact.get("status"),
                                  "reason": artifact.get("reason"),
                                  "basis": artifact.get("basis"),
                                  "candidates": artifact.get("candidates")}
        if exe is None:
            if not args.measure_superseded_binary:
                raise ProbeError(f"no_current_binary: the artifact gate says "
                                 f"{artifact.get('status')} — {str(artifact.get('reason'))[:280]}")
            # Resolution pool: whatever `resolve_app_exe` already enumerated (it honours
            # CARGO_TARGET_DIR, which is how a build writing outside src-tauri/target is found),
            # then a bounded sweep for the release binaries this machine actually produces. Inside
            # that pool a binary whose bytes carry a bundle beats a newer one that carries none
            # (`carries_embedded_bundle`), because the launch budget is one window and a
            # bundle-less shell spends it on a blank page.
            # On this machine the rule lands on the 2026-10-06 build, and that is the honest
            # ceiling: its embedded bundle predates `data-lane`, so no binary here is both current
            # for this tree and carrying lane items to tab through, and the named outcome stays
            # `no_lane_identity_in_attached_bundle`. Nothing in this branch can become a gate —
            # the artifact gate still refuses the bytes, so the run still ends exit 3.
            pool: list[Path] = [Path(str(c["path"])) for c in (artifact.get("candidates") or [])
                                if c.get("exists")]
            runs = ROOT / ".project-local" / "runs"
            for pattern in ("*/target/release/app.exe", "*/*/release/app.exe",
                            "*/target/*/release/app.exe"):
                pool.extend(runs.glob(pattern))
            pool.append(OBS / "src-tauri" / "target" / "release" / "app.exe")
            unique: dict[str, Path] = {}
            for p in pool:
                try:
                    if p.is_file():
                        unique[str(p).lower()] = p
                except OSError:  # a path that cannot be stat'd is not a launch candidate
                    continue
            # Rank by whether the bytes carry a bundle at all, newest inside each rank: a dev-URL
            # build is newer than every release build on this machine and cannot be tabbed through.
            if not unique:
                raise ProbeError("no_binary: no release app.exe at the CARGO_TARGET_DIR path, at "
                                 "src-tauri/target/release, or under .project-local/runs — there is "
                                 "nothing to launch")
            seen = [{"path": str(p),
                     "mtime": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(p.stat().st_mtime)),
                     **carries_embedded_bundle(p)} for p in sorted(unique.values(),
                                                                   key=lambda x: x.stat().st_mtime)]
            with_bundle = [s for s in seen if s.get("embeddedBundle")]
            chosen = (with_bundle or seen)[-1]
            exe = Path(chosen["path"])
            report["binaryAuthority"] = {
                "state": "SUPERSEDED_MEASURED_FOR_INSTRUMENT_VALIDATION_ONLY",
                "gateReason": str(artifact.get("reason"))[:400],
                "chosenBecause": ("newest release app.exe whose bytes carry an embedded frontend "
                                  "bundle" if with_bundle else
                                  "no candidate carries an embedded bundle; newest anyway"),
                "candidatesSeen": seen}

        report["exeIdentity"] = {"path": str(exe), "bytes": exe.stat().st_size,
                                 "sha256": sha256(exe),
                                 "mtime": time.strftime(
                                     "%Y-%m-%dT%H:%M:%S", time.localtime(exe.stat().st_mtime))}
        # Checked before the desktop launch, not after it. A shell whose loader points at a dev
        # server paints nothing without that server; learning that from the attached page burns the
        # run's one window and reports `rail_never_painted`, which is a symptom of the wrong binary
        # rather than a finding about the product.
        embedded = carries_embedded_bundle(exe)
        report["exeIdentity"].update(embedded)
        if not embedded.get("embeddedBundle"):
            raise ProbeError(
                f"no_embedded_bundle: {exe.name} carries no built frontend in its own bytes "
                f"(assetNames={json.dumps(embedded.get('assetNames'), ensure_ascii=False)}, "
                f"devUrlBaked={embedded.get('devUrlBaked')}) — there is no shipped surface to tab "
                f"through. Build it (`npm run build`, then `cargo build --release` in "
                f"apps/observer) and re-run; no window was launched for this verdict.")

        # ---- stage 2: the real read-only backend, on this run's own runtime root ----
        sys.path.insert(0, str(ROOT / "services" / "orchestration"))
        # The import itself is inside the guard: this checkout is edited concurrently, and a
        # half-saved module (one NameError in `snapshot_api.py` on 2026-10-08) must come out as a
        # named "cannot run" instead of a crash that looks like a product failure.
        try:
            from sidecar import WorkflowSidecar, create_server  # noqa: PLC0415
        except Exception as exc:  # noqa: BLE001
            raise ProbeError(f"no_backend_module: `services/orchestration/sidecar.py` cannot be "
                             f"imported, so the app has nothing real to read: {exc!r}"[:400]) from exc
        runtime_root = OUT / f"sidecar-runtime-{stamp}"
        runtime_root.mkdir(parents=True, exist_ok=True)
        sidecar = WorkflowSidecar(ROOT, runtime_root)
        server = create_server(sidecar, "127.0.0.1", 0)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        base_url = f"http://127.0.0.1:{server.server_port}"
        report["backend"] = {"url": base_url + "/api/v1/snapshot"}
        for _ in range(40):
            try:
                with urllib.request.urlopen(base_url + "/api/v1/snapshot", timeout=2) as r:
                    body = json.loads(r.read())
                if str(body.get("schemaVersion", "")).startswith("workflow/snapshot"):
                    report["backend"].update({"schemaVersion": body.get("schemaVersion"),
                                              "revision": body.get("revision"),
                                              "transport": body.get("transport")})
                    break
            except Exception:  # noqa: BLE001
                time.sleep(0.25)
        else:
            raise ProbeError(f"no_backend_snapshot: the v3 endpoint never answered at {base_url}")

        # ---- stage 3: ONE desktop launch; every measurement lives inside it ----
        cdp_port = u19.pick_free_port()
        udf = OUT / f"EBWebView-{stamp}"
        env = dict(os.environ)
        env["WORK_LAB_OBSERVER_API_URL"] = base_url + "/api/v1/snapshot"
        # WebView2 creates one browser environment per user-data folder and reads these args when
        # it creates it — the same process-level injection u19_verify_once proved.
        env["WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS"] = (
            f"--remote-debugging-port={cdp_port} --remote-allow-origins=*")
        env["WEBVIEW2_USER_DATA_FOLDER"] = str(udf)
        errlog = OUT / f"app_stderr_{stamp}.log"
        errlog.write_bytes(b"")
        app = subprocess.Popen([str(exe)], cwd=str(OBS / "src-tauri"), env=env,
                               stdout=subprocess.DEVNULL, stderr=open(errlog, "wb"))
        report["launch"] = {"pid": app.pid, "cdpPortRequested": cdp_port,
                            "webview2UserDataFolder": str(udf), "cwd": str(OBS / "src-tauri")}
        time.sleep(args.boot_wait)
        if app.poll() is not None:
            raise ProbeError(
                f"app_launch_failed: {exe.name} exited rc={app.returncode} "
                f"(0x{app.returncode & 0xFFFFFFFF:08X}) before any measurement; stderr tail="
                f"{errlog.read_text(encoding='utf-8', errors='replace')[-300:]!r}")
        try:
            ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
        except Exception:  # noqa: BLE001
            pass
        report["windowState"] = window_state(app.pid)

        deadline = time.time() + args.cdp_wait
        attempts: list[str] = []
        targets: list[dict] = []
        working_shape = None
        while time.time() < deadline:
            if app.poll() is not None:
                raise ProbeError(f"app_died_before_cdp: rc={app.returncode} "
                                 f"stderr tail="
                                 f"{errlog.read_text(encoding='utf-8', errors='replace')[-240:]!r}")
            # Ask the release line's own shape first; if this runtime stalls it (measured 2026-10-08:
            # every round `ERR recv TimeoutError` with the app alive and visible), fall back to the
            # header set the current Blink answers. Which one answered is recorded, not assumed.
            for shape in (("u19", "blink") if working_shape is None else (working_shape,)):
                body = devtools_get("/json/version", cdp_port, shape)
                if '"Browser"' in body:
                    working_shape = shape
                    try:
                        listed = json.loads(devtools_get("/json/list", cdp_port, shape))
                    except Exception as exc:  # noqa: BLE001
                        attempts.append(f"{shape} list failed {exc!r}"[:140])
                        listed = []
                    if isinstance(listed, list) and listed:
                        targets = listed
                        report["cdpVersion"] = body[:300]
                        report["cdpDiscoveryShape"] = shape
                        break
                attempts.append(f"{shape} :{cdp_port} -> {body[:110]}")
            if targets:
                break
            time.sleep(1.5)
        report["cdpAttempts"] = attempts[-8:]
        report["cdpTargets"] = [{"type": t.get("type"), "url": str(t.get("url"))[:110],
                                 "title": t.get("title")} for t in targets]
        pages = [t for t in targets if t.get("type") == "page" and t.get("webSocketDebuggerUrl")]
        if not pages:
            raise ProbeError(
                f"no_cdp_port: the debug port {cdp_port} this run asked WebView2 to open served no "
                f"page target within {args.cdp_wait}s, in either request shape "
                f"(app alive={app.poll() is None}, window={report['windowState'].get('size')}, "
                f"visible={report['windowState'].get('visible')}, "
                f"targets={json.dumps(report['cdpTargets'], ensure_ascii=False)[:160]}); "
                f"attempts={json.dumps(attempts[-4:], ensure_ascii=False)[:320]}")

        # The app can expose more than one page target; keep the one that actually carries the rail
        # instead of assuming the first page is the main window. The socket URL is rebuilt from the
        # port this run asked for: Blink builds it from the request's Host header, so the portless
        # shape echoes a portless URL that refuses on connect.
        client = make_client(u19)
        for t in pages:
            ws_path = str(t["webSocketDebuggerUrl"]).split("://", 1)[-1].split("/", 1)[-1]
            ws_url = f"ws://127.0.0.1:{cdp_port}/{ws_path}"
            probe = KeyedCDP(ws_url, u19, client=client)
            keep = False
            try:
                probe.cmd("Runtime.enable")
                read = read_rail(probe)
                page = read.get("page") or {}
                entry = {"url": str(t.get("url"))[:110], "title": t.get("title"),
                         "laneButtons": page.get("laneButtons"),
                         "focusables": page.get("focusables"), "sample": read.get("sample")}
                if not page.get("laneButtons"):
                    entry["shape"] = read.get("shape")
                    if read.get("readError"):
                        entry["readError"] = read["readError"]
                report.setdefault("pageCandidates", []).append(entry)
                keep = bool(page.get("laneButtons"))
            except Exception as exc:  # noqa: BLE001
                report.setdefault("pageCandidates", []).append(
                    {"url": str(t.get("url"))[:110], "ws": ws_url, "error": repr(exc)[:220]})
            if keep:
                cdp = probe
                report["chosenTarget"] = {"url": str(t.get("url"))[:110], "ws": ws_url,
                                          "discoveryShape": working_shape}
                break
            probe.close()
        if cdp is None:
            # A page that painted its controls but has no lane attribute is a different finding from
            # a page that never painted, and the difference is the whole story here: the lane
            # identity is what Enter is asserted against.
            shapes = [c.get("shape") for c in report.get("pageCandidates", []) if c.get("shape")]
            painted = any(s and s.get("navButtons", 0) > 0 and s.get("bodyChars", 0) > 200
                          for s in shapes)
            raise ProbeError(
                f"{'no_lane_identity_in_attached_bundle' if painted else 'rail_never_painted'}: the "
                f"debug port answered and the page is attached, but no page target carries lane "
                f"items to tab through; shapes={json.dumps(shapes, ensure_ascii=False)[:520]}; "
                f"candidates={json.dumps(report.get('pageCandidates'), ensure_ascii=False)[:320]}")
        cdp.cmd("Page.enable")
        cdp.cmd("Log.enable")

        measured = measure(cdp, {"tabs": args.tabs, "shift_tabs": args.shift_tabs,
                                 "max_tabs_to_lane": args.max_tabs_to_lane,
                                 "target_lane": args.target_lane,
                                 "key_pause": args.key_pause, "settle": args.settle}, report)
        report["measured"] = measured
        verdict = judge(measured)
        report["verdict"] = verdict
        tab_stops = len(measured["tabs"])
        distinct_stops = len({str(s.get("selector")) for s in measured["tabs"]})
        lane_stops = len([s for s in measured["tabs"] if s.get("lane")])
        if verdict["passed"]:
            verdict_line = (f"KEYBOARD_FOCUS_GATE_PASS tabStops={tab_stops} "
                            f"distinctStops={distinct_stops} laneStops={lane_stops} "
                            f"enterLane={measured['enter'].get('pressedLane')} "
                            f"exeSha={report['exeIdentity']['sha256'][:12]} "
                            f"evidence={json_out}")
            exit_code = 0
        else:
            verdict_line = (f"KEYBOARD_FOCUS_GATE_FAIL reason={verdict['failing'][0]} "
                            f"failing={','.join(verdict['failing'])} "
                            f"detail={verdict['reason'][:300]} "
                            f"sideFindings={','.join(verdict['sideFindings']) or 'none'}")
            exit_code = 1
        if artifact.get("status") != "PASS":
            # Measured, but not on bytes this tree is entitled to call current: no gate.
            report["gateSuppressedBecause"] = "the binary is not current for this tree"
            verdict_line = (f"KEYBOARD_FOCUS_GATE_NOT_RUN reason=no_current_binary "
                            f"(instrument measured on the superseded exe: "
                            f"checks={'PASS' if verdict['passed'] else 'FAIL:' + ','.join(verdict['failing'])}; "
                            f"artifact={str(artifact.get('reason'))[:200]})")
            exit_code = 3
    except ProbeError as exc:
        verdict_line = f"KEYBOARD_FOCUS_GATE_NOT_RUN reason={str(exc)[:460]}"
        report["notRun"] = str(exc)
        exit_code = 3
    except Exception as exc:  # noqa: BLE001 — a probe that dies cannot be green either
        import traceback
        report["error"] = repr(exc)
        report["traceback"] = traceback.format_exc()[-1500:]
        verdict_line = f"KEYBOARD_FOCUS_GATE_NOT_RUN reason=probe_crashed {exc!r}"[:460]
        exit_code = 3
    finally:
        if cdp:
            cdp.close()
        if app is not None:
            if app.poll() is None:
                app.terminate()
                try:
                    app.wait(timeout=10)
                except Exception:  # noqa: BLE001
                    subprocess.run(["taskkill", "/F", "/T", "/PID", str(app.pid)],
                                   capture_output=True, check=False)
                    try:
                        app.wait(timeout=10)
                    except Exception:  # noqa: BLE001
                        report["residue"].append(f"app pid {app.pid} still running")
            try:
                if app.stderr:
                    app.stderr.close()
            except Exception:  # noqa: BLE001
                pass
            report["appExitCode"] = app.returncode
        if udf is not None:
            # The WebView2 browser tree keeps --user-data-dir a moment after the parent dies
            # (WinError 32, measured 2026-10-08 in scripts/audit/topbar_geometry_via_cdp.py).
            # Retry bounded, then name what still cannot go rather than swallowing it.
            last: OSError | None = None
            for _ in range(12):
                try:
                    shutil.rmtree(udf)
                    last = None
                    break
                except OSError as exc:
                    last = exc
                    time.sleep(0.5)
            if last is not None:
                report["residue"].append(f"{udf} {last!r}")
        if server is not None:
            try:
                server.shutdown()
                server.server_close()
            except Exception:  # noqa: BLE001
                report["residue"].append("sidecar server did not close cleanly")
        try:
            if (OUT / f"sidecar-runtime-{stamp}").is_dir():
                shutil.rmtree(OUT / f"sidecar-runtime-{stamp}")
        except OSError as exc:
            report["residue"].append(f"sidecar runtime {exc!r}"[:160])
        report["endedAt"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
        report["verdictLine"] = verdict_line
        report["evidencePath"] = str(json_out)
        json_out.parent.mkdir(parents=True, exist_ok=True)
        json_out.write_text(json.dumps(report, indent=2, ensure_ascii=False, default=str),
                            encoding="utf-8")

    for line in report.get("tabSequence", [])[:80]:
        print(f"[KBF] tab {line['i']:>2} sidebar={str(line['sidebar']):<5} "
              f"fv={line['fv']} outline={json.dumps(line['outline'], ensure_ascii=False)} "
              f"{str(line['selector'])[:72]}")
    if report.get("measured"):
        ent = report["measured"]["enter"]
        print("[KBF] enter " + json.dumps({
            "pressed": ent.get("pressedLane"),
            "before": (ent.get("before") or {}).get("activeClassLane"),
            "after": (ent.get("after") or {}).get("activeClassLane"),
            "mainSigChanged": (ent.get("before") or {}).get("mainSig")
            != (ent.get("after") or {}).get("mainSig"),
            "seekTabs": ent.get("seekTabPresses")}, ensure_ascii=False))
        print("[KBF] escape " + json.dumps({
            "nonGetDuringEscape": report["measured"]["escape"]["writes"],
            "invokesDuringEscape": report["measured"]["escape"]["invokes"],
            "controlPOSTseenByPageHook": report["measured"]["control"]["observedByPageHook"],
            "controlPOSTseenByCdpNetwork": report["measured"]["control"]["observedByCdpNetwork"]},
            ensure_ascii=False))
        for c in report["verdict"]["checks"]:
            print(f"[KBF] {'PASS' if c['pass'] else 'FAIL'}"
                  f"{'      ' if c['gating'] else ' (reported)'} {c['check']:<38} {c['detail']}")
        if report["verdict"]["sideFindings"]:
            print("KEYBOARD_FOCUS_SIDE_FINDINGS " + ",".join(report["verdict"]["sideFindings"]))
    if report.get("residue"):
        print("KEYBOARD_FOCUS_RESIDUE " + json.dumps(report["residue"], ensure_ascii=False))
    print("[KBF] evidence " + str(json_out))
    print(verdict_line)
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
