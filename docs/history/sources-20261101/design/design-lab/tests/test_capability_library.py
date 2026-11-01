# SPDX-License-Identifier: MIT
"""The capability library projection and its route.

These assert the three properties the projection exists to guarantee, plus one real
HTTP round trip. They deliberately do not assert specific record counts from the data:
the counts are derived from the records in the call, so a test that hardcoded 46 or 14
would pass on a stale checkout and fail on a legitimate addition.
"""
from __future__ import annotations

import json
import os
import secrets
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[2]
import sys
sys.path.insert(0, str(ROOT / 'src'))

from design_lab.analysis import capability_library  # noqa: E402


class EnrichmentTests(unittest.TestCase):
    def setUp(self):
        self.doc = capability_library.build(ROOT)

    def test_every_record_has_one_shape_regardless_of_kind(self):
        # Models are outside the vendor/taxonomy mechanism. If their rows simply
        # omitted those keys, every consumer would need a kind branch and an absent
        # axis would be indistinguishable from an unclassified one.
        shapes = {tuple(sorted(record)) for record in self.doc['capabilities']}
        self.assertEqual(len(shapes), 1, f'{len(shapes)} different record shapes')

    def test_popularity_is_never_presented_without_its_label_and_stamp(self):
        # The taxonomy policy states popularityIsNotQuality; a row that shows stars
        # without that marker turns an observation into a de facto score.
        with_stars = [c for c in self.doc['capabilities'] if c['popularity']]
        self.assertTrue(with_stars, 'no joined records to check the rule against')
        for record in with_stars:
            self.assertTrue(record['popularity']['isNotQuality'])
            self.assertIsNotNone(record['popularity']['observedAt'])

    def test_unclassified_axes_are_derived_and_never_invented(self):
        axes = set(capability_library.CLASSIFICATION_AXES)
        reported = set(self.doc['classification']['unclassifiedAxes'])
        self.assertTrue(reported <= axes, f'invented axes surfaced: {reported - axes}')
        for record in self.doc['capabilities']:
            self.assertTrue(set(record['unclassifiedAxes']) <= axes)
        joined = [c for c in self.doc['capabilities'] if c['sourceType']]
        self.assertEqual(self.doc['classification']['joined'], len(joined))

    def test_a_missing_taxonomy_degrades_the_join_without_failing_the_library(self):
        import shutil
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for rel in (capability_library.LOCK_REL, capability_library.REVISIONS_REL,
                        capability_library.RADAR_REL):
                target = root / rel
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(ROOT / rel, target)
            doc = capability_library.build(root)
        self.assertEqual(doc['classification']['joined'], 0)
        self.assertTrue(doc['capabilities'])
        self.assertTrue(all(c['qualified'] is None for c in doc['capabilities']))


class ProjectionTests(unittest.TestCase):
    def setUp(self):
        self.doc = capability_library.build(ROOT)

    def test_every_record_reports_no_qualification_because_none_is_recorded(self):
        # Qualification is a host run plus a human acceptance. Neither is derivable
        # from a registry, so a projection that said `false` would be claiming the
        # capability was evaluated and failed.
        self.assertTrue(self.doc['capabilities'])
        for record in self.doc['capabilities']:
            self.assertIsNone(record['qualified'], f"{record['id']} claims a verdict")
            self.assertIsNone(record['qualificationEvidence'])
        counts = self.doc['counts']
        self.assertEqual(len(self.doc['capabilities']), counts['total'])
        self.assertEqual(0, counts['qualifiedTrue'],
                         'a qualification needs a host run and a human acceptance; neither exists '
                         'in this repository, so nothing may be reported as qualified')
        self.assertEqual(0, counts['qualifiedFalse'])
        self.assertEqual(0, counts['qualificationVerdicts'])
        self.assertEqual(counts['total'], counts['qualificationNotAdjudicated'],
                         'the split has to partition the records it counted, not hint at a third '
                         'category nobody reported')

    def test_absent_revision_is_not_verified_never_absent_provenance(self):
        states = {r['id']: r['revisionState'] for r in self.doc['capabilities']}
        self.assertNotIn(None, states.values())
        self.assertNotIn('', states.values())
        # Models are outside the vendor revision mechanism entirely.
        for record in self.doc['capabilities']:
            if record['kind'] == 'model':
                self.assertEqual(record['revisionState'], 'NOT_VERIFIED')

    def test_counts_are_derived_from_the_records_in_this_call(self):
        counts = self.doc['counts']
        self.assertEqual(counts['total'], len(self.doc['capabilities']))
        self.assertEqual(sum(counts['byKind'].values()), counts['total'])
        self.assertEqual(sum(counts['byRevisionState'].values()), counts['total'])
        self.assertEqual(sum(counts['byLicense'].values()), counts['total'])
        lock = json.loads((ROOT / capability_library.LOCK_REL).read_text(encoding='utf-8'))
        self.assertEqual(counts['byKind']['source'], len(lock['sources']))

    def test_a_missing_input_fails_closed_rather_than_projecting_a_partial_library(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(FileNotFoundError):
                capability_library.build(Path(tmp))

    def test_unmeasured_semantics_are_published_with_the_data(self):
        # The view prints this so a reader cannot take a blank as a zero.
        self.assertIn('null', self.doc['unmeasuredMeans'])


class RouteTests(unittest.TestCase):
    def test_the_route_serves_the_projection_over_the_real_service(self):
        from design_lab.service import ProjectService
        from design_lab.http_service import make_server

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'AGENTS.md').write_text('# capability route probe', encoding='utf-8')
            token = secrets.token_hex(32)
            with patch.dict(os.environ, {'PROJECT_LOCAL_ROOT': str(root / '.project-local')}):
                service = ProjectService(str(root))
                server = make_server(service, token, port=0)
                port = server.server_address[1]
                worker = threading.Thread(target=server.serve_forever, daemon=True)
                worker.start()
                try:
                    unauthenticated = self._get(port, '')
                    self.assertEqual(unauthenticated.getcode(), 401)
                    body = json.loads(self._get(port, token).read().decode('utf-8'))
                finally:
                    server.shutdown()
                    worker.join()
                    server.server_close()
        self.assertEqual(body['schemaVersion'], capability_library.SCHEMA_VERSION)
        self.assertEqual(body['counts']['total'], len(body['capabilities']))

    def _get(self, port, token):
        request = Request(f'http://127.0.0.1:{port}/api/capabilities')
        if token:
            request.add_header('Authorization', f'Bearer {token}')
        try:
            return urlopen(request, timeout=10)
        except Exception as error:      # noqa: BLE001 - 401 arrives as URLError
            code = getattr(error, 'code', None)
            if code == 401 and not token:
                class Handled:
                    def getcode(self): return 401
                return Handled()
            raise


