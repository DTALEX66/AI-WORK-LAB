# SPDX-License-Identifier: MIT
"""A utility class must not lose a cascade fight it never agreed to.

`scripts/verify_utility_class_conflicts.py` exists because folding twenty repeated inline `style:`
strings into `.spaced-top` / `.grid-stack` silently moved elements: a component class defined later in
the stylesheet (`.row-card{display:flex;gap:12px}`, `.quick-launch{margin-top:0}`) started winning by
source order once the inline override disappeared, and all four browser gates stayed green through it.

The second case is the load-bearing one: it re-plants the exact bug (drop the compound rule that states
the intent) and requires the check to go red. A guard nobody has seen fail is decoration.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import unittest

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / 'scripts' / 'verify_utility_class_conflicts.py'
sys.path.insert(0, str(REPO / 'src'))

_spec = importlib.util.spec_from_file_location('verify_utility_class_conflicts', SCRIPT)
vucc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(vucc)

CSS = (REPO / 'apps/workbench/style.css').read_text(encoding='utf-8')
SHELL = (REPO / 'apps/workbench/shell.ts').read_text(encoding='utf-8')


class UtilityClassConflictTests(unittest.TestCase):
    def test_no_utility_class_shares_a_property_with_its_component(self):
        self.assertEqual(vucc.main([]), 0,
                         'a layout utility is fighting a component class over the same property')

    def test_the_check_would_have_caught_the_fold_regression(self):
        """Remove the compound rule that states the intent; the conflict must reappear."""
        compound = '.row-card.grid-stack{display:grid;gap:var(--uif-space-2)}\n'
        self.assertIn(compound, CSS, 'the compound rule is gone from the stylesheet, so this '
                                    'falsifier no longer plants anything')
        problems = vucc.conflicts(CSS.replace(compound, ''), SHELL)
        self.assertTrue(problems, 'deleting the resolution left no complaint -- the check is blind '
                                  'to exactly the shape that broke the six row cards')
        self.assertTrue(any('gap' in p and 'grid-stack' in p for p in problems),
                        f'expected the gap conflict, got: {problems[:3]}')

    def test_a_shell_that_applies_no_utility_is_a_failure_not_a_pass(self):
        """An empty population must not read as "nothing to guard, therefore green"."""
        import tempfile
        quiet_text = "el('div', { class: 'panel' }, 'x')\n"
        with tempfile.TemporaryDirectory() as tmp:
            quiet = Path(tmp) / 'shell.ts'
            quiet.write_text(quiet_text, encoding='utf-8')
            real = vucc.SHELL
            vucc.SHELL = quiet
            try:
                self.assertEqual(vucc.main([]), 1)
            finally:
                vucc.SHELL = real
        self.assertEqual(vucc.applied_class_sets(quiet_text), [])


if __name__ == '__main__':
    unittest.main(verbosity=2)
