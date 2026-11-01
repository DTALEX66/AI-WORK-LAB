#!/usr/bin/env python3
"""Rebuild every shipped WORK-LAB brand asset from the owner-supplied vector artwork.

    python scripts/brand/build_work_brand.py            # write the assets
    python scripts/brand/build_work_brand.py --check    # re-render into a temp dir and report drift

Why this is a script and not a folder of exported images: the artwork arrives as two Illustrator SVG exports
(`docs/history/owner-inputs/20261025/`), the shell needs a *cut* of it (the symbol without the type, because
the top bar already types `WORK-LAB` beside the mark), and the desktop bundle needs fifteen raster sizes plus
two icon containers. Doing that by hand is how a brand swap ends up with a stale tray icon and an .ico that
still shows the previous identity.

Two things are deliberately not done here:

  * no resampling. Every size is rasterised from the vector at its own pixel size, because the project venv
    carries no image library and adding Pillow for a logo is a dependency change nobody asked for. Chrome's
    own SVG renderer is the rasteriser, and it is already the engine the desktop shell uses.
  * no redrawing. The paths are the supplied ones; the only edits are which paths are kept, the viewBox that
    frames them, and the fill colour of the reversed tile.

The cut is found by asking the renderer where the ink is: `getBBox()` per path, pushed through `getCTM()`
into viewBox units. Both supplied cuts report the same symbol ratio (1.8968 / 1.8969), which is why the
shell's existing 42x22 and 91x48 slots still fit it.
"""
from __future__ import annotations

import argparse
import base64
import json
import pathlib
import re
import shutil
import struct
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
ORIGINALS = ROOT / "docs/history/owner-inputs/20261025"
FRONT = ROOT / "apps/observer/frontend/src/assets/brand"
ICONS = ROOT / "apps/observer/src-tauri/icons"

INK = "#231815"          # the artwork's own fill
PAPER = "#F4F1EC"        # the reversed-out field for the mark on an ink tile
MARK_RATIO = 1.8968      # measured: 272.79 x 143.82 viewBox units of symbol ink

STACKED = ORIGINALS / "WORK-1.svg"      # symbol above the type
LOCKUP = ORIGINALS / "WORK-2.svg"       # symbol beside the type

# The symbol is everything above the type block in the stacked cut (ink y < 185 of a 305-unit box);
# the wide cut separates the same three paths by a 19.78-unit gap.
SYMBOL_Y_SPLIT = 185.0

CHROME_CANDIDATES = (
    __import__("os").environ.get("WL_CHROME"),
    r"C:/Program Files/Google/Chrome/Application/chrome.exe",
    r"C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe",
)

# (repo path, kind, size). kind: mark | wordmark | lockup | tile | tileTray | svg
RASTER_TARGETS: list[tuple[str, str, int, int]] = [
    ("apps/observer/frontend/src/assets/brand/work-lab-mark.png", "mark", 1044, 550),
    ("apps/observer/frontend/src/assets/brand/work-lab-wordmark.png", "wordmark", 1112, 300),
    ("apps/observer/frontend/src/assets/brand/work-lab-lockup.png", "lockup", 1397, 299),
    ("apps/observer/frontend/src/assets/brand/app-icon-512.png", "tile", 512, 512),
    # The browser tab. index.html links ./favicon.png, and Vite copies `public/` to the bundle root -- with no
    # entry here the file the page asks for was never produced by the "one command reproduces every asset"
    # build, so the tab fell back to a generic glyph while the claim said otherwise.
    ("apps/observer/frontend/public/favicon.png", "tile", 64, 64),
    ("apps/observer/src-tauri/icons/32x32.png", "tile", 32, 32),
    ("apps/observer/src-tauri/icons/64x64.png", "tile", 64, 64),
    ("apps/observer/src-tauri/icons/128x128.png", "tile", 128, 128),
    ("apps/observer/src-tauri/icons/128x128@2x.png", "tile", 256, 256),
    ("apps/observer/src-tauri/icons/icon.png", "tile", 256, 256),
    ("apps/observer/src-tauri/icons/Square30x30Logo.png", "tile", 30, 30),
    ("apps/observer/src-tauri/icons/Square44x44Logo.png", "tile", 44, 44),
    ("apps/observer/src-tauri/icons/Square71x71Logo.png", "tile", 71, 71),
    ("apps/observer/src-tauri/icons/Square89x89Logo.png", "tile", 89, 89),
    ("apps/observer/src-tauri/icons/Square107x107Logo.png", "tile", 107, 107),
    ("apps/observer/src-tauri/icons/Square142x142Logo.png", "tile", 142, 142),
    ("apps/observer/src-tauri/icons/Square150x150Logo.png", "tile", 150, 150),
    ("apps/observer/src-tauri/icons/Square284x284Logo.png", "tile", 284, 284),
    ("apps/observer/src-tauri/icons/Square310x310Logo.png", "tile", 310, 310),
    ("apps/observer/src-tauri/icons/StoreLogo.png", "tile", 50, 50),
]
VECTOR_TARGETS = {
    "apps/observer/frontend/src/assets/brand/work-lab-mark.svg": "mark",
    "apps/observer/frontend/src/assets/brand/work-lab-wordmark.svg": "wordmark",
    "apps/observer/frontend/src/assets/brand/work-lab-lockup.svg": "lockupAll",
    "apps/observer/frontend/src/assets/brand/work-lab-stacked.svg": "all",
    "apps/observer/frontend/src/assets/brand/work-lab-observer-symbol.svg": "tileSvg",
    "apps/observer/frontend/src/assets/brand/work-lab-observer-tray.svg": "tileTraySvg",
    "apps/observer/src-tauri/icons/brand.svg": "tileSvg",
}
ICO_SIZES = (16, 32, 48, 64, 128, 256)
ICNS_ENTRIES = (("is32", 16), ("il32", 48), ("ic07", 128), ("ic08", 256), ("ic09", 512), ("ic10", 1024))


