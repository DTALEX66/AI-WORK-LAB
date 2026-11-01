#!/usr/bin/env python
"""U19 companion — validate the CDP readback harness against a real Chromium.

WebView2 is a Chromium embed. Running the SAME self-contained CDP/WebSocket
client against a real headless Chromium proves the harness's readback logic
works (target discovery + Runtime.evaluate + screenshot), decoupling it from
the local GNU `app.exe` toolchain limitation (the local release exe is missing
its MinGW runtime chain / has no MSVC linker, so it SEGVs at launch). This is
the web-engine equivalent of the WINDOWS_TAURI_E2E readback: a real engine
rendering the real React `dist` fed by the real sidecar v3 backend.

Evidence is written under .project-local/runs/. It is an explicit
CHROMIUM_E2E companion artifact, NOT a claim that the Tauri exe itself
launched — that exact-SHA step is the CI windows-latest job.
"""
from __future__ import annotations
import json, os, socket, subprocess, sys, time, threading, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OBS = ROOT / "apps" / "observer"
sys.path.insert(0, str(ROOT / "packages" / "client-neutral-core" / "scripts"))
sys.path.insert(0, str(ROOT / "services" / "orchestration"))
sys.path.insert(0, str(OBS / "scripts"))
from u19_webview_e2e import start_sidecar, CDP, discover_cdp_ws, pick_free_port, readback_asserts  # noqa

RUNS = ROOT / ".project-local" / "runs"
RUNS.mkdir(parents=True, exist_ok=True)

CHROMES = [
    r"C:\Users\ALEX\AppData\Local\ms-playwright\chromium-1228\chrome-win64\chrome.exe",
    r"D:\All projects\OS External Configuration\toolchains\playwright\chromium-1228\chrome-win64\chrome.exe",
]
def find_chrome() -> str:
    for c in CHROMES:
        if os.path.exists(c):
            return c
    for base in [os.path.expanduser("~/.cache/ms-playwright"), r"C:\Users\ALEX\AppData\Local\ms-playwright"]:
        for r_, d_, f_ in os.walk(base):
            if "chrome.exe" in f_:
                return os.path.join(r_, "chrome.exe")
    return ""


def main() -> int:
    chrome = find_chrome()
    if not chrome:
        print("[U19-chromium] no Chromium found — cannot validate CDP harness"); return 1
    dist = OBS / "frontend" / "dist"
    if not (dist / "index.html").exists():
        print("[U19-chromium] frontend/dist absent — build first (npm run build)"); return 1

    # 1) real v3 backend
    sidecar, port, th, server = start_sidecar()
    backend = f"http://127.0.0.1:{port}"

    # 2) serve the real React dist on a dynamic loopback port
    from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
    import functools
    hsvc = ThreadingHTTPServer(("127.0.0.1", 0),
                               functools.partial(SimpleHTTPRequestHandler, directory=str(dist)))
    hport = hsvc.server_port
    threading.Thread(target=hsvc.serve_forever, daemon=True).start()

    # 3) CDP port + Chromium headless
    cdp = pick_free_port()
    udf = RUNS / "u19_chromium_udf"
    import shutil
    shutil.rmtree(udf, ignore_errors=True); udf.mkdir(parents=True, exist_ok=True)
    url = f"http://127.0.0.1:{hport}/?api={backend}&view=full&theme=dark"
    cmd = [chrome, "--headless=new", f"--remote-debugging-port={cdp}",
           f"--user-data-dir={udf}", "--no-sandbox", "--disable-gpu",
           "--window-size=1280,820", url]
    app = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    result = {"gate": "WINDOWS_TAURI_E2E_CHROMIUM_COMPANION",
              "chrome": chrome, "cdp_port": cdp, "url": url,
              "stages": {}, "verdict": "FAIL"}
    cdp_obj = None
    try:
        # wait for CDP target
        ws = discover_cdp_ws(cdp, tries=90)
        cdp_obj = CDP(ws)
        time.sleep(3)  # let React mount + first snapshot fetch settle
        dom = readback_asserts(cdp_obj)
        png = cdp_obj.screenshot()
        shot = RUNS / "u19_chromium_readback.png"
        shot.write_bytes(png)
        real_render = (dom.get("rootPopulated") and dom.get("bodyLen", 0) > 40
                      and not dom.get("isAboutBlank"))
        result["stages"]["webview_readback"] = {
            "status": "PASS" if real_render else "FAIL",
            "cdpTarget": ws, "dom": dom, "screenshot": str(shot),
            "screenshotBytes": len(png),
        }
        result["verdict"] = "PASS" if real_render else "FAIL"
        print("[U19-chromium] readback:", json.dumps(dom, indent=2, ensure_ascii=False))
    except Exception as e:
        result["stages"]["webview_readback"] = {"status": "FAIL", "reason": repr(e)}
        print("[U19-chromium] FAILED:", repr(e))
    finally:
        if cdp_obj: cdp_obj.close()
        try: app.terminate(); app.wait(timeout=8)
        except Exception: app.kill()
        hsvc.shutdown(); hsvc.server_close()
        server.shutdown(); server.server_close()

    (RUNS / "u19_chromium_readback.json").write_text(json.dumps(result, indent=2, ensure_ascii=False))
    print("[U19-chromium] VERDICT:", result["verdict"], "| evidence:",
          result.get("stages", {}).get("webview_readback", {}).get("screenshot"))
    return 0 if result["verdict"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
