#!/usr/bin/env python
"""Text legibility gate — measure the shipped bundle in a real browser: type floor, AA contrast, both themes.

DESIGN.md and SCREEN_SPEC.md state numeric clauses (no meaningful text below 12px, 4.5:1 normal / 3:1
large, in BOTH themes). Until this instrument existed nothing measured them: `verify_design_contract.py`
parses token files and `standard_validators.py` stores "text contrast >= 4.5:1" as a *string* and then
checks whether a caller declared it — both stay green over text a user cannot read. A standard nobody
measures is a description, not a contract.

Division of labour is deliberate: the browser harvests raw computed styles only, and every judgement
(parse the colour, composite the alpha, take the ratio, apply the large-text exemption) is pure Python
here, so it is unit-testable and falsifiable without launching anything (see
`tests/ci/test_text_legibility_gate.py`). The first version of this maths lived in a browser script and
carried a bug nobody could test — it dropped the foreground's alpha and scored 50%-transparent black
text as solid black, 21:1 instead of the 3.98:1 a user actually sees.

What it refuses to fake:
  * a sample that has not settled. The skins animate colour, so a read taken mid-transition returns
    interpolated values no user ever sees; two disagreeing samples exit 3, they do not average.
  * a thin harvest. Fewer text nodes than that surface's own chrome count means the page rendered
    nothing readable, which is reported as NOT_RUN — `scannedFileCount: 0` was a false green in this
    project once already. The count is per surface and never a population's node total, so a sparse real
    ledger is not convicted for holding fewer agents than the declared fixture.
  * an unparsable colour. A value this instrument cannot interpret is UNKNOWN and fails; it is never
    skipped into a pass.

Gradient backdrops are the one documented approximation: text over a `background-image` is measured
against the solid layer stack beneath it, and the affected node count is printed, not hidden.

Exit: 0 LEGIBILITY_GATE_PASS, 1 LEGIBILITY_GATE_FAIL, 3 LEGIBILITY_GATE_NOT_RUN.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import math
import re
import sys
import traceback
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "audit"))
import bundle_provenance  # noqa: E402  # every receipt names the bytes the browser loaded
GEOMETRY = ROOT / "scripts" / "audit" / "topbar_geometry_via_cdp.py"
STRIP_GATE = ROOT / "scripts" / "audit" / "hud_strip_geometry_via_cdp.py"
OUT_DIR = ROOT / ".project-local" / "artifacts" / "legibility"

WINDOW_SIZE = "1280,820"
THEMES = ("dark", "light")
# How long one whole-rail harvest may take to ANSWER. The sweep clicks every rail lane and walks every
# scroll range of every view inside ONE page session, so it cannot live on the default 60 s that fits a
# single shell: measured 2026-10-21, one theme costs ~35 s on the development host, and a runner only
# somewhat slower produced `LEGIBILITY_GATE_NOT_RUN views/light at 1280px TimeoutError('timed out')` at
# ed7b8fa6 — the instrument's own ceiling, not a product defect. Declaring the budget here puts it in the
# receipt, so a verdict says which budget it was produced under; a genuine timeout still exits 3.
SWEEP_EVALUATE_TIMEOUT_S = 300.0

FLOOR_PX = 12.0          # DESIGN.md: no text a user must read below 12px
AA_NORMAL = 4.5          # SC 1.4.3
AA_LARGE = 3.0           # SC 1.4.3 large-text exemption
# WCAG 1.4.3 exempts inactive controls outright. This product does not: a disabled button is how the
# read-only shell explains a refusal ("执行由 Task Protocol 创建，Observer 不发起执行"), and an
# explanation the user cannot see is not an explanation. 3:1 is the level at which an object becomes
# discernible (SC 1.4.11), so that is the bar a disabled label must clear here — not the 4.5:1 body
# text rule, and not zero.
AA_DISABLED = 3.0
LARGE_PX = 24.0          # 18pt
LARGE_BOLD_PX = 18.66    # 14pt bold
MIN_NODES = 30           # a harvest thinner than this measured nothing
# The shell surfaces are smaller by design, and a floor written for a 1280px shell would convict a
# 150px strip for being a strip. But the floor may not be the FIXTURE's node count either. Measured
# 2026-10-28 against the shipped bundle from both sides: the declared fixture snapshot paints 12 text
# nodes on `strip-h01` and 19 on `panel-h01`, the live ledger paints 9 and 16. The whole difference is
# how many agent rows each population declares (5 and 6 rows on the fixture, 3 on the ledger), so the
# 12 the fixture happened to produce convicted a healthy strip that simply holds fewer agents than the
# fixture does — the same fixture coupling the hover marker had. What does not move with the population
# is the chrome around the rows: 6 nodes on the strip, 13 on the panel, and an empty page is 0.
# Each floor therefore sits at or below its own chrome count: it can still refuse a render that painted
# nothing, and it stops convicting a sparse real ledger. The two daily screens clear their floor on both
# populations (`daily-home` 44 on the fixture against 33 on the ledger, `daily-governance` 33 on both,
# floor 30), so they keep the shell floor — three nodes of headroom is the number to re-measure if a
# sparser ledger ever convicts them.
MIN_SHELL_NODES = 12     # panel-h01: below its 13 chrome nodes
MIN_STRIP_NODES = 6      # strip-h01: its chrome count, 3 rows short of what the fixture declares
MIN_DAILY_NODES = MIN_NODES

# Roles permitted below the floor. An entry must name a glyph that repeats information available
# elsewhere; `no_stale_floor_exception` fails any entry that matches nothing on the measured screen,
# and the list ships EMPTY because every role that used to claim an exception (.winctl-zoom, the
# first-frame strip, the brand caption) turns out to be text a user must read. Earning a slot here
# means proving the node is decorative, not that it is small.
FLOOR_EXCEPTIONS: list[tuple[str, str]] = []


def load_geometry():
    """Reuse the CDP client and the headless launcher the geometry gate already proved out."""
    spec = importlib.util.spec_from_file_location("topbar_geometry_via_cdp", GEOMETRY)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)  # type: ignore[attr-defined]
    return module


def load_strip_gate():
    """Reuse the narrow-strip gate's declared surfaces and its fixture origin.

    The shell surfaces are not re-declared here on purpose: window shapes have one owner
    (`apps/observer/src-tauri/tauri.conf.json` → `hud_strip_geometry_via_cdp.SURFACES`), and a second
    copy of "150, 480" in this file is a constant that nothing checks against the first.
    """
    spec = importlib.util.spec_from_file_location("hud_strip_geometry_via_cdp", STRIP_GATE)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)  # type: ignore[attr-defined]
    return module


# Which declared surfaces the legibility sweep reads, and the density floor each one owes. Keyed by the
# strip gate's own surface names, so a rename there lands here as a test failure, not a silent skip.
SHELL_SURFACE_KINDS = {
    "strip-h01": MIN_STRIP_NODES,
    "panel-h01": MIN_SHELL_NODES,
    "daily-home": MIN_DAILY_NODES,
    # D2's screen. This dict is an allow-list, so declaring the surface in the strip gate is not enough to
    # have it measured here -- a coverage gate only ever proves the population it actually lists.
    "daily-governance": MIN_DAILY_NODES,
}


def shell_surfaces(strip) -> list[dict]:
    """The shell surfaces to sweep, taken from the strip gate's declarations."""
    out = []
    for spec in strip.SURFACES:
        name = spec["name"]
        if name not in SHELL_SURFACE_KINDS:
            continue
        out.append({"label": name, "query": spec["query"], "size": spec["size"],
                    "mount": strip.MOUNT_SELECTOR[spec["kind"]],
                    "minNodes": SHELL_SURFACE_KINDS[name]})
    missing = sorted(set(SHELL_SURFACE_KINDS) - {s["label"] for s in out})
    if missing:
        raise RuntimeError(f"SHELL_SURFACE_MISSING {missing} — the strip gate no longer declares them")
    return out


