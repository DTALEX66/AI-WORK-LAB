# SPDX-License-Identifier: MIT
"""Design-system token documents over the real loopback API.

The write path is only a capability if a page can reach it and the refusal reason
survives the trip. These tests drive ``make_server`` over HTTP: POST the document,
read the persisted row back through the GET routes, restart the service over the
same root and read it again, and check that each refusal arrives as its own code
(with the field paths attached for an invalid document) rather than collapsing
into the generic INVALID_REQUEST.

E1 structural contract + E2 controlled-runtime local persistence over a synthetic
fixture. No host token tool, no jury acceptance, no release claim.
"""
from __future__ import annotations

import copy
import hashlib
import http.client
import json
import os
import secrets
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
DESIGN_SYSTEM = 'uiux-commercial-light'
NAME = 'anomaly-monitor-dark'

TOKENS = {
    'color': {'$type': 'color', 'brand': {'$value': '#2563EB'},
              'surface': {'$value': '{color.brand}'}},
    'scale': {'$type': 'dimension', 'space': {'md': {'$value': '16px'}}},
}


class TokenHttpTests(unittest.TestCase):
    def setUp(self):
        sys.path.insert(0, str(ROOT / 'src'))
        self.addCleanup(sys.path.remove, str(ROOT / 'src'))
        parent = ROOT / '.project-local' / 'task-runtime' / 'token-http-tests'
        parent.mkdir(parents=True, exist_ok=True)
        tmp = tempfile.TemporaryDirectory(dir=parent)
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        (self.root / 'AGENTS.md').write_text('# synthetic token HTTP project', encoding='utf-8')
        self.env = patch.dict(os.environ, {'PROJECT_LOCAL_ROOT': str(self.root / '.project-local')})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.project_id = None
        self.start_service()

    def start_service(self):
        """Boot a loopback server over the same root (call again for the restart)."""
        from design_lab.service import ProjectService
        from design_lab.http_service import make_server
        self.service = ProjectService(str(self.root))
        if self.project_id is None:
            self.project_id = self.service.create_project('Token HTTP')['id']
        self.token = secrets.token_hex(32)
        self.server = make_server(self.service, self.token, port=0)
        self.port = self.server.server_address[1]
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

        def _stop(server=self.server, thread=self.thread):
            server.shutdown()
            thread.join()
            server.server_close()
        self.addCleanup(_stop)

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
            response = conn.getresponse()
            payload = response.read()
            try:
                return response.status, json.loads(payload)
            except ValueError:
                return response.status, {'raw': payload}
        finally:
            conn.close()

    def key(self, text):
        return hashlib.sha256(text.encode()).hexdigest()

    def write(self, *, document=None, expected_version=0, name=DESIGN_SYSTEM, key='tok-1',
              extra=None, omit=None, actor='ALEX', actor_kind='human'):
        body = {'document': copy.deepcopy(TOKENS) if document is None else document,
                'expected_version': expected_version, 'actor': actor,
                'actor_kind': actor_kind, 'idempotency_key': self.key(key)}
        body.update(extra or {})
        for field in omit or ():
            body.pop(field, None)
        return self.request('POST', f'/api/projects/{self.project_id}/design-system-tokens/{name}',
                            body)

    # -- the chain over HTTP -----------------------------------------------
    def test_write_then_read_back_through_the_routes(self):
        status, created = self.write()
        self.assertEqual(status, 201, created)
        document = created['token_document']
        self.assertEqual(document['version'], 1)
        self.assertEqual(document['token_count'], 3)
        self.assertEqual(document['dtcg_schema_version'], '2025.10')

        listed_status, listed = self.request(
            path=f'/api/projects/{self.project_id}/design-system-tokens')
        self.assertEqual(listed_status, 200)
        self.assertEqual(listed['token_documents'], [document])

        single_status, single = self.request(
            path=f'/api/projects/{self.project_id}/design-system-tokens/{DESIGN_SYSTEM}')
        self.assertEqual((single_status, single['token_document']), (200, document))

        lineage_status, lineage = self.request(
            path=f'/api/projects/{self.project_id}/design-system-tokens/{DESIGN_SYSTEM}/lineage')
        self.assertEqual(lineage_status, 200)
        self.assertEqual([v['version'] for v in lineage['lineage']['versions']], [1])

    def test_revision_appends_a_version_and_the_chain_reads_back(self):
        first = self.write()[1]['token_document']
        revised = copy.deepcopy(TOKENS)
        revised['scale']['space']['md']['$value'] = '20px'
        second = self.write(document=revised, expected_version=first['version'],
                            key='tok-2')[1]['token_document']
        self.assertEqual(second['version'], 2)
        self.assertIsNone(second['superseded_by'])
        self.assertEqual(second['document']['scale']['space']['md']['$value'], '20px')
        # The pointer is read back from the persisted chain, not from the response
        # that was returned while v1 was still the tip.
        versions = self.request(
            path=f'/api/projects/{self.project_id}/design-system-tokens/{DESIGN_SYSTEM}/lineage'
        )[1]['lineage']['versions']
        self.assertEqual(versions[0]['superseded_by'], second['token_document_id'])

        live = self.request(
            path=f'/api/projects/{self.project_id}/design-system-tokens')[1]['token_documents']
        self.assertEqual([row['token_document_id'] for row in live],
                         [second['token_document_id']],
                         'the superseded version must not appear as a live document')
        lineage = self.request(
            path=f'/api/projects/{self.project_id}/design-system-tokens/{DESIGN_SYSTEM}/lineage'
        )[1]['lineage']
        self.assertEqual([v['version'] for v in lineage['versions']], [1, 2])
        self.assertEqual(lineage['versions'][0]['document']['scale']['space']['md']['$value'],
                         '16px', 'a revision must not rewrite the earlier version')

    def test_a_restart_reads_the_same_persisted_document_back(self):
        written = self.write()[1]['token_document']
        # Same root, brand-new service object and a brand-new server: the page must
        # see the row, not the process that wrote it.
        self.start_service()
        status, readback = self.request(
            path=f'/api/projects/{self.project_id}/design-system-tokens/{DESIGN_SYSTEM}')
        self.assertEqual(status, 200)
        self.assertEqual(readback['token_document'], written)

    def test_replayed_idempotency_key_returns_the_same_version(self):
        first = self.write()[1]['token_document']
        again = self.write()[1]['token_document']
        self.assertEqual(again, first)
        self.assertEqual(len(self.request(
            path=f'/api/projects/{self.project_id}/design-system-tokens'
        )[1]['token_documents']), 1)

    # -- refusals, each with its own reachable reason -----------------------
    def test_unknown_design_system_is_refused_by_name(self):
        status, body = self.write(name='no-such-system')
        self.assertEqual((status, body['error']), (400, 'UNKNOWN_DESIGN_SYSTEM'))
        self.assertEqual(self.request(
            path=f'/api/projects/{self.project_id}/design-system-tokens')[1]['token_documents'], [])

    def test_invalid_document_reaches_the_page_with_field_paths(self):
        broken = copy.deepcopy(TOKENS)
        broken['color']['brand']['$value'] = '#12'      # not a legal hex color
        status, body = self.write(document=broken)
        self.assertEqual((status, body['error']), (400, 'TOKEN_DOCUMENT_INVALID'),
                         'the generic INVALID_REQUEST would hide which field is wrong')
        self.assertTrue(any('color' in item for item in body['detail']), body['detail'])

    def test_a_legacy_document_is_refused_and_names_the_adapter(self):
        legacy = copy.deepcopy(TOKENS)
        legacy['text'] = {'$type': 'string', 'body': {'$value': 'hello'}}
        status, body = self.write(document=legacy)
        self.assertEqual(status, 400)
        self.assertEqual(body['error'], 'TOKEN_DOCUMENT_INVALID')
        self.assertIn('from_legacy_document', ' '.join(body['detail']))

    def test_a_stale_expected_version_is_refused_as_recoverable(self):
        self.write()
        self.write(expected_version=1, key='tok-2')
        status, body = self.write(expected_version=1, key='tok-3')
        self.assertEqual((status, body['error']), (409, 'STALE_REVISION'))
        tip = self.request(
            path=f'/api/projects/{self.project_id}/design-system-tokens/{DESIGN_SYSTEM}'
        )[1]['token_document']
        self.assertEqual(tip['version'], 2, 'a refused write must not move the chain')

    def test_exact_key_body_validation(self):
        status, body = self.write(extra={'surprise': 1})
        self.assertEqual((status, body['error']), (400, 'INVALID_PROJECT_FIELDS'))
        for field in ('document', 'expected_version', 'actor', 'actor_kind', 'idempotency_key'):
            status, body = self.write(omit=(field,), key='omit-' + field)
            self.assertEqual((status, body['error']), (400, 'INVALID_PROJECT_FIELDS'),
                             f'{field} is a required body key')

    def test_unknown_project_and_missing_document_are_404(self):
        foreign = '0' * 32
        status, body = self.request(
            'POST', f'/api/projects/{foreign}/design-system-tokens/{DESIGN_SYSTEM}',
            {'document': TOKENS, 'expected_version': 0, 'actor': 'ALEX',
             'actor_kind': 'human', 'idempotency_key': self.key('x')})
        self.assertEqual((status, body['error']), (404, 'PROJECT_NOT_FOUND'))
        status, body = self.request(
            path=f'/api/projects/{self.project_id}/design-system-tokens/{DESIGN_SYSTEM}')
        self.assertEqual((status, body['error']), (404, 'TOKEN_DOCUMENT_NOT_FOUND'))
        status, body = self.request(
            path=f'/api/projects/{self.project_id}/design-system-tokens/{NAME}/lineage')
        self.assertEqual((status, body['error']), (404, 'TOKEN_DOCUMENT_NOT_FOUND'))

    def test_routes_are_authenticated_and_method_checked(self):
        status, body = self.request(
            path=f'/api/projects/{self.project_id}/design-system-tokens',
            headers={'Authorization': 'Bearer ' + '0' * 64})
        self.assertEqual((status, body['error']), (401, 'UNAUTHORIZED'))
        status, body = self.request(
            'DELETE', f'/api/projects/{self.project_id}/design-system-tokens/{DESIGN_SYSTEM}')
        self.assertEqual((status, body['error']), (405, 'METHOD_NOT_ALLOWED'))

    def test_oversized_document_is_refused_before_validation(self):
        huge = copy.deepcopy(TOKENS)
        huge['padding'] = {'$type': 'color'}
        for index in range(5000):
            huge['padding'][f'c{index}'] = {'$value': '#000000'}
        status, body = self.write(document=huge)
        self.assertIn(status, (400, 413))
        self.assertIn(body['error'], ('BODY_TOO_LARGE', 'TOKEN_DOCUMENT_INVALID'))


if __name__ == '__main__':
    unittest.main()
