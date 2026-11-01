# SPDX-License-Identifier: MIT
"""The brand mark in the stylesheet is the tracked vector, and nothing else.

The Workbench carries the owner's logo as an SVG data URI inside `style.css` rather than as
an asset route, because src/design_lab/workbench.py serves a fixed three-path allowlist
under `img-src data:`. That makes the shipped stylesheet hold bytes that no editor
should be trusted to keep in sync with the asset they came from, so the sync is checked
here -- through design-lab/scripts/render_brand_asset.py's own `--check`, which is the
single owner of the predicate (this module imports it rather than re-deriving it).

The asset changed shape mid-round: a 144x144 PNG cut-out produced by a brightness-threshold
pipeline was replaced by the owner's vector, and this module was not re-run then, so four of
its cases went red on the first exact-SHA cloud run after the switch (design-lab/tests/
test_workbench_brand_asset.py was not in the 76-gate rollup, which is why "aggregate green"
never exercised it). They now grade the vector: the encoded payload, its path count, its
single brand ink per encoding, its viewBox identity with the tracked file, and the digest the
provenance record claims.

What each case is for:
  * the tree passes `--check`, and the ways it can rot (payload swapped, digest claim
    swapped, asset file absent) each make it fail -- a check that cannot be disturbed
    guards nothing;
  * exactly one region exists, inside `:root`, and every named consumer uses the token;
  * the mark is a two-path glyph drawn in one ink, identical between its two encodings;
  * the mechanism that forces inlining is still the mechanism: if an asset route is ever
    added, this test says so instead of the data URI quietly surviving on its own;
  * the positioning line is one claim across three surfaces -- the authority states it, the
    served landing page repeats it twice, the rail splits it at a seam -- and they must agree.
"""
from __future__ import annotations

import base64
import hashlib
import importlib.util
import io
import json
import re
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / 'design-lab' / 'scripts' / 'render_brand_asset.py'
sys.path.insert(0, str(REPO / 'src'))

_spec = importlib.util.spec_from_file_location('render_brand_asset', SCRIPT)
rba = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rba)


def _check(png: Path, css: Path, html: Path | None = None) -> tuple[int, str]:
    """Run the script's own --check against a chosen set of files.

    `png` is the mark the check hashes. It was the bitmap until 2026-10-25 and is now
    `MARK_PATH`, the owner's vector; patching the wrong constant is what let a missing-asset
    case pass on green, so every path the checker reads is swapped together -- including
    `HTML_PATH`, which the tab-icon half of the check reads. Leaving it real would mean a
    swapped mark still "passed" the icon against the shipped page, i.e. the case would grade
    two different subjects and call the agreement a result.

    `html` defaults to a page carrying the icon composed from `png`, so the pre-existing
    stylesheet cases keep testing exactly what they tested before the icon joined the check.
    """
    import contextlib
    out = io.StringIO()
    synthetic = None
    if html is None:
        # The scratch page goes to the git-ignored runtime root, not beside the tracked mark:
        # writing it into apps/workbench/brand/ left an untracked file in a governed directory,
        # and a generated report then named a path the clone does not carry.
        scratch = REPO / '.project-local' / 'task-runtime' / 'brand-asset-scratch'
        scratch.mkdir(parents=True, exist_ok=True)
        synthetic = scratch / ('index-synthetic-%s.html' % png.stem)
        try:
            synthetic.write_text('<html><head>' + rba.favicon_block(rba.favicon_svg(png.read_bytes()))
                                 + '</head><body></body></html>', encoding='utf-8')
        except (SystemExit, OSError):
            # An unreadable or uncomposable subject gets a page with no icon region, so the
            # checker reaches its own named refusal instead of crashing inside the harness.
            synthetic.write_text('<html><head></head><body></body></html>', encoding='utf-8')
        html = synthetic
    real = (rba.PNG_PATH, rba.CSS_PATH, rba.MARK_PATH, rba.HTML_PATH)
    rba.PNG_PATH, rba.CSS_PATH, rba.MARK_PATH, rba.HTML_PATH = png, css, png, html
    try:
        with contextlib.redirect_stdout(out):
            code = rba.main(['--check'])
    finally:
        (rba.PNG_PATH, rba.CSS_PATH, rba.MARK_PATH, rba.HTML_PATH) = real
        if synthetic is not None:
            synthetic.unlink(missing_ok=True)
    return code, out.getvalue().strip()


