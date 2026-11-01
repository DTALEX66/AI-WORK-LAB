"""Launch the real Observer against the real sidecar and capture its CLIENT area.

Why this exists next to shot2.py: every viewport-width conclusion drawn from that
script was suspicious, because a capture taken by a DPI-unwinnaware process is
resampled by the DWM. This instrument measures its own coordinate space instead
of assuming one, refuses to report layout when the measurements disagree, and
writes a magnified crop of the top-right corner so the window-control cluster can
be judged by looking at pixels rather than by inference.
"""
import array
import ctypes
import ctypes.wintypes as wt
import hashlib
import json
import os
import struct
import subprocess
import sys
import threading
import time
import urllib.request
import zlib
from pathlib import Path

ROOT = Path(r"D:\All projects\WORK-LAB")
OUT = ROOT / ".project-local/runs/p0a-diag-20261006"
OUT.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(ROOT / "packages/client-neutral-core/scripts"))

user32 = ctypes.WinDLL("user32", use_last_error=True)
gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)
dwmapi = ctypes.WinDLL("dwmapi")
try:
    shcore = ctypes.WinDLL("shcore")
except OSError:
    shcore = None

SRCCOPY = 0x00CC0020
DWMWA_EXTENDED_FRAME_BOUNDS = 9
AWARENESS = {0: "DPI_UNAWARE", 1: "SYSTEM_AWARE", 2: "PER_MONITOR_AWARE",
             3: "PER_MONITOR_AWARE_V2"}


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [("biSize", wt.DWORD), ("biWidth", ctypes.c_long),
                ("biHeight", ctypes.c_long), ("biPlanes", wt.WORD),
                ("biBitCount", wt.WORD), ("biCompression", wt.DWORD),
                ("biSizeImage", wt.DWORD), ("biXPelsPerMeter", ctypes.c_long),
                ("biYPelsPerMeter", ctypes.c_long), ("biClrUsed", wt.DWORD),
                ("biClrImportant", wt.DWORD)]


user32.GetWindowThreadProcessId.argtypes = [wt.HWND, ctypes.POINTER(wt.DWORD)]
user32.GetWindowRect.argtypes = [wt.HWND, ctypes.POINTER(wt.RECT)]
user32.GetClientRect.argtypes = [wt.HWND, ctypes.POINTER(wt.RECT)]
user32.GetClientRect.restype = ctypes.c_bool
user32.ClientToScreen.argtypes = [wt.HWND, ctypes.POINTER(wt.POINT)]
user32.ClientToScreen.restype = ctypes.c_bool
user32.SetWindowPos.argtypes = [wt.HWND, wt.HWND, ctypes.c_int, ctypes.c_int,
                                ctypes.c_int, ctypes.c_int, wt.UINT]
user32.IsWindowVisible.argtypes = [wt.HWND]
user32.GetWindowTextLengthW.restype = ctypes.c_int
user32.GetWindowTextW.restype = ctypes.c_int
user32.GetDpiForWindow.argtypes = [wt.HWND]
user32.GetDpiForWindow.restype = ctypes.c_uint
user32.GetDpiForWindow.errcheck = lambda r, f, a: r or (_raise("GetDpiForWindow"))
user32.GetDC.restype = wt.HDC
user32.ReleaseDC.argtypes = [wt.HWND, wt.HDC]
user32.SystemParametersInfoW.argtypes = [wt.UINT, wt.UINT, ctypes.c_void_p, wt.UINT]
gdi32.CreateCompatibleDC.argtypes = [wt.HDC]
gdi32.CreateCompatibleDC.restype = wt.HDC
gdi32.CreateCompatibleBitmap.argtypes = [wt.HDC, ctypes.c_int, ctypes.c_int]
gdi32.CreateCompatibleBitmap.restype = wt.HBITMAP
gdi32.GetDIBits.argtypes = [wt.HDC, wt.HBITMAP, wt.UINT, wt.UINT, ctypes.c_void_p,
                            ctypes.POINTER(BITMAPINFOHEADER), wt.UINT]
