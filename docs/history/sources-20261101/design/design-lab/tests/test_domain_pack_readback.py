# SPDX-License-Identifier: MIT
"""Domain Pack readback: the loader, its checker agreement, and GET /api/domains.

Three properties are asserted, in this order:

1. the projection lists the pack directories that are really on disk -- nothing added,
   nothing dropped, so a pack the checker rejects cannot be omitted into a cleaner list;
2. per pack, `validation == 'VALIDATES'` exactly when `verify_domain_pack_v2.validate()`
   returns ok. The read path reuses that checker, and this test re-runs it independently,
   so the two cannot drift apart without a red test;
3. the route serves the same projection and has no write form.

Data counts are derived, not pinned, following design-lab/tests/test_capability_library.py:
a test that hardcoded "13 packs" would pass on a stale checkout and fail on a legitimate
addition. The count that WAS hardcoded lives in the shell assertions at the bottom.
"""
from __future__ import annotations

import importlib.util
import json
import os
import re
import secrets
import shutil
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src'))

from design_lab import domain_packs  # noqa: E402

CHECKER = ROOT / 'design-lab' / 'scripts' / 'verify_domain_pack_v2.py'
SCHEMA = ROOT / 'design-lab' / 'schemas' / 'domain-pack.schema.json'
PACK_ROOT = ROOT / 'design-lab' / 'domain-packs'
SHELL = ROOT / 'apps' / 'workbench' / 'shell.ts'
CONTRACTS = ROOT / 'apps' / 'workbench' / 'contracts.ts'


def run_checker(pack: Path):
    """The repo's own validator, in a fresh interpreter-side load per call."""
    spec = importlib.util.spec_from_file_location('verify_domain_pack_v2_under_test', CHECKER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.validate(pack)


def make_pack(base: Path, name: str, *, complete: bool = True,
              overrides: dict | None = None, raw: str | None = None) -> Path:
    """A Spec V2 pack in `base`, optionally broken on purpose.

    `complete=False` leaves the declared elements absent (the prompt-only shape the
    spec forbids); `overrides` edits manifest fields after the required keys are set,
    so a schema violation is deliberate rather than incidental.
    """
    pack = base / name
    (pack / 'schemas').mkdir(parents=True)
    (pack / 'benchmarks').mkdir()
    (pack / 'evidence').mkdir()
    (pack / 'benchmarks' / 'case1.json').write_text('{}', encoding='utf-8')
    (pack / 'evidence' / 'card1.json').write_text('{}', encoding='utf-8')
    (pack / 'schemas' / 'brief.schema.json').write_text('{}', encoding='utf-8')
    for rel in ('scenario.md', 'profile.json', 'rubric.json', 'preflight.json',
                'handoff-contract.json', 'sources.json'):
        (pack / rel).write_text('{}' if rel.endswith('.json') else '# scenario\n',
                                encoding='utf-8')
    manifest = {
        'schema_version': 'design-lab/domain-pack/v2',
        'pack_id': name,
        'version': '0.1.0',
        'display_name': f'{name} pack',
        'domain': name.replace('-design', ''),
        'size_bytes_budget': 5_242_880,
        'dependencies': ['jsonschema'],
        'files': {
            'manifest': 'manifest.json',
            'brief_schema': 'schemas/brief.schema.json',
            'scenario': 'scenario.md',
            'profile': 'profile.json',
            'rubric': 'rubric.json',
            'preflight': 'preflight.json',
            'handoff_contract': 'handoff-contract.json',
            'source_mapping': 'sources.json',
            'benchmark_cases': 'benchmarks/',
            'evidence_cards': 'evidence/',
        },
    }
    if not complete:
        manifest['files'] = {'manifest': 'manifest.json'}
    for key, value in (overrides or {}).items():
        if value is None:
            manifest.pop(key, None)
        else:
            manifest[key] = value
    text = raw if raw is not None else json.dumps(manifest)
    (pack / 'manifest.json').write_text(text, encoding='utf-8')
    return pack


def stage_root(tmp: Path, build_packs) -> Path:
    """A repository-shaped temp root holding the checker, the schema and chosen packs.

    The checker resolves the schema from its own file location, so both travel
    together -- the temp root validates against the committed schema rather than
    against a copy of the rules written here.
    """
    (tmp / CHECKER.parent.relative_to(ROOT)).mkdir(parents=True, exist_ok=True)
    shutil.copyfile(CHECKER, tmp / CHECKER.relative_to(ROOT))
    (tmp / SCHEMA.parent.relative_to(ROOT)).mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SCHEMA, tmp / SCHEMA.relative_to(ROOT))
    packs = tmp / PACK_ROOT.relative_to(ROOT)
    packs.mkdir(parents=True, exist_ok=True)
    build_packs(packs)
    return tmp


