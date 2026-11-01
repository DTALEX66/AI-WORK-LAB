# SPDX-License-Identifier: MIT
"""DL-KB-07: the assistance plan store -- revisions, pinned references, and four honest states.

What this suite is for. A plan is the object a short task can be written into without building a
complete project first, and the ways it can start lying are specific:

* **a saved plan quietly claims more than storage.** "saved", "provided", "chosen" and "externally
  verified" are four different facts. A plan with an objective and no creative is saved and not
  provided; a named human choosing a revision is the only way "chosen" turns true; nothing in this
  repository dispatches an external step, so "externally verified" is a constant false that only a
  contract change can move.
* **a registered link is read as analysis.** Citing an image is not analysing it. The readback must
  say LINKED_ONLY until a stored reversal for that exact asset digest exists -- and the same test
  then performs the reversal and requires ANALYZED, so LINKED_ONLY is a measurement rather than a
  constant.
* **a reference silently follows its object.** A plan pins the revision and digest it used. When
  the object moves on, the readback says CHANGED instead of presenting the new bytes as the old
  basis.
* **an agent's choice is filed as a person's.** The route refuses `actor_kind: agent`, and the
  storage CHECK refuses it again, so the rule survives an application bug.
* **a correction overwrites its parent.** Revisions are append-only, "current" is MAX(revision),
  and a write prepared against a stale revision is refused with the actual number.
* **a caller mints its own evidence.** Reference revision/digest are resolved from the live object;
  a request that supplies them is refused. A missing job_id is the literal UNUSED, never an id the
  service invented.
* **history exists but cannot be read.** DL-KB-12. The readback serves the newest revision's
  document and lists the older rows by digest only, so a comparison page had one real document and
  a row of hashes to compare it with. The single-revision route has to answer the older row's own
  bytes -- and refuse a number nobody wrote, a row whose text no longer matches the digest it
  publishes, and a row that cannot be parsed, each with its own code.

Nothing here proves a model ran, an external job executed, or an asset was analysed by a model: the
counts are rows in a local store, and the one analysis this suite records is a reversal whose
observations the caller supplied.
"""
from __future__ import annotations

import base64
import hashlib
import http.client
import io
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

from design_lab import assistance_plan                              # noqa: E402
from design_lab.assistance_plan import (                            # noqa: E402
    AssistancePlanError, UNKNOWN, UNUSED)
from design_lab.http_service import make_server                     # noqa: E402
from design_lab.interop import load_schema, schema_errors            # noqa: E402
from design_lab.service import ProjectService                       # noqa: E402

DETECTIONS = [
    {'text': 'PROMPT', 'confidence': 0.91, 'polygon': [[1, 1], [4, 1], [4, 3], [1, 3]]},
    {'text': 'HOP', 'confidence': 0.57, 'polygon': [[1, 4], [4, 4], [4, 6], [1, 6]]},
]


def _png_bytes() -> bytes:
    from PIL import Image

    stream = io.BytesIO()
    Image.new('RGB', (8, 6), 'white').save(stream, format='PNG')
    return stream.getvalue()


def plan_body(**overrides):
    body = {
        'objective': '为秋季新品做一张克制的主视觉海报',
        'output_type': 'IMAGE',
        'neutral_creative': '一束侧光穿过纸纤维，留出大面积空白承载标题。',
        'brand_constraints': ['只用两种油墨'],
        'role_constraints': [],
        'lens': None,
        'sound': None,
        'references': [],
        'external_steps': [],
        'known_gaps': ['目标纸张未定'],
        'limits': ['未包含多语言排版'],
        'created_by': 'owner',
    }
    body.update(overrides)
    return body


