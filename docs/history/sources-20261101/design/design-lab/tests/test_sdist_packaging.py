#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""The packaging-provenance gate, graded both ways.

Owner audit at 7671ec70: the published sdist could not rebuild the wheel it ships
(`FileNotFoundError: Forced include not found: …/design-lab/domain-packs`). The static relation
"every wheel force-include source needs an sdist root" is what broke; these cases plant each way it
can break again, because a coverage check that only ever sees a correct pyproject proves nothing.

Scope stated plainly: the static check compares the paths the two tables *declare*. A glob that eats
files *inside* a directory source is caught only by `--build`, which unpacks the real archive.
"""
from __future__ import annotations

import contextlib
import io
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(ROOT / 'design-lab' / 'scripts'))

import verify_sdist_packaging as gate  # noqa: E402

PYPROJECT = ROOT / 'pyproject.toml'
SCRIPT = ROOT / 'design-lab' / 'scripts' / 'verify_sdist_packaging.py'
NEEDED_ROOT = 'design-lab/domain-packs'


class SdistPackagingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.text = PYPROJECT.read_text(encoding='utf-8')
        self.forced, self.only, self.excludes = gate.load_map(self.text)

    def test_it_reads_the_two_lists_it_claims_to_compare(self) -> None:
        # A parser that silently returns empty lists would let every later assertion pass on
        # nothing, so the population itself is graded first.
        self.assertGreaterEqual(len(self.forced), 40,
                                f'only {len(self.forced)} force-include sources parsed; the table '
                                f'moved or the parser stopped matching it')
        self.assertGreaterEqual(len(self.only), 5, f'only {len(self.only)} sdist roots parsed')
        self.assertIn('src/design_lab', self.only)
        self.assertIn(NEEDED_ROOT, self.only,
                      'the path the shipped defect went missing on is still not carried by name')

    def test_the_shipped_pyproject_needs_no_exception(self) -> None:
        self.assertEqual(gate.findings(self.forced, self.only, self.excludes), [],
                         'the wheel asks for paths the published sdist will not carry')

    def test_the_script_reports_the_covered_state_by_name(self) -> None:
        proc = subprocess.run([sys.executable, str(SCRIPT)], capture_output=True, text=True,
                              encoding='utf-8')
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn(f'SDIST_PACKAGING=OK wheel_sources={len(self.forced)} '
                      f'covered={len(self.forced)} missing=0', proc.stdout)

    def test_removing_one_sdist_root_is_convicted_by_name(self) -> None:
        """The exact shape of the shipped defect: a root goes away, the wheel still asks for it."""
        without = [entry for entry in self.only if entry != NEEDED_ROOT]
        self.assertEqual(len(without), len(self.only) - 1,
                         'the plant found nothing to remove, so it would convict nothing')
        problems = gate.findings(self.forced, without, self.excludes)
        self.assertTrue(any(NEEDED_ROOT in p for p in problems),
                        f'deleting the root produced {problems}')

    def test_a_force_include_pointing_at_nothing_is_convicted(self) -> None:
        ghost = 'design-lab/schemas/not-a-real-file.schema.json'
        problems = gate.findings(self.forced + [ghost], self.only, self.excludes)
        self.assertTrue(any(ghost in p and 'not in the repository' in p for p in problems),
                        f'a typo in the wheel map produced {problems}')

    def test_an_sdist_root_that_does_not_exist_is_convicted(self) -> None:
        problems = gate.findings(self.forced, self.only + ['design-lab/no-such-tree'],
                                 self.excludes)
        self.assertTrue(any('design-lab/no-such-tree' in p and 'does not exist' in p
                            for p in problems),
                        f'a stale sdist root produced {problems}')

    def test_an_exclude_that_eats_a_listed_source_is_convicted(self) -> None:
        problems = gate.findings(self.forced, self.only, [NEEDED_ROOT])
        self.assertTrue(any('excludes it away' in p for p in problems),
                        f'listing a path and globbing it away produced {problems}')

    def test_the_verifier_refuses_when_the_table_it_reads_is_gone(self) -> None:
        renamed = self.text.replace('[tool.hatch.build.targets.wheel.force-include]',
                                    '[tool.hatch.build.targets.wheel.force-include-disabled]')
        self.assertEqual(gate.load_map(renamed)[0], [],
                         'the parser still matched after the table was renamed, so the refusal '
                         'below cannot fire')
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            (repo / 'pyproject.toml').write_text(renamed, encoding='utf-8')
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                rc = gate.main(['--repo', str(repo)])
        self.assertEqual(rc, 1, buf.getvalue())
        self.assertIn('SDIST_PACKAGING=FAIL', buf.getvalue())

    def test_build_mode_refuses_instead_of_passing_without_a_builder(self) -> None:
        with patch('shutil.which', return_value=None):
            problems = gate.build_round_trip(ROOT)
        self.assertTrue(problems, 'a machine with no builder reported a successful round trip')
        self.assertIn('uv is not on PATH', problems[0])


if __name__ == '__main__':
    unittest.main(verbosity=2)
