# SPDX-License-Identifier: MIT
"""DL-KB-09: the target profile registry, measured at the HTTP boundary.

The card's acceptance is B3: an unknown entry may only export planning material that says it is
unverified, a known incompatibility is stated rather than faked away, the four provenance kinds
stay separate, and an entry nobody can verify keeps UNKNOWN instead of inferring that the desktop
has it. These tests drive the real routes rather than the store functions, because the sentence a
page can repeat is the answer it actually received.
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

from design_lab import target_profile                                # noqa: E402
from design_lab.http_service import make_server                      # noqa: E402
from design_lab.service import ProjectService                        # noqa: E402
from design_lab.target_profile import load_seeds                     # noqa: E402

DRAFT_BODY = {
    'software': 'Owner 的草稿目标', 'agent': None, 'model': None, 'provider': None,
    'version': None, 'entry': 'DESKTOP_CLIENT', 'task_mode': '海报排版',
    'actor': 'dtalex66', 'source_ref': None,
    'fields': {'input_modality': {'state': 'DOCUMENTED', 'value': '文本',
                                  'provenance': 'USER_FEEDBACK', 'source': 'owner 口述'}},
}


def profile_id_for(profile_key: str) -> str:
    return target_profile._seed_id(profile_key)


class TargetProfileTests(unittest.TestCase):
    def setUp(self):
        os.environ.pop('PROJECT_LOCAL_ROOT', None)
        self.base = Path(tempfile.mkdtemp(dir=REPO / '.project-local' / 'task-runtime'))
        self.root = self.base / 'project'
        self.root.mkdir()
        (self.root / 'AGENTS.md').write_text('# target profile fixture', encoding='utf-8')
        self.token = secrets.token_hex(32)
        self._serve(ProjectService(self.root))

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

    def _list(self):
        status, body = self._call('GET', '/api/target-profiles')
        self.assertEqual(200, status, body)
        return body

    def _by_key(self, prefix):
        return next(p for p in self._list()['profiles'] if p['profile_key'].startswith(prefix))

    # -- the config, not the database, owns the seeded rows ---------------------------

    def test_seeded_profiles_are_served_from_the_tracked_config_with_no_database_copy(self):
        listing = self._list()
        seeds = load_seeds()
        self.assertEqual(len(seeds), listing['total'],
                         'a seeded profile went missing, or a draft was counted as a seed')
        for profile in listing['profiles']:
            if profile['origin'] == 'SEEDED':
                self.assertNotIn('revision', profile,
                                 'a seeded row was read out of a table it is not stored in')
                self.assertEqual(profile_id_for(profile['profile_key']), profile['profile_id'],
                                 'a seeded id was minted rather than derived from its own key')
        self.assertEqual({'SEEDED'}, {p['origin'] for p in listing['profiles']})

    def test_the_config_refuses_to_describe_a_capability_nobody_read_without_a_reason(self):
        """The file I edit is itself under test: an empty cell has to say why it is empty."""
        seeds = load_seeds()
        measured = [(p['profile_key'], name) for p in seeds
                    for name, field in p['fields'].items()
                    if field['provenance'] == 'PROJECT_MEASURED']
        self.assertEqual([], measured,
                         'no external product or model was run this round')
        for profile in seeds:
            for name, field in profile['fields'].items():
                if field['state'] == 'UNKNOWN':
                    self.assertTrue((field.get('reason') or '').strip(),
                                    f'{profile["profile_key"]}.{name} is UNKNOWN silently')
                if field['state'] == 'DOCUMENTED' and field['provenance'] == 'OFFICIAL_DOC':
                    self.assertTrue(field['source'].strip(), 'a documented claim cites nothing')
                    self.assertRegex(field['observed_at'], r'^\d{4}-\d{2}-\d{2}$',
                                     'a documented claim names no day it was read')

    def test_a_null_axis_in_the_config_states_its_own_reason_and_not_the_stores_fallback(self):
        """07 line 29: 未知可空并解释原因，不能自动补支持.

        The store supplies a generic sentence for a draft that says nothing; a seeded profile may
        not lean on that, because "the vendor page does not describe an Agent form" and "nobody
        filled this in" are different facts and only the first one is worth reading later.
        """
        axes = ('software', 'agent', 'model', 'provider', 'version', 'entry', 'task_mode')
        silent = []
        for profile in load_seeds():
            for axis in axes:
                if profile.get(axis) is None and not (profile.get(f'{axis}_reason') or '').strip():
                    silent.append((profile['profile_key'], axis))
        self.assertEqual([], silent, 'a seeded null axis explains nothing')

    def test_an_unreached_entry_carries_its_failed_attempts_and_stays_unknown(self):
        meshy = self._by_key('meshy')
        self.assertEqual('UNREACHED', meshy['support_state'])
        self.assertEqual(4, len(meshy['reach_attempts']),
                         'the registry says it tried and did not reach the host -- show the tries')
        unknown = [name for name, field in meshy['fields'].items()
                   if field['state'] == 'UNKNOWN']
        self.assertGreaterEqual(len(unknown), 9,
                                f'an unreachable entry documented {len(unknown)} fields')
        self.assertEqual('UNSTATED', meshy['axes']['entry'],
                         'a URL path is not an entry point; nothing was read to name one')

    def test_a_documented_incompatibility_is_kept_in_the_vendors_own_words(self):
        flux = self._by_key('flux2')
        negative = flux['fields']['negative_input']
        self.assertEqual('DOCUMENTED', negative['state'])
        self.assertIn('does not support', negative['quote'])
        self.assertNotEqual('UNKNOWN', negative['state'],
                            'a documented "no" is not the same fact as an unread "who knows"')

    # -- the vocabulary the panel is built from --------------------------------------

    def test_axes_serve_the_two_lists_the_pack_agrees_on_and_counts_measurement_as_zero(self):
        status, axes = self._call('GET', '/api/target-profile-axes')
        self.assertEqual(200, status, axes)
        self.assertEqual([f['key'] for f in axes['capability_fields']],
                         list(target_profile.CAPABILITY_FIELDS))
        self.assertEqual([a['key'] for a in axes['axes']], list(target_profile.AXIS_FIELDS))
        self.assertEqual(5, len(axes['provenance_kinds']))
        self.assertEqual(0, axes['measured_fields'],
                         'the count the panel shows for 本项目实测 must be read from the service')
        self.assertFalse(axes['executable'])

    # -- a draft is intent, not evidence ---------------------------------------------

    def test_a_draft_is_stored_marked_unverified_and_read_back_after_a_restart(self):
        status, written = self._call('POST', '/api/target-profiles', DRAFT_BODY)
        self.assertEqual(201, status, written)
        profile = written['profile']
        self.assertEqual('USER_DRAFT', profile['support_state'])
        self.assertTrue(written['stored'])
        self.assertEqual('UNUSED', profile['source_ref'],
                         'an absent external id is the literal UNUSED, never one this service made up')
        self.assertFalse(profile['executable'])
        self.assertIsNone(profile['external_run_record'])
        self.assertTrue(written['claims_not_made'])
        # A field the caller left out is stored as UNKNOWN rather than vanishing from the document.
        self.assertEqual('UNKNOWN', profile['fields']['ranges']['state'])
        self.assertTrue(profile['axis_reasons']['agent'],
                        'a null axis must explain why it is null')

        self._restart()
        again = self._call('GET', f'/api/target-profiles/{profile["profile_id"]}')[1]
        self.assertEqual(profile, {k: v for k, v in again.items()
                                   if k not in ('revision', 'created_at', 'created_by')},
                         'the draft read back differs from the draft that was written')
        self.assertEqual(profile['content_sha256'], again['content_sha256'])

    def test_a_draft_cannot_write_itself_as_a_measurement(self):
        body = json.loads(json.dumps(DRAFT_BODY))
        body['fields']['ranges'] = {'state': 'DOCUMENTED', 'value': '60 秒',
                                    'provenance': 'PROJECT_MEASURED'}
        status, refused = self._call('POST', '/api/target-profiles', body)
        self.assertEqual(409, status, refused)
        self.assertEqual('TARGET_PROFILE_MEASUREMENT_NOT_AVAILABLE', refused['error'])

    def test_a_draft_cannot_name_a_column_the_contract_does_not_have(self):
        status, refused = self._call('POST', '/api/target-profiles',
                                     dict(DRAFT_BODY, desktop_confirmed=True))
        self.assertEqual(400, status, refused)
        self.assertEqual('INVALID_PROJECT_FIELDS', refused['error'],
                         'the route compares key sets, so an extra axis is refused not dropped')
        body = json.loads(json.dumps(DRAFT_BODY))
        body['fields']['invented_field'] = {'state': 'DOCUMENTED', 'value': 'x',
                                            'provenance': 'USER_FEEDBACK', 'source': 's'}
        status, refused = self._call('POST', '/api/target-profiles', body)
        self.assertEqual(400, status, refused)
        self.assertEqual('TARGET_PROFILE_FIELD_NOT_IN_CONTRACT', refused['error'])

    def test_an_unknown_profile_id_says_what_a_profile_can_be(self):
        status, refused = self._call('GET', f'/api/target-profiles/{profile_id_for("nope")}')
        self.assertEqual(404, status, refused)
        self.assertEqual('TARGET_PROFILE_NOT_FOUND', refused['error'])
        self.assertIn('seeded', refused['detail'])

    # -- validation reports the profile, never a go-ahead ----------------------------

    def test_validation_of_an_unreached_entry_returns_unknown_without_granting_execution(self):
        meshy = self._by_key('meshy')
        status, answered = self._call(
            'POST', f'/api/target-profiles/{meshy["profile_id"]}/validate',
            {'dimensions': {'modality': 'image', 'asset_count': 3}})
        self.assertEqual(200, status, answered)
        self.assertFalse(answered['executable'])
        for verdict in answered['verdicts']:
            self.assertEqual('UNKNOWN', verdict['verdict'])
            self.assertFalse(verdict['grants_execution'])
            self.assertTrue(verdict['reason'])
        self.assertEqual('UNKNOWN', meshy['fields']['input_modality']['state'])

    def test_validation_reports_a_documented_no_as_a_no(self):
        flux = self._by_key('flux2')
        _, answered = self._call(
            'POST', f'/api/target-profiles/{flux["profile_id"]}/validate',
            {'dimensions': {'negative_input': 'no people', 'parameter': 'guidance'}})
        pairs = {v['dimension']: v for v in answered['verdicts']}
        self.assertEqual('DOCUMENTED_NOT_SUPPORT', pairs['negative_input']['verdict'])
        self.assertEqual('OFFICIAL_DOC', pairs['negative_input']['provenance'])
        self.assertFalse(any(v['grants_execution'] for v in answered['verdicts']),
                         'no verdict may read as a go-ahead')

    def test_a_draft_cannot_be_validated_as_if_it_were_documented(self):
        _, written = self._call('POST', '/api/target-profiles', DRAFT_BODY)
        draft = written['profile']
        _, answered = self._call(
            'POST', f'/api/target-profiles/{draft["profile_id"]}/validate',
            {'dimensions': {'modality': 'text'}})
        self.assertEqual('USER_DRAFT', answered['support_state'])
        self.assertEqual('DOCUMENTED_SUPPORT', answered['verdicts'][0]['verdict'])
        self.assertEqual('USER_FEEDBACK', answered['verdicts'][0]['provenance'],
                         'the provenance a verdict carries is the draft author\'s word, '
                         'not an official claim')

    def test_the_histogram_a_page_reads_comes_from_the_same_bytes_as_the_profiles(self):
        listing = self._list()
        counted = {kind: 0 for kind in target_profile.PROVENANCE_KINDS}
        for profile in listing['profiles']:
            for field in profile['fields'].values():
                counted[field['provenance']] = counted.get(field['provenance'], 0) + 1
        self.assertEqual(counted, listing['provenance_histogram'],
                         'the summary the panel columns does not match the rows it summarises')
        self.assertEqual(0, listing['provenance_histogram']['PROJECT_MEASURED'])
        self.assertFalse(listing['executable'])

    def test_an_out_of_range_page_is_refused_loudly_at_the_right_layer(self):
        status, refused = self._call('GET', '/api/target-profiles?limit=500')
        self.assertEqual(400, status, refused)
        self.assertEqual('TARGET_PROFILE_FILTER_MALFORMED', refused['error'],
                         'the cap is stated where the query is parsed, not left to the contract')
        status, refused = self._call('GET', '/api/target-profiles?limit=abc')
        self.assertEqual(400, status, refused)
        self.assertEqual('TARGET_PROFILE_FILTER_MALFORMED', refused['error'])
        status, refused = self._call('GET', '/api/target-profiles?offset=-1')
        self.assertEqual(400, status, refused)
        self.assertEqual('TARGET_PROFILE_OFFSET_INVALID', refused['error'])

    def test_a_draft_revision_cannot_be_rewritten_or_withdrawn_underneath_a_reader(self):
        _, written = self._call('POST', '/api/target-profiles', DRAFT_BODY)
        profile_id = written['profile']['profile_id']
        with closing(target_profile.connect(self.service.paths.database_path(
                self.service.database), project_root=self.service.paths.project_root)) as conn:
            with self.assertRaises(sqlite3.IntegrityError):
                conn.execute('UPDATE target_profile_draft SET support_state = ?'
                             ' WHERE profile_id = ?', ('DOCUMENTED_CLAIM', profile_id))
            conn.rollback()
            with self.assertRaises(sqlite3.IntegrityError):
                conn.execute('DELETE FROM target_profile_draft WHERE profile_id = ?',
                             (profile_id,))
            conn.rollback()
            rows = conn.execute('SELECT support_state FROM target_profile_draft'
                                ' WHERE profile_id = ?', (profile_id,)).fetchall()
            self.assertEqual([('USER_DRAFT',)], [(r[0],) for r in rows],
                             'the refused statements still moved the row')


if __name__ == '__main__':
    unittest.main()
