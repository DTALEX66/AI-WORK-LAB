# SPDX-License-Identifier: MIT
"""The official personal launch connects its own page -- without leaking the token.

This is the difference between "start a server and make the user paste a secret"
and a product that opens. The interesting failure mode is not that the handshake
does not work, it is that it works too broadly: a loopback HTTP server on
127.0.0.1 answers anybody on the machine, so these tests drive a real socket and
assert who is refused as well as who is served.
"""
from __future__ import annotations

import http.client
import json
import os
import queue
import secrets
import subprocess
import sys
import tempfile
import threading
import unittest
from contextlib import closing
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src'))

from design_lab.http_service import make_server      # noqa: E402
from design_lab.service import ProjectService        # noqa: E402


class LocalSessionTests(unittest.TestCase):
    def setUp(self):
        self.base = Path(tempfile.mkdtemp(dir=ROOT / '.project-local' / 'task-runtime'))
        self.project = self.base / 'project'
        self.project.mkdir()
        (self.project / 'AGENTS.md').write_text('# local session fixture', encoding='utf-8')
        os.environ.pop('PROJECT_LOCAL_ROOT', None)
        self.service = ProjectService(self.project)
        self.token = secrets.token_hex(32)

    def serve(self, local_session):
        httpd = make_server(self.service, self.token, 0, local_session=local_session)
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(lambda: (httpd.shutdown(), httpd.server_close(), thread.join(timeout=5)))
        return httpd.server_port

    def get(self, port, path, headers=None):
        headers = dict(headers or {})
        headers.setdefault('Host', f'127.0.0.1:{port}')
        with closing(http.client.HTTPConnection('127.0.0.1', port, timeout=10)) as conn:
            conn.request('GET', path, headers=headers)
            response = conn.getresponse()
            return response.status, response.read().decode('utf-8', 'replace')

    def test_the_served_page_is_handed_the_token_it_cannot_already_have(self):
        port = self.serve(True)
        status, body = self.get(port, '/api/local-session',
                               {'Sec-Fetch-Site': 'same-origin'})
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)['token'], self.token)

    def test_a_local_process_that_forges_the_host_is_still_refused(self):
        """`guard` allows an absent Sec-Fetch-Site; this endpoint must not."""
        port = self.serve(True)
        status, body = self.get(port, '/api/local-session')
        self.assertEqual(status, 403)
        self.assertEqual(json.loads(body)['error'], 'SAME_ORIGIN_REQUIRED')
        self.assertNotIn(self.token, body)

    def test_a_cross_site_or_foreign_origin_page_gets_nothing(self):
        port = self.serve(True)
        for headers, expected in (
                ({'Sec-Fetch-Site': 'cross-site'}, 'CROSS_SITE_DENIED'),
                ({'Sec-Fetch-Site': 'same-origin', 'Origin': 'http://evil.example'},
                 'ORIGIN_DENIED'),
                ({'Sec-Fetch-Site': 'same-origin', 'Host': 'evil.test'}, 'HOST_DENIED')):
            with self.subTest(**headers):
                status, body = self.get(port, '/api/local-session', headers)
                self.assertEqual(status, 403)
                self.assertEqual(json.loads(body)['error'], expected)
                self.assertNotIn(self.token, body)

    def test_the_endpoint_does_not_exist_when_auto_connect_is_off(self):
        port = self.serve(False)
        status, body = self.get(port, '/api/local-session',
                               {'Sec-Fetch-Site': 'same-origin'})
        self.assertNotEqual(status, 200)
        self.assertNotIn(self.token, body)

    def test_only_the_marked_page_knocks(self):
        port = self.serve(True)
        status, html = self.get(port, '/workbench')
        self.assertEqual(status, 200)
        self.assertIn('data-local-session="auto"', html)
        # The token is never baked into served bytes: the page must ask for it.
        self.assertNotIn(self.token, html)
        plain = self.serve(False)
        status, html = self.get(plain, '/workbench')
        self.assertEqual(status, 200)
        self.assertNotIn('data-local-session', html)


class WorkbenchCommandLineTests(unittest.TestCase):
    """`design-lab workbench` is the documented entry point for a personal install."""

    def run_launcher(self, extra):
        env = dict(os.environ)
        env.pop('PROJECT_LOCAL_ROOT', None)
        env['PYTHONPATH'] = str(ROOT / 'src')
        base = Path(tempfile.mkdtemp(dir=ROOT / '.project-local' / 'task-runtime'))
        project = base / 'project'
        project.mkdir()
        (project / 'AGENTS.md').write_text('# launcher fixture', encoding='utf-8')
        process = subprocess.Popen(
            [sys.executable, '-B', '-m', 'design_lab', '--project', str(project),
             'workbench', '--no-browser', '--port', '0', *extra],
            cwd=base, env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True, encoding='utf-8')
        try:
            line = self.first_line(process)
        except Exception:
            process.kill()
            raise
        return process, line, base

    @staticmethod
    def first_line(process):
        lines: queue.Queue = queue.Queue()
        threading.Thread(target=lambda: lines.put(process.stdout.readline()),
                         daemon=True).start()
        try:
            return lines.get(timeout=20)
        except queue.Empty:
            raise AssertionError(
                f'launcher printed no readiness line; stderr={process.stderr.read()[:400]}')

    def test_default_launch_never_prints_a_token(self):
        process, line, _ = self.run_launcher([])
        try:
            record = json.loads(line)
            self.assertEqual(record['status'], 'LISTENING')
            self.assertEqual(record['connection'], 'automatic')
            self.assertNotIn('token', record,
                             'a printed token is a secret in scrollback, in a log '
                             'capture, and in whatever the user copies somewhere else')
            self.assertNotIn('token_ttl', record)
            # And it must not appear anywhere in the line at all, under any key.
            self.assertNotRegex(line, r'[0-9a-f]{64}')
            port = record['port']
            with closing(http.client.HTTPConnection('127.0.0.1', port, timeout=10)) as conn:
                conn.request('GET', '/api/local-session',
                             headers={'Host': f'127.0.0.1:{port}',
                                      'Sec-Fetch-Site': 'same-origin'})
                body = json.loads(conn.getresponse().read())
            self.assertRegex(body['token'], r'^[0-9a-f]{64}$')
        finally:
            process.terminate()
            process.wait(timeout=10)

    def test_manual_connect_still_hands_over_a_token(self):
        process, line, _ = self.run_launcher(['--manual-connect'])
        try:
            record = json.loads(line)
            self.assertEqual(record['status'], 'LISTENING')
            self.assertRegex(record['token'], r'^[0-9a-f]{64}$')
            self.assertNotIn('connection', record)
        finally:
            process.terminate()
            process.wait(timeout=10)


if __name__ == '__main__':
    unittest.main()
