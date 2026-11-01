# SPDX-License-Identifier: MIT
"""Research findings over real HTTP: what a page can file, and what it can be told.

``design-lab/schemas/research-finding.schema.json`` had no table, no route and no reader, so
the Workbench panel honestly printed "当前服务没有研究结论的持久化路由" and marked its card
PLANNED. These cases drive a real ``make_server`` on a real socket against a real project, and
every payload compared is a body that server actually wrote.

The two things this boundary has to get right are not the same two things the rights boundary
had to get right, and the difference is asserted here rather than discussed:

* a finding is refused for citing nothing, including when what it cites is a space;
* the read-back publishes **no project-level verdict word**. Rights has ``rights_clearance``
  because the rights gate exists; research has a count, because no gate is cleared by having
  written findings down. So the empty case is a 200 with zeros and a null verdict, and the
  words the gate vocabulary owns are asserted absent from the body -- a future "RESEARCH_DONE"
  would have to arrive with a state-vocabulary entry and an emitter, not be invented here.

404 means "this project is not in this state database"; 409 means "a row exists and it
contradicts itself or the id it carries"; a retry of the second one fixes nothing.
"""
from __future__ import annotations

import http.client
import json
import os
import secrets
import sqlite3
import tempfile
import threading
import unittest
from contextlib import closing
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
import sys
sys.path.insert(0, str(REPO / 'src'))

from design_lab.assurance import research_store                    # noqa: E402
from design_lab.http_service import make_server                     # noqa: E402
from design_lab.research_review import write_fields                 # noqa: E402
from design_lab.service import ProjectService                       # noqa: E402


def finding(finding_id='rf-http-1', **overrides) -> dict:
    """One complete finding, exactly as a designer who had looked at something would file it."""
    document = {
        'finding_id': finding_id,
        'claim': 'the comparison table sits below the price, so shoppers decide on one number',
        'sourceRefs': ['interview-07', 'bench-competitor-2026-05'],
        'confidence': 'medium',
        'notDesignRule': True,
    }
    document.update(overrides)
    return document


