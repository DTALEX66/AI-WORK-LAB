# SPDX-License-Identifier: MIT
"""DL-KB-16: voluntary external-use feedback, measured at the HTTP boundary.

The acceptance this module exists to hold is the one people get wrong: a satisfied report is
somebody's word about an external tool, not the system confirming anything. So the central test here
is not "can I write a row" -- it is that writing the row leaves the plan's own readback
byte-identical, including ``external.verified``.
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
from contextlib import closing
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / 'src'))

from design_lab import plan_feedback                                   # noqa: E402
from design_lab.http_service import make_server                        # noqa: E402
from design_lab.plan_feedback import OUTCOMES, PlanFeedback, UNUSED    # noqa: E402
from design_lab.service import ProjectService                          # noqa: E402

PLAN_BODY = {
    'objective': '为秋季新品做一张克制的主视觉海报',
    'output_type': 'IMAGE',
    'neutral_creative': '一束侧光穿过纸纤维，留出大面积空白承载标题。',
    'brand_constraints': ['只用两种油墨'], 'role_constraints': [],
    'lens': None, 'sound': None, 'references': [], 'external_steps': [],
    'known_gaps': ['目标纸张未定'], 'limits': ['未包含多语言排版'],
    'created_by': 'owner',
}


def feedback(**overrides):
    body = {'outcome': 'MATCHES', 'target_key': 'elevenlabs--web-app--music',
            'target_model': None, 'dimensions': [], 'issue_timecodes': [],
            'actor': 'dtalex66', 'note': '拿去外部走了一遍，符合。',
            'source_ref': None, 'revision': 1}
    body.update(overrides)
    return body


class PlanFeedbackTests(unittest.TestCase):
    def setUp(self):
        os.environ.pop('PROJECT_LOCAL_ROOT', None)
        self.base = Path(tempfile.mkdtemp(dir=REPO / '.project-local' / 'task-runtime'))
        self.root = self.base / 'project'
        self.root.mkdir()
        (self.root / 'AGENTS.md').write_text('# plan feedback fixture', encoding='utf-8')
        self.token = secrets.token_hex(32)
        self._serve(ProjectService(self.root))
        self.project = self.service.create_project('Feedback Plan')['id']
        status, created = self._call('POST', f'/api/projects/{self.project}/assistance-plans',
                                     PLAN_BODY)
        self.assertEqual(201, status, created)
        self.plan = created['plan']['plan_id']

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

    def _feedback_path(self):
        return (f'/api/projects/{self.project}/assistance-plans/{self.plan}/feedback')

    def _detail(self):
        return self._call('GET', f'/api/projects/{self.project}/assistance-plans/{self.plan}')[1]

    # -- the central honesty claim ----------------------------------------------------

    def test_recording_feedback_leaves_the_plan_readback_byte_identical(self):
        before = json.dumps(self._detail(), sort_keys=True)
        status, written = self._call('POST', self._feedback_path(), feedback())
        self.assertEqual(201, status, written)
        self.assertTrue(written['plan_states_unchanged'])
        after = self._detail()
        self.assertEqual(before, json.dumps(after, sort_keys=True),
                         'a feedback row changed the plan it describes')
        self.assertFalse(after['external']['verified'],
                         'a satisfied report must not become system verification')
        self.assertFalse(after['states']['externally_verified'])

    def test_a_feedback_record_states_what_it_does_not_prove(self):
        _, written = self._call('POST', self._feedback_path(), feedback())
        record = written['feedback']
        joined = ' '.join(record['does_not_say'])
        self.assertIn('不证明外部工具运行过', joined)
        self.assertIn('不会把方案的「外部未验证」状态改成已验证', joined)
        self.assertFalse(record['externally_verified'])
        self.assertTrue(record['voluntary'])
        self.assertIn('外部结果未被系统核验', ' '.join(written['claims_not_made']))

    # -- the outcome vocabulary -------------------------------------------------------

    def test_only_the_three_outcome_words_are_writable(self):
        for outcome in OUTCOMES:
            status, body = self._call('POST', self._feedback_path(), feedback(outcome=outcome))
            self.assertEqual(201, status, body)
        status, refused = self._call('POST', self._feedback_path(),
                                     feedback(outcome='DELIVERED'))
        self.assertEqual(400, status, refused)
        self.assertEqual('PLAN_FEEDBACK_OUTCOME_INVALID', refused['error'])
        status, refused = self._call('POST', self._feedback_path(), feedback(outcome=None))
        self.assertEqual(400, status, refused)

    def test_a_report_must_cite_a_revision_that_was_actually_written(self):
        status, refused = self._call('POST', self._feedback_path(), feedback(revision=7))
        self.assertEqual(409, status, refused)
        self.assertEqual('PLAN_FEEDBACK_REVISION_NOT_FOUND', refused['error'])
        status, refused = self._call('POST', self._feedback_path(), feedback(revision=None))
        self.assertEqual(400, status, refused)
        self.assertEqual('PLAN_FEEDBACK_REVISION_INVALID', refused['error'])

    def test_the_route_refuses_a_key_that_would_speak_for_the_system(self):
        status, refused = self._call('POST', self._feedback_path(),
                                     dict(feedback(), verified=True))
        self.assertEqual(400, status, refused)
        self.assertEqual('INVALID_PROJECT_FIELDS', refused['error'])

    def test_the_writer_mints_no_external_identifier(self):
        _, written = self._call('POST', self._feedback_path(), feedback(source_ref=None))
        self.assertEqual(UNUSED, written['feedback']['source_ref'])
        _, supplied = self._call('POST', self._feedback_path(), feedback(source_ref='op-77'))
        self.assertEqual('op-77', supplied['feedback']['source_ref'])

    def test_only_a_human_may_report_an_external_outcome(self):
        with closing(plan_feedback.connect(
                self.service.paths.database_path(self.service.database),
                project_root=self.service.paths.project_root)) as conn:
            with self.assertRaises(sqlite3.IntegrityError):
                conn.execute(
                    'INSERT INTO plan_feedback (plan_id, revision, feedback_no, outcome,'
                    " target_key, actor, actor_kind, note, source_ref, recorded_at,"
                    ' document_json, content_sha256) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',
                    (self.plan, 1, 99, 'MATCHES', 't', 'ci-bot', 'agent', None, UNUSED,
                     '2026-10-24T00:00:00Z', '{}', 'sha256:' + '0' * 64))

    # -- history, not a mutable marker -------------------------------------------------

    # -- 「符合/部分符合/不符合」的维度结论、问题时间码、绑定当时的模型 -----------------

    def test_a_report_carries_per_dimension_verdicts_in_the_card_s_words(self):
        _, written = self._call('POST', self._feedback_path(), feedback(dimensions=[
            {'name': '画幅', 'verdict': 'MATCHES', 'note': None},
            {'name': '品牌色', 'verdict': 'PARTIALLY_MATCHES', 'note': '暗部偏灰'},
            {'name': '留白比例', 'verdict': 'DOES_NOT_MATCH', 'note': '标题区被填满'}]))
        rows = written['feedback']['dimensions']
        self.assertEqual(['符合', '部分符合', '不符合'], [r['verdict_label'] for r in rows])
        self.assertEqual(['画幅', '品牌色', '留白比例'], [r['name'] for r in rows])
        # The dimension NAME is the reporter's words: the vocabulary is closed, the axes are not,
        # because a fixed axis list would be this service deciding what a plan cares about.
        self.assertFalse(any('UNKNOWN' in json.dumps(r) for r in rows))

    def test_a_dimension_without_a_closed_verdict_is_refused_not_defaulted(self):
        status, refused = self._call('POST', self._feedback_path(),
                                     feedback(dimensions=[{'name': '画幅', 'verdict': 'FINE'}]))
        self.assertEqual(400, status, refused)
        self.assertEqual('PLAN_FEEDBACK_DIMENSION_VERDICT_INVALID', refused['error'])

    def test_the_same_dimension_cannot_be_reported_twice_in_one_statement(self):
        status, refused = self._call('POST', self._feedback_path(), feedback(dimensions=[
            {'name': '画幅', 'verdict': 'MATCHES'}, {'name': '画幅', 'verdict': 'DOES_NOT_MATCH'}]))
        self.assertEqual(400, status, refused)
        self.assertEqual('PLAN_FEEDBACK_DIMENSION_DUPLICATED', refused['error'])

    def test_issue_timecodes_survive_verbatim_and_a_label_is_not_a_timecode(self):
        _, written = self._call('POST', self._feedback_path(),
                                feedback(issue_timecodes=['00:03-00:05', '00:11 单点']))
        self.assertEqual(['00:03-00:05', '00:11 单点'], written['feedback']['issue_timecodes'])
        status, refused = self._call('POST', self._feedback_path(),
                                     feedback(issue_timecodes=['标题区太挤']))
        self.assertEqual(400, status, refused)
        self.assertEqual('PLAN_FEEDBACK_TIMECODE_MALFORMED', refused['error'])

    def test_an_unreported_model_stays_null_with_a_reason_instead_of_being_inferred(self):
        _, written = self._call('POST', self._feedback_path(), feedback())
        self.assertIsNone(written['feedback']['target_model'])
        self.assertEqual('记录人没有说明当时用的模型/版本',
                         written['feedback']['target_model_reason'])
        _, bound = self._call('POST', self._feedback_path(),
                              feedback(target_model='eleven_v4'))
        self.assertEqual('eleven_v4', bound['feedback']['target_model'])
        self.assertIsNone(bound['feedback']['target_model_reason'])

    def test_the_material_binding_is_the_cited_revision_not_the_newest_one(self):
        """「反馈绑定当时资料与模型版本」: a report about r1 must still say r1 after r2 exists."""
        self._call('POST', self._feedback_path(), feedback(target_model='eleven_v4'))
        # The revise route's key set is the create set minus `supersedes`, plus
        # `expected_revision`; sending the create set verbatim is a 400 by design.
        revision = {key: value for key, value in PLAN_BODY.items() if key != 'supersedes'}
        revision['expected_revision'] = 1
        status, edited = self._call(
            'POST', f'/api/projects/{self.project}/assistance-plans/{self.plan}/revisions',
            revision)
        self.assertEqual(201, status, edited)
        self.assertEqual(2, edited['plan']['revision'])
        _, listing = self._call('GET', self._feedback_path())
        self.assertEqual([1], [r['revision'] for r in listing['records']],
                         'the earlier report drifted onto the newest revision')

    def test_recording_feedback_does_not_promote_the_plan_into_trusted_knowledge(self):
        """D-边界「采用一次方案不得自动升级为通用可信知识」/ 未反馈既不是失败也不是接受."""
        _, written = self._call('POST', self._feedback_path(),
                                feedback(outcome='MATCHES', target_model='eleven_v4'))
        self.assertTrue(written['feedback']['voluntary'])
        joined = ' '.join(written['feedback']['does_not_say'])
        self.assertIn('不是系统核验通过', joined)
        detail = self._detail()
        self.assertFalse(detail['external']['verified'])
        self.assertFalse(detail['states']['externally_verified'])
        # No feedback row is a knowledge candidate: promotion stays a separate, human-gated export.
        _, candidates = self._call('GET', f'/api/projects/{self.project}/knowledge-candidates')
        self.assertEqual(0, candidates['candidate_count'],
                         'a satisfied report must not file itself as reusable knowledge')

    def test_reports_are_a_history_and_a_correction_does_not_erase_the_first(self):
        first = self._call('POST', self._feedback_path(),
                           feedback(outcome='MATCHES', note='第一次'))[1]
        second = self._call('POST', self._feedback_path(),
                            feedback(outcome='DOES_NOT_MATCH', note='第二次：其实不符合',
                                     revision=1))[1]
        self.assertEqual(1, first['feedback']['feedback_no'])
        self.assertEqual(2, second['feedback']['feedback_no'])

        self._restart()
        _, listing = self._call('GET', self._feedback_path())
        self.assertEqual(2, listing['total'], 'the earlier statement disappeared')
        self.assertEqual(['MATCHES', 'DOES_NOT_MATCH'],
                         [r['outcome'] for r in listing['records']])
        self.assertEqual({'MATCHES': 1, 'PARTIALLY_MATCHES': 0, 'DOES_NOT_MATCH': 1},
                         listing['outcome_histogram'])
        self.assertEqual(second['feedback']['feedback_no'], listing['latest']['feedback_no'])
        self.assertFalse(listing['externally_verified'])
        self.assertIsNone(listing['next_offset'])

    def test_the_service_serves_the_words_the_contract_declares(self):
        """LANGUAGE-POLICY §5: the screen consumes these pairs instead of hand-copying them."""
        contract = json.loads((REPO / 'design-lab' / 'config' / 'state-vocabularies.json')
                              .read_text(encoding='utf-8'))['planFeedback']
        _, listing = self._call('GET', self._feedback_path())
        self.assertEqual([w['value'] for w in listing['outcome_words']],
                         contract['outcomes'], 'the served outcome words drifted from the contract')
        self.assertEqual([w['label'] for w in listing['outcome_words']],
                         contract['outcomeLabels'])
        self.assertEqual([w['value'] for w in listing['dimension_verdict_words']],
                         contract['dimensionVerdicts'])

    def test_a_label_that_contradicts_its_own_verdict_cannot_be_stored(self):
        """Two independently valid fields must not be allowed to disagree.

        The writer derives the label from the verdict, so no normal path can produce this. The
        contract still refuses it because the screen prints the LABEL: a stored row whose verdict
        says DOES_NOT_MATCH while its label says 符合 would render the operator's complaint as a
        blessing, and 'the writer would never do that' protects nothing already on disk.
        """
        from design_lab.interop import load_schema, schema_errors
        schema = load_schema(plan_feedback._SCHEMA_PATH)
        _, written = self._call('POST', self._feedback_path(), feedback(
            dimensions=[{'name': '画幅', 'verdict': 'DOES_NOT_MATCH', 'note': None}]))
        record = written['feedback']
        self.assertEqual('不符合', record['dimensions'][0]['verdict_label'])
        self.assertEqual([], schema_errors(schema, record),
                         'the honest record the writer produced is not valid under its own contract')
        for tamper in ({'key': 'outcome_label', 'value': '符合', 'set': ('outcome', 'DOES_NOT_MATCH')},
                       {'key': 'verdict_label', 'value': '符合'}):
            bad = json.loads(json.dumps(record))
            if tamper.get('set'):
                bad['outcome'], bad[tamper['key']] = tamper['set'][1], tamper['value']
            else:
                bad['dimensions'][0]['verdict'] = 'DOES_NOT_MATCH'
                bad['dimensions'][0][tamper['key']] = tamper['value']
            problems = schema_errors(schema, bad)
            self.assertTrue(problems, f'{tamper["key"]} disagreed with its verdict and was '
                                      'accepted -- the contract has a hole')
            self.assertIn('was expected', ' '.join(problems))

    def test_the_histogram_is_computed_from_the_rows_the_page_lists(self):
        for outcome in ('MATCHES', 'MATCHES', 'PARTIALLY_MATCHES'):
            self._call('POST', self._feedback_path(), feedback(outcome=outcome, revision=1))
        _, listing = self._call('GET', self._feedback_path())
        counted = {}
        for record in listing['records']:
            counted[record['outcome']] = counted.get(record['outcome'], 0) + 1
        expected = {'MATCHES': 0, 'PARTIALLY_MATCHES': 0, 'DOES_NOT_MATCH': 0}
        expected.update(counted)
        self.assertEqual(expected, listing['outcome_histogram'],
                         'the summary does not match the rows it summarises')

    def test_an_empty_collection_says_nothing_was_recorded_without_inventing_a_zero_state(self):
        _, listing = self._call('GET', self._feedback_path())
        self.assertEqual(0, listing['total'])
        self.assertEqual([], listing['records'])
        self.assertIsNone(listing['latest'])

    def test_a_row_cannot_be_rewritten_or_withdrawn_underneath_a_reader(self):
        self._call('POST', self._feedback_path(), feedback())
        with closing(plan_feedback.connect(
                self.service.paths.database_path(self.service.database),
                project_root=self.service.paths.project_root)) as conn:
            with self.assertRaises(sqlite3.IntegrityError):
                conn.execute('UPDATE plan_feedback SET outcome = ? WHERE plan_id = ?',
                             ('NOT_USABLE', self.plan))
            conn.rollback()
            with self.assertRaises(sqlite3.IntegrityError):
                conn.execute('DELETE FROM plan_feedback WHERE plan_id = ?', (self.plan,))
            conn.rollback()
            rows = conn.execute('SELECT outcome FROM plan_feedback WHERE plan_id = ?',
                                (self.plan,)).fetchall()
            self.assertEqual(['MATCHES'], [row[0] for row in rows],
                             'the refused statements still moved the row')

    def test_paging_out_of_range_is_refused_at_the_right_layer(self):
        status, refused = self._call('GET', self._feedback_path() + '?limit=999')
        self.assertEqual(400, status, refused)
        self.assertEqual('PLAN_FEEDBACK_FILTER_MALFORMED', refused['error'])
        status, refused = self._call('GET', self._feedback_path() + '?offset=-2')
        self.assertEqual(400, status, refused)
        self.assertEqual('PLAN_FEEDBACK_OFFSET_INVALID', refused['error'])

    def test_a_report_on_an_unknown_plan_is_a_404_not_an_empty_history(self):
        stranger = 'aplan-' + 'c' * 32
        status, refused = self._call('POST',
                                     f'/api/projects/{self.project}/assistance-plans/'
                                     f'{stranger}/feedback', feedback())
        self.assertEqual(404, status, refused)
        self.assertEqual('ASSISTANCE_PLAN_NOT_FOUND', refused['error'])
        status, refused = self._call('GET',
                                     f'/api/projects/{self.project}/assistance-plans/'
                                     f'{stranger}/feedback')
        self.assertEqual(404, status, refused)


if __name__ == '__main__':
    unittest.main()
