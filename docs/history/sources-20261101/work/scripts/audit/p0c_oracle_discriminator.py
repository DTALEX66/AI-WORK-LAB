#!/usr/bin/env python
"""P0-C discriminator: is the release "black screen" real, or a capture artifact?

The prior round's decisive comparison mixed two different instruments: a
headless-Chrome screenshot (renderer-side surface capture) against a GDI BitBlt
of a WebView2 window. GDI cannot see a DirectComposition visual, so both cases
were not comparable. This probe asks a question that needs no pixels at all:

  did the shipped release binary's JavaScript actually execute and reach the
  network?

The real React bundle, when it mounts, issues GET <api>/api/v1/snapshot and
opens an EventSource on GET <api>/api/v1/events. Both are recorded on the
in-process sidecar at HTTP level, plus TCP-level accept evidence, plus the
window/document titles. Headless Chrome on the SAME dist is the positive
control, so a silent release path cannot be explained away as "the frontend
never fetches".

Read-only with respect to the repository: nothing here writes a tracked file.
"""
from __future__ import annotations

import ctypes
import http.client
import http.server
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
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(r"D:\All projects\WORK-LAB")
OBS = ROOT / "apps" / "observer"
HERE = ROOT / ".project-local" / "runs" / "p0c-oracle-20261006"
HERE.mkdir(parents=True, exist_ok=True)

spec = importlib.util.spec_from_file_location(
    "u19", OBS / "scripts" / "u19_webview_e2e.py")
u19 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(u19)  # type: ignore[attr-defined]

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32


# ---------------------------------------------------------------------------
# HTTP-level oracle: record every request the sidecar answers.
# ---------------------------------------------------------------------------
T0 = time.time()
REQS: list[dict] = []
_lock = threading.Lock()

_orig_send_response_only = http.server.BaseHTTPRequestHandler.send_response_only


def _send_response_only(self, code, message=None):  # noqa: N802
    with _lock:
        REQS.append({
            "t": round(time.time() - T0, 3),
            "method": getattr(self, "command", None),
            "path": getattr(self, "path", None),
            "code": code,
            "origin": self.headers.get("Origin"),
            "referer": self.headers.get("Referer"),
            "accept": (self.headers.get("Accept") or "")[:80],
            "ua": (self.headers.get("User-Agent") or "")[:120],
        })
    return _orig_send_response_only(self, code, message)


http.server.BaseHTTPRequestHandler.send_response_only = _send_response_only


def requests_since(mark: int, needle: str) -> list[dict]:
    with _lock:
        return [r for r in REQS[mark:] if needle in (r["path"] or "")]


def tcp_evidence(port: int) -> list[dict]:
    out = subprocess.run(["netstat", "-ano", "-p", "TCP"], capture_output=True,
                         encoding="utf-8", errors="replace",
                         check=False).stdout or ""
    hits = []
    for line in out.splitlines():
        if f":{port}" in line and "LISTEN" not in line.upper():
            hits.append(line.strip())
    return hits[:12]


def port_listening(port: int) -> bool:
    s = socket.socket()
    s.settimeout(0.4)
    try:
        return s.connect_ex(("127.0.0.1", port)) == 0
    finally:
        s.close()


def webview2_procs() -> list[dict]:
    """Command lines of the msedgewebview2.exe processes our app owns."""
    ps = ("Get-CimInstance Win32_Process -Filter \"Name='msedgewebview2.exe'\" "
          "| ForEach-Object { \"$($_.ProcessId)|$($_.CommandLine)\" }")
    out = subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                         capture_output=True, encoding="utf-8", errors="replace",
                         check=False).stdout or ""
    rows = []
    for line in out.splitlines():
        if "app.exe" in line.lower():
            pid, _, cmd = line.partition("|")
            rows.append({
                "pid": pid.strip(),
                "browser": "--type=" not in cmd,
                "debugFlag": ("remote-debugging-port" in cmd),
                "userDataDir": (re.search(r'--user-data-dir="?([^"\s]+)', cmd)
                                or [None, None])[1],
                "len": len(cmd),
            })
    return rows


