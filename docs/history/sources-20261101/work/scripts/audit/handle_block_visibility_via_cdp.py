"""Attribute the artifact-handle block's first-visible latency into three page-measured segments.

Closes the metric blueprint's "should" gap (`.project-local/artifacts/standalone-run-20261019/metric.json`,
gap 5) and, in doing so, retracts what this instrument used to report.

**Why the old number was not a latency.** The previous version polled the DOM every 20 ms from the moment
its own page expression started running, and that expression was evaluated by the shared browser bootstrap
`topbar_geometry_via_cdp.serve_and_eval` — which launches Chrome with the URL **on the command line** (so
navigation starts there), then sleeps 2.0 s for the CDP endpoint and 1.0 s after `Page.enable`. Measured on
five fresh loads of the same bundle: `rowsMs` median 3,225 ms, worst 3,239 ms, spread 14 ms, `rowsMs` equal
to `capacityMs` on every single load, and `domContentLoadedMs` ~140 ms in the same samples. Equal
first-two-marks means the poll loop broke on its FIRST iteration: the instrument's earliest possible look
was ~3.2 s after navigation, so it reported when it itself woke up, never when the block appeared. A
14 ms spread is the shape of a `sleep()`, not of a page.

**What this version does instead.** A recorder is installed with `Page.addScriptToEvaluateOnNewDocument`
BEFORE navigating, and it stamps every boundary with the page's own monotonic clock (`performance.now()`,
milliseconds since navigationStart):

* A 快照解析 — navigationStart until the snapshot body finishes parsing. Sub-divided into boot-to-request,
  server+transfer from Resource Timing, and the JSON parse measured around `Response.prototype.json`.
* B React 提交 — that parse finishing until `[data-testid="evidence-handles-rows"]` holds its first child,
  caught by a MutationObserver, so it cannot be inflated by a late read-back.
* C 到首可见 — rows in the DOM until the rows element intersects the viewport, judged from the ELEMENT'S
  OWN rect (an ancestor's intersection is not the rows being on screen), plus the cost of the scroll that
  puts it there when it starts below the fold.

The instrument also refuses to answer: if the recorder did not install, or a segment is missing or negative,
that is `HANDLE_LATENCY_NOT_MEASURABLE`, not a small number.

Known limits, stated rather than hidden: `responseStart` is 0 for this backend's responses (no
`content-length`), so "server time alone" is unmeasurable and only request-issued→response-end is reported;
and a headless tab delivers IntersectionObserver entries late, so "visible" is decided from geometry, not
from when the observer happened to fire.

Exit: 0 HANDLE_LATENCY_PASS, 1 HANDLE_LATENCY_FAIL, 3 HANDLE_LATENCY_NOT_RUN / NOT_MEASURABLE.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import statistics
import subprocess
import sys
import time
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GEOMETRY = ROOT / "scripts" / "audit" / "topbar_geometry_via_cdp.py"
OUT_DIR = ROOT / ".project-local" / "runs" / "handle-latency-attribution"

# The three boundaries the acceptance asks for, in the order a reader reasons about them.
SEGMENTS = ("A_snapshotParseMs", "B_reactCommitMs", "C_rowsToVisibleMs", "totalNavToVisibleMs")

RECORDER = r"""(() => {
  const rec = {parseEvents: [], problems: [], instrumented: false};
  window.__WL_ATTR = rec;
  const now = () => performance.now();
  const note = (event) => { rec.parseEvents.push(event); return event; };
  const looksLikeSnapshot = (value) => !!value && typeof value === 'object'
      && (Array.isArray(value.artifactHandles) || value.schema_version === 'workflow/snapshot/v3');

  // Two transports deliver the v3 snapshot to this lane: the authoritative `?api=` fetch, and the SSE
  // `snapshot` frame that api.ts applies straight away. Wrapping only Response.prototype.json observed the
  // first, so a load whose rows came over SSE had NO parse before rowsAt and the causal pairing produced a
  // negative commit segment. Both are stamped now, and the receipt says which one fed the render.
  const origJson = Response.prototype.json;
  Response.prototype.json = function () {
    const url = String(this.url || '');
    if (!url.includes('/api/v1/snapshot')) { return origJson.call(this); }
    const event = note({seq: rec.parseEvents.length, transport: 'response.json', start: now(), end: null});
    const p = origJson.call(this);
    return p.then((value) => {
      event.end = now();
      if (looksLikeSnapshot(value)) {
        rec.snapshotRevision = value.revision === undefined ? null : value.revision;
        const h = value.artifactHandles;
        rec.snapshotHandleRows = Array.isArray(h) ? h.length : null;
      }
      return value;
    }, (error) => { event.error = String((error && error.message) || error); throw error; });
  };

  const origParse = JSON.parse;
  JSON.parse = function (text, reviver) {
    const start = now();
    const value = origParse.call(this, text, reviver);
    if (looksLikeSnapshot(value)) {
      note({seq: rec.parseEvents.length, transport: 'sse-or-json.parse',
            start: start, end: now(), chars: String(text).length});
      rec.snapshotRevision = value.revision === undefined ? null : value.revision;
      const h = value.artifactHandles;
      rec.snapshotHandleRows = Array.isArray(h) ? h.length : null;
    }
    return value;
  };

  const rows = () => document.querySelector('[data-testid="evidence-handles-rows"]');
  const mo = new MutationObserver(() => {
    const el = rows();
    if (!el || !el.children.length || rec.rowsAt !== undefined) { return; }
    rec.rowsAt = now();
    rec.rowCount = el.children.length;
    const rect = el.getBoundingClientRect();
    rec.rowsRect = {top: Math.round(rect.top), bottom: Math.round(rect.bottom),
                    height: Math.round(rect.height)};
    rec.viewport = {width: window.innerWidth, height: window.innerHeight};
    rec.belowFoldAtCommit = rect.top >= window.innerHeight || rect.bottom <= 0;
    requestAnimationFrame(() => requestAnimationFrame(() => { rec.paintChanceAt = now(); }));
    window.__WL_ATTR_SCROLL = () => {
      rec.scrollStart = now();
      el.scrollIntoView({block: 'start'});
      const after = el.getBoundingClientRect();
      rec.rectAfterScroll = {top: Math.round(after.top), bottom: Math.round(after.bottom)};
      rec.visibleAfterScroll = after.top < window.innerHeight && after.bottom > 0;
      // Segment C is the wait a reader actually experiences: scroll asked for, then the frame that paints
      // the rows. Reading the rect back synchronously would cost ~0 ms and say nothing about paint.
      requestAnimationFrame(() => requestAnimationFrame(() => { rec.scrollPaintAt = now(); }));
      return rec.visibleAfterScroll ? 'NOW_VISIBLE' : 'STILL_NOT_VISIBLE';
    };
  });
  try {
    // Observe the Document node: documentElement does not exist yet at document-start, and observing null
    // throws — leaving the recorder installed but blind, which reads exactly like a block that never
    // rendered.
    mo.observe(document, {childList: true, subtree: true});
    rec.instrumented = true;
  } catch (error) {
    rec.instrumentError = String((error && error.message) || error);
  }
})();"""

READBACK = r"""(async () => {
  const rec = window.__WL_ATTR || {};
  const readbackAt = performance.now();
  const nav = performance.getEntriesByType('navigation')[0];
  const resources = performance.getEntriesByType('resource')
      .filter((e) => String(e.name).includes('/api/v1/snapshot'))
      .map((e) => ({fetchStart: Math.round(e.fetchStart), responseEnd: Math.round(e.responseEnd),
                    responseStart: Math.round(e.responseStart), duration: Math.round(e.duration)}));
  const paint = performance.getEntriesByType('paint')
      .map((e) => ({name: e.name, at: Math.round(e.startTime)}));
  const fcp = (paint.find((p) => p.name === 'first-contentful-paint') || {}).at ?? null;
  const scroll = (window.__WL_ATTR_SCROLL ? window.__WL_ATTR_SCROLL() : 'NO_SCROLL_HOOK');
  await new Promise((r) => setTimeout(r, 120));
  const r2 = window.__WL_ATTR || {};
  const events = (r2.parseEvents || []).filter((e) => e.end !== null && e.end !== undefined);
  const rowsAt = (r2.rowsAt === undefined) ? null : r2.rowsAt;
  // Which parse FED this render? The app reads the snapshot more than once before the rows land, so
  // "whichever parse started first" is not "whichever parse the rows came from" -- pairing the wrong one
  // produced a NEGATIVE commit segment. The feeding parse is the last one that finished before the rows
  // appeared; if none did, segment B is unmeasurable and says so rather than reporting a negative number.
  let feeding = null;
  if (rowsAt !== null) { for (const e of events) { if (e.end <= rowsAt) feeding = e; } }
  const feedStart = feeding ? feeding.start : null;
  // A request-timed subdivision only exists for the fetch transport; an SSE-delivered parse has no
  // fetchStart/responseEnd pair, so A2 stays unmeasurable there instead of borrowing another request's.
  const requests = (feeding && feeding.transport === 'response.json')
      ? resources.filter((x) => x.responseEnd !== null && feedStart !== null && x.responseEnd <= feedStart)
      : [];
  const snap = requests.length ? requests[requests.length - 1] : {};
  const round = (v) => (v === null || v === undefined ? null : Math.round(v));
  const between = (a, b) => (a === null || b === null || a === undefined || b === undefined)
      ? null : Math.round(b - a);
  return JSON.stringify({
    readbackAtMs: round(readbackAt),
    navStartToDclMs: nav ? Math.round(nav.domContentLoadedEventEnd) : null,
    firstContentfulPaintMs: fcp,
    snapshotResourceMs: {fetchStart: snap.fetchStart ?? null, responseEnd: snap.responseEnd ?? null,
                         responseStart: snap.responseStart ?? null},
    parseEvents: (r2.parseEvents || []).map((e) => ({seq: e.seq, transport: e.transport,
                                                     start: round(e.start), end: round(e.end),
                                                     chars: e.chars === undefined ? null : e.chars,
                                                     error: e.error || null})),
    feedingParseSeq: feeding ? feeding.seq : null,
    feedingTransport: feeding ? feeding.transport : null,
    feedingParseEndMs: feeding ? round(feeding.end) : null,
    snapshotRevisions: r2.snapshotRevision === undefined ? null : r2.snapshotRevision,
    snapshotHandleRows: r2.snapshotHandleRows === undefined ? null : r2.snapshotHandleRows,
    rowsAtMs: round(r2.rowsAt), rowCount: r2.rowCount || 0,
    rowsRect: r2.rowsRect || null, viewport: r2.viewport || null,
    belowFoldAtCommit: r2.belowFoldAtCommit === undefined ? null : r2.belowFoldAtCommit,
    paintChanceAtMs: round(r2.paintChanceAt),
    instrumented: r2.instrumented === true, instrumentError: r2.instrumentError || null,
    scrollOutcome: scroll, scrollStartMs: round(r2.scrollStart), scrollPaintMs: round(r2.scrollPaintAt),
    rectAfterScroll: r2.rectAfterScroll || null,
    visibleAfterScroll: r2.visibleAfterScroll === undefined ? null : r2.visibleAfterScroll,
    segments: {
      A1_bootToRequestMs: between(0, feedStart),
      A2_serverAndTransferMs: between(snap.fetchStart ?? null, snap.responseEnd ?? null),
      A3_jsonParseMs: between(feedStart, feeding ? feeding.end : null),
      A_snapshotParseMs: between(0, feeding ? feeding.end : null),
      B_reactCommitMs: between(feeding ? feeding.end : null, rowsAt),
      C_rowsToVisibleMs: between(r2.scrollStart, r2.scrollPaintAt),
      totalNavToVisibleMs: between(0, rowsAt),
    },
  });
})()"""


def handle_geometry(sample: dict) -> dict:
    """The list's own shape, computed from the rect the page reported.

    A prose claim of "23,056px of un-windowed rows" is worth nothing unless the receipt that made it says
    so in numbers, and unless the number is tied to the row count the snapshot actually served.
    """
    rect = sample.get("rowsRect") or {}
    view = sample.get("viewport") or {}
    rows = sample.get("rowCount") or 0
    served = sample.get("snapshotHandleRows")
    height, viewport_height = rect.get("height"), view.get("height")
    return {"rowsInDom": rows,
            "rowsServedBySnapshot": served,
            "listHeightPx": height,
            "viewportHeightPx": viewport_height,
            "pxPerRow": round(height / rows, 1) if height and rows else None,
            "viewportsOfScrolling": round(height / viewport_height, 1) if height and viewport_height else None}


def problems(sample: dict, fail_over_ms: int | None) -> list[str]:
    """Every assertion the instrument makes about ITS OWN measurement, as a pure function.

    Kept pure so `tests/ci/test_handle_latency_attribution.py` can feed it planted shapes instead of
    trusting a green run on a page that happened to be fast.
    """
    found: list[str] = []
    if not sample.get("instrumented"):
        return [f"the page-side recorder never installed ({sample.get('instrumentError') or 'no reason'}), "
                "so no boundary below was observed -- this is a missing measurement, not a fast one"]

    segments = sample.get("segments") or {}
    rows_at = sample.get("rowsAtMs")
    if rows_at is None:
        found.append("the handle rows never entered the DOM, so A/B/C are absent, not zero")
    if sample.get("readbackAtMs") is not None and rows_at is not None:
        # The guard the old version lacked: a timestamp recorded by the page must PREDATE the read-back by
        # more than the settle window can explain, or we are again reporting when we looked.
        margin = sample["readbackAtMs"] - rows_at
        if margin <= 0:
            found.append(f"rowsAt {rows_at} ms is not earlier than the read-back "
                         f"{sample['readbackAtMs']} ms -- the event was recorded at read time")
        sample["_lookaheadMarginMs"] = margin

    for name in SEGMENTS:
        value = segments.get(name)
        if value is None:
            found.append(f"segment {name} is unmeasurable (a boundary the page did not record)")
        elif value < 0:
            found.append(f"segment {name} = {value} ms is negative -- the boundaries are wired in the "
                         "wrong order, so this instrument, not the page, is what is broken")

    below = sample.get("belowFoldAtCommit")
    after = sample.get("visibleAfterScroll")
    if below is None:
        found.append("the rows' own rect was never read, so 'visible' has no basis here")
    if below is True and after is False:
        found.append(f"scrolling to a committed rect of {sample.get('rowsRect')} with viewport "
                     f"{sample.get('viewport')} did not bring the rows on screen")
    if below is True and segments.get("C_rowsToVisibleMs") == 0:
        found.append("the block starts below the fold but segment C reports 0 ms -- nobody scrolled")

    shape = handle_geometry(sample)
    rows, served = shape["rowsInDom"], shape["rowsServedBySnapshot"]
    if served is None and rows:
        found.append(f"the block mounted {rows} rows but the snapshot's own row count was never observed, "
                     "so those rows have no denominator and 'every served handle is shown' is unsupported")
    if served is not None and rows > served:
        found.append(f"the block mounted {rows} rows while the snapshot served {served} -- the extra rows "
                     "were not read from the projection, they were invented")
    height, viewport_height = shape["listHeightPx"], shape["viewportHeightPx"]
    if height and viewport_height and height > viewport_height and sample.get("scrollOutcome") == "NO_SCROLL_HOOK":
        found.append(f"the list is {height}px inside a {viewport_height}px viewport "
                     f"({shape['viewportsOfScrolling']} screens of un-windowed rows) and no scroll was "
                     "attempted, so the tail of the list was never on screen and never measured")

    bundle = sample.get("servedBundle") or {}
    if not bundle.get("files"):
        found.append("the receipt names no bundle bytes, so this verdict cannot be tied to a build")

    if fail_over_ms is not None and segments.get("totalNavToVisibleMs") is not None:
        if segments["totalNavToVisibleMs"] > fail_over_ms:
            found.append(f"navStart-to-rows {segments['totalNavToVisibleMs']} ms exceeds the stated "
                         f"budget {fail_over_ms} ms")
    return found


def aggregate(samples: list[dict], key: str) -> dict[str, float | None]:
    values = [s["segments"][key] for s in samples
              if s.get("segments", {}).get(key) is not None]
    return {"n": len(values),
            "median": statistics.median(values) if values else None,
            "worst": max(values) if values else None}


def run_once(geometry, u19, browser: str, api_port: int, settle_ms: int, index: int) -> dict:
    """Launch Chrome blank, install the recorder, navigate, and read the page's own timestamps back."""
    page_port = u19.pick_free_port()
    cdp_requested = u19.pick_free_port()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    udf = OUT_DIR / f"udf-{int(time.time())}-{os.getpid()}-{index}"
    log_path = OUT_DIR / f"chrome-{int(time.time())}-{os.getpid()}-{index}.log"
    dist = ROOT / "apps" / "observer" / "frontend" / "dist"
    srv = subprocess.Popen([sys.executable, "-m", "http.server", str(page_port), "--bind", "127.0.0.1"],
                           cwd=str(dist), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    url = (f"http://127.0.0.1:{page_port}/index.html?view=evidence&theme=dark"
           f"&api=http://127.0.0.1:{api_port}")
    proc = None
    try:
        with log_path.open("wb") as log:
            proc = subprocess.Popen(
                [browser, "--headless=new", "--disable-gpu", "--no-sandbox", "--no-first-run",
                 "--no-default-browser-check", "--disable-extensions", f"--user-data-dir={udf}",
                 "--window-size=1280,820", f"--remote-debugging-port={cdp_requested}",
                 "--remote-allow-origins=*", "about:blank"],
                stdout=log, stderr=subprocess.STDOUT)
            cdp_port = None
            deadline = time.time() + 90
            while time.time() < deadline and cdp_port is None:
                time.sleep(0.5)
                match = geometry.LISTEN_RE.search(log_path.read_text(encoding="utf-8", errors="replace"))
                if match:
                    cdp_port = int(match.group(1))
                if proc.poll() is not None:
                    raise RuntimeError(f"chrome exited rc={proc.returncode}")
            if cdp_port is None:
                raise RuntimeError("chrome announced no CDP port within 90s")
        cdp, _ws = geometry.connect_with_retry(cdp_port)
        try:
            cdp.send("Page.enable")
            cdp.send("Runtime.enable")
            cdp.send("Page.addScriptToEvaluateOnNewDocument", {"source": RECORDER})
            cdp.send("Page.navigate", {"url": url})
            time.sleep(settle_ms / 1000.0)
            body = json.loads(cdp.evaluate(READBACK))
        finally:
            cdp.close()
    finally:
        if proc is not None:
            proc.kill()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                pass
        srv.kill()
        try:
            srv.wait(timeout=10)
        except subprocess.TimeoutExpired:
            pass
        geometry._release_profile(udf)
    body["index"] = index
    body["url"] = url
    return body


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--samples", type=int, default=3)
    ap.add_argument("--settle-ms", type=int, default=3500,
                    help="how long the page runs before its own timestamps are read back")
    ap.add_argument("--fail-over-ms", type=int, default=None,
                    help="median budget for navStart-to-rows; the gate fails above it. "
                         "Unset means report-only and says so.")
    ap.add_argument("--json-out", default=None)
    args = ap.parse_args()

    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    spec = importlib.util.spec_from_file_location("geometry", GEOMETRY)
    geometry = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(geometry)  # type: ignore[attr-defined]
    if not (ROOT / "apps/observer/frontend/dist/index.html").is_file():
        print("HANDLE_LATENCY_NOT_RUN DIST_ABSENT (run npm run build in apps/observer/frontend)")
        return 3
    browser = geometry.find_browser()
    if not browser:
        print("HANDLE_LATENCY_NOT_RUN BROWSER_NOT_FOUND")
        return 3
    u19 = geometry.load_u19()
    bundle = geometry.bundle_provenance.describe(ROOT)

    _sidecar, api_port, _thread, server = u19.start_sidecar()
    samples: list[dict] = []
    try:
        for index in range(max(1, args.samples)):
            try:
                sample = run_once(geometry, u19, browser, api_port, args.settle_ms, index)
            except Exception:  # noqa: BLE001 -- a failed launch is reported, never averaged into a number
                traceback.print_exc()
                print("HANDLE_LATENCY_NOT_RUN LAUNCH_FAILED")
                return 3
            sample["servedBundle"] = bundle
            samples.append(sample)
    finally:
        server.shutdown()

    report = {
        "instrument": "handle_block_visibility_via_cdp",
        "measurement": "page-side performance.now() boundaries recorded before navigation",
        "backend": f"live sidecar on loopback port {api_port}",
        "browser": browser,
        "settleMs": args.settle_ms,
        "servedBundle": bundle,
        "samples": samples,
        "segments": {name: aggregate(samples, name) for name in SEGMENTS},
        "rowCountObserved": [s.get("rowCount") for s in samples],
        "belowFoldAtCommit": [s.get("belowFoldAtCommit") for s in samples],
        "handleGeometry": [handle_geometry(s) for s in samples],
        "failOverMs": args.fail_over_ms,
    }
    per_sample = [problems(s, args.fail_over_ms) for s in samples]
    report["problemsPerSample"] = per_sample
    flat = sorted({p for one in per_sample for p in one})
    report["problems"] = flat
    unmeasurable = any(not s.get("instrumented") or s["segments"].get("totalNavToVisibleMs") is None
                       for s in samples)

    if args.json_out:
        out = Path(args.json_out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                       encoding="utf-8", newline="\n")

    line = " ".join(f"{name}={report['segments'][name]['median']}/{report['segments'][name]['worst']}"
                    for name in SEGMENTS)
    shapes = [g for g in report["handleGeometry"] if g["listHeightPx"]]
    widest = max(shapes, key=lambda g: g["listHeightPx"]) if shapes else None
    geometry_note = ("" if widest is None else
                     f" listPx={widest['listHeightPx']} viewportPx={widest['viewportHeightPx']}"
                     f" pxPerRow={widest['pxPerRow']} screens={widest['viewportsOfScrolling']}"
                     f" servedRows={widest['rowsServedBySnapshot']} domRows={widest['rowsInDom']}")
    print(f"HANDLE_LATENCY n={len(samples)} {line} rows={report['rowCountObserved']} "
          f"belowFold={report['belowFoldAtCommit']}{geometry_note}")
    for problem in flat:
        print("  PROBLEM", problem)
    if args.fail_over_ms is None:
        print("HANDLE_LATENCY_BUDGET_NOT_SET reporting only; pass --fail-over-ms to make this a gate")
    if unmeasurable:
        print(f"HANDLE_LATENCY_NOT_MEASURABLE -> {args.json_out or 'stdout only'}")
        return 3
    if flat:
        print("HANDLE_LATENCY_FAIL")
        return 1
    print(f"HANDLE_LATENCY_PASS -> {args.json_out or 'stdout only'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
