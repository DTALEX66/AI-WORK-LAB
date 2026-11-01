#!/usr/bin/env python
"""P0-C: attach to the RUNNING release binary over CDP and read the truth.

The prior round concluded "release builds expose no CDP endpoint because
Cargo.toml has no [features] devtools section". Measured 2026-10-06 20:15 that
is wrong on both halves: WebView2's remote-debugging port is opened by the
Chromium browser process, not by Tauri's devtools feature, and
WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS does reach it (the flag is present in the
browser process command line and the port LISTENS).

So this probe needs no build-config change at all. It reads, from the shipping
release binary:
  * the CDP target list (URL + document title of the live page),
  * the rendered DOM through Runtime.evaluate,
  * every console / security / CSP event through Log + Runtime,
  * a renderer-side screenshot (Page.captureScreenshot), which is the capture
    path that CAN see a DirectComposition surface — unlike GDI BitBlt.
"""
from __future__ import annotations

import ctypes
import hashlib
import importlib.util
import json
import os
import re
import socket
import struct
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(r"D:\All projects\WORK-LAB")
OBS = ROOT / "apps" / "observer"
HERE = ROOT / ".project-local" / "runs" / "p0c-oracle-20261006"
TARGET_DIR = ROOT / ".project-local" / "runs" / "u19-msvc-20261006" / "target"
os.environ["CARGO_TARGET_DIR"] = str(TARGET_DIR)

spec = importlib.util.spec_from_file_location(
    "u19", OBS / "scripts" / "u19_webview_e2e.py")
u19 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(u19)  # type: ignore[attr-defined]

user32 = ctypes.windll.user32
report: dict = {"startedAt": time.strftime("%Y-%m-%dT%H:%M:%S")}


def dump() -> None:
    (HERE / "cdp.json").write_text(json.dumps(report, indent=2, default=str),
                                   encoding="utf-8")


def port_listening(port: int) -> bool:
    s = socket.socket()
    s.settimeout(0.4)
    try:
        return s.connect_ex(("127.0.0.1", port)) == 0
    finally:
        s.close()


class RecordingCDP(u19.CDP):  # type: ignore[misc,name-defined]
    """Same wire protocol, but keep the interleaved CDP events."""

    def __init__(self, ws_url: str):
        super().__init__(ws_url)
        self.events: list[dict] = []

    def _send_cmd(self, method, params=None):
        self._id += 1
        msg = {"id": self._id, "method": method, "params": params or {}}
        payload = json.dumps(msg).encode("utf-8")
        frame = bytearray([0x81])
        if len(payload) < 126:
            frame.append(0x80 | len(payload))
        elif len(payload) < 65536:
            frame.append(0x80 | 126)
            frame += struct.pack(">H", len(payload))
        else:
            frame.append(0x80 | 127)
            frame += struct.pack(">Q", len(payload))
        mask = os.urandom(4)
        frame += mask
        frame += bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
        self._sock.sendall(bytes(frame))
        while True:
            raw = self._recv_frame()
            try:
                obj = json.loads(raw.decode("utf-8"))
            except Exception:
                continue
            if obj.get("method") and "id" not in obj:
                self.events.append(obj)
            if obj.get("id") == self._id:
                if "error" in obj:
                    raise RuntimeError(f"CDP {method}: {obj['error']}")
                return obj.get("result", {})

    def drain(self, seconds: float) -> None:
        self._sock.settimeout(seconds)
        try:
            while True:
                raw = self._recv_frame()
                try:
                    obj = json.loads(raw.decode("utf-8"))
                except Exception:
                    continue
                if obj.get("method"):
                    self.events.append(obj)
        except (socket.timeout, OSError):
            pass
        finally:
            self._sock.settimeout(None)


