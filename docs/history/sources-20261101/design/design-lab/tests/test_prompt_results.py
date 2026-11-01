# SPDX-License-Identifier: MIT
"""Prompt results are kept, addressed, and separately accepted by a named human.

The audit closed-loop table said 结果保存与版本 was "缺关键一段": the two prompt routes produced a
complete document and the server kept nothing, so the 18-hop chain proved several routes answered on
one box rather than one artifact travelling anywhere. These cases pin the other half:

* **the stored row is the response's own bytes.** `content_sha256` must equal the `document_sha256`
  the composing route published -- a store that normalised or re-serialised on the way in would be
  keeping a document nobody was shown;
* **an identity is not reusable.** the result id is a digest over the sources, so the same id with
  different bytes is refused as a collision instead of silently becoming a second row;
* **nothing ran.** `model.executed` true cannot be stored at all, because this repository loads no
  model and has no transport;
* **acceptance is a human act with a citation.** the agent refusal names the owner ruling, a review
  of an unstored result is a 404, and the signature quotes the digest it judged;
* **the store refuses its own rewrite.** the append-only triggers are asserted through direct SQL,
  because an immutable record whose immutability lives only in Python is one careless UPDATE away.

Storage rules are checked against a real socket wherever the product has a route for them, because a
process-only test cannot show what the page will actually receive.
"""
from __future__ import annotations

import http.client
import json
import os
import re
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

from design_lab.http_service import make_server                          # noqa: E402
from design_lab.prompt_results import (PromptResultError, PromptResults,  # noqa: E402
                                       connect)
from design_lab.service import ProjectService                            # noqa: E402

TARGET = 'image-generation'


