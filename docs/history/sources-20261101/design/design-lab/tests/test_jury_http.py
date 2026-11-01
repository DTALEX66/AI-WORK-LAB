# SPDX-License-Identifier: MIT
"""The jury endpoints over real HTTP, and what a restart still shows.

Human Jury was a validated contract with no route and no table for weeks: the UI
could not display a judgement and nothing survived a restart. These drive a real
server on a real socket against a real published version.
"""
from __future__ import annotations

import hashlib
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

from design_lab.assurance import jury_store                       # noqa: E402
from design_lab.http_service import make_server                   # noqa: E402
from design_lab.runtime import asset_store as assets               # noqa: E402
from design_lab.service import ProjectService                      # noqa: E402

CRITERIA = [{'criterion_id': 'composition', 'weight': 0.4, 'score': 4.2, 'note': 'ok'},
            {'criterion_id': 'typography', 'weight': 0.3, 'score': 3.8, 'note': 'ok'},
            {'criterion_id': 'brand-fit', 'weight': 0.3, 'score': 4.0, 'note': 'ok'}]


class JuryHttpTests(unittest.TestCase):
    def setUp(self):
        os.environ.pop('PROJECT_LOCAL_ROOT', None)
        self.base = Path(tempfile.mkdtemp(dir=REPO / '.project-local' / 'task-runtime'))
        self.project = self.base / 'project'
        self.project.mkdir()
        (self.project / 'AGENTS.md').write_text('# jury fixture project', encoding='utf-8')
        self.service = ProjectService(self.project)
        self.project_id = self.service.create_project('Jury Probe')['id']
        self.version_id, self.digest = self._publish(b'artwork under review')
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

    def _publish(self, payload: bytes, *, project_id=None, asset_id='a1'):
        project_id = project_id or self.project_id
        source = self.base / f'incoming-{asset_id}-{len(payload)}.psd'
        source.write_bytes(payload)
        digest = 'sha256:' + hashlib.sha256(payload).hexdigest()
        store = self.service.paths.category_dir('projects', project_id, 'assets')
        database = self.service.database
        with closing(assets.connect(database, project_root=self.service.paths.project_root)) as conn:
            # A second call for the same asset_id is a re-publication, which is what
            # supersedes a judged version with new bytes; the asset row already exists.
            if conn.execute('SELECT 1 FROM asset WHERE asset_id = ? AND project_id = ?',
                            (asset_id, project_id)).fetchone() is None:
                conn.execute('INSERT INTO asset VALUES (?, ?, "psd", ?)',
                             (asset_id, project_id, '2026-10-08T00:00:00Z'))
            conn.commit()
            resource = f'asset:{asset_id}'
            self.assertTrue(assets.acquire_writer(conn, resource, 'attempt-http'))
            generation = assets.writer_token(conn, resource, 'attempt-http')
            version_id = assets.publish_version(conn, asset_id, source, store_root=store,
                                               artifact_name='native.psd',
                                               expected_sha256=digest,
                                               holder_attempt_id='attempt-http',
                                               generation=generation)
            assets.release_writer(conn, resource, 'attempt-http', generation=generation)
        return version_id, digest

    def serve(self):
        self.httpd = make_server(self.service, self.token, 0)
        self.port = self.httpd.server_port
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()

    def call(self, method, path, body=None):
        if self.httpd is None:
            self.serve()
        headers = {'Authorization': 'Bearer ' + self.token}
        if body is not None:
            headers['Content-Type'] = 'application/json'
        with closing(http.client.HTTPConnection('127.0.0.1', self.port, timeout=15)) as conn:
            conn.request(method, path, body=None if body is None else json.dumps(body),
                         headers=headers)
            response = conn.getresponse()
            return response.status, json.loads(response.read() or b'null')

    def _verdict(self, **overrides):
        base = {
            'schemaVersion': 'design-lab/assurance-jury-record/v2',
            'kind': 'JURY_VERDICT',
            'jury_record_id': 'jury-http-1',
            'subject_ref': f'{jury_store.SUBJECT_PREFIX}{self.version_id}',
            'artifact_sha256': self.digest,
            'juror': {'juror_id': 'dtalex66', 'kind': 'HUMAN', 'members': [],
                      'attestation': 'reviewed the exported artwork at 100%'},
            'criteria': CRITERIA,
            'verdict': 'APPROVE',
            'decided_at': '2026-10-08T00:00:00Z',
            'supersedes': None,
            'evidence_refs': [],
        }
        base.update(overrides)
        return base

    def test_empty_review_reports_nothing_accepted_rather_than_zero_of_something(self):
        status, body = self.call('GET', f'/api/projects/{self.project_id}/jury')
        self.assertEqual(status, 200)
        self.assertEqual(body['records'], [])
        self.assertEqual(body['verdict_count'], 0)
        self.assertEqual(body['human_acceptance'], 'NOT_ACCEPTED')
        self.assertEqual(body['current_verdicts'], {})
        # The counts are published, so 'NOT_ACCEPTED' never has to be taken on faith:
        # 0 of 1 is a project nobody has accepted, and it is distinguishable from
        # 0 of 0, which is a project with nothing published yet.
        self.assertEqual(body['accepted_versions'], 0)
        self.assertEqual(body['reviewable_active_versions'], 1)
        # The reviewer is shown what may be judged, with its digest, so a verdict
        # never depends on a hand-typed hash.
        self.assertEqual([row['subject_ref'] for row in body['reviewable_versions']],
                         [f'{jury_store.SUBJECT_PREFIX}{self.version_id}'])
        self.assertEqual(body['reviewable_versions'][0]['artifact_sha256'], self.digest)

    def test_a_superseded_version_leaves_the_reviewable_list(self):
        """Only the currently readable version can be accepted, and the list says so."""
        with closing(sqlite3.connect(self.service.database)) as conn:
            conn.execute('UPDATE asset_version SET state="SUPERSEDED" WHERE version_id=?',
                         (self.version_id,))
            conn.commit()
        _, body = self.call('GET', f'/api/projects/{self.project_id}/jury')
        self.assertEqual(body['reviewable_versions'], [])
        document = self._verdict()
        status, refused = self.call('POST', f'/api/projects/{self.project_id}/jury/verdict',
                                    document)
        self.assertEqual(status, 400)
        self.assertIn('SUPERSEDED', refused['error'])

    def test_a_human_verdict_is_recorded_read_back_and_survives_a_restart(self):
        status, stored = self.call('POST', f'/api/projects/{self.project_id}/jury/verdict',
                                   self._verdict())
        self.assertEqual(status, 201, stored)
        status, body = self.call('GET', f'/api/projects/{self.project_id}/jury')
        self.assertEqual(body['verdict_count'], 1)
        self.assertEqual(body['human_acceptance'], 'ACCEPTED')
        self.assertEqual(list(body['current_verdicts']), [self._verdict()['subject_ref']])

        # Restart proof: a second server process over the same state database.
        self.tearDown()
        self.httpd = None
        self.serve()
        status, reread = self.call('GET', f'/api/projects/{self.project_id}/jury')
        self.assertEqual(status, 200)
        self.assertEqual([row['jury_record_id'] for row in reread['records']], ['jury-http-1'])
        self.assertEqual(reread['human_acceptance'], 'ACCEPTED')

    def test_one_approved_version_does_not_stand_for_a_project_that_has_two(self):
        """`ACCEPTED` is a sentence about the project, so partial acceptance reads partial."""
        second_version, second_digest = self._publish(b'second artwork under review',
                                                      asset_id='a2')
        _, before = self.call('GET', f'/api/projects/{self.project_id}/jury')
        self.assertEqual((before['accepted_versions'], before['reviewable_active_versions']),
                         (0, 2))

        self.assertEqual(self.call('POST', f'/api/projects/{self.project_id}/jury/verdict',
                                   self._verdict())[0], 201)
        _, half = self.call('GET', f'/api/projects/{self.project_id}/jury')
        self.assertEqual((half['accepted_versions'], half['reviewable_active_versions']), (1, 2))
        self.assertEqual(half['human_acceptance'], 'NOT_ACCEPTED',
                         'a signature on one of two live versions is not the project accepted')

        self.assertEqual(
            self.call('POST', f'/api/projects/{self.project_id}/jury/verdict',
                      self._verdict(jury_record_id='jury-http-2',
                                    subject_ref=f'{jury_store.SUBJECT_PREFIX}{second_version}',
                                    artifact_sha256=second_digest))[0], 201)
        _, whole = self.call('GET', f'/api/projects/{self.project_id}/jury')
        self.assertEqual((whole['accepted_versions'], whole['reviewable_active_versions']),
                         (2, 2))
        self.assertEqual(whole['human_acceptance'], 'ACCEPTED')

        # A withdrawal has to be able to take the project back out of ACCEPTED, so the
        # status tracks the current verdicts rather than the mere fact that somebody
        # once signed. (The rejection carries an evidence_ref because a REJECT without
        # one is refused by the contract, and it has to here too.)
        self.assertEqual(
            self.call('POST', f'/api/projects/{self.project_id}/jury/verdict',
                      self._verdict(jury_record_id='jury-http-3', verdict='REJECT',
                                    subject_ref=f'{jury_store.SUBJECT_PREFIX}{second_version}',
                                    artifact_sha256=second_digest,
                                    evidence_refs=['100% crop: the colour band shifts'],
                                    supersedes='jury-http-2',
                                    decided_at='2026-10-08T02:00:00Z'))[0], 201)
        _, withdrawn = self.call('GET', f'/api/projects/{self.project_id}/jury')
        self.assertEqual((withdrawn['accepted_versions'],
                          withdrawn['reviewable_active_versions']), (1, 2))
        self.assertEqual(withdrawn['human_acceptance'], 'NOT_ACCEPTED')

    def test_a_project_with_nothing_published_is_not_accepted_by_default(self):
        """0 of 0 is vacuously 'all accepted' and must never be reported as ACCEPTED."""
        empty_id = self.service.create_project('Nothing Published')['id']
        _, body = self.call('GET', f'/api/projects/{empty_id}/jury')
        self.assertEqual(body['reviewable_versions'], [])
        self.assertEqual(body['reviewable_active_versions'], 0)
        self.assertEqual(body['accepted_versions'], 0)
        self.assertEqual(body['human_acceptance'], 'NOT_ACCEPTED')

    def test_an_approval_of_bytes_that_no_longer_exist_stops_accepting_the_project(self):
        """A signature is bound to a digest, so it cannot outlive the version it signed.

        This is the case that a 'did anybody approve anything' rule got wrong: the
        approval is still on file and still true of the bytes it named, but those
        bytes are no longer what the project would deliver. Reporting ACCEPTED there
        certified a version nobody can read back.
        """
        self.assertEqual(self.call('POST', f'/api/projects/{self.project_id}/jury/verdict',
                                   self._verdict())[0], 201)
        _, before = self.call('GET', f'/api/projects/{self.project_id}/jury')
        self.assertEqual(before['human_acceptance'], 'ACCEPTED')

        newer_version, newer_digest = self._publish(b'revised artwork supersedes the old one')
        _, after = self.call('GET', f'/api/projects/{self.project_id}/jury')
        self.assertEqual([row['version_id'] for row in after['reviewable_versions']],
                         [newer_version])
        self.assertEqual((after['accepted_versions'], after['reviewable_active_versions']),
                         (0, 1))
        self.assertEqual(after['human_acceptance'], 'NOT_ACCEPTED',
                         'the live version is unjudged; an old signature is not consent to it')
        # The store never demotes replaced bytes, so 'still ACTIVE' is not enough to make
        # a revision judgeable: signing a draft has to be refused by name rather than
        # filed as a verdict that quietly counts for nothing.
        status, refused = self.call(
            'POST', f'/api/projects/{self.project_id}/jury/verdict',
            self._verdict(jury_record_id='jury-http-stale'))
        self.assertEqual(status, 400, 'a replaced revision must not be filable as a verdict')
        self.assertIn('latest ACTIVE', refused['error'])
        # The superseded approval is still readable and still names its own digest.
        self.assertIn(self._verdict()['jury_record_id'],
                      [row['jury_record_id'] for row in after['records']])
        self.assertEqual(list(after['current_verdicts']),
                         [f'{jury_store.SUBJECT_PREFIX}{self.version_id}'])
        # And re-judging the bytes that are actually current closes it again.
        self.assertEqual(
            self.call('POST', f'/api/projects/{self.project_id}/jury/verdict',
                      self._verdict(jury_record_id='jury-http-2',
                                    subject_ref=f'{jury_store.SUBJECT_PREFIX}{newer_version}',
                                    artifact_sha256=newer_digest))[0], 201)
        _, closed = self.call('GET', f'/api/projects/{self.project_id}/jury')
        self.assertEqual((closed['accepted_versions'], closed['reviewable_active_versions']),
                         (1, 1))
        self.assertEqual(closed['human_acceptance'], 'ACCEPTED')

    def test_an_agent_signature_is_refused_with_the_reason_not_a_generic_400(self):
        document = self._verdict(juror={'juror_id': 'codex', 'kind': 'CODEX',
                                        'members': [], 'attestation': 'auto'})
        status, body = self.call('POST', f'/api/projects/{self.project_id}/jury/verdict',
                                 document)
        self.assertEqual(status, 400)
        self.assertIn('CODEX', body['error'])
        status, after = self.call('GET', f'/api/projects/{self.project_id}/jury')
        self.assertEqual(after['verdict_count'], 0, 'a refused signature must leave no record')

    def test_reposting_the_same_submission_is_a_replay_not_a_second_verdict(self):
        first = self._verdict()
        self.assertEqual(self.call('POST', f'/api/projects/{self.project_id}/jury/verdict',
                                   first)[0], 201)
        status, replay = self.call('POST', f'/api/projects/{self.project_id}/jury/verdict',
                                   first)
        self.assertEqual(status, 201)
        self.assertEqual(replay['jury_record_id'], 'jury-http-1')
        _, body = self.call('GET', f'/api/projects/{self.project_id}/jury')
        self.assertEqual(body['verdict_count'], 1,
                         'a resend after a lost response must not duplicate an attestation')

    def test_reusing_an_id_for_different_content_is_a_conflict(self):
        self.call('POST', f'/api/projects/{self.project_id}/jury/verdict', self._verdict())
        status, body = self.call('POST', f'/api/projects/{self.project_id}/jury/verdict',
                                 self._verdict(verdict='REJECT',
                                               evidence_refs=['contact sheet, 100% crop']))
        self.assertEqual(status, 409)
        self.assertEqual(body['error'], 'JURY_RECORD_ID_TAKEN')

    def test_a_verdict_cannot_borrow_a_version_from_another_project(self):
        """The version must belong to the project the verdict is filed against."""
        other_id = self.service.create_project('Other Probe')['id']
        other_version, other_digest = self._publish(b'other project artwork',
                                                    project_id=other_id, asset_id='a9')
        document = self._verdict(subject_ref=f'{jury_store.SUBJECT_PREFIX}{other_version}',
                                 artifact_sha256=other_digest)
        status, body = self.call('POST', f'/api/projects/{self.project_id}/jury/verdict',
                                 document)
        self.assertEqual(status, 400, body)
        self.assertIn('not a version of this project', body['error'])
        _, after = self.call('GET', f'/api/projects/{self.project_id}/jury')
        self.assertEqual(after['verdict_count'], 0)

    def test_a_proposal_is_recorded_separately_and_grants_nothing(self):
        proposal = {
            'schemaVersion': 'design-lab/assurance-jury-proposal/v2',
            'kind': 'JURY_PROPOSAL', 'proposal_id': 'prop-http-1',
            'subject_ref': f'{jury_store.SUBJECT_PREFIX}{self.version_id}',
            'artifact_sha256': self.digest, 'proposer': 'review-agent',
            'criteria': CRITERIA, 'suggested_verdict': 'APPROVE',
            'rationale': 'weighted mean above the floor',
            'created_at': '2026-10-08T00:00:00Z',
        }
        status, stored = self.call('POST', f'/api/projects/{self.project_id}/jury/proposal',
                                   proposal)
        self.assertEqual(status, 201, stored)
        _, body = self.call('GET', f'/api/projects/{self.project_id}/jury')
        self.assertEqual(body['proposal_count'], 1)
        self.assertEqual(body['verdict_count'], 0)
        self.assertEqual(body['human_acceptance'], 'NOT_ACCEPTED',
                         'an agent suggestion must not read as an accepted gate')

    def test_unknown_project_is_404_not_an_empty_review(self):
        status, body = self.call('GET', f'/api/projects/{"0" * 32}/jury')
        self.assertEqual(status, 404)
        self.assertEqual(body['error'], 'PROJECT_NOT_FOUND')

    def _other_project(self):
        other = self.base / 'other'
        other.mkdir()
        (other / 'AGENTS.md').write_text('# other project', encoding='utf-8')
        return other


if __name__ == '__main__':
    unittest.main()
