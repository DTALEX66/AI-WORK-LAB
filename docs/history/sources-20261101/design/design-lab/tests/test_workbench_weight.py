# SPDX-License-Identifier: MIT
"""Teeth for scripts/measure_workbench_weight.py's DL-KB-13 readings.

The card's rule is 先量基线再改, so the two readings this module guards are the ones that were
missing: 列表初始行数 (how many rows a first paint can even get) and 附件缩略图策略 (what the
attachment listing actually costs). Both are instruments that can go blind without going red --
a slice on a query-term list would print an 8-row page for a route that never promised one, and an
empty "region" extraction would print "0 img elements" for a panel that has one. So each test here
either cross-checks a printed number against the file that states it, or proves the reader is not
blind before it is believed.

Nothing here judges a threshold: the size ceiling is an owner decision (the script says so), and
the attachment numbers are a baseline, not an optimisation.
"""
from __future__ import annotations

import ast
import contextlib
import importlib.util
import io
import json
import re
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / 'src'))

SCRIPT = REPO / 'scripts' / 'measure_workbench_weight.py'
SCRATCH = REPO / '.project-local' / 'task-runtime' / 'kb13-weight'
TEST_CORPUS = SCRATCH / 'test-corpus'
# A stand-in store the reader is pointed at, to prove which of its signals it trusts.
FAKE_STORE = SCRATCH / 'fake_store.py'
FAKE_SOURCE = '''DEFAULT_LIMIT = 50
MAX_LIMIT = 200


class FakeLibrary:
    def search(self, *, limit=DEFAULT_LIMIT):
        terms = _TERM.findall(self.query)[:8]
        rows = self._rows(terms)
        return {'entries': [dict(r) for r in rows[:100]], 'total': len(rows)}

    def _rows(self, terms):
        return []

    def browse(self):
        rows = self._rows([])
        return [dict(r) for r in rows][:1] if rows else []


def _TERM(text):
    return []
'''