class PromptResultsStoreTests(unittest.TestCase):
    def setUp(self):
        os.environ.pop('PROJECT_LOCAL_ROOT', None)
        self.base = Path(tempfile.mkdtemp(dir=REPO / '.project-local' / 'task-runtime'))
        self.project = self.base / 'project'
        self.project.mkdir()
        (self.project / 'AGENTS.md').write_text('# prompt result fixture', encoding='utf-8')
        self.service = ProjectService(self.project)
        self.project_id = self.service.create_project('Prompt Store')['id']
        self.token = secrets.token_hex(32)
        self.httpd = make_server(self.service, self.token, 0)
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()
        self.brief_id = self._call('POST', f'/api/projects/{self.project_id}/briefs', {
            'title': 'archive poster, print first', 'goals': ['restrained'],
            'constraints': 'must survive single-colour', 'reference_asset_ids': [],
            'idempotency_key': 'brief-1'})[1]['brief']['brief_id']

    def tearDown(self):
        self.httpd.shutdown()
        self.httpd.server_close()
        self.thread.join(timeout=5)

    def _call(self, method, path, body=None):
        headers = {'Authorization': 'Bearer ' + self.token}
        if body is not None:
            headers['Content-Type'] = 'application/json'
        with closing(http.client.HTTPConnection('127.0.0.1', self.httpd.server_port,
                                                timeout=15)) as conn:
            conn.request(method, path, body=None if body is None else json.dumps(body),
                         headers=headers)
            response = conn.getresponse()
            raw = response.read()
            return response.status, (json.loads(raw) if raw else None)

    def _compose(self, brief_id=None):
        status, body = self._call('POST', f'/api/projects/{self.project_id}/prompts', {
            'brief_id': brief_id or self.brief_id, 'direction_id': None, 'target': TARGET})
        self.assertEqual(status, 201, body)
        return body

    # --- the stored bytes are the answered bytes ----------------------------------

    def test_a_composed_prompt_is_kept_and_its_digest_matches_the_response(self):
        answer = self._compose()
        listed = self._call('GET', f'/api/projects/{self.project_id}/prompt-results')[1]
        self.assertEqual(listed['state'], 'UNREVIEWED',
                         'a stored result nobody signed must not read as NONE')
        self.assertEqual(1, listed['result_count'])
        row = listed['results'][0]
        self.assertEqual(answer['document']['composition_id'], row['result_id'])
        self.assertEqual(answer['document_sha256'], row['content_sha256'],
                         'the store re-encoded the document, so the digest a reader was shown and '
                         'the digest on file describe different bytes')
        self.assertEqual(answer['document'], row['document'])
        self.assertTrue(row['columns_match_document'],
                        'the scalar columns drifted from the document they restate')
        self.assertFalse(row['executed'])

    def test_recomposing_the_same_inputs_replays_instead_of_stacking_rows(self):
        first = self._compose()
        again = self._compose()
        self.assertEqual(first['document']['composition_id'],
                         again['document']['composition_id'])
        listed = self._call('GET', f'/api/projects/{self.project_id}/prompt-results')[1]
        self.assertEqual(1, listed['result_count'],
                         'determinism means a repeat is the same document; storing it twice would '
                         'turn every page load into a revision')

    def test_a_changed_brief_grows_a_new_result_rather_than_editing_the_old_one(self):
        first = self._compose()['document']['composition_id']
        revised = self._call('POST',
                             f'/api/projects/{self.project_id}/briefs/{self.brief_id}/revisions',
                             {'title': 'archive poster, print first',
                              'goals': ['restrained', 'no stock shapes'],
                              'constraints': 'must survive single-colour',
                              'reference_asset_ids': [],
                              'idempotency_key': 'brief-2'})
        self.assertEqual(201, revised[0], revised[1])
        second = self._compose(brief_id=revised[1]['brief']['brief_id'])['document']
        self.assertNotEqual(first, second['composition_id'])
        listed = self._call('GET', f'/api/projects/{self.project_id}/prompt-results')[1]
        self.assertEqual(2, listed['result_count'])
        self.assertEqual([1, 2], [row['revision'] for row in listed['results']],
                         'revisions must be the append order, not a shuffled id list')

    # --- the list is bounded, and the bound may not hide anything ------------------

    def _second_result(self):
        revised = self._call('POST',
                             f'/api/projects/{self.project_id}/briefs/{self.brief_id}/revisions',
                             {'title': 'archive poster, print first',
                              'goals': ['restrained', 'no stock shapes'],
                              'constraints': 'must survive single-colour',
                              'reference_asset_ids': [],
                              'idempotency_key': 'brief-page-2'})
        self.assertEqual(201, revised[0], revised[1])
        return self._compose(brief_id=revised[1]['brief']['brief_id'])

    def test_the_answer_names_its_page_and_the_whole_it_belongs_to(self):
        self._compose()
        status, listed = self._call('GET', f'/api/projects/{self.project_id}/prompt-results')
        self.assertEqual(200, status)
        self.assertEqual(100, listed['limit'],
                         'the published default page is the bound; a silent change here would '
                         'move the contract without a word')
        self.assertEqual(0, listed['offset'])
        self.assertEqual(1, listed['returned'])
        self.assertEqual(1, listed['total_readable'])
        self.assertFalse(listed['truncated'])
        self.assertIsNone(listed['next_offset'])
        self.assertEqual(1, listed['result_count'],
                         'result_count is the row count and must not become the page size')

    def test_a_page_cannot_make_a_long_list_look_short(self):
        self._compose()
        self._second_result()
        base = f'/api/projects/{self.project_id}/prompt-results'
        full = self._call('GET', base)[1]
        first = self._call('GET', base + '?limit=1')[1]
        self.assertEqual(2, first['total_readable'],
                         'a first page of two must still say there are two')
        self.assertEqual(1, first['returned'])
        self.assertEqual([1], [row['revision'] for row in first['results']])
        self.assertTrue(first['truncated'])
        self.assertEqual(1, first['next_offset'])
        self.assertEqual(full['state'], first['state'])
        self.assertEqual(full['newest'], first['newest'])
        self.assertEqual(full['reviews'], first['reviews'],
                         'the acceptance history is never paginated: cutting signatures would '
                         'hide decisions, the one thing this readback may not do')
        second = self._call('GET', base + '?limit=1&offset=1')[1]
        self.assertEqual([2], [row['revision'] for row in second['results']])
        self.assertFalse(second['truncated'])
        self.assertIsNone(second['next_offset'],
                         'the last page claiming a next one exists would send a reader nowhere')

    def test_a_malformed_or_out_of_range_bound_refuses_by_name_not_by_404(self):
        base = f'/api/projects/{self.project_id}/prompt-results'
        for query, code in (('?limit=0', 'PROMPT_RESULT_LIMIT_INVALID'),
                            ('?limit=201', 'PROMPT_RESULT_LIMIT_INVALID'),
                            ('?limit=ten', 'PROMPT_RESULT_FILTER_MALFORMED'),
                            ('?offset=-1', 'PROMPT_RESULT_OFFSET_INVALID')):
            status, body = self._call('GET', base + query)
            self.assertEqual(400, status, f'{query} answered {status}: {body}')
            self.assertEqual(code, body.get('error'),
                             f'{query} answered {body.get("error")!r} instead of naming the '
                             'bound it refuses -- an unnamed 400 is how a parameter becomes a mystery')


    # --- refusals that keep the record honest -------------------------------------

    def test_a_document_claiming_inference_cannot_be_stored(self):
        document = self._compose()['document']
        document['model']['executed'] = True
        with self.assertRaises(PromptResultError) as caught:
            PromptResults(self.service).store(self.project_id, document)
        self.assertEqual(400, caught.exception.status)
        self.assertEqual('PROMPT_RESULT_EXECUTED_ASSERTED', caught.exception.code)

    def test_a_composition_without_a_named_source_is_refused(self):
        document = self._compose()['document']
        document['observed'] = [entry for entry in document['observed']
                                if 'brief_id' not in entry]
        with self.assertRaises(PromptResultError) as caught:
            PromptResults(self.service).store(self.project_id, document)
        self.assertEqual('PROMPT_RESULT_SOURCE_UNNAMED', caught.exception.code,
                         'a prompt with no citable source is exactly what the audit called '
                         'unreusable, so it may not be filed as if it were one')

    def test_the_same_result_id_with_different_bytes_is_a_collision_not_a_second_row(self):
        document = self._compose()['document']
        results = PromptResults(self.service)
        results.store(self.project_id, document)
        tampered = json.loads(json.dumps(document))
        tampered['prompt_text'] = document['prompt_text'] + '\nextra sentence nobody filed'
        with self.assertRaises(PromptResultError) as caught:
            results.store(self.project_id, tampered)
        self.assertEqual(409, caught.exception.status)
        self.assertEqual('PROMPT_RESULT_ID_COLLISION', caught.exception.code)

    def test_an_unknown_document_version_is_not_stored(self):
        with self.assertRaises(PromptResultError) as caught:
            PromptResults(self.service).store(self.project_id, {'schemaVersion': 'x/y/v9'})
        self.assertEqual('PROMPT_RESULT_UNKNOWN_VERSION', caught.exception.code)

    # --- acceptance ---------------------------------------------------------------

    def test_an_agent_cannot_accept_a_prompt_result(self):
        result_id = self._compose()['document']['composition_id']
        status, body = self._call(
            'POST', f'/api/projects/{self.project_id}/prompt-results/{result_id}/review',
            {'decision': 'ACCEPTED', 'reviewer': 'qoder-agent', 'reviewer_kind': 'agent',
             'reviewed_at': '2026-10-22T00:00:00Z', 'note': None})
        self.assertEqual(400, status)
        self.assertEqual('PROMPT_REVIEW_HUMAN_REQUIRED', body['error'])
        self.assertIn('2026-10-21', body['detail'],
                      'the refusal must name the ruling it enforces, not just say no')

    def test_a_human_acceptance_lands_and_is_read_back_as_accepted(self):
        result_id = self._compose()['document']['composition_id']
        status, body = self._call(
            'POST', f'/api/projects/{self.project_id}/prompt-results/{result_id}/review',
            {'decision': 'ACCEPTED', 'reviewer': 'dtalex66', 'reviewer_kind': 'human',
             'reviewed_at': '2026-10-22T00:00:00Z', 'note': 'read every assembled field'})
        self.assertEqual(201, status, body)
        listed = self._call('GET', f'/api/projects/{self.project_id}/prompt-results')[1]
        self.assertEqual('ACCEPTED', listed['state'])
        self.assertEqual(1, listed['accepted_count'])
        row = listed['results'][0]
        self.assertEqual('ACCEPTED', row['review_state'])
        self.assertEqual(row['content_sha256'], row['review']['content_sha256'],
                         'the signature does not quote the bytes it claims to have judged')
        self.assertEqual('human', row['review']['reviewer_kind'])

    def test_reviewing_a_result_that_was_never_stored_is_a_404(self):
        status, body = self._call(
            'POST', f'/api/projects/{self.project_id}/prompt-results/prompt-{"0" * 32}/review',
            {'decision': 'ACCEPTED', 'reviewer': 'dtalex66', 'reviewer_kind': 'human',
             'reviewed_at': '2026-10-22T00:00:00Z', 'note': None})
        self.assertEqual(404, status)
        self.assertEqual('PROMPT_RESULT_NOT_STORED', body['error'])

    def test_a_review_with_a_missing_or_blank_reviewer_is_refused_by_name(self):
        result_id = self._compose()['document']['composition_id']
        for reviewer, code in ((None, 'REVIEWER_REQUIRED'), ('   ', 'REVIEWER_REQUIRED'),
                               ('dtalex66', 'INVALID_REVIEWED_AT')):
            status, body = self._call(
                'POST', f'/api/projects/{self.project_id}/prompt-results/{result_id}/review',
                {'decision': 'ACCEPTED', 'reviewer': reviewer, 'reviewer_kind': 'human',
                 'reviewed_at': 'yesterday' if code == 'INVALID_REVIEWED_AT'
                 else '2026-10-22T00:00:00Z', 'note': None})
            self.assertEqual(400, status, (reviewer, code))
            self.assertEqual(code, body['error'],
                             'a refusal must name the field it rejected, not collapse into one '
                             '"invalid request"')

    def test_an_empty_project_reads_as_none_not_as_unreviewed(self):
        other = self.service.create_project('Never Prompted')['id']
        listed = self._call('GET', f'/api/projects/{other}/prompt-results')[1]
        self.assertEqual('NONE', listed['state'])
        self.assertEqual(0, listed['result_count'])
        self.assertIsNone(listed['newest'])

    # --- the store refuses its own rewrite ---------------------------------------

    def test_the_tables_refuse_update_and_delete_through_direct_sql(self):
        result_id = self._compose()['document']['composition_id']
        self._call('POST', f'/api/projects/{self.project_id}/prompt-results/{result_id}/review',
                   {'decision': 'ACCEPTED', 'reviewer': 'dtalex66', 'reviewer_kind': 'human',
                    'reviewed_at': '2026-10-22T00:00:00Z', 'note': None})
        connection = connect(self.service.paths.database_path(self.service.database),
                             project_root=self.service.paths.project_root)
        try:
            self.assertEqual(1, connection.execute(
                'SELECT COUNT(*) AS n FROM prompt_result_review').fetchone()['n'])
            for statement, params in (('UPDATE prompt_result SET target = ?', ('x',)),
                                      ('DELETE FROM prompt_result', ()),
                                      ('UPDATE prompt_result_review SET decision = ?', ('x',)),
                                      ('DELETE FROM prompt_result_review', ())):
                with self.assertRaises(sqlite3.IntegrityError, msg=statement):
                    connection.execute(statement, params)
        finally:
            connection.close()

    def test_a_review_cannot_name_a_result_from_another_project(self):
        result_id = self._compose()['document']['composition_id']
        other = self.service.create_project('Other')['id']
        with self.assertRaises(PromptResultError) as caught:
            PromptResults(self.service).review(
                other, result_id=result_id, decision='ACCEPTED', reviewer='dtalex66',
                reviewer_kind='human', reviewed_at='2026-10-22T00:00:00Z')
        self.assertEqual('PROMPT_RESULT_NOT_STORED', caught.exception.code,
                         'the composite foreign key is what makes "signed something that is not '
                         'mine" unrepresentable rather than merely disallowed')

    def test_the_readback_never_loses_a_row_because_one_was_unreadable(self):
        self._compose()
        connection = connect(self.service.paths.database_path(self.service.database),
                             project_root=self.service.paths.project_root)
        try:
            # A row whose stored document cannot be parsed must be counted, not dropped quietly:
            # `unreadable_count` is the difference between "two results" and "two rows, one of
            # which this service cannot read".
            connection.execute('DROP TRIGGER prompt_result_no_update')
            connection.execute("UPDATE prompt_result SET document_json = '{not json'")
            connection.commit()
        finally:
            connection.close()
        listed = PromptResults(self.service).readback(self.project_id)
        self.assertEqual(1, listed['unreadable_count'])
        self.assertEqual(1, listed['result_count'])
        self.assertEqual([], listed['results'])
        self.assertEqual('UNREVIEWED', listed['state'],
                         'a row that cannot be parsed still means this service produced something; '
                         'reporting NONE would erase the fact a prompt was made, and reporting it as '
                         'readable would invent its contents. unreadable_count carries the difference')
        self.assertEqual(0, listed['accepted_count'])


