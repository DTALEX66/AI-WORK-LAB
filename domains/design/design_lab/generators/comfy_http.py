# SPDX-License-Identifier: MIT
"""Bounded loopback Comfy transport; not a model qualification or task ledger.

The caller persists dispatch intent before submit and handles uncertain output.
No retries, redirects, generic URL API, cancellation or shared process control.
"""
import http.client
import json
import re
import socket
import threading
import time

_ID = re.compile(r'[A-Za-z0-9][A-Za-z0-9_-]{0,127}')
_LIMIT = 4_000_000
_DEADLINE_SECONDS = 10


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('DUPLICATE_JSON_KEY')
        result[key] = value
    return result


class ComfyTransportError(RuntimeError):
    def __init__(self, *, outcome_unknown):
        super().__init__('COMFY_TRANSPORT_UNVERIFIED')
        self.outcome_unknown = outcome_unknown


class ComfyHttp:
    def __init__(self, port):
        if type(port) is not int or not 1 <= port <= 65535:
            raise ValueError('INVALID_COMFY_PORT')
        self.port = port

    def system_stats(self):
        return self._exchange('GET', '/system_stats')

    def history(self, prompt_id):
        if not isinstance(prompt_id, str) or not _ID.fullmatch(prompt_id):
            raise ValueError('INVALID_COMFY_PROMPT_ID')
        return self._exchange('GET', '/history/' + prompt_id)

    def submit(self, graph, client_id):
        if not isinstance(graph, dict) or not graph:
            raise ValueError('INVALID_COMFY_GRAPH')
        if not isinstance(client_id, str) or not _ID.fullmatch(client_id):
            raise ValueError('INVALID_COMFY_CLIENT_ID')
        # JSON serialization fails before any socket opens. Model/node/graph
        # qualification remains the responsibility of the owning task layer.
        body = json.dumps({'prompt': graph, 'client_id': client_id},
                          allow_nan=False, separators=(',', ':')).encode('utf-8')
        if len(body) > _LIMIT:
            raise ValueError('COMFY_GRAPH_TOO_LARGE')
        result = self._exchange('POST', '/prompt', body)
        identity = result.get('prompt_id')
        if not isinstance(identity, str) or not _ID.fullmatch(identity):
            raise ComfyTransportError(outcome_unknown=True)
        return result

    def _exchange(self, method, path, body=None):
        started = time.monotonic()
        connection = http.client.HTTPConnection('127.0.0.1', self.port, timeout=_DEADLINE_SECONDS)
        deadline = None
        try:
            connection.connect()
            remaining = _DEADLINE_SECONDS - (time.monotonic() - started)
            if remaining <= 0:
                raise TimeoutError('COMFY_DEADLINE')
            owned_socket = connection.sock
            def expire():
                # Interrupt only this request's socket, never a shared host.
                try:
                    owned_socket.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass
            deadline = threading.Timer(remaining, expire)
            deadline.daemon = True
            deadline.start()
            connection.request(method, path, body, {'Content-Type': 'application/json'})
            response = connection.getresponse()
            if response.status != 200:
                raise ValueError('UNEXPECTED_HTTP_STATUS')
            raw = response.read(_LIMIT + 1)
            if len(raw) > _LIMIT:
                raise ValueError('RESPONSE_TOO_LARGE')
            if response.length not in (None, 0):
                raise ValueError('INCOMPLETE_HTTP_BODY')
            result = json.loads(raw, object_pairs_hook=_unique_object)
            # Reject NaN/Infinity and numeric overflow, including nested values.
            json.dumps(result, allow_nan=False)
            if not isinstance(result, dict):
                raise ValueError('EXPECTED_JSON_OBJECT')
            if time.monotonic() - started >= _DEADLINE_SECONDS:
                raise TimeoutError('COMFY_DEADLINE')
            return result
        except (OSError, http.client.HTTPException, ValueError, RecursionError) as exc:
            # Even a non-200 POST may follow partial execution in an unknown
            # instance: never turn an uncertain submit into a retryable failure.
            raise ComfyTransportError(outcome_unknown=method == 'POST') from exc
        finally:
            if deadline is not None:
                deadline.cancel()
            connection.close()