# --------------------------------------------------------------------------- colour maths


_COLOR_RE = re.compile(r"rgba?\(([^)]+)\)")
_SRGB_RE = re.compile(r"color\(srgb\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)(?:\s*/\s*([\d.]+))?\)")
_OKLAB_RE = re.compile(r"oklab\(\s*([\d.]+%?|0*\.\d+)\s+(-?[\d.]+%?|0*\.\d+|0)\s+(-?[\d.]+%?|0*\.\d+|0)(?:\s*/\s*([\d.]+%?))?\)")
_OKLCH_RE = re.compile(r"oklch\(\s*([\d.]+%?|0*\.\d+)\s+([\d.]+%?|0*\.\d+|0)\s+(-?[\d.]+)(?:deg)?(?:\s*/\s*([\d.]+%?))?\)")

# Chrome serialises some computed colours as `oklab(...)`/`oklch(...)` even though the source never
# names that space, so a parser limited to rgb()/color(srgb) marks those nodes UNKNOWN. An UNKNOWN is
# (correctly) a gate failure — which means ten perfectly measurable nodes reported "cannot compute"
# and the census could never go green for reasons that had nothing to do with the UI. Conversion is
# Ottosson's published oklab -> linear-sRGB matrix; out-of-gamut results clamp.
def _channel_gamma(value: float) -> float:
    v = max(0.0, min(1.0, value))
    return 12.92 * v if v <= 0.0031308 else 1.055 * (v ** (1 / 2.4)) - 0.055


def _oknum(token: str, scale: float = 1.0) -> float:
    text = str(token)
    if text.endswith("%"):
        return float(text[:-1]) / 100.0 * scale
    return float(text) * scale


def oklab_to_srgb(lightness: float, a: float, b: float) -> tuple[float, float, float]:
    l_ = lightness + 0.3963377774 * a + 0.2158037573 * b
    m_ = lightness - 0.1055613458 * a - 0.0638541728 * b
    s_ = lightness - 0.0894841775 * a - 1.2914855480 * b
    lin = (l_ ** 3, m_ ** 3, s_ ** 3)
    r = 4.0767416621 * lin[0] - 1.5376030856 * lin[1] - 0.4985357996 * lin[2]
    g = -1.2684380046 * lin[0] + 2.6097574011 * lin[1] - 0.3413193965 * lin[2]
    bl = -0.0041960863 * lin[0] - 0.7034186147 * lin[1] + 1.7076147010 * lin[2]
    return (_channel_gamma(r) * 255.0, _channel_gamma(g) * 255.0, _channel_gamma(bl) * 255.0)


def _ok_alpha(token: object, default: float = 1.0) -> float:
    if token is None:
        return default
    text = str(token)
    return float(text[:-1]) / 100.0 if text.endswith("%") else float(text)


def parse_color(value: str) -> tuple[float, float, float, float] | None:
    """`rgb(14 171 188 / 0.7)` and `color(srgb 0.055 0.086 0.098)` to 0-255 channels plus alpha.

    Both forms are live in this bundle: Chrome reports computed colours as `rgb(...)`, and the B10
    skin writes `color(srgb R G B / A)` for its alpha-composited tokens. `color(srgb ...)` channels
    are 0-1 fractions, so reading them as 0-255 would silently make every such colour near-black.
    """
    if not isinstance(value, str):
        return None
    text = value.strip()
    if text == "transparent":
        return (0.0, 0.0, 0.0, 0.0)
    if text == "currentcolor":
        return None
    srgb = _SRGB_RE.search(text)
    if srgb:
        alpha = 1.0 if srgb[4] is None else float(srgb[4])
        return tuple(float(srgb[i]) * 255.0 for i in (1, 2, 3)) + (alpha,)  # type: ignore[return-value]
    lab = _OKLAB_RE.search(text)
    if lab:
        rgb = oklab_to_srgb(_oknum(lab.group(1), 1.0), _oknum(lab.group(2), 1.0), _oknum(lab.group(3), 1.0))
        return tuple(rgb) + (_ok_alpha(lab.group(4)),)                    # type: ignore[return-value]
    lch = _OKLCH_RE.search(text)
    if lch:
        chroma = _oknum(lch.group(2), 0.4)          # CSS: 100% == 0.4 in the C axis
        hue = math.radians(float(lch.group(3)))
        rgb = oklab_to_srgb(_oknum(lch.group(1), 1.0), chroma * math.cos(hue),
                            chroma * math.sin(hue))
        return tuple(rgb) + (_ok_alpha(lch.group(4)),)                    # type: ignore[return-value]
    plain = _COLOR_RE.search(text)
    if not plain:
        return None
    parts = [p for p in re.split(r"[\s,/]+", plain[1].strip()) if p]
    if len(parts) < 3:
        return None
    channels: list[float] = []
    for piece in parts[:3]:
        if piece.endswith("%"):
            channels.append(float(piece[:-1]) * 2.55)
        else:
            channels.append(float(piece))
    alpha = 1.0
    if len(parts) >= 4:
        fourth = parts[3]
        alpha = float(fourth[:-1]) / 100.0 if fourth.endswith("%") else float(fourth)
    return (channels[0], channels[1], channels[2], alpha)


def channel_linear(value: float) -> float:
    s = value / 255.0
    return s / 12.92 if s <= 0.03928 else ((s + 0.055) / 1.055) ** 2.4