class BrandBuildError(RuntimeError):
    pass


def find_browser() -> str:
    for candidate in CHROME_CANDIDATES:
        if candidate and pathlib.Path(candidate).is_file():
            return candidate
    raise BrandBuildError("BRAND_BUILD_NOT_RUN BROWSER_NOT_FOUND — set WL_CHROME to a Chrome/Edge binary")


def run_browser(browser: str, extra: list[str]) -> str:
    proc = subprocess.run([browser, "--headless=new", "--no-sandbox", "--disable-gpu", "--hide-scrollbars",
                           *extra], capture_output=True, text=True, encoding="utf-8", errors="replace",
                          timeout=240)
    return proc.stdout


# ---------------------------------------------------------------- the cut, measured in the renderer
DERIVE_PAGE = """<!doctype html><html><head><meta charset="utf-8"></head><body><div id="stage"></div>
<pre id="out"></pre><script>
const JOBS = __JOBS__;
const SOURCES = __SOURCES__;
function corners(b, m) {
  return [[b.x, b.y], [b.x + b.width, b.y], [b.x, b.y + b.height], [b.x + b.width, b.y + b.height]]
    .map(p => ({x: m.a * p[0] + m.c * p[1] + m.e, y: m.b * p[0] + m.d * p[1] + m.f}));
}
function units(svg, el) {
  const rect = svg.getBoundingClientRect();
  const vb = svg.getAttribute('viewBox').split(/[ ,]+/).map(Number);
  const c = corners(el.getBBox(), el.getCTM());
  const xs = c.map(p => p.x / (rect.width / vb[2])), ys = c.map(p => p.y / (rect.height / vb[3]));
  return {x: Math.min(...xs), y: Math.min(...ys), w: Math.max(...xs) - Math.min(...xs),
          h: Math.max(...ys) - Math.min(...ys)};
}
const out = {};
for (const [name, job] of Object.entries(JOBS)) {
  const host = document.createElement('div');
  host.innerHTML = SOURCES[job.file];
  document.getElementById('stage').appendChild(host);
  const svg = host.querySelector('svg');
  const shapes = Array.from(svg.querySelectorAll('path, rect, circle, ellipse, polygon, polyline'));
  const boxes = shapes.map(el => ({el, box: units(svg, el)}));
  let keep = boxes;
  if (job.mode === 'y-below') keep = boxes.filter(b => b.box.y < job.value);
  else if (job.mode === 'x-after-gap') {
    const sorted = [...boxes].sort((a, b) => a.box.x - b.box.x);
    let gap = -1, at = 0;
    for (let i = 0; i + 1 < sorted.length; i++) {
      const g = sorted[i + 1].box.x - (sorted[i].box.x + sorted[i].box.w);
      if (g > gap) { gap = g; at = i + 1; }
    }
    keep = sorted.slice(at);
  }
  for (const b of boxes) if (!keep.includes(b)) b.el.remove();
  const x1 = Math.min(...keep.map(b => b.box.x)), y1 = Math.min(...keep.map(b => b.box.y));
  const x2 = Math.max(...keep.map(b => b.box.x + b.box.w)), y2 = Math.max(...keep.map(b => b.box.y + b.box.h));
  svg.setAttribute('viewBox', `${x1.toFixed(3)} ${y1.toFixed(3)} ${(x2 - x1).toFixed(3)} ${(y2 - y1).toFixed(3)}`);
  svg.removeAttribute('style');
  svg.setAttribute('xmlns', 'http://www.w3.org/2000/svg');
  out[name] = {svg: new XMLSerializer().serializeToString(svg),
               box: {w: x2 - x1, h: y2 - y1}, ratio: (x2 - x1) / (y2 - y1)};
}
// Base64: `--dump-dom` prints HTML, so an SVG sitting in a text node would come back entity-escaped.
const bytes = new TextEncoder().encode(JSON.stringify(out));
let bin = '';
for (const b of bytes) bin += String.fromCharCode(b);
document.getElementById('out').textContent = btoa(bin);
</script></body></html>"""