def load_script():
    spec = importlib.util.spec_from_file_location('measure_workbench_weight_under_test', SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def run(argv: list[str]) -> tuple[int, str]:
    """Invoke the script's main() with the given flags and return (exit code, stdout)."""
    module = load_script()
    buffer = io.StringIO()
    previous = sys.argv
    sys.argv = [str(SCRIPT)] + argv
    try:
        with contextlib.redirect_stdout(buffer):
            code = module.main()
    finally:
        sys.argv = previous
    return code, buffer.getvalue()


class ShippedBytesStillReported(unittest.TestCase):
    """The lines other records already read must keep being printed, and keep being true."""

    @classmethod
    def setUpClass(cls):
        cls.code, cls.out = run(['--check', '--no-assets'])

    def test_existing_weight_and_verdict_lines_survive(self):
        for prefix in ('WEIGHT bundle', 'WEIGHT stylesheet', 'WEIGHT document',
                       'WEIGHT inline-data', 'WEIGHT mountPoints', 'WEIGHT page',
                       'WEIGHT module ', 'WEIGHT modules declarations',
                       'WEIGHT remoteReferences', 'WEIGHT NOTE'):
            self.assertIn(prefix, self.out, f'{prefix} is no longer printed')
        self.assertEqual(self.code, 0)
        self.assertIn('WORKBENCH_WEIGHT_GATE=OK remote=0 bundle_gzip=', self.out)

    def test_check_path_writes_nothing(self):
        # The CI step is this script with --check; it must not seed a corpus to do its verdict.
        self.assertIn('THUMBNAIL baseline SKIPPED', self.out)
        self.assertIn('Nothing above this line wrote a file', self.out)

    def test_json_carries_the_new_sections(self):
        _code, out = run(['--json', '--no-assets'])
        # The NOTE line the script prints outside the JSON branch is its own long-standing shape,
        # so the payload is the first line -- not the whole stdout.
        data = json.loads(out.splitlines()[0])
        for key in ('files', 'modules', 'pageSizes', 'listRows', 'thumbnailPolicy'):
            self.assertIn(key, data)
        self.assertIsNone(data['assetListBaseline'])
        self.assertGreater(len(data['listRows']['routes']), 10)
        self.assertIn('listRowsWithImgElement', data['thumbnailPolicy'])


class ListInitialRows(unittest.TestCase):
    """列表初始行数: one reading per list-bearing GET route, bounded by its own code."""

    @classmethod
    def setUpClass(cls):
        cls.module = load_script()
        cls.reading = cls.module.list_row_readings()
        cls.by_action = {r['action']: r for r in cls.reading['routes']}

    def test_the_reader_sees_the_route_table_it_claims(self):
        # A blind reader would print an empty table and a zero "without limit" count, which is
        # exactly the confident-nothing this repository already refuses elsewhere.
        self.assertIsNone(self.reading['readerError'], self.reading['readerError'])
        self.assertGreater(self.reading['listRoutes'], 10)
        self.assertGreater(self.reading['frontendCallSites'], 50)

    def test_every_route_is_accounted_for_exactly_once(self):
        bounded = [r for r in self.reading['routes'] if r['initialRows'] is not None]
        unbounded = [r for r in self.reading['routes'] if r['initialRows'] is None]
        self.assertEqual(len(bounded) + len(unbounded), self.reading['listRoutes'])
        self.assertEqual(sorted(r['action'] for r in unbounded), sorted(self.reading['withoutLimit']))
        for row in self.reading['routes']:
            self.assertTrue(row['action'].startswith(('_list_', '_search_')))
            self.assertEqual(row['method'], 'GET')

    def test_a_reported_bound_points_at_a_line_that_states_it(self):
        # The number is only a measurement if the file:line printed says that number in code.
        seen = 0
        for row in self.reading['routes']:
            if row['initialRows'] is None:
                continue
            seen += 1
            name, rest = row['boundAt'].split(':', 1)
            line = int(re.match(r'[0-9]+', rest).group(0))
            candidates = list((REPO / 'src' / 'design_lab').glob(name))
            self.assertEqual(len(candidates), 1, f'{name} is not exactly one file')
            text = candidates[0].read_text(encoding='utf-8').splitlines()[line - 1]
            stated = (str(row['initialRows']) in text or str(row['initialRows'] - 1) in text
                      or 'rows[:' in text or 'LIMIT' in text)
            self.assertTrue(stated, f'{name}:{line} says {text!r}, not a bound of '
                                    f'{row["initialRows"]}')
        self.assertGreaterEqual(seen, 5, 'the bounded half of the table went untested')

    def test_the_page_sizes_already_on_record_still_agree(self):
        # scripts/measure_workbench_weight.py prints five documented defaults on its own; the new
        # per-route reading must not disagree with the same constants it re-derives.
        from design_lab import knowledge_library, assistance_plan, target_profile, plan_feedback
        for action, expected in (('_search_knowledge_entries', knowledge_library.DEFAULT_LIMIT),
                                 ('_list_assistance_plans', assistance_plan.DEFAULT_LIMIT),
                                 ('_list_target_profiles', target_profile.DEFAULT_LIMIT),
                                 ('_list_plan_feedback', plan_feedback.DEFAULT_LIMIT)):
            self.assertEqual(self.by_action[action]['initialRows'], expected, action)

    def test_the_attachment_list_is_the_route_without_a_bound(self):
        assets = self.by_action['_list_or_read_assets']
        self.assertIsNone(assets['initialRows'])
        self.assertEqual(assets['unresolved'], [])
        self.assertGreaterEqual(assets['clientCalls'], 1)

    def test_none_means_resolved_and_unbounded_not_unread(self):
        # An unresolved delegate is reported separately; a NONE born of reader blindness would let
        # the script tell an owner "no limit here" about a route it never opened.
        self.assertEqual(self.reading['unresolved'], [])

    def test_the_query_term_slice_is_not_reported_as_the_page(self):
        action = self.by_action['_search_knowledge_entries']
        self.assertNotEqual(action['initialRows'], 8)
        self.assertEqual(action['maxRows'], 200)

    def test_which_signals_the_reader_trusts_on_a_store_it_can_read(self):
        SCRATCH.mkdir(parents=True, exist_ok=True)
        FAKE_STORE.write_text(FAKE_SOURCE, encoding='utf-8', newline='\n')
        self.addCleanup(lambda: FAKE_STORE.unlink(missing_ok=True))
        rel = FAKE_STORE.relative_to(REPO).as_posix()
        bounds = self.module.row_bounds(rel, 'FakeLibrary', 'search')
        values = sorted({c['value'] for c in bounds['caps']})
        self.assertIn(50, values)                       # the method's own limit default
        self.assertIn(100, values)                      # the rows[:100] page
        self.assertNotIn(8, values)                     # a slice on a CALL is not a row bound
        self.assertEqual(bounds['maximum'], 200)
        browse = self.module.row_bounds(rel, 'FakeLibrary', 'browse')
        self.assertNotIn(1, {c['value'] for c in browse['caps']})
        missing = self.module.row_bounds(rel, 'FakeLibrary', 'nothing_here')
        self.assertIsNotNone(missing['reason'])


class AttachmentThumbnailPolicy(unittest.TestCase):
    """附件缩略图策略: what the shipped client and the store really do about pixels."""

    @classmethod
    def setUpClass(cls):
        cls.module = load_script()
        cls.policy = cls.module.thumbnail_policy()

    def test_the_regions_read_are_not_empty(self):
        # Proving "no img in the list" with a region that was never found would be a pass built on
        # blindness, so the byte counts of both regions are asserted first.
        for name in ('referencePickerForProject', 'renderReferencePanel'):
            self.assertGreater(self.policy['bundleRegionBytes'][name], 500, name)

    def test_first_paint_pulls_no_pixels(self):
        self.assertEqual(self.policy['listRowsWithImgElement'], 0)
        self.assertEqual(self.policy['listRowsFetchingContent'], 0)

    def test_the_preview_is_one_lazy_element_not_a_grid(self):
        self.assertEqual(self.policy['panelImgElements'], 1)
        self.assertTrue(self.policy['previewAssetDefined'])
        self.assertGreaterEqual(self.policy['panelClickHandlers'], 1)

    def test_no_server_side_scaled_variant_exists(self):
        self.assertEqual(self.policy['scaledVariantSymbolsInStore'], [])
        self.assertIn('object-fit:contain', ';'.join(self.policy['previewBoxRules']))


class AttachmentBaselineIsMeasured(unittest.TestCase):
    """The price list, at a size small enough to re-run inside a test."""

    def test_two_assets_produce_two_accounted_points(self):
        module = load_script()
        # 64px, not 8px: the claim "the list is cheap and the pixels are not" is false for a
        # 74-byte PNG, and a test that asserts a falsehood about its own fixture proves nothing.
        result = module.asset_list_baseline(counts=(1, 2), side=64, passes=1, clean=True,
                                            corpus=str(TEST_CORPUS))
        self.assertEqual([p['assets'] for p in result['points']], [1, 2])
        self.assertTrue(result['removed'])
        self.assertFalse(TEST_CORPUS.exists(), '--clean left the corpus behind')
        for point in result['points']:
            self.assertEqual(point['bytesRead'], point['perAssetBytes'] * point['assets'])
            self.assertGreater(point['splitWallMs'], 0.0)
            parts = (point['pathCheckMs'] + point['readMs'] + point['hashMs']
                     + point['decodeMs'])
            self.assertLessEqual(parts, point['splitWallMs'] + 0.05)
            self.assertGreaterEqual(point['unattributedMs'], -0.05)
            self.assertLess(point['listJsonBytes'], point['previewAllBase64Bytes'])
            self.assertEqual(point['previewAllBase64Bytes'],
                             sum(4 * ((point['perAssetBytes'] + 2) // 3)
                                 for _ in range(point['assets'])))
            self.assertGreater(point['onePreviewJsonBytes'],
                               4 * ((point['perAssetBytes'] + 2) // 3))
            self.assertLessEqual(sum((point['pathCheckPercent'], point['readPercent'],
                                      point['hashPercent'], point['decodePercent'])), 100.0)
        growing = [p['listJsonBytes'] for p in result['points']]
        self.assertEqual(growing, sorted(growing))
        self.assertLess(growing[0], growing[1])

#: The list routes that answer without a bound, each with why it is registered rather than
#: bounded in this cut. This is a fail-closed register, not a to-do list: a tenth unbounded
#: route goes red, and so does bounding one of these without retiring its entry -- because a
#: silent improvement is how the next person inherits a hole they cannot see.
#:
#: Grounding rule for this table: `cost` states a number only where this round measured one,
#: and says NOT MEASURED otherwise. A register full of plausible-sounding costs is worse than
#: a short one, because the reader cannot tell which row was earned.
UNBOUNDED_REGISTER = {
    '_list_or_read_assets': {
        'cost': 'measured: 199.59 ms server-side for 200 assets of 47,160 B; 59.0% of it is '
                'per-row checked_path+stat, 30.5% double image decode, 2.4% hashing',
        'why_not_bounded_now': 'pagination is the wrong tool for this cost: every row is '
                're-read and re-decoded because list() calls _verified() per asset '
                '(image_assets.py:75-88), and width/height/media_type are not stored, so the '
                'real fix is to materialise them at write time -- a state-schema change with '
                'its own migration, precheck and contract row',
    },
    '_list_projects': {
        'cost': 'NOT MEASURED this round; the answer is a per-project roll-up '
                '(ProjectIndex.list, http_service.py:850) so the work grows with projects',
        'why_not_bounded_now': 'a page of projects without a page affordance in the sidebar '
                'would show fewer projects and say nothing about it, which is a worse answer '
                'than a complete one at this corpus size',
    },
    '_list_design_systems': {
        'cost': 'NOT MEASURED; the handler answers from a fixed four-name registry '
                '(VALID_DESIGN_SYSTEMS, test_design_layer_http.py:57), so growth is not '
                'person-controlled',
        'why_not_bounded_now': 'bounded by its own domain, not by a limit; registered so the '
                'claim stays checkable if that ever stops being true',
    },
    '_list_jury': {'cost': 'NOT MEASURED',
                  'why_not_bounded_now': 'no bound and no measurement yet; registered so the '
                  'next cut starts from a number instead of an assumption'},
    '_list_rights': {'cost': 'NOT MEASURED',
                     'why_not_bounded_now': 'no bound and no measurement yet; the rights ledger '
                     'is a Human Gate surface, so a page that hides rows hides decisions'},
    '_list_research': {
        'cost': 'NOT MEASURED',
        'why_not_bounded_now': 'no bound and no measurement this round; it stays registered '
                'rather than merely printed, so the next cut must either measure it or bound it '
                'instead of inheriting a number nobody took',
    },
    '_list_knowledge_candidates': {
        'cost': 'NOT MEASURED',
        'why_not_bounded_now': 'no bound and no measurement yet; the export path is a read-back, '
                'so truncating it would misreport what was ever offered'},
    '_list_token_documents': {
        'cost': 'NOT MEASURED',
        'why_not_bounded_now': 'no bound and no measurement yet; the workbench column reads this '
                'list form and an empty answer is deliberately a list, not a 404'},
}


class UnboundedListRoutesAreRegistered(unittest.TestCase):
    """Every list GET route that answers without a bound is named in the register below.

    The instrument prints a count and the first test proves that print agrees with this table, but
    neither of them makes adding one more unbounded route a finding. A printed number nobody
    compares against anything is a report, not a gate: the register is the part that bites.
    No number is written in this sentence on purpose -- it said "nine of eighteen" until
    `_list_prompt_results` was bounded on 2026-10-26 and left the count stale in the prose while the
    register stayed correct, which is the exact rot this round was called to catch elsewhere.
    """

    @classmethod
    def setUpClass(cls):
        cls.module = load_script()
        cls.reading = cls.module.list_row_readings()

    def test_the_unbounded_set_is_exactly_the_register(self):
        actual = sorted(self.reading['withoutLimit'])
        self.assertEqual(actual, sorted(UNBOUNDED_REGISTER),
                         'the set of list routes with no bound moved. A new one is a finding; '
                         'a retired one must leave its register entry, or the hole comes back '
                         'unnoticed. actual=%s register=%s' % (actual, sorted(UNBOUNDED_REGISTER)))

    def test_every_register_entry_states_cost_and_a_reason(self):
        for action, entry in UNBOUNDED_REGISTER.items():
            self.assertTrue(entry['cost'].strip(), f'{action} states no cost source')
            self.assertGreater(len(entry['why_not_bounded_now']), 40,
                               f'{action} carries filler instead of a reason')

    def test_a_new_unbounded_route_is_convicted(self) -> None:
        # Both directions of drift must fail: one more route than the register admits, and one
        # fewer -- the second leg is what stops a bound being added while the entry lingers.
        grown = sorted(UNBOUNDED_REGISTER) + ['_list_planted']
        self.assertNotEqual(grown, sorted(UNBOUNDED_REGISTER))
        self.assertNotIn('_list_planted', UNBOUNDED_REGISTER,
                         'the plant must not exist in the register, or this proves nothing')
        # _list_prompt_results was bounded on 2026-10-26 (prompt_results.py readback now pages
        # with a default limit and an envelope). Delisting it is only honest if the instrument
        # agrees, so the entry may not come back and the route may not reappear as unbounded.
        self.assertNotIn('_list_prompt_results', UNBOUNDED_REGISTER,
                         'this route is bounded now; keeping it registered would hide the bound')
        self.assertNotIn('_list_prompt_results', self.reading['withoutLimit'],
                         'the register says bounded but the live route reading says otherwise')
        # And the register may not drift from reality in the other direction either.
        for action in UNBOUNDED_REGISTER:
            self.assertIn(action, self.reading['withoutLimit'],
                          f'{action} is registered as unbounded but the instrument no longer '
                          'agrees -- retire the entry in the same change that bounds it')


    def test_the_reader_sees_the_route_table_it_claims(self):
        # A blind reader would print an empty table and a zero "without limit" count, which is
        # exactly the confident-nothing this repository already refuses elsewhere.
        self.assertIsNone(self.reading['readerError'], self.reading['readerError'])
        self.assertGreater(self.reading['listRoutes'], 10)
        self.assertGreater(self.reading['frontendCallSites'], 50)
        self.assertIsNone(self.reading['callSiteError'],
                          'the client column needs the canonical route-call matcher, which '
                          'imports the product dependencies; this suite must run under the '
                          'project venv or say so, not read 0 as "the page asks for nothing"')

    def test_the_check_path_stays_stdlib_only(self):
        """The workbench strict-TS job runs `python3 scripts/measure_workbench_weight.py --check`
        in a node job that installs no Python third-party packages. When the route reader was
        changed to `from design_lab.http_service import ROUTES`, that import reached image_assets,
        needed Pillow, and the job died with MEASURE_SOURCE_MOVED -- while passing locally under
        the venv, which is the exact shape of a platform-dependent green.

        So the rule is pinned structurally: nothing outside a function body may import a
        first-party or third-party module. The optional client-half reader may still import the
        gate inside its try block, because that degradation is reported rather than trusted.
        """
        tree = ast.parse(SCRIPT.read_text(encoding='utf-8'))
        offenders = []
        for node in tree.body:
            if isinstance(node, ast.Import):
                offenders += [a.name.split('.')[0] for a in node.names]
            elif isinstance(node, ast.ImportFrom):
                offenders.append((node.module or '').split('.')[0])
        stdlib = {'__future__', 'argparse', 'ast', 'gzip', 'importlib', 'json', 're',
                  'statistics', 'sys', 'time', 'functools', 'pathlib', 'contextlib', 'unittest'}
        bad = sorted(set(offenders) - stdlib)
        self.assertEqual(bad, [],
                         f'module-level non-stdlib imports would make --check need the project '
                         f'venv, and the strict-TS job has none: {bad}')

    def test_a_when_bearing_route_is_not_guessed_at(self):
        """The parsed route stands in for the real Route, and the canonical matcher calls
        accepts(); a route carrying a `when=` predicate cannot be evaluated from source text, so
        it must refuse rather than answer True and quietly over-match."""
        routes = self.module.live_routes()
        with_when = [r for r in routes if r.has_when]
        self.assertTrue(with_when, 'the plant of this assertion is that one route still '
                                   'carries when=; if that changed, re-read this test')
        for route in with_when:
            with self.assertRaises(ValueError):
                route.accepts(None)
        plain = [r for r in routes if not r.has_when]
        self.assertTrue(all(r.accepts(None) for r in plain))


if __name__ == '__main__':
    unittest.main()