def _css_encodings(css_text=None):
    """The two decoded `--brand-mark-*` SVG encodings the managed block declares.

    The favicon cases read the brand through here. An attempt to fold the older class onto this
    helper was abandoned because its own pattern is already correct and pinned; the duplication
    that leaves is two readers of one fact, so a future change to the declaration must update
    both -- which is exactly the kind of thing this docstring exists to say out loud.
    """
    css = rba.CSS_PATH.read_text(encoding='utf-8') if css_text is None else css_text
    found = {}
    for name in ('paper', 'ink'):
        match = re.search(r'--brand-mark-%s:url\("data:image/svg\+xml;base64,'
                          r'([A-Za-z0-9+/=]*)"\);' % name, css)
        found[name] = base64.b64decode(match.group(1)).decode('utf-8') if match else None
    return found


class BrandAssetSyncTests(unittest.TestCase):
    def test_the_shipped_pair_passes_the_generators_own_check(self):
        code, line = _check(rba.MARK_PATH, rba.CSS_PATH)
        self.assertEqual(code, 0, f'the stylesheet and the tracked svg disagree: {line}')
        self.assertIn('BRAND_ASSET=OK', line)

    def test_a_swapped_payload_is_caught(self):
        """Replace the inlined glyph with a different svg and the check has to say stale."""
        mark = rba.MARK_PATH.read_bytes()
        other = (b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10">'
                 b'<path fill="#EEF2F5" d="M0 0h10v10H0z"/></svg>')
        self.assertNotEqual(mark, other)
        css = rba.CSS_PATH.read_text(encoding='utf-8')
        swapped = css.replace(base64.b64encode(mark).decode('ascii'),
                              base64.b64encode(other).decode('ascii'))
        self.assertNotEqual(swapped, css, 'the vector payload was not findable in the css, so '
                                         'this case would be comparing the file to itself')
        with _temp_pair(swapped.encode('utf-8'), other) as (p, c):
            code, line = _check(p, c)
        self.assertEqual(code, 1)
        self.assertIn('BRAND_CSS_STALE', line)

    def test_a_stale_digest_claim_is_caught(self):
        """The claim in the comment must be the digest of the svg, not of any file at all.

        This case used to hand the checker the retired bitmap as the subject. It still exited 1
        then -- for a different reason than it names -- which is exactly how a green suite hides
        an unread assertion.
        """
        css = re.sub(r'(brand-mark:begin sha256=)[0-9a-f]{64}', r'\g<1>' + 'a' * 64,
                     rba.CSS_PATH.read_text(encoding='utf-8'))
        self.assertIn('aaaaaa', css)
        with _temp_pair(css.encode('utf-8'), rba.MARK_PATH.read_bytes()) as (p, c):
            code, line = _check(p, c)
        self.assertEqual(code, 1)
        self.assertIn('BRAND_CSS_STALE', line)

    def test_a_missing_asset_is_a_failure_not_a_pass(self):
        missing = rba.MARK_PATH.with_name('no-such-mark.svg')
        self.assertFalse(missing.exists())
        code, line = _check(missing, rba.CSS_PATH)
        self.assertEqual(code, 1)
        self.assertIn('BRAND_ASSET_MISSING', line)


class BrandRegionTests(unittest.TestCase):
    def setUp(self):
        self.css = rba.CSS_PATH.read_text(encoding='utf-8')

    def test_the_stylesheet_carries_exactly_one_region(self):
        self.assertEqual(len(rba.REGION.findall(self.css)), 1,
                         'two regions would mean the generator rewrites one while the '
                         'cascade wins with the other')

    def test_the_region_lives_inside_the_root_token_block(self):
        """A second `:root{...}` rule would satisfy the browser and break the gate."""
        start = self.css.index(':root{')
        end = self.css.index('\n}', start)
        begin = self.css.index('brand-mark:begin')
        self.assertTrue(start < begin < end,
                        'the generated declaration must sit inside the existing :root block; '
                        'design-lab/tests/test_workbench_css_single_definition.py fails on a '
                        'selector defined twice')

    def test_the_nav_mark_and_the_legacy_tiles_consume_the_token(self):
        """An unread declaration is decoration: the asset must actually be painted.

        `.app-nav-mark` is the surface the product mounts; `.mark` and `.brand-mark::after` are
        the pre-shell tiles that still carry the token. The bloom claim this case used to make
        (`var(--glow)` on `.mark`) was dropped with the bitmap: `filter` on a masked glyph is
        clipped by paint order, so asserting it would pin a decoration nobody can see.
        """
        for selector in ('.app-nav-mark{', '.mark{', '.brand-mark::after{'):
            self.assertIn(selector, self.css, f'{selector} is gone -- the consumer sweep is '
                                              'only as good as the names it knows')
            block = self.css[self.css.index(selector):]
            block = block[:block.index('}')]
            self.assertIn('var(--brand-mark)', block, f'{selector} does not use the mark')


