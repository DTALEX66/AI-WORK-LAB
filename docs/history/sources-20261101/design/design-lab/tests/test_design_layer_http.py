# SPDX-License-Identifier: MIT
"""E-SLICE design layer vertical slice (Brief -> Reference -> Direction -> DesignSystem).

Real loopback HTTP contract tests: a Brief, a Direction, a human Choice and a
DesignSystem binding are driven through the actual workbench API and read back
as persisted state.

Beyond the E-SLICE-01 slice, this class also pins the P0 correctness invariants
that the batch-A fixes introduced, asserting the PERSISTED database state via
the design-layer readback (not merely an HTTP code):

* P0-01 single-choice: within one brief exactly ONE direction may be chosen;
  choosing a second direction atomically de-selects the first.
* P0-02 no fake chosen: with no real choice, ``chosen_direction`` is null (it
  never falls back to the most-recently-created direction).
* P0-03 chosen-before-bind: binding a design system to an UNCHOSEN direction
  fails closed (409 DIRECTION_NOT_CHOSEN) and persists no binding.
* P0-04 single constraints contract: constraints round-trips as string|null,
  never as an object (no [object Object] double truth).
* P0-05 real references: a brief may only reference assets that genuinely exist
  and belong to the SAME project; malformed / unknown / cross-project ids fail
  closed.
* P0-06 idempotency + isolation regressions.

Nothing here claims E3 host runs or E4 jury acceptance.
"""
import base64
import hashlib
import http.client
import json
import os
import secrets
import sqlite3
import struct
import sys
import tempfile
import threading
import unittest
import zlib
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
VALID_DESIGN_SYSTEMS = {'anomaly-monitor-dark', 'nebula-tech',
                       'personal-design-intelligence', 'uiux-commercial-light'}


def _png_bytes() -> bytes:
    """A valid 1x1 RGBA PNG, built with stdlib only (no external fixture)."""
    signature = b'\x89PNG\r\n\x1a\n'

    def chunk(tag, data):
        out = struct.pack('>I', len(data)) + tag + data
        out += struct.pack('>I', zlib.crc32(tag + data) & 0xFFFFFFFF)
        return out

    ihdr = chunk(b'IHDR', struct.pack('>IIBBBBB', 1, 1, 8, 6, 0, 0, 0))
    scanline = b'\x00' + b'\xff\x00\x00\xff'          # filter 0 + RGBA
    idat = chunk(b'IDAT', zlib.compress(scanline))
    iend = chunk(b'IEND', b'')
    return signature + ihdr + idat + iend