def png_stats(path: Path) -> dict:
    """Colour statistics for a PNG using Tk as the decoder (PNG -> PPM)."""
    try:
        import tkinter
    except ImportError:
        return {"decoder": "tkinter-missing"}
    try:
        tk = tkinter.Tk()
        tk.withdraw()
        photo = tkinter.PhotoImage(file=str(path))
        ppm = path.with_suffix(".ppm")
        photo.write(str(ppm), format="ppm")
        tk.destroy()
        raw = ppm.read_bytes()
        toks = raw.split(b"\n")
        idx, w, h, _max = 0, 0, 0, 0
        got = 0
        for i, t in enumerate(toks):
            if t.startswith(b"#") or not t:
                continue
            if got == 0:
                idx = i
                got = 1
                continue
            if got == 1:
                w, h = (int(x) for x in t.split())
                got = 2
                continue
            if got == 2:
                _max = int(t)
                break
        body = b"\n".join(toks[idx + 3:]) if got == 2 else b""
        body = raw.split(b"\n", 3)[3] if got == 2 else b""
        colors: dict[int, int] = {}
        for p in range(0, len(body) - 2, 3):
            c = (body[p] << 16) | (body[p + 1] << 8) | body[p + 2]
            colors[c] = colors.get(c, 0) + 1
        total = sum(colors.values()) or 1
        top = max(colors.items(), key=lambda kv: kv[1]) if colors else (0, 0)
        near_black = sum(v for c, v in colors.items() if c < 0x0A0A0A)
        return {"decoder": "tk-ppm", "size": f"{w}x{h}",
                "distinctColors": len(colors),
                "dominant": f"#{top[0]:06x}",
                "dominantFrac": round(top[1] / total, 4),
                "nearBlackFrac": round(near_black / total, 4)}
    except Exception as exc:  # noqa: BLE001
        return {"decoder": "failed", "error": repr(exc)[:200]}


def webview_browser_rows() -> list[str]:
    ps = ("Get-CimInstance Win32_Process -Filter \"Name='msedgewebview2.exe'\" "
          "| ForEach-Object { \"$($_.ProcessId)|$($_.CommandLine)\" }")
    out = subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                         capture_output=True, encoding="utf-8",
                         errors="replace", check=False).stdout or ""
    return [l for l in out.splitlines()
            if "com.dtalex.worklab.observer" in l.lower()
            or "p0c-oracle-20261006" in l.lower()]


def kill_stale_webview_environment() -> dict:
    """WebView2 keeps ONE browser process per user-data folder and reuses it: an
    orphan from an earlier launch silently owns the debug port, so the port the
    new process asks for is never opened. Clear only OUR leftovers first — the
    match is on this project's own WebView2 folders, never on the exe name."""
    # webview_browser_rows() already restricts to this project's own folders.
    before = webview_browser_rows()
    for line in before:
        pid = line.split("|", 1)[0].strip()
        subprocess.run(["taskkill", "/F", "/T", "/PID", pid],
                       capture_output=True, check=False)
    time.sleep(2.0)
    return {"killed": [l.split('|', 1)[0].strip() for l in before],
            "remainingAfter": [l.split('|', 1)[0].strip()
                               for l in webview_browser_rows()]}


def cdp_json(port: int, path: str, extra: str = "", wait: float = 3.0) -> str:
    """Raw-socket GET (never urllib: proxy env state breaks loopback CDP)."""
    try:
        s = socket.create_connection(("127.0.0.1", port), timeout=wait)
    except Exception as exc:  # noqa: BLE001
        return f"ERR {exc!r}"[:200]
    try:
        s.sendall((f"GET {path} HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\n"
                   f"{extra}Connection: close\r\n\r\n").encode("latin-1"))
        s.settimeout(wait)
        chunks = []
        while True:
            c = s.recv(65536)
            if not c:
                break
            chunks.append(c)
    except Exception as exc:  # noqa: BLE001
        return f"ERR {exc!r}"[:200]
    finally:
        s.close()
    raw = b"".join(chunks)
    head, _, body = raw.partition(b"\r\n\r\n")
    status = head.split(b"\r\n", 1)[0].decode("latin-1", "replace")
    if not status.endswith("200"):
        return f"ERR HTTP {status}"[:200]
    return body.decode("utf-8", "replace")


def find_page_ws(port: int, tries: int = 40) -> tuple[str, str]:
    """Return (wsUrl, how). Falls back to any target that exposes a page-level
    debugger url, not only type=='page'."""
    for i in range(tries):
        raw = cdp_json(port, "/json/list")
        try:
            targets = json.loads(raw)
        except Exception:
            time.sleep(0.5)
            continue
        for want in ("page", None):
            for t in targets:
                if t.get("type") == want and t.get("webSocketDebuggerUrl"):
                    return t["webSocketDebuggerUrl"], f"try={i} type={want}"
        time.sleep(0.5)
    return "", "timeout"


