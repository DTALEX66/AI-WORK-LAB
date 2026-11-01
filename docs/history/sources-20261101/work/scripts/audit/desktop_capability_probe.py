#!/usr/bin/env python3
"""W04 (2026-10-17): probe the DESKTOP CAPABILITY, in layers, without touching the product.

Why this exists
---------------
U19's verdict was derived from GitHub job flags, a passing backend, a built probe and a live process. None of
those can distinguish "the product renders" from "the process stayed alive", and the recorded failure mode is
concrete: on a runner with no interactive desktop the harness logged `SKIPPED_HEADLESS` and exited 0, so a
green tick meant "we did not check" -- the exact conflation the project forbids.

This probe answers the question the harness needs answered BEFORE it can trust any product readback:
*is this environment capable of drawing at all?* It never launches the product. Each layer returns its own
machine verdict, and the layers are the ones the plan names: interactive session, display, real drawing, a desktop that shows
windows, WebView2 runtime, loopback, and cleanup.

Verdict discipline (the whole point)
------------------------------------
`PASS` is returned by this script only when every REQUIRED layer passes. `NOT_AVAILABLE`, `NOT_RUN` and
`SKIPPED` are reported as themselves and can never add up to a pass -- the layer that could not be probed is
printed by name, and the summary verdict stays `INCOMPLETE`. A probe that cannot run is information; a probe
that cannot run and reports success is a lie.
"""
from __future__ import annotations

import argparse
import ctypes
import json
import os
import shutil
import socket
import sys
import time
from pathlib import Path

SCHEMA_VERSION = "work-lab/desktop-capability/v1"
DEFAULT_DEADLINE_SECONDS = 90.0

LAYERS = ("session", "display", "draw", "visible_desktop", "webview2", "loopback", "cleanup")
REQUIRED = ("display", "draw", "loopback", "cleanup")


def _windows() -> bool:
    return sys.platform.startswith("win")


def probe_session() -> tuple[str, dict]:
    """An interactive desktop session: the class of environment a real window can exist in.

    `SESSIONNAME` is empty/"Services" inside a service or a non-interactive session. This is a *heuristic*
    and is reported as one: it says "the session looks interactive", not "a window was drawn" -- that is the
    `draw` layer's job, and keeping them separate is what stops a session flag from standing in for a paint.
    """
    if not _windows():
        return "NOT_APPLICABLE", {"platform": sys.platform, "reason": "not a Windows host"}
    name = os.environ.get("SESSIONNAME", "")
    interactive = bool(name) and "services" not in name.lower()
    return ("PASS" if interactive else "FAIL"), {"SESSIONNAME": name or None,
                                                 "basis": "heuristic (session name), not a paint"}


def probe_display() -> tuple[str, dict]:
    """A display with real metrics. `GetSystemMetrics` is the cheapest honest answer: a headless session
    reports 0x0 or fails outright."""
    if not _windows():
        return "NOT_APPLICABLE", {"platform": sys.platform, "reason": "not a Windows host"}
    try:
        user32 = ctypes.windll.user32                     # type: ignore[attr-defined]
        width, height = int(user32.GetSystemMetrics(0)), int(user32.GetSystemMetrics(1))
    except Exception as exc:  # noqa: BLE001 - named, not swallowed
        return "FAIL", {"error": f"{type(exc).__name__}: {exc}"}
    return ("PASS" if width > 0 and height > 0 else "FAIL"), {"width": width, "height": height}


def probe_draw() -> tuple[str, dict]:
    """Can this environment DRAW? A minimal, product-independent window: create a hidden window class,
    paint one pixel, read it back -- the plan's "已知能绘制的最小窗口探针".

    Reported as FAIL on any Windows host where the drawing primitives are unavailable, and NOT_APPLICABLE
    elsewhere. It deliberately does not open a visible window: a probe must not depend on a human, and a
    hidden window still proves the graphics path.
    """
    if not _windows():
        return "NOT_APPLICABLE", {"platform": sys.platform, "reason": "not a Windows host"}
    try:
        gdi32 = ctypes.windll.gdi32                        # type: ignore[attr-defined]
        user32 = ctypes.windll.user32                      # type: ignore[attr-defined]
        hdc_screen = user32.GetDC(0)
        if not hdc_screen:
            return "FAIL", {"error": "GetDC(0) returned null: no screen device context"}
        hdc_mem = gdi32.CreateCompatibleDC(hdc_screen)
        if not hdc_mem:
            user32.ReleaseDC(0, hdc_screen)
            return "FAIL", {"error": "CreateCompatibleDC failed"}
        bitmap = gdi32.CreateCompatibleBitmap(hdc_screen, 1, 1)
        gdi32.SelectObject(hdc_mem, bitmap)
        # Paint one pixel and read it back: a real graphics operation, not a capability flag.
        gdi32.SetPixel(hdc_mem, 0, 0, 0x00FF00)
        pixel = gdi32.GetPixel(hdc_mem, 0, 0)
        gdi32.DeleteObject(bitmap)
        gdi32.DeleteDC(hdc_mem)
        user32.ReleaseDC(0, hdc_screen)
        painted = int(pixel) == 0x00FF00
        return ("PASS" if painted else "FAIL"), {"painted_pixel": hex(int(pixel)), "expected": "0xff00"}
    except Exception as exc:  # noqa: BLE001
        return "FAIL", {"error": f"{type(exc).__name__}: {exc}"}