class DesignLayerHttpTests(unittest.TestCase):
    def setUp(self):
        sys.path.insert(0, str(ROOT / 'src'))
        self.addCleanup(sys.path.remove, str(ROOT / 'src'))
        parent = ROOT / '.project-local' / 'task-runtime' / 'design-layer-tests'
        parent.mkdir(parents=True, exist_ok=True)
        tmp = tempfile.TemporaryDirectory(dir=parent)
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        (self.root / 'AGENTS.md').write_text('# synthetic design-layer HTTP project', encoding='utf-8')

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
            # Stop the serve loop, wait for the background thread to wind down
            # before closing the socket; otherwise close() races the thread's
            # select() and emits a WinError 10038 teardown trace.
            self.server.shutdown()
            self.thread.join()
            self.server.server_close()
        self.addCleanup(_stop_server)

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
            payload = json.loads(resp.read())
            return resp.status, payload
        finally:
            conn.close()

    def key(self, n):
        return hashlib.sha256(n.encode()).hexdigest()

    def _project(self, name='E slice'):
        status, body = self.request('POST', '/api/projects', {'name': name})
        self.assertEqual(status, 201)
        return body['project']['id']

    def _import_asset(self, pid, key='imp'):
        """Import a real 1x1 PNG into the project and return its asset id."""
        b64 = base64.b64encode(_png_bytes()).decode('ascii')
        status, body = self.request('POST', f'/api/projects/{pid}/assets',
                                    {'content_base64': b64, 'idempotency_key': self.key(key)})
        self.assertEqual(status, 201)
        return body['asset']['id']

    def _brief(self, pid, title='Autumn', key='b1', goals=('modern',),
               constraints=None, references=None):
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

    # -- E-SLICE-01 full slice --------------------------------------------
    def test_full_vertical_slice_persists_and_reads_back(self):
        pid = self._project()
        aid = self._import_asset(pid)
        brief = self._brief(pid, references=[aid])
        self.assertEqual(brief['reference_asset_ids'], [aid])
        direction = self._direction(pid, brief['brief_id'])
        # Idempotent retry: same key -> same identity, still one row.
        self.assertEqual(self._brief(pid, references=[aid]), brief)
        self.assertEqual(self._direction(pid, brief['brief_id']), direction)
        self.assertEqual(len(self.request(path=f'/api/projects/{pid}/briefs')[1]['briefs']), 1)

        chosen = self.request('POST', f"/api/projects/{pid}/directions/{direction['direction_id']}/choose",
                              {'actor': 'ALEX', 'actor_kind': 'human',
                               'idempotency_key': self.key('c1')})[1]['direction']
        self.assertTrue(chosen['chosen'])
        self.assertEqual(chosen['actor'], 'ALEX')
        self.assertEqual(chosen['actor_kind'], 'human')

        binding = self.request('POST', f"/api/projects/{pid}/directions/{direction['direction_id']}/bind",
                               {'design_system_name': 'uiux-commercial-light',
                                'idempotency_key': self.key('s1')})[1]['binding']
        self.assertEqual(binding['design_system_name'], 'uiux-commercial-light')

        readback = self.request(path=f'/api/projects/{pid}/design-layer')[1]['design_layer']
        self.assertEqual(readback['chosen_direction']['direction_id'], direction['direction_id'])
        self.assertEqual(readback['active_binding']['design_system_name'], 'uiux-commercial-light')
        self.assertEqual(len(readback['briefs']), 1)
        self.assertEqual(len(readback['directions']), 1)
        self.assertEqual(len(readback['bindings']), 1)
        self.assertEqual(readback['briefs'][0]['reference_asset_ids'], [aid])

    # -- P0-02 no choice => null chosen_direction -------------------------
    def test_no_choice_returns_null_chosen_direction(self):
        pid = self._project()
        brief = self._brief(pid)
        self._direction(pid, brief['brief_id'])
        layer = self.request(path=f'/api/projects/{pid}/design-layer')[1]['design_layer']
        self.assertEqual(layer['chosen_direction'], None)
        # The created direction is present but NOT chosen.
        self.assertEqual(len(layer['directions']), 1)
        self.assertFalse(layer['directions'][0]['chosen'])

    def test_agent_cannot_make_the_human_direction_choice(self):
        pid = self._project()
        brief = self._brief(pid)
        direction = self._direction(pid, brief['brief_id'])
        status, body = self.request(
            'POST', f"/api/projects/{pid}/directions/{direction['direction_id']}/choose",
            {'actor': 'agent-r5', 'actor_kind': 'agent',
             'idempotency_key': self.key('agent-choice')})
        self.assertEqual(status, 403)
        self.assertEqual(body['error'], 'HUMAN_DIRECTION_CHOICE_REQUIRED')
        layer = self.request(path=f'/api/projects/{pid}/design-layer')[1]['design_layer']
        self.assertIsNone(layer['chosen_direction'])
        self.assertEqual(len(layer['directions']), 1)
        self.assertFalse(layer['directions'][0]['chosen'])

    # -- P0-01 single-choice invariant ------------------------------------
    def test_single_choice_invariant_deselects_siblings(self):
        pid = self._project()
        brief = self._brief(pid)
        dir_a = self._direction(pid, brief['brief_id'], title='A', key='da')
        dir_b = self._direction(pid, brief['brief_id'], title='B', key='db')
        # Choose A, then B. Only B may be chosen; A must be de-selected.
        self.request('POST', f"/api/projects/{pid}/directions/{dir_a['direction_id']}/choose",
                     {'actor': 'A', 'actor_kind': 'human', 'idempotency_key': self.key('ca')})
        self.request('POST', f"/api/projects/{pid}/directions/{dir_b['direction_id']}/choose",
                     {'actor': 'B', 'actor_kind': 'human', 'idempotency_key': self.key('cb')})
        layer = self.request(path=f'/api/projects/{pid}/design-layer')[1]['design_layer']
        chosen_flags = {d['direction_id']: d['chosen'] for d in layer['directions']}
        self.assertEqual(chosen_flags, {dir_a['direction_id']: False, dir_b['direction_id']: True})
        self.assertEqual(layer['chosen_direction']['direction_id'], dir_b['direction_id'])

    # -- P0-03 unchosen direction cannot bind ----------------------------
    def test_bind_requires_chosen_direction(self):
        pid = self._project()
        brief = self._brief(pid)
        direction = self._direction(pid, brief['brief_id'])
        # Unchosen direction -> 409 DIRECTION_NOT_CHOSEN, no binding persisted.
        status, body = self.request('POST',
                                    f"/api/projects/{pid}/directions/{direction['direction_id']}/bind",
                                    {'design_system_name': 'nebula-tech', 'idempotency_key': self.key('s1')})
        self.assertEqual(status, 409)
        self.assertEqual(body['error'], 'DIRECTION_NOT_CHOSEN')
        self.assertEqual(len(self.request(path=f'/api/projects/{pid}/design-layer')[1]['design_layer']['bindings']), 0)
        # After choosing, the same bind succeeds.
        self.request('POST', f"/api/projects/{pid}/directions/{direction['direction_id']}/choose",
                     {'actor': 'ALEX', 'actor_kind': 'human', 'idempotency_key': self.key('c')})
        status, body = self.request('POST',
                                    f"/api/projects/{pid}/directions/{direction['direction_id']}/bind",
                                    {'design_system_name': 'nebula-tech', 'idempotency_key': self.key('s2')})
        self.assertEqual(status, 201)
        self.assertEqual(body['binding']['design_system_name'], 'nebula-tech')

    def test_bind_rejects_a_legacy_agent_chosen_direction(self):
        pid = self._project()
        brief = self._brief(pid)
        direction = self._direction(pid, brief['brief_id'])
        # Simulate a pre-fix persisted row. The new choose endpoint cannot create
        # this state, but bind must still fail closed when upgrading an old DB.
        conn = sqlite3.connect(str(self.service.database))
        try:
            conn.execute(
                "UPDATE design_direction SET chosen=1, actor=?, actor_kind=? WHERE direction_id=?",
                ('legacy-agent', 'agent', direction['direction_id']))
            conn.commit()
        finally:
            conn.close()
        status, body = self.request(
            'POST', f"/api/projects/{pid}/directions/{direction['direction_id']}/bind",
            {'design_system_name': 'nebula-tech', 'idempotency_key': self.key('legacy-bind')})
        self.assertEqual(status, 409)
        self.assertEqual(body['error'], 'HUMAN_DIRECTION_CHOICE_REQUIRED')
        layer = self.request(path=f'/api/projects/{pid}/design-layer')[1]['design_layer']
        self.assertEqual(layer['bindings'], [])

    # -- P0-04 constraints is a string|null, not an object ---------------
    def test_constraints_string_roundtrip(self):
        pid = self._project()
        brief = self._brief(pid, constraints='no logo topology change')
        self.assertEqual(brief['constraints'], 'no logo topology change')
        readback = self.request(path=f"/api/projects/{pid}/briefs/{brief['brief_id']}")[1]['brief']
        self.assertEqual(readback['constraints'], 'no logo topology change')
        self.assertNotIsInstance(readback['constraints'], dict)
        # A null constraints round-trips to None.
        empty = self._brief(pid, title='NoCon', key='bc', constraints=None)
        self.assertIsNone(self.request(path=f"/api/projects/{pid}/briefs/{empty['brief_id']}")[1]['brief']['constraints'])

    # -- P0-05 real reference validation --------------------------------
    def test_valid_reference_persists_and_reads_back(self):
        pid = self._project()
        aid = self._import_asset(pid)
        brief = self._brief(pid, references=[aid])
        self.assertEqual(brief['reference_asset_ids'], [aid])
        readback = self.request(path=f"/api/projects/{pid}/briefs/{brief['brief_id']}")[1]['brief']
        self.assertEqual(readback['reference_asset_ids'], [aid])
        # Dedupe: sending the same id twice persists it once.
        dup = self.request('POST', f'/api/projects/{pid}/briefs',
                           {'title': 'Dup', 'goals': ['g'], 'constraints': None,
                            'reference_asset_ids': [aid, aid], 'idempotency_key': self.key('dup')})[1]['brief']
        self.assertEqual(dup['reference_asset_ids'], [aid])

    def test_malformed_and_unknown_reference_fail_closed(self):
        pid = self._project()
        status, body = self.request('POST', f'/api/projects/{pid}/briefs',
                                    {'title': 'T', 'goals': ['g'], 'constraints': None,
                                     'reference_asset_ids': ['not-an-asset'], 'idempotency_key': self.key('m')})
        self.assertEqual(status, 400)
        self.assertEqual(body['error'], 'INVALID_REFERENCE_ASSET_ID')
        # Well-formed but non-existent asset id -> 404.
        status, body = self.request('POST', f'/api/projects/{pid}/briefs',
                                    {'title': 'T', 'goals': ['g'], 'constraints': None,
                                     'reference_asset_ids': ['img-' + 'b' * 64], 'idempotency_key': self.key('u')})
        self.assertEqual(status, 404)
        self.assertEqual(body['error'], 'REFERENCE_ASSET_NOT_FOUND')

    def test_cross_project_reference_fails_closed(self):
        owner = self._project()
        other = self._project('Other')
        aid = self._import_asset(owner)
        status, body = self.request('POST', f'/api/projects/{other}/briefs',
                                    {'title': 'T', 'goals': ['g'], 'constraints': None,
                                     'reference_asset_ids': [aid], 'idempotency_key': self.key('x')})
        self.assertEqual(status, 409)
        self.assertEqual(body['error'], 'REFERENCE_ASSET_PROJECT_MISMATCH')

    # -- P0-06 idempotency + isolation + empty fields --------------------
    def test_repeated_choose_is_idempotent(self):
        pid = self._project()
        brief = self._brief(pid)
        direction = self._direction(pid, brief['brief_id'])
        first = self.request('POST', f"/api/projects/{pid}/directions/{direction['direction_id']}/choose",
                             {'actor': 'ALEX', 'actor_kind': 'human', 'idempotency_key': self.key('c')})
        second = self.request('POST', f"/api/projects/{pid}/directions/{direction['direction_id']}/choose",
                              {'actor': 'ALEX', 'actor_kind': 'human', 'idempotency_key': self.key('c')})
        self.assertEqual(first[0], 200)
        self.assertEqual(second[0], 200)
        self.assertEqual(first[1]['direction']['direction_id'], second[1]['direction']['direction_id'])
        self.assertTrue(second[1]['direction']['chosen'])

    def test_repeated_bind_is_idempotent(self):
        pid = self._project()
        brief = self._brief(pid)
        direction = self._direction(pid, brief['brief_id'])
        self.request('POST', f"/api/projects/{pid}/directions/{direction['direction_id']}/choose",
                     {'actor': 'ALEX', 'actor_kind': 'human', 'idempotency_key': self.key('c')})
        first = self.request('POST', f"/api/projects/{pid}/directions/{direction['direction_id']}/bind",
                            {'design_system_name': 'nebula-tech', 'idempotency_key': self.key('s')})
        second = self.request('POST', f"/api/projects/{pid}/directions/{direction['direction_id']}/bind",
                             {'design_system_name': 'nebula-tech', 'idempotency_key': self.key('s')})
        self.assertEqual(first[1]['binding']['binding_id'], second[1]['binding']['binding_id'])
        self.assertEqual(len(self.request(path=f'/api/projects/{pid}/design-layer')[1]['design_layer']['bindings']), 1)

    def test_reused_key_with_different_content_fails_closed_409(self):
        pid = self._project()
        self._brief(pid)
        status, body = self.request('POST', f'/api/projects/{pid}/briefs', {
            'title': 'Autumn', 'goals': ['DIFFERENT'], 'constraints': None,
            'reference_asset_ids': [], 'idempotency_key': self.key('b1')})
        self.assertEqual(status, 409)
        self.assertEqual(body['error'], 'IDEMPOTENCY_CONFLICT')
        self.assertEqual(len(self.request(path=f'/api/projects/{pid}/briefs')[1]['briefs']), 1)

    def test_unknown_design_system_and_missing_rows_fail_closed(self):
        pid = self._project()
        brief = self._brief(pid)
        direction = self._direction(pid, brief['brief_id'])
        # Unknown catalog name -> 400 (checked before the chosen invariant).
        status, body = self.request('POST',
                                    f"/api/projects/{pid}/directions/{direction['direction_id']}/bind",
                                    {'design_system_name': 'nope', 'idempotency_key': self.key('bad')})
        self.assertEqual(status, 400)
        self.assertEqual(body['error'], 'UNKNOWN_DESIGN_SYSTEM')
        status, body = self.request(path=f"/api/projects/{pid}/briefs/brief-" + '0' * 32)
        self.assertEqual(status, 404)
        self.assertEqual(body['error'], 'BRIEF_NOT_FOUND')
        status, body = self.request('POST', f'/api/projects/{pid}/briefs',
                                    {'title': '', 'goals': [], 'constraints': None,
                                     'reference_asset_ids': [], 'idempotency_key': self.key('empty')})
        self.assertEqual(status, 400)

    def test_design_system_catalog_is_read_only_and_consistent(self):
        status, body = self.request(path='/api/design-systems')
        self.assertEqual(status, 200)
        self.assertEqual({s['name'] for s in body['design_systems']}, VALID_DESIGN_SYSTEMS)
        # The catalog is a pure read: it neither creates state nor needs a project.
        self.assertFalse((self.root / '.project-local').exists())

    def test_design_layer_reads_are_owner_scoped(self):
        owner = self._project()
        other = self._project('Other')
        brief = self._brief(owner)
        self.assertEqual(self.request(
            path=f"/api/projects/{other}/briefs/{brief['brief_id']}")[0], 404)
        self.assertEqual(self.request(path=f'/api/projects/{other}/design-layer')[1]['design_layer']['briefs'], [])

    def test_write_routes_require_auth_and_cannot_create_state(self):
        pid = self._project()
        self.assertEqual(self.request('POST', f'/api/projects/{pid}/briefs',
                                      {'idempotency_key': self.key('x')},
                                      headers={'Authorization': ''})[0], 401)
        self.assertEqual(self.request(path='/api/design-systems',
                                      headers={'Authorization': ''})[0], 401)

    # -- P0-D active_binding follows the CHOSEN direction -----------------
    def test_switching_choice_nulls_stray_binding(self):
        # Choosing A then binding A, then switching the choice to B (unbound)
        # must make active_binding NULL -- it must not keep pointing at A's
        # binding. A's binding still persists in the bindings list.
        pid = self._project()
        brief = self._brief(pid)
        dir_a = self._direction(pid, brief['brief_id'], title='A', key='da')
        dir_b = self._direction(pid, brief['brief_id'], title='B', key='db')

        self.request('POST', f"/api/projects/{pid}/directions/{dir_a['direction_id']}/choose",
                     {'actor': 'A', 'actor_kind': 'human', 'idempotency_key': self.key('ca')})
        self.request('POST', f"/api/projects/{pid}/directions/{dir_a['direction_id']}/bind",
                     {'design_system_name': 'uiux-commercial-light',
                      'idempotency_key': self.key('sa')})
        layer = self.request(path=f'/api/projects/{pid}/design-layer')[1]['design_layer']
        self.assertEqual(layer['chosen_direction']['direction_id'], dir_a['direction_id'])
        self.assertEqual(layer['active_binding']['direction_id'], dir_a['direction_id'])

        # Switch the human choice to B. B has no binding of its own.
        self.request('POST', f"/api/projects/{pid}/directions/{dir_b['direction_id']}/choose",
                     {'actor': 'B', 'actor_kind': 'human', 'idempotency_key': self.key('cb')})
        layer = self.request(path=f'/api/projects/{pid}/design-layer')[1]['design_layer']
        self.assertEqual(layer['chosen_direction']['direction_id'], dir_b['direction_id'])
        # A's binding still exists (history is append-only) ...
        self.assertEqual([b['direction_id'] for b in layer['bindings']], [dir_a['direction_id']])
        # ... but it is no longer ACTIVE, because B is the chosen direction.
        self.assertIsNone(layer['active_binding'])

    # -- P0-A+ database-level single-choice invariant --------------------
    def test_single_choice_partial_unique_index_exists(self):
        # The design-layer-v2 migration installed a partial UNIQUE index that
        # caps one active chosen direction per brief, at the database level.
        import sqlite3
        pid = self._project()
        brief = self._brief(pid)  # force the design-layer migration chain to run
        conn = sqlite3.connect(str(self.service.database))
        try:
            row = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='index' "
                "AND name='ux_design_direction_one_chosen_per_brief'").fetchone()
        finally:
            conn.close()
        self.assertIsNotNone(row, 'P0-A+ partial unique index was not created')

    def test_v2_precheck_fails_closed_on_duplicate_choices(self):
        # The migration precheck refuses to build the index over legacy
        # duplicate chosen rows, listing the offending briefs (it never picks
        # a winner with MAX(direction_id)).
        import sqlite3
        from design_lab.creative import store as cstore
        conn = sqlite3.connect(':memory:')
        conn.executescript(
            "CREATE TABLE design_direction ("
            "direction_id TEXT PRIMARY KEY, brief_id TEXT, chosen INTEGER, "
            "superseded_by TEXT, actor TEXT, actor_kind TEXT, "
            "spec_sha256 TEXT, version INTEGER, created_at TEXT)")
        conn.execute("INSERT INTO design_direction VALUES ('d1','b1',1,NULL,NULL,NULL,'x',1,'t')")
        conn.execute("INSERT INTO design_direction VALUES ('d2','b1',1,NULL,NULL,NULL,'y',1,'t')")
        with self.assertRaises(cstore.CreativeError) as ctx:
            cstore._design_layer_v2_precheck(conn)
        self.assertIn('b1', str(ctx.exception))
        # A brief with a single chosen direction passes the precheck.
        conn.execute("DELETE FROM design_direction WHERE direction_id='d2'")
        cstore._design_layer_v2_precheck(conn)  # must not raise
        conn.close()


    def test_unknown_project_id_answers_404_with_the_established_word(self):
        """`GET /api/projects/<32-hex>` used to fall off the end of the handler when the id was
        well-formed but absent: `_get_project` only had an `if project is not None` branch, so
        the client got a connection with no status line instead of a 404. At the UI that makes
        "the project is not there" and "the service died mid-answer" the same event.

        Every sibling module already answers an unknown project with PROJECT_NOT_FOUND
        (image_assets.py:46, jury_review.py:33, model_selection.py:121, design_layer.py:464),
        so this pins the one route that had not joined them. Two 404 words are asserted on
        purpose: a malformed id never reaches the handler (the route table's pattern rejects
        it and the dispatcher answers NOT_FOUND), while a well-formed absent id does -- so the
        two paths must not be collapsed into one expectation, and a handler that 404s
        everything would still pass a not-found-only check.
        """
        project_id = self._project('404 leg')
        status, body = self.request('GET', f'/api/projects/{project_id}')
        self.assertEqual(status, 200)
        self.assertEqual(body['project']['id'], project_id)

        absent = hashlib.sha256(b'design-lab-absent-project-id').hexdigest()[:32]
        self.assertEqual(len(absent), 32,
                         'the route pattern is /api/projects/([0-9a-f]{32}); a longer id never '
                         'reaches the handler and the 404 it proves is the dispatcher\'s, not '
                         'the one under test')
        self.assertNotEqual(absent, project_id)
        status, body = self.request('GET', f'/api/projects/{absent}')
        self.assertEqual(status, 404,
                         'a well-formed id that is not in the store must be a 404, '
                         'not an empty reply')
        self.assertEqual(body.get('error'), 'PROJECT_NOT_FOUND',
                         'the word must match the sibling modules, not invent a new one')

        status, body = self.request('GET', '/api/projects/not-an-id')
        self.assertEqual(status, 404)
        self.assertEqual(body.get('error'), 'NOT_FOUND',
                         'a malformed id is refused by the route pattern, not by the handler; '
                         'these two 404s are different facts and must stay distinguishable')


if __name__ == '__main__':
    unittest.main()