def relative_luminance(rgb: tuple[float, float, float]) -> float:
    r, g, b = (channel_linear(v) for v in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast_ratio(fg: tuple[float, float, float], bg: tuple[float, float, float]) -> float:
    hi, lo = max(fg, bg, key=relative_luminance), min(fg, bg, key=relative_luminance)
    light, dark = relative_luminance(hi), relative_luminance(lo)
    return round(((light + 0.05) / (dark + 0.05)) * 100) / 100


def over(fg: tuple[float, float, float, float], bg: tuple[float, float, float]) -> tuple[float, float, float]:
    """Source-over compositing of a translucent colour onto an opaque backdrop."""
    alpha = max(0.0, min(1.0, fg[3]))
    return tuple(fg[i] * alpha + bg[i] * (1.0 - alpha) for i in range(3))  # type: ignore[return-value]


def parse_gradient_stops(value: str) -> list[tuple[float, float, float, float]]:
    """The colour stops of a `linear-gradient(...)` / `radial-gradient(...)`, with their alpha kept.

    b10 paints its filled controls and status pills with two-stop gradients, so "the backdrop is the
    solid layer underneath" is not an approximation worth keeping: white text on a bright cyan end can
    read 1.04:1 against a page that is nowhere near that colour.

    The stop's alpha is part of the answer, not decoration. `.nav button.active` is
    `linear-gradient(180deg, color-mix(in srgb, var(--primary) 26%, transparent), …)` — a 26% wash, not
    a solid fill — and reading it as opaque turns a ~13:1 selected row into a false 2.92:1 failure that
    would send a fix to the wrong file.
    """
    if not isinstance(value, str) or "gradient(" not in value:
        return []
    stops: list[tuple[float, float, float, float]] = []
    for match in re.finditer(r"(rgba?\([^)]+\)|color\(srgb[^)]+\))", value):
        parsed = parse_color(match.group(1))
        if parsed is not None:
            stops.append(parsed)
    return stops


def backdrop_candidates(layers: list[str], page_background: str,
                        images: list[str] | None = None) -> tuple[list[tuple[float, float, float]], bool]:
    """Every colour the glyph could actually be painted on, plus whether all of them were readable.

    Walking element-first, the *decider* is the first layer with a gradient, or the first opaque solid;
    whatever sits below it is composited, the decider's own colour(s) are placed on top, and any
    translucent layers between the text and the decider are blended last. A gradient yields its stops,
    not the page colour underneath: an earlier version listed every layer and scored white text on a
    green pill as 1.0:1 "against white", a backdrop that glyph never touches.
    """
    paints = list(images or [])
    while len(paints) < len(layers):
        paints.append("none")
    order = list(zip(layers, paints))            # element-first
    base = parse_color(page_background)
    if base is None:
        return [], False
    parsed: list[tuple[float, float, float, float] | None] = [parse_color(raw) for raw, _ in order]
    if any(item is None for item in parsed):
        return [], False

    decider: tuple[int, str, object] | None = None
    for index, (raw_color, raw_image) in enumerate(order):
        stops = parse_gradient_stops(raw_image)
        if stops:
            decider = (index, "gradient", stops)
            break
        if parsed[index][3] >= 1:                 # type: ignore[index]
            decider = (index, "solid", parsed[index])
            break

    if decider is None:
        current = (base[0], base[1], base[2])
        for entry in reversed(parsed):
            if entry is not None and entry[3] > 0:
                current = over(entry, current)
        return [current], True

    index, kind, payload = decider
    current = (base[0], base[1], base[2])
    for entry in reversed(parsed[index + 1:]):    # what lies beneath the decider, root-first
        if entry is not None and entry[3] > 0:
            current = over(entry, current)
    if kind == "solid":
        candidates = [over(payload, current)]     # type: ignore[arg-type]
    else:
        candidates = [over(stop, current) for stop in payload]  # type: ignore[union-attr]
    for entry in parsed[:index]:                  # translucent layers between text and decider
        if entry is not None and entry[3] > 0:
            candidates = [over(entry, candidate) for candidate in candidates]
    return candidates, True


def composite_backdrop(layers: list[str], page_background: str) -> tuple[tuple[float, float, float] | None, bool]:
    """The solid-only backdrop, kept for callers that have no gradient information."""
    candidates, ok = backdrop_candidates(layers, page_background)
    return (candidates[-1] if candidates else None), ok


def required_ratio(size_px: float, weight: str) -> float:
    """WCAG large text: 18pt (24px) at any weight, or 14pt bold (18.66px at 700+)."""
    try:
        bold = int(re.sub(r"[^\d]", "", weight or "") or 400) >= 700
    except ValueError:
        bold = False
    if size_px >= LARGE_PX or (size_px >= LARGE_BOLD_PX and bold):
        return AA_LARGE
    return AA_NORMAL


def node_contrast(node: dict, page_background: str) -> dict:
    """Attach `renderedRatio`, `requiredRatio`, `pass`, `floorOk` and a `status` to one harvested node.

    Every branch sets `floorOk`: a node whose colour cannot be read still has a font size, and an
    unreadable node must not slip out of the floor census as well as the contrast one.

    The reported ratio is the WORST candidate backdrop (see `backdrop_candidates`), so a glyph painted
    across a gradient is judged at its least favourable pixel rather than at a colour it never sits on.
    """
    size = float(node.get("size") or 0)
    disabled = bool(node.get("disabled"))
    base = {**node, "floorOk": size >= FLOOR_PX, "disabled": disabled}
    fg = parse_color(node.get("color") or "")
    candidates, ok = backdrop_candidates(node.get("bg") or [], page_background, node.get("bgImage"))
    if fg is None or not ok or not candidates:
        return {**base, "status": "unknown-colour", "pass": False}
    if fg[3] <= 0:
        return {**base, "status": "invisible-foreground", "pass": False}
    need = AA_DISABLED if disabled else required_ratio(size, str(node.get("weight") or ""))
    # Ancestor `opacity` multiplies into the painted glyph's alpha; the browser composites the whole
    # subtree, and folding it here is the same arithmetic seen a pixel further down.
    effective_alpha = fg[3] * float(node.get("opacity") or 1)
    painted = (fg[0], fg[1], fg[2], effective_alpha)
    ratio = min(contrast_ratio(over(painted, bg), bg) for bg in candidates)
    return {**base, "status": "ok", "renderedRatio": ratio, "requiredRatio": need,
            "pass": ratio >= need}


def exception_matches(path: str) -> str | None:
    for pattern, reason in FLOOR_EXCEPTIONS:
        if re.search(pattern, path or ""):
            return reason
    return None


# --------------------------------------------------------------------------- harvest


HARVEST_BODY = """(() => {
  const nodes = [];
  const pathOf = (el) => {
    const bits = [];
    let node = el;
    for (let depth = 0; node && node !== document.documentElement && depth < 4; depth += 1) {
      const name = node.tagName ? node.tagName.toLowerCase() : '';
      const cls = (typeof node.className === 'string' ? node.className.trim() : '')
          .split(/\\s+/).filter(Boolean).slice(0, 3).join('.');
      bits.push(name + (cls ? '.' + cls : ''));
      node = node.parentElement;
    }
    return bits.join(' > ');
  };
  for (const el of document.querySelectorAll('body *')) {
    const own = Array.from(el.childNodes)
        .filter((n) => n.nodeType === 3 && n.textContent.trim().length)
        .map((n) => n.textContent.trim());
    if (!own.length) continue;                       // text containers are judged by their leaf
    const r = el.getBoundingClientRect();
    if (!r.width || !r.height) continue;             // nothing painted, nothing to read
    if (r.bottom <= 0 || r.top >= innerHeight || r.right <= 0 || r.left >= innerWidth) continue;
    const cs = getComputedStyle(el);
    if (cs.display === 'none' || cs.visibility === 'hidden') continue;
    const bg = [];
    const bgImage = [];
    let gradient = false;
    let opacity = 1;
    for (let node = el; node; node = node.parentElement) {
      const style = getComputedStyle(node);
      bg.push(style.backgroundColor);
      bgImage.push(style.backgroundImage || 'none');
      if (style.backgroundImage && style.backgroundImage !== 'none') gradient = true;
      opacity *= parseFloat(style.opacity || '1');
    }
    const hiddenByAria = !!(el.closest && el.closest('[aria-hidden="true"]'));
    nodes.push({
      text: own[0].slice(0, 60), size: Math.round(parseFloat(cs.fontSize) * 100) / 100,
      weight: cs.fontWeight, color: cs.color, bg: bg, bgImage: bgImage, gradient: gradient,
      disabled: el.disabled === true || el.getAttribute('aria-disabled') === 'true',
      opacity: Math.round(opacity * 1000) / 1000, path: pathOf(el),
      ariaHidden: hiddenByAria ? 'true' : null, role: el.getAttribute('role') || null,
      rect: { w: Math.round(r.width), h: Math.round(r.height) },
    });
  }
  return {
    viewport: innerWidth + 'x' + innerHeight,
    theme: document.documentElement.className || 'dark',
    pageBackground: getComputedStyle(document.body).backgroundColor,
    htmlBackground: getComputedStyle(document.documentElement).backgroundColor,
    nodes: nodes,
  };
})()
"""


HARVEST = "JSON.stringify(" + HARVEST_BODY + ")"

MIN_VIEW_NODES = 12      # a lane rendering fewer readable nodes than this drew nothing but chrome
MIN_VIEWS = 20           # the rail is read live from the DOM; this floor only catches a sweep that
                         # visited a handful of lanes and still called itself "every view"
# The sentence the product prints when it cannot reach a snapshot. Its presence inside a lane means the
# lane's OWN surface was never rendered, so the nodes measured for that lane are shell, not content.
OFFLINE_PANEL_MARK = "读不到快照"


def views_expression(size_key: str) -> str:
    """Click every rail lane in one live session and harvest the screen each produces.

    The lane list is read from the rail itself rather than hardcoded here: the instrument then cannot
    quietly "pass" a subset while the product gained or lost a view. A single page load can only ever
    show one view, so the shipped census measured Overview and was described as the product (ERR-218);
    and a view that renders nothing is reported as a failure rather than as a silence an average hides.

    Each lane is harvested twice — at the top and after scrolling every scrollable region to its bottom —
    because the visibility filter in HARVEST_BODY only accepts painted nodes. Measured on 2026-10-19: the
    evidence lane contributed 42 nodes and a single handle-block node, so a green AA verdict said nothing
    about the 200 handle rows below the fold. The scroll pass also carries the horizontal-overflow reading,
    which no earlier check made at the 900px floor.
    """
    return ("(async () => {\n"
            "  const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));\n"
            "  const harvest = () => (" + HARVEST_BODY + ");\n"
            # The denominator the sampled node counts need: the same leaf predicate as the harvest, minus
            # the viewport-intersection test, so "143 nodes measured" can be read against "1,340 nodes
            # exist" instead of being mistaken for the whole screen.
            "  const presentLeaves = () => { let count = 0;\n"
            "      for (const el of document.querySelectorAll('body *')) {\n"
            "        const own = Array.from(el.childNodes)\n"
            "            .filter((n) => n.nodeType === 3 && n.textContent.trim().length);\n"
            "        if (!own.length) continue;\n"
            "        const r = el.getBoundingClientRect();\n"
            "        if (!r.width || !r.height) continue;\n"
            "        const cs = getComputedStyle(el);\n"
            "        if (cs.display === 'none' || cs.visibility === 'hidden') continue;\n"
            "        count += 1;\n"
            "      }\n"
            "      return count; };\n"
            "  const keyOf = (n) => [n.path, n.text, n.size, n.weight, n.color].join('|');\n"
            "  const merge = (a, b) => { const seen = new Set(a.map(keyOf)); const out = a.slice();\n"
            "      for (const n of b) { if (!seen.has(keyOf(n))) { seen.add(keyOf(n)); out.push(n); } } return out; };\n"
            "  const scrollers = () => { const seen = new Set(); const out = [];\n"
            "      for (const el of [document.scrollingElement, ...document.querySelectorAll('*')]) {\n"
            "        if (!el || seen.has(el) || el === document.body) continue;\n"
            "        if (el.scrollHeight <= el.clientHeight + 8) continue;   // nothing below the fold here\n"
            "        seen.add(el); out.push(el);\n"
            "      }\n"
            "      return out; };\n"
            "  const lanes = Array.from(document.querySelectorAll('.nav button[data-lane]'))\n"
            "      .map((b) => b.getAttribute('data-lane'));\n"
            "  const views = [];\n"
            "  for (const lane of lanes) {\n"
            "    const button = document.querySelector('.nav button[data-lane=\"' + lane + '\"]');\n"
            "    if (!button) { views.push({ lane: lane, error: 'NO_RAIL_BUTTON', nodes: [] }); continue; }\n"
            "    button.click();\n"
            "    await sleep(80);\n"
            "    const top = harvest();\n"
            "    let nodes = top.nodes;\n"
            "    const regions = scrollers().filter((el) => el.clientHeight > 200);\n"
            "    // Sweep each scrollable region in viewport-sized steps under a per-lane budget. The cap is\n"
            "    // the remaining budget, not a fixed number of screens: a 23,031px handle list at a 748px\n"
            "    // viewport needs ~82 steps across its regions, and a smaller constant left whole screens\n"
            "    // untraversed while still reporting a clean floor/AA verdict.\n"
            "    let budget = 96;\n"
            "    let sweepStopsUsed = 0;\n"
            "    let sweepStopsNeeded = 0;\n"
            "    let scrolledPx = 0;\n"
            "    let scrollablePx = 0;\n"
            "    for (const el of regions) {\n"
            "      const step = Math.max(200, Math.floor(el.clientHeight * 0.8));\n"
            "      const wanted = Math.max(1, Math.ceil(el.scrollHeight / step));\n"
            "      const stops = Math.min(wanted, budget);\n"
            "      sweepStopsNeeded += wanted;\n"
            "      scrollablePx += Math.max(0, el.scrollHeight - el.clientHeight);\n"
            "      scrolledPx += Math.min(stops * step, Math.max(0, el.scrollHeight - el.clientHeight));\n"
            "      for (let index = 1; index <= stops && budget > 0;\n"
            "           index += 1, budget -= 1, sweepStopsUsed += 1) {\n"
            "        el.scrollTop = index * step;\n"
            "        await sleep(35);\n"
            "        nodes = merge(nodes, harvest().nodes);\n"
            "      }\n"
            "      el.scrollTop = 0;\n"
            "    }\n"
            "    await sleep(35);\n"
            "    views.push({ lane: lane, error: null, theme: top.theme,\n"
            "        firstText: (top.nodes.length ? top.nodes[0].text : null),\n"
            "        pageBackground: top.pageBackground, nodes: nodes,\n"
            "        coverage: { atTop: top.nodes.length, afterScroll: nodes.length, scrolledRegions: regions.length,\n"
            "            presentNodes: presentLeaves(), sweepStopsUsed: sweepStopsUsed,\n"
            "            sweepStopsNeeded: sweepStopsNeeded,\n"
            "            scrollRangeCovered: scrollablePx ? Math.round(100 * scrolledPx / scrollablePx) : 100,\n"
            "            scrollWidth: document.documentElement.scrollWidth, innerWidth: window.innerWidth,\n"
            "            scrollHeight: document.documentElement.scrollHeight,\n"
            "            innerHeight: window.innerHeight } });\n"
            "  }\n"
            "  return JSON.stringify({ pageBackground: harvest().pageBackground,\n"
            "      sizes: { [" + json.dumps(size_key) + "]: window.innerWidth },\n"
            "      views: views });\n"
            "})()")


def pill_variants(views: list[dict]) -> dict[str, int]:
    """Which tone components were actually on screen.

    Found the hard way on 2026-10-10: a sweep that passes `every_text_node_meets_AA` over 980 nodes proved
    nothing about the status pills, because the run used the static preview and every lane had collapsed to
    the offline panel -- no `.tag` node existed anywhere. A count of what the sample contained is the only
    way a reader can tell "measured the pills" from "never saw the pills".
    """
    variants: dict[str, int] = {}
    for view in views:
        for node in view.get("nodes") or []:
            head = str(node.get("path") or "").split(" > ")[0]
            match = re.match(r"span\.(tag[\w.\-]*)", head)
            if match:
                variants[match.group(1)] = variants.get(match.group(1), 0) + 1
    return variants


def views_verdict(theme: str, collected: dict, size: int | None = None,
                  backend: str = "static") -> dict:
    """Pure: judge every view the rail produced, naming the view in every offender."""
    page_background = collected.get("pageBackground") or "rgb(0,0,0)"
    views = collected.get("views") or []
    scored = {view["lane"]: [node_contrast(n, page_background) for n in view.get("nodes") or []]
              for view in views}
    checks: list[dict] = []

    def add(name: str, ok: bool, detail: str) -> None:
        checks.append({"check": name, "pass": bool(ok), "detail": detail})

    widths = collected.get("sizes") or {}
    asked = f"{size}px" if size is not None else None
    if asked is not None:
        reported = widths.get(asked)
        add("window_is_the_width_asked", reported is not None and abs(reported - size) <= 2,
            f"asked={size}px innerWidth={reported} (Chrome clamps an invalid window size "
            f"rather than refusing it: {json.dumps(sorted(widths))})")
    missing = [view["lane"] for view in views if view.get("error")]
    add("every_lane_is_reachable_from_the_rail", not missing,
        f"lanes={len(views)} missing={json.dumps(missing)}")
    add("registered_views_were_all_attempted", len(views) >= MIN_VIEWS,
        f"views={len(views)} floor={MIN_VIEWS}")
    thin = [lane for lane, rows in scored.items() if len(rows) < MIN_VIEW_NODES]
    add("every_view_rendered_readable_text", not thin,
        "thin_views=" + json.dumps([f"{lane}={len(scored[lane])}" for lane in thin])[:400])

    overflow = []
    unscrolled = []
    uncovered = [view["lane"] for view in views
                 if not all(key in (view.get("coverage") or {})
                            for key in ("atTop", "afterScroll", "scrolledRegions", "scrollWidth",
                                        "presentNodes", "sweepStopsUsed", "sweepStopsNeeded",
                                        "scrollRangeCovered"))]
    add("coverage_was_reported", not uncovered,
        f"lanes_without_coverage={json.dumps(uncovered[:8])} -- the scroll sweep and the overflow reading "
        "come from the same harvest script, so a lane that reports neither means the below-the-fold "
        "population went unmeasured again")
    # A sampled count without its denominator invites the wrong reading: "2,933 nodes measured, 0 below the
    # floor" sounds like the product was checked when a lane with a 23,031px list was sampled for 143 nodes.
    # The invariant here is the one that cannot be argued with -- the sweep cannot have measured more leaf
    # text than the page contains, so a merge or dedup that double-counts convicts itself.
    sampled_total = sum(len(scored.get(view["lane"]) or []) for view in views)
    present_total = sum((view.get("coverage") or {}).get("presentNodes") or 0 for view in views)
    stops_used = sum((view.get("coverage") or {}).get("sweepStopsUsed") or 0 for view in views)
    stops_needed = sum((view.get("coverage") or {}).get("sweepStopsNeeded") or 0 for view in views)
    over_sampled = [f"{view['lane']}={len(scored.get(view['lane']) or [])}"
                    f"/{(view.get('coverage') or {}).get('presentNodes')}"
                    for view in views
                    if (view.get("coverage") or {}).get("presentNodes") is not None
                    and len(scored.get(view["lane"]) or []) > view["coverage"]["presentNodes"]]
    add("sampled_nodes_stay_within_the_measured_population",
        present_total > 0 and not over_sampled,
        f"sampled={sampled_total} present={present_total} over_sampled={json.dumps(over_sampled[:6])} "
        "-- `sampled` counts distinct (path, text, size, weight, colour) readings after the merge, so it is "
        "not a row count and must never be read as one: a table whose 200 rows repeat the same cell strings "
        "legitimately yields few distinct readings. The inequality is the point -- a sampled count above the "
        "leaf texts the page holds means the harvest double-counted.")
    untraversed = [f"{view['lane']}={(view.get('coverage') or {}).get('scrollRangeCovered')}%"
                   for view in views
                   if (view.get("coverage") or {}).get("scrollRangeCovered", 100) < 100]
    add("every_scrollable_range_was_traversed", not untraversed,
        f"stops={stops_used}/{stops_needed} lanes_short={json.dumps(untraversed[:8])} -- a lane whose "
        "scroll range was not walked to the end leaves text nobody measured, which is the same defect the "
        "12px floor and AA checks exist to catch, just silent.")
    for view in views:
        coverage = view.get("coverage") or {}
        width_gap = (coverage.get("scrollWidth") or 0) - (coverage.get("innerWidth") or 0)
        if width_gap > 1:
            overflow.append(f"{view['lane']}={width_gap}px")
        if (coverage.get("scrolledRegions") or 0) > 0 and \
                coverage.get("afterScroll") == coverage.get("atTop"):
            unscrolled.append(f"{view['lane']}({coverage.get('atTop')} nodes, "
                              f"{coverage.get('scrolledRegions')} regions)")
    add("no_horizontal_overflow_at_this_width", not overflow,
        f"width={size}px offenders={json.dumps(overflow[:8])}")
    if backend == "live":
        # Same scoping rule as `every_lane_reached_its_own_content`: under the static preview the lanes
        # collapse to the offline panel by design, so demanding that a scroll add text there would fail
        # `scripts/audit/reseal_wui_evidence.py`'s shell-typography runs for a reason that is not a defect.
        add("scrollable_lanes_gained_nodes_after_scrolling", not unscrolled,
            "a lane with a scrollable region that contributed no new text after the scroll pass means the "
            "below-the-fold content is still unsampled: "
            + json.dumps(unscrolled[:8]))
    else:
        add("scrollable_lanes_scanned", True,
            f"backend=static NOT_ENFORCED unsampled_lanes={json.dumps(unscrolled[:6])} -- the sweep is "
            "measuring shell typography here, not each lane's own surface")

    seen = pill_variants(views)
    stalled = [view["lane"] for view in views
               if any(OFFLINE_PANEL_MARK in str(node.get("text") or "")
                      for node in view.get("nodes") or [])]
    if backend == "live":
        add("every_lane_reached_its_own_content", not stalled,
            f"backend=live lanes_showing_offline_panel={json.dumps(stalled)} -- a lane that only prints the "
            "offline panel contributes no evidence about its own surface")
        add("tone_components_were_actually_on_screen", bool(seen),
            f"pillVariants={json.dumps(seen)} -- with no pill rendered, an AA pass says nothing about pill "
            "contrast (this is how DESIGN.md gap 12 stayed unmeasured while a sweep went green)")
    else:
        add("lane_content_reached", True,
            f"backend=static NOT_ENFORCED -- pills={json.dumps(seen)}; a static preview shows the offline "
            "panel per lane, so this run is evidence about chrome typography only")

    def across(predicate):
        return [(lane, n) for lane, rows in scored.items() for n in rows if predicate(n)]

    below = across(lambda n: not n["floorOk"] and exception_matches(n["path"]) is None)
    add("no_text_below_the_type_floor", not below,
        f"offenders={len(below)} "
        + json.dumps([f"{lane}:{n['size']}px {n['text'][:16]!r}" for lane, n in below[:6]],
                     ensure_ascii=False))
    unknown = across(lambda n: n["status"] == "unknown-colour")
    add("no_unparsable_colour", not unknown,
        f"unknown={len(unknown)} "
        + json.dumps([f"{lane}:{n['path'][:30]}" for lane, n in unknown[:5]], ensure_ascii=False))
    failed = across(lambda n: n["status"] == "ok" and not n["disabled"] and not n["pass"])
    invisible = across(lambda n: n["status"] == "invisible-foreground")
    add("every_text_node_meets_AA", not failed and not invisible,
        f"aa_failures={len(failed)} invisible={len(invisible)} worst="
        + json.dumps([f"{lane} {n['renderedRatio']}:1 need {n['requiredRatio']} {n['size']}px "
                      f"{n['text'][:18]!r}"
                      for lane, n in sorted(failed, key=lambda pair: pair[1]["renderedRatio"])[:6]],
                     ensure_ascii=False))
    disabled_bad = across(lambda n: n["status"] == "ok" and n["disabled"] and not n["pass"])
    add("disabled_text_is_still_legible", not disabled_bad,
        f"disabled={len(disabled_bad)} worst="
        + json.dumps([f"{lane} {n['renderedRatio']}:1 {n['text'][:18]!r}"
                      for lane, n in sorted(disabled_bad, key=lambda pair: pair[1]["renderedRatio"])[:5]],
                     ensure_ascii=False))

    total = sum(len(rows) for rows in scored.values())
    return {"theme": theme, "mode": "views", "passed": all(c["pass"] for c in checks),
            "checks": checks,
            "counts": {"views": len(views), "nodes": total, "aaFailures": len(failed),
                       "disabledFailures": len(disabled_bad), "belowFloor": len(below),
                       "thinViews": len(thin)}}


def require_settled(first: dict, second: dict, label: str, min_nodes: int) -> dict:
    """Two identical samples, or refuse. `.nav button`/`.panel`/the buttons transition `.2s ease`, so a
    single read can catch an interpolating colour that no user ever sees. A harvest thinner than
    `min_nodes` rendered nothing readable and is not a measurement."""
    a = {(n["path"], n["text"]): (n["color"], n["size"]) for n in first["nodes"]}
    b = {(n["path"], n["text"]): (n["color"], n["size"]) for n in second["nodes"]}
    shared = set(a) & set(b)
    moved = sorted(str(key) + f" {a[key]} vs {b[key]}" for key in shared if a[key] != b[key])
    if len(second["nodes"]) < min_nodes:
        raise RuntimeError(f"THIN_HARVEST({label}) only {len(second['nodes'])} text nodes "
                           f"(need {min_nodes}) — that surface rendered nothing readable")
    if moved:
        raise RuntimeError(f"NOT_SETTLED({label}) {len(moved)} of {len(shared)} nodes changed colour "
                           f"between samples: {moved[:3]}")
    return second


def harvest_settled(root: Path, browser: str, u19, u19_geometry, theme: str,
                    api: str | None = None, window_size: str = WINDOW_SIZE) -> dict:
    """Load one theme and require two identical samples before reporting anything.

    `.nav button`, `.list-item`, `.panel` and the buttons carry `transition:.2s ease` in the pinned
    skin, so the first sample after load can still be interpolating. Two equal samples is the minimum
    evidence that what was read is what a user sees.

    `api` points the page at a live v3 snapshot. Without it the shell renders only the offline card —
    33 text nodes — and every filled pill, disabled action button and KPI numeral stays unmeasured.
    A legibility gate that can only see the degraded state is measuring the one screen nobody reads.
    """
    path = (f"/index.html?view=full&theme={theme}&api={api}" if api
            else f"/index.html?view=full&mode=UNKNOWN&theme={theme}&shell=tauri")
    label = "live" if api else "static"
    first = u19_geometry.serve_and_eval(root, path, window_size, HARVEST, browser, u19)
    second = u19_geometry.serve_and_eval(root, path, window_size, HARVEST, browser, u19)
    settled = require_settled(first, second, label, MIN_NODES)
    settled["backend"] = api or "static-preview"
    return settled


def live_api_url(api: str, query: str, theme: str) -> str:
    """The URL shape the fixture origin builds, pointed at a backend that already serves the bundle.

    A sidecar started with `--frontend-root` serves the production `dist` and the real v3 snapshot from
    ONE loopback origin, which is the release line's own read-only browser entry — so a sweep taken
    through it measures the shipped bytes over real data instead of over the declared fixture.
    """
    encoded = urllib.parse.quote(f"{api.rstrip('/')}/api/v1/snapshot", safe="")
    return f"{api.rstrip('/')}/index.html?{query}&mode=UNKNOWN&theme={theme}&api={encoded}"


def harvest_shell_surface(strip, geometry, root: Path, browser: str, u19, fixture,
                          theme: str, surface: dict, api_base: str | None = None,
                          backend: str = "declared-fixture") -> dict:
    """One shell surface, populated either by the declared fixture or by a live backend, at its own shape.

    Same-origin is not a convenience: the front refuses a non-loopback `?api=`, and a second port would
    be a second origin the browser then blocks with CORS. Two launches per surface keep the settled-pair
    rule intact for these surfaces too — the strip's chips and rows animate on mount like the shell does.
    """
    url = (live_api_url(api_base, surface["query"], theme) if api_base
           else fixture.url_for(surface["query"], theme))
    width, height = surface["size"]
    first = geometry.serve_and_eval(root, "/index.html", WINDOW_SIZE, HARVEST, browser, u19, None,
                                    viewport=(width, height), serve_url=url,
                                    mount_selector=surface["mount"])
    second = geometry.serve_and_eval(root, "/index.html", WINDOW_SIZE, HARVEST, browser, u19, None,
                                     viewport=(width, height), serve_url=url,
                                     mount_selector=surface["mount"])
    settled = require_settled(first, second, f"{surface['label']}/{theme}", surface["minNodes"])
    settled["backend"] = backend
    return settled


def verdict(theme: str, harvest: dict, min_nodes: int = MIN_NODES,
            surface: str | None = None) -> dict:
    """Pure: no browser, no filesystem. Every check is one line of the written standard.

    `min_nodes` is the density floor for the surface being judged — the shell, a rail lane and a 150px
    strip are different sizes, and one number would convict the small one for being small. It defaults to
    the shell floor, so nothing that called this before changes behaviour.
    """
    page_background = harvest.get("pageBackground") or harvest.get("htmlBackground") or "rgb(0,0,0)"
    scored = [node_contrast(n, page_background) for n in harvest.get("nodes") or []]
    checks: list[dict] = []

    def add(name: str, ok: bool, detail: str) -> None:
        checks.append({"check": name, "pass": bool(ok), "detail": detail})

    add("harvest_is_dense_enough", len(scored) >= min_nodes,
        f"nodes={len(scored)} floor={min_nodes}"
        + (f" surface={surface}" if surface else ""))

    # A theme that did not apply would make the whole light-theme column meaningless and green.
    announced = harvest.get("theme")
    add("theme_actually_applied", announced == theme,
        f"asked={theme} html.class={announced!r}")

    below = [n for n in scored if not n["floorOk"]]
    unexcepted = [n for n in below if exception_matches(n["path"]) is None]
    add("no_text_below_the_type_floor", not unexcepted,
        f"below={len(below)} unexcepted={len(unexcepted)} "
        + json.dumps([f"{n['size']}px {n['path'][:60]} {n['text'][:24]!r}" for n in unexcepted[:6]],
                     ensure_ascii=False))

    unknown = [n for n in scored if n["status"] == "unknown-colour"]
    add("no_unparsable_colour", not unknown,
        f"unknown={len(unknown)} "
        + json.dumps([f"{n['path'][:40]} color={n.get('color')} bg={(n.get('bg') or [None])[0]}"
                      for n in unknown[:5]], ensure_ascii=False))

    failed_aa = [n for n in scored if n["status"] == "ok" and not n["disabled"] and not n["pass"]]
    failed_disabled = [n for n in scored if n["status"] == "ok" and n["disabled"] and not n["pass"]]
    invisible = [n for n in scored if n["status"] == "invisible-foreground"]
    add("every_text_node_meets_AA", not failed_aa and not invisible,
        f"aa_failures={len(failed_aa)} invisible={len(invisible)} worst="
        + json.dumps([f"{n['renderedRatio']}:1 need {n['requiredRatio']} {n['size']}px "
                      f"{n['path'][:44]} {n['text'][:20]!r}"
                      for n in sorted(failed_aa, key=lambda x: x["renderedRatio"])[:6]],
                     ensure_ascii=False))
    add("disabled_text_is_still_legible", not failed_disabled,
        f"disabled={len(failed_disabled)} (WCAG exempts inactive controls; a refusal this shell "
        f"deliberately displays must still be seen) worst="
        + json.dumps([f"{n['renderedRatio']}:1 {n['size']}px {n['path'][:40]} {n['text'][:18]!r}"
                      for n in sorted(failed_disabled, key=lambda x: x["renderedRatio"])[:5]],
                     ensure_ascii=False))

    stale = [(pattern, reason) for pattern, reason in FLOOR_EXCEPTIONS
             if not any(exception_matches(n["path"]) == reason for n in below)]
    add("no_stale_floor_exception", not stale,
        f"stale={[p for p, _ in stale]} (an exception that matches nothing is dead weight, not a rule)")

    gradient = [n for n in scored if n.get("gradient")]
    return {
        "theme": theme, "viewport": harvest.get("viewport"), "harvestedTheme": harvest.get("theme"),
        "passed": all(c["pass"] for c in checks), "checks": checks,
        "counts": {"nodes": len(scored), "belowFloor": len(below),
                   "unexceptedBelowFloor": len(unexcepted), "aaFailures": len(failed_aa),
                   "disabledFailures": len(failed_disabled),
                   "unknownColour": len(unknown), "gradientBackdrop": len(gradient),
                   "floorExceptions": len(below) - len(unexcepted)},
        "worst": [{"text": n["text"], "path": n["path"], "size": n["size"],
                   "ratio": n.get("renderedRatio"), "need": n.get("requiredRatio")}
                  for n in sorted((n for n in scored if "renderedRatio" in n),
                                  key=lambda x: x["renderedRatio"])[:10]],
    }


def crossfade_verdict(theme: str, samples: dict) -> dict:
    """Pure: judge the samples a theme switch produced, including the frames in between.

    The settled state is one clause of the standard; the other says the switch must not *pass through*
    colours nobody chose, which the first version of this instrument could not see — it deliberately
    refuses unsettled samples. The pinned skin eased colour for ~200-300ms and nav text measured 1.22:1
    inside that window, so `App.tsx` now holds transitions off for the two frames the swap needs. That
    is a mechanism, and a mechanism is only evidence if something reads the rendered values.
    """
    checks: list[dict] = []
    rows = []
    for label, nodes in (samples.get("samples") or []):
        for node in nodes:
            scored = node_contrast(node, samples.get("pageBackground") or "rgb(0,0,0)")
            rows.append({**scored, "sample": label,
                         "instant": node.get("instant"), "duration": node.get("duration")})

    def add(name: str, ok: bool, detail: str) -> None:
        checks.append({"check": name, "pass": bool(ok), "detail": detail})

    add("switch_was_observed", any(r["sample"] != "before" for r in rows),
        f"samples={len({r['sample'] for r in rows})}")

    mid = [r for r in rows if r["sample"] != "before"]
    sub_aa = [r for r in mid if "renderedRatio" in r and r["renderedRatio"] < r["requiredRatio"]]
    add("theme_switch_has_no_sub_aa_frame", bool(mid) and not sub_aa,
        f"mid_frames={len(mid)} sub_aa={len(sub_aa)} min="
        + str(min([r["renderedRatio"] for r in mid if "renderedRatio" in r], default=None))
        + " worst=" + json.dumps([f"{r['sample']} {r['renderedRatio']}:1 {r['path'][:30]}"
                                  for r in sub_aa[:4]], ensure_ascii=False))

    held = [r for r in mid if r.get("instant")]
    leaking = [r for r in held if (r.get("duration") or "0s") not in ("0s", "0.00s")]
    add("transitions_are_held_off_while_switching", bool(held) and not leaking,
        f"held_samples={len(held)} leaking={len(leaking)} "
        + json.dumps(sorted({r.get('duration') for r in leaking})[:4]))

    return {"theme": theme, "mode": "crossfade", "passed": all(c["pass"] for c in checks),
            "checks": checks, "counts": {"samples": len({r["sample"] for r in rows}),
                                         "nodes": len(rows)}}


CROSSFADE = """(async () => {
  const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
  const pick = () => Array.from(document.querySelectorAll('.nav button, .brand small, .topbar .search span'))
      .filter((el) => (el.textContent || '').trim().length)
      .slice(0, 40).map((el) => {
        const cs = getComputedStyle(el);
        const bg = [];
        for (let node = el; node; node = node.parentElement) bg.push(getComputedStyle(node).backgroundColor);
        return {
          text: (el.textContent || '').trim().slice(0, 30), size: parseFloat(cs.fontSize),
          weight: cs.fontWeight, color: cs.color, bg: bg, opacity: 1, gradient: false,
          path: el.tagName.toLowerCase() + '.' + (typeof el.className === 'string'
                ? el.className.trim().split(/\\s+/)[0] : ''),
          instant: document.documentElement.classList.contains('theme-instant'),
          duration: cs.transitionDuration,
        };
      });
  const toggle = Array.from(document.querySelectorAll('button'))
      .find((b) => /浅色|深色/.test((b.textContent || '')));
  if (!toggle) return JSON.stringify({error: 'NO_THEME_TOGGLE'});
  const out = [['before', pick()]];
  toggle.click();
  let elapsed = 0;
  for (const step of [0, 16, 50, 100, 200, 400]) {
    if (step) { await sleep(step); elapsed += step; }
    out.push(['t+' + elapsed + 'ms', pick()]);
  }
  await sleep(400);                       // let the new palette settle before the switch is undone
  toggle.click();
  await sleep(400);
  return JSON.stringify({
    samples: out,
    pageBackground: getComputedStyle(document.body).backgroundColor,
    themeAtStart: document.documentElement.className || 'dark',
  });
})()"""


def crossfade_measure(root: Path, browser: str, u19, geometry) -> dict:
    """Click the theme control in one live session and keep every frame the switch produced."""
    raw = geometry.serve_and_eval(root, "/index.html?view=full&mode=UNKNOWN&theme=dark&shell=tauri",
                                  WINDOW_SIZE, CROSSFADE, browser, u19)
    if raw.get("error"):
        raise RuntimeError(f"CROSSFADE_{raw['error']}")
    if not raw.get("samples"):
        raise RuntimeError("CROSSFADE_NO_SAMPLES")
    return raw


def run_views_session(geometry, root, browser, u19, path, window, size, expr, theme, api,
                      attempts=2):
    """Open the whole-rail sweep in its own browser session, retrying a bounded number of times.

    Measured twice on the runner and never on the development host: the session dies within seconds of the
    geometry gate's own session closing (`LEGIBILITY_GATE_NOT_RUN views/dark at 1280px TimeoutError` 16 s
    after a green geometry step at 9513c216; the light theme at ed7b8fa6), while the same bundle sweeps clean
    in three other runs. A second session is the cheapest honest discriminator: a page or product defect
    repeats, a launch race does not. Every attempt is printed with its traceback and counted in the receipt,
    so a retry is a recorded fact, not a hidden re-roll — and if all attempts fail this still raises, and the
    step still exits 3 as NOT_RUN.
    """
    last: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            collected = geometry.serve_and_eval(root, path, window, expr, browser, u19,
                                                viewport=(size, 820),
                                                evaluate_timeout_s=SWEEP_EVALUATE_TIMEOUT_S)
        except Exception as exc:  # noqa: BLE001 -- every attempt is reported before it is retried
            last = exc
            print(f"LEGIBILITY_SWEEP_ATTEMPT {theme} {size}px attempt={attempt}/{attempts} {exc!r}")
            traceback.print_exc()
            continue
        collected["sweepAttempts"] = attempt
        return collected
    raise last if last is not None else RuntimeError("no sweep attempt was made")


def probe_live_api(api: str) -> dict:
    """Read the backend the operator pointed at and return the population it actually serves.

    Refuses (raises) on anything that is not loopback http answering a `workflow/snapshot/v3` payload: a
    sweep against a dead URL would render the offline card, and an offline card has perfectly readable
    text — so every floor would pass while measuring nothing. Counts are reported, never bodies.
    """
    parsed = urllib.parse.urlparse(api)
    if parsed.scheme != "http" or parsed.hostname not in ("127.0.0.1", "localhost", "::1"):
        raise ValueError(f"LIVE_API_NOT_LOOPBACK {api!r}")
    url = f"{api.rstrip('/')}/api/v1/snapshot"
    with urllib.request.urlopen(url, timeout=10) as response:
        served = json.loads(response.read().decode("utf-8"))
    if served.get("schemaVersion") != "workflow/snapshot/v3":
        raise ValueError(f"LIVE_API_NOT_V3 schemaVersion={served.get('schemaVersion')!r} at {url} "
                         "(the surfaces swept here are the v3 contract's; an older payload renders a "
                         "different page and its legibility would not be this product's)")
    return {"api": api,
            "schemaVersion": served.get("schemaVersion"),
            "revision": served.get("revision"),
            "adapters": len(served.get("adapterCapabilities") or []),
            "projects": len(served.get("projects") or []),
            "executions": len(served.get("executions") or [])}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=str(ROOT))
    ap.add_argument("--json-out", default=None)
    ap.add_argument("--crossfade", action="store_true",
                    help="click the theme control and judge the frames it produces, not the settled page")
    ap.add_argument("--live-backend", action="store_true",
                    help="serve a real v3 snapshot through the release line's sidecar instead of the static preview")
    ap.add_argument("--all-views", action="store_true",
                    help="click every rail lane and judge each view it produces, not just the landing view")
    ap.add_argument("--sizes", default="1280",
                    help="comma-separated window widths in CSS px to sweep with --all-views. The "
                         "surfaces the product can take are 1280 (main default), 900 (main "
                         "minWidth/minHeight floor) and 440 (the HUD); narrower values are legal as "
                         "text stress but are not product surfaces (SCREEN_SPEC: Window surfaces).")
    ap.add_argument("--shell-surfaces", action="store_true",
                    help="also judge the shell surfaces the narrow-strip gate declares — the 150x480 "
                         "HUD strip, the 440x680 panel and the 1280x820 daily entry — populated by that "
                         "gate's declared fixture snapshot. Without this flag the sweep reads only the "
                         "professional shell at `view=full`/`view=overview`, which is how the 12px floor "
                         "and AA standard went unmeasured on the two surfaces owners actually look at.")
    ap.add_argument("--api", default=None,
                    help="measure against this ALREADY RUNNING loopback v3 backend (a sidecar started "
                         "with --frontend-root, so it serves the shipped bundle and the real snapshot "
                         "from one origin) instead of the declared fixture. The URL is probed before any "
                         "browser starts: an unreachable or non-v3 backend is bad input, because a page "
                         "that silently fell back to the offline card would still have readable text.")
    args = ap.parse_args()
    try:
        sizes = [int(token) for token in args.sizes.split(",") if token.strip()]
    except ValueError:
        print(f"LEGIBILITY_GATE_NOT_RUN BAD_SIZES {args.sizes!r}")
        return 2
    if not sizes or any(size < 320 or size > 2560 for size in sizes):
        print(f"LEGIBILITY_GATE_NOT_RUN BAD_SIZES {args.sizes!r} (each must be 320..2560)")
        return 2

    live_population = None
    if args.api:
        try:
            live_population = probe_live_api(args.api)
        except Exception as exc:  # noqa: BLE001 — a backend the operator named is bad input, not a skip
            print(f"LEGIBILITY_GATE_NOT_RUN LIVE_API {type(exc).__name__} {exc}")
            return 2

    root = Path(args.root).resolve()
    if not (root / "apps/observer/frontend/dist/index.html").is_file():
        print(f"LEGIBILITY_GATE_NOT_RUN DIST_ABSENT {root/'apps/observer/frontend/dist'}")
        return 3
    geometry = load_geometry()
    browser = geometry.find_browser()
    if not browser:
        print("LEGIBILITY_GATE_NOT_RUN BROWSER_NOT_FOUND set WL_CHROME to a Chrome/Edge binary")
        return 3
    u19 = geometry.load_u19()

    if args.crossfade:
        try:
            raw = crossfade_measure(root, browser, u19, geometry)
        except Exception as exc:  # noqa: BLE001
            print(f"LEGIBILITY_GATE_NOT_RUN CROSSFADE {exc!r}")
            return 3
        reports = [{"theme": "dark->light", "verdict": crossfade_verdict("dark->light", raw),
                    "samples": raw, "browser": browser}]
    else:
        reports = []
        api = None
        server = None
        if args.api:
            api = live_population["api"]
            print(f"LEGIBILITY_BACKEND {api} "
                  f"adapters={live_population['adapters']} projects={live_population['projects']} "
                  f"executions={live_population['executions']} revision={live_population['revision']}")
        elif args.live_backend:
            # The release line's own sidecar starter, on a dynamic loopback port, serving the real v3
            # snapshot. Read-only: this is the projection the Observer is allowed to read.
            _sidecar, port, _thread, server = u19.start_sidecar()
            api = f"http://127.0.0.1:{port}"
            print(f"LEGIBILITY_BACKEND {api}")
        try:
            for theme in THEMES:
                if args.all_views:
                    # `sizes`, not `args.sizes`: iterating the raw "1280,700,430" string once per
                    # character asked Chrome for a 1px, 2px, comma-wide window each, it clamped
                    # silently, and the run reported twelve confident measurements of nothing.
                    for size in sizes:
                        # The outer window stays comfortably wide; the *layout* width is imposed by
                        # device metrics, because Chrome clamps a narrow `--window-size` rather than
                        # refusing it (430 asked, 482 delivered).
                        window = f"{max(size, 1000)},900"
                        path = (f"/index.html?view=overview&theme={theme}&api={api}" if api
                                else f"/index.html?view=overview&mode=UNKNOWN&theme={theme}&shell=tauri")
                        try:
                            collected = run_views_session(geometry, root, browser, u19, path, window,
                                                          size, views_expression(f"{size}px"),
                                                          theme, api)
                        except Exception as exc:  # noqa: BLE001 — a failed measurement is NOT_RUN, never a pass
                            print(f"LEGIBILITY_GATE_NOT_RUN views/{theme} at {size}px {exc!r}")
                            return 3
                        reports.append({"theme": f"{theme}-views-{size}px",
                                        "verdict": views_verdict(theme, collected, size,
                                                                 "live" if (args.live_backend or args.api)
                                                                 else "static"),
                                        "backend": "live" if (args.live_backend or args.api) else "static",
                                        "collected": collected, "browser": browser})
                    continue
                try:
                    harvest = harvest_settled(root, browser, u19, geometry, theme, api=api)
                except Exception as exc:  # noqa: BLE001 — a failed measurement is NOT_RUN, never a silent pass
                    print(f"LEGIBILITY_GATE_NOT_RUN {theme} {exc!r}")
                    traceback.print_exc()
                    return 3
                reports.append({"theme": theme, "verdict": verdict(theme, harvest),
                                "harvest": harvest, "browser": browser})
            if args.shell_surfaces:
                strip = load_strip_gate()
                surfaces = shell_surfaces(strip)
                # A supplied live entry already serves the shipped bundle and the real snapshot from one
                # loopback origin, so the fixture origin is not started at all. Without `--api` the sweep
                # reads the declared fixture, exactly as CI does.
                fixture = (None if args.api else
                           strip.SnapshotFixture(root / "apps/observer/frontend/dist"))
                if fixture is not None:
                    fixture.start()
                shell_backend = "live-api" if args.api else "declared-fixture"
                shell_data = f"live backend {args.api}" if args.api else "declared fixture snapshot"
                try:
                    for theme in THEMES:
                        for surface in surfaces:
                            try:
                                harvest = harvest_shell_surface(strip, geometry, root, browser, u19,
                                                                fixture, theme, surface,
                                                                api_base=args.api,
                                                                backend=shell_backend)
                            except Exception as exc:  # noqa: BLE001 — NOT_RUN, never a quiet skip
                                print(f"LEGIBILITY_GATE_NOT_RUN shell/{surface['label']}/{theme} "
                                      f"{exc!r}")
                                return 3
                            label = f"{theme}-{surface['label']}"
                            reports.append({
                                "theme": label,
                                "verdict": verdict(theme, harvest, surface["minNodes"],
                                                   surface["label"]),
                                "harvest": harvest, "browser": browser,
                                "surface": {"declaredSize": list(surface["size"]),
                                            "minNodes": surface["minNodes"],
                                            "data": shell_data}})
                finally:
                    if fixture is not None:
                        fixture.stop_server()
        finally:
            if server is not None:
                server.shutdown()

    out = Path(args.json_out) if args.json_out else (
        OUT_DIR / f"legibility_{int(time.time())}.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    # Every row says which bytes it rendered: a legibility verdict is a claim about a stylesheet, and a
    # rebuild moves the stylesheet under it without telling it (found 2026-10-10).
    bundle = bundle_provenance.describe(ROOT)
    for row in reports:
        row["servedBundle"] = bundle
    out.write_text(json.dumps(reports, indent=2, ensure_ascii=False), encoding="utf-8")

    ok = all(r["verdict"]["passed"] for r in reports)
    for report in reports:
        v = report["verdict"]
        print(f"{report['theme']:<18} viewport={v.get('viewport', '-')} "
              f"counts={json.dumps(v['counts'])}")
        for check in v["checks"]:
            print(f"  {check['check']:<34} {'PASS' if check['pass'] else 'FAIL'} {check['detail']}")
        if "harvestedTheme" in v and v["harvestedTheme"] != v["theme"]:
            print(f"  THEME_ANNOUNCEMENT_MISMATCH asked={v['theme']} html.class={v['harvestedTheme']}")
    print(("LEGIBILITY_GATE_PASS " if ok else "LEGIBILITY_GATE_FAIL ") + str(out))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