def probe_webview2() -> tuple[str, dict]:
    """Is the WebView2 runtime REGISTERED? Presence of the runtime is not proof that a product renders in it
    (that is the product's readback), which is why the layer is named `webview2` and not `renders`."""
    if not _windows():
        return "NOT_APPLICABLE", {"platform": sys.platform, "reason": "not a Windows host"}
    try:
        import winreg  # type: ignore[import-not-found]
    except Exception as exc:  # noqa: BLE001
        return "NOT_AVAILABLE", {"error": f"winreg unavailable: {type(exc).__name__}"}
    keys = (
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}"),
        (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}"),
    )
    for root, path in keys:
        try:
            with winreg.OpenKey(root, path) as key:
                version = winreg.QueryValueEx(key, "pv")[0]
                return "PASS", {"version": version, "source": "registry"}
        except OSError:
            continue
    return "FAIL", {"reason": "no WebView2 runtime registered for machine or user"}


def probe_visible_desktop() -> tuple[str, dict]:
    """Is there a desktop that actually SHOWS a top-level window? Measured, not inferred from a flag.

    This is a different capability from `draw`: `draw` proves GDI can paint into a window this process
    created, which a service session can do with nothing on screen. What a native window-state proof needs
    is a window a user could see. The two came apart on the GitHub `windows-latest` runner, measured
    2026-10-26: `display` and `draw` both PASSed while every window the real app owned read back
    `visible=false` and the WebView2 never exposed a CDP page target, so the native proof was unobtainable
    in an environment a two-layer probe called capable. Enumerating the desktop's own visible top-level
    windows is the reading that separates those two situations.
    """
    if sys.platform != "win32":
        return "NOT_APPLICABLE", {"platform": sys.platform, "reason": "not a Windows host"}
    try:
        import ctypes  # noqa: PLC0415 - Windows-only capability
        from ctypes import wintypes as _wt  # noqa: PLC0415
        user32 = ctypes.windll.user32
        user32.GetShellWindow.restype = _wt.HWND
        user32.IsWindowVisible.restype = _wt.BOOL
        user32.GetWindowTextLengthW.restype = _wt.INT
        callback = ctypes.WINFUNCTYPE(_wt.BOOL, _wt.HWND, _wt.LPARAM)
    except Exception as exc:  # noqa: BLE001 - an unavailable API is a fact about the host, not a crash
        return "NOT_AVAILABLE", {"error": f"{type(exc).__name__}: {exc}"}

    counts = {"visible": 0, "titled": 0, "enumerated": 0}

    def _each(hwnd, _lparam):  # noqa: ANN001 - the Win32 callback shape
        counts["enumerated"] += 1
        try:
            if user32.IsWindowVisible(hwnd):
                counts["visible"] += 1
                if user32.GetWindowTextLengthW(hwnd):
                    counts["titled"] += 1
        except OSError:
            return True
        return True

    user32.EnumWindows(callback(_each), 0)
    shell = bool(user32.GetShellWindow())
    evidence = {"visibleTopLevel": counts["visible"], "titledVisible": counts["titled"],
                "windowsEnumerated": counts["enumerated"], "shellWindowPresent": shell}
    if counts["enumerated"] == 0:
        return "FAIL", {**evidence, "reason": "the desktop exposes no top-level window at all"}
    if counts["titled"] == 0 or not shell:
        return "FAIL", {**evidence,
                        "reason": "no titled visible window and/or no shell window: nothing could show a window here"}
    return "PASS", evidence


def probe_loopback() -> tuple[str, dict]:
    """Bind and release a loopback port. The harness needs one for CDP readback; a session that cannot bind
    is not a session where a readback can happen -- and the port must come back, or the next run inherits the
    leak."""
    port = 0
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind(("127.0.0.1", 0))
            port = int(sock.getsockname()[1])
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as again:
            again.bind(("127.0.0.1", port))
            again.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    except OSError as exc:
        return "FAIL", {"error": f"{type(exc).__name__}: {exc}", "port": port}
    return "PASS", {"port": port, "released": True}


