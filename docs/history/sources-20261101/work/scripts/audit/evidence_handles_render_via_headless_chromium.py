"""Paint the evidence lane in real Chromium at the repository's own window sizes and keep the images.

What this can and cannot claim. Chromium's `--dump-dom` never returns against this app because the page
holds an open `/api/v1/events` stream, so a markup assertion cannot be made from a one-shot browser run;
and a PNG byte count says nothing about whether the projection arrived, because a shorter window paints
fewer bytes. This tool therefore only captures, records every attempt, and names the harnesses that do
carry the assertions: `src/views/evidenceHandles.contract.test.tsx` (component truth) and
`text_legibility_via_cdp.py` / `topbar_geometry_via_cdp.py` (rendered geometry and the 12px floor).
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import threading
import time
import urllib.request
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OBS = ROOT / "apps/observer"
RUNS = ROOT / ".project-local/runs/standalone-20261019"
ARTIFACTS = ROOT / ".project-local/artifacts/standalone-run-20261019"
WINDOWS = {"full": (1280, 820), "tall": (1280, 2600), "floor": (900, 600)}

sys.path.insert(0, str(OBS / "scripts"))
sys.path.insert(0, str(ROOT / "scripts" / "audit"))
from u19_webview_e2e import start_sidecar  # noqa: E402
# The browser is resolved, never asserted: this host's earlier copy pinned one Playwright build by absolute
# path, so on any other machine -- and in CI -- the tool refused for a reason that had nothing to do with the
# product. `find_browser` is the same resolution the geometry, legibility and HUD gates use (WL_CHROME wins,
# then Chrome, then Edge), and a refusal now names what is missing instead of printing a path that only
# exists here.
from topbar_geometry_via_cdp import find_browser  # noqa: E402


def main() -> int:
    browser = find_browser()
    if not browser:
        print("EVIDENCE_PAINT_NOT_RUN BROWSER_NOT_FOUND — set WL_CHROME to a Chrome/Edge binary")
        return 3
    dist = OBS / "frontend" / "dist"
    if not (dist / "index.html").is_file():
        print(f"EVIDENCE_PAINT_NOT_RUN DIST_ABSENT {dist} — run npm run build first")
        return 3
    ARTIFACTS.mkdir(parents=True, exist_ok=True)

    sidecar, sidecar_port, thread, server = start_sidecar()
    backend = f"http://127.0.0.1:{sidecar_port}"
    with urllib.request.urlopen(f"{backend}/api/v1/snapshot", timeout=30) as response:
        summary = (json.loads(response.read().decode("utf-8")).get("artifactHandlesSummary") or {})
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), partial(SimpleHTTPRequestHandler, directory=str(dist)))
    web_port = httpd.server_port
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    profile = RUNS / "paint_profile"
    shutil.rmtree(profile, ignore_errors=True)
    profile.mkdir(parents=True, exist_ok=True)
    url = f"http://127.0.0.1:{web_port}/?view=evidence&api={backend}/api/v1/snapshot&theme=dark"
    # Warm the projection twice before any browser starts: the first build enumerates the declared
    # evidence surfaces, and a cold first paint is what made earlier captures time out.
    for _ in range(2):
        with urllib.request.urlopen(f"{backend}/api/v1/snapshot", timeout=30) as response:
            response.read()
        time.sleep(1.0)
    report: dict[str, object] = {"url": url, "backend": {"projected": summary.get("projectedCount"),
                                                         "enumerated": summary.get("enumeratedCount"),
                                                         "omitted": summary.get("omittedCount")},
                                 "windows": {}}
    try:
        for name, size in WINDOWS.items():
            attempts = []
            for take in range(1, 3):
                png = ARTIFACTS / f"15-evidence-{name}-{take}.png"
                command = [str(browser), "--headless=new", "--no-sandbox", "--disable-gpu", "--no-first-run",
                           "--disable-crash-reporter", "--hide-scrollbars", f"--user-data-dir={profile}",
                           f"--window-size={size[0]},{size[1]}", "--timeout=20000",
                           f"--screenshot={png}", url]
                try:
                    completed = subprocess.run(command, capture_output=True, text=True,
                                               encoding="utf-8", errors="replace", timeout=75)
                    code = completed.returncode
                except subprocess.TimeoutExpired:
                    code = 124
                attempts.append({"file": png.name, "exit": code,
                                 "bytes": png.stat().st_size if png.is_file() else 0})
            report["windows"][name] = attempts
            print(f"{name}: {attempts}")
        report["assertionsLiveIn"] = ["apps/observer/frontend/src/views/evidenceHandles.contract.test.tsx",
                                      "scripts/audit/text_legibility_via_cdp.py",
                                      "scripts/audit/topbar_geometry_via_cdp.py"]
        report["verdict"] = "EVIDENCE_PAINT_CAPTURED"
    finally:
        try:
            httpd.shutdown()
        except OSError:
            pass
        try:
            server.shutdown()
            server.server_close()
        except OSError:
            pass
        time.sleep(0.3)
        shutil.rmtree(profile, ignore_errors=True)

    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    (ARTIFACTS / "15-evidence-paint.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("RECEIPT ->", ARTIFACTS / "15-evidence-paint.json")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    raise SystemExit(main())