class AssistancePlanTests(unittest.TestCase):
    def setUp(self):
        os.environ.pop('PROJECT_LOCAL_ROOT', None)
        self.base = Path(tempfile.mkdtemp(dir=REPO / '.project-local' / 'task-runtime'))
        self.root = self.base / 'project'
        self.root.mkdir()
        (self.root / 'AGENTS.md').write_text('# assistance plan fixture', encoding='utf-8')
        self.token = secrets.token_hex(32)
        self._serve(ProjectService(self.root))
        self.project = self.service.create_project('Assistance Plan')['id']

    def tearDown(self):
        self.httpd.shutdown()
        self.httpd.server_close()
        self.thread.join(timeout=5)

    def _serve(self, service):
        self.service = service
        self.httpd = make_server(service, self.token, 0)
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()

    def _restart(self):
        self.httpd.shutdown()
        self.httpd.server_close()
        self.thread.join(timeout=5)
        self._serve(ProjectService(self.root))

    def _call(self, method, path, body=None):
        headers = {'Authorization': 'Bearer ' + self.token}
        if body is not None:
            headers['Content-Type'] = 'application/json'
        with closing(http.client.HTTPConnection('127.0.0.1', self.httpd.server_port,
                                                timeout=20)) as conn:
            conn.request(method, path, body=None if body is None else json.dumps(body),
                         headers=headers)
            response = conn.getresponse()
            raw = response.read()
            return response.status, (json.loads(raw) if raw else None)

    def _create(self, project=None, **overrides):
        status, body = self._call(
            'POST', f'/api/projects/{project or self.project}/assistance-plans',
            plan_body(**overrides))
        self.assertEqual(status, 201, body)
        return body['plan']

    def _import_asset(self, project=None, key='asset-1'):
        status, body = self._call(
            'POST', f'/api/projects/{project or self.project}/assets',
            {'content_base64': base64.b64encode(_png_bytes()).decode(),
             'idempotency_key': key})
        self.assertEqual(status, 201, body)
        return body['asset']

    # -- B1: a plan, its basis, its limits; saved and read back after a restart -------

    def test_a_plan_is_saved_with_its_basis_and_reads_back_after_a_restart(self):
        created = self._create(
            external_steps=[{'step': '手动导出印刷 PDF', 'tool': 'Illustrator',
                             'job_id': None, 'operation_id': 'op-1024'}],
            known_gaps=['目标纸张未定'], limits=['未包含多语言排版'])
        detail = self._call('GET',
                            f'/api/projects/{self.project}/assistance-plans/'
                            f'{created["plan_id"]}')[1]
        self.assertEqual(1, detail['latest_revision'])
        self.assertEqual(created, detail['current'],
                         'the readback rebuilt a different document from the one the write answered')
        self.assertEqual(created['content_sha256'],
                         assistance_plan._content_digest(created),
                         'the stored digest does not cover the bytes it claims to')
        self.assertEqual(['目标纸张未定'], detail['current']['known_gaps'])
        self.assertEqual(['未包含多语言排版'], detail['current']['limits'])
        self.assertEqual([{'step': '手动导出印刷 PDF', 'tool': 'Illustrator',
                           'job_id': UNUSED, 'operation_id': 'op-1024'}],
                         detail['current']['external_steps'],
                         'an absent job_id must be stored as the literal UNUSED, never omitted')
        self.assertFalse(detail['external']['verified'])
        self.assertEqual(['op-1024'], detail['external']['supplied_ids'])
        self.assertTrue(detail['states']['saved'])
        self.assertTrue(detail['states']['provided'])
        self.assertFalse(detail['states']['chosen'])
        self.assertFalse(detail['states']['externally_verified'])
        self.assertTrue(detail['current']['claims_not_made'])

        self._restart()
        again = self._call('GET', f'/api/projects/{self.project}/assistance-plans/'
                                  f'{created["plan_id"]}')
        self.assertEqual(200, again[0], again[1])
        self.assertEqual(created, again[1]['current'],
                         'the plan did not survive a restart byte for byte')
        listed = self._call('GET', f'/api/projects/{self.project}/assistance-plans')[1]
        self.assertEqual(1, listed['total'])
        self.assertEqual(created['plan_id'], listed['plans'][0]['plan_id'])
        self.assertEqual(0, listed['plans'][0]['reference_count'])

    def test_a_draft_without_a_creative_is_saved_but_not_provided(self):
        created = self._create(neutral_creative=None)
        self.assertEqual(UNKNOWN, created['neutral_creative'])
        detail = self._call('GET', f'/api/projects/{self.project}/assistance-plans/'
                                   f'{created["plan_id"]}')[1]
        self.assertTrue(detail['states']['saved'])
        self.assertFalse(detail['states']['provided'],
                         'a plan with no creative must not read as provided just because it saved')

    # -- revisions --------------------------------------------------------------------

    def test_a_stale_revision_is_refused_with_the_actual_number(self):
        created = self._create()
        status, body = self._call(
            'POST', f'/api/projects/{self.project}/assistance-plans/'
                    f'{created["plan_id"]}/revisions',
            plan_body(expected_revision=1, objective='第二版'))
        self.assertEqual(201, status, body)
        self.assertEqual(2, body['revision'])
        status, refused = self._call(
            'POST', f'/api/projects/{self.project}/assistance-plans/'
                    f'{created["plan_id"]}/revisions',
            plan_body(expected_revision=1, objective='第三版'))
        self.assertEqual(409, status)
        self.assertEqual('ASSISTANCE_PLAN_REVISION_CONFLICT', refused['error'])
        self.assertIn('revision 2', refused['detail'])
        detail = self._call('GET', f'/api/projects/{self.project}/assistance-plans/'
                                   f'{created["plan_id"]}')[1]
        self.assertEqual([1, 2], [row['revision'] for row in detail['revisions']],
                         'a refused write left a row behind')
        self.assertEqual('第二版', detail['current']['objective'])

    def test_a_plan_revision_without_expected_revision_is_refused(self):
        created = self._create()
        status, body = self._call(
            'POST', f'/api/projects/{self.project}/assistance-plans/'
                    f'{created["plan_id"]}/revisions', plan_body())
        self.assertEqual(400, status,
                         'the route requires expected_revision by exact key set, so this body '
                         'never reaches the store')
        self.assertEqual('INVALID_PROJECT_FIELDS', body['error'])
        # The store refuses the same shape for any other caller; the route's exact key set is a
        # first line, not the only one.
        with self.assertRaises(AssistancePlanError) as caught:
            assistance_plan.AssistancePlans(self.service).revise(
                self.project, created['plan_id'], plan_body())
        self.assertEqual('ASSISTANCE_PLAN_EXPECTED_REVISION_REQUIRED', caught.exception.code)

    def test_the_revision_table_refuses_its_own_rewrite(self):
        created = self._create()
        with closing(assistance_plan.connect(
                self.service.database, project_root=self.service.paths.project_root)) as conn:
            for statement in (
                    'UPDATE assistance_plan_revision SET objective = ? WHERE plan_id = ?',
                    'DELETE FROM assistance_plan_revision WHERE plan_id = ?'):
                args = (('rewritten', created['plan_id']) if statement.startswith('UPDATE')
                        else (created['plan_id'],))
                with self.assertRaises(sqlite3.IntegrityError):
                    conn.execute(statement, args)
            conn.rollback()

    # -- B6: a link is not an analysis ------------------------------------------------

    def test_a_linked_asset_is_reported_linked_only_until_a_reversal_exists(self):
        asset = self._import_asset()
        created = self._create(references=[{'kind': 'ASSET', 'id': asset['id']}])
        self.assertEqual(asset['id'], created['references'][0]['id'])
        self.assertEqual(asset['sha256'], created['references'][0]['sha256'],
                         'the pinned digest is not the digest the import route verified')
        detail = self._call('GET', f'/api/projects/{self.project}/assistance-plans/'
                                   f'{created["plan_id"]}')[1]
        status = detail['reference_status'][0]
        self.assertEqual('CURRENT', status['state'])
        self.assertEqual('LINKED_ONLY', status['analysis'],
                         'registering a link was reported as analysing the image')
        self.assertEqual({'analyzed': 0, 'linked_only': 1}, detail['analysis_summary'])

        status_code, reversal = self._call(
            'POST', f'/api/projects/{self.project}/assets/{asset["id"]}/prompt-reversal',
            {'module': 'ocr-fixture', 'detections': DETECTIONS, 'decomposition_id': None})
        self.assertEqual(201, status_code, reversal)
        detail = self._call('GET', f'/api/projects/{self.project}/assistance-plans/'
                                   f'{created["plan_id"]}')[1]
        self.assertEqual('ANALYZED', detail['reference_status'][0]['analysis'],
                         'a stored reversal for the exact asset digest must flip LINKED_ONLY; '
                         'otherwise the first assertion proves only a constant')
        self.assertEqual({'analyzed': 1, 'linked_only': 0}, detail['analysis_summary'])

    def test_a_reference_that_moved_on_is_reported_changed(self):
        asset = self._import_asset()
        created = self._create(references=[{'kind': 'ASSET', 'id': asset['id']}])
        other = 'sha256:' + hashlib.sha256(b'second version').hexdigest()
        with closing(assistance_plan.connect(
                self.service.database, project_root=self.service.paths.project_root)) as conn:
            conn.execute('INSERT INTO asset_version (version_id, asset_id, version_no,'
                         ' content_sha256, state, created_at) VALUES (?,?,?,?,?,?)',
                         ('v-' + secrets.token_hex(16), asset['id'], 2, other, 'ACTIVE',
                          '2026-10-24T00:00:00Z'))
            conn.commit()
        status = self._call('GET', f'/api/projects/{self.project}/assistance-plans/'
                                   f'{created["plan_id"]}')[1]['reference_status'][0]
        self.assertEqual('CHANGED', status['state'])
        self.assertEqual(1, status['recorded_revision'])
        self.assertEqual(asset['sha256'], status['recorded_sha256'])
        self.assertEqual(2, status['current_revision'])
        self.assertEqual(other, status['current_sha256'])

    def test_a_caller_supplied_revision_or_digest_is_refused(self):
        asset = self._import_asset()
        for extra in ({'sha256': asset['sha256']}, {'revision': 1}):
            status, body = self._call(
                'POST', f'/api/projects/{self.project}/assistance-plans',
                plan_body(references=[dict({'kind': 'ASSET', 'id': asset['id']}, **extra)]))
            self.assertEqual(400, status)
            self.assertEqual('ASSISTANCE_PLAN_REFERENCE_UNKNOWN_FIELD', body['error'])

    def test_a_reference_from_another_project_is_refused(self):
        other_project = self.service.create_project('Other')['id']
        foreign = self._import_asset(project=other_project, key='foreign-1')
        status, body = self._call(
            'POST', f'/api/projects/{self.project}/assistance-plans',
            plan_body(references=[{'kind': 'ASSET', 'id': foreign['id']}]))
        self.assertEqual(409, status)
        self.assertEqual('ASSISTANCE_PLAN_REFERENCE_PROJECT_MISMATCH', body['error'])

    def test_an_unstored_reference_is_a_404_not_a_saved_plan(self):
        status, body = self._call(
            'POST', f'/api/projects/{self.project}/assistance-plans',
            plan_body(references=[{'kind': 'ASSET', 'id': 'img-' + '0' * 64}]))
        self.assertEqual(404, status)
        self.assertEqual('ASSISTANCE_PLAN_REFERENCE_NOT_FOUND', body['error'])
        listed = self._call('GET', f'/api/projects/{self.project}/assistance-plans')[1]
        self.assertEqual(0, listed['total'], 'a refused create left a plan row behind')

    # -- choosing is a named human's record -------------------------------------------

    def test_only_a_named_human_can_choose_a_revision(self):
        created = self._create()
        status, body = self._call(
            'POST', f'/api/projects/{self.project}/assistance-plans/'
                    f'{created["plan_id"]}/choose',
            {'actor': 'agent-1', 'actor_kind': 'agent', 'revision': 1})
        self.assertEqual(409, status)
        self.assertEqual('ASSISTANCE_PLAN_CHOICE_NOT_HUMAN', body['error'])
        status, chosen = self._call(
            'POST', f'/api/projects/{self.project}/assistance-plans/'
                    f'{created["plan_id"]}/choose',
            {'actor': 'DTALEX66', 'actor_kind': 'human', 'revision': 1})
        self.assertEqual(200, status, chosen)
        self.assertEqual({'chosen': True, 'revision': 1, 'actor': 'DTALEX66',
                          'actor_kind': 'human',
                          'chosen_at': chosen['choice']['chosen_at'], 'is_latest': True},
                         chosen['choice'])
        self.assertTrue(chosen['states']['chosen'])
        with closing(assistance_plan.connect(
                self.service.database, project_root=self.service.paths.project_root)) as conn:
            with self.assertRaises(sqlite3.IntegrityError):
                conn.execute('INSERT INTO assistance_plan_choice (plan_id, revision, actor,'
                             ' actor_kind, chosen_at) VALUES (?,?,?,?,?)',
                             (created['plan_id'], 1, 'agent-2', 'agent', '2026-10-24T00:00:00Z'))
            conn.rollback()

    def test_choosing_a_revision_that_does_not_exist_is_refused(self):
        created = self._create()
        status, body = self._call(
            'POST', f'/api/projects/{self.project}/assistance-plans/'
                    f'{created["plan_id"]}/choose',
            {'actor': 'DTALEX66', 'actor_kind': 'human', 'revision': 3})
        self.assertEqual(400, status)
        self.assertEqual('ASSISTANCE_PLAN_CHOICE_REVISION_INVALID', body['error'])

    # -- DL-KB-12: one stored revision, read back as its own bytes -------------------

    def _revise(self, plan_id, **overrides):
        status, answer = self._call(
            'POST', f'/api/projects/{self.project}/assistance-plans/{plan_id}/revisions',
            plan_body(expected_revision=1, **overrides))
        self.assertEqual(201, status, answer)
        return answer['plan']

    def _read(self, plan_id, revision, project=None):
        return self._call('GET', f'/api/projects/{project or self.project}/assistance-plans'
                                 f'/{plan_id}/revisions/{revision}')

    def _detail(self, plan_id):
        return self._call('GET', f'/api/projects/{self.project}/assistance-plans/{plan_id}')[1]

    def _append_revision(self, plan_id, document, *, content_sha256=None, document_json=None):
        """File one row holding exactly these bytes, the way the store would have written them.

        ``assistance_plan_revision`` is append-only *by trigger* -- UPDATE aborts, and that refusal
        is the invariant this whole family rests on -- so a row whose stored text predates an
        optional field, or whose digest has come to disagree with its own bytes, is reproduced by
        inserting it. ``content_sha256`` and ``document_json`` may be handed over separately from
        ``document`` on purpose: those are the two ways a row can stop matching what it publishes.
        """
        with closing(assistance_plan.connect(
                self.service.database, project_root=self.service.paths.project_root)) as conn:
            top = conn.execute('SELECT MAX(revision) AS top FROM assistance_plan_revision'
                               ' WHERE plan_id=?', (plan_id,)).fetchone()['top']
            document = dict(document, revision=top + 1)
            conn.execute(
                'INSERT INTO assistance_plan_revision (plan_id, revision, objective, output_type,'
                ' content_sha256, created_at, created_by, document_json) VALUES (?,?,?,?,?,?,?,?)',
                (plan_id, document['revision'], document['objective'], document['output_type'],
                 content_sha256 or document['content_sha256'],
                 document.get('created_at', '2026-10-24T00:00:00Z'), document['created_by'],
                 assistance_plan._canonical(document) if document_json is None else document_json))
            conn.commit()
        return document

    def test_an_older_revision_reads_back_as_that_revision_and_not_as_the_current_one(self):
        """The bug this route exists to make impossible: a comparison page reading r2 twice.

        ``assertNotEqual`` on the two documents is the whole acceptance clause -- 「新版本不覆盖历史；
        对比页读的是两份真实修订」 is only checkable when the older row answers its own objective and
        its own creative, and a service that quietly served the newest bytes for any number would
        still return a 200 with a plausible-looking envelope.
        """
        created = self._create()
        second = self._revise(created['plan_id'], objective='第二版：把主视觉改成竖版',
                              neutral_creative='竖构图，标题落在上三分之一。')
        status, first = self._read(created['plan_id'], 1)
        self.assertEqual(200, status, first)
        self.assertEqual('design-lab/assistance-plan-revision/v1', first['schemaVersion'])
        self.assertEqual(1, first['revision'])
        self.assertEqual(2, first['latest_revision'])
        self.assertFalse(first['is_latest'], 'r1 of a two-revision plan cannot be the newest row')
        self.assertEqual(created, first['document'],
                         'the older read rebuilt the document instead of serving the stored bytes')
        self.assertNotEqual(second, first['document'])
        self.assertNotEqual(second['objective'], first['document']['objective'],
                            'the two revisions answered the same objective, so the diff is empty')
        self.assertNotEqual(second['neutral_creative'], first['document']['neutral_creative'])
        self.assertNotEqual(first['content_sha256'], second['content_sha256'])

    def test_the_latest_revision_carries_the_digest_the_readback_publishes(self):
        plan_id = self._create()['plan_id']
        self._revise(plan_id, objective='第二版')
        detail = self._detail(plan_id)
        status, latest = self._read(plan_id, 2)
        self.assertEqual(200, status, latest)
        self.assertTrue(latest['is_latest'])
        self.assertEqual(2, latest['latest_revision'])
        self.assertEqual(detail['current'], latest['document'],
                         'two routes serving "the newest revision" answered different bytes')
        self.assertEqual(detail['current']['content_sha256'], latest['content_sha256'])

    def test_every_revision_row_the_readback_lists_is_served_byte_for_byte(self):
        """No second truth: the readback's per-row columns and this route's answer are one row.

        The comparison page is handed the readback's ``revisions`` list to pick two numbers with, so
        the digest, author and timestamp it shows for r1 must be the ones the r1 read reports -- and
        the document must be the exact JSON in the database, not a re-rendering of it.
        """
        plan_id = self._create()['plan_id']
        self._revise(plan_id, objective='第二版')
        detail = self._detail(plan_id)
        with closing(assistance_plan.connect(
                self.service.database, project_root=self.service.paths.project_root)) as conn:
            stored = {row['revision']: row['document_json'] for row in conn.execute(
                'SELECT revision, document_json FROM assistance_plan_revision WHERE plan_id=?',
                (plan_id,))}
        for row in detail['revisions']:
            status, answer = self._read(plan_id, row['revision'])
            self.assertEqual(200, status, answer)
            self.assertTrue(row['readable'], 'the readback listed a row this route could not read')
            self.assertEqual(row['content_sha256'], answer['content_sha256'])
            self.assertEqual(row['created_at'], answer['created_at'])
            self.assertEqual(row['created_by'], answer['created_by'])
            self.assertEqual(assistance_plan._canonical(answer['document']),
                             stored[row['revision']],
                             'the served document is not the stored bytes, character for character')

    def test_an_unstored_revision_number_is_a_404_that_names_the_highest_one(self):
        created = self._create()
        self._revise(created['plan_id'], objective='第二版')
        status, refused = self._read(created['plan_id'], 3)
        self.assertEqual(404, status, refused)
        self.assertEqual('ASSISTANCE_PLAN_REVISION_NOT_FOUND', refused['error'])
        self.assertIn(created['plan_id'], refused['detail'])
        self.assertIn('the highest revision it has is 2', refused['detail'],
                      'the refusal must name the numbers that really exist, or the page cannot '
                      'tell a wrong revision from a wrong plan')
        # `revisions/0` is refused by the path pattern before the store is reached, and a target
        # with a query string is no route at all -- the number is a path segment here.
        status, refused = self._read(created['plan_id'], 0)
        self.assertEqual(404, status, refused)
        self.assertEqual('NOT_FOUND', refused['error'])
        status, refused = self._call(
            'GET', f'/api/projects/{self.project}/assistance-plans/{created["plan_id"]}'
                   f'/revisions/2?revision=1')
        self.assertEqual(404, status, refused)
        self.assertEqual('NOT_FOUND', refused['error'],
                         'a query the route does not define must not be honoured quietly')

    def test_is_chosen_follows_the_choice_row_and_stays_false_for_a_plan_nobody_chose(self):
        plan_id = self._create()['plan_id']
        self._revise(plan_id, objective='第二版')
        for number in (1, 2):
            status, answer = self._read(plan_id, number)
            self.assertEqual(200, status, answer)
            self.assertFalse(answer['is_chosen'], f'r{number} cannot be chosen by nobody')
        status, chosen = self._call(
            'POST', f'/api/projects/{self.project}/assistance-plans/{plan_id}/choose',
            {'actor': 'DTALEX66', 'actor_kind': 'human', 'revision': 1})
        self.assertEqual(200, status, chosen)
        self.assertTrue(self._read(plan_id, 1)[1]['is_chosen'])
        self.assertFalse(self._read(plan_id, 2)[1]['is_chosen'],
                         'the newest revision is not thereby the adopted one')
        self.assertEqual(self._detail(plan_id)['choice']['revision'],
                         self._read(plan_id, 1)[1]['revision'],
                         'the readback and the revision read answer a different adopted revision')

    def test_a_revision_with_no_creative_reads_back_as_not_provided(self):
        """`provided` is this row's own answer, not the readback's answer about the newest row."""
        draft = self._create(neutral_creative=None)
        self._revise(draft['plan_id'], objective='第二版：现在写得出创意了',
                     neutral_creative='竖构图，标题落在上三分之一。')
        self.assertFalse(self._read(draft['plan_id'], 1)[1]['provided'],
                         'the draft row has no creative even though the plan now has one')
        self.assertTrue(self._read(draft['plan_id'], 2)[1]['provided'])
        self.assertTrue(self._detail(draft['plan_id'])['states']['provided'])

    def test_a_revision_stored_before_an_optional_field_existed_still_reads_back(self):
        """A pre-DL-KB-11 document is history, not a defect -- and it still satisfies the contract.

        The row is rewritten to the bytes the writer produced before ``shots`` existed (no ``shots``
        key at all, its digest over the fields it had), because the compatibility claim is about
        stored history. The digest guard is the load-bearing part of this read: a re-derivation that
        quietly supplied the missing key would convict an untouched plan of drift.
        """
        created = self._create()
        document = dict(created)
        document.pop('shots')
        legacy_fields = tuple(key for key in assistance_plan.CONTENT_FIELDS if key != 'shots')
        document['content_sha256'] = assistance_plan._digest(
            {key: document.get(key) for key in legacy_fields})
        self._append_revision(created['plan_id'], document)

        status, answer = self._read(created['plan_id'], 2)
        self.assertEqual(200, status, answer)
        self.assertNotIn('shots', answer['document'],
                         'the read rebuilt the document instead of serving the stored bytes')
        self.assertEqual(document['content_sha256'], answer['content_sha256'])
        self.assertEqual([], schema_errors(load_schema(assistance_plan.PLAN_SCHEMA_PATH),
                                           answer['document']),
                         'a plan stored before an optional field existed no longer satisfies the '
                         'plan contract')
        # The row that does carry the field is untouched by any of this.
        self.assertEqual([], schema_errors(load_schema(assistance_plan.PLAN_SCHEMA_PATH),
                                           self._read(created['plan_id'], 1)[1]['document']))

    def test_the_served_does_not_say_is_the_readback_s_list_unchanged(self):
        created = self._create()
        self._revise(created['plan_id'], objective='第二版')
        detail = self._detail(created['plan_id'])
        for number in (1, 2):
            self.assertEqual(detail['does_not_say'], self._read(created['plan_id'], number)[1]
                             ['does_not_say'], f'r{number} rewrote what a plan record is not')
        self.assertEqual(list(assistance_plan.DOES_NOT_SAY),
                         self._read(created['plan_id'], 1)[1]['does_not_say'],
                         'the sentence list was re-authored for this envelope -- a second copy of '
                         'a disclaimer is how the two answers start disagreeing')

    def test_the_revision_read_keeps_the_plan_s_own_refusal_vocabulary(self):
        """Unknown project, and a plan that is not in this project, are two different 404s."""
        created = self._create()
        other = self.service.create_project('Revision Reader')['id']
        status, refused = self._read(created['plan_id'], 1, project='0' * 32)
        self.assertEqual(404, status, refused)
        self.assertEqual('PROJECT_NOT_FOUND', refused['error'])
        status, refused = self._read(created['plan_id'], 1, project=other)
        self.assertEqual(404, status, refused)
        self.assertEqual('ASSISTANCE_PLAN_NOT_FOUND', refused['error'])
        # The store refuses a non-number for any caller, not only the one the pattern screens out.
        with self.assertRaises(AssistancePlanError) as caught:
            assistance_plan.AssistancePlans(self.service).revision(
                self.project, created['plan_id'], '1')
        self.assertEqual('ASSISTANCE_PLAN_REVISION_NUMBER_INVALID', caught.exception.code)

    def test_an_unreadable_revision_row_is_refused_rather_than_returned_as_a_guess(self):
        created = self._create()
        self._append_revision(created['plan_id'], dict(created), document_json='{not json')
        status, refused = self._read(created['plan_id'], 2)
        self.assertEqual(409, status, refused)
        self.assertEqual('ASSISTANCE_PLAN_REVISION_UNREADABLE', refused['error'])
        self.assertIn('无法解析', refused['detail'])
        self.assertIn('猜出来', refused['detail'],
                      'the refusal has to say the service does not hand back a guessed version')

    def test_a_revision_whose_digest_no_longer_covers_its_bytes_is_refused(self):
        """Both directions of the same disagreement: edited bytes, or a column that moved alone.

        ``plan_feedback.list()`` raises PLAN_FEEDBACK_BYTES_MOVED in exactly this situation and this
        read copies that discipline at 500 -- a row that no longer hashes to what it publishes is a
        server-side fault, and serving it would put one revision's digest beside another
        revision's words on a comparison card.
        """
        created = self._create()
        edited = dict(created, neutral_creative='被人改过的正文，摘要却还是旧的。')
        self._append_revision(created['plan_id'], edited)
        status, refused = self._read(created['plan_id'], 2)
        self.assertEqual(500, status, refused)
        self.assertEqual('ASSISTANCE_PLAN_REVISION_BYTES_MOVED', refused['error'])
        self.assertIn(created['plan_id'], refused['detail'])
        self.assertIn('no longer hashes to what was stored', refused['detail'])

        self._append_revision(created['plan_id'], created, content_sha256='sha256:' + '1' * 64)
        status, refused = self._read(created['plan_id'], 3)
        self.assertEqual(500, status, refused)
        self.assertEqual('ASSISTANCE_PLAN_REVISION_BYTES_MOVED', refused['error'])
        self.assertIn('sha256:' + '1' * 64, refused['detail'])

    # -- the object's own refusals ----------------------------------------------------

    def test_the_output_type_vocabulary_is_served_before_any_project_exists(self):
        # DL-KB-08: the initial screen must offer an output type before a workspace exists. A
        # vocabulary that rides the project-scoped list route would be unavailable at exactly the
        # moment it is first needed, so this read is measured on a checkout with zero projects.
        empty = Path(tempfile.mkdtemp(dir=REPO / '.project-local' / 'task-runtime')) / 'empty'
        empty.mkdir()
        (empty / 'AGENTS.md').write_text('# empty checkout for the vocabulary read',
                                         encoding='utf-8')
        service = ProjectService(empty)
        httpd = make_server(service, self.token, 0)
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        try:
            with closing(http.client.HTTPConnection('127.0.0.1', httpd.server_port,
                                                    timeout=20)) as conn:
                conn.request('GET', '/api/assistance-plan-output-types',
                             headers={'Authorization': 'Bearer ' + self.token})
                response = conn.getresponse()
                body = json.loads(response.read())
            self.assertEqual(200, response.status, body)
            self.assertEqual(0, len(service.list_projects()))
            self.assertEqual('design-lab/assistance-plan-output-types/v1', body['schemaVersion'])
            self.assertEqual(list(assistance_plan.OUTPUT_TYPES),
                             [row['value'] for row in body['output_types']],
                             'the screen would offer a different set than the routes accept')
            for row in body['output_types']:
                self.assertEqual(assistance_plan.OUTPUT_LABELS[row['value']], row['label'])
        finally:
            httpd.shutdown()
            httpd.server_close()
            thread.join(timeout=5)

    def test_every_served_output_type_is_one_the_create_route_accepts(self):
        status, body = self._call('GET', '/api/assistance-plan-output-types')
        self.assertEqual(200, status, body)
        for row in body['output_types']:
            created = self._create(output_type=row['value'])
            self.assertEqual(row['value'], created['output_type'],
                             'the screen offered a word the create route stored as something else')

    def test_an_unknown_output_type_is_refused_by_name(self):
        status, body = self._call('POST', f'/api/projects/{self.project}/assistance-plans',
                                  plan_body(output_type='VIDEOGAME'))
        self.assertEqual(400, status)
        self.assertEqual('ASSISTANCE_PLAN_OUTPUT_TYPE_INVALID', body['error'])

    def test_a_plan_for_an_unknown_project_is_404(self):
        status, body = self._call('POST',
                                  f'/api/projects/{"0" * 32}/assistance-plans', plan_body())
        self.assertEqual(404, status)
        self.assertEqual('PROJECT_NOT_FOUND', body['error'])

    def test_a_plan_is_not_readable_through_another_project(self):
        created = self._create()
        other = self.service.create_project('Reader')['id']
        status, body = self._call('GET', f'/api/projects/{other}/assistance-plans/'
                                         f'{created["plan_id"]}')
        self.assertEqual(404, status)
        self.assertEqual('ASSISTANCE_PLAN_NOT_FOUND', body['error'])

    def test_the_schemas_are_packaged_and_named_by_state_resources(self):
        from design_lab.runtime.state_resources import state_schema
        self.assertTrue(state_schema('design-lab-state-assistance-plan-v1.sql').is_file())
        for path in (assistance_plan.PLAN_SCHEMA_PATH, assistance_plan._READBACK_SCHEMA_PATH,
                     assistance_plan._WRITE_SCHEMA_PATH, assistance_plan._LIST_SCHEMA_PATH,
                     assistance_plan._OUTPUT_TYPES_SCHEMA_PATH,
                     assistance_plan._REVISION_SCHEMA_PATH):
            self.assertTrue(path.is_file(), path)


    # -- DL-KB-05 D5: a plan that cites a library entry keeps its own pin ----------------

    #: The create route's exact key set. Written out here rather than imported from the knowledge
    #: suite so this file's cases cannot pass by borrowing another file's fixture.
    KNOWLEDGE_BODY = {
        'entry_type': 'METHOD',
        'title': '分镜拆解三步法',
        'summary': '把一段脚本拆成镜头表：先定节拍，再定景别，最后定转场。',
        'domain_tags': ['film'], 'task_tags': ['storyboard'], 'target_tools': ['storyboarder'],
        'body': '第一步按段落切节拍。第二步给每个节拍选景别。第三步只标必要的转场。',
        'applicability': '适合 30-90 秒短片的分镜前置。',
        'limits': '不适用于需要精确口型对位的动画。',
        'source': {'sourceId': 'plan-cites-knowledge', 'origin': 'UNKNOWN',
                   'author': 'owner', 'license': 'project-internal', 'licenseStatus': 'reviewed',
                   'allowedUsage': 'UNKNOWN', 'citationScope': 'UNKNOWN', 'version': '1',
                   'observedAt': '2026-10-24T00:00:00Z', 'contentHash': 'UNKNOWN',
                   'verification': 'UNVERIFIED'},
        'related_capability_ids': [], 'recommended': True, 'created_by': 'owner',
        'supersedes': None,
    }

    def _knowledge(self, **overrides) -> tuple:
        status, created = self._call('POST', '/api/knowledge-entries',
                                     dict(self.KNOWLEDGE_BODY, **overrides))
        self.assertEqual(201, status, created)
        entry = created['entry']
        return (entry['knowledge_entry_id'], entry['revision'], entry['content_sha256'])

    def _knowledge_revise(self, entry_id, revision, **overrides):
        body = {key: value for key, value in dict(self.KNOWLEDGE_BODY, **overrides).items()
                if key != 'supersedes'}
        status, answer = self._call(
            'POST', f'/api/knowledge-entries/{entry_id}/revisions',
            dict(body, expected_revision=revision, recommended=False,
                 title='分镜拆解三步法（修订）'))
        self.assertEqual(201, status, answer)
        return answer['entry']

    def _plan_reference(self, plan_id):
        detail = self._call('GET', f'/api/projects/{self.project}/assistance-plans/'
                                   f'{plan_id}')[1]
        return detail['current']['references'][0], detail['reference_status'][0]

    def test_a_cited_entry_is_pinned_to_the_newest_revision_not_the_recommended_one(self):
        entry_id, first_revision, first_digest = self._knowledge()
        second = self._knowledge_revise(entry_id, first_revision)
        created = self._create(references=[{'kind': 'KNOWLEDGE', 'id': entry_id}])
        pinned, status = self._plan_reference(created['plan_id'])
        self.assertEqual(second['revision'], pinned['revision'],
                         'a plan pinned the recommended revision; it cites the bytes that exist, '
                         'which is the newest revision -- recommendation is a separate answer')
        self.assertEqual(second['content_sha256'], pinned['sha256'])
        self.assertEqual('CURRENT', status['state'])
        self.assertIsNone(status['analysis'],
                          'a knowledge link is not an image analysis; nothing here ran a model')

    def test_moving_the_recommendation_back_leaves_the_cited_plan_reading_the_same_bytes(self):
        """DL-KB-05 D5, end to end through the routes: 回退推荐版本后旧方案仍可读."""
        entry_id, first_revision, _ = self._knowledge()
        second = self._knowledge_revise(entry_id, first_revision)
        created = self._create(references=[{'kind': 'KNOWLEDGE', 'id': entry_id}])
        before, before_status = self._plan_reference(created['plan_id'])
        status, moved = self._call(
            'POST', f'/api/knowledge-entries/{entry_id}/judgements',
            {'kind': 'RECOMMENDATION', 'revision': first_revision, 'value': None,
             'replaced_by': None, 'reason': '旧版本那三步在实际项目里更稳。',
             'recorded_by': '张工', 'recorded_by_kind': 'HUMAN'})
        self.assertEqual(201, status, moved)
        self.assertEqual(first_revision, moved['recommended_revision'])
        self.assertEqual(2, moved['latest_revision'])
        self.assertEqual('recorded-judgement', moved['recommendation_basis'])
        after, after_status = self._plan_reference(created['plan_id'])
        self.assertEqual(before, after,
                         'the plan changed what it cites because somebody moved a recommendation')
        self.assertEqual(second['content_sha256'], after['sha256'])
        self.assertEqual('CURRENT', after_status['state'],
                         'the pinned revision is still the newest row, so the link cannot be '
                         'reported as changed by a judgement that wrote no revision')

    def test_a_new_revision_moves_the_link_to_changed_without_touching_the_pin(self):
        entry_id, first_revision, _ = self._knowledge()
        second = self._knowledge_revise(entry_id, first_revision)
        created = self._create(references=[{'kind': 'KNOWLEDGE', 'id': entry_id}])
        pinned, _ = self._plan_reference(created['plan_id'])
        third = self._knowledge_revise(entry_id, 2, body='第三步改成先标轴线，再标转场。')
        still_pinned, status = self._plan_reference(created['plan_id'])
        self.assertEqual(pinned, still_pinned, 'a later revision rewrote an older plan\'s pin')
        self.assertEqual(second['content_sha256'], still_pinned['sha256'],
                         'the pin moved off the revision the plan actually cited')
        self.assertEqual('CHANGED', status['state'])
        self.assertEqual(third['revision'], status['current_revision'])

    def test_an_unknown_or_malformed_knowledge_reference_is_refused(self):
        for identifier, code, status_wanted in (
                ('kentry-' + '0' * 32, 'ASSISTANCE_PLAN_REFERENCE_NOT_FOUND', 404),
                ('kc-2026-01', 'ASSISTANCE_PLAN_REFERENCE_ID_MALFORMED', 400)):
            status, body = self._call(
                'POST', f'/api/projects/{self.project}/assistance-plans',
                plan_body(references=[{'kind': 'KNOWLEDGE', 'id': identifier}]))
            self.assertEqual(status_wanted, status, body)
            self.assertEqual(code, body['error'], body)

    def test_the_reference_kind_list_is_one_list_across_the_schemas(self):
        # Five words, four schemas, one tuple. Without this tie a kind can be added to the store
        # and left out of a contract (or the other way round) and every per-file test still passes.
        from design_lab import plan_export
        expected = list(assistance_plan.REFERENCE_KINDS)
        self.assertIn('KNOWLEDGE', expected)
        for path in (assistance_plan.PLAN_SCHEMA_PATH, assistance_plan._READBACK_SCHEMA_PATH,
                     plan_export._SCHEMA_PATH):
            document = load_schema(path)
            found = set()

            def walk(node):
                if isinstance(node, dict):
                    if node.get('enum') == expected or 'ASSET' in str(node.get('enum')):
                        found.add(tuple(node['enum']))
                    for value in node.values():
                        walk(value)
                elif isinstance(node, list):
                    for value in node:
                        walk(value)
            walk(document)
            self.assertTrue(found, f'{path.name} declares no reference-kind enum at all')
            for kinds in found:
                self.assertEqual(tuple(expected), kinds,
                                 f'{path.name} lists reference kinds the store does not accept '
                                 '(or is missing one): ' + str(kinds))

    def test_the_workbench_picker_labels_exactly_the_kinds_the_store_accepts(self):
        # The failure this pins already happened once: KNOWLEDGE went into REFERENCE_KINDS, the
        # four schemas and the resolver, and the picker kept offering two of the five kinds --
        # so a brief, a direction or a prompt result was citable by API and not from the screen.
        # No per-file test could see that, because each side was internally consistent.
        shell = (REPO / 'apps' / 'workbench' / 'shell.ts').read_text(encoding='utf-8')
        start = shell.index('const REFERENCE_KIND_LABELS')
        body = shell[start:shell.index('};', start)]
        labelled = sorted(token.rstrip(':')
                          for line in body.splitlines()[1:]
                          for token in line.split()
                          if token.endswith(':') and token[:-1].isupper())
        self.assertEqual(sorted(assistance_plan.REFERENCE_KINDS), labelled,
                         'the kinds the workbench can name are not the kinds the store accepts')
        for kind in assistance_plan.REFERENCE_KINDS:
            self.assertIn(f"referenceGroup('{kind}'", shell,
                          f'{kind} has a label but no group in the reference picker')


if __name__ == '__main__':
    unittest.main()
