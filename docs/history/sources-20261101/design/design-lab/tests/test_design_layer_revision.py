# SPDX-License-Identifier: MIT
"""F-2a design-layer revisions: immutable content + an append-only event log.

Real loopback HTTP contract tests plus direct database assertions. The batch that
added ``design-lab-state-design-layer-v3.sql`` claimed the design layer had
"version-ready" columns (version / superseded_by) that nothing wrote: every path
inserted version=1 and superseded_by stayed NULL. These tests pin the revision
model that closes that gap, at the level the claim lives at (persisted bytes,
not HTTP codes alone):

* a revision APPENDS a new row (version = old + 1) and moves only the old row's
  ``superseded_by`` pointer -- every content column of the retired row keeps its
  original bytes, including ``spec_sha256`` and the JSON content columns;
* every write path appends its typed event in the same transaction, and
  ``direction-chosen`` carries the direction it replaced (null when it is the
  first choice), so the choice history is readable without reconstructing it;
* the event log is append-only: a repeated ``event_id`` fails closed instead of
  overwriting, and the schema's triggers abort UPDATE/DELETE of an event;
* idempotency is unchanged: a replayed key returns the SAME new identity and
  appends nothing, a key reused with different content is a 409 conflict;
* fail-closed faces: unknown id, foreign project, already-superseded version.

Nothing here claims an E3 host run or an E4 jury acceptance.
"""
import base64
import hashlib
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
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]

# The columns that carry the record's CONTENT (and its identity/ordering). A
# revision may move superseded_by and, for a chosen direction, the materialized
# chosen/actor state -- it may never rewrite any of these.
BRIEF_CONTENT_COLUMNS = ('brief_id', 'operation_id', 'project_id', 'title', 'goals_json',
                         'constraints_json', 'reference_asset_ids', 'spec_sha256', 'version',
                         'created_at')
DIRECTION_CONTENT_COLUMNS = ('direction_id', 'operation_id', 'project_id', 'brief_id', 'title',
                             'style_notes_json', 'color_mood', 'typography_mood', 'spec_sha256',
                             'version', 'created_at')