class RealPackProjectionTests(unittest.TestCase):
    def setUp(self):
        self.doc = domain_packs.build(ROOT)

    def test_the_root_reports_present_and_the_list_is_the_disk(self):
        self.assertEqual(self.doc['rootState'], domain_packs.ROOT_PRESENT)
        on_disk = sorted(item.name for item in PACK_ROOT.iterdir() if item.is_dir())
        self.assertEqual([pack['directory'] for pack in self.doc['packs']], on_disk,
                         'the projection must list exactly the pack directories on disk')

    def test_every_count_is_derived_from_the_records_in_the_call(self):
        counts = self.doc['counts']
        self.assertEqual(counts['packs'], len(self.doc['packs']))
        self.assertEqual(sum(counts['byValidation'].values()), counts['packs'])
        for state, tally in counts['byValidation'].items():
            self.assertEqual(tally,
                             sum(1 for pack in self.doc['packs']
                                 if pack['validation'] == state))

    def test_no_pack_shows_validates_that_the_checker_would_reject(self):
        """The load-bearing assertion: the read path and CI's checker cannot disagree."""
        for pack in self.doc['packs']:
            ok, errors = run_checker(PACK_ROOT / pack['directory'])
            expected = (domain_packs.VALIDATES if ok else domain_packs.INVALID)
            self.assertEqual(pack['validation'], expected,
                             f"{pack['directory']}: checker says ok={ok} errors={errors[:1]}, "
                             f"projection says {pack['validation']}")
            self.assertEqual(pack['validationErrorCount'], len(errors))
            if expected == domain_packs.INVALID:
                self.assertTrue(pack['validationErrors'],
                                f'{pack["directory"]} is rejected but reports no reason')

    def test_a_rejected_pack_is_visible_with_a_reason_and_never_silently_ok(self):
        rejected = [pack for pack in self.doc['packs']
                    if pack['validation'] == domain_packs.INVALID]
        self.assertTrue(rejected, 'this checkout is expected to carry a pack the v2 '
                                  'checker rejects; if it no longer does, delete this '
                                  'test on purpose and record why')
        for pack in rejected:
            self.assertGreater(pack['validationErrorCount'], 0)
            # A verdict whose reasons are gone is the mutation this must convict: count
            # and list are separate fields, and the page can only show what the list
            # holds. Measured 2026-10-08 -- without these two lines a mutant that
            # blanked `validationErrors` while keeping the total passed this test.
            self.assertTrue(pack['validationErrors'],
                            f"{pack['directory']}: INVALID with no reason to show")
            self.assertEqual(len(pack['validationErrors']),
                             min(pack['validationErrorCount'], domain_packs.MAX_ERRORS),
                             f"{pack['directory']}: reasons and their stated total "
                             'disagree')
            for line in pack['validationErrors']:
                self.assertTrue(0 < len(line) <= domain_packs.MAX_ERROR_CHARS)
                self.assertNotIn('\n', line, 'a checker reason must arrive as one line')

    def test_the_projection_distinguishes_directories_from_compliant_packs(self):
        # The claim this route replaces was a single hand-typed number. The projection
        # has two, and they are only equal when every pack really does validate.
        validates = self.doc['counts']['byValidation'][domain_packs.VALIDATES]
        self.assertLessEqual(validates, self.doc['counts']['packs'])
        if validates != self.doc['counts']['packs']:
            self.assertGreater(self.doc['counts']['packs'] - validates, 0)

    def test_identity_fields_come_from_the_manifest_and_absent_ones_stay_null(self):
        for pack in self.doc['packs']:
            manifest = PACK_ROOT / pack['directory'] / 'manifest.json'
            if not manifest.is_file():
                continue
            declared = json.loads(manifest.read_text(encoding='utf-8'))
            self.assertEqual(pack['packId'], declared.get('pack_id'))
            self.assertEqual(pack['version'], declared.get('version'))
            self.assertEqual(pack['domain'], declared.get('domain'))
            self.assertEqual(pack['manifestSchemaVersion'], declared.get('schema_version'))
            if 'domain' not in declared:
                self.assertIsNone(pack['domain'],
                                  f"{pack['directory']}: a v1 pack must not be handed a domain")

    def test_the_verdict_vocabulary_is_closed(self):
        self.assertEqual(set(self.doc['validationVocabulary']),
                         set(domain_packs.VALIDATION_STATES))
        for pack in self.doc['packs']:
            self.assertIn(pack['validation'], domain_packs.VALIDATION_STATES)
        self.assertEqual(self.doc['checker']['state'], 'LOADED')

    def test_the_meaning_fields_refuse_an_e1_reading_of_a_host_run(self):
        # VALIDATES is a statement about files. If the payload ever stopped saying so,
        # the page would be advertising accepted domain capability from a directory scan.
        self.assertIn('STRUCTURAL', self.doc['meaning'])
        self.assertIn('null', self.doc['unmeasuredMeans'])