class AxisPassthroughTests(unittest.TestCase):
    """DL-FINAL-T06 / DL-UI-U03: the seven axes must carry their **values**, and a
    recorded qualification must reach the UI instead of being overwritten by null.

    Both halves are measured against the real inputs and against one synthetic
    record, because the shipped data currently populates none of the seven axes:
    a test that only reads the real tree would pass whether or not the passthrough
    worked at all, and a test that only synthesises would not notice if the real
    join broke.
    """

    def _root_with_taxonomy(self, entry_extra: dict) -> Path:
        import shutil
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        for rel in (capability_library.LOCK_REL, capability_library.REVISIONS_REL,
                    capability_library.RADAR_REL):
            target = root / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / rel, target)
        joined = next(c for c in capability_library.build(ROOT)['capabilities']
                      if c.get('repo'))
        entry = {'candidateId': 'synthetic-axis-probe', 'canonicalRepo': joined['repo'],
                 'sourceType': 'skill'}
        entry.update(entry_extra)
        tax = root / capability_library.TAXONOMY_REL
        tax.parent.mkdir(parents=True, exist_ok=True)
        tax.write_text(json.dumps({'entries': [entry]}, ensure_ascii=False),
                       encoding='utf-8')
        return root

    def test_shipped_data_populates_no_axis_and_keeps_the_two_empties_apart(self):
        # Measured on 2026-10-09: 37 joined candidates carry the axis fields as EMPTY
        # containers ([] / {}) and `tier` is absent (null) everywhere; zero axes hold a
        # value. The projection must preserve that distinction, because "the taxonomy
        # has the field but nobody classified this one" and "this row has no such field
        # at all" are different things for a UI to say -- and if a human classification
        # round ever fills an axis, the truthy assertion below is what must change, and
        # it changes because the data changed, not because the code dropped values.
        joined = [c for c in self.doc['capabilities'] if c['sourceType']]
        self.assertTrue(joined, 'no joined records, so this test measures nothing')
        for record in self.doc['capabilities']:
            self.assertFalse([a for a, v in record['axes'].items() if v],
                             f"{record['id']} carries an axis value the test did not expect")
        for record in joined:
            self.assertEqual(record['axes']['domains'], [],
                             'a joined candidate lost its empty-but-present axis field')
        self.assertTrue(all(c['axes']['tier'] is None for c in joined),
                        '`tier` is declared but never populated; null is the honest value')

    def setUp(self):
        self.doc = capability_library.build(ROOT)

    def test_every_record_carries_all_seven_axis_keys(self):
        axes = set(capability_library.CLASSIFICATION_AXES)
        for record in self.doc['capabilities']:
            self.assertEqual(set(record['axes']), axes,
                             'a record is missing axis keys, so a view must special-case it')

    def test_a_populated_axis_reaches_the_projection(self):
        root = self._root_with_taxonomy({
            'domains': ['brand'], 'tier': 'T2',
            'qualification': {'qualified': True, 'evidence': ['host-run-1', 'jury-accept-1']},
        })
        doc = capability_library.build(root)
        joined = [c for c in doc['capabilities'] if c['axes']['domains'] == ['brand']]
        self.assertTrue(joined, 'a populated axis was dropped by the projection')
        record = joined[0]
        self.assertEqual(record['axes']['tier'], 'T2')
        self.assertNotIn('domains', record['unclassifiedAxes'],
                         'an axis with a value is still reported as unclassified')
        self.assertIs(record['qualified'], True,
                      'a recorded qualification was overwritten by the default')
        self.assertEqual(record['qualificationEvidence'], ['host-run-1', 'jury-accept-1'])
        self.assertIsNone(record['qualificationReason'])

    def test_no_record_still_means_unknown_with_a_stated_reason(self):
        root = self._root_with_taxonomy({'domains': ['brand']})
        doc = capability_library.build(root)
        record = next(c for c in doc['capabilities'] if c['axes']['domains'] == ['brand'])
        self.assertIsNone(record['qualified'],
                          'an absent record must stay unknown, not become false')
        self.assertIn('没有资格记录', record['qualificationReason'])
        # The falsification the other way: the reason must not be a bare word the
        # reader cannot act on -- it names the two evidences that would qualify.
        self.assertIn('宿主', record['qualificationReason'])
        self.assertIn('真人', record['qualificationReason'])

if __name__ == '__main__':
    unittest.main()