class RevisionTestCase(unittest.TestCase):
    """Loopback HTTP fixture shared by the revision tests."""

    def setUp(self):
        sys.path.insert(0, str(ROOT / 'src'))
        self.addCleanup(sys.path.remove, str(ROOT / 'src'))
        parent = ROOT / '.project-local' / 'task-runtime' / 'design-layer-revision-tests'
        parent.mkdir(parents=True, exist_ok=True)
        tmp = tempfile.TemporaryDirectory(dir=parent)
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        (self.root / 'AGENTS.md').write_text('# synthetic design-layer revision project',
                                             encoding='utf-8')

        from design_lab.service import ProjectService
        from design_lab.http_service import make_server
        local_env = patch.dict(os.environ, {'PROJECT_LOCAL_ROOT': str(self.root / '.project-local')})
        local_env.start()
        self.addCleanup(local_env.stop)
        self.service = ProjectService(str(self.root))
        self.token = secrets.token_hex(32)
        self.server = make_server(self.service, self.token, port=0)
        self.port = self.server.server_address[1]
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

        def _stop_server(self=self):
            self.server.shutdown()
            self.thread.join()
            self.server.server_close()
        self.addCleanup(_stop_server)

    # -- transport ---------------------------------------------------------
    def request(self, method='GET', path='/api/projects', body=None, headers=None):
        defaults = {'Authorization': 'Bearer ' + self.token,
                    'Host': f'127.0.0.1:{self.port}',
                    'Origin': f'http://127.0.0.1:{self.port}',
                    'Sec-Fetch-Site': 'same-origin'}
        if body is not None:
            defaults['Content-Type'] = 'application/json'
        defaults.update(headers or {})
        raw = json.dumps(body).encode() if body is not None else None
        conn = http.client.HTTPConnection('127.0.0.1', self.port, timeout=5)
        try:
            conn.request(method, path, body=raw, headers=defaults)
            resp = conn.getresponse()
            return resp.status, json.loads(resp.read())
        finally:
            conn.close()

    def key(self, n):
        return hashlib.sha256(n.encode()).hexdigest()

    # -- fixtures ----------------------------------------------------------
    def _project(self, name='F-2a revision'):
        status, body = self.request('POST', '/api/projects', {'name': name})
        self.assertEqual(status, 201)
        return body['project']['id']

    def _import_asset(self, pid, key='imp'):
        signature = b'\x89PNG\r\n\x1a\n'
        import struct
        import zlib

        def chunk(tag, data):
            out = struct.pack('>I', len(data)) + tag + data
            return out + struct.pack('>I', zlib.crc32(tag + data) & 0xFFFFFFFF)
        png = (signature + chunk(b'IHDR', struct.pack('>IIBBBBB', 1, 1, 8, 6, 0, 0, 0))
               + chunk(b'IDAT', zlib.compress(b'\x00\xff\x00\x00\xff')) + chunk(b'IEND', b''))
        status, body = self.request('POST', f'/api/projects/{pid}/assets',
                                    {'content_base64': base64.b64encode(png).decode('ascii'),
                                     'idempotency_key': self.key(key)})
        self.assertEqual(status, 201)
        return body['asset']['id']

    def _brief(self, pid, title='Autumn', key='b1', goals=('modern',), constraints=None,
               references=None):
        status, body = self.request('POST', f'/api/projects/{pid}/briefs', {
            'title': title, 'goals': list(goals), 'constraints': constraints,
            'reference_asset_ids': list(references or []), 'idempotency_key': self.key(key)})
        self.assertEqual(status, 201)
        return body['brief']

    def _direction(self, pid, bid, title='Warm', key='d1'):
        status, body = self.request('POST', f'/api/projects/{pid}/directions', {
            'brief_id': bid, 'title': title, 'style_notes': ['soft'],
            'color_mood': 'warm', 'typography_mood': 'sans',
            'idempotency_key': self.key(key)})
        self.assertEqual(status, 201)
        return body['direction']

    def _choose(self, pid, did, key='c1', actor='ALEX'):
        status, body = self.request('POST', f'/api/projects/{pid}/directions/{did}/choose',
                                    {'actor': actor, 'actor_kind': 'human',
                                     'idempotency_key': self.key(key)})
        self.assertEqual(status, 200)
        return body['direction']

    def _bind(self, pid, did, name='nebula-tech', key='s1'):
        return self.request('POST', f'/api/projects/{pid}/directions/{did}/bind',
                            {'design_system_name': name, 'idempotency_key': self.key(key)})

    def _revise_brief(self, pid, bid, *, key, title='Autumn v2', goals=('modern', 'quiet'),
                      constraints='keep', references=None):
        return self.request('POST', f'/api/projects/{pid}/briefs/{bid}/revisions', {
            'title': title, 'goals': list(goals), 'constraints': constraints,
            'reference_asset_ids': list(references or []), 'idempotency_key': self.key(key)})

    def _revise_direction(self, pid, did, *, key, title='Warm v2', style_notes=('soft', 'calm'),
                          color_mood='warmer', typography_mood='serif'):
        return self.request('POST', f'/api/projects/{pid}/directions/{did}/revisions', {
            'title': title, 'style_notes': list(style_notes), 'color_mood': color_mood,
            'typography_mood': typography_mood, 'idempotency_key': self.key(key)})

    # -- direct database reads --------------------------------------------
    def _connect(self):
        conn = sqlite3.connect(str(self.service.database))
        conn.row_factory = sqlite3.Row
        return conn

    def _raw(self, table, id_column, row_id):
        conn = self._connect()
        try:
            row = conn.execute(f"SELECT * FROM {table} WHERE {id_column}=?",
                               (row_id,)).fetchone()
            return dict(row) if row is not None else None
        finally:
            conn.close()

    def _events(self, pid):
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT kind, brief_id, direction_id, binding_id, payload_json, actor, actor_kind"
                " FROM design_layer_event WHERE project_id=? ORDER BY created_at, rowid",
                (pid,)).fetchall()
        finally:
            conn.close()
        return [{**dict(row), 'payload': json.loads(row['payload_json'])} for row in rows]

    def _kinds(self, pid):
        return [event['kind'] for event in self._events(pid)]

    # -- assertions --------------------------------------------------------
    def assertContentUnchanged(self, table, id_column, row_id, before, columns):
        after = self._raw(table, id_column, row_id)
        self.assertIsNotNone(after)
        for column in columns:
            self.assertEqual(after[column], before[column],
                             f'{table}.{column} changed on the retired row')

    def assertEventKinds(self, pid, expected):
        self.assertEqual(self._kinds(pid), expected)


