# SPDX-License-Identifier: MIT
"""The RIGHTS gate over real HTTP: what a page can file, and what it can be told.

rights-decision.schema.json existed for weeks with no table, no route and no reader, so
the UI had nothing honest to show for the gate and an untouched one had no word that could
not be mistaken for "in review". These cases drive a real ``make_server`` on a real socket
against a real project, and every payload compared is a body that server actually wrote.

The two refusals a caller must be able to tell apart are here on purpose: 404 means "this
project is not in this state database", 409 means "a row exists and it contradicts itself
or the id it carries" -- and a client that retries the second case does not fix anything.
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

from design_lab.assurance import rights_ledger                      # noqa: E402
from design_lab.http_service import make_server                      # noqa: E402
from design_lab.rights_review import write_fields                    # noqa: E402
from design_lab.service import ProjectService                         # noqa: E402


def decision(decision_id='rd-http-1', **overrides) -> dict:
    """One complete rights decision, exactly as a human would file it."""
    document = {
        'schemaVersion': 'design-lab/rights-decision/v1',
        'decision_id': decision_id,
        'use_scope': 'commercial-print',
        'decision': 'APPROVED',
        'decided_by': 'dtalex66',
        'decided_at': '2026-10-08T00:00:00Z',
        'territory': 'worldwide',
        'license_ref': 'OFL-1.1',
        'note': 'read the licence of the shipped font revision',
    }
    document.update(overrides)
    return document


class RightsHttpTests(unittest.TestCase):
    def setUp(self):
        os.environ.pop('PROJECT_LOCAL_ROOT', None)
        self.base = Path(tempfile.mkdtemp(dir=REPO / '.project-local' / 'task-runtime'))
        self.project = self.base / 'project'
        self.project.mkdir()
        (self.project / 'AGENTS.md').write_text('# rights fixture project', encoding='utf-8')
        self.service = ProjectService(self.project)
        self.project_id = self.service.create_project('Rights Probe')['id']
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

    def call(self, method, path, body=None, headers=None):
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
        return self.call('GET', f'/api/projects/{project_id or self.project_id}/rights')

    def write(self, document, *, supersedes=None):
        path = f'/api/projects/{self.project_id}/rights'
        if supersedes is not None:
            path += f'?supersedes={supersedes}'
        return self.call('POST', path, document)

    # ------------------------------------------------------------------ the empty gate

    def test_a_project_nobody_filed_for_reads_not_reviewed_and_never_pending(self):
        status, body = self.read()
        self.assertEqual(status, 200)
        self.assertEqual(body['schemaVersion'], 'design-lab/rights-readback/v1')
        self.assertEqual(body['decisions'], [])
        self.assertEqual(body['decision_count'], 0)
        self.assertEqual(body['current_decisions'], {})
        # NOT_REVIEWED is the honest word: PENDING_REVIEW would claim somebody had been
        # asked, and nobody had. The counts next to the word keep the two cases apart.
        self.assertEqual(body['rights_clearance'], 'NOT_REVIEWED')
        self.assertEqual(body['filed_scope_count'], 0)
        self.assertEqual(body['approved_scope_count'], 0)
        self.assertEqual(body['decision_states']['PENDING_REVIEW'], 0)
        self.assertEqual(body['unapproved_scopes'], [])
        self.assertEqual(body['clearance_vocabulary'], ['CLEARED', 'NOT_REVIEWED'])
        self.assertTrue(body['does_not_prove'])

    def test_an_unknown_project_is_404_not_an_empty_read_back(self):
        for method, path in (('GET', f'/api/projects/{"0" * 32}/rights'),
                             ('POST', f'/api/projects/{"0" * 32}/rights')):
            with self.subTest(method=method):
                status, body = self.call(method, path, None if method == 'GET' else decision())
                self.assertEqual(status, 404, body)
                self.assertEqual(body['error'], 'PROJECT_NOT_FOUND')

    # ------------------------------------------------------------------ filing one

    def test_a_human_decision_is_filed_read_back_and_survives_a_restart(self):
        status, stored = self.write(decision())
        self.assertEqual(status, 201, stored)
        self.assertEqual(stored['decision_id'], 'rd-http-1')
        status, body = self.read()
        self.assertEqual(body['decision_count'], 1)
        self.assertEqual(body['rights_clearance'], 'CLEARED')
        self.assertEqual(list(body['current_decisions']), ['commercial-print'])
        # Every decision filed over this boundary is name-checked only: the contract closes
        # its properties and has no actor-kind field, and the read-back says which rows that
        # covers instead of presenting one word for declared and inferred humans alike.
        self.assertEqual(body['name_checked_only'], ['commercial-print'])

        self.tearDown()
        self.httpd = None
        self.serve()
        status, reread = self.read()
        self.assertEqual(status, 200)
        self.assertEqual([row['decision_id'] for row in reread['decisions']], ['rd-http-1'])
        self.assertEqual(reread['rights_clearance'], 'CLEARED')

    def test_one_approved_scope_does_not_clear_a_project_with_two(self):
        """`CLEARED` is a sentence about the project, so partial clearance reads partial."""
        self.assertEqual(self.write(decision(decision_id='rd-http-1'))[0], 201)
        self.assertEqual(self.write(decision(decision_id='rd-http-2',
                                             use_scope='client-delivery',
                                             decision='DENIED',
                                             note='the stock licence bars redistribution'))[0],
                         201)
        _, half = self.read()
        self.assertEqual((half['approved_scope_count'], half['filed_scope_count']), (1, 2))
        self.assertEqual(half['rights_clearance'], 'NOT_REVIEWED',
                         'a signature on one of two live scopes is not the gate cleared')
        self.assertEqual([row['use_scope'] for row in half['unapproved_scopes']],
                         ['client-delivery'])

        # The refusal has to be able to become an approval without editing history: the
        # correction is a new decision that supersedes, and only then does the word move.
        self.assertEqual(self.write(decision(decision_id='rd-http-3',
                                             use_scope='client-delivery'),
                                    supersedes='rd-http-2')[0], 201)
        _, whole = self.read()
        self.assertEqual((whole['approved_scope_count'], whole['filed_scope_count']), (2, 2))
        self.assertEqual(whole['rights_clearance'], 'CLEARED')
        self.assertEqual(whole['decision_count'], 3,
                         'the withdrawn refusal stays readable')

    def test_a_withdrawal_takes_the_project_back_out_of_cleared(self):
        """History is append-only: the correction is a new decision that supersedes."""
        self.assertEqual(self.write(decision())[0], 201)
        _, before = self.read()
        self.assertEqual(before['rights_clearance'], 'CLEARED')
        status, stored = self.write(decision(decision_id='rd-http-2', decision='DENIED',
                                             note='a second reading found a redistribution '
                                                  'clause'),
                                    supersedes='rd-http-1')
        self.assertEqual(status, 201, stored)
        _, after = self.read()
        self.assertEqual(after['rights_clearance'], 'NOT_REVIEWED')
        self.assertEqual(after['current_decisions']['commercial-print']['decision_id'],
                         'rd-http-2')
        self.assertEqual([row['decision_id'] for row in after['decisions']],
                         ['rd-http-1', 'rd-http-2'],
                         'withdrawing an approval must not erase the record it replaces')

    def test_superseding_an_unknown_id_is_a_400_that_names_the_id(self):
        self.assertEqual(self.write(decision())[0], 201)
        status, body = self.write(decision(decision_id='rd-http-2'), supersedes='rd-nope')
        self.assertEqual(status, 400, body)
        self.assertEqual(body['error'], 'RIGHTS_SUPERSEDES_UNKNOWN')
        self.assertIn('rd-nope', body['detail'])

    # ------------------------------------------------------------------ refusals

    def test_an_agent_signature_is_refused_with_the_rule_and_the_name(self):
        """Not a generic 400: the code says which gate rule fired, the detail says who."""
        status, body = self.write(decision(decision_id='rd-codex', decided_by='codex'))
        self.assertEqual(status, 400, body)
        self.assertEqual(body['error'], 'RIGHTS_NOT_HUMAN')
        self.assertIn('codex', body['detail'])
        _, after = self.read()
        self.assertEqual(after['decision_count'], 0, 'a refused signature must leave no record')
        self.assertEqual(after['rights_clearance'], 'NOT_REVIEWED')

    def test_a_decision_word_the_contract_does_not_allow_is_refused(self):
        for word in ('MAYBE', 'CLEARED', 'approve'):
            with self.subTest(word=word):
                status, body = self.write(decision(decision_id=f'rd-{word}', decision=word))
                self.assertEqual(status, 400, body)
                self.assertEqual(body['error'], 'RIGHTS_DECISION_INVALID')
        _, after = self.read()
        self.assertEqual(after['decision_count'], 0)

    def test_a_timestamp_that_is_not_a_timestamp_is_refused(self):
        """The contract's `format: date-time` is not enforced by the installed validator,
        so the store has to be the one that refuses -- or it becomes permanent history."""
        status, body = self.write(decision(decision_id='rd-when', decided_at='last tuesday'))
        self.assertEqual(status, 400, body)
        self.assertEqual(body['error'], 'RIGHTS_TIMESTAMP_INVALID')

    def test_a_resend_that_stated_nothing_for_an_optional_field_is_still_a_replay(self):
        """The null -> absent clean-up happens before the replay comparison.

        Comparing the raw body against the stored (normalized) document would answer a
        resend with 409 "id taken", and the only way a human could then re-file is with a new
        decision_id -- a second signature for one decision.
        """
        document = decision(decision_id='rd-http-null', note=None)
        self.assertEqual(self.write(document)[0], 201)
        _, after_first = self.read()
        self.assertNotIn('note', after_first['current_decisions']['commercial-print'])
        status, replay = self.write(document)
        self.assertEqual(status, 201, replay)
        self.assertEqual(replay['decision_id'], 'rd-http-null')
        _, body = self.read()
        self.assertEqual(body['decision_count'], 1,
                         'a resend is not a second attestation')

    def test_the_route_pins_the_contract_key_set_and_refuses_an_invention(self):
        document = decision(decision_id='rd-extra')
        document['expires_at'] = '2027-01-01T00:00:00Z'
        status, body = self.write(document)
        self.assertEqual(status, 400, body)
        self.assertEqual(body['error'], 'INVALID_PROJECT_FIELDS')
        # The key set the route demands is the contract's own property names, loaded from
        # the schema file rather than restated in the dispatcher.
        self.assertEqual(set(write_fields()), set(rights_ledger.field_names()))
        self.assertEqual(status, 400)

    def test_a_missing_decision_id_is_refused_before_anything_is_stored(self):
        status, body = self.write(decision(decision_id=''))
        self.assertEqual(status, 400, body)
        self.assertEqual(body['error'], 'RIGHTS_DECISION_ID_REQUIRED')

    # ------------------------------------------------------------------ 409 vs 404

    def test_reposting_the_same_submission_is_a_replay_not_a_second_decision(self):
        first = decision()
        self.assertEqual(self.write(first)[0], 201)
        status, replay = self.write(first)
        self.assertEqual(status, 201)
        self.assertEqual(replay['decision_id'], 'rd-http-1')
        _, body = self.read()
        self.assertEqual(body['decision_count'], 1,
                         'a resend after a lost response must not duplicate an attestation')
        self.assertEqual(body['approved_scope_count'], 1)

    def test_reusing_an_id_for_different_content_is_a_conflict_not_a_404(self):
        """404 says "this project is not here"; 409 says "a row is here and it disagrees".
        A client cannot fix the second one by retrying, so the two stay apart."""
        self.assertEqual(self.write(decision())[0], 201)
        status, body = self.write(decision(decision='DENIED',
                                           note='the same id, a different decision'))
        self.assertEqual(status, 409, body)
        self.assertEqual(body['error'], 'RIGHTS_DECISION_ID_TAKEN')
        _, after = self.read()
        self.assertEqual(after['current_decisions']['commercial-print']['decision'], 'APPROVED')

    def test_a_stored_row_that_contradicts_its_own_contract_is_a_409(self):
        """Re-validated on every read: a row the contract refuses is not served as a gate.

        Reached the way tampering would be reached -- past the module, straight at the file,
        with the immutability trigger dropped first. The answer has to be a refusal that
        names the record, not a clearance computed from bytes nobody trusts.
        """
        self.assertEqual(self.write(decision())[0], 201)
        with closing(sqlite3.connect(self.service.database)) as tampered:
            tampered.execute('DROP TRIGGER rights_decision_no_update')
            tampered.execute('UPDATE rights_decision SET document_json ='
                             " replace(document_json, '\"APPROVED\"', '\"MAYBE\"')"
                             " WHERE decision_id='rd-http-1'")
            tampered.commit()
        status, body = self.read()
        self.assertEqual(status, 409, body)
        self.assertEqual(body['error'], 'RIGHTS_STORED_RECORD_INVALID')
        self.assertIn('rd-http-1', body['detail'])
        self.assertNotIn('rights_clearance', body)
        # A fresh filing still succeeds (201): the corrupt row is only ever read on the way
        # back out, and it keeps the read-back refusing for as long as it is present. That
        # is the honest shape of this guard -- it blocks the claim, not the keystrokes.
        status, fresh = self.write(decision(decision_id='rd-http-2',
                                            use_scope='client-delivery'))
        self.assertEqual(status, 201, fresh)
        status, again = self.read()
        self.assertEqual(status, 409, again)
        self.assertEqual(again['error'], 'RIGHTS_STORED_RECORD_INVALID')

    # ------------------------------------------------------------------ the guard

    def test_the_new_routes_sit_behind_the_same_host_and_token_guard(self):
        """The boundary rules are not re-implemented per route; a new one has to be inside them."""
        status, body = self.call('GET', f'/api/projects/{self.project_id}/rights',
                                 headers={'Authorization': 'Bearer wrong'})
        self.assertEqual(status, 401, body)
        self.assertEqual(body['error'], 'UNAUTHORIZED')
        status, body = self.call('GET', f'/api/projects/{self.project_id}/rights',
                                 headers={'Origin': 'http://evil.example'})
        self.assertEqual(status, 403, body)
        self.assertEqual(body['error'], 'ORIGIN_DENIED')
        _, after = self.read()
        self.assertEqual(after['decision_count'], 0)


if __name__ == '__main__':
    unittest.main()
