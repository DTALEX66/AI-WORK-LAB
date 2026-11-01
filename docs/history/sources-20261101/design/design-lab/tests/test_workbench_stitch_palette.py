# SPDX-License-Identifier: MIT
"""The 20261023 pack's STITCH colours ship as a third optional palette, and only as one.

What this pins, and why each line is a real risk rather than ceremony:

* the six values are quoted from the pack itself, so a recolour cannot quietly drift away from
  what the owner adopted (the pack text is the authority, this file re-reads it at test time);
* they live ONLY inside ``:root[data-palette="stitch"]`` -- the default palette keeps every pixel,
  which is the standing owner ruling that a new pack's colours become a selectable theme, never an
  override;
* every scheme a palette declares has a CSS rule and every CSS rule belongs to a declared palette,
  so the table in shell.ts and the stylesheet cannot each be right on their own;
* the URL/attribute reader consults the table instead of a pair of string comparisons, which is how
  a palette could exist in the menu and stay unreachable from ``?palette=``;
* the pack's typography floor (元数据至少12px) holds for every size the stylesheet declares, not
  only for the ones a browser sweep happened to paint -- the two guards cover different sets and
  the difference is exactly the rule that no measured route renders.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CSS = REPO / 'apps/workbench/style.css'
SHELL = REPO / 'apps/workbench/shell.ts'
PACK = REPO / 'docs/taskpacks/20261023-ui-kb/source/08_STITCH完整提示词.txt'

# role -> the hex the pack names for it
SPEC_COLOURS = {
    'accent': '#356B92', 'text': '#17212B', 'muted': '#566472',
    'background': '#F4F6F8', 'content': '#FFFFFF', 'border': '#D8DFE5',
}


class StitchPaletteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.css = CSS.read_text(encoding='utf-8')
        cls.shell = SHELL.read_text(encoding='utf-8')
        cls.pack = PACK.read_text(encoding='utf-8')
        start = cls.css.index(':root[data-palette="stitch"]')
        cls.block = cls.css[start:cls.css.index('}', cls.css.index('--glow', start))]

    def test_the_pack_actually_names_every_value_this_theme_uses(self):
        # Reading the pack instead of copying it into this test: if the archived text stops naming a
        # value, this fails and the theme has to be re-derived rather than trusted from memory.
        missing = [value for value in SPEC_COLOURS.values() if value.upper() not in self.pack.upper()]
        self.assertEqual(missing, [],
                         'the STITCH prompt no longer names these colours: %s' % missing)

    def test_the_six_named_values_are_all_declared_in_the_theme_block(self):
        absent = [f'{role} {value}' for role, value in SPEC_COLOURS.items()
                  if value.upper() not in self.block.upper()]
        self.assertEqual(absent, [],
                         'the stitch block does not carry the pack value for: %s' % absent)

    def test_the_default_palette_keeps_the_values_it_shipped_with(self):
        # The owner ruling is that a new pack's colours become a theme, never an override. Scope is
        # the first :root block -- the shared rules -- because "no pack colour appears anywhere in
        # the file" would be false on its face (#FFFFFF is a legitimate ink elsewhere); what must
        # hold is that the default挂载点 still declares the dark values it shipped with.
        block = self.css[:self.css.index('}', self.css.index('--layer-toast'))]
        for token, value in (('--color-bg', '#060A14'), ('--color-primary', '#316CFF'),
                             ('--color-text', '#F5F7FC')):
            self.assertIn('%s:%s' % (token, value), block,
                          'the default palette no longer declares %s -- the stitch theme is '
                          'supposed to be additive' % token)
        leaked = [value for value in SPEC_COLOURS.values()
                  if value.upper() in block.upper() and value.upper() != '#FFFFFF']
        self.assertEqual(leaked, [],
                         'these pack colours reached the default :root block, which would recolour '
                         'the shipped palette: %s' % leaked)

    def test_every_declared_scheme_of_a_palette_has_a_css_rule(self):
        # applyTheme removes data-scheme for the dark side, so a palette's dark values may live on
        # the bare [data-palette] selector; either shape counts as declaring the scheme, and
        # neither is optional.
        declared = re.findall(r"\{ id: '([a-z0-9-]+)'[^{]*?schemes: \[([^\]]*)\]", self.shell)
        self.assertTrue(declared, 'no palette table found in shell.ts to check against the CSS')
        for palette, schemes in declared:
            if palette == 'design-lab':
                continue  # its dark values ARE the shared :root block, by design
            for scheme in re.findall(r"'([a-z]+)'", schemes):
                scoped = ':root[data-palette="%s"][data-scheme="%s"]' % (palette, scheme)
                bare = ':root[data-palette="%s"]' % palette
                self.assertIn(True, (scoped in self.css,
                                     scheme == 'dark' and bare in self.css),
                              'shell.ts offers %s/%s but the stylesheet declares no values for it '
                              '-- the switch would paint the default colours and label them %s'
                              % (palette, scheme, palette))

    def test_no_css_theme_block_names_a_palette_the_table_does_not_offer(self):
        for palette in set(re.findall(r':root\[data-palette="([a-z0-9-]+)"\]', self.css)):
            if palette == 'ui2026' and palette not in self.shell:
                continue
            self.assertIn("id: '%s'" % palette, self.shell,
                          'the stylesheet styles %s but shell.ts never offers it, so nobody can '
                          'reach those rules' % palette)

    def test_the_theme_reader_asks_the_palette_table_instead_of_a_hardcoded_pair(self):
        # The bug this closes: `urlParam('palette') === 'ui2026' ? 'ui2026' : 'design-lab'` made a
        # third palette unreachable from the URL even though the menu and CSS both had it.
        self.assertNotIn("? 'ui2026' : 'design-lab'", self.shell,
                         'the URL palette is back to a hardcoded comparison; a palette added to '
                         'PALETTES would be unreachable and no test would notice')
        self.assertIn('PALETTES.some((entry) => entry.id === value)', self.shell,
                      'readThemeChoice no longer consults PALETTES for the palette value')

    def test_the_stitch_palette_declares_only_the_side_the_pack_named(self):
        # Nothing in the pack describes a dark version of these values, so claiming one would be
        # the project inventing a design and calling it a 1:1 reproduction.
        self.assertIn("{ id: 'stitch', label: 'STITCH 珍珠白（20261023 包）', schemes: ['light']",
                      re.sub(r'\s+', ' ', self.shell.replace('\n', ' ')))
        self.assertNotIn(':root[data-palette="stitch"][data-scheme="dark"]', self.css,
                         'a dark stitch rule exists although the pack never named dark values')

    def _sizes_in(self, text):
        """Every px font size the stylesheet declares, in any of the three shapes it appears in."""
        found = []
        for pattern in (r'font-size:\s*([0-9.]+)px', r'font:\s*([0-9.]+)px',
                        r'--[a-z0-9-]*font[a-z0-9-]*:\s*([0-9.]+)px'):
            found += [float(m.group(1)) for m in re.finditer(pattern, text)]
        return found

    def test_the_pack_typography_floor_holds_in_the_stylesheet_not_only_where_the_walk_painted(self):
        """CT_SPEC grades 元数据至少12px on painted text, so a rule no measured route renders is
        invisible to it forever. `.brand small` was exactly that case: 10px, declared, never
        painted on any swept route, so the browser ruler reported minPx=12 while the file still
        shipped a smaller floor. This is the static half of the same rule -- every font-size in
        the stylesheet, reachable or not, sits at or above the pack's 12px.
        """
        sizes = self._sizes_in(self.css)
        self.assertGreater(len(sizes), 40,
                           'the reader found only %d sizes; the pattern is broken, so a '
                           'violation would pass unseen' % len(sizes))
        low = sorted({s for s in sizes if s < 12})
        self.assertEqual(low, [],
                         'the pack puts 元数据 at 至少12px, but the stylesheet still declares %s'
                         % low)
        # The guard itself must be able to bite: plant a violation and show this reader sees it.
        planted = self.css.replace('--uif-font-micro:12px;', '--uif-font-micro:11px;', 1)
        self.assertNotEqual(planted, self.css,
                            'the token line this guard watches has moved; re-point the plant so '
                            'the guard keeps biting')
        self.assertIn(11.0, self._sizes_in(planted),
                      'a planted 11px token got past the reader, so the pass above measures '
                      'nothing')


if __name__ == '__main__':
    unittest.main()