class MarkShapeTests(unittest.TestCase):
    """The shipped mark is a two-path cut-out in one of two brand inks, not a box.

    These cases used to open the 144x144 RGBA bitmap and assert a transparent ground, a white
    glyph and an inset edge. That asset is superseded -- the interface now paints the owner's
    vector -- so guarding its pixels guarded nothing that ships, which is the same mistake as
    leaving a checker pointed at a retired pipeline.
    """

    @classmethod
    def setUpClass(cls):
        cls.mark = rba.MARK_PATH.read_bytes()
        css = rba.CSS_PATH.read_text(encoding='utf-8')
        cls.encodings = {}
        for name in ('paper', 'ink'):
            found = re.search(r'--brand-mark-%s:url\("data:image/svg\+xml;base64,'
                              r'([A-Za-z0-9+/=]*)"\);' % name, css)
            cls.encodings[name] = base64.b64decode(found.group(1)).decode('utf-8') \
                if found else None

    def test_the_tracked_mark_is_a_path_bearing_svg_with_a_view_box(self):
        self.assertIn(b'<svg', self.mark[:200])
        self.assertIn(b'viewBox', self.mark)
        self.assertEqual(self.mark.count(b'<path '), 2,
                         'the monogram is the D plus the star burst; a third path means the '
                         'cut that separates glyph from wordmark moved')

    def test_each_encoding_carries_exactly_one_of_the_two_brand_inks(self):
        """Two encodings of one geometry: paper for charcoal, ink for the light palettes."""
        for name, want in (('paper', '#EEF2F5'), ('ink', '#17212B')):
            text = self.encodings[name]
            self.assertIsNotNone(text, f'--brand-mark-{name} is gone from the stylesheet')
            self.assertEqual(text.count('<path '), 2,
                             f'--brand-mark-{name} lost geometry')
            self.assertIn('fill="%s"' % want, text,
                          f'--brand-mark-{name} is not drawn in the ink its name claims')
            other = '#17212B' if want == '#EEF2F5' else '#EEF2F5'
            self.assertNotIn('fill="%s"' % other, text,
                             f'--brand-mark-{name} mixes both brand inks')

    def test_the_encoding_is_the_tracked_mark_reinked_and_not_a_reinterpretation(self):
        """Same viewBox, same path data: the two tokens differ only in the fill."""
        paper, ink = self.encodings['paper'], self.encodings['ink']
        self.assertEqual(paper.replace('#EEF2F5', '@'), ink.replace('#17212B', '@'),
                         'the paper and ink encodings differ in more than their ink, so one '
                         'palette is showing a different drawing')
        self.assertEqual(re.search(r'viewBox="([^"]+)"', paper).group(1),
                         re.search(r'viewBox="([^"]+)"', self.mark.decode('utf-8')).group(1),
                         'the inlined viewBox is not the tracked file\'s, so the tile scales '
                         'a drawing nobody reviewed')

    def test_the_provenance_records_source_digests_and_no_machine_path_for_the_shipped_svg(self):
        """The artwork lives outside the repository and is not fetched here.

        What this pins is that every tracked derivation names its source by digest and its
        method, and that the shipped file's recorded digest is the file on disk. The absolute
        owner directory is recorded once, in `source_dir_outside_repository`, as a provenance
        note -- not as a path the verification reads.
        """
        meta = json.loads(rba.PROVENANCE.read_text(encoding='utf-8'))
        tracked = meta['tracked_derivations']
        key = 'apps/workbench/brand/design-mark.svg'
        self.assertIn(key, tracked)
        self.assertEqual(len(tracked[key]['sha256']), 64)
        self.assertEqual(tracked[key]['sha256'], hashlib.sha256(self.mark).hexdigest(),
                         'the provenance record and the shipped bytes disagree')
        self.assertEqual(tracked[key]['paths'], 2)
        self.assertIn('derived_from', tracked[key])
        for entry in meta['sources'].values():
            self.assertEqual(len(entry['sha256']), 64,
                             'a source without a full digest cannot be re-obtained verifiably')