class ResearchHttpTests(unittest.TestCase):
    def setUp(self):
        os.environ.pop('PROJECT_LOCAL_ROOT', None)
        self.base = Path(tempfile.mkdtemp(dir=REPO / '.project-local' / 'task-runtime'))
        self.project = self.base / 'project'
        self.project.mkdir()
        (self.project / 'AGENTS.md').write_text('# research fixture project', encoding='utf-8')
        self.service = ProjectService(self.project)
        self.project_id = self.service.create_project('Research Probe')['id']
        self.other_id = self.service.create_project('Other Probe')['id']
        self.token = secrets.token_hex(32)
        self.httpd = None
        self.thread = None

    def tearDown(self):
        if self.httpd is not None:
            self.httpd.shutdown()
            self.httpd.server_close()
            if self.thread is not None:
                self.thread.join(timeout=5)
            self.httpd = None

    def serve(self):
        self.httpd = make_server(self.service, self.token, 0)
        self.port = self.httpd.server_port
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()

    def call(self, method, path, body=None, headers=None, project_id=None):
        if self.httpd is None:
            self.serve()
        sent = {'Authorization': 'Bearer ' + self.token}
        if body is not None:
            sent['Content-Type'] = 'application/json'
        sent.update(headers or {})
        with closing(http.client.HTTPConnection('127.0.0.1', self.port, timeout=15)) as conn:
            conn.request(method, path, body=None if body is None else json.dumps(body),
                         headers=sent)
            response = conn.getresponse()
            return response.status, json.loads(response.read() or b'null')

    def read(self, project_id=None):
        return self.call('GET', f'/api/projects/{project_id or self.project_id}/research')

    def write(self, document, *, supersedes=None, project_id=None):
        path = f'/api/projects/{project_id or self.project_id}/research'
        if supersedes is not None:
            path += f'?supersedes={supersedes}'
        return self.call('POST', path, document)

    # ------------------------------------------------------------------ the empty surface

    def test_a_project_with_no_findings_reads_zero_and_produces_no_verdict(self):
        status, body = self.read()
        self.assertEqual(status, 200)
        self.assertEqual(body['schemaVersion'], 'design-lab/research-readback/v1')
        self.assertEqual(body['findings'], [])
        self.assertEqual(body['finding_count'], 0)
        self.assertEqual(body['current_findings'], {})
        self.assertEqual(body['sourced_finding_count'], 0)
        self.assertEqual(body['unsourced_finding_count'], 0)
        self.assertEqual(body['unattributed_findings'], [])
        # There is no word for "research finished", and none is emitted.
        self.assertIsNone(body['research_verdict'])
        self.assertTrue(body['research_verdict_note'])
        self.assertFalse(body['proves_design_quality'])
        self.assertFalse(body['is_knowledge_export'])
        self.assertEqual(body['source_ref_field'], 'sourceRefs')
        self.assertTrue(body['does_not_prove'])
        for word in ('CLEARED', 'NOT_REVIEWED', 'PENDING_REVIEW', 'ACCEPTED', 'NOT_ACCEPTED',
                     'RESEARCH_COMPLETE', 'research_clearance'):
            self.assertNotIn(word, json.dumps(body),
                             f'the read-back emits {word!r}: research has no gate to clear, '
                             'and a page handed one would show it')

    def test_an_unknown_project_is_404_not_an_empty_read_back(self):
        for method in ('GET', 'POST'):
            with self.subTest(method=method):
                status, body = self.call(method, f'/api/projects/{"0" * 32}/research',
                                         None if method == 'GET' else finding())
                self.assertEqual(status, 404, body)
                self.assertEqual(body['error'], 'PROJECT_NOT_FOUND')

    # ------------------------------------------------------------------ filing one

    def test_a_finding_is_filed_read_back_and_survives_a_restart(self):
        status, stored = self.write(finding())
        self.assertEqual(status, 201, stored)
        self.assertEqual(stored['finding_id'], 'rf-http-1')
        status, body = self.read()
        self.assertEqual(body['finding_count'], 1)
        self.assertEqual(body['sourced_finding_count'], 1)
        self.assertEqual(body['source_ref_total'], 2)
        self.assertEqual(body['confidence_counts']['medium'], 1)
        self.assertEqual(list(body['current_findings']), ['rf-http-1'])

        self.tearDown()
        self.httpd = None
        self.serve()
        status, reread = self.read()
        self.assertEqual(status, 200)
        self.assertEqual([row['finding_id'] for row in reread['findings']], ['rf-http-1'])
        self.assertEqual(reread['sourced_finding_count'], 1)

    def test_a_finding_filed_over_http_has_no_author_and_says_so(self):
        """The contract closes its properties and declares no actor, so nothing can arrive.

        The rights façade can at least name-check a signature; here there is no name to
        check, and the honest answer is an empty attribution reported as empty -- not a
        reader shown a finding and left to assume a person wrote it.
        """
        self.assertEqual(self.write(finding())[0], 201)
        _, body = self.read()
        self.assertEqual(body['unattributed_findings'], ['rf-http-1'])
        self.assertEqual(body['actor_kinds'], {'rf-http-1': None})
        self.assertEqual(body['undeclared_disclaimer'], [])

    def test_superseding_moves_the_current_set_and_keeps_history_readable(self):
        self.assertEqual(self.write(finding())[0], 201)
        status, replaced = self.write(finding(finding_id='rf-http-2',
                                              claim='a second session reversed the first',
                                              sourceRefs=['interview-09']),
                                      supersedes='rf-http-1')
        self.assertEqual(status, 201, replaced)
        _, body = self.read()
        self.assertEqual((body['finding_count'], body['current_finding_count'],
                          body['superseded_finding_count']), (2, 1, 1))
        self.assertEqual(list(body['current_findings']), ['rf-http-2'])
        self.assertEqual([row['finding_id'] for row in body['findings']],
                         ['rf-http-1', 'rf-http-2'])

    def test_superseding_an_unknown_id_is_a_400_that_names_the_id(self):
        self.assertEqual(self.write(finding())[0], 201)
        status, body = self.write(finding(finding_id='rf-http-2'), supersedes='rf-nope')
        self.assertEqual(status, 400, body)
        self.assertEqual(body['error'], 'RESEARCH_SUPERSEDES_UNKNOWN')
        self.assertIn('rf-nope', body['detail'])

    def test_superseding_another_project_s_finding_is_refused_by_name(self):
        """A chain that leaves the project would leave that project with a current finding its
        own read-back never filed."""
        self.assertEqual(self.write(finding(finding_id='rf-other'),
                                    project_id=self.other_id)[0], 201)
        self.assertEqual(self.write(finding(finding_id='rf-mine'))[0], 201)
        status, body = self.write(finding(finding_id='rf-http-3'), supersedes='rf-other')
        self.assertEqual(status, 400, body)
        self.assertEqual(body['error'], 'RESEARCH_SUPERSEDES_FOREIGN_PROJECT')
        self.assertIn(self.other_id, body['detail'])
        _, mine = self.read()
        self.assertEqual(mine['finding_count'], 1, 'the refused link left no row')
        _, theirs = self.read(project_id=self.other_id)
        self.assertEqual(list(theirs['current_findings']), ['rf-other'],
                         'another project read-back may not be touched by this filing')

    # ------------------------------------------------------------------ refusals

    def test_a_finding_that_cites_nothing_is_refused_and_leaves_no_row(self):
        """The spirit of `sourceRefs`, not its arithmetic: [] and [" "] both fail."""
        for label, refs in (('empty', []), ('whitespace', ['   ']), ('blank', ['']),
                            ('half-blank', ['interview-07', ' ']),
                            ('duplicated', ['bench-x', 'bench-x'])):
            with self.subTest(sources=label):
                status, body = self.write(finding(finding_id=f'rf-{label}', sourceRefs=refs))
                self.assertEqual(status, 400, body)
                self.assertIn(body['error'], ('RESEARCH_SOURCE_REFS_EMPTY',
                                              'RESEARCH_SOURCE_REF_INVALID'))
        _, after = self.read()
        self.assertEqual(after['finding_count'], 0, 'a refused filing must leave no record')

    def test_a_claim_that_says_nothing_is_refused_though_minLength_passes_it(self):
        status, body = self.write(finding(finding_id='rf-void', claim='   '))
        self.assertEqual(status, 400, body)
        self.assertEqual(body['error'], 'RESEARCH_FINDING_INVALID')

    def test_a_confidence_word_the_contract_does_not_allow_is_refused(self):
        for word in ('certain', 'MEDIUM', 'definitely'):
            with self.subTest(word=word):
                status, body = self.write(finding(finding_id=f'rf-{word}', confidence=word))
                self.assertEqual(status, 400, body)
                self.assertEqual(body['error'], 'RESEARCH_FINDING_INVALID')
        _, after = self.read()
        self.assertEqual(after['finding_count'], 0)

    def test_a_finding_that_claims_to_be_a_design_rule_is_refused(self):
        """`notDesignRule` is `const: true`: 研究结论不能直接冒充设计规则."""
        status, body = self.write(finding(finding_id='rf-rule', notDesignRule=False))
        self.assertEqual(status, 400, body)
        self.assertEqual(body['error'], 'RESEARCH_FINDING_INVALID')

    def test_the_route_pins_the_contract_key_set_and_refuses_an_invention(self):
        """Including the `schemaVersion` every other assurance route accepts."""
        document = finding(finding_id='rf-extra')
        document['schemaVersion'] = 'design-lab/research-finding/v1'
        status, body = self.write(document)
        self.assertEqual(status, 400, body)
        self.assertEqual(body['error'], 'INVALID_PROJECT_FIELDS')
        self.assertEqual(set(write_fields()), set(research_store.field_names()))
        self.assertNotIn('schemaVersion', write_fields())
        self.assertEqual(set(write_fields()),
                         {'finding_id', 'claim', 'sourceRefs', 'confidence', 'notDesignRule'})

    def test_a_missing_finding_id_is_refused_before_anything_is_stored(self):
        status, body = self.write(finding(finding_id=''))
        self.assertEqual(status, 400, body)
        self.assertEqual(body['error'], 'RESEARCH_FINDING_ID_REQUIRED')

    def test_a_resend_that_stated_nothing_for_an_optional_field_is_still_a_replay(self):
        """The null -> absent clean-up happens before the replay comparison.

        Comparing the raw body against the stored (normalised) document would answer a resend
        with 409 "id taken", and the only way a caller could then re-file is with a new
        finding_id -- a second finding for one claim.
        """
        document = finding(finding_id='rf-http-null', confidence=None, notDesignRule=None)
        self.assertEqual(self.write(document)[0], 201)
        _, after_first = self.read()
        self.assertNotIn('confidence', after_first['current_findings']['rf-http-null'])
        status, replay = self.write(document)
        self.assertEqual(status, 201, replay)
        self.assertEqual(replay['finding_id'], 'rf-http-null')
        _, body = self.read()
        self.assertEqual(body['finding_count'], 1, 'a resend is not a second finding')

    # ------------------------------------------------------------------ 409 vs 404

    def test_reposting_the_same_submission_is_a_replay_not_a_second_finding(self):
        first = finding()
        self.assertEqual(self.write(first)[0], 201)
        status, replay = self.write(first)
        self.assertEqual(status, 201)
        self.assertEqual(replay['finding_id'], 'rf-http-1')
        _, body = self.read()
        self.assertEqual(body['finding_count'], 1,
                         'a resend after a lost response must not double the count')
        self.assertEqual(body['source_ref_total'], 2)

    def test_reusing_an_id_for_different_content_is_a_conflict_not_a_404(self):
        """404 says "this project is not here"; 409 says "a row is here and it disagrees"."""
        self.assertEqual(self.write(finding())[0], 201)
        status, body = self.write(finding(claim='the same id, a different claim'))
        self.assertEqual(status, 409, body)
        self.assertEqual(body['error'], 'RESEARCH_FINDING_ID_TAKEN')
        _, after = self.read()
        self.assertEqual(after['current_findings']['rf-http-1']['claim'],
                         'the comparison table sits below the price, so shoppers decide on '
                         'one number')

    def test_a_stored_row_that_contradicts_its_own_contract_is_a_409(self):
        """Re-validated on every read: a row the contract refuses is not served as a panel.

        Reached the way tampering would be reached -- past the module, straight at the file,
        with the immutability trigger dropped first.
        """
        self.assertEqual(self.write(finding())[0], 201)
        with closing(sqlite3.connect(self.service.database)) as tampered:
            tampered.execute('DROP TRIGGER research_finding_no_update')
            changed = tampered.execute(
                'UPDATE research_finding SET document_json ='
                ' replace(document_json,\'"medium"\',\'"certain"\')'
                " WHERE finding_id='rf-http-1'")
            tampered.commit()
            # The tamper has to have actually happened, or this case would be watching a
            # replace() that matched nothing report a perfectly good row.
            self.assertEqual(changed.rowcount, 1)
            self.assertEqual(tampered.execute('SELECT instr(document_json,\'"certain"\') > 0'
                                              " FROM research_finding"
                                              " WHERE finding_id='rf-http-1'").fetchone()[0], 1)
        status, body = self.read()
        self.assertEqual(status, 409, body)
        self.assertEqual(body['error'], 'RESEARCH_STORED_RECORD_INVALID')
        self.assertIn('rf-http-1', body['detail'])
        self.assertNotIn('finding_count', body)
        # A fresh filing still succeeds (201): the corrupt row is read back out on every read
        # and keeps the read-back refusing for as long as it is present. That is the honest
        # shape of this guard -- it blocks the claim, not the keystrokes.
        status, fresh = self.write(finding(finding_id='rf-http-2', claim='another finding',
                                           sourceRefs=['interview-11']))
        self.assertEqual(status, 201, fresh)
        status, again = self.read()
        self.assertEqual(status, 409, again)
        self.assertEqual(again['error'], 'RESEARCH_STORED_RECORD_INVALID')

    def test_a_stored_row_whose_count_disagrees_with_its_bytes_is_a_409(self):
        """The published numbers come from the bytes; the column is a projection of them."""
        self.assertEqual(self.write(finding())[0], 201)
        with closing(sqlite3.connect(self.service.database)) as tampered:
            tampered.execute('DROP TRIGGER research_finding_no_update')
            tampered.execute("UPDATE research_finding SET source_ref_count = 7"
                             " WHERE finding_id='rf-http-1'")
            tampered.commit()
        status, body = self.read()
        self.assertEqual(status, 409, body)
        self.assertEqual(body['error'], 'RESEARCH_STORED_RECORD_INVALID')
        self.assertIn('source_ref_count', body['detail'])

    # ------------------------------------------------------------------ the guard

    def test_the_new_routes_sit_behind_the_same_host_and_token_guard(self):
        """The boundary rules are not re-implemented per route; a new one has to be inside them."""
        status, body = self.call('GET', f'/api/projects/{self.project_id}/research',
                                 headers={'Authorization': 'Bearer wrong'})
        self.assertEqual(status, 401, body)
        self.assertEqual(body['error'], 'UNAUTHORIZED')
        status, body = self.call('GET', f'/api/projects/{self.project_id}/research',
                                 headers={'Origin': 'http://evil.example'})
        self.assertEqual(status, 403, body)
        self.assertEqual(body['error'], 'ORIGIN_DENIED')
        _, after = self.read()
        self.assertEqual(after['finding_count'], 0)


if __name__ == '__main__':
    unittest.main()
