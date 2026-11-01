#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Extract the DESIGN-LAB brand mark from the owner's black-and-white artwork and
inline it into the served stylesheet as a data URI.

Why a data URI and not an asset route: src/design_lab/workbench.py serves a fixed
three-path allowlist ("never serve arbitrary paths or project assets") and its CSP
says `img-src data:`. A new /workbench/*.png route would mean widening both. The
stylesheet is already a served route, so the mark travels inside it.

The lockup has three ink bands (monogram / DESIGN-LAB / 设计实验室). Only the
monogram is used here: the brand slot is a 48px square and a 1088x117 wordmark does
not survive that reduction. The bands are found by measuring the image, not by
hardcoded coordinates.

Usage:
    python design-lab/scripts/render_brand_asset.py --source <BW artwork> [--check]
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import re
import sys
from pathlib import Path

import numpy as np
from PIL import Image

REPO = Path(__file__).resolve().parents[2]
BRAND_DIR = REPO / 'apps' / 'workbench' / 'brand'
PNG_PATH = BRAND_DIR / 'design-lab-mark.png'
MARK_PATH = BRAND_DIR / 'design-mark.svg'
PROVENANCE = BRAND_DIR / 'PROVENANCE.json'
CSS_PATH = REPO / 'apps' / 'workbench' / 'style.css'
HTML_PATH = REPO / 'apps' / 'workbench' / 'index.html'
CANVAS = 144          # square output canvas; the tile renders it at 48px (3x)
GLYPH_FILL = 0.86     # fraction of the canvas the glyph occupies
LO, HI = 64.0, 192.0  # luminance ramp: below LO is transparent, above HI is solid
BEGIN = '/* brand-mark:begin sha256='
END = '/* brand-mark:end */'
FAVICON_BEGIN = '<!-- brand-favicon:begin sha256='
FAVICON_END = '<!-- brand-favicon:end -->'


def bands(mask: np.ndarray) -> list[tuple[int, int]]:
    """Row spans that carry ink, in y order. Ink fraction > 0.2% of the row."""
    rows = (mask.mean(axis=1) > 0.002)
    out, start = [], None
    for y, on in enumerate(rows):
        if on and start is None:
            start = y
        elif not on and start is not None:
            out.append((start, y - 1))
            start = None
    if start is not None:
        out.append((start, len(rows) - 1))
    return out


def extract(source: Path) -> tuple[bytes, dict]:
    im = Image.open(source)
    if im.mode not in ('L', 'LA', 'RGB', 'RGBA'):
        raise SystemExit(f'BRAND_SOURCE_UNUSABLE {im.mode}')
    lum = np.asarray(im.convert('L'), dtype=np.float32)
    alpha = np.clip((lum - LO) / (HI - LO), 0.0, 1.0)
    found = bands(alpha > 0.5)
    if not found:
        raise SystemExit('BRAND_SOURCE_HAS_NO_INK')
    # The monogram is the band closest to square -- not "the first band", which would
    # silently become the wordmark if the artwork were ever cropped above it.
    def squareness(span):
        y0, y1 = span
        box = alpha[y0:y1 + 1] > 0.5
        xs = np.where(box.any(axis=0))[0]
        w, h = xs.max() - xs.min() + 1, y1 - y0 + 1
        return max(w / h, h / w)

    y0, y1 = min(found, key=squareness)
    box = alpha[y0:y1 + 1] > 0.0
    xs = np.where(box.any(axis=0))[0]
    ys = np.where(box.any(axis=1))[0]
    x0, x1 = xs.min(), xs.max()
    crop = alpha[y0 + ys.min():y0 + ys.max() + 1, x0:x1 + 1]
    ch, cw = crop.shape
    side = CANVAS
    glyph = int(round(side * GLYPH_FILL))
    scale = glyph / max(cw, ch)
    nw, nh = max(1, int(round(cw * scale))), max(1, int(round(ch * scale)))
    rgba = np.zeros((side, side, 4), dtype=np.uint8)
    resampled = Image.fromarray((crop * 255).astype(np.uint8), 'L').resize(
        (nw, nh), Image.LANCZOS)
    pad = np.pad(np.asarray(resampled, dtype=np.uint8),
                 ((0, nh % 2), (0, nw % 2)))  # keep the centre exact on odd sizes
    ph, pw = pad.shape
    top, left = (side - ph) // 2, (side - pw) // 2
    rgba[top:top + ph, left:left + pw] = np.dstack(
        [np.full(pad.shape, 255, np.uint8)] * 3 + [pad])
    out = Image.fromarray(rgba, 'RGBA')
    png = _encode(out)
    return png, {
        'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
        'source_size': list(im.size),
        'monogram_band': [int(x0), int(y0 + ys.min()), int(x1), int(y0 + ys.max())],
        'monogram_source_px': [int(cw), int(ch)],
        'canvas_px': side,
        'glyph_px': [int(pw), int(ph)],
        'luminance_ramp': [LO, HI],
    }


