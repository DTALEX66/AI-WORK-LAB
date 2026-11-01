#!/usr/bin/env python
"""Read the rendered top-row geometry from headless Chrome.

A scratch copy of the shipped dist gets one extra script that measures after
load and prints the JSON into the DOM; `--dump-dom` reads it back. That avoids
the CDP attach path entirely and still measures the same bundle the release
binary embeds, at the same CSS viewport the window lays out against.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.parse
from pathlib import Path

ROOT = Path(r"D:\All projects\WORK-LAB")
OBS = ROOT / "apps" / "observer"
HERE = ROOT / ".project-local" / "runs" / "topbar-measure-20261006"
CHROME = str(Path(os.environ.get("PROGRAMFILES", "C:/Program Files"))
             / "Google/Chrome/Application/chrome.exe")

MEASURE_JS = r"""
(function () {
  // Deferred: the React bundle mounts after parsing, so measuring inline would
  // photograph an empty #root. --virtual-time-budget advances this timer.
  window.addEventListener("load", function () { setTimeout(run, 700); });
  function run() {
  var SELECTORS = [".app", ".topbar", ".search", ".top-actions", ".winctl",
                   ".winctl-btn", ".sidebar", ".main", ".brand", ".wl-mark"];
  function edge(el) {
    var r = el.getBoundingClientRect(), cs = getComputedStyle(el);
    return {
      left: Math.round(r.left * 10) / 10, top: Math.round(r.top * 10) / 10,
      right: Math.round(r.right * 10) / 10, bottom: Math.round(r.bottom * 10) / 10,
      width: Math.round(r.width * 10) / 10, height: Math.round(r.height * 10) / 10,
      gapLeft: Math.round(r.left * 10) / 10,
      gapTop: Math.round(r.top * 10) / 10,
      gapRight: Math.round((innerWidth - r.right) * 10) / 10,
      gapBottom: Math.round((innerHeight - r.bottom) * 10) / 10,
      padding: cs.padding, margin: cs.margin, position: cs.position,
      display: cs.display
    };
  }
  var out = { viewport: innerWidth + "x" + innerHeight, scrollWidth: document.documentElement.scrollWidth,
             scrollHeight: document.documentElement.scrollHeight, items: {} };
  SELECTORS.forEach(function (sel) {
    var els = Array.prototype.slice.call(document.querySelectorAll(sel));
    out.items[sel] = els.length ? els.slice(0, 3).map(edge) : { absent: true };
  });
  // Anything whose top edge is within 6px of the viewport top is what the owner
  // means by "touching the border"; list it with a readable handle.
  out.touchingTop = [];
  out.touchingRight = [];
  Array.prototype.forEach.call(document.querySelectorAll("body *"), function (el) {
    var r = el.getBoundingClientRect();
    if (r.width < 4 || r.height < 4) return;
    var handle = el.tagName + "." + (typeof el.className === "string" ? el.className : "") +
                 (el.getAttribute("aria-label") ? "[aria=" + el.getAttribute("aria-label") + "]" : "");
    if (r.top <= 6 && r.bottom > 10) out.touchingTop.push(handle + " top=" + Math.round(r.top) + " h=" + Math.round(r.height));
    if (r.right >= innerWidth - 6 && r.left < innerWidth - 6) out.touchingRight.push(handle + " right=" + Math.round(r.right) + " w=" + Math.round(r.width));
  });
  out.touchingTop = out.touchingTop.slice(0, 15);
  out.touchingRight = out.touchingRight.slice(0, 15);
  var pre = document.createElement("pre");
  pre.id = "__measure__";
  pre.textContent = "MEASURE-BEGIN" + JSON.stringify(out) + "MEASURE-END";
  document.body.appendChild(pre);
  }
})();
"""


def pick_free_port() -> int:
    import socket
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


def build_probe_dist(api: str | None = None) -> tuple[Path, int]:
    src = OBS / "frontend" / "dist"
    tag = f"{int(time.time())}"
    dst = HERE / f"dist-probe-{tag}"
    if dst.exists():
        shutil.rmtree(dst, ignore_errors=True)
    shutil.copytree(src, dst)
    index = dst / "index.html"
    html = index.read_text(encoding="utf-8")
    injection = ("<script id=\"__measure_src\">" + MEASURE_JS + "</script>")
    if "MEASURE-BEGIN" not in html:
        html = html.replace("</body>", injection + "</body>")
    index.write_text(html, encoding="utf-8")
    port = pick_free_port()
    return dst, port


def render(dist: Path, port: int, width: int, height: int, extra_query: str,
           view: str = "full", budget_ms: int = 9000) -> dict:
    srv = subprocess.Popen([sys.executable, "-m", "http.server", str(port),
                            "--bind", "127.0.0.1"],
                           cwd=str(dist), stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL)
    udd = HERE / f"chrome-udf-{int(time.time() * 1000)}"
    url = (f"http://127.0.0.1:{port}/index.html?view={view}&mode=UNKNOWN"
           f"&theme=dark&shell=tauri{extra_query}")
    try:
        time.sleep(1.5)
        done = subprocess.run(
            [CHROME, "--headless=new", "--disable-gpu", "--no-sandbox",
             f"--user-data-dir={udd}", f"--window-size={width},{height}",
             f"--virtual-time-budget={budget_ms}", "--dump-dom", url],
            capture_output=True, timeout=150, check=False)
        dom = done.stdout.decode("utf-8", "replace")
    finally:
        srv.kill()
    m = re.search(r"MEASURE-BEGIN(\{.*\})MEASURE-END", dom, re.S)
    if not m:
        return {"error": "no measurement in DOM", "domBytes": len(dom),
                "stderr": done.stderr.decode("utf-8", "replace")[-300:]}
    return json.loads(m.group(1))


def main() -> int:
    report: dict = {"startedAt": time.strftime("%Y-%m-%dT%H:%M:%S"), "cases": []}
    for (w, h, label, view) in ((1280, 820, "main-window", "full"),
                                (440, 680, "panel-window", "compact")):
        dist, port = build_probe_dist()
        data = render(dist, port, w, h, "", view)
        report["cases"].append({"case": label, "cssViewport": f"{w}x{h}", **data})
        shutil.rmtree(dist, ignore_errors=True)
    (HERE / "geometry.json").write_text(json.dumps(report, indent=2), encoding="utf-8")

    for case in report["cases"]:
        print(f"\n===== {case['case']} reported viewport {case.get('viewport')} "
              f"(scrollW {case.get('scrollWidth')}) =====")
        if "error" in case:
            print("  ERROR:", case["error"], case.get("stderr"))
            continue
        for sel, val in case["items"].items():
            if isinstance(val, list):
                for e in val:
                    print(f"  {sel:<12} top={e['top']:<6} left={e['left']:<7} "
                          f"gapRight={e['gapRight']:<7} w={e['width']:<7} "
                          f"h={e['height']:<6} pad={e['padding']!r} pos={e['position']}")
            else:
                print(f"  {sel:<12} {val}")
        print("  touchingTop:", json.dumps(case["touchingTop"], ensure_ascii=False)[:700])
        print("  touchingRight:", json.dumps(case["touchingRight"], ensure_ascii=False)[:700])
    return 0


if __name__ == "__main__":
    sys.exit(main())