class PromptResultsContractTests(unittest.TestCase):
    def test_the_module_writes_the_versions_the_contracts_const(self):
        source = (REPO / 'src/design_lab/prompt_results.py').read_text(encoding='utf-8')
        for version in ('design-lab/prompt-result/v1', 'design-lab/prompt-result-readback/v1',
                        'design-lab/prompt-result-review/v1'):
            self.assertIn(f"'{version}'", source, version)
            for name in ('prompt-result-v1', 'prompt-result-readback-v1',
                         'prompt-result-review-v1'):
                path = REPO / 'design-lab/schemas' / f'{name}.schema.json'
                if not path.is_file():
                    continue
                document = json.loads(path.read_text(encoding='utf-8'))
                if document['properties']['schemaVersion'].get('const') == version:
                    break
            else:
                self.fail(f'{version} is not const in any shipped prompt-result contract')

    def test_the_review_contract_pins_the_human_only_rule_where_the_table_repeats_it(self):
        schema = json.loads((REPO / 'design-lab/schemas'
                             / 'prompt-result-review-v1.schema.json').read_text(encoding='utf-8'))
        self.assertEqual({'const': 'human'}, schema['properties']['reviewer_kind'])
        sql = (REPO / 'design-lab/schemas/state'
               / 'design-lab-state-prompt-results-v1.sql').read_text(encoding='utf-8')
        self.assertIn("reviewer_kind TEXT NOT NULL CHECK (reviewer_kind = 'human')", sql)

    def test_the_state_resource_name_is_registered_and_applied_by_the_module(self):
        from design_lab.runtime import state_resources
        self.assertIn('design-lab-state-prompt-results-v1.sql', state_resources._NAMES)
        source = (REPO / 'src/design_lab/prompt_results.py').read_text(encoding='utf-8')
        self.assertIn("state_schema('design-lab-state-prompt-results-v1.sql')", source)


if __name__ == '__main__':
    unittest.main(verbosity=2)
