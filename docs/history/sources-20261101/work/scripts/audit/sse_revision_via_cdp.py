#!/usr/bin/env python3
"""WUI-15 / WUI-14 · live revision push in a real browser: reconnect, refusal of a stale revision, and
whether a snapshot arriving under the user actually leaves the screen where they left it.

`.project-local/artifacts/wui-20261009/keyboard-focus-fresh.json` recorded why nothing like this existed:
`STALE_OR_MISSING_BINARY`, no release `app.exe` to drive, and an idle repository produces no second revision —
so the only way to observe a real projection update is to serve one. The stub below is a TEST INSTRUMENT, not
a product surface: nothing here is shipped, the snapshot bodies come from the real producer
(`snapshot_api.build_snapshot`, the same function the sidecar calls), and the whole thing listens on loopback.

Three claims, each falsifiable, and the run refuses to report a pass it did not observe:

  1. revision advance — the page must visibly change from marker A to marker B. If both markers are identical
     the instrument did nothing, so that is NOT_RUN rather than a pass (my own legibility sweep taught this:
     identical numbers across samples that must differ mean the probe never moved).
  2. a LOWER revision arriving after a higher one must not replace what is on screen (`api.ts:466-471`
     refuses it). The stub therefore sends rev 7, then rev 9, then a deliberately stale rev 8, and the page
     has to stay on rev 9.
  3. WUI-14's 不抢焦点/选中/阅读位置 in pixels — jsdom could only prove node survival, so here the rail's
     `scrollTop`, `window.scrollY`, a text selection and a caret in the search field are recorded BEFORE the
     update and compared AFTER it, in a Chromium that really lays out and really scrolls.

Exit: 0 SSE_REVISION_GATE_PASS, 1 SSE_REVISION_GATE_FAIL, 3 SSE_REVISION_GATE_NOT_RUN.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
import traceback
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "audit"))
import bundle_provenance  # noqa: E402  # the receipt has to name the bytes the browser loaded

GEOMETRY = ROOT / "scripts" / "audit" / "topbar_geometry_via_cdp.py"
OUT_DIR = ROOT / ".project-local" / "artifacts" / "wui-20261009"
PRODUCER = ROOT / "packages/client-neutral-core/scripts"

MARKER_REVISIONS = [7, 9, 8]   # 8 last: a stale frame must not win
PUSH_FIRST_DELAY_S = 0.0
# Revisions 2 and 3 are released by the page itself, through POST/GET /arm, once the "before" reading has
# been taken. A fixed clock cannot work: the browser finishes booting whenever it wants, and two runs proved
# both failure modes — pushing at 0/3/5s put rev 9 on screen before the instrument looked, while 0/1.5/3s put
# it there even earlier. The page is the only party that knows when it is ready.
ARM_DELAYS_S = [0.6, 1.8]
HEARTBEAT_EVERY = 0.2
STREAM_DEADLINE = 25.0
# The waits below are sized against a measured constraint, not a guess: the CDP client's websocket is created
# with `timeout=10` (topbar_geometry_via_cdp.py:337), and `evaluate` blocks in a plain socket recv until the
# response arrives — so the WHOLE in-page script must finish inside 10s or the launch dies with a bare
# TimeoutError, which is exactly what a 6s+4s budget did on the fourth run. Worst path here: 3 + 3 + 2.5 = 8s.
PAGE_WAIT_MS = 3000
STALE_BUDGET_MS = 2500


def load_geometry():
    spec = importlib.util.spec_from_file_location("geometry", GEOMETRY)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[attr-defined]
    return module


def snapshot_for(revision: int) -> dict:
    """A real producer payload, tagged with a revision and a unique visible timestamp."""
    sys.path.insert(0, str(PRODUCER))
    import snapshot_api
    # The token the assertion watches is the project's displayName, because that is rendered verbatim by
    # ProjectSummaryTable. A timestamp would not do: 来源新鲜度 prints it through fmtTimestamp, so the raw
    # ISO string never appears on screen and the probe would silently watch for something absent.
    payload = snapshot_api.build_snapshot(
        revision=revision,
        projects=[{"projectId": "work-lab", "displayName": f"rev{revision} WORK-LAB",
                   "agentPlatform": "codex", "workingAreas": ["apps/observer"]}],
        executions=[{"executionId": f"ex-{revision}", "state": "RUNNING",
                     "anchorProjectId": "work-lab", "sourceRef": f"git:rev{revision}"}],
        transport={"transportState": "LIVE", "freshnessState": "FRESH",
                   "eventsUrl": None, "eventStreamConnected": True},
        governance={"state": "CLEAN"},
        workspace={"plan": {}},
        generated_at="2026-10-10T00:00:00.000Z",
        source_watermark="2026-10-10T00:00:00.000Z",
    )
    return payload


class StubState:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.queue: list[dict] = []
        self.current: dict | None = None
        self.served_revisions: list[int] = []
        self.last_event_ids: list[str] = []

    def push(self, payload: dict) -> None:
        with self.lock:
            self.queue.append(payload)

    def arm(self) -> bool:
        """Release the scheduled revisions. One-shot: a second call does nothing, so a page that re-arms
        cannot make the stale frame arrive twice and be counted as a second refusal."""
        if getattr(self, "armed", False):
            return False
        self.armed = True
        def release() -> None:
            for delay, payload in self.arm_payloads:
                time.sleep(delay)
                self.push(payload)
        threading.Thread(target=release, daemon=True).start()
        return True

    def next_frame(self):
        with self.lock:
            if self.queue:
                self.current = self.queue.pop(0)
                self.served_revisions.append(self.current["revision"])
                return self.current
            return self.current


class QuietServer(ThreadingHTTPServer):
    """A browser abandons an open EventSource the moment the tab goes away, and the resulting
    ConnectionResetError is expected, not a finding. Printing its traceback hid the verdict line in noise."""
    def handle_error(self, request, client_address) -> None:  # noqa: N802 (socketserver API)
        exc = sys.exc_info()[1]
        if isinstance(exc, (ConnectionResetError, BrokenPipeError)):
            return
        super().handle_error(request, client_address)


def make_handler(state: StubState):
    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, *args) -> None:  # silence; the evidence is the JSON, not stderr
            pass

        def _cors(self) -> dict:
            return {"Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Headers": "Last-Event-ID, Cache-Control",
                    "Cache-Control": "no-cache"}

        def do_GET(self) -> None:  # noqa: N802 (http.server API)
            if self.path.startswith("/api/v1/snapshot"):
                body = json.dumps(state.current or state.next_frame() or {}).encode("utf-8")
                self.send_response(200, "OK")
                for k, v in self._cors().items():
                    self.send_header(k, v)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            if self.path.startswith("/api/v1/arm"):
                body = json.dumps({"armed": state.arm()}).encode("utf-8")
                self.send_response(200, "OK")
                for k, v in self._cors().items():
                    self.send_header(k, v)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            if self.path.startswith("/api/v1/events"):
                cursor = self.headers.get("Last-Event-ID")
                if cursor:
                    state.last_event_ids.append(cursor)
                self.send_response(200, "OK")
                for k, v in self._cors().items():
                    self.send_header(k, v)
                self.send_header("Content-Type", "text/event-stream")
                self.end_headers()
                deadline = time.time() + STREAM_DEADLINE
                sent_id = 0
                while time.time() < deadline:
                    payload = state.next_frame()
                    if payload is None:
                        break
                    sent_id += 1
                    frame = (f"id: {sent_id}\nevent: snapshot\ndata: {json.dumps(payload)}\n\n")
                    try:
                        self.wfile.write(frame.encode("utf-8"))
                        self.wfile.flush()
                    except (BrokenPipeError, ConnectionResetError):
                        return
                    time.sleep(HEARTBEAT_EVERY)
                return
            self.send_error(404, "stub serves /api/v1/snapshot and /api/v1/events only")

    return Handler


EXPRESSION = r"""(async () => {
  const CFG = %s;
  const sleep = (ms) => new Promise(r => setTimeout(r, ms));
  const box = document.querySelector('.nav') || document.querySelector('.sidebar');
  const out = {before: null, after: null, markerSeen: null, problems: [], timeline: []};
  const snapshot = () => ({
    railScrollTop: box ? Math.round(box.scrollTop) : null,
    railScrollable: box ? (box.scrollHeight > box.clientHeight) : false,
    windowScrollY: Math.round(window.scrollY),
    selectionAttached: (() => {
      const s = document.getSelection();
      return !!(s && s.rangeCount && s.anchorNode && document.contains(s.anchorNode));
    })(),
    activeTag: document.activeElement ? document.activeElement.tagName : null,
    revisionText: (document.body.innerText.match(/rev\d+/g) || []).join(','),
  });
  if (!box) { out.problems.push('no rail element to scroll'); return JSON.stringify(out); }

  const shown = (n) => (document.body.innerText.match(/rev\d+/g) || []).includes('rev' + n);
  const waitFor = async (n, budgetMs) => {
    const stop = Date.now() + budgetMs;
    while (Date.now() < stop) { if (shown(n)) return true; await sleep(200); }
    return false;
  };

  // Phase 1: the page must actually be showing the FIRST revision before anything is measured. A stream
  // that pushes rev7/9/8 back-to-back is finished before React subscribes, and the first run of this
  // instrument proved it: markerSeen came back [false, true, false] because rev 7 had already been replaced.
  const sawFirst = await waitFor(CFG.revisions[0], CFG.waitMs);
  out.timeline.push(['first revision visible', sawFirst]);

  // Drive the page into a state a reader could plausibly be in: rail scrolled, a sentence selected, and the
  // search box holding a caret.
  box.scrollTop = Math.min(240, Math.max(0, box.scrollHeight - box.clientHeight));
  window.scrollTo(0, 40);
  await sleep(120);
  const heading = document.querySelector('#content h1, #content h2, #content h3, #content p');
  const sel = document.getSelection();
  if (heading && sel) { sel.removeAllRanges(); const r = document.createRange();
                        r.selectNodeContents(heading); sel.addRange(r); }
  const search = document.querySelector('.search input, input[role="searchbox"], input[type="search"]');
  if (search) { search.focus(); }
  await sleep(200);
  out.before = snapshot();
  out.before.searchValue = search ? search.value : null;

  // Phase 2: arm the stub, THEN wait. The order is the whole point — the page decides when the next
  // revision is released, so the "before" reading is guaranteed to be of the earlier one.
  await fetch(CFG.armUrl).then((r) => r.json()).catch(() => null);
  const sawSecond = await waitFor(CFG.revisions[1], CFG.waitMs);
  out.timeline.push(['second revision visible', sawSecond]);
  await sleep(CFG.staleBudgetMs);
  out.after = snapshot();
  out.markerSeen = CFG.revisions.map(shown);
  out.staleVisible = shown(CFG.revisions[2]);
  return JSON.stringify(out);
})()"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=str(ROOT))
    ap.add_argument("--json-out", default=None)
    ap.add_argument("--revisions", default=None,
                    help="override the revision schedule for a falsification run. `--revisions 7,9,10` makes "
                         "the trailing frame HIGHER than the one on screen, which must turn the gate red: a "
                         "check that cannot report a wrong answer is not measuring anything.")
    args = ap.parse_args()
    global MARKER_REVISIONS
    if args.revisions:
        MARKER_REVISIONS = [int(token) for token in args.revisions.split(",") if token.strip()]

    root = Path(args.root).resolve()
    dist = root / "apps/observer/frontend/dist/index.html"
    if not dist.is_file():
        print(f"SSE_REVISION_GATE_NOT_RUN DIST_ABSENT {dist}")
        return 3
    geometry = load_geometry()
    browser = geometry.find_browser()
    if not browser:
        print("SSE_REVISION_GATE_NOT_RUN BROWSER_NOT_FOUND set WL_CHROME to a Chrome/Edge binary")
        return 3
    u19 = geometry.load_u19()

    state = StubState()
    port = u19.pick_free_port()
    server = QuietServer(("127.0.0.1", port), make_handler(state))
    threading.Thread(target=server.serve_forever, daemon=True).start()

    # Paced on purpose. The first run pushed all three frames at t=0 and the browser only ever saw the last
    # one, which made the "advance" claim unfalsifiable; each revision now arrives while the page is live.
    state.push(snapshot_for(MARKER_REVISIONS[0]))
    state.arm_payloads = [(delay, snapshot_for(revision))
                          for delay, revision in zip(ARM_DELAYS_S, MARKER_REVISIONS[1:])]

    cfg = {"revisions": MARKER_REVISIONS, "waitMs": PAGE_WAIT_MS,
           "staleBudgetMs": STALE_BUDGET_MS, "armUrl": f"http://127.0.0.1:{port}/api/v1/arm"}
    expr = EXPRESSION % (json.dumps(cfg),)
    path = f"/index.html?view=overview&mode=UNKNOWN&theme=dark&api=http://127.0.0.1:{port}"

    report = {"instrument": "sse_revision_via_cdp", "stubPort": port,
              "revisionsPushed": MARKER_REVISIONS, "armDelaysS": ARM_DELAYS_S, "cfg": cfg,
              "staleFrameExpectedRefused": True}
    failures: list[str] = []
    try:
        measured = geometry.serve_and_eval(root, path, "1280,820", expr, browser, u19, None)
    except Exception:  # noqa: BLE001 — a launch that dies is reported, never defaulted to a pass
        # The frame is printed because "TimeoutError" alone cannot be triaged: whether the websocket connect,
        # the /json/list probe or the page evaluation timed out decides what to fix.
        traceback.print_exc()
        print("SSE_REVISION_GATE_NOT_RUN LAUNCH_FAILED see the traceback above")
        return 3
    finally:
        server.shutdown()

    report["measured"] = measured
    before, after = measured.get("before") or {}, measured.get("after") or {}
    served = state.served_revisions
    report["servedRevisions"] = served
    report["reconnectLastEventIds"] = state.last_event_ids

    if not before or not after:
        failures.append("the page produced no before/after snapshot — nothing was measured")
    if measured.get("problems"):
        failures.extend(measured["problems"])
    seen = measured.get("markerSeen") or []
    report["timeline"] = measured.get("timeline")
    timeline = {str(row[0]): row[1] for row in (measured.get("timeline") or [])}
    # The advance is stated in the only form that survives being superseded: what was on screen BEFORE the
    # update and what is on screen AFTER. Re-testing "is rev 7 still visible" at the end was this
    # instrument's first mistake — by then rev 9 has legitimately replaced it, and a check that convicts a
    # correct product is a broken check, not a bug report.
    if not timeline.get("first revision visible"):
        failures.append("rev 7 was never observed before the update, so nothing was shown to advance")
    if not timeline.get("second revision visible"):
        failures.append("rev 9 never reached the screen — the SSE/poll path did not deliver an update")
    if before.get("revisionText") != "rev7":
        failures.append(f"the pre-update screen read {before.get('revisionText')!r}, expected 'rev7'")
    if after.get("revisionText") != "rev9":
        failures.append(f"the post-update screen read {after.get('revisionText')!r}, expected 'rev9'")
    stale = MARKER_REVISIONS[2]
    newest = MARKER_REVISIONS[1]
    if stale not in served:
        failures.append(f"the trailing rev {stale} frame was never served, so the ordering rule was not "
                        "exercised — an untested branch is not evidence")
    if measured.get("staleVisible"):
        # Correct in both directions: in the shipped schedule rev 8 < rev 9, so seeing it means a stale
        # projection replaced newer facts; in `--revisions 7,9,10` rev 10 > rev 9, so seeing it means the
        # screen never settled on the revision this instrument claims to have measured.
        failures.append(f"the screen shows rev {stale} after the update instead of staying on rev {newest}"
                        " — api.ts:466-471 (reject a lower revision) or the settle assumption did not hold")
    if before.get("railScrollTop") != after.get("railScrollTop"):
        failures.append(f"rail scrollTop moved {before.get('railScrollTop')} -> {after.get('railScrollTop')}")
    if before.get("windowScrollY") != after.get("windowScrollY"):
        failures.append(f"window scrollY moved {before.get('windowScrollY')} -> {after.get('windowScrollY')}")
    if before.get("selectionAttached") and not after.get("selectionAttached"):
        failures.append("the text selection was dropped by the update")
    if before.get("activeTag") == "INPUT" and after.get("activeTag") != "INPUT":
        failures.append(f"focus left the search field ({before.get('activeTag')} -> {after.get('activeTag')})")
    if before.get("railScrollTop", 0) == 0:
        failures.append("the rail did not actually scroll, so scrollTop survival proves nothing — "
                        "a control that cannot fail guards nothing")
    if not before.get("railScrollable"):
        failures.append("the rail was not scrollable at this viewport, so the reading-position claim is empty")

    report["failures"] = failures
    report["servedBundle"] = bundle_provenance.describe(ROOT)
    report["verdictToken"] = "SSE_REVISION_GATE_PASS" if not failures else "SSE_REVISION_GATE_FAIL"
    out_path = Path(args.json_out) if args.json_out else OUT_DIR / "sse-revision.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"revisionsServed={served} markerSeen={seen} reconnectCursor={state.last_event_ids}")
    print(f"before={json.dumps(before, ensure_ascii=False)}")
    print(f"after ={json.dumps(after, ensure_ascii=False)}")
    for failure in failures:
        print(f"FAIL {failure}")
    print(f"JSON_OUT {out_path}")
    print(report["verdictToken"])
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