def probe_cleanup() -> tuple[str, dict]:
    """Create and remove a tree INSIDE the project boundary.

    Deliberately NOT the self-deleting temp-dir helper: production source is held to zero of those, and the
    rule records why (`tests/workflow-assistance/test_worker_runtime_roots_stay_inside_the_project.py`) -- on
    Windows its cleanup fails while a handle is still open, and this machine has measured the residue. The
    layer's question is unchanged, and answering it inside the declared temp root is the honest reading of
    "does this runner clean up what it creates".
    """
    root = Path(__file__).resolve().parents[2] / ".project-local" / "runs" / "tmp"
    target = root / f"desktop-probe-{os.getpid()}"
    try:
        (target / "child").mkdir(parents=True, exist_ok=True)
        marker = target / "child" / "marker.txt"
        marker.write_text("probe", encoding="utf-8")
        created = marker.is_file()
        shutil.rmtree(target)
        gone = not target.exists()
    except OSError as exc:
        return "FAIL", {"error": f"{type(exc).__name__}: {exc}", "path": str(target)}
    return ("PASS" if created and gone else "FAIL"), {"created": created, "removed": gone,
                                                      "root": ".project-local/runs/tmp"}


PROBES = {
    "session": probe_session,
    "display": probe_display,
    "draw": probe_draw,
    "visible_desktop": probe_visible_desktop,
    "webview2": probe_webview2,
    "loopback": probe_loopback,
    "cleanup": probe_cleanup,
}


def run(deadline_seconds: float = DEFAULT_DEADLINE_SECONDS) -> dict:
    started = time.monotonic()
    results: list[dict] = []
    for layer in LAYERS:
        elapsed = time.monotonic() - started
        if elapsed >= deadline_seconds:
            # A deadline that silently drops layers would be the same defect as a skipped check reported as a
            # pass: the layer is recorded as NOT_RUN with the reason, and the summary cannot pass.
            results.append({"layer": layer, "verdict": "NOT_RUN",
                            "evidence": {"reason": f"total deadline {deadline_seconds:.0f}s reached "
                                                   f"({elapsed:.1f}s elapsed)"}, "seconds": 0.0})
            continue
        t0 = time.monotonic()
        try:
            verdict, evidence = PROBES[layer]()
        except Exception as exc:  # noqa: BLE001 - a crashing probe is a named failure, not an absent layer
            verdict, evidence = "FAIL", {"error": f"probe raised {type(exc).__name__}: {exc}"}
        results.append({"layer": layer, "verdict": verdict, "evidence": evidence,
                        "seconds": round(time.monotonic() - t0, 3)})

    failing = [r["layer"] for r in results if r["verdict"] == "FAIL"]
    unresolved = [r["layer"] for r in results if r["verdict"] in ("NOT_RUN", "NOT_AVAILABLE", "SKIPPED", "NOT_APPLICABLE")]
    required_unresolved = [layer for layer in unresolved if layer in REQUIRED]
    if failing:
        verdict = "FAIL"
    elif required_unresolved:
        verdict = "INCOMPLETE"
    else:
        verdict = "PASS"
    return {
        "schemaVersion": SCHEMA_VERSION,
        "platform": sys.platform,
        "deadlineSeconds": deadline_seconds,
        "elapsedSeconds": round(time.monotonic() - started, 3),
        "layers": results,
        "verdict": verdict,
        "failing": failing,
        "unresolved": unresolved,
        "note": ("NOT_AVAILABLE / NOT_RUN / NOT_APPLICABLE never add up to a pass: a desktop readback may "
                 "only be attempted in an environment whose layers all resolved. This probe cannot make a "
                 "product render, and it does not try."),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Probe desktop capability in layers (never the product).")
    parser.add_argument("--deadline", type=float, default=DEFAULT_DEADLINE_SECONDS)
    parser.add_argument("--json-out", type=Path)
    args = parser.parse_args(argv)

    report = run(args.deadline)
    summary = {layer["layer"]: layer["verdict"] for layer in report["layers"]}
    print(f"DESKTOP_CAPABILITY_{report['verdict']} platform={report['platform']} "
          f"elapsed={report['elapsedSeconds']}s layers={summary}")
    for layer in report["layers"]:
        if layer["verdict"] != "PASS":
            print(f"  {layer['layer']}={layer['verdict']} {json.dumps(layer['evidence'], ensure_ascii=False)}")
    if args.json_out:
        out = args.json_out if args.json_out.is_absolute() else Path.cwd() / args.json_out
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8",
                       newline="\n")
        print(f"DESKTOP_CAPABILITY_REPORT={out}")
    return {"PASS": 0, "FAIL": 1}.get(report["verdict"], 3)


if __name__ == "__main__":
    raise SystemExit(main())