gdi32.SelectObject.argtypes = [wt.HDC, wt.HGDIOBJ]
gdi32.SelectObject.restype = wt.HGDIOBJ
gdi32.BitBlt.argtypes = [wt.HDC, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                         wt.HDC, ctypes.c_int, ctypes.c_int, wt.DWORD]
gdi32.BitBlt.restype = ctypes.c_bool
gdi32.DeleteObject.argtypes = [wt.HANDLE]
gdi32.DeleteDC.argtypes = [wt.HDC]
dwmapi.DwmGetWindowAttribute.argtypes = [wt.HWND, wt.DWORD, ctypes.c_void_p, wt.DWORD]
dwmapi.DwmGetWindowAttribute.restype = ctypes.c_long


def _raise(what):
    raise ctypes.WinError(ctypes.get_last_error())


def process_awareness():
    if shcore is None:
        return "shcore_missing"
    val = wt.DWORD()
    if shcore.GetProcessDpiAwareness(None, ctypes.byref(val)) != 0:
        return "query_failed"
    return AWARENESS.get(val.value, "unknown(%d)" % val.value)


def make_process_dpi_aware():
    """Ask the OS for the physical-pixel coordinate space; report whether it took."""
    before = process_awareness()
    ok = None
    if hasattr(user32, "SetProcessDpiAwarenessContext"):
        user32.SetProcessDpiAwarenessContext.argtypes = [ctypes.c_void_p]
        user32.SetProcessDpiAwarenessContext.restype = ctypes.c_bool
        ok = bool(user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4)))
    after = process_awareness()
    return {"before": before, "contextCallReturned": ok, "after": after,
            "physicalCoordinates": after in ("PER_MONITOR_AWARE", "PER_MONITOR_AWARE_V2")}


def windows_of(pid):
    found = []

    def cb(hwnd, _):
        p = wt.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(p))
        if p.value != pid or not user32.IsWindowVisible(hwnd):
            return True
        r = wt.RECT()
        user32.GetWindowRect(hwnd, ctypes.byref(r))
        n = user32.GetWindowTextLengthW(hwnd)
        buf = ctypes.create_unicode_buffer(max(n + 1, 1))
        user32.GetWindowTextW(hwnd, buf, n + 1)
        if (r.right - r.left) >= 400 and (r.bottom - r.top) >= 300:
            found.append({"hwnd": hwnd, "title": buf.value,
                          "rect": [r.left, r.top, r.right, r.bottom]})
        return True

    user32.EnumWindows(ctypes.WINFUNCTYPE(ctypes.c_int, wt.HWND, wt.LPARAM)(cb), 0)
    return found


def geometry(hwnd):
    win = wt.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(win))
    client = wt.RECT()
    if not user32.GetClientRect(hwnd, ctypes.byref(client)):
        raise ctypes.WinError(ctypes.get_last_error())
    tl = wt.POINT(0, 0)
    br = wt.POINT(client.right, client.bottom)
    if not user32.ClientToScreen(hwnd, ctypes.byref(tl)):
        raise ctypes.WinError(ctypes.get_last_error())
    if not user32.ClientToScreen(hwnd, ctypes.byref(br)):
        raise ctypes.WinError(ctypes.get_last_error())
    frame = wt.RECT()
    dwm = dwmapi.DwmGetWindowAttribute(hwnd, DWMWA_EXTENDED_FRAME_BOUNDS,
                                       ctypes.byref(frame), ctypes.sizeof(frame))
    dpi = user32.GetDpiForWindow(hwnd)
    return {
        "windowRect": [win.left, win.top, win.right, win.bottom],
        "clientLogical": [client.right - client.left, client.bottom - client.top],
        "clientOnScreen": [tl.x, tl.y, br.x, br.y],
        "clientPhysical": [br.x - tl.x, br.y - tl.y],
        "dwmFrameBounds": [frame.left, frame.top, frame.right, frame.bottom] if dwm == 0 else None,
        "dwmQuery": dwm,
        "dpi": dpi,
        "scalePercent": round(dpi / 96 * 100),
        "cssViewport": [round((br.x - tl.x) * 96 / dpi), round((br.y - tl.y) * 96 / dpi)],
    }