class InlineMechanismTests(unittest.TestCase):
    def test_the_reason_the_asset_is_inlined_is_still_the_reason(self):
        from design_lab import workbench
        self.assertIn('img-src data:', workbench.CSP)
        self.assertNotIn("img-src 'self'", workbench.CSP)
        self.assertEqual(len(workbench.ROUTES), 3,
                         'the allowlist grew; if the mark can be served as a file, the '
                         'data URI should be replaced by that route and this test updated '
                         'with the CSP line that makes it legal')

    def test_the_service_still_serves_the_stylesheet_that_carries_it(self):
        from design_lab import workbench
        body, mime = workbench.resource('/workbench/style.css')
        self.assertEqual(mime, 'text/css')
        self.assertIn(b'--brand-mark', body)
        self.assertEqual(hashlib.sha256(rba.MARK_PATH.read_bytes()).hexdigest()[:16],
                         re.search(rb'brand-mark:begin sha256=([0-9a-f]{16})', body).group(1).decode())


class PositioningLineTests(unittest.TestCase):
    """The positioning line is one claim repeated on three surfaces; AUTHORITY.md is its source.

    The authority states it, the landing page repeats it under the h1 and again in the footer, and
    the mounted shell splits it across two `.brand-line` spans so it breaks at its own seam instead
    of mid-word (16 characters do not fit the 168px rail). Before this class nothing tied the three
    together, so rewording one surface was free and the product could quietly start describing
    itself differently in three places.
    """

    LINE = '专业视觉智能与可复用设计能力系统'

    def test_the_authority_still_says_it(self):
        text = (REPO / 'AUTHORITY.md').read_text(encoding='utf-8')
        self.assertIn(self.LINE, text,
                      'AUTHORITY.md no longer carries the line this test pins. Rewording the '
                      'positioning is the owner call; when it happens, update this constant and '
                      'every surface that repeats it in the same change')

    def test_the_served_landing_page_repeats_it_in_the_header_and_the_footer(self):
        """Served bytes, not the checkout file: the wheel copy wins when installed."""
        from design_lab import workbench
        body, mime = workbench.resource('/workbench')
        self.assertEqual(mime, 'text/html')
        html = body.decode('utf-8')
        self.assertEqual(html.count(self.LINE), 2,
                         'the landing page shows the line under the h1 and once in the footer; '
                         f'the served bytes carry it {html.count(self.LINE)} times')

    def test_the_shell_splits_it_at_the_seam_and_the_pieces_rejoin_the_authority(self):
        src = (REPO / 'apps' / 'workbench' / 'shell.ts').read_text(encoding='utf-8')
        parts = re.findall(r"class: 'brand-line' \}, '([^']*)'", src)
        self.assertEqual(len(parts), 2,
                         f'expected two brand lines, parsed {parts!r} -- the extraction is '
                         'stale, do not conclude anything from it')
        self.assertEqual(''.join(parts), self.LINE,
                         'the rail breaks the line at a seam; the two halves must still read '
                         'as the authority sentence, not as two different claims')


class _temp_pair:
    """Context manager writing a (png, css) pair to a temp dir and yielding the paths."""

    def __init__(self, css_bytes: bytes, png_bytes: bytes):
        self.css_bytes, self.png_bytes = css_bytes, png_bytes

    def __enter__(self):
        import tempfile
        self.dir = tempfile.TemporaryDirectory()
        root = Path(self.dir.name)
        css = root / 'style.css'
        png = root / 'mark.png'
        css.write_bytes(self.css_bytes)
        png.write_bytes(self.png_bytes)
        return png, css

    def __exit__(self, *exc):
        self.dir.cleanup()
        return False