def main() -> int:
    exe, art = u19.resolve_app_exe()
    if exe is None:
        report["verdict"] = {"status": "STALE_OR_MISSING_BINARY",
                             "reason": art.get("reason")}
        dump()
        return 1
    st = exe.stat()
    report["exe"] = {"path": str(exe), "bytes": st.st_size,
                     "sha256": hashlib.sha256(exe.read_bytes()).hexdigest()}

    sidecar, port, _th, _srv = u19.start_sidecar()
    base = f"http://127.0.0.1:{port}"
    report["staleEnvironment"] = kill_stale_webview_environment()
    cdp_port = u19.pick_free_port()
    report["sidecar"] = base
    report["cdpPortRequested"] = cdp_port

    # A private WebView2 user-data folder is what makes the port trustworthy:
    # WebView2 keeps ONE browser process per folder and reuses it, so an
    # inherited environment from the shared folder answers on the OLD port and
    # the requested one goes nowhere.
    udf = HERE / f"EBWebView-cdp-{int(time.time())}"
    env = dict(os.environ)
    env["WORK_LAB_OBSERVER_API_URL"] = base + "/api/v1/snapshot"
    env["WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS"] = (
        f"--remote-debugging-port={cdp_port} --remote-allow-origins=*")
    env["WEBVIEW2_USER_DATA_FOLDER"] = str(udf)
    p = subprocess.Popen([str(exe)], cwd=str(OBS / "src-tauri"), env=env,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    cdp = None
    try:
        time.sleep(10.0)
        rows = webview_browser_rows()
        report["webview2BrowserProcess"] = [
            {"pid": l.split("|", 1)[0],
             "portInCmdline": (re.search(r"--remote-debugging-port=(\d+)", l)
                               or [None, None])[1],
             "debugFlag": "remote-debugging-port" in l,
             "isBrowser": "--type=" not in l}
            for l in rows]
        listener_pids = {r["pid"] for r in report["webview2BrowserProcess"]}
        cand = [cdp_port] + [r["portInCmdline"] for r in report["webview2BrowserProcess"]
                             if r["portInCmdline"] and str(r["portInCmdline"]) != str(cdp_port)]
        report["candidatePorts"] = sorted(set(int(c) for c in cand))

        # Chromium writes the port it ACTUALLY bound to <udf>/DevToolsActivePort;
        # the number in --remote-debugging-port is only a request.
        dap = udf / "DevToolsActivePort"
        report["devToolsActivePortPath"] = str(dap)
        for _ in range(30):
            if dap.exists():
                try:
                    p_no = int(dap.read_text(encoding="utf-8", errors="replace")
                               .splitlines()[0].strip())
                    if p_no not in report["candidatePorts"]:
                        report["candidatePorts"].insert(0, p_no)
                    report["devToolsActivePort"] = p_no
                    break
                except Exception:  # noqa: BLE001
                    pass
            time.sleep(1.0)
        ns = subprocess.run(
            ["netstat", "-ano", "-p", "TCP"], capture_output=True,
            encoding="utf-8", errors="replace", check=False).stdout or ""
        report["listeningBefore"] = [l.strip() for l in ns.splitlines()
                                     if "LISTENING" in l and
                                     any(f":{c} " in l + " " for c in
                                         report["candidatePorts"])][:8]

        live_port = 0
        deadline = time.time() + 45
        tries = 0
        probe_log = []
        while time.time() < deadline:
            tries += 1
            for c in report["candidatePorts"]:
                for variant, hdr in (("plain", ""), ("origin",
                                                     "Origin: http://127.0.0.1\r\n")):
                    body = cdp_json(int(c), "/json/version", hdr, wait=6.0)
                    if '"Browser"' in body:
                        live_port = int(c)
                        report["answeredVia"] = variant
                        report["jsonVersionRaw"] = body[:600]
                        break
                    probe_log.append(f"{tries}:{c}:{variant}:{body[:70]}")
                if live_port:
                    break
            if live_port:
                break
            time.sleep(1.0)
        ns = subprocess.run(
            ["netstat", "-ano", "-p", "TCP"], capture_output=True,
            encoding="utf-8", errors="replace", check=False).stdout or ""
        report["netstatForCandidates"] = [l.strip() for l in ns.splitlines()
                                          if any(f":{c}" in l for c in
                                                 report["candidatePorts"])][:6]
        report["cdpPortProbeTries"] = tries
        report["cdpPortProbeLog"] = probe_log[:6]
        if not live_port:
            raise RuntimeError(f"no answering CDP port among {report['candidatePorts']}")
        report["cdpPortUsed"] = live_port
        report["cdpPortListening"] = port_listening(live_port)
        report["jsonListRaw"] = cdp_json(live_port, "/json/list")[:1500]

        ws, how = find_page_ws(live_port)
        report["cdpWebSocket"] = ws
        report["cdpWebSocketFoundBy"] = how
        if not ws:
            raise RuntimeError(f"no debugger ws on :{live_port}")
        targets = json.loads(cdp_json(live_port, "/json/list"))
        report["cdpTargets"] = [{"type": t.get("type"), "title": t.get("title"),
                                 "url": t.get("url")} for t in targets]
        cdp = RecordingCDP(ws)
        cdp._send_cmd("Runtime.enable")
        cdp._send_cmd("Log.enable")
        cdp._send_cmd("Page.enable")
        time.sleep(4.0)
        cdp.drain(3.0)

        q = """JSON.stringify({
          href: location.href,
          title: document.title,
          readyState: document.readyState,
          rootChildren: document.getElementById('root') ? document.getElementById('root').children.length : -1,
          rootHtmlBytes: document.getElementById('root') ? document.getElementById('root').innerHTML.length : -1,
          bodyTextChars: (document.body && document.body.innerText || '').length,
          bodyTextSample: ((document.body && document.body.innerText) || '').replace(/\\s+/g,' ').slice(0,160),
          htmlBg: getComputedStyle(document.documentElement).backgroundColor,
          bodyBg: getComputedStyle(document.body).backgroundColor,
          rootBg: document.getElementById('root') ? getComputedStyle(document.getElementById('root')).backgroundColor : null,
          scriptTags: document.scripts.length,
          moduleScripts: [...document.scripts].filter(s=>s.type==='module').length,
          linkStylesheets: document.styleSheets.length,
          cssRules: (()=>{try{return [...document.styleSheets].reduce((n,s)=>n+s.cssRules.length,0)}catch(e){return 'blocked:'+e.name}})(),
          sidebarPresent: !!document.querySelector('nav, aside, [class*=sidebar]'),
          kpiOrTable: !!document.querySelector('table, [class*=kpi], [class*=metric'),
          tauriGlobal: typeof window.__TAURI__,
          reactRootInternals: !!(document.getElementById('root') && Object.keys(document.getElementById('root')).some(k=>k.startsWith('__react')))
        })"""
        report["domReadback"] = json.loads(cdp.evaluate(q))
        report["cdpEvents"] = [
            {"method": e["method"],
             "detail": {k: v for k, v in (e.get("params") or {}).items()
                        if k in ("level", "text", "source", "url", "message",
                                 "type", "arguments")}}
            for e in cdp.events
            if e["method"] in ("Log.entryAdded", "Runtime.consoleAPICalled",
                               "Runtime.exceptionThrown")]
        png = HERE / "release-cdp-screenshot.png"
        png.write_bytes(cdp.screenshot())
        report["cdpScreenshot"] = {"path": str(png), "bytes": png.stat().st_size,
                                   **png_stats(png)}
        report["gdiCrossCheck"] = u19._gdi_render_proof(p.pid)
        dump()
        return 0
    except Exception as exc:  # noqa: BLE001
        report["error"] = repr(exc)
        dump()
        return 1
    finally:
        if cdp:
            cdp.close()
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(p.pid)],
                       capture_output=True, check=False)


import struct  # noqa: E402  (used by RecordingCDP._send_cmd)

if __name__ == "__main__":
    sys.exit(main())
