# SPDX-License-Identifier: MIT
"""The recorded model choice: three states kept apart, a snapshot copied, nothing promoted.

The owner un-locked model choice (「不锁死 做好菜单导航和接口 用户自行选择本地或者是云端模型」) and
said the identifier fields may be filled or explicitly not used. A picker that forgets the answer on
the next request is still locked, so these cases drive the choice over HTTP and check what survives:
who chose, what the catalogue said at that moment, and that no run, qualification or send is implied.

Every expectation is read from `GET /api/models` in the test rather than copied from the registry
files, so a registry edit moves the catalogue and this file together instead of leaving a hand-typed
model name as a second source.
"""
from __future__ import annotations

import http.client
import json
import os
import secrets
import sqlite3
import sys
import tempfile
import threading
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
# Literal inserts naming each root: verify_test_selfsufficiency.py credits only a module that puts
# the root on sys.path in its own statement.
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(ROOT / 'design-lab' / 'tests'))

from design_lab.model_selection import (  # noqa: E402
    SCHEMA_PATH, ModelSelectionError, _check)
from design_lab.service import ProjectService  # noqa: E402

CANVAS = (8, 6)


class ModelSelectionTests(unittest.TestCase):
    def setUp(self):
        parent = ROOT / '.project-local/task-runtime/model-selection-http'
        parent.mkdir(parents=True, exist_ok=True)
        os.environ.pop('PROJECT_LOCAL_ROOT', None)
        self._temp = tempfile.TemporaryDirectory(dir=parent)
        self.root = Path(self._temp.name)
        (self.root / 'AGENTS.md').write_text('# model selection fixture', encoding='utf-8')
        from design_lab.http_service import make_server
        self.service = ProjectService(str(self.root))
        self.token = secrets.token_hex(32)
        self.server = make_server(self.service, self.token, port=0)
        self.port = self.server.server_address[1]
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.db = self.service.paths.database_path(self.service.database)

        def _stop(self=self):
            self.server.shutdown()
            self.thread.join()
            self.server.server_close()
        self.addCleanup(_stop)
        self.addCleanup(self._temp.cleanup)

    def call(self, method, path, body=None):
        headers = {'Authorization': 'Bearer ' + self.token,
                   'Host': f'127.0.0.1:{self.port}',
                   'Origin': f'http://127.0.0.1:{self.port}',
                   'Sec-Fetch-Site': 'same-origin'}
        raw = None
        if body is not None:
            headers['Content-Type'] = 'application/json'
            raw = json.dumps(body).encode('utf-8')
        conn = http.client.HTTPConnection('127.0.0.1', self.port, timeout=15)
        try:
            conn.request(method, path, body=raw, headers=headers)
            response = conn.getresponse()
            return response.status, json.loads(response.read() or b'null')
        finally:
            conn.close()

    def expect(self, method, path, body, status):
        got, payload = self.call(method, path, body)
        self.assertEqual(got, status, f'{method} {path} -> {got}: '
                                      f'{json.dumps(payload, ensure_ascii=False)[:400]}')
        return payload

    def project(self):
        return self.expect('POST', '/api/projects', {'name': 'Selection project'},
                           201)['project']['id']

    def catalogue(self):
        document = self.expect('GET', '/api/models', None, 200)
        return {row['model_id']: row for row in document['models']}

    def choose(self, project, **body):
        payload = {'model_id': None, 'declared_unused': False, 'actor': 'dtalex66',
                   'actor_kind': 'human'}
        payload.update(body)
        return self.expect('POST', f'/api/projects/{project}/model-selection/choose', payload, 201)

    def read(self, project):
        return self.expect('GET', f'/api/projects/{project}/model-selection', None, 200)

    # -- the three states -------------------------------------------------------

    def test_never_asked_declined_and_chosen_are_three_different_answers(self):
        project = self.project()
        cold = self.read(project)
        self.assertEqual('NEVER_ASKED', cold['state'])
        self.assertIsNone(cold['selection'])
        self.assertEqual(0, cold['revision_count'])
        self.assertTrue(any('NEVER_ASKED' in line for line in cold['does_not_say']),
                        'the readback must keep "nobody was asked" distinct from "declined"')

        model_id = next(iter(self.catalogue()))
        self.choose(project, model_id=model_id)
        self.assertEqual('CHOSEN', self.read(project)['state'])

        declined = self.choose(project, declared_unused=True)
        self.assertEqual('DECLINED', declined['state'])
        self.assertIsNone(declined['selection']['model_id'])
        self.assertIsNone(declined['selection']['snapshot'],
                          'a declination carries no catalogue facts; it says nothing was picked')
        self.assertEqual('DECLINED', self.read(project)['state'])

    def test_the_choice_carries_the_catalogues_facts_at_the_moment_of_choosing(self):
        project = self.project()
        row = self.catalogue()['sam2'] if 'sam2' in self.catalogue() else next(
            iter(self.catalogue().values()))
        recorded = self.choose(project, model_id=row['model_id'])['selection']
        self.assertEqual('design-lab/model-selection/v1', recorded['schemaVersion'])
        self.assertEqual(row['model_id'], recorded['model_id'])
        self.assertEqual({'placement': row['placement'], 'radar_state': row['radar_state'],
                          'machine_state': row['machine_state'],
                          'commercial_use': row['commercial_use'],
                          'weights_recorded': row['weights_recorded'],
                          'qualified_local': row['radar_state'] == 'QUALIFIED_LOCAL'},
                         recorded['snapshot'],
                         'the snapshot must be what the catalogue said, copied by the service')
        self.assertNotIn('executed', self.read(project)['selection'],
                         'a selection document carries no execution field at all: the choice is '
                         'not a run, and a false here would still be a claim about running')

    def test_a_choice_is_replayed_and_a_change_of_mind_appends(self):
        project = self.project()
        models = list(self.catalogue())
        first = self.choose(project, model_id=models[0])
        again = self.choose(project, model_id=models[0])
        self.assertTrue(again['replayed'], 'the same answer twice appended a second decision')
        self.assertEqual(first['revision_count'], again['revision_count'])
        changed = self.choose(project, model_id=models[1])
        self.assertFalse(changed['replayed'])
        self.assertEqual(2, changed['revision_count'])
        readback = self.read(project)
        self.assertEqual(models[1], readback['selection']['model_id'])
        self.assertEqual(2, readback['revision_count'], 'the decision path lost a revision')
        self.assertEqual([1, 2], [row['revision'] for row in readback['history']])

    # -- refusals ---------------------------------------------------------------

    def test_an_ambiguous_or_unattributed_choice_is_refused(self):
        project = self.project()
        status, body = self.call('POST', f'/api/projects/{project}/model-selection/choose',
                                 {'model_id': None, 'declared_unused': False,
                                  'actor': 'dtalex66', 'actor_kind': 'human'})
        self.assertEqual(400, status)
        self.assertEqual('MODEL_SELECTION_REQUIRED', body['error'])

        model_id = next(iter(self.catalogue()))
        status, body = self.call('POST', f'/api/projects/{project}/model-selection/choose',
                                 {'model_id': model_id, 'declared_unused': True,
                                  'actor': 'dtalex66', 'actor_kind': 'human'})
        self.assertEqual(400, status)
        self.assertEqual('MODEL_SELECTION_CONFLICT', body['error'])

        status, body = self.call('POST', f'/api/projects/{project}/model-selection/choose',
                                 {'model_id': model_id, 'declared_unused': False,
                                  'actor': '   ', 'actor_kind': 'human'})
        self.assertEqual(400, status)
        self.assertEqual('ACTOR_REQUIRED', body['error'])

        status, body = self.call('POST', f'/api/projects/{project}/model-selection/choose',
                                 {'model_id': model_id, 'declared_unused': False,
                                  'actor': 'ci', 'actor_kind': 'HUMAN'})
        self.assertEqual(400, status)
        self.assertEqual('INVALID_ACTOR_KIND', body['error'],
                         'the actor vocabulary is the design layer\'s lowercase one, not a new one')

    def test_a_model_outside_the_catalogue_cannot_be_chosen(self):
        project = self.project()
        status, body = self.call('POST', f'/api/projects/{project}/model-selection/choose',
                                 {'model_id': 'gpt-5-turbo-max', 'declared_unused': False,
                                  'actor': 'dtalex66', 'actor_kind': 'human'})
        self.assertEqual(404, status)
        self.assertEqual('MODEL_NOT_IN_CATALOGUE', body['error'])
        self.assertEqual('NEVER_ASKED', self.read(project)['state'],
                         'a refused choice must not leave a row behind')

    # -- the store's own teeth --------------------------------------------------

    def test_a_recorded_choice_cannot_be_rewritten_or_erased(self):
        project = self.project()
        self.choose(project, declared_unused=True)
        connection = sqlite3.connect(str(self.db))
        self.addCleanup(connection.close)
        try:
            # RAISE(ABORT, …) surfaces as IntegrityError, not OperationalError; the point is that
            # the store itself refuses, not which subclass Python happens to raise.
            with self.assertRaises(sqlite3.IntegrityError):
                connection.execute('UPDATE model_selection SET actor = ? WHERE project_id = ?',
                                   ('whoever', project))
            with self.assertRaises(sqlite3.IntegrityError):
                connection.execute('DELETE FROM model_selection WHERE project_id = ?', (project,))
        finally:
            connection.rollback()

    def test_a_selection_document_that_overstates_itself_is_refused(self):
        good = {
            'schemaVersion': 'design-lab/model-selection/v1', 'project_id': '0' * 32,
            'revision': 1, 'model_id': 'sam2', 'declared_unused': False,
            'snapshot': {'placement': 'huggingface', 'radar_state': 'WATCH',
                         'machine_state': 'ABSENT', 'commercial_use': 'PERMITTED',
                         'weights_recorded': 0, 'qualified_local': False},
            'actor': 'dtalex66', 'actor_kind': 'human', 'recorded_at': '2026-10-20T00:00:00Z',
            'claims_not_made': ['a', 'b', 'c', 'd'],
        }
        self.assertEqual(_check(dict(good)), good)
        # What the contract can refuse: a declination that still carries a model, a document that
        # adds a field about running or applying, and a shape mismatch. That `qualified_local`
        # matches the catalogue is the service's job, not the schema's -- a JSON Schema cannot
        # reach into the registry -- so it is proven by
        # test_the_choice_carries_the_catalogues_facts_at_the_moment_of_choosing instead.
        for label, mutate in (
                ('declination carrying a model',
                 lambda d: d.update({'declared_unused': True, 'model_id': None})),
                ('a run claim', lambda d: d.update({'ran': True})),
                ('an applied flag', lambda d: d.update({'applied': True})),
                ('a model with no snapshot', lambda d: d.update({'snapshot': None})),
                ('an invented state word',
                 lambda d: d.update({'actor_kind': 'HUMAN'}))):
            doctored = json.loads(json.dumps(good))
            mutate(doctored)
            with self.assertRaises(ModelSelectionError) as caught:
                _check(doctored)
            self.assertEqual('MODEL_SELECTION_CONTRACT_VIOLATION', caught.exception.code,
                             f'a document that {label} passed the contract check')

    def test_the_prompt_document_echoes_the_choice_and_still_runs_nothing(self):
        project = self.project()
        brief = self.expect(
            'POST', f'/api/projects/{project}/briefs',
            {'title': 'Selection brief', 'goals': ['read back'], 'constraints': None,
             'reference_asset_ids': [], 'idempotency_key': 'sel-brief'},
            201)['brief']['brief_id']
        before = self.expect('POST', f'/api/projects/{project}/prompts',
                             {'brief_id': brief, 'direction_id': None,
                              'target': 'image-generation'}, 201)['document']
        self.assertEqual('NEVER_ASKED', before['model']['selection_state'])

        model_id = next(iter(self.catalogue()))
        chosen = self.choose(project, model_id=model_id)['selection']
        after = self.expect('POST', f'/api/projects/{project}/prompts',
                            {'brief_id': brief, 'direction_id': None,
                             'target': 'image-generation'}, 201)['document']
        self.assertEqual('CHOSEN', after['model']['selection_state'])
        self.assertEqual(chosen['revision'], after['model']['selected']['revision'])
        self.assertIs(False, after['model']['executed'],
                      'echoing a choice must not turn the composition into a model run')
        self.assertNotEqual(before['composition_id'], after['composition_id'],
                            'the same brief under a different recorded choice produced the same '
                            'document id, so the digest ignores what the document now claims')


if __name__ == '__main__':
    unittest.main()
