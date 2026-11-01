# SPDX-License-Identifier: MIT
"""The counts written into the design contract and the next-agent prompt match measurement.

`scripts/verify_documented_counts.py` exists because two stale figures reached a live surface on
2026-10-19 (a route-table comment naming 15 entries when there are 19, and DESIGN.md's "11 nav
items, overflow only below 720px") and no gate noticed. This module runs that script and, in the
second case, proves the predicate can actually be disturbed: a doc that disagrees with the code has
to turn the gate red, or the gate guards nothing.
"""
from __future__ import annotations

from pathlib import Path
import importlib.util
import sys
import unittest
from unittest import mock

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / 'scripts' / 'verify_documented_counts.py'
sys.path.insert(0, str(REPO / 'src'))

_spec = importlib.util.spec_from_file_location('verify_documented_counts', SCRIPT)
vdc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(vdc)


class DocumentedCountsTests(unittest.TestCase):
    def test_every_documented_count_matches_the_code(self):
        self.assertEqual(vdc.check(), 0, 'prose disagrees with measurement (see FAIL lines above)')

    def test_a_prose_number_that_disagrees_is_caught(self):
        """The claim is keyed by file, so rewriting the sentence must not slip through."""
        rel, template, _measure = vdc.CLAIMS[0]
        truth = vdc.route_views()
        original = (REPO / rel).read_text(encoding='utf-8')
        stale = original.replace(template.format(n=truth), template.format(n=truth - 1))
        self.assertNotEqual(stale, original,
                            f'the template {template!r} no longer matches {rel}; the claim is '
                            'unpinned and this falsifier is testing nothing')
        real_read = Path.read_text

        def read_text(self, *args, **kwargs):
            if self.name == Path(rel).name:
                return stale
            return real_read(self, *args, **kwargs)

        with mock.patch.object(Path, 'read_text', read_text):
            self.assertEqual(vdc.check(), 1, 'a doc one off from measurement still passed')


if __name__ == '__main__':
    unittest.main(verbosity=2)
