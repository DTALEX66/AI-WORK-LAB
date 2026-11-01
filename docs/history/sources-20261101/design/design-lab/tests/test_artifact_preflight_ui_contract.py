# SPDX-License-Identifier: MIT
"""The Workbench may only offer artifact preflight the service can actually run.

`assurance/production_preflight.py` reports a check only when it measured it, carries the
`criterion` each verdict was judged against, and caps the result at INCOMPLETE when a check
was left NOT_MEASURED. A page can undo all of that without a single type error: offer a
profile no file declares, drop the NOT_MEASURED rows because they look like noise, or print
only the detail and hide what the judgement was based on. That turns an honest column back
into a tick box, so the column is checked against the service here.

Every extraction asserts on the way. A pattern that matches nothing fails the gate rather
than passing on an empty set.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SHELL = REPO / 'apps/workbench/shell.ts'
SERVICE = REPO / 'src/design_lab/http_service.py'
PREFLIGHT = REPO / 'src/design_lab/assurance/production_preflight.py'
PROFILE_DIR = REPO / 'design-lab' / 'production' / 'profiles'


def declared_profiles():
    names = sorted(path.name.removeprefix('preflight-').removesuffix('.json')
                   for path in PROFILE_DIR.glob('preflight-*.json'))
    assert names, 'no preflight profile files exist -- this gate would prove nothing'
    return names


def route_profiles():
    """The profile names the HTTP route's own query pattern accepts."""
    pattern = re.search(r"\(\?:\\\?profile=\(([^)]+)\)\)\?", SERVICE.read_text(encoding='utf-8'))
    assert pattern, 'the bundle preflight route no longer declares a profile query pattern; ' \
                    're-read this gate instead of relaxing it'
    return pattern.group(1).split('|')


def ui_profiles():
    """The profile names the page offers."""
    text = SHELL.read_text(encoding='utf-8')
    block = re.search(r"const PREFLIGHT_PROFILES(?::[^=]*)?\s*=\s*\[([^\]]*)\]", text)
    assert block, 'PREFLIGHT_PROFILES is missing from shell.ts -- the page stopped declaring ' \
                  'what it offers, which must read as a failure, not as a pass'
    names = re.findall(r"'([a-z]+)'", block.group(1))
    assert names, 'PREFLIGHT_PROFILES declared no profile'
    return names


def renderer_body():
    """The source of the function that paints a preflight readback."""
    text = SHELL.read_text(encoding='utf-8')
    match = re.search(r"function artifactPreflightPanel\([^)]*\)[^{]*\{(.*?)\n\}\n", text, re.S)
    assert match, 'artifactPreflightPanel is gone from shell.ts -- the readback column was ' \
                  'removed, not renamed'
    return match.group(1)


class ProfilesLineUp(unittest.TestCase):
    def test_the_page_offers_exactly_the_declared_profiles(self):
        self.assertEqual(sorted(ui_profiles()), declared_profiles(),
                         'the page offers a profile no file declares (the service would refuse '
                         'it) or hides a profile that exists (the feature looks absent)')

    def test_the_route_accepts_exactly_the_declared_profiles(self):
        self.assertEqual(sorted(route_profiles()), declared_profiles(),
                         'the route and the profile directory disagree about what exists')

    def test_the_page_offers_exactly_what_the_route_accepts(self):
        self.assertEqual(sorted(ui_profiles()), sorted(route_profiles()),
                         'a profile the page offers but the route refuses is a button that '
                         'cannot work')


class ReadbackKeepsTheServicesHonesty(unittest.TestCase):
    def test_the_page_calls_the_bundle_preflight_route(self):
        text = SHELL.read_text(encoding='utf-8')
        call = re.search(r"`/projects/\$\{[^}]+\}/bundles/\$\{[^}]+\}/preflight\?profile=", text)
        assert call, 'the page does not build the bundle preflight URL from a project id and a ' \
                     'bundle id -- it is calling something else or nothing at all'

    def test_no_path_comes_from_the_page(self):
        """The endpoint resolves the artifact from the state database by id.

        A page-supplied path would let the check read arbitrary files, so this column is
        only safe while the URL shape holds. Checked on the request builders, not the file.
        """
        text = SHELL.read_text(encoding='utf-8')
        self.assertNotIn('/preflight?path=', text)
        self.assertNotIn('archive_path', text)

    def test_the_criterion_is_rendered_not_dropped(self):
        body = renderer_body()
        self.assertIn('.criterion', body,
                      'every finding carries the criterion it was judged against; a table '
                      'without it shows a verdict with no basis')

    def test_NOT_MEASURED_rows_survive_to_the_screen(self):
        body = renderer_body()
        self.assertNotIn('findings.filter', body,
                         'filtering findings is how NOT_MEASURED disappears and an INCOMPLETE '
                         'readback starts looking like a pass')
        self.assertIn('data.findings.map', body,
                      'the table must render the service findings as they arrived')

    def test_the_verdict_vocabulary_is_the_services_own(self):
        body = renderer_body()
        verdicts = re.search(r"^VERDICTS = \((.*)\)$",
                             PREFLIGHT.read_text(encoding='utf-8'), re.M).group(1)
        for verdict in re.findall(r"'([A-Z]+)'", verdicts):
            self.assertIn(verdict, body,
                          f'the service can emit {verdict} and the page has no wording for it, '
                          'so it would fall through to the failure colour')

    def test_the_column_opens_as_not_yet_run(self):
        """The column must declare that nothing has run.

        Whether a click really fires exactly one request, and whether a refusal replaces
        the previous verdict, is proven behaviourally in apps/workbench/tests/appshell.mjs
        (block ⑥) against the built bundle -- a text window around a call site could only
        ever guess at that.
        """
        text = SHELL.read_text(encoding='utf-8')
        assert '尚未预检' in text, 'the preflight column must open by saying nothing has run'
        assert 'async function runArtifactPreflight(' in text, \
            'the runner is gone -- the column has no way to reach the service'


if __name__ == '__main__':
    unittest.main()
