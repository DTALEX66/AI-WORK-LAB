# SPDX-License-Identifier: MIT
"""The DL-UI-U06 runtime read-back, against a real database and a real socket.

`native_tasks.py` has always recorded which host is held, whether an attempt reached
quiescence, whether a reconciliation is open and which recovery protocol was written -- and no
route exposed any of it, so the workbench could print a job's state word while being unable to
say whether Photoshop was currently occupied. These cases pin what the new read surface is
allowed to claim, which is mostly *not* claiming:

* **absent is not empty.** A database where no native attempt was ever recorded has no
  `native_host_guard_v1` table at all. Reporting that as "0 hosts held" would be the same
  mistake this repository has already been caught making twice, so the envelope distinguishes
  `ABSENT` (rows: null) from `PRESENT` with zero rows, and the counts follow it.
* **the read may not create what it reads.** Table creation belongs to
  `native_tasks._connect`; a reader that ran the same DDL would turn an honest ABSENT into a
  lie. One case asserts the table list before and after the read.
* **no verdict word is invented.** There is no IDLE, HEALTHY, SAFE_TO_RETRY or READY here: a
  held guard row says a host is held, and that is all it says.
* **budget is null because nothing records one**, not because it is zero.
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
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / 'src'))

from design_lab.http_service import make_server                      # noqa: E402
from design_lab.native_runtime import (NativeRuntimeError,             # noqa: E402
                                       readback)
from design_lab.native_tasks import NativeTasks                        # noqa: E402
from design_lab.service import ProjectService                          # noqa: E402

_SECTIONS = ('host_guard', 'quiescence', 'reconciliation', 'recovery_protocol', 'executions')
_VERDICT_WORDS = ('IDLE', 'HEALTHY', 'READY', 'SAFE', 'CLEARED', 'NOT_REVIEWED',
                  'PENDING_REVIEW', 'ACCEPTED', 'AVAILABLE')


def table_names(service) -> set[str]:
    path = service.paths.database_path(service.database)
    conn = sqlite3.connect(path.as_uri() + '?mode=ro', uri=True)
    try:
        return {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    finally:
        conn.close()


class NativeRuntimeReadbackTests(unittest.TestCase):
    def setUp(self):
        os.environ.pop('PROJECT_LOCAL_ROOT', None)
        self.base = Path(tempfile.mkdtemp(dir=REPO / '.project-local' / 'task-runtime'))
        self.project = self.base / 'project'
        self.project.mkdir()
        (self.project / 'AGENTS.md').write_text('# native runtime fixture project',
                                                encoding='utf-8')
        self.service = ProjectService(self.project)
        self.project_id = self.service.create_project('Runtime Probe')['id']

    def doc(self):
        return readback(self.service, self.project_id)

    def test_absent_tables_are_absent_and_not_zero(self):
        doc = self.doc()
        self.assertEqual(doc['schemaVersion'], 'design-lab/native-runtime-readback/v1')
        for section in _SECTIONS:
            self.assertEqual(doc[section]['table'], 'ABSENT',
                             f'{section} was reported present in a database that never ran a '
                             'native attempt')
            self.assertIsNone(doc[section]['rows'])
        self.assertIsNone(doc['counts']['hosts_held'],
                          'a null count is the only honest answer when the table is absent; '
                          '0 would read as "the host is free"')

    def test_the_read_never_creates_the_tables_it_reads(self):
        before = table_names(self.service)
        self.doc()
        after = table_names(self.service)
        self.assertEqual(before, after,
                         'the read-back wrote DDL: an absent table would start reporting zero '
                         'rows, which is a different claim from the one it replaces')

    def test_present_but_empty_reports_a_real_zero(self):
        native = NativeTasks(self.service)
        conn = native._connect()
        conn.commit()
        conn.close()
        doc = self.doc()
        self.assertEqual(doc['host_guard']['table'], 'PRESENT')
        self.assertEqual(doc['host_guard']['rows'], [])
        self.assertEqual(doc['counts']['hosts_held'], 0,
                         'once the table exists, zero held hosts is a fact worth printing')

    def test_a_held_host_is_reported_as_held(self):
        native = NativeTasks(self.service)
        conn = native._connect()
        # The guard's attempt_id is a real foreign key with FK enforcement on, so the chain
        # under it has to exist: an intent, a job, an attempt. Fabricating an attempt id would
        # have the fixture lie about the shape of the data the projection reads.
        conn.execute("INSERT INTO operation_intent VALUES (?,?,?,?,?)",
                     ('op-1', 'native:' + self.project_id + ':photoshop', 'key-1',
                      'a' * 64, '2026-10-09T20:00:00Z'))
        conn.execute("INSERT INTO job (job_id, operation_id) VALUES ('job-1', 'op-1')")
        conn.execute("INSERT INTO job_attempt VALUES ('job-1', 1, '2026-10-09T20:00:00Z')")
        conn.execute("INSERT INTO attempt_state VALUES ('att-held','job-1',1,'RUNNING',"
                     "'2026-10-09T20:00:00Z',NULL,'fixture')")
        conn.execute('INSERT INTO native_host_guard_v1 VALUES (?,?,?)',
                     ('photoshop', 'att-held', '2026-10-09T20:00:00Z'))
        conn.commit()
        conn.close()
        doc = self.doc()
        self.assertEqual(doc['counts']['hosts_held'], 1)
        self.assertEqual(doc['host_guard']['rows'],
                         [{'host': 'photoshop', 'attempt_id': 'att-held',
                           'acquired_at': '2026-10-09T20:00:00Z'}])

    def test_budget_is_null_with_a_reason_and_no_invented_zero(self):
        doc = self.doc()
        self.assertIsNone(doc['budget'])
        self.assertIn('no table', doc['budget_reason'])
        self.assertFalse(doc['proves_production_ready'])
        self.assertFalse(doc['is_host_action_performed'])
        self.assertTrue(doc['does_not_say'],
                        'the envelope must carry the sentences a reader must not infer')

    def test_no_verdict_word_appears_anywhere(self):
        body = json.dumps(self.doc())
        for word in _VERDICT_WORDS:
            self.assertNotIn(word, body,
                             f'{word!r} is not a word this service can emit; the read must '
                             'report rows, not a health verdict')

    def test_unknown_project_is_a_404_not_an_empty_panel(self):
        with self.assertRaises(NativeRuntimeError) as caught:
            readback(self.service, 'f' * 32)
        self.assertEqual(caught.exception.status, 404)
        self.assertEqual(caught.exception.code, 'PROJECT_NOT_FOUND')


class NativeRuntimeRouteTests(unittest.TestCase):
    def setUp(self):
        os.environ.pop('PROJECT_LOCAL_ROOT', None)
        self.base = Path(tempfile.mkdtemp(dir=REPO / '.project-local' / 'task-runtime'))
        self.project = self.base / 'project'
        self.project.mkdir()
        (self.project / 'AGENTS.md').write_text('# native runtime route fixture',
                                                encoding='utf-8')
        self.service = ProjectService(self.project)
        self.project_id = self.service.create_project('Runtime Route')['id']
        self.token = secrets.token_hex(32)
        self.httpd = make_server(self.service, self.token, 0)
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.httpd.shutdown()
        self.httpd.server_close()
        self.thread.join(timeout=5)

    def call(self, path, project_id=None):
        conn = http.client.HTTPConnection('127.0.0.1', self.httpd.server_port, timeout=10)
        conn.request('GET', path.format(pid=project_id or self.project_id),
                     headers={'Authorization': 'Bearer ' + self.token})
        response = conn.getresponse()
        body = response.read().decode('utf-8')
        conn.close()
        return response.status, json.loads(body) if body else None

    def test_the_route_serves_the_projection(self):
        status, body = self.call('/api/projects/{pid}/native-runtime')
        self.assertEqual(status, 200)
        self.assertEqual(body['schemaVersion'], 'design-lab/native-runtime-readback/v1')
        self.assertEqual(body['project_id'], self.project_id)

    def test_the_route_refuses_an_unknown_project_by_code(self):
        status, body = self.call('/api/projects/{pid}/native-runtime', project_id='e' * 32)
        self.assertEqual(status, 404)
        self.assertEqual(body['error'], 'PROJECT_NOT_FOUND')


if __name__ == '__main__':
    unittest.main(verbosity=2)