def _encode(im: Image.Image) -> bytes:
    from io import BytesIO
    buf = BytesIO()
    im.save(buf, 'PNG', optimize=True)
    return buf.getvalue()


def css_block(png: bytes) -> str:
    """The generated region, as declarations inside the existing `:root` block.

    It is a token, not a second `:root` rule: design-lab/tests/
    test_workbench_css_single_definition.py fails on a selector defined twice, and the
    cascade would make the later block the winner for every token in it.
    """
    digest = hashlib.sha256(png).hexdigest()
    uri = 'data:image/png;base64,' + base64.b64encode(png).decode('ascii')
    return (f'  {BEGIN}{digest} */\n'
            f'  --brand-mark:url("{uri}");\n'
            f'  {END}\n')


REGION = re.compile(r'[ \t]*' + re.escape(BEGIN) + r'[0-9a-f]{64} \*/.*?'
                    + re.escape(END) + r'\n?', re.S)


def patch_css(text: str, block: str) -> str:
    found = REGION.findall(text)
    if len(found) != 1:
        # Two regions would mean the generator rewrites one and the page reads the
        # other -- the stale copy wins by cascade order and nothing says so.
        raise SystemExit(f'BRAND_CSS_REGION_COUNT={len(found)} (exactly one is required)')
    return REGION.sub(lambda _: block, text, count=1)


#: The two inks the managed CSS block is checked for. They are not restated here as a free choice:
#: `--check` below asserts the stylesheet carries exactly these, so the favicon and the stylesheet
#: cannot drift into two different brand colours without one of the two failing.
BRAND_INKS = {'paper': '#EEF2F5', 'ink': '#17212B'}
PATH_TOKEN = b'<path '
VIEW_BOX = re.compile(r'viewBox="([-\d.]+) ([-\d.]+) ([-\d.]+) ([-\d.]+)"')
FAVICON_REGION = re.compile(r'[ \t]*' + re.escape(FAVICON_BEGIN) + r'[0-9a-f]{64} -->.*?'
                            + re.escape(FAVICON_END) + r'\n?', re.S)


def favicon_svg(mark: bytes) -> bytes:
    """Compose the tab icon out of the tracked vector, adding no new drawing.

    Exactly two things change relative to `apps/workbench/brand/design-mark.svg`, and both are
    derived rather than typed:

    * the ink flips from `#17212B` to `#EEF2F5`, because a glyph is invisible on a browser tab
      whose chrome can be either light or dark; the tile carries the colour instead;
    * one `<rect>` is inserted as the tile, its `x/y/width/height` read straight out of the
      tracked `viewBox` and its `rx` one third of the shorter side -- the same ratio the shipped
      48px tile uses in CSS (`border-radius:16px`), so the icon is the mark the interface already
      draws, not a second interpretation of the brand.

    The `<path d=...>` payload is left byte-identical on purpose, which is what lets
    `design-lab/tests/test_workbench_brand_asset.py` assert both surfaces come from one source
    instead of trusting a comment that says so.
    """
    match = VIEW_BOX.search(mark.decode('utf-8'))
    if not match:
        raise SystemExit('BRAND_FAVICON_SOURCE_UNREADABLE the tracked svg carries no parseable '
                         'viewBox, so no tile geometry can be derived from it')
    x, y, width, height = (float(v) for v in match.groups())
    rx = round(min(width, height) / 3, 2)
    text = mark.decode('utf-8')
    if f'fill="{BRAND_INKS["ink"]}"' not in text:
        raise SystemExit(f'BRAND_FAVICON_SOURCE_UNREADABLE the tracked svg does not carry '
                         f'{BRAND_INKS["ink"]}, so the ink flip has nothing to flip')
    reinked = text.replace(f'fill="{BRAND_INKS["ink"]}"', f'fill="{BRAND_INKS["paper"]}"')
    tile = (f'<rect x="{x}" y="{y}" width="{width}" height="{height}" rx="{rx}" '
            f'fill="{BRAND_INKS["ink"]}"/>')
    head, _, body = reinked.partition('>')
    composed = f'{head}>{tile}{body}'
    if composed.count('<path ') != mark.count(b'<path '):
        raise SystemExit('BRAND_FAVICON_GEOMETRY_MOVED the composed icon no longer carries the '
                         'tracked path count; this composes, it does not redraw')
    return composed.encode('utf-8')