def png(path, w, h, rgba):
    rows = [b"\x00" + rgba[i * w * 4:(i + 1) * w * 4] for i in range(h)]

    def chunk(tag, payload):
        body = tag + payload
        return (struct.pack(">I", len(payload)) + body
                + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF))
    path.write_bytes(b"\x89PNG\r\n\x1a\n"
                     + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0))
                     + chunk(b"IDAT", zlib.compress(b"".join(rows), 6))
                     + chunk(b"IEND", b""))


def capture(mode, hwnd, x, y, w, h):
    sdc = user32.GetDC(0)
    hdc = gdi32.CreateCompatibleDC(sdc)
    hb = gdi32.CreateCompatibleBitmap(sdc, w, h)
    gdi32.SelectObject(hdc, hb)
    if mode == "bitblt":
        if not gdi32.BitBlt(hdc, 0, 0, w, h, sdc, x, y, SRCCOPY):
            raise ctypes.WinError(ctypes.get_last_error())
    else:
        # PW_CLIENTONLY | PW_RENDERFULLCONTENT: ask the window to paint itself, so a
        # File Explorer or terminal that happens to sit on top of it cannot be
        # photographed and reported as the app. A screen BitBlt cannot tell those
        # two apart, and the earlier "the control cluster never renders" reading was
        # taken exactly that way.
        user32.PrintWindow.argtypes = [wt.HWND, wt.HDC, wt.UINT]
        user32.PrintWindow.restype = ctypes.c_bool
        if not user32.PrintWindow(hwnd, hdc, 0x1 | 0x2):
            raise ctypes.WinError(ctypes.get_last_error())
    bi = BITMAPINFOHEADER(biSize=ctypes.sizeof(BITMAPINFOHEADER), biWidth=w,
                          biHeight=-h, biPlanes=1, biBitCount=32, biCompression=0)
    buf = (ctypes.c_char * (w * h * 4))()
    if not gdi32.GetDIBits(hdc, hb, 0, h, buf, ctypes.byref(bi), 0):
        raise ctypes.WinError(ctypes.get_last_error())
    raw = bytes(buf)
    a = array.array("B", raw)
    out = bytearray(len(raw))
    out[0::4] = a[2::4].tobytes()   # GDI hands back BGRA; PNG wants RGBA.
    out[1::4] = a[1::4].tobytes()
    out[2::4] = a[0::4].tobytes()
    out[3::4] = a[3::4].tobytes()
    gdi32.DeleteObject(hb)
    gdi32.DeleteDC(hdc)
    user32.ReleaseDC(0, sdc)
    return w, h, bytes(out)


def diff_ratio(rgba_a, rgba_b, stride=4 * 7):
    """Fraction of sampled pixels that differ by more than a JPEG-ish noise band."""
    if len(rgba_a) != len(rgba_b):
        return None
    n = total = 0
    for i in range(0, min(len(rgba_a), len(rgba_b)), stride):
        total += 1
        if max(abs(rgba_a[i] - rgba_b[i]), abs(rgba_a[i + 1] - rgba_b[i + 1]),
               abs(rgba_a[i + 2] - rgba_b[i + 2])) > 24:
            n += 1
    return round(n / total, 4) if total else None


def crop_rgba(full_w, full_h, rgba, x0, y0, cw, ch, zoom):
    """Nearest-neighbour zoom of a sub-rect, indexed with the full-image stride."""
    cw = max(1, min(cw, full_w - x0))
    ch = max(1, min(ch, full_h - y0))
    ow, oh = cw * zoom, ch * zoom
    out = bytearray(ow * oh * 4)
    for oy in range(oh):
        sy = y0 + oy // zoom
        if sy >= full_h:
            sy = full_h - 1
        for ox in range(ow):
            sx = x0 + ox // zoom
            if sx >= full_w:
                sx = full_w - 1
            i = (sy * full_w + sx) * 4
            j = (oy * ow + ox) * 4
            out[j:j + 4] = rgba[i:i + 4]
    return ow, oh, bytes(out)