class TempRootPackTests(unittest.TestCase):
    def test_a_complete_a_broken_and_an_unreadable_pack_each_get_their_own_state(self):
        def build_packs(packs: Path) -> None:
            make_pack(packs, 'alpha-design')
            make_pack(packs, 'bravo-design', complete=False)
            make_pack(packs, 'charlie-design', raw='{ not json at all')
            (packs / 'delta-design').mkdir()

        with tempfile.TemporaryDirectory() as tmp:
            root = stage_root(Path(tmp), build_packs)
            doc = domain_packs.build(root)

        by_state = {pack['directory']: pack for pack in doc['packs']}
        self.assertEqual(by_state['alpha-design']['validation'], domain_packs.VALIDATES)
        self.assertIsNone(by_state['alpha-design']['note'])
        self.assertEqual(by_state['bravo-design']['validation'], domain_packs.INVALID)
        self.assertTrue(any('files.' in error for error in
                            by_state['bravo-design']['validationErrors']),
                        by_state['bravo-design']['validationErrors'])
        self.assertEqual(by_state['charlie-design']['validation'], domain_packs.UNREADABLE)
        self.assertEqual(by_state['charlie-design']['packId'], None)
        self.assertEqual(by_state['delta-design']['validation'], domain_packs.UNREADABLE)
        self.assertEqual(doc['counts']['packs'], 4)
        self.assertEqual(doc['counts']['byValidation'][domain_packs.VALIDATES], 1)
        self.assertEqual(doc['counts']['byValidation'][domain_packs.INVALID], 1)
        self.assertEqual(doc['counts']['byValidation'][domain_packs.UNREADABLE], 2)
        self.assertEqual(doc['counts']['byValidation'][domain_packs.NOT_CHECKED], 0)

    def test_a_schema_violation_is_invalid_not_unreadable(self):
        # The manifest parses, so the identity is readable; only the verdict may not be
        # claimed. Collapsing the two would hide which pack declared what.
        def build_packs(packs: Path) -> None:
            make_pack(packs, 'alpha-design', overrides={'domain': None})

        with tempfile.TemporaryDirectory() as tmp:
            doc = domain_packs.build(stage_root(Path(tmp), build_packs))
        self.assertEqual(doc['packs'][0]['validation'], domain_packs.INVALID)
        self.assertEqual(doc['packs'][0]['packId'], 'alpha-design')
        self.assertIsNone(doc['packs'][0]['domain'])
        self.assertTrue(any("'domain' is a required property" in error
                            for error in doc['packs'][0]['validationErrors']),
                        doc['packs'][0]['validationErrors'])

    def test_without_the_checker_no_pack_is_given_a_verdict(self):
        """Fail closed on the checker itself: an absent authority is NOT_CHECKED."""
        def build_packs(packs: Path) -> None:
            make_pack(packs, 'alpha-design')

        with tempfile.TemporaryDirectory() as tmp:
            root = stage_root(Path(tmp), build_packs)
            (root / CHECKER.relative_to(ROOT)).unlink()
            doc = domain_packs.build(root)
        pack = doc['packs'][0]
        self.assertEqual(doc['checker']['state'], 'UNAVAILABLE')
        self.assertEqual(pack['validation'], domain_packs.NOT_CHECKED)
        self.assertIn('checker', pack['note'])
        self.assertEqual(doc['counts']['byValidation'][domain_packs.VALIDATES], 0)

    def test_a_missing_pack_root_is_reported_as_missing_not_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            doc = domain_packs.build(Path(tmp))
        self.assertEqual(doc['rootState'], domain_packs.ROOT_MISSING)
        self.assertEqual(doc['packs'], [])
        self.assertEqual(doc['counts']['packs'], 0)

    def test_a_symbolic_link_pack_gets_no_verdict(self):
        # Branch guard without needing OS link privileges: the loader asks is_symlink(),
        # so the guard is exercised against a real pack path with that one probe stubbed.
        pack = next(p for p in PACK_ROOT.iterdir() if p.is_dir())
        with patch.object(Path, 'is_symlink', return_value=True):
            entry = domain_packs._pack_entry(pack, None, None)
        self.assertEqual(entry['validation'], domain_packs.NOT_CHECKED)
        self.assertIsNone(entry['packId'], 'a link must not be read as a declared identity')
        self.assertIn('symbolic link', entry['note'])


