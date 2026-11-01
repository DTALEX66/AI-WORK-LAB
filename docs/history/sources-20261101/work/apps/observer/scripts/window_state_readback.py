#!/usr/bin/env python
r"""WINDOW STATE READBACK — measure the real panel window, never an emulation of it.

Why this exists (the gap it closes)
-----------------------------------
`scripts/audit/topbar_geometry_via_cdp.py` is a required CI step, and in one
recorded run it reported a 500x629 viewport while `tauri.conf.json` declares the
panel window at 440x680. Reproduced here rather than argued: that script's
`measure()` starts **Chrome with `--headless=new --window-size=440,680`** and
reads `innerWidth/innerHeight` out of the page (topbar_geometry_via_cdp.py:381
-433). It never launches `app.exe` and never touches the Tauri window at all, so
the two numbers describe two different objects measured by two different
subsystems. The Rust side only ever SET geometry (`set_position`, the probe
builder's `inner_size`) — nothing read a window back.

This probe closes it from the native side: `app.exe` is launched for real, the
read-only `window_metrics` command (apps/observer/src-tauri/src/lib.rs) reports
the window's real inner/outer size, position and scale factor over the same CDP
transport `u19_webview_e2e.py` already trusts, and the declared numbers come from
the Config the binary was built with. The Chrome emulation is then measured a
second time in the same run so the gap is a number on one line, not a story.

Units, because this is where the confusion lived: `tauri.conf.json`
width/height are LOGICAL pixels of the INNER area
(tauri-runtime-wry-2.11.4/src/lib.rs:932 maps them through
`.inner_size(TaoLogicalSize::new(w, h))`), while `inner_size()` reads PHYSICAL
pixels. The comparison is made in logical pixels after dividing by `scale_factor`
on both sides, and every raw number is printed so the conversion can be checked
instead of trusted.

Verdicts
--------
    WINDOW_STATE_READBACK_PASS declared=440x680 measured=440x680 scale=1.0   exit 0
    WINDOW_STATE_READBACK_FAIL reason=...                                    exit 1
    WINDOW_STATE_READBACK_NOT_RUN reason=...                                 exit 3

`decide_window_state_claim()` is pure — no app, no browser, no filesystem — and
is guarded by tests/ci/test_window_state_claim.py. Fail-closed by construction: a
missing, unreadable, unresolvable or non-native readback can only land on FAIL or
NOT_RUN, never on PASS. Exit 3 is a red in the aggregate gate on purpose
(same convention as the geometry gate); only exit 0 is green.

Usage
-----
    python apps/observer/scripts/window_state_readback.py \
        --label panel --json-out .project-local/runs/window-state/readback.json

Every path this probe writes — the evidence JSON, the app's stderr log, the
emulation browser's `--user-data-dir` — is resolved under `.project-local/runs/`
and checked against the project boundary helper before anything is created. An
`--evidence-dir` / `--json-out` outside the Git root is refused with exit 3 and
writes nothing at all; the scratch is never taken from the host temp directory,
because a boundary expressed as "wherever temp happens to be" is ERR-163
(`C:\Windows\Temp\wsr-test-*`, one directory per test that trusted `%TEMP%`).

Set CARGO_TARGET_DIR (or pass --target-dir) if the release binary was built
outside apps/observer/src-tauri/target.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]          # WORK-LAB repo root
OBS = ROOT / "apps" / "observer"
U19_PATH = OBS / "scripts" / "u19_webview_e2e.py"
# The single authority on what "inside the project boundary" means. This probe
# used to derive its scratch root from wherever the host happened to put the temp
# directory (ERR-163) — see `boundary_refusal`.
PROJECT_TEMP_PATH = (ROOT / "packages" / "client-neutral-core"
                     / "scripts" / "project_temp.py")
DEFAULT_EVIDENCE = ROOT / ".project-local" / "runs" / "window-state"

GATE = "WINDOW_STATE_READBACK"
# Same slack the Rust command uses (apps/observer/src-tauri/src/lib.rs,
# GEOMETRY_TOLERANCE_LOGICAL_PX). Kept as a local literal — and asserted equal
# to the value the payload carries — so the two layers cannot silently diverge.
TOLERANCE_LOGICAL_PX = 2.0
# The declared panel size, quoted here only as the expected value of the printed
# line. The authoritative declared numbers are carried by the payload (which
# reads the Config embedded in the binary) and cross-checked against
# tauri.conf.json on disk by `declared_from_conf`.
DECLARED_PANEL = (440, 680)
EMULATION_WINDOW_SIZE = "440,680"


# ---------------------------------------------------------------------------
# Pure claim rule. No app, no browser, no filesystem. tests/ci imports this.
# ---------------------------------------------------------------------------
def decide_window_state_claim(metrics, *, tolerance: float = TOLERANCE_LOGICAL_PX,
                              tree_declared: dict | None = None) -> dict:
    """Decide one native readback against its declared geometry.

    `metrics` is the `window_metrics` payload (a dict), or None when no readback
    was obtained. `tree_declared`, when given, is the same window's declared
    width/height read straight off `tauri.conf.json` on disk: the payload carries
    the Config *embedded in the binary*, so comparing the two convicts a binary
    built from a different config than the tree being reviewed. Returns
    `{"status": "PASS"|"FAIL"|"NOT_RUN", "reason": str|None, "declared": "WxH",
      "measured": "WxH"|None, "scale": float|None, "deviation": "dWxDh"|None}`.

    Every branch that cannot prove the claim says so instead of defaulting to
    green — the project rule is that a UI claim is real only when measured.
    """
    out = {"status": "NOT_RUN", "reason": None, "declared": None, "measured": None,
           "scale": None, "deviation": None}
    if metrics is None:
        out["reason"] = "no readback obtained"
        return out
    if not isinstance(metrics, dict):
        out["status"] = "FAIL"
        out["reason"] = f"readback is not an object: {type(metrics).__name__}"
        return out

    # A number that came from emulation is not a measurement of the window.
    mode = metrics.get("measurementMode") or metrics.get("measurement_mode")
    if mode not in (None, "native-readback"):
        out["status"] = "FAIL"
        out["reason"] = f"readback is emulated, not native: measurementMode={mode!r}"
        return out
    if metrics.get("__error"):
        out["status"] = "FAIL"
        out["reason"] = f"ipc readback error: {metrics['__error']}"
        return out

    declared = metrics.get("declared") or {}
    d_w, d_h = declared.get("width"), declared.get("height")
    if not (isinstance(d_w, (int, float)) and isinstance(d_h, (int, float))):
        out["status"] = "FAIL"
        out["reason"] = "declared geometry absent from the readback — nothing to match"
        return out
    out["declared"] = f"{int(d_w)}x{int(d_h)}"

    if tree_declared is not None:
        t_w, t_h = tree_declared.get("width"), tree_declared.get("height")
        if (t_w, t_h) != (d_w, d_h):
            out["status"] = "FAIL"
            out["reason"] = (f"binary/config drift: the built shell declares "
                             f"{int(d_w)}x{int(d_h)} but tauri.conf.json on disk "
                             f"declares {t_w}x{t_h} for this label — the binary is "
                             f"not built from this tree")
            return out

    if not metrics.get("resolutionSucceeded"):
        out["status"] = "FAIL"
        out["reason"] = (f"window label not resolved: {metrics.get('windowLabel')!r} "
                         f"({metrics.get('resolutionNote') or 'no note'})")
        return out

    measured = metrics.get("innerSizeLogical") or metrics.get("inner_size_logical")
    if not isinstance(measured, dict) \
            or not isinstance(measured.get("width"), (int, float)) \
            or not isinstance(measured.get("height"), (int, float)):
        out["status"] = "FAIL"
        out["reason"] = "no measured inner size in the readback (unmeasured is never green)"
        return out
    out["measured"] = f"{round(measured['width'], 1)}x{round(measured['height'], 1)}"

    scale = metrics.get("scaleFactor")
    if not isinstance(scale, (int, float)) or scale <= 0:
        out["status"] = "FAIL"
        out["reason"] = f"scale factor missing or non-positive: {scale!r}"
        return out
    out["scale"] = scale

    dev_w = measured["width"] - d_w
    dev_h = measured["height"] - d_h
    out["deviation"] = f"{dev_w:+.1f}x{dev_h:+.1f}"

    # Cross-check the Rust verdict instead of trusting it: the payload carries a
    # verdict AND the raw numbers, so a bug in either layer must be able to
    # convict the claim. Disagreement is red even if both would individually
    # allow it, because a gate that only re-reads a verdict proves nothing.
    verdict = metrics.get("verdict") or {}
    reported = verdict.get("status")
    recomputed = "match" if (abs(dev_w) <= tolerance and abs(dev_h) <= tolerance) else "mismatch"
    carried_tol = verdict.get("toleranceLogicalPx")
    if isinstance(carried_tol, (int, float)) and abs(carried_tol - tolerance) > 1e-9:
        out["status"] = "FAIL"
        out["reason"] = (f"tolerance drift: probe says {tolerance}, payload says "
                         f"{carried_tol} — one rule cannot live in two places")
        return out
    if reported != recomputed:
        out["status"] = "FAIL"
        out["reason"] = (f"verdict disagreement: payload says {reported!r}, "
                         f"recomputed {recomputed!r} from {out['measured']} vs "
                         f"{out['declared']}")
        return out
    if reported == "match":
        out["status"] = "PASS"
        return out
    if reported == "mismatch":
        out["status"] = "FAIL"
        out["reason"] = (f"measured {out['measured']} != declared {out['declared']} "
                         f"beyond +/-{tolerance} logical px (deviation {out['deviation']})")
        return out
    out["status"] = "FAIL"
    out["reason"] = f"undecidable verdict status: {reported!r}"
    return out


def _pair(value) -> str:
    if not isinstance(value, dict):
        return "unknown"
    return f"{value.get('width')}x{value.get('height')}"


def declared_from_conf(conf_path: Path, label) -> dict | None:
    """The same window's declared size straight off tauri.conf.json on disk.

    Read-only, and returns None (never a guess) when the file or the label is
    absent, so the cross-check degrades to 'not available' instead of to a false
    agreement.
    """
    if not label:
        return None
    try:
        conf = json.loads(conf_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    for window in conf.get("app", {}).get("windows", []):
        if window.get("label") == label:
            return {"width": window.get("width"), "height": window.get("height")}
    return None


# ---------------------------------------------------------------------------
# Boundary. Every path this probe writes is decided here, not by the host.
# ---------------------------------------------------------------------------
def load_project_temp():
    r"""Load the project's own bounded fixture helper by path.

    `apps/observer` and `packages/client-neutral-core` are separate module roots with
    no shared package, so this is the same importlib-by-path trick `load_u19` uses.
    It raises when the helper is missing instead of returning a stand-in: ERR-163 was
    precisely a boundary rule that got re-implemented locally as a convention ("the
    temp directory is fine, everybody uses it"), so a run that cannot reach the
    authority gets NO readback and an exit 3, not a silently duplicated rule.
    """
    spec = importlib.util.spec_from_file_location("project_temp", PROJECT_TEMP_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"no import spec for {PROJECT_TEMP_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[attr-defined]
    for name in ("inside_project", "temp_root", "fixture_dir"):
        if not hasattr(module, name):
            raise RuntimeError(f"{PROJECT_TEMP_PATH} no longer exposes {name}()")
    return module


def boundary_refusal(evidence_dir: Path, json_out: Path) -> str | None:
    """Name why these paths may not be written, or None when both are in bounds.

    Checked BEFORE the first mkdir and before the evidence file exists, because the
    defect being closed is that this probe created scratch outside the Git root and
    then treated the leftovers as normal. `.project/governance/project-data-boundary
    .json` says any write outside the root is a spill that has to be traceable and
    cleanable, so a caller who asks for an outside path is refused rather than
    honoured — and the refusal writes nothing anywhere, which is what makes it
    assertable.
    """
    try:
        project_temp = load_project_temp()
    except Exception as exc:
        return (f"boundary helper unavailable, cannot prove the evidence root is "
                f"inside the repo: {PROJECT_TEMP_PATH} ({exc!r})")
    for role, path in (("evidence-dir", evidence_dir), ("json-out", json_out)):
        if not project_temp.inside_project(path):
            return (f"{role} resolves outside the project Git root "
                    f"({project_temp.REPO_ROOT}): {path} — the data boundary makes "
                    f"that a spill, so this probe writes nothing and refuses to run")
    return None


def release_scratch(path: Path) -> str | None:
    r"""Remove a scratch root, reporting a refusal instead of swallowing it.

    ERR-140 and ERR-163 ended the same way on Windows: `shutil.rmtree(...,
    ignore_errors=True)` hid that the directory had survived because a handle was
    still open in it (a SQLite store, a browser process, this probe's own stderr
    log). The wording matches `project_temp._release_tracked` so one grep finds
    every residue in the repository.
    """
    try:
        shutil.rmtree(path)
    except OSError as error:
        print(f"TEMP_RESIDUE_NOT_REMOVED {path} {type(error).__name__}: {error}")
        return f"residue not removed: {path} ({type(error).__name__})"
    return None


# ---------------------------------------------------------------------------
# CDP transport — reuse the harness that already works, do not fork a second one.
# ---------------------------------------------------------------------------
def load_u19():
    spec = importlib.util.spec_from_file_location("u19", U19_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[attr-defined]
    return module


def evaluate(cdp, expression: str, *, await_promise: bool = False):
    """Runtime.evaluate with awaitPromise, and the exception the CDP class hides.

    u19.CDP.evaluate hard-codes awaitPromise=False, which cannot read an
    invoke() promise; the private _send_cmd is the only way to ask. exceptionDeta
    ils is surfaced because a rejected promise otherwise arrives as a silent None.
    """
    res = cdp._send_cmd("Runtime.evaluate", {  # noqa: SLF001 - reuse, not fork
        "expression": expression,
        "returnByValue": True,
        "awaitPromise": await_promise,
    })
    if res.get("exceptionDetails"):
        raise RuntimeError(f"page threw: {json.dumps(res['exceptionDetails'])[:400]}")
    return res.get("result", {}).get("value")


INVOKE_METRICS_JS = """(async () => {
  const i = window.__TAURI_INTERNALS__;
  if (!i || typeof i.invoke !== 'function') {
    return {__error: 'no __TAURI_INTERNALS__.invoke in this page '
                    + '(bridge not injected, or this is not a Tauri webview)'};
  }
  try {
    return await i.invoke('window_metrics', {label: %s});
  } catch (e) {
    return {__error: String(e && (e.message || e))};
  }
})()"""

PAGE_VIEWPORT_JS = """JSON.stringify({
  innerWidth: innerWidth, innerHeight: innerHeight,
  devicePixelRatio: window.devicePixelRatio,
  screenW: screen.width, screenH: screen.height,
  url: location.href.slice(0, 160)
})"""


# Two header shapes, because the two DevTools endpoints on this machine are
# genuinely different (both measured 2026-10-08, not guessed):
#   * WebView2, which serves the Tauri app, answers u19's plain shape — the one
#     `apps/observer/scripts/u19_webview_e2e.py:_cdp_http_get` has always used.
#   * Chrome 154, which serves the emulation leg, stalls a request that carries
#     no User-Agent or that puts a port in `Host:` (recorded at
#     scripts/audit/topbar_geometry_via_cdp.py:291).
# Trying both and recording which one answered beats hard-coding either.
REQUEST_SHAPES = {
    "webview2-plain": lambda port, path: (
        f"GET {path} HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\nConnection: close\r\n\r\n"),
    "chrome-ua-portless-host": lambda port, path: (
        f"GET {path} HTTP/1.1\r\nHost: 127.0.0.1\r\n"
        f"User-Agent: worklab-window-state-readback\r\n"
        f"Accept: application/json\r\nConnection: close\r\n\r\n"),
}


def _http_json(port: int, path: str, shape: str) -> str:
    """Raw loopback GET, terminated by Content-Length rather than by EOF.

    Measured 2026-10-08 against WebView2 154.0.4258.62 on this machine: the
    DevTools HTTP endpoint answers `HTTP/1.1 200 OK` with the whole JSON body and
    then KEEPS THE SOCKET OPEN even though the request asked for `Connection:
    close`. A read-until-EOF loop therefore never returns and the caller concludes
    "no page target" while the answer was already on the wire — which is exactly
    how this probe first reported NOT_RUN with the port demonstrably listening.
    u19_webview_e2e.py:_cdp_http_get still reads to EOF; this one does not, and
    that is the difference between a red and a measurement.
    """
    s = socket.create_connection(("127.0.0.1", port), timeout=6)
    try:
        s.sendall(REQUEST_SHAPES[shape](port, path).encode("latin-1"))
        s.settimeout(6)
        buf = bytearray()
        while b"\r\n\r\n" not in buf:
            piece = s.recv(4096)
            if not piece:
                break
            buf += piece
        head, _, body = bytes(buf).partition(b"\r\n\r\n")
        status = head.split(b"\r\n", 1)[0].decode("latin-1", "replace")
        if "200" not in status:
            raise RuntimeError(f"CDP {path} via {shape}: HTTP {status or 'no response'}")
        headers = head.split(b"\r\n", 1)[1].decode("latin-1", "replace").lower()
        length = None
        for line in headers.split("\r\n"):
            if line.startswith("content-length:"):
                try:
                    length = int(line.split(":", 1)[1].strip())
                except ValueError:
                    length = None
        have = len(body)
        while length is not None and have < length:
            piece = s.recv(min(65536, length - have))
            if not piece:
                break
            body += piece
            have += len(piece)
        if length is None:
            # Chunked or unanswered: fall back to draining until close, bounded.
            s.settimeout(2)
            try:
                while True:
                    piece = s.recv(65536)
                    if not piece:
                        break
                    body += piece
            except OSError:
                pass
        return body.decode("utf-8", "replace")
    finally:
        s.close()


def page_targets(cdp_port: int, tries: int,
                 shapes: tuple = ("webview2-plain", "chrome-ua-portless-host")) -> dict:
    """All `page` targets on a debug port, retried: WebView2 opens lazily.

    Returns `{"pages": [...], "shape": str|None, "errors": [...]}` — never a
    mixed target list, because the caller connects to whatever it gets and a
    non-page target cannot answer Runtime.evaluate. The shape that worked is part
    of the result so a silent endpoint-behaviour change is visible in the
    evidence instead of in a 30s timeout.
    """
    deadline = time.time() + tries * 0.5
    errors: list[str] = []
    used: str | None = None
    while time.time() < deadline:
        for shape in shapes:
            try:
                body = json.loads(_http_json(cdp_port, "/json/list", shape))
            except Exception as exc:
                errors.append(f"{shape}: {repr(exc)[:120]}")
                continue
            used = shape
            pages = [t for t in body if t.get("type") == "page"
                     and t.get("webSocketDebuggerUrl")]
            if pages:
                return {"pages": pages, "shape": used, "errors": errors[-4:]}
        time.sleep(0.5)
    return {"pages": [], "shape": used, "errors": errors[-4:]}


# ---------------------------------------------------------------------------
# The Chrome side of the gap: reproduce what the existing gate actually measures.
# ---------------------------------------------------------------------------
def _serve_dist(dist: Path, u19) -> tuple[subprocess.Popen, int]:
    """Serve the built bundle on a dynamic loopback port — the same mechanism the
    geometry gate uses, so the emulated number stays comparable to the recorded
    one instead of being measured through a different door."""
    port = u19.pick_free_port()
    proc = subprocess.Popen(
        [sys.executable, "-m", "http.server", str(port), "--bind", "127.0.0.1"],
        cwd=str(dist), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return proc, port


def measure_chrome_emulation(u19, browser: str, evidence_dir: Path) -> dict:
    """Launch Chrome `--headless=new --window-size=440,680` on the built dist and
    read innerWidth/innerHeight. This is the number the geometry gate records;
    measuring it here turns 'nobody can explain 500x629' into one line of data.

    Its result can never change the native verdict: the emulation is context for
    the gap line, not evidence about the window.
    """
    out: dict = {"status": "NOT_RUN", "reason": None}
    dist = OBS / "frontend" / "dist"
    if not dist.is_dir():
        out["reason"] = f"no built frontend dist at {dist}"
        return out
    cdp_port = u19.pick_free_port()
    stamp = int(time.time())
    udf = evidence_dir / f"emulation-profile-{stamp}"
    log_path = evidence_dir / f"emulation-chrome-{stamp}.log"
    srv = proc = cdp = None
    try:
        srv, srv_port = _serve_dist(dist, u19)
        url = (f"http://127.0.0.1:{srv_port}/index.html"
               f"?view=compact&mode=UNKNOWN&theme=dark")
        with log_path.open("wb") as log:
            proc = subprocess.Popen(
                [browser, "--headless=new", "--disable-gpu", "--no-sandbox",
                 "--no-first-run", "--no-default-browser-check",
                 "--disable-extensions", f"--user-data-dir={udf}",
                 f"--window-size={EMULATION_WINDOW_SIZE}",
                 f"--remote-debugging-port={cdp_port}",
                 "--remote-allow-origins=*", url],
                stdout=log, stderr=subprocess.STDOUT)
        emu = page_targets(cdp_port, 40,
                           shapes=("chrome-ua-portless-host", "webview2-plain"))
        pages = emu["pages"]
        if not pages:
            tail = ""
            try:
                tail = log_path.read_text(errors="replace")[:200]
            except OSError:
                pass
            out["reason"] = (f"no page target on emulation port {cdp_port}; "
                             f"rc={proc.poll()} errors={emu['errors']} log={tail!r}")
            return out
        time.sleep(1.5)
        cdp = u19.CDP(pages[0]["webSocketDebuggerUrl"])
        viewport = json.loads(evaluate(cdp, PAGE_VIEWPORT_JS))
        out.update({
            "status": "MEASURED",
            "requestedWindowSize": EMULATION_WINDOW_SIZE,
            "viewport": f"{viewport.get('innerWidth')}x{viewport.get('innerHeight')}",
            "devicePixelRatio": viewport.get("devicePixelRatio"),
            "browser": Path(browser).name,
            "pageUrl": (viewport.get("url") or "")[:160],
            "discoveryShape": emu["shape"],
        })
    except Exception as exc:                       # never fail the native claim
        out["reason"] = repr(exc)[:300]
    finally:
        for child in (proc, srv):
            if child is not None:
                child.kill()
                try:
                    child.wait(timeout=10)
                except Exception:
                    pass
        if cdp is not None:
            cdp.close()
        residue = release_scratch(udf)
        out["scratchRelease"] = "RELEASED" if residue is None else residue
    return out


# ---------------------------------------------------------------------------
# The native measurement.
# ---------------------------------------------------------------------------
def read_metrics_via_ipc(u19, cdp_port: int, label: str | None,
                         discover_tries: int) -> dict:
    """Ask the live app for its real window geometry over CDP+IPC.

    `label` None omits the argument and exercises the Rust-side resolution rule.
    Returns {"status": ..., "metrics": dict|None, "page": ..., "attempts": [...],
    "pageViewport": dict|None, "reason": str|None}.
    """
    attempts: list[dict] = []
    expr = INVOKE_METRICS_JS % json.dumps(label)
    deadline = time.time() + discover_tries * 0.5
    shape: str | None = None
    seen_urls: list[str] = []
    saw_navigated = False
    last_reason = "the debug port never listed a page target"

    while time.time() < deadline:
        found = page_targets(cdp_port, 1)
        shape = found["shape"] or shape
        pages = found["pages"]
        if not pages:
            last_reason = (f"debug port answered but listed no page target "
                           f"(shape={shape}, errors={found['errors'][-2:]})")
            time.sleep(0.5)
            continue

        # `about:blank` is the WebView2 state BEFORE navigation: the Tauri IPC
        # bridge is injected with the document, so a blank target can never
        # answer window_metrics. Measured 2026-10-08 — the first target to appear
        # is about:blank, and attaching straight to it produced an IPC_ERROR that
        # looked like a product failure. Wait for a navigated page instead.
        navigated = [t for t in pages
                     if not (t.get("url") or "about:blank").startswith("about:")]
        seen_urls = [(t.get("url") or "")[:80] for t in pages]
        if not navigated:
            last_reason = (f"all {len(pages)} target(s) still pre-navigation: "
                           f"{seen_urls}")
            time.sleep(0.5)
            continue
        saw_navigated = True

        # Prefer the window whose own URL shows the compact view: its page
        # viewport is then directly comparable to the panel geometry it reports.
        ordered = sorted(navigated,
                         key=lambda t: 0 if "view=compact" in (t.get("url") or "") else 1)
        for target in ordered:
            page = {"url": (target.get("url") or "")[:160],
                    "title": target.get("title"),
                    "ws": target.get("webSocketDebuggerUrl")}
            cdp = None
            try:
                cdp = u19.CDP(target["webSocketDebuggerUrl"])
                payload = evaluate(cdp, expr, await_promise=True)
                viewport = json.loads(evaluate(cdp, PAGE_VIEWPORT_JS)) if payload else None
                page["status"] = ("OK" if isinstance(payload, dict)
                                  and not payload.get("__error") else "IPC_ERROR")
                if page["status"] == "IPC_ERROR" and isinstance(payload, dict):
                    page["ipcError"] = str(payload.get("__error"))[:250]
                attempts.append(page)
                if page["status"] == "OK":
                    return {"status": "OK", "metrics": payload, "attempts": attempts,
                            "pageViewport": viewport, "page": page, "reason": None,
                            "discoveryShape": shape, "targetsSeen": seen_urls}
            except Exception as exc:
                page["status"] = "ERROR"
                page["error"] = repr(exc)[:300]
                attempts.append(page)
            finally:
                if cdp is not None:
                    cdp.close()
        last_reason = ("every navigated target refused the window_metrics readback: "
                       + json.dumps(attempts)[-500:])
        time.sleep(0.5)

    return {"status": "FAIL" if saw_navigated else "NOT_RUN",
            "metrics": None, "attempts": attempts, "pageViewport": None,
            "discoveryShape": shape, "targetsSeen": seen_urls,
            "reason": f"{last_reason} (budget {discover_tries * 0.5:.0f}s)"}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=GATE)
    ap.add_argument("--label", action="append", default=None,
                    help="window label to measure; repeat to batch several labels in "
                         "the ONE app launch this probe performs (default: panel, main)")
    ap.add_argument("--no-label", action="store_true",
                    help="omit the label argument and let the Rust command resolve it")
    ap.add_argument("--exe", default=None,
                    help="explicit app.exe path, bypassing the build-provenance check "
                         "(recorded as such in the evidence; a CI run should not use it)")
    ap.add_argument("--target-dir", default=None,
                    help="CARGO_TARGET_DIR to search for the built release binary")
    ap.add_argument("--json-out", default=None, help="evidence JSON path")
    ap.add_argument("--evidence-dir", default=None,
                    help="directory for the emulation browser's scratch (default: "
                         f"{DEFAULT_EVIDENCE})")
    ap.add_argument("--discover-tries", type=int, default=90,
                    help="0.5s attempts to wait for a CDP page target")
    ap.add_argument("--skip-emulation", action="store_true",
                    help="do not re-measure the Chrome --window-size path")
    args = ap.parse_args(argv)
    # One launch, every measurement: the desktop app must not be started per
    # label, so all requested windows are read from the same running process.
    labels: list = [None] if args.no_label else (args.label or ["panel", "main"])

    # RESOLVED to absolute on purpose: `evidence_dir` is handed to the app as
    # WORK_LAB_U19_PROBE_STATUS, and the app is launched with cwd=src-tauri, so a
    # relative path here would make the shell write its probe status next to the
    # crate instead of into the evidence root (measured: the file simply vanished
    # and the run looked like "the probe block never executed").
    evidence_dir = (Path(args.evidence_dir) if args.evidence_dir
                    else DEFAULT_EVIDENCE).resolve()
    json_out = (Path(args.json_out) if args.json_out
                else evidence_dir / "readback.json").resolve()

    # Boundary first, before a single byte or directory is created: an evidence
    # root the project cannot account for is a spill, not a convenience.
    refusal = boundary_refusal(evidence_dir, json_out)
    if refusal:
        print(f"{GATE}_NOT_RUN reason={refusal}")
        return 3
    evidence_dir.mkdir(parents=True, exist_ok=True)

    result: dict = {
        "gate": GATE, "startedAt": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "requestedLabels": labels,
        "verdict": "NOT_RUN", "reason": None, "stages": {},
        "toleranceLogicalPx": TOLERANCE_LOGICAL_PX,
        "evidencePath": str(json_out),
        "boundary": {"repoRoot": str(ROOT), "evidenceDir": str(evidence_dir),
                     "checkedBy": str(PROJECT_TEMP_PATH)},
    }

    def finish(code: int, reason: str | None, claim: dict | None = None) -> int:
        if reason:
            result["reason"] = reason
        if claim:
            result["claim"] = claim
        result["endedAt"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
        json_out.write_text(json.dumps(result, indent=2, ensure_ascii=False),
                            encoding="utf-8")
        status = {"PASS": "PASS", "FAIL": "FAIL"}.get(result["verdict"], "NOT_RUN")
        if claim:
            print(f"{GATE}_{status} declared={claim.get('declared') or 'unknown'} "
                  f"measured={claim.get('measured') or 'unmeasured'} "
                  f"scale={claim.get('scale') if claim.get('scale') is not None else 'unknown'}")
        else:
            print(f"{GATE}_{status} reason={reason or result.get('reason')}")
        print(f"[{GATE}] evidence: {json_out}")
        return code

    # --- stage 0: the harness we reuse -------------------------------------
    try:
        u19 = load_u19()
    except Exception as exc:
        result["stages"]["harness"] = {"status": "NOT_RUN", "reason": repr(exc)}
        return finish(3, f"cannot load u19_webview_e2e.py: {exc!r}")

    # --- stage 1: which binary, and can this machine prove it? -------------
    if args.target_dir:
        os.environ["CARGO_TARGET_DIR"] = args.target_dir
    exe: Path | None = None
    if args.exe:
        exe = Path(args.exe)
        result["stages"]["artifact"] = {
            "status": "PASS" if exe.is_file() else "NOT_RUN", "basis": "explicit --exe",
            "path": str(exe),
            "basisLimit": "an --exe override is not checked against the tree that built it"}
        if not exe.is_file():
            return finish(3, f"--exe path does not exist: {exe}")
    else:
        exe, artifact = u19.resolve_app_exe()
        result["stages"]["artifact"] = artifact
        if exe is None:
            return finish(3, f"no provably-current release binary: "
                             f"{(artifact or {}).get('reason')}")

    # --- stage 2: launch the real shell once, batch every measurement in it --
    cdp_port = u19.pick_free_port()
    env = dict(os.environ)
    # The CDP probe window (lib.rs) is opt-in and default-OFF in the shipped
    # binary; WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS is what actually opens the
    # debug port for the whole browser process (measured in U19: per-window args
    # are inert because the environment is created once per user-data folder).
    env["WORK_LAB_U19_CDP_PORT"] = str(cdp_port)
    env["WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS"] = (
        f"--remote-debugging-port={cdp_port} --remote-allow-origins=*")
    env["WORK_LAB_U19_PROBE_STATUS"] = str(evidence_dir / "probe_status.txt")
    env["NO_AUTO_UPDATE"] = "1"
    # No WORK_LAB_OBSERVER_API_URL: geometry does not need a backend, and
    # leaving it unset means no sidecar is required for this gate to run.
    errlog = evidence_dir / "app_stderr.log"
    errlog.write_bytes(b"")
    app = None
    # Named and closed: `stderr=open(errlog, "wb")` inline left a handle alive for
    # the whole process, and on Windows a directory a handle still points into
    # cannot be removed — that leaked handle is why every previous run of this
    # probe left its scratch directory behind instead of only leaving it unwritten.
    errhandle = open(errlog, "wb")
    try:
        app = subprocess.Popen([str(exe)], cwd=str(OBS / "src-tauri"), env=env,
                               stdout=subprocess.DEVNULL, stderr=errhandle)
        result["stages"]["launch"] = {"status": "RUNNING", "pid": app.pid,
                                      "cdpPort": cdp_port, "exe": str(exe)}
        print(f"[{GATE}] launched {exe.name} pid={app.pid} cdp=:{cdp_port}")

        # --- stage 3: native readback over IPC, batched in this one launch ---
        readings: list[dict] = []
        for lbl in labels:
            got = read_metrics_via_ipc(u19, cdp_port, lbl, args.discover_tries)
            if got["status"] != "OK":
                result["stages"]["ipc"] = {k: got.get(k) for k in
                                           ("status", "attempts", "page", "reason",
                                            "discoveryShape", "targetsSeen")}
                poll = app.poll()
                result["stages"]["processLiveness"] = {
                    "status": "ALIVE" if poll is None else "EXITED_EARLY",
                    "returncode": poll,
                    "stderrTail": errlog.read_text(errors="replace")[-400:] or None}
                return finish(3 if got["status"] == "NOT_RUN" else 1, got["reason"])
            metrics = got["metrics"]
            tree_declared = declared_from_conf(
                OBS / "src-tauri" / "tauri.conf.json", metrics.get("windowLabel"))
            claim = decide_window_state_claim(metrics, tree_declared=tree_declared)
            readings.append({
                "requestedLabel": lbl,
                "resolvedLabel": metrics.get("windowLabel"),
                "metrics": metrics,
                "claim": claim,
                "pageViewport": got["pageViewport"],
                "attempts": got.get("attempts", []),
                "discoveryShape": got.get("discoveryShape"),
                "targetsSeen": got.get("targetsSeen"),
                "declaredCrossCheck": {
                    "status": "AVAILABLE" if tree_declared else "NOT_RUN",
                    "treeDeclared": tree_declared,
                    "binaryDeclared": {k: (metrics.get("declared") or {}).get(k)
                                       for k in ("width", "height")},
                },
            })
        poll = app.poll()
        result["stages"]["ipc"] = {
            "status": "OK", "labelsRead": [r["resolvedLabel"] for r in readings],
            "discoveryShape": readings[0].get("discoveryShape"),
            "targetsSeen": readings[0].get("targetsSeen"),
            "attempts": readings[0]["attempts"] if readings else []}
        result["stages"]["processLiveness"] = {
            "status": "ALIVE" if poll is None else "EXITED_EARLY",
            "returncode": poll,
            "stderrTail": errlog.read_text(errors="replace")[-400:] or None}
        result["stages"]["declaredCrossCheck"] = readings[0]["declaredCrossCheck"]
        result["measurements"] = [
            {"requestedLabel": r["requestedLabel"], "resolvedLabel": r["resolvedLabel"],
             "claim": r["claim"], "metrics": r["metrics"]} for r in readings]

        # --- stage 4: the emulation side, measured in the same run ---------
        emulation: dict = {"status": "NOT_RUN", "reason": "skipped by --skip-emulation"}
        if not args.skip_emulation:
            browser = None
            for name in ("chrome", "chrome.exe", "msedge", "msedge.exe"):
                browser = shutil.which(name)
                if browser:
                    break
            if not browser:
                for base in (os.environ.get("PROGRAMFILES"),
                             os.environ.get("PROGRAMFILES(X86)")):
                    for sub in ("Google/Chrome/Application/chrome.exe",
                                "Microsoft/Edge/Application/msedge.exe"):
                        cand = Path(base or "") / sub
                        if cand.is_file():
                            browser = str(cand)
                            break
                    if browser:
                        break
            if browser:
                emulation = measure_chrome_emulation(u19, browser, evidence_dir)
            else:
                emulation = {"status": "NOT_RUN",
                             "reason": "no Chrome/Edge binary found to reproduce the "
                                       "geometry gate's emulated viewport"}
        result["stages"]["emulation"] = emulation

        # --- the claim, and the one-line gap -------------------------------
        # The WORST reading decides the printed verdict: an extra label that went
        # red must never hide behind the primary label's green.
        primary = readings[0]
        deciding = next((r for r in readings if r["claim"]["status"] == "FAIL"),
                        None) or \
            next((r for r in readings if r["claim"]["status"] == "NOT_RUN"), None) or primary
        claim = dict(deciding["claim"])
        if claim["status"] != "PASS":
            claim["reason"] = (f"[label={deciding['resolvedLabel']}] "
                               f"{claim['reason'] or 'no reason given'}")
        metrics = deciding["metrics"]
        result["verdict"] = claim["status"]
        for r in readings:
            print(f"[{GATE}] label={r['resolvedLabel']} {r['claim']['status']} "
                  f"declared={r['claim'].get('declared')} "
                  f"measured={r['claim'].get('measured')} scale={r['claim'].get('scale')} "
                  f"{r['claim'].get('reason') or ''}")
        measured_inner = metrics.get("innerSizePhysical") or {}
        page_vp = deciding["pageViewport"] or {}
        gap = None
        if page_vp.get("innerWidth"):
            gap = {
                "pageViewportCssPx": f"{page_vp['innerWidth']}x{page_vp['innerHeight']}",
                "nativeInnerPhysicalPx": _pair(measured_inner),
                "nativeInnerLogicalPx": claim.get("measured"),
                "declaredLogicalPx": claim.get("declared"),
                "devicePixelRatio": page_vp.get("devicePixelRatio"),
                "scaleFactorFromShell": claim.get("scale"),
                "emulatedWindowSizeRequested": EMULATION_WINDOW_SIZE,
                "emulatedViewport": emulation.get("viewport"),
            }
        result["gap"] = gap
        if gap:
            print(f"[{GATE}] GAP real_window={gap['nativeInnerPhysicalPx']} physical / "
                  f"{gap['nativeInnerLogicalPx']} logical == page viewport "
                  f"{gap['pageViewportCssPx']} css (scale={gap['scaleFactorFromShell']}, "
                  f"dpr={gap['devicePixelRatio']}); "
                  f"chrome_emulation(--window-size={EMULATION_WINDOW_SIZE})="
                  f"{gap['emulatedViewport'] or 'NOT_RUN'} vs declared "
                  f"{gap['declaredLogicalPx']}")
        code = {"PASS": 0, "FAIL": 1}.get(claim["status"], 3)
        return finish(code, claim["reason"], claim)
    except Exception as exc:
        result["stages"]["error"] = {"status": "FAIL", "reason": repr(exc)}
        return finish(1, f"unexpected failure: {exc!r}")
    finally:
        if app is not None:
            app.terminate()
            try:
                app.wait(timeout=10)
            except Exception:
                app.kill()
        errhandle.close()          # releasing this is what makes the scratch removable


if __name__ == "__main__":
    sys.exit(main())