# ---------------------------------------------------------------------------
# Window / title readback (no pixels)
# ---------------------------------------------------------------------------
def enumerate_windows(pid: int) -> list[dict]:
    import ctypes.wintypes as wt
    WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
    found: list[dict] = []

    def cb(hwnd, _lparam):
        wpid = wt.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(wpid))
        if wpid.value != pid:
            return True
        if not user32.IsWindowVisible(hwnd):
            return True
        n = user32.GetWindowTextLengthW(hwnd)
        buf = ctypes.create_unicode_buffer(n + 1)
        user32.GetWindowTextW(hwnd, buf, n + 1)
        rect = wt.RECT()
        user32.GetClientRect(hwnd, ctypes.byref(rect))
        cls = ctypes.create_unicode_buffer(256)
        user32.GetClassNameW(hwnd, cls, 256)
        found.append({
            "hwnd": hwnd,
            "title": buf.value,
            "client": f"{rect.right - rect.left}x{rect.bottom - rect.top}",
            "dpi": user32.GetDpiForWindow(hwnd),
            "class": cls.value,
        })
        return True

    user32.EnumWindows(WNDENUMPROC(cb), 0)
    return found


def child_windows(pid: int) -> list[dict]:
    """WebView2 puts its render surface in named child HWNDs; their presence is
    a structural (non-pixel) sign that a document is being displayed."""
    import ctypes.wintypes as wt
    out: list[dict] = []

    def walk(hwnd, depth):
        buf = ctypes.create_unicode_buffer(256)
        user32.GetClassNameW(hwnd, buf, 256)
        vis = bool(user32.IsWindowVisible(hwnd))
        rect = wt.RECT()
        user32.GetClientRect(hwnd, ctypes.byref(rect))
        if depth > 0 and "Chrome_" in buf.value:
            out.append({"class": buf.value, "visible": vis, "depth": depth,
                        "client": f"{rect.right - rect.left}x{rect.bottom - rect.top}"})
        child = user32.GetWindow(hwnd, 5)  # GW_CHILD
        while child:
            walk(child, depth + 1)
            child = user32.GetWindow(child, 2)  # GW_HWNDNEXT

    for w in enumerate_windows(pid):
        walk(w["hwnd"], 0)
    return out


def launch(exe: Path, api_url: str, extra_env: dict | None) -> subprocess.Popen:
    env = dict(os.environ)
    env["WORK_LAB_OBSERVER_API_URL"] = api_url
    env.pop("WORK_LAB_U19_CDP_PORT", None)
    env.pop("WORK_LAB_U19_PROBE_STATUS", None)
    env.pop("WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS", None)
    env.update(extra_env or {})
    return subprocess.Popen([str(exe)], cwd=str(OBS / "src-tauri"), env=env,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def kill(pid: int) -> None:
    subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)],
                   capture_output=True, text=True, encoding="utf-8", errors="replace", check=False)


def observe(exe: Path, label: str, extra_env: dict | None,
            settle_s: float = 14.0, sidecar_base: str = "") -> dict:
    mark = len(REQS)
    p = launch(exe, sidecar_base + "/api/v1/snapshot", extra_env)
    rec: dict = {"case": label, "pid": p.pid, "env": sorted(
        k for k in (extra_env or {}) if k.startswith(("WEBVIEW2", "WORK_LAB")))}
    try:
        time.sleep(settle_s)
        alive = p.poll() is None
        rec["alive"] = alive
        rec["exitCode"] = p.returncode
        rec["windows"] = enumerate_windows(p.pid)
        rec["webviewChildHwnds"] = child_windows(p.pid)
        rec["snapshotReqs"] = requests_since(mark, "/api/v1/snapshot")
        rec["eventsReqs"] = requests_since(mark, "/api/v1/events")
        rec["tcpToSidecar"] = tcp_evidence(int(sidecar_base.rsplit(":", 1)[1]))
        if extra_env and "WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS" in extra_env:
            m = re.search(r"--remote-debugging-port=(\d+)",
                          extra_env["WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS"])
            port = int(m.group(1))
            rec["cdpPort"] = port
            rec["cdpPortListening"] = port_listening(port)
            rec["webview2Procs"] = webview2_procs()
        rec["gdiProof"] = u19._gdi_render_proof(p.pid)
    finally:
        kill(p.pid)
        time.sleep(1.0)
    return rec


CHROME = str(Path(os.environ.get("PROGRAMFILES", "C:/Program Files"))
             / "Google/Chrome/Application/chrome.exe")