def derive_cuts(browser: str, workdir: pathlib.Path) -> dict[str, str]:
    sources = {"WORK-1.svg": STACKED.read_text(encoding="utf-8"),
               "WORK-2.svg": LOCKUP.read_text(encoding="utf-8")}
    jobs = {
        "mark": {"file": "WORK-1.svg", "mode": "y-below", "value": SYMBOL_Y_SPLIT},
        "wordmark": {"file": "WORK-2.svg", "mode": "x-after-gap"},
        "lockupAll": {"file": "WORK-2.svg", "mode": "all"},
        "all": {"file": "WORK-1.svg", "mode": "all"},
    }
    page = (DERIVE_PAGE.replace("__JOBS__", json.dumps(jobs))
            .replace("__SOURCES__", json.dumps(sources, ensure_ascii=False)))
    page_path = workdir / "derive.html"
    page_path.write_text(page, encoding="utf-8")
    dom = run_browser(browser, ["--virtual-time-budget=4000", "--dump-dom", page_path.as_uri()])
    start = dom.find('<pre id="out">')
    if start < 0:
        raise BrandBuildError(f"BRAND_BUILD_NOT_RUN derivation produced no output (rc={dom!r:.200})")
    payload = dom[start + len('<pre id="out">'):dom.find("</pre>", start)].strip()
    data = json.loads(base64.b64decode(payload).decode("utf-8"))
    measured = data["mark"]["ratio"]
    if abs(measured - MARK_RATIO) > 0.01:
        raise BrandBuildError(f"BRAND_GEOMETRY_DRIFT mark ratio {measured:.4f} != pinned {MARK_RATIO:.4f}; "
                              "the artwork changed, so every slot ratio needs re-measuring")
    return {name: item["svg"] for name, item in data.items()}


# ---------------------------------------------------------------- the tile
def tile_svg(size: int, field: str, glyph: str, mark: str, radius: float, mark_width: float) -> str:
    x, y, w, h = (float(v) for v in re.search(r'viewBox="([^"]+)"', mark).group(1).split())
    scale = (size * mark_width) / w
    tx = (size - w * scale) / 2 - x * scale
    ty = (size - h * scale) / 2 - y * scale
    body = mark[mark.index(">") + 1:mark.rindex("</svg>")].replace(f"fill:{INK}", f"fill:{glyph}")
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {size} {size}" width="{size}" height="{size}">'
            f'<rect x="0" y="0" width="{size}" height="{size}" rx="{size * radius:.1f}" fill="{field}"/>'
            f'<g transform="translate({tx:.3f} {ty:.3f}) scale({scale:.6f})">{body}</g></svg>\n')


def sized(svg: str, width: int, height: int) -> str:
    return svg.replace("<svg ", f'<svg width="{width}" height="{height}" ', 1)


def render(browser: str, svg: str, target: pathlib.Path, width: int, height: int) -> None:
    page = target.parent / f".render-{target.stem}-{width}x{height}.html"
    page.write_text("<!doctype html><html><head><meta charset=\"utf-8\"><style>"
                    f"html,body{{margin:0;padding:0;width:{width}px;height:{height}px;overflow:hidden;"
                    "background:transparent}svg{display:block;width:100%;height:100%}</style></head><body>"
                    + svg + "</body></html>", encoding="utf-8")
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        target.unlink()
    run_browser(browser, ["--force-device-scale-factor=1", "--default-background-color=00000000",
                          f"--window-size={width},{height}", f"--screenshot={target}", page.as_uri()])
    page.unlink(missing_ok=True)
    if not target.is_file():
        raise BrandBuildError(f"BRAND_BUILD_NOT_RUN no image written for {target.name}")
    data = target.read_bytes()
    got_w, got_h = int.from_bytes(data[16:20], "big"), int.from_bytes(data[20:24], "big")
    if (got_w, got_h) != (width, height):
        raise BrandBuildError(f"BRAND_BUILD_SIZE {target.name} rendered {got_w}x{got_h}, asked {width}x{height}")
    if data[25] != 6:
        raise BrandBuildError(f"BRAND_BUILD_SIZE {target.name} colour type {data[25]}, expected 6 (RGBA)")