class BrandFaviconTests(unittest.TestCase):
    """The tab icon is the same tracked vector, and `--check` now owns that claim.

    Before this cut the served page had no `link[rel=icon]` at all (measured: three surfaces
    reported NONE), so the browser drew a generic document glyph while the rail drew the owner's
    mark. The icon is composed, not drawn: one ink flip plus one tile rect whose numbers come out
    of the tracked `viewBox`, leaving the `<path>` payload untouched. These cases are what stop
    "composed" from quietly becoming "a second logo somebody typed".
    """

    def _served_icon(self) -> bytes:
        html = rba.HTML_PATH.read_text(encoding='utf-8')
        found = re.search(r'href="data:image/svg\+xml;base64,([A-Za-z0-9+/=]*)"', html)
        self.assertIsNotNone(found, 'the served page carries no svg data-uri icon to read')
        return base64.b64decode(found.group(1))

    def _pair_with_page(self, html_text, body):
        with _temp_pair(rba.CSS_PATH.read_bytes(), rba.MARK_PATH.read_bytes()) as (m, c):
            h = m.parent / 'index.html'
            h.write_text(html_text, encoding='utf-8')
            return _check(m, c, h)

    def test_the_icon_and_the_tracked_mark_share_one_path_payload(self):
        """The one-source claim, measured on bytes rather than asserted in a comment."""
        mark = rba.MARK_PATH.read_bytes()
        icon = self._served_icon()
        paths_in_mark = re.findall(rb'<path[^>]*>', mark)
        paths_in_icon = re.findall(rb'<path[^>]*>', icon)
        self.assertEqual(len(paths_in_mark), 2, 'expected the two-path glyph')
        self.assertEqual(paths_in_icon, paths_in_mark,
                         'the tab icon no longer carries the tracked path payload verbatim, so it '
                         'is a second drawing rather than the same mark on a tile')
        self.assertEqual(icon.count(b'<rect'), 1, 'the icon is supposed to add exactly one tile')

    def test_the_tile_geometry_and_both_inks_are_derived_not_typed(self):
        mark = rba.MARK_PATH.read_bytes().decode('utf-8')
        box = re.search(r'viewBox="([-\d.]+) ([-\d.]+) ([-\d.]+) ([-\d.]+)"', mark)
        x, y, width, height = (float(v) for v in box.groups())
        icon = self._served_icon().decode('utf-8')
        expected = ('<rect x="' + str(x) + '" y="' + str(y) + '" width="' + str(width)
                    + '" height="' + str(height) + '" rx="'
                    + str(round(min(width, height) / 3, 2)) + '" fill="'
                    + rba.BRAND_INKS['ink'] + '"/>')
        self.assertIn(expected, icon,
                      'the tile is no longer derived from the tracked viewBox and the shipped '
                      'border-radius ratio, so somebody is typing these numbers')
        self.assertIn('fill="' + rba.BRAND_INKS['paper'] + '"', icon,
                      'the glyph lost the light ink it needs on a tab of unknown chrome colour')

    def test_the_inks_are_the_same_two_the_stylesheet_check_claims(self):
        """One vocabulary for both surfaces, or the brand has two colours by accident.

        The stylesheet never spells these hex values as plaintext -- they live inside the two
        base64 encodings, which is exactly why this reads the decoded payloads instead of
        grepping the file. A grep would have passed on a token of the same name and failed on a
        correct file, which is the difference between checking the ink and checking a string.
        """
        css = rba.CSS_PATH.read_text(encoding='utf-8')
        decoded = _css_encodings(css)
        for name in ('paper', 'ink'):
            self.assertIsNotNone(decoded[name],
                                 f'the stylesheet no longer declares --brand-mark-{name}')
        icon = self._served_icon().decode('utf-8')
        self.assertIn('fill="' + rba.BRAND_INKS['paper'] + '"', icon,
                      'the glyph on the tab is not drawn in the paper ink the stylesheet uses')
        self.assertIn('fill="' + rba.BRAND_INKS['ink'] + '"', icon,
                      'the tab tile is not drawn in the ink the stylesheet uses')
        self.assertIn(rba.BRAND_INKS['paper'], decoded['paper'],
                      'BRAND_INKS and the shipped paper encoding disagree; the check below would '
                      'still pass because it reads its own constant')
        self.assertIn(rba.BRAND_INKS['ink'], decoded['ink'],
                      'BRAND_INKS and the shipped ink encoding disagree')

    def test_a_swapped_icon_payload_is_caught(self):
        """Tamper only the icon and the command must say so -- not report a clean tree."""
        html = rba.HTML_PATH.read_text(encoding='utf-8')
        good = self._served_icon()
        other = (b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10">'
                 b'<path fill="#EEF2F5" d="M0 0h10v10H0z"/></svg>')
        swapped = html.replace(base64.b64encode(good).decode('ascii'),
                               base64.b64encode(other).decode('ascii'))
        self.assertNotEqual(swapped, html, 'the icon payload was not findable in the page, so '
                                         'this case would be comparing the file to itself')
        code, line = self._pair_with_page(swapped, None)
        self.assertEqual(code, 1, 'a redrawn tab icon passed the check: ' + line)
        self.assertIn('BRAND_FAVICON_STALE', line)

    def test_a_stale_icon_digest_is_caught(self):
        html = rba.HTML_PATH.read_text(encoding='utf-8')
        claimed = re.search(re.escape(rba.FAVICON_BEGIN) + r'([0-9a-f]{64})', html)
        self.assertIsNotNone(claimed)
        code, line = self._pair_with_page(html.replace(claimed.group(1), '0' * 64), None)
        self.assertEqual(code, 1, 'a digest claim matching nothing passed the check: ' + line)
        self.assertIn('BRAND_FAVICON_STALE', line)

    def test_a_page_without_the_icon_is_refused_not_passed(self):
        """The pre-fix state of this cut, kept as a permanent case.

        Before `--sync-favicon` existed, index.html had no managed region and `--check` still
        printed `BRAND_ASSET=OK`, because the command only ever looked at the stylesheet. A check
        that stays silent about a surface it does not read is how "covered" becomes a lie, so the
        absence is now a named refusal.
        """
        html = rba.HTML_PATH.read_text(encoding='utf-8')
        stripped = re.sub(re.escape(rba.FAVICON_BEGIN) + '.*?' + re.escape(rba.FAVICON_END),
                          '', html, flags=re.S)
        self.assertNotEqual(stripped, html, 'no managed icon region was found to strip, so this '
                                         'case would be comparing the page to itself')
        self.assertNotIn(rba.FAVICON_BEGIN, stripped)
        code, line = self._pair_with_page(stripped, None)
        self.assertEqual(code, 1, 'a page with no tab icon passed the check: ' + line)
        self.assertIn('BRAND_FAVICON_REGION_UNREADABLE', line)

    def test_the_page_carries_exactly_one_managed_region_inside_the_head(self):
        html = rba.HTML_PATH.read_text(encoding='utf-8')
        self.assertEqual(html.count(rba.FAVICON_BEGIN), 1,
                         'two managed regions would mean the generator rewrites one and the page '
                         'reads the other')
        self.assertLess(html.find(rba.FAVICON_BEGIN), html.find('<title>'),
                        'the icon link must sit in the head; workbench.py serves this file '
                        'verbatim, so a link after the body starts is a page-order bug')
        self.assertIn('<link rel="icon" type="image/svg+xml"', html)

    def test_the_icon_adds_no_served_path_and_no_csp_change(self):
        """Inlining is still the only option, so the icon may not quietly become an asset route.

        `workbench.py` serves a fixed three-path allowlist under CSP `img-src data:`. A favicon
        fetched from a new URL would widen both, which the owner list reserves as a security
        decision rather than a convenience -- this asserts the shipped icon is a data URI and that
        the allowlist still has exactly three entries.
        """
        from design_lab import workbench
        self.assertEqual(len(workbench.ROUTES), 3,
                         'the served allowlist changed shape; the reason the brand is inlined has '
                         'to be re-argued, not inherited')
        self.assertNotIn('/workbench/favicon', ' '.join(workbench.ROUTES))
        self.assertIn('href="data:image/svg+xml;base64,',
                      rba.HTML_PATH.read_text(encoding='utf-8'))


if __name__ == '__main__':
    unittest.main(verbosity=2)