def chrome_render(url: str, udd: Path, timeout_s: int) -> dict:
    """Headless Chrome render of the shipped dist. A live EventSource keeps
    virtual time from settling, so --dump-dom can hang; a timeout is recorded,
    never silently turned into a zero."""
    args = [CHROME, "--headless=new", "--disable-gpu", "--no-sandbox",
            f"--user-data-dir={udd}", "--window-size=1280,820",
            "--virtual-time-budget=10000", "--dump-dom", url]
    try:
        cp = subprocess.run(args, capture_output=True, timeout=timeout_s, check=False)
        out, err, timed_out = cp.stdout or b"", cp.stderr or b"", False
    except subprocess.TimeoutExpired as e:
        out, err, timed_out = (e.stdout or b""), (e.stderr or b""), True
    body = out.decode("utf-8", "replace")
    return {"url": url, "domBytes": len(body.encode("utf-8")),
            "timedOut": timed_out,
            "domHasChrome": "Chrome_WidgetWin" in body,
            "sidebarText": ("CONTROL TOWER" in body.upper() or "工作台" in body
                            or "Observer" in body),
            "stderr": err.decode("utf-8", "replace")[-300:]}


def main() -> int:
    user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))  # PER_MONITOR_AWARE_V2
    report: dict = {"startedAt": time.strftime("%Y-%m-%dT%H:%M:%S"), "cases": []}

    def dump() -> None:
        (HERE / "oracle.json").write_text(
            json.dumps(report, indent=2, default=str), encoding="utf-8")

    exe, art = u19.resolve_app_exe()
    report["artifact"] = {"exe": str(exe),
                          "chosen": art.get("chosen"), "reason": art.get("reason")}
    if exe is None:
        report["verdict"] = "STALE_OR_MISSING_BINARY"
        dump()
        print(json.dumps(report, indent=2, default=str))
        return 1
    st = exe.stat()
    report["exeIdentity"] = {"path": str(exe), "bytes": st.st_size,
                             "mtime": time.strftime(
                                 "%Y-%m-%dT%H:%M:%S", time.localtime(st.st_mtime))}

    sidecar, port, _th, _srv = u19.start_sidecar()
    base = f"http://127.0.0.1:{port}"
    report["sidecar"] = {"base": base}

    # --- case A: the production launch path, nothing injected ----------------
    report["cases"].append(observe(exe, "A-release-default", None,
                                   sidecar_base=base))
    dump()

    # --- case B: same, plus the process-level CDP env var -------------------
    cdp_port = u19.pick_free_port()
    report["cases"].append(observe(
        exe, "B-release-webview2-cdp-env",
        {"WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS":
         f"--remote-debugging-port={cdp_port} --remote-allow-origins=*"},
        sidecar_base=base))
    dump()

    # --- positive controls: headless Chrome on the SAME dist ----------------
    ctrl_port = u19.pick_free_port()
    srv = subprocess.Popen(
        [sys.executable, "-m", "http.server", str(ctrl_port), "--bind", "127.0.0.1"],
        cwd=str(OBS / "frontend" / "dist"), stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL)
    time.sleep(2.0)
    udd = HERE / "chrome-udf"
    try:
        mark = len(REQS)
        report["cases"].append({
            "case": "C1-chrome-no-api",
            **chrome_render(f"http://127.0.0.1:{ctrl_port}/index.html"
                            "?view=full&mode=UNKNOWN&theme=dark&shell=tauri",
                            udd, 90)})
        dump()

        mark = len(REQS)
        api_url = urllib.parse.quote(base + "/api/v1/snapshot", safe="")
        c2 = chrome_render(f"http://127.0.0.1:{ctrl_port}/index.html"
                           f"?view=full&mode=UNKNOWN&theme=dark&shell=tauri&api={api_url}",
                           HERE / "chrome-udf2", 45)
        c2["case"] = "C2-chrome-with-api"
        c2["snapshotReqs"] = requests_since(mark, "/api/v1/snapshot")
        c2["eventsReqs"] = requests_since(mark, "/api/v1/events")
        report["cases"].append(c2)
        dump()
    finally:
        srv.kill()

    # --- verdict ------------------------------------------------------------
    def hits(case):
        return len(case.get("snapshotReqs", [])) + len(case.get("eventsReqs", []))

    rel = next((c for c in report["cases"] if c["case"].startswith("A-")), {})
    ctrl = next((c for c in report["cases"] if c["case"].startswith("C2-")), {})
    report["sidecarTotalRequests"] = len(REQS)
    r, c = hits(rel), hits(ctrl)
    if r > 0:
        reading = ("RELEASE JS RAN and reached the backend: the GDI blank capture "
                   "is an instrument artifact, not a product defect")
    elif c > 0:
        reading = (f"release silent while the control on the SAME dist fetched {c}x "
                   "-> the release webview really never ran the bundle")
    else:
        reading = ("both silent: the oracle does not fire in either engine -> "
                   "inconclusive, fix the oracle")
    report["verdict"] = {"releaseHits": r, "controlHits": c, "reading": reading}
    dump()
    print(json.dumps(report["verdict"], indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
