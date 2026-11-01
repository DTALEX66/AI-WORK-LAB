#!/usr/bin/env python
"""One desktop launch, every remaining U19/P0-C/ERR-103 question answered.

Silent work is already done (content-keyed freshness gate, ACL contract test,
both rebuild chains). What cannot be proven without the real binary running:

  1. Does the release surface actually render?     CDP DOM + Page.captureScreenshot
  2. Was ERR-102's black screen only the GDI instrument?  same launch, GDI cross-check
  3. Do the caption controls really work now?      dispatch real mouse events and
                                                   read the resulting window state

Clicks are dispatched through CDP at the coordinates the page itself reports,
after confirming with elementFromPoint that the intended button is what sits
there. Close runs last, because it ends the app.
"""
from __future__ import annotations

import base64
import ctypes
import ctypes.wintypes as wt
import hashlib
import importlib.util
import json
import os
import re
import socket
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(r"D:\All projects\WORK-LAB")
OBS = ROOT / "apps" / "observer"
HERE = ROOT / ".project-local" / "runs" / "p0c-final-20261006"
HERE.mkdir(parents=True, exist_ok=True)
os.environ["CARGO_TARGET_DIR"] = str(
    ROOT / ".project-local" / "runs" / "u19-msvc-20261006" / "target")

spec = importlib.util.spec_from_file_location(
    "u19", OBS / "scripts" / "u19_webview_e2e.py")
u19 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(u19)  # type: ignore[attr-defined]

user32 = ctypes.windll.user32
report: dict = {"startedAt": time.strftime("%Y-%m-%dT%H:%M:%S")}
COLUMNS: dict = {}


def dump() -> None:
    (HERE / "final.json").write_text(json.dumps(report, indent=2, default=str),
                                     encoding="utf-8")


def ps(script: str) -> str:
    return (subprocess.run(["powershell", "-NoProfile", "-Command", script],
                           capture_output=True, encoding="utf-8",
                           errors="replace", check=False).stdout or "").strip()


def cdp_get(port: int, path: str, wait: float = 6.0) -> str:
    try:
        s = socket.create_connection(("127.0.0.1", port), timeout=wait)
    except Exception as exc:  # noqa: BLE001
        return f"ERR connect {exc!r}"[:160]
    try:
        s.sendall((f"GET {path} HTTP/1.1\r\nHost: localhost:{port}\r\n"
                   "Connection: close\r\n\r\n").encode("latin-1"))
        s.settimeout(wait)
        chunks = []
        while True:
            c = s.recv(65536)
            if not c:
                break
            chunks.append(c)
    except Exception as exc:  # noqa: BLE001
        return f"ERR recv {exc!r}"[:160]
    finally:
        s.close()
    _head, _, body = b"".join(chunks).partition(b"\r\n\r\n")
    return body.decode("utf-8", "replace")


def our_webview_rows(app_pid: int, udf: Path) -> list[dict]:
    out = ps("Get-CimInstance Win32_Process -Filter \"Name='msedgewebview2.exe'\" "
             "| ForEach-Object { \"$($_.ProcessId)|$($_.ParentProcessId)|$($_.CommandLine)\" }")
    marker = udf.name.lower()
    rows = []
    for line in out.splitlines():
        parts = line.split("|", 2)
        if len(parts) < 3:
            continue
        pid, ppid, cmd = parts
        low = cmd.lower()
        # Our own environment: this run's private user-data folder, or a process
        # this launch parented, or the profile folder of the shipped identifier.
        if not (marker in low or ppid == str(app_pid)
                or "com.dtalex.worklab.observer" in low):
            continue
        rows.append({"pid": pid, "ppid": ppid,
                     "type": (re.search(r"--type=([\w-]+)", cmd) or [None, "browser"])[1],
                     "port": (re.search(r"--remote-debugging-port=(\d+)", cmd) or [None, None])[1],
                     "udf": (re.search(r'--user-data-dir="([^"]+)"', cmd) or [None, None])[1]})
    return rows


def wait_for_cdp_port(cdp_port: int, udf: Path, app_pid: int,
                      seconds: float = 120) -> tuple[int, list[dict]]:
    """Poll until the debug port answers. WebView2 opens it lazily, and the port
    in the command line is only a request, so re-enumerate every round."""
    deadline = time.time() + seconds
    rows: list[dict] = []
    attempts: list[str] = []
    round_no = 0
    while time.time() < deadline:
        round_no += 1
        rows = our_webview_rows(app_pid, udf)
        cands = sorted({cdp_port} | {int(r["port"]) for r in rows if r["port"]})
        for cand in cands:
            body = cdp_get(cand, "/json/version", wait=12.0)
            if '"Browser"' in body:
                report["cdpFirstResponse"] = body[:400]
                return cand, rows
            attempts.append(f"round {round_no} :{cand} -> {body[:110]}")
        time.sleep(1.5)
    report["cdpAttempts"] = attempts[-8:]
    return 0, rows


