#!/usr/bin/env python
"""U19 — Final Windows product E2E, real-WebView readback (WINDOWS_TAURI_E2E gate).

The release iron law: the converged product must be proven through a REAL
WebView readback (not `about:blank`). This harness:

  1. Serves the real v3 snapshot backend on a dynamic loopback port via
     `services/orchestration/sidecar.py` (`create_server(WorkflowSidecar(...))`
     + ThreadingHTTPServer) — the SAME pattern the governance tests use. No
     second engine.
  2. Launches the *real* portable Tauri `app.exe` with
     `WORK_LAB_OBSERVER_API_URL=http://127.0.0.1:<port>/api/v1/snapshot` and
     `WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS=--remote-debugging-port=<cdp>` so
     the WebView2 can be inspected over CDP without modifying the app.
  3. Reads the WebView back over CDP (a self-contained stdlib WebSocket client
     — no dependency) and asserts the root node rendered the REAL React app
     (not about:blank): the title, `#root` populated, the sidebar/KPI text,
     and the U03-migrated WCAG AA live region (role=status[aria-live=polite])
     present in the shipped build.
  4. Writes a real E2E evidence artifact under `.project-local/runs/` and archives it under
     `.project-local/artifacts/native-evidence/` with the commit and the exe digest in its name,
     so an uploaded verdict cannot be read as evidence about a different tree.

Exit 0 = PASS (evidence written), or NATIVE_SURFACE_UNAVAILABLE — and only
when `scripts/audit/desktop_capability_probe.py` reports that this environment
cannot draw at all (any of `layers.display.verdict`, `layers.draw.verdict`,
`layers.visible_desktop.verdict` is not PASS). The probe, not an environment variable, decides: `GITHUB_ACTIONS`
says which machine this is, and a machine flag is weaker evidence than a pixel
read back. An unproven surface in an environment that CAN draw is a real
failure and exits non-zero, because that is exactly the case the old
`SKIPPED_HEADLESS` rule reported as a green tick (measured on `main` at
b218ef82: the runner's probe printed `display PASS 1024x768 / draw PASS`, the
WebView2 surface printed nothing, and the step exited 0). Exit 1 = FAIL. No
unverified stage is ever reported as PASS.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import socket
import struct
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
import urllib.error
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]  # WORK-LAB (file lives at apps/observer/scripts/)
OBS = ROOT / "apps" / "observer"
sys.path.insert(0, str(ROOT / "packages" / "client-neutral-core" / "scripts"))
sys.path.insert(0, str(ROOT / "services" / "orchestration"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from write_artifact_receipt import (  # noqa: E402
    RECEIPT_SCHEMA, RECEIPT_SCHEMA_V1, RECEIPT_SUFFIX, archive_native_evidence, digest,
    frontend_chain_files, input_files)

RUNS = ROOT / ".project-local" / "runs"
RUNS.mkdir(parents=True, exist_ok=True)

# The main window's declared width (tauri.conf.json app.windows[0].width), used
# only to decide whether the API already returned physical pixels.
WINDOW_LOGICAL_WIDTH_PX = 1280


# ---------------------------------------------------------------------------
# 1. Real v3 snapshot backend (loopback, dynamic port) — reuses the sidecar.
# ---------------------------------------------------------------------------
def start_sidecar() -> tuple[object, int, "threading.Thread", Path]:
    from sidecar import WorkflowSidecar, create_server  # noqa: PLC0415

    runtime_root = RUNS / "u19_sidecar_runtime"
    runtime_root.mkdir(parents=True, exist_ok=True)
    sidecar = WorkflowSidecar(ROOT, runtime_root)
    server = create_server(sidecar, "127.0.0.1", 0)  # port 0 = dynamic
    port = server.server_port
    th = threading.Thread(target=server.serve_forever, daemon=True)
    th.start()
    # wait until the endpoint actually answers
    base = f"http://127.0.0.1:{port}"
    for _ in range(40):
        try:
            with urllib.request.urlopen(base + "/api/v1/snapshot", timeout=2) as r:
                body = json.loads(r.read())
                if body.get("schemaVersion", "").startswith("workflow/snapshot"):
                    break
        except (urllib.error.URLError, TimeoutError):
            time.sleep(0.25)
    else:
        raise RuntimeError(f"sidecar v3 snapshot endpoint not ready at {base}")
    return sidecar, port, th, server


def snapshot_has_data(base_url: str) -> dict:
    with urllib.request.urlopen(base_url + "/api/v1/snapshot", timeout=5) as r:
        snap = json.loads(r.read())
    return {
        "schemaVersion": snap.get("schemaVersion"),
        "revision": snap.get("revision"),
        "projectCount": len(snap.get("projects", [])),
        "executionCount": len(snap.get("executions", [])),
        "nonEmpty": snap.get("projects") or snap.get("executions") is not None,
    }


# ---------------------------------------------------------------------------
# 2. Self-contained CDP over WebSocket (RFC6455, minimal, stdlib-only).
# ---------------------------------------------------------------------------
class ConnectionClosedError(RuntimeError):
    """The DevTools websocket sent a close frame (target died or was replaced)."""


class CDP:
    """Talk the Chrome DevTools Protocol to a WebView2 remote-debug port.

    Only implements the frames the E2E readback needs: Runtime.evaluate
    (returnByValue), Page.getLayoutMetrics / captureScreenshot. No library.
    """

    def __init__(self, ws_url: str):
        host, port, path = self._split(ws_url)
        self._sock = socket.create_connection((host, port), timeout=15)
        self._send_handshake(host, port, path)
        self._id = 0

    @staticmethod
    def _split(ws_url: str):
        m = re.match(r"ws://([^:/]+):(\d+)(/.*)", ws_url)
        if not m:
            raise ValueError("bad ws url " + ws_url)
        return m.group(1), int(m.group(2)), m.group(3) or "/"

    def _send_handshake(self, host: str, port: int, path: str) -> None:
        key = uuid.uuid4().hex
        req = (
            f"GET {path} HTTP/1.1\r\nHost: {host}:{port}\r\n"
            f"Upgrade: websocket\r\nConnection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n"
        )
        self._sock.sendall(req.encode("latin-1"))
        # read the 101 line by line
        buf = b""
        while b"\r\n\r\n" not in buf:
            chunk = self._sock.recv(4096)
            if not chunk:
                raise RuntimeError("CDP handshake: connection closed")
            buf += chunk
        head = buf.split(b"\r\n\r\n", 1)[0].decode("latin-1", "replace")
        if "101" not in head.split("\r\n")[0]:
            raise RuntimeError("CDP handshake rejected: " + head[:120])

    def _recv_frame(self, mask_len: bytes = b"") -> bytes:
        while True:
            b1b2 = self._sock.recv(2)
            if len(b1b2) < 2:
                raise RuntimeError("CDP: short frame header")
            b1, b2 = b1b2[0], b1b2[1]
            op = b1 & 0x0F
            masked = b2 & 0x80
            ln = b2 & 0x7F
            if ln == 126:
                ln = struct.unpack(">H", self._sock.recv(2))[0]
            elif ln == 127:
                ln = struct.unpack(">Q", self._sock.recv(8))[0]
            if masked:
                mask = self._sock.recv(4)
                data = bytearray(self._sock.recv(ln))
                for i in range(ln):
                    data[i] ^= mask[i % 4]
                payload = bytes(data)
            else:
                payload = self._sock.recv(ln) if ln else b""
            if op == 0x8:  # close
                raise ConnectionClosedError("CDP websocket closed")
            if op in (0x1, 0x2):  # text/binary
                return payload

    def _send_cmd(self, method: str, params: dict | None = None) -> dict:
        self._id += 1
        msg = {"id": self._id, "method": method, "params": params or {}}
        payload = json.dumps(msg).encode("utf-8")
        frame = bytearray()
        frame.append(0x81)  # FIN + text
        # RFC 6455 §5.3: client->server frames MUST be masked, so the payload-
        # length byte carries the 0x80 mask bit whenever a mask key follows.
        if len(payload) < 126:
            frame.append(0x80 | len(payload))
        elif len(payload) < 65536:
            frame.append(0x80 | 126); frame += struct.pack(">H", len(payload))
        else:
            frame.append(0x80 | 127); frame += struct.pack(">Q", len(payload))
        mask = os.urandom(4)
        frame += mask
        frame += bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
        self._sock.sendall(bytes(frame))
        # read frames until we get our id (server may interleave events)
        while True:
            raw = self._recv_frame()
            try:
                obj = json.loads(raw.decode("utf-8"))
            except Exception:
                continue
            if obj.get("id") == self._id:
                if "error" in obj:
                    raise RuntimeError(f"CDP {method} error: {obj['error']}")
                return obj.get("result", {})

    def evaluate(self, expr: str) -> object:
        res = self._send_cmd("Runtime.evaluate", {
            "expression": expr, "returnByValue": True, "awaitPromise": False,
        })
        return res.get("result", {}).get("value")

    def screenshot(self) -> bytes:
        res = self._send_cmd("Page.captureScreenshot", {"format": "png"})
        import base64
        return base64.b64decode(res.get("data", ""))

    def close(self):
        try:
            self._sock.close()
        except Exception:
            pass


def _cdp_http_get(path: str, port: int) -> str:
    """Minimal raw-socket HTTP/1.1 GET against a CDP debug port.

    urllib is deliberately NOT used here: any http_proxy/https_proxy
    environment state would break the loopback /json endpoints with
    confusing BadStatusLine errors.
    """
    s = socket.create_connection(("127.0.0.1", port), timeout=3)
    try:
        s.sendall(
            (f"GET {path} HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\n"
             f"Connection: close\r\n\r\n").encode("latin-1")
        )
        chunks = []
        while True:
            c = s.recv(65536)
            if not c:
                break
            chunks.append(c)
        raw = b"".join(chunks)
    finally:
        s.close()
    head, _, body = raw.partition(b"\r\n\r\n")
    status = head.split(b"\r\n", 1)[0].decode("latin-1", "replace")
    if not status.endswith("200"):
        raise RuntimeError(f"CDP {path}: HTTP {status}")
    return body.decode("utf-8", "replace")


def discover_cdp_ws(cdp_port: int, tries: int = 60) -> str:
    """Find the WebView2 page's CDP websocket url. Retry — WebView2 opens the
    debug port lazily; the target appears once the first page loads."""
    last = ""
    for _ in range(tries):
        try:
            body = _cdp_http_get("/json/list", cdp_port)
            targets = json.loads(body)
            for t in targets:
                url = t.get("webSocketDebuggerUrl", "")
                if url and t.get("type") == "page":
                    last = url
                    return url
        except Exception:
            pass
        time.sleep(0.5)
    if last:
        return last
    raise RuntimeError(f"no CDP page target on 127.0.0.1:{cdp_port}")


def pick_free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


# ---------------------------------------------------------------------------
# 3. The readback assertions (real content, not about:blank).
# ---------------------------------------------------------------------------
def readback_asserts(cdp: CDP) -> dict:
    expr = """
    (() => {
      const root = document.querySelector('#root');
      const region = document.querySelector('div[role="status"][aria-live="polite"]');
      const kpiTitles = [...document.querySelectorAll('.grid')].length;
      return {
        url: location.href,
        isAboutBlank: location.href.startsWith('about:'),
        title: document.title,
        rootPopulated: !!(root && root.children && root.children.length > 0),
        rootTextLen: (root ? root.innerText : '').length,
        hasLiveRegion: !!region,
        liveRegionText: region ? region.textContent : null,
        bodyLen: (document.body ? document.body.innerText : '').length,
        hasSidebar: !!document.querySelector('nav, [class*="sidebar"], aside'),
      };
    })()
    """
    return cdp.evaluate(expr)


def _gdi_render_proof(app_pid: int) -> dict:
    """Capture the app's top-level windows via GDI PrintWindow and decide
    whether the WebView2 rendered REAL content (not about:blank). Pure
    stdlib + ctypes; graceful — returns status=unavailable on failure.

    A solid about:blank / background fill yields ~1-2 distinct colors; a real
    dashboard (text, KPI cards, accent colors) yields many. This is the
    architecture-agnostic proof that a real WebView painted the React app —
    it does not depend on the CDP browser-process subsystem (which may be
    absent on a headless runner even when the app itself runs fine).
    """
    import ctypes
    import ctypes.wintypes as wt
    try:
        u32 = ctypes.WinDLL("user32")
        g32 = ctypes.WinDLL("gdi32")
    except Exception as e:  # pragma: no cover - only non-Windows
        return {"status": "unavailable", "reason": "no win32 ctypes: " + repr(e)}

    # Strict argtypes (x64 ABI). Note the real export owners:
    #   user32: GetDC / ReleaseDC / PrintWindow
    #   gdi32 : CreateCompatibleDC / CreateCompatibleBitmap / SelectObject /
    #           DeleteDC / DeleteObject / GetBitmapBits
    u32.GetWindowThreadProcessId.argtypes = [wt.HWND, ctypes.POINTER(wt.DWORD)]
    # GetClientRect takes (HWND, LPRECT) — a RECT out-param, NOT two INT outs.
    # Calling it with byref(w), byref(h) writes the whole RECT into `w`, so the
    # width/height read back as left/top (always 0) and every real window looked
    # "0x0" — the defect that made a rendered surface look impossible.
    u32.GetClientRect.argtypes = [wt.HWND, ctypes.POINTER(wt.RECT)]
    u32.EnumWindows.argtypes = [ctypes.WINFUNCTYPE(ctypes.c_int, wt.HWND, wt.LPARAM), wt.LPARAM]
    u32.IsWindowVisible.argtypes = [wt.HWND]
    # GDI handles must be typed BOTH ways. These functions return HDC / HBITMAP
    # but default to c_int, so a raw int was being passed into the next call's
    # argtypes=[wt.HDC] and ctypes raised "argument 2: TypeError: wrong type".
    # Latent until 2026-10-06: the GetClientRect bug above meant `found` was
    # always empty, so PrintWindow was never reached on any machine.
    u32.GetDC.restype = wt.HDC
    u32.ReleaseDC.argtypes = [wt.HWND, wt.HDC]
    u32.PrintWindow.argtypes = [wt.HWND, wt.HDC, ctypes.c_uint]
    u32.PrintWindow.restype = ctypes.c_bool
    g32.CreateCompatibleDC.restype = wt.HDC
    g32.CreateCompatibleDC.argtypes = [wt.HDC]
    g32.CreateCompatibleBitmap.restype = wt.HBITMAP
    g32.CreateCompatibleBitmap.argtypes = [wt.HDC, wt.INT, wt.INT]
    g32.SelectObject.argtypes = [wt.HDC, wt.HGDIOBJ]
    g32.SelectObject.restype = wt.HGDIOBJ
    g32.GetBitmapBits.argtypes = [wt.HANDLE, ctypes.c_ulong, ctypes.c_void_p]
    g32.GetBitmapBits.restype = ctypes.c_ulong
    g32.DeleteObject.argtypes = [wt.HANDLE]
    g32.DeleteDC.argtypes = [wt.HDC]

    # Coordinate space, stated before anything is measured. Two facts, both
    # measured on this machine (2026-10-06):
    #
    #  (a) Once a process is per-monitor DPI aware, EVERY user32 rectangle call
    #      already returns physical pixels. Tauri declares width/height in
    #      LOGICAL pixels (tauri.conf.json width=1280), and at GetDpiForWindow
    #      =120 an unaware process sees the same window as 1280x820, so on this
    #      display logical == physical for this window and multiplying again is
    #      a double scale. A first cut of this code did multiply, allocated
    #      1600x1025 and photographed mostly empty space. The scale is
    #      therefore applied only when the read size and the DPI disagree.
    #  (b) PrintWindow CANNOT photograph a WebView2 surface: measured under
    #      PW_RENDERFULLCONTENT, PW_CLIENTONLY|PW_RENDERFULLCONTENT, plain 0 and
    #      PW_CLIENTONLY, at both sizes, it returned 1-2 distinct colours on a
    #      window that was visible, 1280x820, and painting a live dashboard.
    #      The surface is a composited child with no GDI paint path, so the
    #      parent's PrintWindow captures the shell background only. A screen
    #      BitBlt of the same rectangle returned 260 colours and the real UI.
    #      PrintWindow is still taken, as the cheap "did anything paint" signal
    #      and as a cross-check, but it can no longer decide the verdict alone:
    #      making it authoritative would fail a working build on every machine.
    #
    # BitBlt's own weakness is that it photographs whatever is on top. That is
    # handled POSITIVELY rather than assumed away: the client rectangle is
    # brought to the top first, the foreground window is then read back and
    # compared with the window we are photographing, and a disagreement marks
    # the capture occluded (not a product failure, and not evidence either).
    u32.GetDpiForWindow.argtypes = [wt.HWND]
    u32.GetDpiForWindow.restype = ctypes.c_uint
    u32.GetForegroundWindow.restype = wt.HWND
    u32.GetForegroundWindow.argtypes = []
    u32.SetWindowPos.argtypes = [wt.HWND, wt.HWND, ctypes.c_int, ctypes.c_int,
                                 ctypes.c_int, ctypes.c_int, wt.UINT]
    u32.SetWindowPos.restype = ctypes.c_bool
    u32.ClientToScreen.argtypes = [wt.HWND, ctypes.POINTER(wt.POINT)]
    u32.ClientToScreen.restype = ctypes.c_bool
    g32.BitBlt.argtypes = [wt.HDC, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                           ctypes.c_int, wt.HDC, ctypes.c_int, ctypes.c_int, wt.DWORD]
    g32.BitBlt.restype = ctypes.c_bool
    awareness = {}
    try:
        if hasattr(u32, "SetProcessDpiAwarenessContext"):
            u32.SetProcessDpiAwarenessContext.argtypes = [ctypes.c_void_p]
            u32.SetProcessDpiAwarenessContext.restype = ctypes.c_bool
            awareness["contextCallReturned"] = bool(
                u32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
            )
    except Exception as e:  # pragma: no cover - older Windows
        awareness["error"] = repr(e)

    dwmapi = None
    try:
        dwmapi = ctypes.WinDLL("dwmapi")
        dwmapi.DwmGetWindowAttribute.argtypes = [
            wt.HWND, wt.DWORD, ctypes.c_void_p, wt.DWORD]
        dwmapi.DwmGetWindowAttribute.restype = ctypes.c_long
    except Exception:  # pragma: no cover - non-Windows / no dwmapi
        dwmapi = None

    def _client_size(hwnd):
        rect = wt.RECT()
        if not u32.GetClientRect(hwnd, ctypes.byref(rect)):
            return 0, 0
        return rect.right - rect.left, rect.bottom - rect.top

    # 1) find the app's capturable top-level windows (sizeable, not the tray)
    found = {}
    def _enum(hwnd, _):
        pidout = wt.DWORD()
        u32.GetWindowThreadProcessId(hwnd, ctypes.byref(pidout))
        if pidout.value == app_pid:
            w, h = _client_size(hwnd)
            if w >= 200 and h >= 150:
                found[int(hwnd)] = (w, h, bool(u32.IsWindowVisible(hwnd)))
        return True
    cb = ctypes.WINFUNCTYPE(ctypes.c_int, wt.HWND, wt.LPARAM)(_enum)
    # Diagnostic: also enumerate EVERY top-level window owned by the pid (no
    # size/visibility filter) so the next CI run can distinguish
    # "no window at all" from "window exists but too small / hidden / unrendered".
    all_windows = {}
    def _enum_all(hwnd, _):
        pidout = wt.DWORD()
        u32.GetWindowThreadProcessId(hwnd, ctypes.byref(pidout))
        if pidout.value == app_pid:
            w, h = _client_size(hwnd)
            all_windows[int(hwnd)] = {"w": w, "h": h,
                                     "visible": bool(u32.IsWindowVisible(hwnd))}
        return True
    cb_all = ctypes.WINFUNCTYPE(ctypes.c_int, wt.HWND, wt.LPARAM)(_enum_all)
    u32.EnumWindows(cb_all, 0)
    u32.EnumWindows(cb, 0)
    if not found:
        return {"status": "unavailable",
                "reason": "no capturable top-level window for pid %d" % app_pid,
                "diagnostic_all_pid_windows": all_windows}

    def _histogram(raw: bytes, size: int) -> dict:
        seen = set()
        dom: dict = {}
        total = 0
        for i in range(0, size, 16):
            r, g, b = raw[i + 2], raw[i + 1], raw[i]  # BGRA in a DIB section
            q = ((r >> 4) << 8) | ((g >> 4) << 4) | (b >> 4)
            seen.add(q); total += 1
            dom[q] = dom.get(q, 0) + 1
        dominant = (max(dom.values()) / total) if total else 1.0
        return {"distinctColors": len(seen),
                "dominantFrac": round(dominant, 3),
                "nonBlank": bool(total) and len(seen) >= 16 and dominant < 0.92}

    def _blit(hwnd, w, h, source):
        """One capture attempt. source='screen' uses BitBlt from the desktop
        DC (the only path that sees the WebView2 surface); source='print' uses
        PrintWindow (background only, kept as a cross-check)."""
        scr_dc = u32.GetDC(0)
        mem_dc = g32.CreateCompatibleDC(scr_dc)
        hbm = g32.CreateCompatibleBitmap(scr_dc, w, h)
        old = g32.SelectObject(mem_dc, hbm)
        if source == "screen":
            pt = wt.POINT()
            u32.ClientToScreen(hwnd, ctypes.byref(pt))
            ok = g32.BitBlt(mem_dc, 0, 0, w, h, scr_dc, pt.x, pt.y, 0x00CC0020)
        else:
            ok = u32.PrintWindow(hwnd, mem_dc, 2)  # PW_RENDERFULLCONTENT
        data_size = w * h * 4
        buf = ctypes.create_string_buffer(data_size)
        # GetBitmapBits(hBmp, DWORD cbBuffer, LPVOID) — the count is a VALUE.
        # The previous call passed ctypes.byref(c_size_t(...)), which ctypes
        # rejects with "argument 2: TypeError: wrong type". It was never
        # reached before because the GetClientRect bug kept `found` empty.
        got = g32.GetBitmapBits(hbm, data_size, buf)
        g32.SelectObject(mem_dc, old)
        g32.DeleteObject(hbm)
        g32.DeleteDC(mem_dc)
        u32.ReleaseDC(0, scr_dc)
        if not ok or not got:
            return None
        return _histogram(buf.raw[:data_size], data_size)

    analysis = []
    for hwnd, (w, h, visible) in found.items():
        dpi = 96
        try:
            dpi = u32.GetDpiForWindow(hwnd) or 96
        except Exception:  # pragma: no cover - pre-1607 Windows
            pass
        # Whether user32 hands back PHYSICAL pixels is a property of THIS
        # process' DPI awareness, not of the window. Once
        # SetProcessDpiAwarenessContext(PER_MONITOR_AWARE_V2) succeeds, every
        # rectangle API already reports physical pixels and scaling again is a
        # double scale.
        #
        # Measured 2026-10-06: tauri.conf.json declares main = 1280x820 logical,
        # GetClientRect reports 1600x1025 at GetDpiForWindow = 120 -- exactly
        # 1280 * 120/96 -- i.e. already physical.
        #
        # A first cut tried to infer that from the numbers alone with a broken
        # comparison (w * 12 >= 1280 * dpi), concluded "logical", multiplied by
        # 1.25 AGAIN and allocated 2000x1281 for a 1600x1025 window. BitBlt then
        # copied 400x256 px of DESKTOP past the window's right/bottom edge, and
        # that foreign content made a completely blank window look like it had
        # painted 375-722 colours. Never enlarge past what the window occupies.
        aware = awareness.get("contextCallReturned") is True
        scale = 1.0 if aware else dpi / 96.0
        # Belt and braces: never request a rectangle larger than the client area
        # we actually measured. An over-large BitBlt silently photographs the
        # desktop beside the window and forges "content" that is not the app's.
        pw = max(1, min(w, int(round(w * scale))))
        ph = max(1, min(h, int(round(h * scale))))

        entry = {"hwnd": hwnd, "visible": visible, "dpi": dpi,
                 "sizeAsRead": [w, h], "captureSize": [pw, ph],
                 "scaleApplied": round(scale, 3),
                 "dpiAwareProcess": aware,
                 "expectedPhysicalWIfMain": round(
                     WINDOW_LOGICAL_WIDTH_PX * dpi / 96.0),
                 "capturedRectIn": ("physical client px (DPI-aware process)"
                                    if aware else "logical px, scaled to physical"),
                 "screen": {}, "printWindow": {}, "occlusion": {}}
        if dwmapi is not None:
            frame = wt.RECT()
            rc = wt.RECT()
            u32.GetWindowRect.argtypes = [wt.HWND, ctypes.POINTER(wt.RECT)]
            if dwmapi.DwmGetWindowAttribute(hwnd, 9, ctypes.byref(frame),
                                            ctypes.sizeof(frame)) == 0 \
                    and u32.GetWindowRect(hwnd, ctypes.byref(rc)):
                # Borderless windows still carry an invisible resize border; a
                # disagreement between the two rectangles is what makes a
                # capture look offset by a few px. Recorded, not fatal.
                entry["windowRectWH"] = [rc.right - rc.left, rc.bottom - rc.top]
                entry["frameBoundsWH"] = [frame.right - frame.left,
                                          frame.bottom - frame.top]

        # Bring the client rectangle to the top without resizing it, then read
        # back who actually owns the foreground. z-order is the only lever here
        # we can verify from inside this process.
        moved = False
        try:
            moved = bool(u32.SetWindowPos(hwnd, wt.HWND(-1), 0, 0, 0, 0,
                                          0x0001 | 0x0002 | 0x0008))
        except Exception:  # pragma: no cover
            moved = False
        time.sleep(0.4)
        foreground = int(u32.GetForegroundWindow() or 0)
        pt = wt.POINT()
        u32.ClientToScreen(hwnd, ctypes.byref(pt))
        entry["occlusion"] = {
            "raised": moved,
            "foregroundHwnd": foreground,
            "isForeground": foreground == int(hwnd),
            "clientOriginScreen": [pt.x, pt.y],
        }

        entry["screen"] = _blit(hwnd, pw, ph, "screen") or {"capture": "failed"}
        entry["printWindow"] = _blit(hwnd, pw, ph, "print") or {"capture": "failed"}
        # A screen capture only counts when the window we photographed is the
        # one on top of that rectangle. Otherwise the pixels belong to another
        # program and are evidence of nothing.
        entry["screen"]["usableAsEvidence"] = bool(
            entry["screen"].get("nonBlank") and entry["occlusion"]["isForeground"])
        analysis.append(entry)

    rendered = any(a["screen"].get("usableAsEvidence") for a in analysis)
    occluded = [a["hwnd"] for a in analysis
                if a["screen"].get("nonBlank") and not a["occlusion"]["isForeground"]]
    return {"status": "PASS" if rendered else "FAIL",
            "provenBy": "gdi-screen-bitblt-foreground-verified",
            "printWindowNote": (
                "PrintWindow is reported but cannot decide the verdict: it "
                "returns 1-2 colours for a WebView2 surface on this platform "
                "(measured 2026-10-06), because the composited web content has "
                "no GDI paint path through the parent window."
            ),
            "dpiAwareness": awareness,
            "occludedNotCounted": occluded,
            "windows": analysis}


def _stderr_tail(path: Path, n: int = 2048) -> str:
    """Read the tail of a captured app-stderr log (diagnostic evidence)."""
    try:
        data = path.read_bytes()
    except OSError:
        return ""
    if len(data) > n:
        data = data[-n:]
    return data.decode("utf-8", "replace")


# ---------------------------------------------------------------------------
# 3d. Artifact resolution — the binary must be the one THIS tree just built.
# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# Freshness, keyed to content rather than to filesystem times (ERR-105).
# ---------------------------------------------------------------------------
# Paths are relative to apps/observer. Git normalises line endings on this
# working copy, so `git checkout`, `git stash` or a filter pass can rewrite a
# file's mtime without changing one byte of it; keying freshness to mtime then
# reports a perfectly current binary as STALE, which is what blocked this gate
# twice on 2026-10-06.
FRONTEND_SOURCE_INPUTS = [
    "frontend/src",
    "frontend/index.html",
    "frontend/package.json",
    "frontend/package-lock.json",
    "frontend/vite.config.ts",
    "frontend/tsconfig.json",
    "frontend/postcss.config.js",
    "frontend/tailwind.config.js",
]
RUST_INPUTS = [
    "src-tauri/src",
    "src-tauri/Cargo.toml",
    "src-tauri/Cargo.lock",
    "src-tauri/build.rs",
    "src-tauri/tauri.conf.json",
    "src-tauri/capabilities",
]


def _git_raw(root: Path, *args: str) -> str:
    try:
        done = subprocess.run(["git", "-C", str(root), *args],
                              capture_output=True, text=True,
                              encoding="utf-8", errors="replace", check=False)
    except OSError:
        return ""
    return done.stdout


def content_change_floor(root: Path, obs: Path, segments: list[str]) -> tuple[float, dict]:
    """The latest evidenced content change among these inputs, else 0.0.

    Only a change that git can see in the *bytes* counts, and git answers for
    that through `git diff` (which applies the working-copy filters, so an
    end-of-line rewrite that leaves the text alone is not a change) plus
    untracked additions. Files that match HEAD contribute nothing: their mtimes
    move under checkout, stash and filter passes without any edit, and a
    timestamp is not content. A path that was deleted contributes "now", which
    fails the gate closed — the tree demonstrably changed.
    """
    pathspecs = [(obs / s).relative_to(root).as_posix() for s in segments]
    detail: dict = {"pathspecs": pathspecs}

    if _git_raw(root, "rev-parse", "--git-dir").strip() == "":
        detail["gitUnavailable"] = True
        return 0.0, detail

    changed = set()
    for args in (("diff", "--name-only", "HEAD", "-z", "--"),
                 ("ls-files", "--others", "--exclude-standard", "-z", "--")):
        raw = _git_raw(root, *args, *pathspecs)
        changed.update(r.strip().strip('"') for r in raw.split("\0") if r.strip())
    changed.discard("")

    floor = 0.0
    evidenced: list[str] = []
    for path in sorted(changed):
        target = root / path
        if not target.exists():
            detail.setdefault("deletedInputs", []).append(path)
            floor = max(floor, time.time())
            continue
        floor = max(floor, target.stat().st_mtime)
        evidenced.append(path)
    detail["changedSinceHead"] = evidenced
    return floor, detail


def artifact_freshness(root: Path, obs: Path) -> dict:
    """The timestamp each build stage must beat, plus the stage boundaries."""
    frontend_floor, frontend_detail = content_change_floor(
        root, obs, FRONTEND_SOURCE_INPUTS)
    rust_floor, rust_detail = content_change_floor(root, obs, RUST_INPUTS)

    dist = obs / "frontend" / "dist"
    dist_files = sorted(p for p in dist.rglob("*") if p.is_file()) if dist.is_dir() else []
    dist_newest = 0.0
    dist_newest_path = None
    for p in dist_files:
        m = p.stat().st_mtime
        if m >= dist_newest:
            dist_newest, dist_newest_path = m, p

    def iso(seconds: float) -> str:
        return (time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(seconds))
                if seconds else "NONE")

    return {
        "basis": "content-not-mtime",
        "gitUnavailable": bool(frontend_detail.get("gitUnavailable")
                               or rust_detail.get("gitUnavailable")),
        "frontendSourceFloor": frontend_floor,
        "frontendSourceFloorAt": iso(frontend_floor),
        "frontendSourceDetail": frontend_detail,
        "rustFloor": rust_floor,
        "rustFloorAt": iso(rust_floor),
        "rustDetail": rust_detail,
        "frontendDistFileCount": len(dist_files),
        "frontendDistNewest": {"path": str(dist_newest_path), "mtime": iso(dist_newest)}
        if dist_files else {"path": None, "mtime": "NONE"},
        # The bundle embedded in the binary is only as current as dist, and
        # dist is only as current as the source that produced it.
        "distSuperseded": bool(dist_files) and dist_newest < frontend_floor,
        "binaryFloor": max(rust_floor, dist_newest),
        "binaryFloorAt": iso(max(rust_floor, dist_newest)),
    }


def _iso(seconds: float) -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(seconds))


def _describe(path: Path) -> dict:
    st = path.stat()
    return {"path": str(path), "bytes": st.st_size, "mtime": _iso(st.st_mtime),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def receipt_verdict(root: Path, obs: Path, exe: Path) -> dict:
    """Judge the tree against the bytes the build itself attested to.

    Stronger than any timestamp rule: it sees a rollback to an older commit,
    where every input matches HEAD and nothing in the tree evidences the
    change. A receipt that does not describe the binary on disk is unusable
    rather than convenient — that is the one way this can be forged.

    The comparison set is whatever the receipt claims to cover, never whatever
    the current code happens to collect: a v1 receipt records only the
    compiler's inputs, so the frontend chain is reported as unattested rather
    than silently counted as a set of new files.
    """
    path = exe.with_name(exe.name + RECEIPT_SUFFIX)
    out: dict = {"present": False, "usable": False, "matches": False,
                 "exeSha256": digest(exe)}
    if not path.is_file():
        return out
    out["present"] = True
    out["receiptPath"] = str(path)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        stages = {RECEIPT_SCHEMA: ("inputs", "frontendInputs"),
                  RECEIPT_SCHEMA_V1: ("inputs",)}
        recorded: dict[str, str] = {}
        for key in stages.get(data.get("schemaVersion"), ()):
            for item in data.get(key, []):
                recorded[item["path"]] = item["sha256"]
    except Exception as exc:  # noqa: BLE001
        out["error"] = repr(exc)[:200]
        return out
    if data.get("schemaVersion") not in stages:
        out["reason"] = f"unexpected receipt schema {data.get('schemaVersion')!r}"
        return out
    if data.get("binary", {}).get("sha256") != out["exeSha256"]:
        out["reason"] = ("the receipt describes a different binary than the one "
                         "on disk, so it attests to nothing here")
        return out
    schema = data["schemaVersion"]
    live = input_files(root, obs)
    if schema == RECEIPT_SCHEMA:
        live = live + frontend_chain_files(root, obs)
    out["usable"] = True
    out["schemaVersion"] = schema
    out["coverage"] = ("compiler inputs + frontend build chain"
                      if schema == RECEIPT_SCHEMA else
                      "compiler inputs only")
    out["frontendChainAttested"] = schema == RECEIPT_SCHEMA
    out["writtenAt"] = data.get("writtenAt")
    out["gitHead"] = data.get("gitHead")
    out["inputCount"] = len(recorded)
    changed, missing = [], []
    for rel, sha in sorted(recorded.items()):
        current = root / rel
        if not current.is_file():
            missing.append(rel)
        elif digest(current) != sha:
            changed.append(rel)
    added = [p.relative_to(root).as_posix() for p in live
             if p.relative_to(root).as_posix() not in recorded]
    out.update({"changedInputs": changed[:20], "missingInputs": missing[:20],
                "addedInputs": added[:20],
                "matches": not (changed or missing or added)})
    return out


def resolve_app_exe() -> tuple[Path | None, dict]:
    """Pick the binary the build actually produced, and prove it is not stale.

    `cargo build` / `cargo tauri build` honour CARGO_TARGET_DIR, so on a
    machine that sets it the release exe lands in that directory while an older
    build leaves one at the default `src-tauri/target/release` path. Launching
    whichever path is hardcoded photographs a SUPERSEDED binary and reports its
    behaviour as current — the defect behind the "no rendered desktop surface"
    conclusion (ERR-099). CI does not set CARGO_TARGET_DIR, so the default path
    is correct there and stays as the fallback.

    Freshness compares content, not filesystem times (ERR-105), and covers
    every stage of the chain: frontend source → `frontend/dist` → `app.exe`.
    Checking only "exe newer than dist" certified a binary whose dist predated
    the source that should have rebuilt it. An artifact older than its inputs
    proves nothing about this tree, so the harness FAILS instead of quietly
    capturing it.
    """
    src_tauri = OBS / "src-tauri"
    target_override = os.environ.get("CARGO_TARGET_DIR")

    candidates: list[Path] = []
    if target_override:
        td = Path(target_override)
        if not td.is_absolute():
            td = Path.cwd() / td
        candidates.append(td / "release" / "app.exe")
    candidates.append(src_tauri / "target" / "release" / "app.exe")
    ordered, seen = [], set()
    for c in candidates:
        key = str(c).lower()
        if key not in seen:
            seen.add(key)
            ordered.append(c)

    freshness = artifact_freshness(ROOT, OBS)
    rs_files = [p for p in sorted((src_tauri / "src").rglob("*.rs"))] if (
        src_tauri / "src").is_dir() else []
    report: dict = {
        "cargoTargetDirEnv": target_override,
        "srcRustFileCount": len(rs_files),
        "frontendDistFileCount": freshness["frontendDistFileCount"],
        "freshness": freshness,
        "candidates": [],
    }
    if not rs_files and not freshness["frontendDistFileCount"]:
        report["status"] = "FAIL"
        report["reason"] = ("no build inputs found under %s — cannot prove any "
                            "binary is current" % src_tauri)
        return None, report

    # The bundle boundary is checked before any receipt: a receipt can prove a
    # binary consumed the dist that sits on disk, and that dist can itself be
    # older than the frontend source that should have rebuilt it.
    if freshness["distSuperseded"]:
        report["status"] = "STALE_OR_MISSING_BINARY"
        report["reason"] = (
            "frontend/dist is older than the last change to the frontend source "
            "that feeds it (dist newest %s, source floor %s). Run `npm run build` "
            "in apps/observer/frontend, then rebuild: a binary embedding a "
            "superseded bundle is not evidence about this tree."
            % (freshness["frontendDistNewest"]["mtime"],
               freshness["frontendSourceFloorAt"]))
        return None, report

    # A build receipt is then the strongest witness available: it compares the
    # bytes the compiler consumed against the bytes on disk now, which catches
    # the one case content evidence cannot — a rollback to an older commit,
    # where every input matches HEAD and nothing in the tree evidences change.
    receipted: list[Path] = []
    mismatched: list[tuple[Path, dict]] = []
    for c in ordered:
        if not c.exists():
            report["candidates"].append({"path": str(c), "exists": False})
            continue
        rv = receipt_verdict(ROOT, OBS, c)
        report["candidates"].append({
            "path": str(c), "exists": True, "bytes": c.stat().st_size,
            "mtime": _iso(c.stat().st_mtime), "sha256": rv["exeSha256"],
            "receipt": {k: rv[k] for k in sorted(rv) if k != "exeSha256"},
        })
        if rv["usable"] and rv["matches"]:
            receipted.append(c)
        elif rv["usable"]:
            mismatched.append((c, rv))

    if receipted:
        chosen = max(receipted, key=lambda p: p.stat().st_mtime)
        chosen_receipt = receipt_verdict(ROOT, OBS, chosen)
        report["status"] = "PASS"
        report["basis"] = "build-receipt"
        report["receiptCoverage"] = chosen_receipt["coverage"]
        report["receiptSchema"] = chosen_receipt["schemaVersion"]
        if not chosen_receipt["frontendChainAttested"]:
            report["basisLimit"] = (
                "this receipt predates the frontend-chain stage (schema "
                f"{chosen_receipt['schemaVersion']}), so the bundle it embeds is "
                "attested but the source that produced that bundle is not; an "
                "uncommitted frontend edit with a back-dated mtime would still "
                "only be visible through the content-evidence rule. Rebuild to "
                "get a v2 receipt.")
        report["chosen"] = _describe(chosen)
        return chosen, report

    if mismatched:
        # A receipt that describes this binary but not this tree is positive
        # evidence that the tree moved after the build. Falling through to the
        # weaker rule here would let a timestamp that nothing proves re-certify
        # a binary the stronger witness already condemned.
        c, rv = max(mismatched, key=lambda pair: pair[0].stat().st_mtime)
        named = (rv["changedInputs"] + rv["missingInputs"] + rv["addedInputs"])[:6]
        report["status"] = "STALE_OR_MISSING_BINARY"
        report["basis"] = "build-receipt"
        report["receiptCoverage"] = rv["coverage"]
        report["reason"] = (
            "the build receipt for %s does not match this tree: %d changed, %d "
            "missing, %d added of its %d recorded inputs (%s). It was written at "
            "%s against gitHead %s, so these bytes were edited after the build "
            "that produced this binary. Rebuild (and `npm run build` first if the "
            "frontend chain moved)."
            % (c.name, len(rv["changedInputs"]), len(rv["missingInputs"]),
               len(rv["addedInputs"]), rv["inputCount"], ", ".join(named) or "none",
               rv["writtenAt"], rv["gitHead"][:9]))
        return None, report

    report["basis"] = "content-evidence"
    report["basisLimit"] = (
        "no usable build receipt describes this binary, so a rollback to an "
        "older commit would not be seen (ERR-105). Run "
        "apps/observer/scripts/write_artifact_receipt.py right after the build.")

    if freshness["gitUnavailable"]:
        report["status"] = "FAIL"
        report["reason"] = (
            "no git repository answers for this tree, so no content change can be "
            "seen in it and no binary can be shown to be current. Run this gate "
            "from a checkout, not from an export.")
        return None, report

    floor = freshness["binaryFloor"]
    fresh = []
    for c in ordered:
        if not c.exists():
            continue
        st = c.stat()
        if st.st_mtime >= floor:
            fresh.append(c)

    if not fresh:
        report["status"] = "STALE_OR_MISSING_BINARY"
        report["reason"] = (
            "no release app.exe is at least as new as the last content change of "
            "its inputs (floor %s, from %s), and no build receipt vouches for one. "
            "Rebuild before running this gate: a superseded binary is not evidence "
            "about the current tree. Set CARGO_TARGET_DIR if your build writes "
            "outside src-tauri/target."
            % (freshness["binaryFloorAt"],
               (freshness["rustDetail"]["changedSinceHead"]
                or [freshness["frontendDistNewest"]["path"]])[0])
        )
        return None, report

    chosen = max(fresh, key=lambda p: p.stat().st_mtime)
    report["status"] = "PASS"
    report["chosen"] = _describe(chosen)
    return chosen, report


# ---------------------------------------------------------------------------
# 5. Desktop capability — the ONLY thing that may excuse an unproven surface.
# ---------------------------------------------------------------------------
CAPABILITY_PROBE = ROOT / "scripts" / "audit" / "desktop_capability_probe.py"
# CI already runs the probe and writes this artifact before reaching U19; consuming it keeps one
# measurement per run instead of two that can disagree.
CAPABILITY_REPORT = RUNS / "ci" / "desktop_capability.json"
# `visible_desktop` is the layer that separates "can paint a window" from "a window can be seen here":
# measured 2026-10-26 on the GitHub windows-latest runner, `display` and `draw` both PASSed while every
# window the real app owned read back `visible=false` and no CDP page target ever appeared.
DRAWABLE_LAYERS = ("display", "draw", "visible_desktop")


def read_capability_report() -> tuple[dict | None, str]:
    """The layered probe's JSON, plus where it came from (or why there is none).

    Artifact first (`$WORK_LAB_DESKTOP_CAPABILITY_JSON`, then the CI default path), then run the probe
    itself. A missing or unreadable report returns None and the caller treats that as "no permission to
    skip": a gate must not skip because its evidence is absent.
    """
    override = os.environ.get("WORK_LAB_DESKTOP_CAPABILITY_JSON")
    for candidate in [Path(override) if override else None, CAPABILITY_REPORT]:
        if candidate is None or not candidate.is_file():
            continue
        try:
            return json.loads(candidate.read_text(encoding="utf-8")), f"artifact={candidate}"
        except (OSError, ValueError) as exc:
            return None, f"unreadable artifact={candidate} reason={type(exc).__name__}: {exc}"
    if not CAPABILITY_PROBE.is_file():
        return None, f"no probe at {CAPABILITY_PROBE}"
    CAPABILITY_REPORT.parent.mkdir(parents=True, exist_ok=True)
    done = subprocess.run([sys.executable, str(CAPABILITY_PROBE), "--json-out", str(CAPABILITY_REPORT)],
                          cwd=str(ROOT), capture_output=True, text=True,
                          encoding="utf-8", errors="replace", check=False)
    try:
        report = json.loads(CAPABILITY_REPORT.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return None, (f"probe run exit={done.returncode} wrote no readable report at {CAPABILITY_REPORT} "
                      f"({type(exc).__name__})")
    return report, f"run-by-u19 exit={done.returncode} artifact={CAPABILITY_REPORT}"


def drawable_display(report: dict | None) -> tuple[bool, str]:
    """(can this environment draw, the probe field that decided it).

    Keys on the probe's own required capability layers: `display` (a screen with real metrics), `draw`
    (one pixel painted and read back) and `visible_desktop` (a desktop that shows top-level windows).
    `session` and `webview2` are corroboration by that file's own rule, so a runner with no interactive
    SESSIONNAME that still paints and still shows windows is a runner where a blank WebView2 is a product
    failure, not an environment boundary — that is the distinction the probe exists to make.

    A layer that is simply absent (an older report, or a probe that could not run it) answers "unresolved",
    which is NOT drawable and also NOT a denial: `capability_denies_drawing` below is what has to be true
    before an unproven surface may be recorded as an unavailable native surface.
    """
    if report is None:
        return False, "capability-report-unavailable"
    layers = _capability_layers(report)
    for name in DRAWABLE_LAYERS:
        verdict = layers.get(name)
        if verdict != "PASS":
            return False, f"layers.{name}.verdict={verdict if verdict else 'MISSING'}"
    return True, ",".join(f"layers.{name}.verdict=PASS" for name in DRAWABLE_LAYERS)


def capability_denies_drawing(report: dict | None) -> bool:
    """Did the probe actually DENY a required layer? Absence is not denial; only a reading is."""
    if report is None:
        return False
    layers = _capability_layers(report)
    return any(layers.get(name) in ("FAIL", "NOT_AVAILABLE") for name in DRAWABLE_LAYERS)


def _capability_layers(report: dict) -> dict[str, object]:
    layers: dict[str, object] = {}
    for layer in report.get("layers", []):
        if isinstance(layer, dict) and isinstance(layer.get("layer"), str):
            layers[layer["layer"]] = layer.get("verdict")
    return layers


def native_render_verdict(*, backend_ok: bool, surface_proven: bool, liveness: str | None,
                          probe_built: bool, drawable: bool, denied: bool = False) -> tuple[str, str]:
    r"""Decide the U19 verdict from the stage readings — the only rule the gate keys on.

    Pure, so a test can convict it without a desktop, a binary or a browser.

    `drawable` comes from the capability probe, not from an environment variable. An unproven surface in
    an environment the probe says CAN draw is a product failure (`FAIL`, exit non-zero); only where the
    probe denies drawing does the stage become `NATIVE_SURFACE_UNAVAILABLE` — recorded as unverified and
    never as a pass. The combination this replaces was `if not surface_proven and ... and GITHUB_ACTIONS:
    return 0`, which made a blank WebView2 render on a drawing runner look like a documented skip.
    """
    if not backend_ok:
        return "FAIL", "backend-not-proven"
    if surface_proven:
        return "PASS", "cdp-or-gdi"
    if liveness == "ALIVE" and probe_built and not drawable and denied:
        return "NATIVE_SURFACE_UNAVAILABLE", "capability-probe-denies-drawing"
    return "FAIL", "surface-not-proven"


def main() -> int:
    result = {
        "gate": "WINDOWS_TAURI_E2E",
        "started_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "stages": {},
        "verdict": "FAIL",
        "evidencePath": str(RUNS / "u19_webview_readback.json"),
    }
    result["gitHead"] = _git_raw(ROOT, "rev-parse", "HEAD").strip() or "UNKNOWN"
    # Read the environment's capability BEFORE judging the product, and record it: this is the only
    # fact that can excuse an unproven surface later, and an auditor has to see it on the same page.
    capability, capability_source = read_capability_report()
    drawable, capability_basis = drawable_display(capability)
    capability_denied = capability_denies_drawing(capability)
    result["stages"]["capability"] = {
        "status": "READABLE" if capability else "UNAVAILABLE",
        "source": capability_source,
        "verdict": (capability or {}).get("verdict"),
        "layers": {layer.get("layer"): layer.get("verdict")
                   for layer in (capability or {}).get("layers", []) if isinstance(layer, dict)},
        "drawable": drawable, "capabilityDenied": capability_denied,
        "basis": capability_basis,
        # Kept as context only. These flags used to BE the skip test, which is the defect this
        # rewrite closes: on `main` at b218ef82 they turned a blank WebView2 into exit 0.
        "environmentContext": {"GITHUB_ACTIONS": os.environ.get("GITHUB_ACTIONS"),
                               "RUNNER_OS": os.environ.get("RUNNER_OS"),
                               "usedForDecision": False},
    }
    print(f"[U19] desktop capability: drawable={drawable} basis={capability_basis} "
          f"source={capability_source}")
    exe, artifact = resolve_app_exe()
    result["stages"]["artifact"] = artifact
    if exe is None:
        result["stages"]["build"] = {
            "status": "FAIL", "reason": artifact.get("reason")}
        (RUNS / "u19_webview_readback.json").write_text(json.dumps(result, indent=2))
        print(json.dumps(result, indent=2)); return 1
    result["stages"]["build"] = {"status": "PASS",
                                 "exe": artifact["chosen"]["path"],
                                 "sha256": artifact["chosen"]["sha256"]}
    # On the top level too, because the archived-evidence file name is built from it.
    result["exeSha256"] = artifact["chosen"]["sha256"]

    sidecar = port = th = server = None
    app = None
    cdp_port = pick_free_port()
    cdp_obj = None
    try:
        # --- stage 1: real v3 backend ---
        sidecar, port, th, server = start_sidecar()
        base = f"http://127.0.0.1:{port}"
        snap = snapshot_has_data(base)
        result["stages"]["backend"] = {
            "status": "PASS" if snap.get("schemaVersion") else "FAIL",
            "url": base + "/api/v1/snapshot",
            **snap,
        }
        print(f"[U19] backend v3 @ {base} rev={snap.get('revision')} "
              f"projects={snap.get('projectCount')} execs={snap.get('executionCount')}")

        # --- stage 2: launch the real Tauri shell against the real backend ---
        env = dict(os.environ)
        env["WORK_LAB_OBSERVER_API_URL"] = base + "/api/v1/snapshot"
        # U19 CDP probe window: the app builds an extra webview window ONLY when
        # this env var is set (lib.rs, default-off in the shipped binary). The
        # probe window's WebView2 environment carries --remote-debugging-port so
        # this harness can read back the REAL rendered DOM over CDP.
        # (The WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS env var is NOT consumed by
        # wry — wry always passes app-level args — so the port must reach the
        # window through the Rust builder hook, which is what this var drives.)
        env["WORK_LAB_U19_CDP_PORT"] = str(cdp_port)
        # Process-level CDP injection. The probe window's per-window
        # additional_browser_args CANNOT open the debug port: WebView2 creates
        # ONE browser environment per user-data folder, and the main window
        # creates it first, so a later window's args are inert (measured
        # 2026-10-06: probe=ok yet no top-level "u19cdp" window and the port
        # refused connections). This variable is read by the WebView2 loader
        # when it creates that first environment.
        env["WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS"] = (
            f"--remote-debugging-port={cdp_port} --remote-allow-origins=*"
        )
        # U19 next-cycle discriminator: the app writes the probe-window build
        # outcome to this exact path (lib.rs), so the CI log below can tell
        # "window built (R1 headless-visible)" from "build failed" from
        # "probe block never reached" — one grep after the next run.
        env["WORK_LAB_U19_PROBE_STATUS"] = str(RUNS / "u19_probe_status.txt")
        env["NO_AUTO_UPDATE"] = "1"
        # Diagnostics: capture the app's stdout/stderr to disk (before it
        # exits) instead of DEVNULL. A GUI-subsystem binary that early-exits
        # (rc 0xC00000163 class) prints its panic message nowhere — this is
        # the only way to know WHY. The file is appended to the evidence JSON
        # when the verdict is FAIL.
        errlog = RUNS / "u19_app_stderr.log"
        try:
            errlog.write_bytes(b"")
        except OSError:
            pass
        app = subprocess.Popen(
            [str(exe)], cwd=str(OBS / "src-tauri"), env=env,
            stdout=subprocess.DEVNULL, stderr=open(errlog, "wb"),
        )
        result["stages"]["tauri_launch"] = {"pid": app.pid, "status": "RUNNING"}
        print(f"[U19] launched real app.exe pid={app.pid} cdp=: {cdp_port}")
        print(f"[U19] artifact exe={artifact['chosen']['path']} "
              f"sha256={artifact['chosen']['sha256'][:16]} "
              f"mtime={artifact['chosen']['mtime']}")

        # --- stage 3: real WebView readback over CDP ---
        try:
            ws = discover_cdp_ws(cdp_port, tries=90)
            cdp_obj = CDP(ws)
            dom = readback_asserts(cdp_obj)
            png = cdp_obj.screenshot()
            shot = RUNS / "u19_webview.png"
            shot.write_bytes(png)
            real_render = (
                dom.get("rootPopulated") and dom.get("bodyLen", 0) > 40
                and not dom.get("isAboutBlank")
            )
            result["stages"]["webview_readback"] = {
                "status": "PASS" if real_render else "FAIL",
                "cdpTarget": ws,
                "dom": dom,
                "screenshot": str(shot),
                "screenshotBytes": len(png),
            }
            print(f"[U19] webview readback: url={dom.get('url')} "
                  f"rootPopulated={dom.get('rootPopulated')} "
                  f"liveRegion={dom.get('hasLiveRegion')} ({dom.get('liveRegionText')!r})")
        except Exception as e:  # CDP unavailable => cannot PROVE the gate
            result["stages"]["webview_readback"] = {
                "status": "FAIL",
                "reason": "CDP readback unavailable: " + repr(e),
            }
            print("[U19] CDP readback FAILED:", repr(e))
        finally:
            if cdp_obj:
                cdp_obj.close()

        # --- stage 3a: process liveness — was the real app still alive? ---
        # A Tauri/WebView2 early-exit (0xC00000163-class rc) leaves no window
        # AND no CDP target, so both stage 3 and 3b fail for the SAME reason.
        # Detect it explicitly so the evidence names the root cause, not the
        # two downstream symptoms.
        poll_rc = app.poll()
        if poll_rc is None:
            result["stages"]["process_liveness"] = {
                "status": "ALIVE",
                "note": "app.exe still running at readback time",
            }
        else:
            errtail = _stderr_tail(RUNS / "u19_app_stderr.log")
            result["stages"]["process_liveness"] = {
                "status": "EXITED_EARLY",
                "returncode": poll_rc,
                "returncode_hex": "0x%08X" % (poll_rc & 0xFFFFFFFF),
                "appStderrTail": errtail,
            }
            print(f"[U19] app.exe exited early rc={poll_rc} "
                  f"(0x{poll_rc & 0xFFFFFFFF:08X}); stderr tail:")
            print(errtail[-800:] or "(no stderr captured — GUI subsystem "
                  "binary or crashed before first write)")

        # --- stage 3b: GDI real-render proof (architecture-agnostic) ---
        # Even when the CDP subsystem is absent, PrintWindow captures the
        # actual on-screen pixels of the app's real window. A real React
        # dashboard paints many distinct colors; about:blank / an empty
        # shell is a near-solid fill. This is what the release gate keys on.
        time.sleep(1.5)  # let the WebView paint the first frame
        gdi = _gdi_render_proof(app.pid)
        result["stages"]["gdi_render_proof"] = gdi
        print(f"[U19] GDI render proof: {gdi.get('status')} "
              f"(windows={len(gdi.get('windows', []))})")

        # U19 next-cycle discriminator — print to the CI log so the next
        # run's failure is a one-grep diagnosis instead of a rebuild:
        #   probe=ok visible=False  -> headless session has no visible desktop (R1)
        #   probe=ok visible=True    -> GDI filter/capture bug (R4); CDP still
        #                                failing means the page target genuinely
        #                                never attached (renderer not up)
        #   probe=build_failed       -> WebView2 instance creation failed (R3)
        #   (no probe file)          -> probe block never reached (env var not
        #                                read / app built before the hook)
        probe_path = RUNS / "u19_probe_status.txt"
        try:
            probe_status = probe_path.read_text().strip() or "(probe file empty)"
        except OSError:
            probe_status = "(no probe status file — probe block not reached)"
        print(f"[U19] probe window status: {probe_status}")
        allw = gdi.get("diagnostic_all_pid_windows")
        if allw is not None:
            if allw:
                for hwnd, info in allw.items():
                    print(
                        f"[U19] pid window hwnd={hwnd} "
                        f"w={info.get('w')} h={info.get('h')} "
                        f"visible={info.get('visible')}"
                    )
            else:
                print("[U19] pid window enumeration: NO top-level windows for pid")

        # verdict: the release gate keys on REAL rendered proof. CDP DOM
        # readback is the strongest (asserts the actual DOM tree + live
        # region); GDI PrintWindow is the architecture-agnostic fallback.
        # Either proving a non-blank real render is sufficient (fail-closed:
        # if NEITHER proves it, verdict is FAIL — never a fabricated PASS).
        backend_ok = result["stages"].get("backend", {}).get("status") == "PASS"
        cdp_ok = result["stages"].get("webview_readback", {}).get("status") == "PASS"
        gdi_ok = result["stages"].get("gdi_render_proof", {}).get("status") == "PASS"
        liveness = result["stages"].get("process_liveness", {}).get("status")
        # The environment boundary, now decided by the capability probe instead of a machine flag:
        #   probe window BUILT (probe=ok), backend PASS, app ALIVE, yet NEITHER GDI nor CDP proved a
        #   non-blank render, AND the probe says this environment cannot draw. Only that combination is
        #   a skip, and it is recorded as NATIVE_SURFACE_UNAVAILABLE — never as a pass.
        # If the probe says the environment CAN draw (on the GitHub windows-latest runner it does:
        # display PASS 1024x768, draw PASS), an unproven surface is a real failure and exits non-zero.
        probe_built = probe_status.startswith("probe=ok")
        surface_proven = cdp_ok or gdi_ok
        verdict, verdict_basis = native_render_verdict(
            backend_ok=backend_ok, surface_proven=surface_proven, liveness=liveness,
            probe_built=probe_built, drawable=drawable, denied=capability_denied)
        result["verdictBasis"] = verdict_basis
        if verdict == "NATIVE_SURFACE_UNAVAILABLE":
            result["verdict"] = verdict
            result["provenBy"] = "none-capability-probe-denied-drawing"
            result["unverifiedBecause"] = capability_basis
            record = {
                "gate": "WINDOWS_TAURI_E2E",
                "verdict": "NATIVE_SURFACE_UNAVAILABLE",
                "state": "unverified",
                "reason": capability_basis,
                "gitHead": result["gitHead"],
                "recordedAt": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                "exe": artifact["chosen"]["path"],
                "exeSha256": artifact["chosen"]["sha256"],
                "notVerified": ["webview2-cdp-dom-readback", "gdi-printwindow-render-proof"],
                "stages": {
                    "backend": result["stages"].get("backend", {}).get("status"),
                    "tauri_launch": result["stages"].get("tauri_launch", {}).get("status"),
                    "process_liveness": liveness,
                    "probe_window": probe_status,
                    "capability": result["stages"]["capability"],
                },
                "owedTo": "a session whose capability probe reports layers.display=PASS and layers.draw=PASS",
            }
            unverified_path = RUNS / "u19_native_surface_unverified.json"
            unverified_path.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
            result["unverifiedRecord"] = str(unverified_path)
            print(f"NATIVE_SURFACE_UNAVAILABLE reason={capability_basis} "
                  f"record={unverified_path} — the real-WebView layer is unverified, not passed")
        else:
            result["verdict"] = verdict
            result["provenBy"] = ("cdp+gdi" if cdp_ok and gdi_ok else
                                  "cdp" if cdp_ok else
                                  "gdi-printwindow" if gdi_ok else "none")
            if verdict_basis == "surface-not-proven":
                # The old SKIPPED_HEADLESS case, now named as what it is: an environment the probe
                # says can draw produced no proven render surface. That is a product failure.
                result["previouslySkippedAs"] = (
                    "SKIPPED_HEADLESS (exit 0) — the run would have been green; the skip is only "
                    f"permitted when the capability probe denies drawing, and it said: {capability_basis}")
    except Exception as e:
        result["verdict"] = "FAIL"
        result["stages"]["error"] = {"status": "FAIL", "reason": repr(e)}
        print("[U19] FAILED:", repr(e))
    finally:
        if app:
            app.terminate()
            try:
                app.wait(timeout=8)
            except Exception:
                app.kill()
            # Flush the captured app stderr now that the process is gone, so
            # the evidence JSON can read its final contents.
            if app.stderr is not None:
                try:
                    app.stderr.close()
                except Exception:
                    pass
        if cdp_obj:
            cdp_obj.close()
        if sidecar is not None and server is not None:
            server.shutdown()
            server.server_close()
        result["ended_at"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")

    (RUNS / "u19_webview_readback.json").write_text(json.dumps(result, indent=2))
    # Archive the native readback into the evidence root, named by the commit and the binary it just
    # measured. `src-tauri/target/` is a cargo cache and `.project-local/runs/` was never uploaded, so
    # until now the exe receipt and this file were evidence for as long as the runner's cache lived.
    try:
        archived = archive_native_evidence(ROOT, "u19-native-readback", result)
        result["archivedEvidencePath"] = str(archived)
    except SystemExit as exc:
        archived = None
        result["archivedEvidenceError"] = str(exc)
    print("\n[U19] VERDICT:", result["verdict"])
    print(json.dumps({k: v.get("status", v) for k, v in result["stages"].items()}, indent=2))
    print("evidence:", result["evidencePath"])
    if archived is not None:
        print("archived evidence:", str(archived))
    if result["verdict"] == "NATIVE_SURFACE_UNAVAILABLE":
        # Not a PASS: the real-WebView layer stayed unverified, and the record says which capability
        # layer denied drawing. Exit 0 because the product was not shown to be broken and the
        # environment was proven unable to show it.
        print(f"[U19] exit 0 (NATIVE_SURFACE_UNAVAILABLE reason={result['unverifiedBecause']})")
        return 0
    return 0 if result["verdict"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
