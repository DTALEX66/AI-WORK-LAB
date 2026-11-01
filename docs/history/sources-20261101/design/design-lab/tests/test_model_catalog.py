# SPDX-License-Identifier: MIT
"""The picker reads two registries and must not merge them, promote anyone, or claim a transport.

`GET /api/models` exists because the owner un-locked model choice on 2026-10-20 (「不锁死 做好菜单导航和接口
用户自行选择本地或者是云端模型」). Every assertion here is checked against the registry files re-read from
disk in this test, not against the module's own arithmetic -- otherwise a bug in the counter and the
test's expectation would move together.
"""
from __future__ import annotations

import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
# Literal inserts naming the roots: verify_test_selfsufficiency.py only credits a module that
# claims `src` in the sys.path statement itself, and this file imports `design_lab` directly.
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(ROOT / 'design-lab' / 'tests'))

from design_lab.model_catalog import (  # noqa: E402
    CLAIMS_NOT_MADE, PLACEMENTS, catalog)

RADAR = ROOT / 'design-lab' / 'readiness' / 'model-radar.json'
PROVIDERS = ROOT / 'design-lab' / 'config' / 'provider-capabilities.json'


class ModelCatalogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.radar = json.loads(RADAR.read_text(encoding='utf-8'))
        cls.providers = json.loads(PROVIDERS.read_text(encoding='utf-8'))
        cls.document = catalog()

    def test_the_catalog_reports_every_row_the_registries_hold(self):
        self.assertEqual('design-lab/model-catalog/v1', self.document['schemaVersion'])
        self.assertEqual(len(self.radar['entries']), self.document['counts']['models'],
                         'a radar entry vanished from the picker')
        self.assertEqual(len(self.providers['providers']), self.document['counts']['endpoints'],
                         'an endpoint vanished from the picker')
        self.assertEqual({entry['model_id'] for entry in self.radar['entries']},
                         {row['model_id'] for row in self.document['models']})

    def test_nothing_is_promoted_and_nothing_default_enables(self):
        """The numbers that make a "ready" chip a lie today, pinned as measured zero."""
        counts = self.document['counts']
        self.assertEqual(0, counts['qualified_local'],
                         'the picker now reports a qualified local model; that is a licence and '
                         'qualification ruling the owner has not made, so this test must be changed '
                         'in the same change as the registry, on purpose')
        self.assertEqual(0, counts['default_enabled_true'],
                         'a row default-enables itself; the radar rule says only QUALIFIED_LOCAL '
                         'may, so the registry and this claim need re-reading together')
        self.assertEqual(0, counts['weights_recorded'],
                         'weight hashes were recorded; re-check whether that earns a state change '
                         'rather than quietly raising the picker\'s claim')
        self.assertTrue(all(row['default_enabled'] is False for row in self.document['models']))

    def test_placement_and_evidence_are_copied_not_invented(self):
        source = {entry['model_id']: entry for entry in self.radar['entries']}
        for row in self.document['models']:
            origin = source[row['model_id']]
            self.assertEqual(origin['source']['kind'], row['placement'])
            self.assertIn(row['placement'], PLACEMENTS)
            self.assertEqual(origin['radar_state'], row['radar_state'])
            self.assertEqual(origin['machine_state'], row['machine_state'])
            self.assertEqual(len(origin['weights_sha256']), row['weights_recorded'])
            self.assertEqual(origin['rights']['commercial_use'], row['commercial_use'])
            self.assertEqual(origin.get('blocking_reason'), row['blocking_reason'])
        self.assertTrue(all(row['evidence_level'] == 'E0' for row in self.document['endpoints']),
                        'an endpoint claims a level the record does not carry')

    def test_the_two_registries_are_never_joined(self):
        self.assertIsNone(self.document['join']['key'],
                          'a join key appeared; there is no shared field between model_id and '
                          'provider_id, so a merged table would fabricate the relationship')
        self.assertIn('model_id', str(self.document['join']['reason']))

    def test_the_catalog_says_choosing_is_not_calling(self):
        selection = self.document['selection']
        self.assertEqual('USER_CHOSEN_NOT_LOCKED', selection['mode'])
        self.assertEqual('NOT_CONNECTED', selection['transport'])
        self.assertIs(False, selection['executed'])
        self.assertTrue(any('fail-closed' in rule for rule in selection['rules']),
                        'the un-locked picker must still state that defaults stay closed')
        self.assertTrue(any('离开本机' in rule for rule in selection['rules']),
                        'a cloud choice has to name the data-leaving consequence')
        self.assertEqual(list(CLAIMS_NOT_MADE), self.document['claims_not_made'])
        self.assertEqual(4, len(self.document['claims_not_made']))

    def test_the_route_exists_and_answers_the_catalog(self):
        from design_lab.http_service import ROUTES
        models_routes = [route for route in ROUTES if route.pattern == '/api/models']
        self.assertEqual(1, len(models_routes), 'the picker has no single stable route')
        self.assertEqual('GET', models_routes[0].method)
        document = catalog()
        self.assertEqual(document['counts']['placement'],
                         {'local': sum(1 for e in self.radar['entries']
                                       if e['source']['kind'] == 'local'),
                          'huggingface': sum(1 for e in self.radar['entries']
                                             if e['source']['kind'] == 'huggingface'),
                          'vendor': sum(1 for e in self.radar['entries']
                                         if e['source']['kind'] == 'vendor')},
                         'the placement histogram must equal a recount from the registry')


if __name__ == '__main__':
    unittest.main()