# ---------------------------------------------------------------------------
# Window state, read from Win32 rather than from pixels
# ---------------------------------------------------------------------------
def all_windows(app_pid: int) -> list[dict]:
    found: list[dict] = []
    cb = ctypes.WINFUNCTYPE(ctypes.c_bool, wt.HWND, wt.LPARAM)

    def each(hwnd, _l):
        pid = wt.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if pid.value != app_pid:
            return True
        cls = ctypes.create_unicode_buffer(256)
        user32.GetClassNameW(hwnd, cls, 256)
        if cls.value != "Tauri Window":
            return True
        cr = wt.RECT()
        user32.GetClientRect(hwnd, ctypes.byref(cr))
        title = ctypes.create_unicode_buffer(256)
        user32.GetWindowTextW(hwnd, title, 256)
        outer = wt.RECT()
        user32.GetWindowRect(hwnd, ctypes.byref(outer))
        found.append({
            "hwnd": hwnd, "class": cls.value, "title": title.value,
            "visible": bool(user32.IsWindowVisible(hwnd)),
            "minimized": bool(user32.IsIconic(hwnd)),
            "maximized": bool(user32.IsZoomed(hwnd)),
            "client": f"{cr.right - cr.left}x{cr.bottom - cr.top}",
            "clientArea": (cr.right - cr.left) * (cr.bottom - cr.top),
            "outer": f"{outer.right - outer.left}x{outer.bottom - outer.top}",
            "dpi": user32.GetDpiForWindow(hwnd)})
        return True

    user32.EnumWindows(cb(each), 0)
    return found


def main_window(app_pid: int) -> dict:
    """The full window, not the hidden compact panel.

    Both are class "Tauri Window" on the same pid, and the panel is declared
    visible:false, so picking the first match photographs a hidden 550x975
    surface and reports it as the app.
    """
    wins = all_windows(app_pid)
    if not wins:
        return {"hwnd": None, "windows": []}
    visible = [w for w in wins if w["visible"] and not w["minimized"]]
    pool = visible or wins
    chosen = max(pool, key=lambda w: w["clientArea"])
    return {**chosen, "windows": wins}


def window_state(app_pid: int) -> dict:
    m = main_window(app_pid)
    return {k: m.get(k) for k in ("hwnd", "title", "visible", "minimized",
                                  "maximized", "client", "outer", "dpi")}


class RecordingCDP(u19.CDP):  # type: ignore[misc]
    def __init__(self, ws_url: str):
        super().__init__(ws_url)
        self.events: list[dict] = []

    def cmd(self, method: str, params: dict | None = None) -> dict:
        return self._send_cmd(method, params)

    def eval(self, expr: str) -> object:
        return self.evaluate(expr)

    def click_at(self, x: float, y: float) -> None:
        for kind in ("mousePressed", "mouseReleased"):
            self._send_cmd("Input.dispatchMouseEvent", {
                "type": kind, "x": x, "y": y, "button": "left",
                "clickCount": 1, "buttons": 1 if kind == "mousePressed" else 0,
            })

    def drain(self, seconds: float) -> None:
        self._sock.settimeout(seconds)
        try:
            while True:
                try:
                    raw = self._recv_frame()
                except (socket.timeout, OSError):
                    break
                try:
                    obj = json.loads(raw.decode("utf-8"))
                except Exception:
                    continue
                if obj.get("method"):
                    self.events.append(obj)
        finally:
            self._sock.settimeout(None)


def png_colour_stats(path: Path) -> dict:
    """Decode a PNG through Tk (PPM intermediate) and count colours."""
    try:
        import tkinter
        tk = tkinter.Tk()
        tk.withdraw()
        photo = tkinter.PhotoImage(file=str(path))
        ppm = path.with_suffix(".ppm")
        photo.write(str(ppm), format="ppm")
        tk.destroy()
    except Exception as exc:  # noqa: BLE001
        return {"decoder": "failed", "error": repr(exc)[:160]}
    raw = ppm.read_bytes()
    parts = raw.split(b"\n", 3)
    if len(parts) < 4:
        return {"decoder": "ppm-unparsed"}
    dims = parts[1].split()
    body = parts[3]
    colors: dict[int, int] = {}
    for i in range(0, len(body) - 2, 3):
        c = (body[i] << 16) | (body[i + 1] << 8) | body[i + 2]
        colors[c] = colors.get(c, 0) + 1
    total = sum(colors.values()) or 1
    top = max(colors.items(), key=lambda kv: kv[1])
    near = sum(v for c, v in colors.items() if c <= 0x0B0B0B)
    return {"decoder": "tk-ppm", "size": f"{int(dims[0])}x{int(dims[1])}",
            "distinctColors": len(colors), "dominant": f"#{top[0]:06x}",
            "dominantFrac": round(top[1] / total, 4),
            "nearBlackFrac": round(near / total, 4)}