def resolve_artifact():
    """Pick the binary the build actually produced, and prove it is not stale.

    `cargo tauri build` with CARGO_TARGET_DIR set writes the exe under the runs
    target dir, while an older build left one at src-tauri/target/release. Launching
    whichever path is hardcoded captures a superseded binary and reports its
    behaviour as current - which is exactly how a rebuild appeared to change nothing.
    """
    candidates = [ROOT / "apps/observer/src-tauri/target/release/app.exe",
                  ROOT / ".project-local/runs/u19-msvc-20261006/target/release/app.exe"]
    inputs = [ROOT / "apps/observer/src-tauri/tauri.conf.json",
              ROOT / "apps/observer/src-tauri/Cargo.toml"]
    inputs += list((ROOT / "apps/observer/src-tauri/src").glob("*.rs"))
    inputs += list((ROOT / "apps/observer/frontend/dist").rglob("*"))
    inputs = [p for p in inputs if p.is_file()]
    newest_input = max(inputs, key=lambda p: p.stat().st_mtime)
    newest_mtime = max(p.stat().st_mtime for p in inputs)
    report = []
    for c in candidates:
        if not c.exists():
            report.append({"path": str(c), "exists": False})
            continue
        st = c.stat()
        report.append({"path": str(c), "bytes": st.st_size,
                       "mtime": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(st.st_mtime)),
                       "sha256": hashlib.sha256(c.read_bytes()).hexdigest(),
                       "newerThanAllInputs": st.st_mtime >= newest_mtime})
    usable = [c for c in candidates if c.exists() and c.stat().st_mtime >= newest_mtime]
    return (max(usable, key=lambda p: p.stat().st_mtime) if usable else None), {
        "candidates": report,
        "newestInput": {"path": str(newest_input),
                        "mtime": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(newest_mtime))},
        "chosen": None,
    }


