# SPDX-License-Identifier: MIT
"""The project roll-up the desk's front page reads: null means "never opened", 0 means "empty".

Stitch screen D01 asks each project row for what it holds, what still waits on a named human, and
when it last moved. ``GET /api/projects`` answered with ``{id, name, created_at}``, so a page had
either to guess or to fan out per project per resource. This suite pins the three ways that
translation can go wrong:

* **absent reported as empty.** a surface whose table was never created must be ``null`` and named
  in ``absentSurfaces``; ``0`` there would tell a person "this project has no prompt results", which
  is a different fact from "nothing has produced a prompt result here yet". The contrast is asserted
  inside one row: the base ``asset`` table exists from project creation, so assets really are 0
  while every unopened surface is null;
* **two implementations of one verdict.** the pending numbers come out of the same
  ``_state_of`` predicate the prompt-result read-back uses and out of the candidate resource's own
  read-back. The drift test plants a signature that quotes other bytes and requires both surfaces
  to say ``NOT_CURRENT`` -- if either counts it as accepted or as first-time unsigned, this fails;
* **a roll-up that contradicts its own contract** must be refused, not served: the module validates
  the envelope through ``design-lab/schemas/project-list-v1.schema.json`` and the route answers 500
  with a named code.

Nothing here proves a model ran or a person was who they said they were: counts are records in a
local store, and the signature is a self-declared name (owner ruling 2026-10-21 keeps acceptance
human-only, inference unwired, export read-back only).
"""
from __future__ import annotations

import json
import os
import secrets
import sqlite3
import sys
import tempfile
import threading
import unittest
from contextlib import closing
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / 'src'))

import http.client                                                   # noqa: E402
from design_lab.http_service import make_server                       # noqa: E402
from design_lab.interop import load_schema, schema_errors             # noqa: E402
from design_lab.knowledge_review import KnowledgeReview               # noqa: E402
from design_lab.project_index import (ProjectIndex, ProjectIndexError,  # noqa: E402
                                      PROJECT_LIST_VERSION)
from design_lab.prompt_results import PromptResults                   # noqa: E402
from design_lab.service import ProjectService                         # noqa: E402

UNOPENED = ('promptResults', 'knowledgeCandidates', 'briefs', 'directions')