class RouteTests(unittest.TestCase):
    def request(self, port, token, path='/api/domains', method='GET'):
        req = Request(f'http://127.0.0.1:{port}{path}', method=method,
                      headers={'Authorization': f'Bearer {token}'} if token else {})
        try:
            with urlopen(req, timeout=10) as response:
                return response.status, json.loads(response.read())
        except HTTPError as error:
            return error.code, json.loads(error.read())

    def test_the_route_serves_the_projection_and_refuses_writes(self):
        from design_lab.http_service import make_server
        from design_lab.service import ProjectService

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'AGENTS.md').write_text('# domain route probe', encoding='utf-8')
            token = secrets.token_hex(32)
            with patch.dict(os.environ, {'PROJECT_LOCAL_ROOT': str(root / '.project-local')}):
                service = ProjectService(str(root))
                server = make_server(service, token, port=0)
                port = server.server_address[1]
                worker = threading.Thread(target=server.serve_forever, daemon=True)
                worker.start()
                try:
                    denied = self.request(port, '')
                    body = self.request(port, token)
                    posted = self.request(port, token, method='POST', path='/api/domains')
                    put = self.request(port, token, method='PUT', path='/api/domains')
                finally:
                    server.shutdown()
                    worker.join()
                    server.server_close()

        self.assertEqual(denied[0], 401, denied)
        self.assertEqual(body[0], 200, body)
        projection = domain_packs.build(ROOT)
        self.assertEqual(body[1]['schemaVersion'], domain_packs.SCHEMA_VERSION)
        # Same records, same derived counts, over the wire as in-process.
        self.assertEqual(body[1]['counts'], projection['counts'])
        self.assertEqual([pack['directory'] for pack in body[1]['packs']],
                         [pack['directory'] for pack in projection['packs']])
        self.assertEqual(body[1]['rootState'], domain_packs.ROOT_PRESENT)
        # Read-only by design: no POST and no PUT form of this path exists.
        self.assertEqual(posted[0], 404, posted)
        self.assertEqual(put[0], 405, put)


