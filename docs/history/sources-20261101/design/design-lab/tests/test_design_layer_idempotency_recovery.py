# SPDX-License-Identifier: MIT
"""P1-RECOVERY: commit-then-disconnect 幂等重放回归（DESIGN-LAB design layer）。

任务书 DL-E2-P1-RECOVERY 场景：``POST choose`` 在服务器已 commit、客户端未
收到响应时断线；客户端以相同 ``operation_intent`` 重试后只能得到原结果，
不能生成第二次选择。bind 同理。

这些测试通过真实 loopback HTTP 驱动，并直接读 SQLite 的
``design_layer_event`` append-only 日志与 ``design_direction`` 表，证明重放
不复制实体、不追加事件行、不破坏 ``SUM(chosen)=1`` 不变量。

Nothing here claims E3 host runs or E4 jury acceptance.
"""
import sqlite3
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / 'design-lab' / 'tests') not in sys.path:
    sys.path.insert(0, str(ROOT / 'design-lab' / 'tests'))
# Import the MODULE, not the class. `from test_design_layer_http import DesignLayerHttpTests`
# binds the P0 class as a module attribute of this file, and unittest's discovery collects every
# TestCase subclass bound in a test module -- so the P0 tests were registered a second time here,
# under their own id and their own __module__, and the suite ran those twenty tests twice.
# Measured 2026-10-16: discovery reported 3011 cases for 2991 distinct ids, all twenty duplicates
# belonging to DesignLayerHttpTests. The docstring below says the P0 methods "already run in
# test_design_layer_http and would just duplicate the suite"; with a plain class import that
# sentence was false while looking satisfied. Qualifying through the module keeps the shared
# implementation and drops the duplicate registration.
import test_design_layer_http