class BriefRevisionTests(RevisionTestCase):
    def test_revision_appends_version_and_retires_the_parent_by_pointer_only(self):
        pid = self._project()
        asset = self._import_asset(pid)
        brief = self._brief(pid, references=[asset])
        before = self._raw('design_brief', 'brief_id', brief['brief_id'])

        status, body = self._revise_brief(pid, brief['brief_id'], key='r1',
                                          references=[asset])
        self.assertEqual(status, 201)
        revised = body['brief']
        # A new identity at the next version; the parent keeps its own id.
        self.assertNotEqual(revised['brief_id'], brief['brief_id'])
        self.assertEqual(revised['version'], 2)
        self.assertEqual(revised['title'], 'Autumn v2')
        self.assertEqual(revised['reference_asset_ids'], [asset])
        self.assertEqual(revised['superseded_by'], None)
        self.assertNotEqual(revised['spec_sha256'], brief['spec_sha256'])

        # The retired row: pointer moved, content bytes untouched.
        after = self._raw('design_brief', 'brief_id', brief['brief_id'])
        self.assertEqual(after['superseded_by'], revised['brief_id'])
        self.assertContentUnchanged('design_brief', 'brief_id', brief['brief_id'], before,
                                    BRIEF_CONTENT_COLUMNS)
        self.assertEqual(after['goals_json'], before['goals_json'])
        self.assertEqual(after['spec_sha256'], before['spec_sha256'])

        # Readback is unchanged in shape and now shows both versions.
        layer = self.request(path=f'/api/projects/{pid}/design-layer')[1]['design_layer']
        self.assertEqual(sorted(b['version'] for b in layer['briefs']), [1, 2])
        self.assertEqual(self.request(path=f"/api/projects/{pid}/briefs/{revised['brief_id']}")[0], 200)

    def test_lineage_reads_the_chain_from_any_member(self):
        pid = self._project()
        brief = self._brief(pid)
        v2 = self._revise_brief(pid, brief['brief_id'], key='r1')[1]['brief']
        v3 = self._revise_brief(pid, v2['brief_id'], key='r2', title='Autumn v3')[1]['brief']
        self.assertEqual([brief['version'], v2['version'], v3['version']], [1, 2, 3])

        for path in (f"/api/design-briefs/{brief['brief_id']}/lineage",
                     f"/api/design-briefs/{v2['brief_id']}/lineage",
                     f"/api/design-briefs/{v3['brief_id']}/lineage",
                     f"/api/projects/{pid}/briefs/{brief['brief_id']}/lineage"):
            status, body = self.request(path=path)
            self.assertEqual(status, 200, path)
            lineage = body['lineage']
            # Any member resolves to the same full chain, oldest first.
            self.assertEqual([v['version'] for v in lineage['versions']], [1, 2, 3])
            self.assertEqual(lineage['root_id'], brief['brief_id'])
            self.assertEqual(lineage['live_id'], v3['brief_id'])
            self.assertEqual([v['superseded_by'] for v in lineage['versions']],
                             [v2['brief_id'], v3['brief_id'], None])
            self.assertEqual([v['brief_id'] for v in lineage['versions']],
                             [brief['brief_id'], v2['brief_id'], v3['brief_id']])

    def test_replayed_key_returns_the_same_identity_and_appends_nothing(self):
        pid = self._project()
        brief = self._brief(pid)
        first = self._revise_brief(pid, brief['brief_id'], key='r1')
        second = self._revise_brief(pid, brief['brief_id'], key='r1')
        self.assertEqual(first[0], 201)
        self.assertEqual(second[0], 201)
        self.assertEqual(first[1]['brief'], second[1]['brief'])
        # One revision happened: one new row, one event, one live tip.
        self.assertEqual(self._kinds(pid), ['brief-created', 'brief-revised'])
        self.assertEqual(len(self.request(path=f'/api/projects/{pid}/briefs')[1]['briefs']), 2)

    def test_reused_key_with_different_content_is_a_conflict(self):
        pid = self._project()
        brief = self._brief(pid)
        self._revise_brief(pid, brief['brief_id'], key='r1')
        status, body = self._revise_brief(pid, brief['brief_id'], key='r1', title='Other')
        self.assertEqual(status, 409)
        self.assertEqual(body['error'], 'IDEMPOTENCY_CONFLICT')
        self.assertEqual(self._kinds(pid), ['brief-created', 'brief-revised'])

    def test_revision_fails_closed_on_unknown_foreign_and_stale_targets(self):
        owner = self._project()
        other = self._project('Other')
        brief = self._brief(owner)
        unknown = 'brief-' + '0' * 32

        # Unknown id, both route shapes: 404, and nothing is written.
        status, body = self._revise_brief(owner, unknown, key='x1')
        self.assertEqual((status, body['error']), (404, 'BRIEF_NOT_FOUND'))
        self.assertEqual(self.request(
            path=f'/api/design-briefs/{unknown}/lineage')[0], 404)
        # Cross-project: the project-scoped route names the foreign project.
        status, body = self.request('POST', f"/api/projects/{other}/briefs/{brief['brief_id']}/revisions",
                                    {'title': 'T', 'goals': ['g'], 'constraints': None,
                                     'reference_asset_ids': [], 'idempotency_key': self.key('x2')})
        self.assertEqual((status, body['error']), (404, 'BRIEF_NOT_FOUND'))
        self.assertEqual(self.request(
            path=f"/api/projects/{other}/briefs/{brief['brief_id']}/lineage")[0], 404)
        # Unauthenticated revision is refused and creates nothing.
        self.assertEqual(self.request('POST', f"/api/projects/{owner}/briefs/{brief['brief_id']}/revisions",
                                      {'title': 'T', 'goals': ['g'], 'constraints': None,
                                       'reference_asset_ids': [], 'idempotency_key': self.key('x3')},
                                      headers={'Authorization': ''})[0], 401)

        # Revising a version that is no longer live would fork the chain -> 409,
        # and the chain is untouched (still one version, one event).
        self._revise_brief(owner, brief['brief_id'], key='r1')
        status, body = self._revise_brief(owner, brief['brief_id'], key='r2')
        self.assertEqual((status, body['error']), (409, 'STALE_REVISION'))
        self.assertEqual(self._kinds(owner), ['brief-created', 'brief-revised'])
        self.assertEqual(len(self.request(path=f'/api/projects/{owner}/briefs')[1]['briefs']), 2)