def main():
    result = {"instrument": "shot3"}
    result["dpiContext"] = make_process_dpi_aware()

    # Park the pointer in a corner no control can be under BEFORE the app starts.
    # WebView2 keeps a stale :hover once the cursor leaves without a message reaching
    # the webview, and a hover-revealed tooltip then appears in the capture as if the
    # UI showed it permanently.
    user32.SetCursorPos.argtypes = [ctypes.c_int, ctypes.c_int]
    user32.SetCursorPos.restype = ctypes.c_bool
    user32.GetCursorPos.argtypes = [ctypes.POINTER(wt.POINT)]
    user32.GetCursorPos.restype = ctypes.c_bool
    cursor = wt.POINT()
    user32.GetCursorPos(ctypes.byref(cursor))
    result["cursorParkedFrom"] = [cursor.x, cursor.y]
    work_area = wt.RECT()
    user32.SystemParametersInfoW(0x30, 0, ctypes.byref(work_area), 0)
    user32.SetCursorPos(work_area.right - 10, work_area.bottom - 10)

    sys.path.insert(0, str(ROOT / "services/orchestration"))
    from sidecar import WorkflowSidecar, create_server
    runtime = OUT / "sidecar_runtime"
    runtime.mkdir(parents=True, exist_ok=True)
    server = create_server(WorkflowSidecar(ROOT, runtime), "127.0.0.1", 0)
    base = "http://127.0.0.1:%d" % server.server_port
    threading.Thread(target=server.serve_forever, daemon=True).start()
    result["backend"] = {"url": base}

    exe, artifact = resolve_artifact()
    if exe is None:
        result["artifact"] = artifact
        result["verdict"] = "STALE_OR_MISSING_BINARY"
        return result
    st = exe.stat()
    artifact["chosen"] = {"path": str(exe), "bytes": st.st_size,
                          "mtime": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(st.st_mtime)),
                          "sha256": hashlib.sha256(exe.read_bytes()).hexdigest()}
    result["artifact"] = artifact
    env = dict(os.environ)
    env["WORK_LAB_OBSERVER_API_URL"] = base + "/api/v1/snapshot"
    app = subprocess.Popen([str(exe)], cwd=str(exe.parent), env=env,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    result["pid"] = app.pid
    hits = []
    try:
        for _ in range(40):
            time.sleep(0.5)
            hits = windows_of(app.pid)
            if hits:
                break
        result["windowCount"] = len(hits)
        result["windows"] = [{k: v for k, v in h.items() if k != "hwnd"} for h in hits]
        if not hits:
            result["verdict"] = "NO_WINDOW"
            return result

        target = hits[0]
        hwnd = target["hwnd"]
        result["screenWorkArea"] = [work_area.left, work_area.top,
                                    work_area.right, work_area.bottom]
        # SWP_NOSIZE: only bring it topmost and put it fully on-screen. Tauri declares
        # window width/height in LOGICAL pixels, so a 1280-wide window is 1600 physical
        # px at 125% scaling. Forcing a physical 1200x800 here instead shrank the real
        # CSS viewport to 946x632 and made the layout being judged a different layout.
        SWP_NOSIZE = 0x1
        user32.SetWindowPos(hwnd, wt.HWND(-1), 20, 20, 0, 0, SWP_NOSIZE | 0x40)
        time.sleep(4.0)
        geo = geometry(hwnd)
        geo["naturalSizeRequested"] = "SWP_NOSIZE (app's own 1280x820 logical)"
        result["geometry"] = geo

        x, y, _, _ = geo["clientOnScreen"]
        cw, ch = geo["clientPhysical"]
        # Instrument self-proof: a virtualized coordinate space makes the client
        # rect and the DWM frame disagree, and then no layout reading is trustworthy.
        dwm = geo["dwmFrameBounds"]
        dwm_size = [dwm[2] - dwm[0], dwm[3] - dwm[1]] if dwm else None
        disagreements = []
        if dwm_size and abs(dwm_size[0] - cw) > 3:
            disagreements.append("clientPhysical=%dx%d vs dwmFrame=%dx%d"
                                 % (cw, ch, dwm_size[0], dwm_size[1]))
        if cw <= 0 or ch <= 0:
            disagreements.append("non-positive client size")
        if not result["dpiContext"]["physicalCoordinates"]:
            disagreements.append("capture process is not DPI aware: %s"
                                 % result["dpiContext"]["after"])
        if (geo["clientOnScreen"][2] > result["screenWorkArea"][2]
                or geo["clientOnScreen"][3] > result["screenWorkArea"][3]):
            disagreements.append("client area extends past the work area: %s vs %s"
                                 % (geo["clientOnScreen"], result["screenWorkArea"]))
        result["instrumentDisagreements"] = disagreements

        ow, oh, rgba_screen = capture("bitblt", hwnd, x, y, cw, ch)
        ow, oh, rgba_print = capture("printwindow", hwnd, x, y, cw, ch)
        # Cross-check the two independent paths. Where they disagree the screen BitBlt
        # has an occluder in it, and only the PrintWindow pixels describe the app.
        occluded = diff_ratio(rgba_screen, rgba_print)
        brightest = max(max(rgba_print[0::4]), max(rgba_print[1::4]), max(rgba_print[2::4]))
        result["captureCrossCheck"] = {
            "differingPixelRatio": occluded,
            "authoritative": "printwindow" if occluded and occluded > 0.02 else "both-agree",
            "printWindowBrightestChannel": brightest,
            "printWindowPaintedBlack": brightest < 8,
        }
        if result["captureCrossCheck"]["printWindowPaintedBlack"]:
            rgba = rgba_screen
        else:
            rgba = rgba_print if (occluded or 0) > 0.02 else rgba_screen

        for tag in ("screen", "print"):
            src = rgba_screen if tag == "screen" else rgba_print
            p = OUT / ("observer-%s.png" % tag)
            png(p, ow, oh, src)
            result[tag] = {"path": str(p), "w": ow, "h": oh,
                           "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}
        full = OUT / "observer-authoritative.png"
        png(full, ow, oh, rgba)
        result["full"] = {"path": str(full), "w": ow, "h": oh,
                          "bytes": full.stat().st_size,
                          "sha256": hashlib.sha256(full.read_bytes()).hexdigest()}

        # Clipping signature: content ink present in the final columns of the client
        # area means something is being cut off by the window edge rather than wrapped.
        bg = (8, 9, 10)  # configured backgroundColor #08090a

        def ink(px, py):
            i = (py * ow + px) * 4
            return max(abs(rgba[i] - bg[0]), abs(rgba[i + 1] - bg[1]),
                       abs(rgba[i + 2] - bg[2])) > 24

        edge_rows = [r for r in range(oh)
                     if any(ink(ow - k, r) for k in range(1, 4))]
        runs = []
        for r in edge_rows:
            if runs and r - runs[-1][1] <= 3:
                runs[-1][1] = r
            else:
                runs.append([r, r])
        result["rightEdgeInk"] = {"rows": len(edge_rows),
                                  "bands": [[a, b] for a, b in runs if b - a >= 2],
                                  "cssBands": [[round(a * 96 / geo["dpi"]), round(b * 96 / geo["dpi"])]
                                               for a, b in runs if b - a >= 2]}
        result["centrePixel"] = list(rgba[(ow // 2) * 4 + (oh // 2) * ow * 4:
                                          (ow // 2) * 4 + (oh // 2) * ow * 4 + 3])

        # Top-right band where a frameless caption cluster must live: 300x70 CSS px
        # converted to physical pixels with the measured window DPI.
        band_w = min(ow, max(64, round(300 * geo["dpi"] / 96)))
        band_h = min(oh, max(48, round(70 * geo["dpi"] / 96)))
        bx, by = ow - band_w, 0
        zw, zh, zrgba = crop_rgba(ow, oh, rgba, bx, by, band_w, band_h, 3)
        crop = OUT / "observer-topright-3x.png"
        png(crop, zw, zh, zrgba)
        nonbg = sum(1 for i in range(0, len(zrgba), 12)
                    if max(abs(zrgba[i] - bg[0]), abs(zrgba[i + 1] - bg[1]),
                           abs(zrgba[i + 2] - bg[2])) > 24)
        samples = len(range(0, len(zrgba), 12))
        result["topRightBand"] = {"cssWidthUsed": band_w, "path": str(crop),
                                  "w": zw, "h": zh, "sha256": hashlib.sha256(crop.read_bytes()).hexdigest(),
                                  "nonBackgroundRatio": round(nonbg / samples, 4),
                                  "distinctColors": len({zrgba[i:i + 3] for i in range(0, len(zrgba), 12)})}
        all_ink = sum(1 for i in range(0, len(rgba), 4 * 37)
                      if max(abs(rgba[i] - bg[0]), abs(rgba[i + 1] - bg[1]),
                             abs(rgba[i + 2] - bg[2])) > 24)
        result["verdict"] = ("INSTRUMENT_INVALID" if disagreements else "CAPTURED")
        result["blankCapture"] = all_ink == 0
        return result
    finally:
        parked = result.get("cursorParkedFrom")
        if parked:
            user32.SetCursorPos(parked[0], parked[1])
        app.terminate()
        try:
            app.wait(timeout=8)
        except Exception:
            app.kill()
        server.shutdown()
        server.server_close()


if __name__ == "__main__":
    out = main()
    (OUT / "capture-provenance.json").write_text(json.dumps(out, ensure_ascii=False, indent=2))
    print(json.dumps(out, ensure_ascii=False, indent=2))
    sys.exit(0 if out.get("verdict") == "CAPTURED" else 1)