def probe_button(cdp: RecordingCDP, app_pid: int, label: str, aria: str) -> dict:
    """Click the real caption button by page coordinates, then read what the
    window did. The DOM says the click landed; Win32 says the shell obeyed."""
    geo = cdp.eval(f"""JSON.stringify((()=>{{
      const el=document.querySelector('[aria-label="{aria}"]');
      if(!el) return {{missing:true}};
      const r=el.getBoundingClientRect();
      const x=r.left+r.width/2, y=r.top+r.height/2;
      const hit=document.elementFromPoint(x,y);
      return {{x, y, w:r.width, h:r.height,
        hitIsButton: !!hit && (hit===el||el.contains(hit)||hit.closest && hit.closest('[aria-label="{aria}"]')===el),
        hitTag: hit? hit.tagName+'.'+(hit.className||''):'',
        zoomText: (document.querySelector('.winctl-zoom')||{{textContent:''}}).textContent.trim()}};
    }})()""")
    g = json.loads(geo)
    out: dict = {"label": label, "aria": aria, "geometry": g}
    if g.get("missing") or not g.get("hitIsButton"):
        out["skipped"] = "target not clickable at its own coordinates"
        return out
    before = window_state(app_pid)
    cdp.click_at(g["x"], g["y"])
    time.sleep(1.4)
    out["stateBefore"] = before
    out["stateAfter"] = window_state(app_pid)
    out["changed"] = {k: [before.get(k), out["stateAfter"].get(k)]
                      for k in ("visible", "minimized", "maximized", "title")
                      if before.get(k) != out["stateAfter"].get(k)}
    out["zoomTextAfter"] = cdp.eval(
        "(document.querySelector('.winctl-zoom')||{textContent:'?'}).textContent")
    return out