class DirectionRevisionTests(RevisionTestCase):
    def test_chosen_direction_revision_carries_the_choice_and_keeps_content_bytes(self):
        pid = self._project()
        brief = self._brief(pid)
        direction = self._direction(pid, brief['brief_id'])
        self._choose(pid, direction['direction_id'], key='c1', actor='ALEX')
        before = self._raw('design_direction', 'direction_id', direction['direction_id'])

        status, body = self._revise_direction(pid, direction['direction_id'], key='dr1')
        self.assertEqual(status, 201)
        revised = body['direction']
        self.assertEqual(revised['version'], 2)
        self.assertNotEqual(revised['direction_id'], direction['direction_id'])
        self.assertEqual(revised['brief_id'], brief['brief_id'])
        # The human choice follows the lineage instead of being lost.
        self.assertTrue(revised['chosen'])
        self.assertEqual(revised['actor'], 'ALEX')
        self.assertEqual(revised['actor_kind'], 'human')

        after = self._raw('design_direction', 'direction_id', direction['direction_id'])
        self.assertEqual(after['superseded_by'], revised['direction_id'])
        self.assertContentUnchanged('design_direction', 'direction_id', direction['direction_id'],
                                    before, DIRECTION_CONTENT_COLUMNS)
        self.assertEqual(after['style_notes_json'], before['style_notes_json'])
        self.assertEqual(after['spec_sha256'], before['spec_sha256'])
        # chosen/actor are materialized state, not content: the retired row
        # releases them, and the brief still holds exactly ONE live choice.
        self.assertEqual((after['chosen'], after['actor']), (0, None))
        layer = self.request(path=f'/api/projects/{pid}/design-layer')[1]['design_layer']
        self.assertEqual(layer['chosen_direction']['direction_id'], revised['direction_id'])
        self.assertEqual(sorted(d['version'] for d in layer['directions']), [1, 2])

    def test_unchosen_direction_revision_does_not_touch_materialized_state(self):
        pid = self._project()
        brief = self._brief(pid)
        direction = self._direction(pid, brief['brief_id'])
        before = self._raw('design_direction', 'direction_id', direction['direction_id'])
        revised = self._revise_direction(pid, direction['direction_id'], key='dr1')[1]['direction']
        self.assertFalse(revised['chosen'])
        after = self._raw('design_direction', 'direction_id', direction['direction_id'])
        self.assertEqual((after['chosen'], after['actor'], after['actor_kind']),
                         (before['chosen'], before['actor'], before['actor_kind']))
        self.assertEqual(after['superseded_by'], revised['direction_id'])
        self.assertContentUnchanged('design_direction', 'direction_id', direction['direction_id'],
                                    before, DIRECTION_CONTENT_COLUMNS)

    def test_direction_lineage_and_route_guards(self):
        pid = self._project()
        other = self._project('Other')
        brief = self._brief(pid)
        direction = self._direction(pid, brief['brief_id'])
        v2 = self._revise_direction(pid, direction['direction_id'], key='dr1',
                                    title='Warm v3')[1]['direction']

        for path in (f"/api/design-directions/{direction['direction_id']}/lineage",
                     f"/api/design-directions/{v2['direction_id']}/lineage",
                     f"/api/projects/{pid}/directions/{direction['direction_id']}/lineage"):
            status, body = self.request(path=path)
            self.assertEqual(status, 200, path)
            lineage = body['lineage']
            self.assertEqual([v['version'] for v in lineage['versions']], [1, 2])
            self.assertEqual(lineage['live_id'], v2['direction_id'])
            self.assertEqual(lineage['versions'][0]['superseded_by'], v2['direction_id'])
            self.assertIsNone(lineage['versions'][1]['superseded_by'])
            self.assertEqual(lineage['versions'][0]['style_notes'], ['soft'])
            self.assertEqual(lineage['versions'][1]['style_notes'], ['soft', 'calm'])
        # Unknown id -> 404; foreign project -> 404 (cross-project boundary).
        self.assertEqual(self.request(
            path='/api/design-directions/direction-' + '0' * 32 + '/lineage')[0], 404)
        self.assertEqual(self.request(
            path=f"/api/projects/{other}/directions/{direction['direction_id']}/lineage")[0], 404)
        status, body = self.request(
            'POST', f"/api/projects/{other}/directions/{direction['direction_id']}/revisions",
            {'title': 'T', 'style_notes': [], 'color_mood': None, 'typography_mood': None,
             'idempotency_key': self.key('drx')})
        self.assertEqual((status, body['error']), (404, 'DIRECTION_NOT_FOUND'))