class ProjectRollUpTests(unittest.TestCase):
    def setUp(self):
        os.environ.pop('PROJECT_LOCAL_ROOT', None)
        self.base = Path(tempfile.mkdtemp(dir=REPO / '.project-local' / 'task-runtime'))
        self.project = self.base / 'project'
        self.project.mkdir()
        (self.project / 'AGENTS.md').write_text('# project roll-up fixture', encoding='utf-8')
        self.service = ProjectService(self.project)
        self.project_id = self.service.create_project('Roll-up Desk')['id']
        self.token = secrets.token_hex(32)
        self.httpd = make_server(self.service, self.token, 0)
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.httpd.shutdown()
        self.httpd.server_close()
        self.thread.join(timeout=5)

    def call(self, method, path, body=None):
        connection = http.client.HTTPConnection('127.0.0.1', self.httpd.server_address[1],
                                                timeout=20)
        headers = {'Authorization': 'Bearer ' + self.token,
                   'Origin': f'http://127.0.0.1:{self.httpd.server_address[1]}',
                   'Host': f'127.0.0.1:{self.httpd.server_address[1]}'}
        payload = None
        if body is not None:
            payload = json.dumps(body)
            headers['Content-Type'] = 'application/json'
        try:
            connection.request(method, path, payload, headers)
            response = connection.getresponse()
            raw = response.read()
            return response.status, (json.loads(raw) if raw else None)
        finally:
            connection.close()

    def row(self, project_id=None):
        status, envelope = self.call('GET', '/api/projects')
        self.assertEqual(200, status, envelope)
        self.assertEqual(PROJECT_LIST_VERSION, envelope['schemaVersion'])
        wanted = project_id or self.project_id
        return next(item for item in envelope['projects'] if item['id'] == wanted)

    def compose(self, title):
        brief = self.call('POST', f'/api/projects/{self.project_id}/briefs', {
            'title': title, 'goals': ['restrained'], 'constraints': 'single colour',
            'reference_asset_ids': [], 'idempotency_key': 'brief-' + title})[1]['brief']['brief_id']
        direction = self.call('POST', f'/api/projects/{self.project_id}/directions', {
            'brief_id': brief, 'title': title + ' direction', 'style_notes': ['measured'],
            'color_mood': 'warm', 'typography_mood': 'sans',
            'idempotency_key': 'direction-' + title})[1]['direction']['direction_id']
        status, result = self.call('POST', f'/api/projects/{self.project_id}/prompts',
                                   {'brief_id': brief, 'direction_id': direction,
                                    'target': 'image-generation'})
        self.assertEqual(201, status, result)
        return brief

    def test_unopened_surfaces_are_null_and_named_never_zero(self):
        item = self.row()
        # The base asset table is created with the project, so this zero is a real measurement.
        self.assertEqual(0, item['objects']['assets'])
        self.assertNotIn('assets', item['absentSurfaces'])
        for surface in UNOPENED:
            self.assertIsNone(item['objects'][surface], f'{surface} must not report 0')
            self.assertIn(surface, item['absentSurfaces'])
        self.assertIsNone(item['last_activity_at'], 'nothing recorded a timestamp yet')
        self.assertIsNone(item['waiting']['promptResultsUnsigned'])
        self.assertIsNone(item['waiting']['knowledgeCandidatesPendingReview'])

    def test_opening_a_surface_turns_null_into_a_count_for_every_project_in_this_checkout(self):
        self.compose('poster')
        before = self.row()
        self.assertEqual(1, before['objects']['promptResults'])
        self.assertNotIn('promptResults', before['absentSurfaces'])
        self.assertIsNotNone(before['last_activity_at'], 'a stored result carries a timestamp')
        self.assertEqual({'total': 1, 'unreviewed': 1, 'accepted': 0, 'declined': 0,
                          'not_current': 0},
                         {'total': before['objects']['promptResults'],
                          'unreviewed': before['waiting']['promptResultsUnsigned'],
                          'accepted': 0, 'declined': 0,
                          'not_current': before['waiting']['promptResultsNotCurrent']})

    def test_pending_numbers_agree_with_the_read_back_that_owns_the_verdict(self):
        self.compose('poster')
        # Open the candidate store first: until a table exists the roll-up is required to report
        # null for it, and that null is not a disagreement with a counter that read 0.
        review = KnowledgeReview(self.service).list(self.project_id)
        readback = PromptResults(self.service).readback(self.project_id)
        item = self.row()
        states = [result['review_state'] for result in readback['results']]
        self.assertEqual(states.count('UNREVIEWED'), item['waiting']['promptResultsUnsigned'])
        self.assertEqual(states.count('NOT_CURRENT'), item['waiting']['promptResultsNotCurrent'])
        self.assertEqual(review['pending_review_count'],
                         item['waiting']['knowledgeCandidatesPendingReview'])
        self.assertEqual(review['export_ready_count'],
                         item['waiting']['knowledgeCandidatesExportReady'])

    def test_a_signature_that_quotes_other_bytes_is_not_current_for_both_surfaces(self):
        """The drift plant: one stale review row, two readers, one answer.

        ``prompt_result_review`` is append-only, so the only realistic way to get here is a review
        recorded against bytes the row no longer holds. Both readers must refuse to count it as
        accepted and refuse to call it a first decision.
        """
        self.compose('poster')
        with closing(PromptResults(self.service)._connect()) as conn:
            stored = conn.execute('SELECT result_id FROM prompt_result WHERE project_id=?',
                                  (self.project_id,)).fetchone()
            stale = 'sha256:' + '1' * 64
            conn.execute(
                'INSERT INTO prompt_result_review (project_id, review_revision, result_id,'
                ' content_sha256, decision, reviewer, reviewer_kind, reviewed_at, note,'
                ' document_json) VALUES (?, 2, ?, ?, ?, ?, ?, ?, ?, ?)',
                (self.project_id, stored['result_id'], stale, 'ACCEPTED', 'Drift Tester', 'human',
                 '2026-10-22T12:00:00+00:00', 'planted stale citation',
                 json.dumps({'schemaVersion': 'design-lab/prompt-result-review/v1',
                             'project_id': self.project_id, 'review_revision': 2,
                             'result_id': stored['result_id'],
                             'decision': 'ACCEPTED', 'reviewer': 'Drift Tester',
                             'reviewer_kind': 'human',
                             'reviewed_at': '2026-10-22T12:00:00+00:00',
                             'content_sha256': stale, 'note': 'planted stale citation',
                             'claims_not_made': ['this review judges the quoted bytes only']})))
            conn.commit()
        item = self.row()
        readback = PromptResults(self.service).readback(self.project_id)
        self.assertEqual(['NOT_CURRENT'], [result['review_state'] for result in readback['results']])
        self.assertEqual(1, item['waiting']['promptResultsNotCurrent'])
        self.assertEqual(0, item['waiting']['promptResultsUnsigned'],
                         'a stale signature is a re-check, not a first decision')
        self.assertEqual(0, readback['accepted_count'])

    def test_the_contract_convicts_a_count_for_a_surface_admitted_absent_in_both_directions(self):
        schema = load_schema(REPO / 'design-lab/schemas/project-list-v1.schema.json')
        envelope = ProjectIndex(self.service).list()
        honest = json.loads(json.dumps(envelope))
        honest['projects'][0]['objects']['promptResults'] = 0
        self.assertTrue(schema_errors(schema, honest),
                        'a count for a surface the row admits it never opened must be refused')
        lying = json.loads(json.dumps(envelope))
        # The count is honestly null on this fresh project; dropping the surface's name is what
        # turns "nobody has opened this here" into a sentence the reader cannot check.
        lying['projects'][0]['absentSurfaces'] = [
            name for name in lying['projects'][0]['absentSurfaces'] if name != 'briefs']
        self.assertTrue(schema_errors(schema, lying),
                        'null without naming the surface in absentSurfaces must be refused')
        self.assertEqual([], schema_errors(schema, envelope),
                         'the shipped envelope must satisfy its own contract')

    def test_a_roll_up_that_cannot_meet_its_contract_is_refused_not_served(self):
        """A broken roll-up answers with a named refusal, never with a plausible-looking list."""
        original = ProjectIndex._one
        try:
            def lying(self, conn, present, row):
                item = original(self, conn, present, row)
                # assets really is 0 here, so claiming the surface is absent is the lie.
                item['absentSurfaces'] = sorted(set(item['absentSurfaces']) | {'assets'})
                return item

            ProjectIndex._one = lying
            status, body = self.call('GET', '/api/projects')
            self.assertEqual(500, status, body)
            self.assertEqual('PROJECT_LIST_CONTRACT_VIOLATION', body['error'])
            self.assertIn('project-list/v1', body['detail'])
        finally:
            ProjectIndex._one = original
        self.assertEqual(200, self.call('GET', '/api/projects')[0],
                         'the refusal must not survive the broken build')
        self.assertIsInstance(ProjectIndexError('x'), ValueError)


if __name__ == '__main__':
    unittest.main()
