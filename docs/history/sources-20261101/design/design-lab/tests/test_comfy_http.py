# SPDX-License-Identifier: MIT
"""Actual loopback transport, no real model or shared Comfy instance."""
import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
import sys
import threading
import time
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'src'))


class ComfyHttpTests(unittest.TestCase):
    def setUp(self):
        self.requests = []
        self.status = 200
        self.response = json.dumps({'system': {'comfyui_version': 'fixture'}}).encode()
        self.drop_post = True
        self.submitted = None
        self.extra_length = 0
        self.drip = False
        owner = self
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass
            def do_GET(self):
                owner.requests.append(('GET', self.path))
                self.reply()
            def reply(self):
                body = owner.response
                self.send_response(owner.status)
                self.send_header('Location', '/must-not-follow')
                self.send_header('Content-Length', str(len(body) + owner.extra_length))
                self.end_headers()
                try:
                    if owner.drip:
                        for byte in body:
                            self.wfile.write(bytes([byte]))
                            self.wfile.flush()
                            time.sleep(0.03)
                    else:
                        self.wfile.write(body)
                except OSError:
                    pass  # Test client deliberately closes its own socket.
            def do_POST(self):
                owner.submitted = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                owner.requests.append(('POST', self.path))
                # Dispatch may have happened, but response is lost.
                if owner.drop_post:
                    self.close_connection = True
                else:
                    self.reply()
        self.server = HTTPServer(('127.0.0.1', 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.stop)

    def stop(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(5)

    def test_stats_uses_fixed_loopback_endpoint(self):
        from design_lab.generators.comfy_http import ComfyHttp
        result = ComfyHttp(self.server.server_port).system_stats()
        self.assertEqual(result, {'system': {'comfyui_version': 'fixture'}})
        self.assertEqual(self.requests, [('GET', '/system_stats')])

    def test_submit_and_history_preserve_identity_and_graph(self):
        from design_lab.generators.comfy_http import ComfyHttp
        self.drop_post = False
        self.response = b'{"prompt_id":"prompt-1","number":1,"node_errors":{}}'
        client = ComfyHttp(self.server.server_port)
        graph = {'1': {'class_type': 'EmptyImage', 'inputs': {'width': 64}}}
        self.assertEqual(client.submit(graph, 'client-1')['prompt_id'], 'prompt-1')
        self.assertEqual(self.submitted, {'prompt': graph, 'client_id': 'client-1'})
        self.response = b'{"prompt-1":{"outputs":{}}}'
        self.assertEqual(client.history('prompt-1'), {'prompt-1': {'outputs': {}}})
        self.assertEqual(self.requests, [('POST', '/prompt'), ('GET', '/history/prompt-1')])

    def test_redirect_is_not_followed(self):
        from design_lab.generators.comfy_http import ComfyHttp, ComfyTransportError
        self.status = 302
        with self.assertRaises(ComfyTransportError) as error:
            ComfyHttp(self.server.server_port).system_stats()
        self.assertFalse(error.exception.outcome_unknown)
        self.assertEqual(self.requests, [('GET', '/system_stats')])

    def test_ambiguous_or_nonfinite_json_is_rejected(self):
        from design_lab.generators.comfy_http import ComfyHttp, ComfyTransportError
        for body in (b'{"x":1,"x":2}', b'{"x":NaN}', b'{"x":Infinity}', b'{"x":1e999}'):
            self.response = body
            with self.subTest(body=body), self.assertRaises(ComfyTransportError):
                ComfyHttp(self.server.server_port).system_stats()

    def test_truncated_http_body_is_not_accepted_as_complete_json(self):
        from design_lab.generators.comfy_http import ComfyHttp, ComfyTransportError
        self.response = b'{}'
        self.extra_length = 10
        with self.assertRaises(ComfyTransportError):
            ComfyHttp(self.server.server_port).system_stats()

    def test_slow_drip_cannot_extend_total_deadline(self):
        from design_lab.generators.comfy_http import ComfyHttp, ComfyTransportError
        self.drip = True
        self.response = b'{"slow":"abcdefghijklmnop"}'
        # Only shorten policy time; the real socket/read path is not mocked.
        with patch('design_lab.generators.comfy_http._DEADLINE_SECONDS', 0.15, create=True):
            started = time.monotonic()
            with self.assertRaises(ComfyTransportError):
                ComfyHttp(self.server.server_port).system_stats()
            self.assertLess(time.monotonic() - started, 0.7)

    def test_oversize_graph_does_not_dispatch(self):
        from design_lab.generators.comfy_http import ComfyHttp
        with self.assertRaises(ValueError):
            ComfyHttp(self.server.server_port).submit({'1': {'text': 'x' * 4_000_001}}, 'client-1')
        self.assertEqual(self.requests, [])

    def test_success_without_prompt_id_remains_unknown(self):
        from design_lab.generators.comfy_http import ComfyHttp, ComfyTransportError
        self.drop_post = False
        self.response = b'{}'
        with self.assertRaises(ComfyTransportError) as error:
            ComfyHttp(self.server.server_port).submit({'1': {}}, 'client-1')
        self.assertTrue(error.exception.outcome_unknown)
        self.assertEqual(self.requests, [('POST', '/prompt')])

    def test_lost_submit_response_is_unknown_and_not_retried(self):
        from design_lab.generators.comfy_http import ComfyHttp, ComfyTransportError
        with self.assertRaises(ComfyTransportError) as captured:
            ComfyHttp(self.server.server_port).submit({'1': {'class_type': 'EmptyImage', 'inputs': {}}}, 'client-1')
        self.assertTrue(captured.exception.outcome_unknown)
        self.assertEqual(self.requests, [('POST', '/prompt')])

    def test_invalid_port_and_history_identity_never_reach_server(self):
        from design_lab.generators.comfy_http import ComfyHttp
        for port in (True, 0, 65536, '8188'):
            with self.subTest(port=port), self.assertRaises(ValueError):
                ComfyHttp(port)
        for identity in ('../queue', 'x?clear=true', '', 'http://remote'):
            with self.subTest(identity=identity), self.assertRaises(ValueError):
                ComfyHttp(self.server.server_port).history(identity)
        self.assertEqual(self.requests, [])


if __name__ == '__main__':
    unittest.main()