def write_ico(target: pathlib.Path, pngs: list[tuple[int, pathlib.Path]]) -> None:
    entries, payload, offset = [], b"", 6 + 16 * len(pngs)
    for size, png in pngs:
        data = png.read_bytes()
        side = 0 if size >= 256 else size
        entries.append(struct.pack("<BBBBHHII", side, side, 0, 0, 1, 32, len(data), offset))
        payload += data
        offset += len(data)
    target.write_bytes(struct.pack("<HHH", 0, 1, len(pngs)) + b"".join(entries) + payload)


def write_icns(target: pathlib.Path, pngs: list[tuple[str, pathlib.Path]]) -> None:
    chunks = b""
    for code, png in pngs:
        data = png.read_bytes()
        chunks += code.encode("ascii") + struct.pack(">I", 8 + len(data)) + data
    target.write_bytes(b"icns" + struct.pack(">I", 8 + len(chunks)) + chunks)


def build(out_root: pathlib.Path, browser: str) -> list[pathlib.Path]:
    cuts = derive_cuts(browser, out_root)
    mark = cuts["mark"]
    written: list[pathlib.Path] = []

    def place(relative: str) -> pathlib.Path:
        target = out_root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        written.append(target)
        return target

    for relative, kind, width, height in RASTER_TARGETS:
        target = place(relative)
        if kind == "mark":
            render(browser, sized(mark, width, height), target, width, height)
        elif kind == "wordmark":
            render(browser, sized(cuts["wordmark"], width, height), target, width, height)
        elif kind == "lockup":
            render(browser, sized(cuts["lockupAll"], width, height), target, width, height)
        else:
            radius = 0.20 if width >= 128 else 0.16
            mark_width = 0.70 if width >= 128 else 0.78
            render(browser, tile_svg(width, INK, PAPER, mark, radius, mark_width), target, width, height)

    for relative, kind in VECTOR_TARGETS.items():
        target = place(relative)
        if kind in cuts:
            text = cuts[kind]
        elif kind == "tileSvg":
            text = tile_svg(512, INK, PAPER, mark, 0.22, 0.70)
        else:
            text = tile_svg(512, PAPER, INK, mark, 0.22, 0.76)
        target.write_text(text, encoding="utf-8", newline="\n")

    masters: dict[int, pathlib.Path] = {}
    for size in sorted({size for _, size in ICNS_ENTRIES} | set(ICO_SIZES)):
        target = out_root / f"containers/master-{size}.png"
        target.parent.mkdir(parents=True, exist_ok=True)
        render(browser, tile_svg(size, INK, PAPER, mark, 0.20 if size >= 128 else 0.16,
                                 0.70 if size >= 128 else 0.78), target, size, size)
        masters[size] = target
    write_ico(place("apps/observer/src-tauri/icons/icon.ico"), [(s, masters[s]) for s in ICO_SIZES])
    write_icns(place("apps/observer/src-tauri/icons/icon.icns"),
               [(code, masters[size]) for code, size in ICNS_ENTRIES])
    return written


def digest(path: pathlib.Path) -> str:
    return __import__("hashlib").sha256(path.read_bytes()).hexdigest()[:16]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true",
                        help="re-render into a temp dir and compare against the committed bytes; writes nothing")
    args = parser.parse_args(argv)

    for original in (STACKED, LOCKUP):
        if not original.is_file():
            print(f"BRAND_BUILD_NOT_RUN missing supplied artwork {original.relative_to(ROOT)}")
            return 3
    try:
        browser = find_browser()
    except BrandBuildError as refused:
        print(str(refused))
        return 3

    workdir = ROOT / ".project-local/runs/brand-build"
    if workdir.exists():
        shutil.rmtree(workdir)
    workdir.mkdir(parents=True)
    try:
        written = build(workdir, browser)
        if args.check:
            drift = []
            for target in written:
                shipped = ROOT / target.relative_to(workdir)
                if not shipped.is_file():
                    drift.append(f"{shipped.relative_to(ROOT)} absent")
                elif digest(shipped) != digest(target):
                    drift.append(f"{shipped.relative_to(ROOT)} bytes differ")
            print(f"BRAND_BUILD_CHECK rendered={len(written)} drift={len(drift)}")
            for line in drift:
                print(f"  {line}")
            if drift:
                print("BRAND_BUILD_DRIFT -- run `python scripts/brand/build_work_brand.py` and commit the result")
                return 1
            print("BRAND_BUILD_FRESH every shipped asset equals what the supplied artwork builds")
            return 0
        for target in written:
            shipped = ROOT / target.relative_to(workdir)
            shipped.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(target, shipped)
        print(f"BRAND_BUILD_PASS assets={len(written)} browser={pathlib.Path(browser).name}")
        return 0
    except BrandBuildError as refused:
        print(f"{refused}")
        return 3
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