def main() -> int:
    user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
    exe, art = u19.resolve_app_exe()
    report["artifactGate"] = {"status": art.get("status"),
                              "reason": art.get("reason"),
                              "freshness": art.get("freshness")}
    if exe is None:
        report["verdict"] = "STALE_OR_MISSING_BINARY"
        dump()
        return 1
    blob = exe.read_bytes()
    report["exeIdentity"] = {"path": str(exe), "bytes": len(blob),
                            "sha256": hashlib.sha256(blob).hexdigest(),
                            "mtime": time.strftime(
                                "%Y-%m-%dT%H:%M:%S",
                                time.localtime(exe.stat().st_mtime))}

    sidecar, port, _th, _srv = u19.start_sidecar()
    base = f"http://127.0.0.1:{port}"
    cdp_port = u19.pick_free_port()
    udf = HERE / f"EBWebView-final-{int(time.time())}"
    report["launch"] = {"sidecar": base, "cdpPortRequested": cdp_port,
                        "webview2UserDataFolder": str(udf)}

    env = dict(os.environ)
    env["WORK_LAB_OBSERVER_API_URL"] = base + "/api/v1/snapshot"
    env["WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS"] = (
        f"--remote-debugging-port={cdp_port} --remote-allow-origins=*")
    env["WEBVIEW2_USER_DATA_FOLDER"] = str(udf)
    p = subprocess.Popen([str(exe)], cwd=str(OBS / "src-tauri"), env=env,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    cdp = None
    try:
        time.sleep(9.0)
        report["appAlive"] = p.poll() is None
        report["windowState"] = window_state(p.pid)
        live, rows = wait_for_cdp_port(cdp_port, udf, p.pid)
        report["webviewProcesses"] = rows
        report["cdpPortLive"] = live
        if not live:
            report["verdict"] = "NO_CDP_ENDPOINT"
            dump()
            return 1
        targets = json.loads(cdp_get(live, "/json/list"))
        report["cdpTargets"] = [{"type": t.get("type"), "title": t.get("title"),
                                 "url": t.get("url")} for t in targets]
        page = next((t for t in targets if t.get("type") == "page"
                     and t.get("webSocketDebuggerUrl")), None)
        if not page:
            report["verdict"] = "NO_PAGE_TARGET"
            dump()
            return 1

        cdp = RecordingCDP(page["webSocketDebuggerUrl"])
        cdp.cmd("Runtime.enable")
        cdp.cmd("Log.enable")
        cdp.cmd("Page.enable")
        cdp.drain(2.0)

        q = """JSON.stringify({
          href: location.href, title: document.title,
          rootChildren: (document.getElementById('root')||{children:[]}).children.length,
          rootHtmlBytes: (document.getElementById('root')||{innerHTML:''}).innerHTML.length,
          bodyTextChars: (document.body.innerText||'').length,
          bodyTextSample: (document.body.innerText||'').replace(/\\s+/g,' ').slice(0,200),
          htmlBg: getComputedStyle(document.documentElement).backgroundColor,
          styleSheets: document.styleSheets.length,
          cssRules: (()=>{try{return [...document.styleSheets].reduce((n,s)=>n+s.cssRules.length,0)}catch(e){return 'blocked:'+e.name}})(),
          zoomText: (document.querySelector('.winctl-zoom')||{textContent:'?'}).textContent,
          captionButtons: [...document.querySelectorAll('.winctl-btn')].map(b=>b.getAttribute('aria-label')),
          routeButtons: document.querySelectorAll('nav button, aside button').length,
          devicePixelRatio: window.devicePixelRatio,
          viewport: innerWidth+'x'+innerHeight}})"""
        report["domReadback"] = json.loads(cdp.eval(q))
        dump()

        png = HERE / "release-render-cdp.png"
        png.write_bytes(base64.b64decode(
            cdp.cmd("Page.captureScreenshot", {"format": "png"}).get("data", "")))
        report["cdpScreenshot"] = {"path": str(png), "bytes": png.stat().st_size,
                                   **png_colour_stats(png)}
        dump()

        report["gdiCrossCheck"] = u19._gdi_render_proof(p.pid)
        dump()

        # ---- the interaction proof, in the order that keeps the app alive ----
        seq = []
        seq.append(probe_button(cdp, p.pid, "zoom-out", "缩小界面"))
        seq.append(probe_button(cdp, p.pid, "zoom-reset", "重置缩放"))
        seq.append(probe_button(cdp, p.pid, "maximize-toggle", "最大化或还原窗口"))
        if window_state(p.pid).get("maximized"):
            seq.append(probe_button(cdp, p.pid, "maximize-toggle-back",
                                    "最大化或还原窗口"))
        seq.append(probe_button(cdp, p.pid, "minimize", "最小化窗口"))
        if window_state(p.pid).get("minimized"):
            h = window_state(p.pid).get("hwnd")
            if h:
                user32.ShowWindow(h, 9)  # SW_RESTORE
                time.sleep(1.0)
        report["interactionProof"] = seq

        # Events collected across the whole run: CSP blocks, exceptions, logs.
        # _send_cmd discards interleaved frames it is not waiting for, so drain
        # while nothing is pending to pick up what the interactions produced.
        cdp.drain(2.0)
        report["cdpEvents"] = [
            {"method": e["method"],
             "params": {k: v for k, v in (e.get("params") or {}).items()
                        if k in ("level", "text", "source", "url", "type",
                                 "message", "exception")}}
            for e in cdp.events
            if e["method"] in ("Log.entryAdded", "Runtime.exceptionThrown",
                               "Runtime.consoleAPICalled")]

        # Close last: it ends the process.
        seq.append(probe_button(cdp, p.pid, "close", "关闭窗口"))
        time.sleep(2.0)
        report["appExitedAfterClose"] = p.poll() is not None
        report["exitCode"] = p.returncode
        dump()

        clicks_ok = [s for s in seq if s.get("changed")]
        report["verdict"] = {
            "surfaceRendered": report["domReadback"]["rootChildren"] > 0
            and report["cdpScreenshot"].get("distinctColors", 0) > 100,
            "captionControlsResponded": len(clicks_ok),
            "closedTheApp": report["appExitedAfterClose"],
            "note": ("changed=non-empty window state after a dispatched click; "
                     "zoom moves webview state, not window state, so it is read "
                     "from the page"),
        }
        dump()
        return 0
    except Exception as exc:  # noqa: BLE001
        report["error"] = repr(exc)
        dump()
        return 1
    finally:
        if cdp:
            cdp.close()
        if p.poll() is None:
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(p.pid)],
                           capture_output=True, check=False)


if __name__ == "__main__":
    sys.exit(main())