class EventLogTests(RevisionTestCase):
    def test_full_slice_appends_the_expected_kind_sequence_with_payloads(self):
        pid = self._project()
        brief = self._brief(pid)
        dir_a = self._direction(pid, brief['brief_id'], title='A', key='da')
        dir_b = self._direction(pid, brief['brief_id'], title='B', key='db')
        self._choose(pid, dir_a['direction_id'], key='ca', actor='A')
        self._choose(pid, dir_b['direction_id'], key='cb', actor='B')
        first_binding = self._bind(pid, dir_b['direction_id'], 'nebula-tech', key='s1')[1]['binding']
        rebound = self._bind(pid, dir_b['direction_id'], 'uiux-commercial-light', key='s2')[1]['binding']
        # A rebind is a new version of the contract; the read model picks it up.
        layer = self.request(path=f'/api/projects/{pid}/design-layer')[1]['design_layer']
        self.assertEqual(layer['active_binding']['binding_id'], rebound['binding_id'])
        self.assertEqual(layer['active_binding']['version'], 2)
        self.assertEqual(rebound['version'], 2)
        self.assertEqual(first_binding['version'], 1)

        revised_brief = self._revise_brief(pid, brief['brief_id'], key='r1')[1]['brief']
        revised_direction = self._revise_direction(pid, dir_b['direction_id'], key='dr1')[1]['direction']

        self.assertEqual(self._kinds(pid), [
            'brief-created', 'direction-created', 'direction-created',
            'direction-chosen', 'direction-unchosen', 'direction-chosen',
            'binding-created', 'binding-rebound', 'brief-revised', 'direction-revised'])

        events = self._events(pid)
        created_brief = events[0]
        self.assertEqual(created_brief['brief_id'], brief['brief_id'])
        self.assertEqual(created_brief['payload'],
                         {'brief_id': brief['brief_id'], 'version': 1,
                          'spec_sha256': brief['spec_sha256']})
        self.assertEqual(events[1]['kind'], events[2]['kind'])
        self.assertEqual([event['direction_id'] for event in events[1:3]],
                         [dir_a['direction_id'], dir_b['direction_id']])

        # The FIRST choice replaced nothing; the SECOND one records A as the
        # previous chosen direction, and A is de-selected by its own event.
        first_choice, unchosen, second_choice = events[3], events[4], events[5]
        self.assertEqual(first_choice['payload']['previous_chosen_direction_id'], None)
        self.assertEqual(first_choice['payload']['direction_id'], dir_a['direction_id'])
        self.assertEqual(first_choice['payload']['actor_kind'], 'human')
        self.assertEqual(first_choice['actor'], 'A')
        self.assertEqual(unchosen['payload']['direction_id'], dir_a['direction_id'])
        self.assertEqual(unchosen['payload']['unchosen_by_direction_id'], dir_b['direction_id'])
        self.assertEqual(second_choice['payload']['previous_chosen_direction_id'],
                         dir_a['direction_id'])
        self.assertEqual(second_choice['payload']['direction_id'], dir_b['direction_id'])

        # A first binding is created; the second replaces it and names it.
        self.assertEqual(events[6]['payload']['replaced_binding_id'], None)
        self.assertEqual(events[6]['payload']['binding_id'], first_binding['binding_id'])
        self.assertEqual(events[7]['payload']['replaced_binding_id'], first_binding['binding_id'])
        self.assertEqual(events[7]['payload']['binding_id'], rebound['binding_id'])
        self.assertEqual(events[7]['payload']['version'], 2)

        # The revisions name both ends of the edge and the new version.
        self.assertEqual(events[8]['payload']['old_id'], brief['brief_id'])
        self.assertEqual(events[8]['payload']['new_id'], revised_brief['brief_id'])
        self.assertEqual(events[8]['payload']['version'], 2)
        self.assertEqual(events[9]['payload']['old_id'], dir_b['direction_id'])
        self.assertEqual(events[9]['payload']['new_id'], revised_direction['direction_id'])
        self.assertEqual(events[9]['payload']['chosen_moved'], True)
        self.assertEqual(events[9]['payload']['previous_chosen_direction_id'],
                         dir_b['direction_id'])

        # A revised CHOSEN direction is a new identity, and a binding stays
        # attached to the version it was bound to (its row is append-only), so
        # the contract must be bound again before it is active again. This is the
        # documented consequence of an append-only binding, not a silent rebind.
        layer = self.request(path=f'/api/projects/{pid}/design-layer')[1]['design_layer']
        self.assertEqual(layer['chosen_direction']['direction_id'],
                         revised_direction['direction_id'])
        self.assertIsNone(layer['active_binding'])
        self.assertEqual(sorted(b['binding_id'] for b in layer['bindings']),
                         sorted([first_binding['binding_id'], rebound['binding_id']]))

    def test_repeated_choose_appends_no_second_choice_event(self):
        pid = self._project()
        brief = self._brief(pid)
        direction = self._direction(pid, brief['brief_id'])
        for _ in range(3):
            self._choose(pid, direction['direction_id'], key='c1', actor='ALEX')
        self.assertEqual(self._kinds(pid),
                         ['brief-created', 'direction-created', 'direction-chosen'])

    def test_event_ids_are_unique_and_every_write_appends_one(self):
        pid = self._project()
        brief = self._brief(pid)

        def event_ids():
            conn = self._connect()
            try:
                return [row[0] for row in conn.execute(
                    "SELECT event_id FROM design_layer_event WHERE project_id=?"
                    " ORDER BY created_at, rowid", (pid,))]
            finally:
                conn.close()

        first = event_ids()
        self.assertEqual(len(first), 1)
        self.assertTrue(all(isinstance(event_id, str) and event_id for event_id in first))
        self.assertEqual(len(first), len(set(first)))
        self._revise_brief(pid, brief['brief_id'], key='r1')
        second = event_ids()
        # An append, never a replacement: one new event id, the old one intact.
        self.assertEqual(len(second), 2)
        self.assertEqual(second[:1], first)
        self.assertEqual(len(second), len(set(second)))

    def test_duplicate_event_id_fails_closed_instead_of_overwriting(self):
        pid = self._project()
        self._brief(pid)  # force the v3 migration to run
        from design_lab.creative import store as cstore
        from design_lab.design_layer import _append_event

        fixed = 'event-' + 'a' * 32
        payload = {'brief_id': 'brief-' + 'b' * 32, 'version': 1, 'spec_sha256': 'sha256:' + 'c' * 64}
        conn = self._connect()
        try:
            with cstore.transaction(conn):
                _append_event(conn, project_id=pid, kind='brief-created', payload=payload,
                              brief_id='brief-' + 'b' * 32, event_id=fixed)
            stored = dict(conn.execute(
                "SELECT * FROM design_layer_event WHERE event_id=?", (fixed,)).fetchone())
            self.assertEqual(stored['payload_json'],
                             json.dumps(payload, ensure_ascii=False, sort_keys=True,
                                        separators=(',', ':')))
            # The same event_id again must fail closed, not replace the row.
            with self.assertRaises(sqlite3.IntegrityError):
                with cstore.transaction(conn):
                    _append_event(conn, project_id=pid, kind='brief-revised',
                                  payload={'overwrite': True}, brief_id=stored['brief_id'],
                                  event_id=fixed)
            after = dict(conn.execute(
                "SELECT * FROM design_layer_event WHERE event_id=?", (fixed,)).fetchone())
            self.assertEqual(after, stored)
            # ... and the log itself refuses UPDATE and DELETE at the DB level.
            with self.assertRaises(sqlite3.IntegrityError):
                conn.execute("UPDATE design_layer_event SET kind='brief-created' WHERE event_id=?",
                             (fixed,))
            conn.rollback()
            with self.assertRaises(sqlite3.IntegrityError):
                conn.execute("DELETE FROM design_layer_event WHERE event_id=?", (fixed,))
            conn.rollback()
            self.assertIsNotNone(conn.execute(
                "SELECT 1 FROM design_layer_event WHERE event_id=?", (fixed,)).fetchone())
        finally:
            conn.close()

    def test_v3_upgrades_a_populated_database_after_a_backup(self):
        # The migration is additive and runs on a LIVE database: build real state
        # (a project and a brief), then present the same database as the v1/v2
        # chain would have left it -- no event table, no v3 record. The next open
        # must back the populated file up and re-apply v3.
        pid = self._project()
        brief = self._brief(pid)
        db = Path(self.service.database)
        conn = self._connect()
        try:
            conn.execute("DROP TABLE design_layer_event")
            conn.execute("DELETE FROM runtime_migration WHERE name='design-layer-v3'")
            conn.commit()
        finally:
            conn.close()

        from design_lab.creative import store as cstore
        conn = cstore.connect(db, project_root=self.root)
        try:
            applied = [row[0] for row in conn.execute(
                "SELECT name FROM runtime_migration WHERE name='design-layer-v3'")]
        finally:
            conn.close()
        self.assertEqual(applied, ['design-layer-v3'])
        backups = sorted(p.name for p in db.parent.glob(db.name + '.pre-design-layer-v3-*.bak'))
        self.assertTrue(backups, 'a populated database must be backed up before the migration')

        # The pre-migration content is intact and the log is writable again.
        after = self._raw('design_brief', 'brief_id', brief['brief_id'])
        self.assertEqual(after['title'], brief['title'])
        self.assertEqual(after['superseded_by'], None)
        self.assertEqual(self._revise_brief(pid, brief['brief_id'], key='r1')[0], 201)
        self.assertEqual(self._kinds(pid), ['brief-revised'])

    def test_v3_migration_is_registered_and_applied(self):
        from design_lab.creative import store as cstore
        from design_lab.runtime.state_resources import state_schema

        path = state_schema('design-lab-state-design-layer-v3.sql')
        self.assertTrue(Path(path).is_file())
        names = [entry[0] for entry in cstore.GUARDED_MIGRATIONS]
        self.assertIn('design-layer-v3', names)
        self.assertEqual(names.index('design-layer-v3'), names.index('design-layer-v2') + 1)

        pid = self._project()
        self._brief(pid)
        conn = self._connect()
        try:
            applied = [row[0] for row in conn.execute("SELECT name FROM runtime_migration")]
            self.assertIn('design-layer-v3', applied)
            objects = {row[0] for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE name LIKE 'design_layer_event%'")}
        finally:
            conn.close()
        self.assertLessEqual({'design_layer_event', 'design_layer_event_no_update',
                              'design_layer_event_no_delete'}, objects)


if __name__ == '__main__':
    unittest.main()