class DesignLayerIdempotencyRecoveryTests(unittest.TestCase):
    """Replays the commit-then-disconnect retry against the REAL loopback API.

    A plain ``unittest.TestCase`` that DELEGATES the P0 harness's ``setUp``
    (so we get the exact server / token / SQLite root the P0 tests use, with
    no second backend and no mock) WITHOUT inheriting the P0 test methods —
    those already run in ``test_design_layer_http`` and would just duplicate
    the suite. The P0 helper methods are bound by name from the P0 class, so
    the implementation is shared, not forked.
    """

    # Delegate P0 harness setup (server + token + SQLite root) verbatim.
    def setUp(self):
        test_design_layer_http.DesignLayerHttpTests.setUp(self)

    # Bind the P0 helpers (same implementation, no fork; this class does NOT
    # inherit them, so pull them in by name).
    request = test_design_layer_http.DesignLayerHttpTests.request
    key = test_design_layer_http.DesignLayerHttpTests.key
    _project = test_design_layer_http.DesignLayerHttpTests._project
    _import_asset = test_design_layer_http.DesignLayerHttpTests._import_asset
    _brief = test_design_layer_http.DesignLayerHttpTests._brief
    _direction = test_design_layer_http.DesignLayerHttpTests._direction

    def _event_count(self, project_id, kind=None):
        conn = sqlite3.connect(str(self.service.database))
        try:
            if kind:
                row = conn.execute(
                    "SELECT COUNT(*) FROM design_layer_event WHERE project_id=? AND kind=?",
                    (project_id, kind)).fetchone()
            else:
                row = conn.execute(
                    "SELECT COUNT(*) FROM design_layer_event WHERE project_id=?",
                    (project_id,)).fetchone()
            return int(row[0])
        finally:
            conn.close()

    def _chosen_count(self, brief_id):
        conn = sqlite3.connect(str(self.service.database))
        try:
            return int(conn.execute(
                "SELECT SUM(chosen) FROM design_direction WHERE brief_id=?",
                (brief_id,)).fetchone()[0] or 0)
        finally:
            conn.close()

    # -- 1. choose A, replay same intent -> same identity, no 2nd event row
    def test_choose_replay_same_intent_returns_same_identity(self):
        pid = self._project()
        brief = self._brief(pid)
        direction = self._direction(pid, brief['brief_id'])
        key = self.key('c-recover')
        payload = {'actor': 'ALEX', 'actor_kind': 'human', 'idempotency_key': key}

        first = self.request('POST',
                             f"/api/projects/{pid}/directions/{direction['direction_id']}/choose",
                             payload)
        self.assertEqual(first[0], 200)
        events_after_first = self._event_count(pid, 'direction-chosen')
        self.assertEqual(events_after_first, 1)

        # commit-then-disconnect: the client never saw `first`; it retries with
        # the SAME operation intent. The server must return the ORIGINAL result.
        second = self.request('POST',
                              f"/api/projects/{pid}/directions/{direction['direction_id']}/choose",
                              payload)
        self.assertEqual(second[0], 200)
        self.assertEqual(second[1]['direction'], first[1]['direction'])
        # No second event row, no duplicated direction.
        self.assertEqual(self._event_count(pid, 'direction-chosen'), events_after_first)
        self.assertEqual(self._chosen_count(brief['brief_id']), 1)

    # -- 2. choose A then choose B (different intent) -> exactly one chosen
    def test_switch_choice_replay_preserves_single_chosen(self):
        pid = self._project()
        brief = self._brief(pid)
        dir_a = self._direction(pid, brief['brief_id'], title='A', key='ra')
        dir_b = self._direction(pid, brief['brief_id'], title='B', key='rb')

        self.request('POST', f"/api/projects/{pid}/directions/{dir_a['direction_id']}/choose",
                     {'actor': 'A', 'actor_kind': 'human', 'idempotency_key': self.key('ca')})
        self.assertEqual(self._chosen_count(brief['brief_id']), 1)

        # Replay the A-choose (client lost the response) — still one chosen, A.
        self.request('POST', f"/api/projects/{pid}/directions/{dir_a['direction_id']}/choose",
                     {'actor': 'A', 'actor_kind': 'human', 'idempotency_key': self.key('ca')})
        self.assertEqual(self._chosen_count(brief['brief_id']), 1)

        # Now switch to B with a NEW intent — A is de-selected, B becomes the one.
        self.request('POST', f"/api/projects/{pid}/directions/{dir_b['direction_id']}/choose",
                     {'actor': 'B', 'actor_kind': 'human', 'idempotency_key': self.key('cb')})
        self.assertEqual(self._chosen_count(brief['brief_id']), 1)
        layer = self.request(path=f"/api/projects/{pid}/design-layer")[1]['design_layer']
        self.assertEqual(layer['chosen_direction']['direction_id'], dir_b['direction_id'])

    # -- 3. same key + DIFFERENT actor on the SAME direction -> 409
    # (scope is 'choose:<direction_id>'; the same direction's choose is
    #  idempotent only when replayed with the identical document — a different
    #  actor is different content and must fail closed, matching the P0-06
    #  brief-level rule test_reused_key_with_different_content_fails_closed_409)
    def test_reused_key_different_content_fails_closed(self):
        pid = self._project()
        brief = self._brief(pid)
        direction = self._direction(pid, brief['brief_id'])
        self.request('POST', f"/api/projects/{pid}/directions/{direction['direction_id']}/choose",
                     {'actor': 'ALEX', 'actor_kind': 'human', 'idempotency_key': self.key('k1')})
        # Same key, different actor: must NOT be silently accepted.
        status, body = self.request('POST',
                                    f"/api/projects/{pid}/directions/{direction['direction_id']}/choose",
                                    {'actor': 'OTHER', 'actor_kind': 'human',
                                     'idempotency_key': self.key('k1')})
        self.assertEqual(status, 409)
        self.assertEqual(body['error'], 'IDEMPOTENCY_CONFLICT')
        # The original choice is intact.
        layer = self.request(path=f"/api/projects/{pid}/design-layer")[1]['design_layer']
        self.assertEqual(layer['chosen_direction']['direction_id'], direction['direction_id'])
        self.assertEqual(layer['chosen_direction']['actor'], 'ALEX')
        self.assertEqual(self._chosen_count(brief['brief_id']), 1)

    # -- 4. bind replay is idempotent: same binding, no duplicate row
    def test_bind_replay_same_intent_is_idempotent(self):
        pid = self._project()
        brief = self._brief(pid)
        direction = self._direction(pid, brief['brief_id'])
        self.request('POST', f"/api/projects/{pid}/directions/{direction['direction_id']}/choose",
                     {'actor': 'ALEX', 'actor_kind': 'human', 'idempotency_key': self.key('cb')})
        key = self.key('b-recover')
        payload = {'design_system_name': 'uiux-commercial-light', 'idempotency_key': key}
        first = self.request('POST',
                             f"/api/projects/{pid}/directions/{direction['direction_id']}/bind",
                             payload)
        self.assertEqual(first[0], 201)
        second = self.request('POST',
                              f"/api/projects/{pid}/directions/{direction['direction_id']}/bind",
                              payload)
        # The retry must return the SAME binding identity, not create a second one.
        self.assertEqual(second[1]['binding'], first[1]['binding'])
        layer = self.request(path=f"/api/projects/{pid}/design-layer")[1]['design_layer']
        self.assertEqual(len(layer['bindings']), 1)
        self.assertEqual(self._event_count(pid, 'binding-created'), 1)

    # -- 5. restart-resilient readback: fresh service on same DB sees same state
    def test_readback_stable_across_service_restart(self):
        from design_lab.service import ProjectService
        pid = self._project()
        brief = self._brief(pid)
        direction = self._direction(pid, brief['brief_id'])
        self.request('POST', f"/api/projects/{pid}/directions/{direction['direction_id']}/choose",
                     {'actor': 'ALEX', 'actor_kind': 'human', 'idempotency_key': self.key('cr')})
        before = self.request(path=f"/api/projects/{pid}/design-layer")[1]['design_layer']

        # Simulate a backend crash/restart: a brand-new service object over the
        # SAME database must read back the identical persisted state.
        reloaded = ProjectService(str(self.root))
        status, body = None, None
        import http.client, secrets as _secrets
        from design_lab.http_service import make_server
        import threading, os
        token = _secrets.token_hex(32)
        server = make_server(reloaded, token, port=0)
        port = server.server_address[1]
        th = threading.Thread(target=server.serve_forever, daemon=True)
        th.start()
        try:
            conn = http.client.HTTPConnection('127.0.0.1', port, timeout=5)
            conn.request('GET', f'/api/projects/{pid}/design-layer',
                         headers={'Authorization': 'Bearer ' + token,
                                  'Host': f'127.0.0.1:{port}',
                                  'Origin': f'http://127.0.0.1:{port}',
                                  'Sec-Fetch-Site': 'same-origin'})
            resp = conn.getresponse()
            body = resp.read()
            conn.close()
            self.assertEqual(resp.status, 200)
            import json
            after = json.loads(body)['design_layer']
        finally:
            server.shutdown()
            th.join()
            server.server_close()
        self.assertEqual(after['chosen_direction'], before['chosen_direction'])
        self.assertEqual(self._chosen_count(brief['brief_id']), 1)


if __name__ == '__main__':
    unittest.main()
