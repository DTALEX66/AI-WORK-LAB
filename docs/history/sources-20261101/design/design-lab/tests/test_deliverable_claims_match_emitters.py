# SPDX-License-Identifier: MIT
"""The Workbench may only offer delivery formats the bundle writer can produce.

The page used to list nine '导出候选' from a flat constant while the emitter produces
five member names. That is the false-green shape this repo forbids: an offer the
service cannot honour looks identical to a feature.

Checked in both directions, and every extraction fails loudly when it matches
nothing -- a gate that silently finds zero emitters would pass forever.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SHELL = REPO / 'apps/workbench/shell.ts'
NATIVE_BUNDLES = REPO / 'src/design_lab/native_bundles.py'
BUNDLE_STORE = REPO / 'src/design_lab/runtime/bundle_store.py'


def ui_claims():
    """[(format, member_or_None)] from DELIVERABLE_FORMATS in the Workbench shell."""
    text = SHELL.read_text(encoding='utf-8')
    # The colon is part of the anchor on purpose: the looser `[^=]+` pattern let a
    # renamed `DELIVERABLE_FORMATS_REMOVED` still match, so deleting the declaration
    # looked like a passing mutation instead of a missing contract.
    block = re.search(r"const DELIVERABLE_FORMATS:\s*ReadonlyArray<[^>]*>\s*=\s*\["
                      r"(.*?)\]\s*as const", text, re.S)
    assert block, 'DELIVERABLE_FORMATS is missing from shell.ts -- the gate must not ' \
                  'pass because the page stopped declaring what it offers'
    rows = re.findall(r"\{ format: '([^']+)', producedBy: (null|'[^']+') \}", block.group(1))
    assert rows, 'DELIVERABLE_FORMATS declared nothing'
    return [(name, (None if value == 'null' else value.strip("'"))) for name, value in rows]


def emitter_members():
    """Member names the delivery layer actually writes into a bundle."""
    source = NATIVE_BUNDLES.read_text(encoding='utf-8')
    primaries = re.search(r"primary\s*=\s*'psd' if host=='photoshop' else 'ai'", source)
    assert primaries, 'cannot find the native primary-kind choice in native_bundles.py; ' \
                      'the emitter changed shape and this gate has to be re-read, not skipped'
    names = re.search(r"names=\{primary:'native\.'\+primary,'png':'([^']+)','svg':'([^']+)'\}",
                      source)
    assert names, 'cannot find the bundle member names in native_bundles.py'
    zip_member = re.search(r"artifact_name='([^']+)'", BUNDLE_STORE.read_text(encoding='utf-8'))
    assert zip_member, 'cannot find the bundle archive member in bundle_store.py'
    return {'native.psd', 'native.ai', names.group(1), names.group(2),
            zip_member.group(1)}


class DeliverableClaimsMatchEmitters(unittest.TestCase):
    def setUp(self):
        self.claims = ui_claims()
        self.emitted = emitter_members()

    def test_every_offered_format_maps_to_a_real_member(self):
        for name, member in self.claims:
            if member is not None:
                self.assertIn(member, self.emitted,
                              f'the page offers {name} as producible via {member!r}, '
                              'but no bundle writer emits that member')

    def test_no_emitted_member_is_left_unoffered(self):
        offered = {member for _, member in self.claims if member is not None}
        self.assertEqual(offered, self.emitted,
                         'the bundle layer produces members the page does not offer, or '
                         'the page lists members nobody writes -- both drift silently')

    def test_unoffered_formats_are_genuinely_unproduced(self):
        for name, member in self.claims:
            if member is None:
                self.assertNotIn(f'native.{name.lower()}', self.emitted,
                                 f'{name} is declared as not produced but the emitter '
                                 'can produce it -- say so instead of hiding the feature')

    def test_the_page_says_unproduced_instead_of_calling_it_a_candidate(self):
        text = SHELL.read_text(encoding='utf-8')
        rendering = re.search(r"DELIVERABLE_FORMATS\.map\((.*?)\)\);", text, re.S)
        assert rendering, 'the deliverable grid no longer renders DELIVERABLE_FORMATS'
        body = rendering.group(1)
        self.assertIn('当前不产出', body,
                      'a format with no emitter must be labelled as not produced')
        self.assertNotIn("'导出候选'", body,
                         'the flat "candidate" caption made every entry look available')


if __name__ == '__main__':
    unittest.main()