class ShellClaimTests(unittest.TestCase):
    """The #/domains view may not carry the number that started this.

    Extraction failures assert loudly rather than returning '' -- a static gate that
    finds zero matches passes forever, which is the shape of every claim bug here.
    """

    def setUp(self):
        self.shell = SHELL.read_text(encoding='utf-8')

    def _region(self, start: str, end: str, name: str) -> str:
        """Source between two anchors, or a hard failure if either moved.

        Deliberately marker-based rather than brace-matched: shell.ts carries template
        literals and Chinese punctuation, and a scanner that loses count produces a
        silently truncated region -- which would make these claim checks vacuous.
        """
        begin = self.shell.find(start)
        self.assertNotEqual(begin, -1, f'{name} is missing from shell.ts -- the gate '
                                      'must not pass because the page stopped declaring it')
        stop = self.shell.find(end, begin)
        self.assertNotEqual(stop, -1, f'{name}: the end marker {end!r} is gone, so the '
                                      'region cannot be bounded and this gate proves nothing')
        return self.shell[begin:stop]

    def test_the_domains_view_reads_through_the_seam_and_reports_its_shape(self):
        body = self._region('export async function renderDomains(',
                            '\nexport async function renderSettings', 'renderDomains')
        self.assertIn("apiOrEmpty<DomainListResponse>('/domains'", body)
        self.assertIn('shapeNoticeRows(data)', body)
        self.assertIn('emptyLi(data,', body)
        self.assertIn("el('ul', { class: 'list' },", body)
        self.assertIn('domainPackRow', body)
        self.assertIn('domainVerdict(pack.validation)', body)

    def test_the_verdict_word_is_marked_and_never_translated(self):
        # en() is how a service state word survives a lang="zh-CN" page without becoming
        # a second vocabulary (WCAG 3.1.2). The row builder must route every verdict
        # through it, and the no-verdict case must NOT be wrapped in one.
        helpers = self._region('export function domainVerdict(',
                               '\nexport async function renderDomains', 'domainVerdict')
        self.assertIn('? DOMAIN_UNREAD : en(value)', helpers)

    def test_the_view_counts_records_and_never_the_summary_scalars(self):
        # `counts.packs` / `counts.byValidation[...]` are scalars, and normaliseShape
        # refills collections only: a response that omitted them would be displayed as
        # the zero the service never answered. The cards count the rows instead.
        body = self._region('export async function renderDomains(',
                            '\nexport async function renderSettings', 'renderDomains')
        kpi_block = body[body.index('const kpis'):body.index('const unavailable')]
        self.assertIn('String(packs.length)', kpi_block)
        self.assertIn("judged('VALIDATES')", kpi_block)
        self.assertNotIn('data.counts.packs', kpi_block)

    def test_no_pack_count_is_typed_into_the_shell(self):
        # 2026-10-08: VIEW_NOT_OPEN and CAPABILITY_REGISTRY both stated "13 个域包" while
        # the repo's checker accepts 12 of the 13 directories. Every number a reader sees
        # now comes from the projection, so the literals must stay gone.
        found = re.findall(r'\d+\s*个域包', self.shell)
        self.assertEqual(found, [], f'hand-typed pack counts returned to shell.ts: {found}')

    def test_the_domains_slot_is_no_longer_declared_unopened(self):
        declared = self._region('export const VIEW_NOT_OPEN', '\n};', 'VIEW_NOT_OPEN')
        self.assertNotIn("'design-domains'", declared,
                         'the slot still claims it has no readback route')
        self.assertIn("'collaboration'", declared, 'the remaining honest slot disappeared')

    def test_an_implemented_capability_row_names_a_route_that_is_dispatched(self):
        """The registry is a claim register, so an IMPLEMENTED row is checked against
        the HTTP layer. The PLANNED/BLOCKED rows are exempt by design: they claim
        nothing is reachable. The rule is only meaningful while at least one row claims
        IMPLEMENTED, so that is asserted too instead of being left assumed."""
        registry = self._region('const CAPABILITY_REGISTRY', '\n] as const;',
                                'CAPABILITY_REGISTRY')
        # The dispatch shape is data now (`http_service.ROUTES`), not an if/elif chain of
        # `self.path == ...` comparisons. Read the inventory itself: grepping for the old
        # textual shape would pass on a file that no longer dispatches that way.
        from design_lab.http_service import ROUTES
        dispatched = {route.pattern for route in ROUTES if route.method == 'GET'}
        rows = re.findall(r"capabilityId: '([^']+)'(.*?)nextAction:", registry, re.S)
        self.assertTrue(rows, 'no capability rows extracted')
        implemented = [(name, body) for name, body in rows
                       if "implementationState: 'IMPLEMENTED'" in body]
        # This case exists to hold the 设计领域 row to its own claim, so it asserts that row is
        # present and checked, not that it is alone. It used to pin the whole IMPLEMENTED set to
        # ['design-domain-model'], which meant a second honest row anywhere in the registry failed a
        # domain-pack gate -- and the route regex below only understands a flat '/api/x' path, so a
        # scoped route like /api/projects/{id}/research could not have passed it however true it was.
        # The general property ("no row may claim IMPLEMENTED over a route the service does not
        # dispatch") is not dropped by this: design-lab/scripts/verify_capability_self_description.py
        # owns it, matches `{id}` segment by segment, adds the slot linkage, and runs in the local
        # aggregate -- and its own teeth test refuses a weakened copy of that comparison.
        names = [name for name, _ in implemented]
        self.assertIn('design-domain-model', names,
                      'the IMPLEMENTED claim this gate exists to check has disappeared')
        self.assertEqual(len(names), len(set(names)),
                         'a capability row is claimed IMPLEMENTED twice, so one of them is not '
                         'the row this gate can vouch for')
        self.assertTrue(implemented, 'no row claims IMPLEMENTED, so the rule below checks nothing')
        # Flat-route grammar: a one-segment route is an exact entry in ROUTES, and
        # a scoped route (/api/projects/{id}/research) is a compiled regex instead, so this gate
        # literally cannot vouch for one. Rows outside its grammar are named here rather than left
        # silently unchecked -- verify_capability_self_description.py matches those segment by
        # segment, and a weakened copy of that comparison is convicted by its own teeth test.
        flat = [(name, body) for name, body in implemented
                if re.search(r"route: 'GET /api/[a-z0-9-]+'", body)]
        outside = sorted(name for name, body in implemented
                         if not re.search(r"route: 'GET /api/[a-z0-9-]+'", body))
        for name, body in flat:
            route = re.search(r"route: 'GET (/api/[a-z0-9-]+)'", body)
            self.assertIsNotNone(route, f'{name}: an IMPLEMENTED row declares no exact route')
            path = route.group(1)
            self.assertIn(path, dispatched,
                          f'{name}: claims {path} is implemented, but http_service.py '
                          'does not dispatch it')
        self.assertTrue(flat, 'no IMPLEMENTED row is inside this gate\'s grammar, so it proves '
                        'nothing about the registry it reads')
        self.assertEqual(outside, ['research-insights'],
                         f'IMPLEMENTED rows outside the flat grammar are now {outside}; each one '
                         'must be named here and covered by '
                         'verify_capability_self_description.py')

    def test_the_two_languages_declare_the_same_validation_vocabulary(self):
        # LANGUAGE-POLICY §5: an enum may be hand-copied only where a check proves both
        # copies agree. Order included, because the payload publishes the vocabulary as a
        # list and the page iterates the tally it is built from.
        text = CONTRACTS.read_text(encoding='utf-8')
        block = re.search(r'export type DomainPackValidation =([^;]+);', text)
        self.assertIsNotNone(block, 'DomainPackValidation is missing from contracts.ts; '
                                    'the TS-side copy of the enum cannot be verified')
        declared = tuple(re.findall(r"'([A-Z_]+)'", block.group(1)))
        self.assertEqual(declared, domain_packs.VALIDATION_STATES,
                         'the TypeScript union and the Python vocabulary disagree')



if __name__ == '__main__':
    unittest.main()
