"""Gate: the sidecar's read-only 405 must survive a keep-alive connection at the byte level.

The sidecar serves HTTP/1.1, so a connection stays open after a response. A refused write that leaves its
request body in the buffer makes the NEXT response on that connection begin with the caller's JSON, and a
client then reads a broken status line where the read-only contract promises 405. The product already
drains (``refuse_write`` -> ``_drain_request_body``), but until now the only proof at the byte level was on
the Control server, and ERR-187's own boundary claimed the sidecar needed a subprocess boot because its
handler class is nested inside the serving function. That claim was never tested: ``create_server`` is a
module-level function that binds port 0, so this test speaks raw bytes to it in-process.

The control case is the reason to believe the rest. A deliberately naive refusal (deny without draining)
is served on the same client code path, and the second request must come back desynchronized. An assertion
that cannot fail guards nothing.

Evidence level: SYNTHETIC/INTEGRATED local loopback, one process, one runtime root.
"""
from __future__ import annotations

import socket
import sys
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "packages" / "client-neutral-core" / "scripts"))
sys.path.insert(0, str(ROOT / "services" / "orchestration"))

from sidecar import WorkflowSidecar, create_server  # noqa: E402

BODY = b'{"marker":"unconsumed"}'  # 25 bytes; Content-Length is sent to match


def _exchange(host: str, port: int) -> tuple[bytes, bytes]:
    """Two requests on one keep-alive socket: a refused write, then a read."""
    with socket.create_connection((host, port), timeout=5) as sock:
        sock.sendall(b"POST /api/v1/snapshot HTTP/1.1\r\nHost: 127.0.0.1\r\n"
                    b"Content-Type: application/json\r\nContent-Length: %d\r\n"
                    b"Connection: keep-alive\r\n\r\n%s" % (len(BODY), BODY))
        first = _read_response(sock)
        sock.sendall(b"GET /api/v1/snapshot HTTP/1.1\r\nHost: 127.0.0.1\r\n"
                     b"Connection: keep-alive\r\n\r\n")
        second = _read_status_line(sock)
    return first, second


def _read_response(sock: socket.socket) -> bytes:
    """Read exactly one response: headers, then the body its own Content-Length promises."""
    buffer = b""
    while b"\r\n\r\n" not in buffer:
        chunk = sock.recv(4096)
        if not chunk:
            return buffer
        buffer += chunk
    head, _, tail = buffer.partition(b"\r\n\r\n")
    declared = 0
    for line in head.split(b"\r\n")[1:]:
        name, _, value = line.partition(b":")
        if name.strip().lower() == b"content-length":
            declared = int(value.strip() or 0)
    while len(tail) < declared:
        chunk = sock.recv(4096)
        if not chunk:
            break
        tail += chunk
    return head + b"\r\n\r\n" + tail


def _read_status_line(sock: socket.socket) -> bytes:
    buffer = b""
    while b"\r\n" not in buffer:
        chunk = sock.recv(4096)
        if not chunk:
            break
        buffer += chunk
    return buffer.split(b"\r\n", 1)[0]


class SidecarWriteRefusalBytes(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.sidecar = WorkflowSidecar(self.root, self.root / "runtime")
        self.server = create_server(self.sidecar, "127.0.0.1", 0)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self._stop)

    def _stop(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)
        self.sidecar.close()
        self._tmp.cleanup()

    def test_the_refusal_and_the_next_read_both_arrive_whole_on_one_connection(self) -> None:
        first, second = _exchange("127.0.0.1", self.server.server_port)
        status_line = first.split(b"\r\n", 1)[0]
        self.assertTrue(status_line.startswith(b"HTTP/1."), status_line)
        self.assertIn(b" 405 ", status_line, status_line)
        self.assertNotIn(b"marker", first,
                         "the refused POST's own body came back ahead of the denial")
        self.assertTrue(first.split(b"\r\n\r\n", 1)[1], "the denial carried no body")
        self.assertEqual(second, b"HTTP/1.1 200 OK",
                         f"the second response on the kept-alive connection did not start cleanly: "
                         f"{second!r} -- a refusal that leaves its body unread poisons the next reply")

    def test_a_refusal_without_draining_really_does_break_the_next_response(self) -> None:
        """The control: the same client code against a server that denies sloppily must go wrong.

        Without this case the test above could be passing because nothing can ever fail. Measured here, the
        naive server reads the leftover JSON as a request line, fails to parse it, and the handler dies --
        so the second response arrives as an abort or as nothing at all rather than `HTTP/1.1 200 OK`. That
        is the same hazard the sidecar drains: a kept-alive connection whose next reply is not a status line.
        """
        naive = _NaiveRefusalServer()
        naive.start()
        try:
            first, second = _exchange("127.0.0.1", naive.port)
            self.assertIn(b" 405 ", first.split(b"\r\n", 1)[0])
            self.assertNotEqual(second, b"HTTP/1.1 200 OK",
                                "the naive server did not desynchronize, so this control proves nothing "
                                "and the guard above is measuring the wrong thing")
        finally:
            naive.stop()


class _NaiveRefusalServer:
    """Deny with 405 and never read the body -- the mistake, served on purpose."""

    def __init__(self) -> None:
        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def do_POST(self):  # noqa: N802 - http.server naming
                payload = b'{"error":"read_only"}'
                self.send_response(405)
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            def do_GET(self):  # noqa: N802
                payload = b'{"ok":true}'
                self.send_response(200)
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            def log_message(self, *args):  # keep the test output honest
                pass

        self._httpd = _QuietServer(("127.0.0.1", 0), Handler)
        self.port = self._httpd.server_port
        self._thread = None

    def start(self) -> None:
        self._thread = threading.Thread(target=self._httpd.serve_forever, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._httpd.shutdown()
        self._httpd.server_close()
        if self._thread is not None:
            self._thread.join(timeout=5)


class _QuietServer(ThreadingHTTPServer):
    """The desync is the finding; the abandoned handler traceback is not a failure of this test."""

    def handle_error(self, request, client_address) -> None:  # noqa: D102
        pass


if __name__ == "__main__":
    unittest.main()
