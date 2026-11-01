#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Report paths must be printable wherever they are written.

Owner audit 2026-10-26, finding 7: `scripts/audit_workbench_ui.py` finished a full sweep, wrote the
JSON, and THEN called `out_path.relative_to(REPO)` while printing the path -- so with `--out` (or
`E2E_EVIDENCE_DIR`) outside the checkout the run died with `ValueError` after measuring everything.
Two sites in `run_design_review_plugin.py` had the same shape.
"""
from __future__ import annotations
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(ROOT / 'scripts'))

from report_paths import display_path  # noqa: E402


class ReportPathDisplayTests(unittest.TestCase):
    """Why the out-of-repo path is built from the checkout's own location, not from `tempfile`.

    The first version of these two cases used `tempfile.TemporaryDirectory()`. On this machine that
    is `C:\\Users\\...\\Temp`, so the "outside" path really was outside and the cases passed; the CI
    runner sets `TMPDIR` INSIDE the workspace, so the same code produced a path under `REPO`,
    `display_path` correctly answered relative, `relative_to` correctly did not raise, and my tests
    went red (CI run 40331019135, shard 2/3, `FAIL: 2`). The product was right and the test's premise
    was an unverified assumption about the environment. `outside_report()` derives the path from the
    repository itself and refuses to continue if it is not genuinely outside.
    """

    @staticmethod
    def outside_report() -> Path:
        """A path that is outside the checkout by construction, with the premise checked.

        The directory name deliberately does NOT contain the repository's own folder name: the leak
        assertion below compares path components, and a sibling literally named
        `design-lab-outside-check` would have made that check trivially passable again -- the exact
        weakness of the substring form this replaces.
        """
        candidate = (ROOT.parent / 'outside-repo-report-check' / 'report.json').resolve()
        root = ROOT.resolve()
        if root == candidate or root in candidate.parents:
            raise AssertionError('the derived "outside the repo" path %s is inside %s -- the '
                                 'premise of these two cases would be false again'
                                 % (candidate, root))
        return candidate

    def test_an_in_repo_path_is_still_printed_relative(self) -> None:
        target = ROOT / '.project-local' / 'task-artifacts' / 'browser-e2e' / 'x.json'
        self.assertEqual(display_path(target, ROOT),
                         target.resolve().relative_to(ROOT.resolve()).as_posix(),
                         'the line a human greps for changed shape for paths that were fine')

    def test_an_out_of_repo_path_is_printed_absolutely_and_does_not_raise(self) -> None:
        outside = self.outside_report()
        shown = display_path(outside, ROOT)
        self.assertEqual(Path(shown), outside,
                         'an out-of-repo path must still be identifiable from the line')
        # Components, not substrings. The previous form asked "is the repo path a substring of the
        # parent", which any sibling whose name starts with the repo name satisfies -- a check that
        # can be fooled by the fixture's spelling is not a check.
        parents = list(Path(shown).parents)
        self.assertNotIn(ROOT.resolve(), parents,
                         'the display path leaked the repo prefix back in')

    def test_the_two_scripts_no_longer_print_an_unguarded_relative_to(self) -> None:
        for rel in ('scripts/audit_workbench_ui.py', 'scripts/run_design_review_plugin.py'):
            text = (ROOT / rel).read_text(encoding='utf-8')
            self.assertNotIn('relative_to(REPO).as_posix()', text,
                             f'{rel} still derives a display path with the call that raised')
            self.assertIn('display_path(', text,
                          f'{rel} stopped using the shared helper, so the crash class can return')

    def test_the_source_check_bites_a_reintroduced_relative_to(self) -> None:
        """Without this, the assertion above is a string match that could pass on a broken script."""
        sample = (ROOT / 'scripts' / 'audit_workbench_ui.py').read_text(encoding='utf-8')
        reintroduced = sample.replace('display_path(out_path, REPO)',
                                      'out_path.relative_to(REPO).as_posix()')
        self.assertNotEqual(reintroduced, sample,
                            'the sample no longer contains the call site, so this plant is hollow')
        self.assertIn('relative_to(REPO).as_posix()', reintroduced)
        self.assertNotIn('relative_to(REPO).as_posix()',
                         (ROOT / 'scripts' / 'run_design_review_plugin.py').read_text(
                             encoding='utf-8'))

    def test_the_expression_that_crashed_still_crashes_on_the_same_input(self) -> None:
        """Non-vacuity for the fix: the pre-print expression is what raised, on exactly this path.

        Proved against the raw call rather than against a copy of the old script, because the old
        line is deleted and a deleted line cannot be executed. The path comes from
        `outside_report()` for the reason documented on the class: a temp dir is not allowed to be
        inside the checkout, or this assertion is checking nothing.
        """
        outside = self.outside_report()
        with self.assertRaises(ValueError):
            outside.relative_to(ROOT.resolve())
        # And the helper returns a usable path for the same input, which is the difference.
        self.assertTrue(display_path(outside, ROOT).endswith('report.json'))

    def test_the_helper_survives_a_windows_case_difference(self) -> None:
        # Case-insensitive filesystems are why `is_relative_to` was not trusted here: the two paths
        # can differ only in drive-letter case and still be the same directory.
        upper = display_path(ROOT / 'reports' / 'current' / 'TASK_PROGRESS.json', ROOT)
        self.assertEqual(upper, 'reports/current/TASK_PROGRESS.json', upper)
        odd_case = display_path(Path(str(ROOT).upper()) / 'reports' / 'x.json', ROOT)
        self.assertTrue(odd_case.endswith('reports/x.json'),
                        f'a case-differing repo root produced {odd_case!r}')


if __name__ == '__main__':
    unittest.main(verbosity=2)