def favicon_block(svg: bytes) -> str:
    """The managed HTML region: a `data:` URI, so no new served path and no CSP widening."""
    digest = hashlib.sha256(svg).hexdigest()
    uri = 'data:image/svg+xml;base64,' + base64.b64encode(svg).decode('ascii')
    return (f'{FAVICON_BEGIN}{digest} -->\n'
            f'<link rel="icon" type="image/svg+xml" href="{uri}">\n'
            f'{FAVICON_END}\n')


def patch_html(text: str, block: str) -> str:
    if FAVICON_REGION.search(text):
        found = FAVICON_REGION.findall(text)
        if len(found) != 1:
            raise SystemExit(f'BRAND_FAVICON_REGION_COUNT={len(found)} (exactly one is required)')
        return FAVICON_REGION.sub(lambda _: block, text, count=1)
    if text.count('<title>') != 1:
        raise SystemExit('BRAND_FAVICON_ANCHOR_UNSAFE <title> is not unique, so the region '
                         'cannot be placed deterministically')
    return text.replace('<title>', block + '<title>', 1)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--source', type=Path)
    ap.add_argument('--check', action='store_true')
    ap.add_argument('--sync-favicon', action='store_true')
    args = ap.parse_args(argv)

    if args.check:
        # The shipped mark is now the owner's vector, not a bitmap cut-out: the token derives from
        # apps/workbench/brand/design-mark.svg, so the check follows that byte-for-byte. The PNG
        # pipeline below is kept for provenance of the superseded asset, and a checker that still
        # hashed it would either fail on a correct stylesheet or pass on a stale one.
        mark_path = MARK_PATH
        if not mark_path.is_file():
            print('BRAND_ASSET_MISSING design-mark.svg is not on disk')
            return 1
        mark = mark_path.read_bytes()
        css = CSS_PATH.read_text(encoding='utf-8')
        m = re.search(r'[ \t]*' + re.escape(BEGIN) + r'([0-9a-f]{64}) \*/.*?'
                      r'--brand-mark-paper:url\("data:image/svg\+xml;base64,([A-Za-z0-9+/=]*)"\);\s*'
                      r'--brand-mark-ink:url\("data:image/svg\+xml;base64,([A-Za-z0-9+/=]*)"\);\s*'
                      r'--brand-mark:var\(--brand-mark-(paper|ink)\);.*?'
                      + re.escape(END), css, re.S)
        if not m:
            print('BRAND_CSS_REGION_UNREADABLE the managed block no longer carries the two '
                  'svg encodings plus the default selection this check expects')
            return 1
        claimed, paper_b64, ink_b64, default_variant = m.group(1), m.group(2), m.group(3), m.group(4)
        problems = []
        if hashlib.sha256(mark).hexdigest() != claimed:
            problems.append('the tracked design-mark.svg no longer matches the digest the css claims')
        for name, blob, want_fill in (('paper', paper_b64, '#EEF2F5'), ('ink', ink_b64, '#17212B')):
            decoded = base64.b64decode(blob)
            if b'<path d=' not in decoded:
                problems.append(f'--brand-mark-{name} is not a path-bearing svg')
                continue
            if decoded.replace(b' ', b'').count(b'<path') < 1:
                problems.append(f'--brand-mark-{name} carries no path geometry')
            if ('fill="%s"' % want_fill).encode() not in decoded:
                problems.append(f'--brand-mark-{name} does not carry the {want_fill} ink it claims')
            if b'viewBox' not in decoded:
                problems.append(f'--brand-mark-{name} lost its viewBox, so it cannot scale to the tile')
        source_paths = mark.count(b'<path ')
        for name, blob in (('paper', paper_b64), ('ink', ink_b64)):
            got = base64.b64decode(blob).count(b'<path ')
            if got != source_paths:
                problems.append(f'--brand-mark-{name} carries {got} paths, the tracked svg has '
                                f'{source_paths}')
        if default_variant != 'paper':
            problems.append('the default --brand-mark must be the paper glyph, because the '
                            'shipped palette is charcoal; a light palette has to opt in explicitly')
        # Every `--brand-mark:var(--brand-mark-ink)` outside the managed block is one light palette
        # opting in; the block's own default is the paper glyph, so it never appears there and no
        # correction term is needed. (An earlier draft subtracted one and so convicted a correct
        # stylesheet of being one palette short.)
        light_flips = len(re.findall(r'--brand-mark:var\(--brand-mark-ink\);', css))
        if light_flips < 2:
            problems.append(f'only {light_flips} light palette(s) opt into the ink glyph; both '
                            'ui2026/light and stitch/light must, or the mark is invisible there')
        if problems:
            print('BRAND_CSS_STALE: ' + '; '.join(problems))
            return 1
        # The tab icon is covered by the same command as the stylesheet token, because the two
        # surfaces fail in the same way: someone edits one copy and the managed digest still
        # matches the source it names. Checking only the CSS would leave the favicon free to drift
        # into a second drawing of the brand, which is the outcome the owner list reserves for a
        # ruling -- so the check recomposes the icon from the tracked vector and compares bytes.
        html = HTML_PATH.read_text(encoding='utf-8')
        fmatch = re.search(r'[ \t]*' + re.escape(FAVICON_BEGIN) + r'([0-9a-f]{64}) -->\n'
                          r'<link rel="icon" type="image/svg\+xml" '
                          r'href="data:image/svg\+xml;base64,([A-Za-z0-9+/=]*)">\n'
                          + re.escape(FAVICON_END), html)
        if fmatch is None:
            print('BRAND_FAVICON_REGION_UNREADABLE index.html does not carry exactly one managed '
                  'favicon region in the shape this check expects')
            return 1
        if html.count(FAVICON_BEGIN) != 1:
            print(f'BRAND_FAVICON_REGION_COUNT={html.count(FAVICON_BEGIN)} '
                  '(exactly one is required)')
            return 1
        claimed_favicon = base64.b64decode(fmatch.group(2))
        expected = favicon_svg(mark)
        fproblems = []
        if hashlib.sha256(claimed_favicon).hexdigest() != fmatch.group(1):
            fproblems.append('the pinned digest does not match the pinned bytes')
        if claimed_favicon != expected:
            fproblems.append('the icon in index.html is not what the tracked vector composes to '
                             'now -- one copy moved and the other did not')
        if claimed_favicon.count(b'<path ') != mark.count(b'<path '):
            icon_paths = claimed_favicon.count(PATH_TOKEN)
            source_paths_in_mark = mark.count(PATH_TOKEN)
            fproblems.append(f'the icon carries {icon_paths} paths, the tracked svg has '
                             f'{source_paths_in_mark}')
        if fproblems:
            print('BRAND_FAVICON_STALE: ' + '; '.join(fproblems))
            return 1
        print(f'BRAND_ASSET=OK svg={len(mark)}B paths={source_paths} encodings=2 '
              f'default={default_variant} light_flips={light_flips} '
              f'favicon={len(claimed_favicon)}B composed_from_source=yes')
        return 0

    if args.sync_favicon:
        if not MARK_PATH.is_file():
            print('BRAND_ASSET_MISSING design-mark.svg is not on disk')
            return 1
        mark = MARK_PATH.read_bytes()
        html = HTML_PATH.read_text(encoding='utf-8')
        patched = patch_html(html, favicon_block(favicon_svg(mark)))
        HTML_PATH.write_text(patched, encoding='utf-8', newline='')
        print(f'BRAND_FAVICON=SYNCED bytes={len(html)} -> {len(patched)} '
              f'region={"replaced" if FAVICON_REGION.search(html) else "inserted"}')
        return 0

    if not args.source or not args.source.is_file():
        print('BRAND_SOURCE_REQUIRED -- an existing --source path is needed to regenerate')
        return 2
    BRAND_DIR.mkdir(parents=True, exist_ok=True)
    png, meta = extract(args.source)
    before = PNG_PATH.read_bytes() if PNG_PATH.is_file() else None
    PNG_PATH.write_bytes(png)
    PROVENANCE.write_bytes((json.dumps(meta, indent=2) + '\n').encode('utf-8'))
    css = CSS_PATH.read_text(encoding='utf-8')
    CSS_PATH.write_text(patch_css(css, css_block(png)), encoding='utf-8', newline='')
    same = 'unchanged' if before == png else 'rewritten'
    print(f'BRAND_ASSET=OK png={len(png)}B ({same}) canvas={meta["canvas_px"]} '
          f'glyph={meta["glyph_px"]} from {meta["monogram_source_px"]}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
