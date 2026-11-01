"""U03 (2026-10-07): the browser entry must serve the SAME production artifact Tauri ships.

The legacy `apps/observer/web` surface was justified for years as "the live browser
read-only entry". It is not: the sidecar's static root is documented and coded as a Vite
`dist/`, and nothing in the tree serves `web/` any more. These tests pin the browser path
to the real React artifact and to the read-only contract, so retiring the second UI cannot
later be re-justified as "we still need it for browsers".
"""
from __future__ import annotations

import json
import sys
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from tempfile import TemporaryDirectory

# Same preamble as the sibling sidecar tests: this file must run standalone
# (`python tests/workflow-assistance/test_sidecar_ui_browser_entry.py`), not only
# through the gate's PYTHONPATH, otherwise the regression command recorded in the
# ledger fails for a reason that has nothing to do with the contract it points at.
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "packages" / "client-neutral-core" / "scripts"))
sys.path.insert(0, str(ROOT / "services" / "orchestration"))

from sidecar import WorkflowSidecar, create_server

INDEX = "<!doctype html><title>WORK-LAB Observer</title><div id=root>react-app</div>\n"
ASSET = "console.log('production bundle')\n"
OUTSIDE = "NOT-FOR-THE-BROWSER\n"


class SidecarUiBrowserEntryTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = TemporaryDirectory()
        self.root = Path(self._tmp.name)
        dist = self.root / "dist"
        (dist / "assets").mkdir(parents=True)
        # newline="" keeps the fixture byte-exact: write_text's default translate
        # would turn LF into CRLF on Windows, and a real Vite dist ships LF. The
        # assertions below compare bytes, so the fixture must not lie first.
        (dist / "index.html").write_text(INDEX, encoding="utf-8", newline="")
        (dist / "assets" / "app.js").write_text(ASSET, encoding="utf-8", newline="")
        (self.root / "secret.txt").write_text(OUTSIDE, encoding="utf-8", newline="")
        self.dist = dist
        self.sidecar = WorkflowSidecar(self.root, self.root / "runtime")
        self.server = None
        self.thread = None

    def tearDown(self) -> None:
        # shutdown() before server_close(): closing the listening socket while
        # serve_forever() is still selecting makes the worker thread print an
        # OSError that looks like a failure in the log even though the test passed.
        if self.server is not None:
            self.server.shutdown()
            self.server.server_close()
        if self.thread is not None:
            self.thread.join(timeout=5)
        self._tmp.cleanup()

    def start(self, **kwargs):
        self.server = create_server(self.sidecar, "127.0.0.1", 0, **kwargs)
        self.base = f"http://127.0.0.1:{self.server.server_port}"
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def get(self, path: str):
        with urllib.request.urlopen(self.base + path, timeout=5) as resp:
            return resp.status, dict(resp.headers), resp.read()

    def test_root_serves_the_production_bundle_not_a_second_page(self) -> None:
        self.start(frontend_root=self.dist)
        status, headers, body = self.get("/")
        self.assertEqual(status, 200)
        self.assertTrue(headers["Content-Type"].startswith("text/html"))
        self.assertEqual(body.decode("utf-8"), INDEX)

    def test_assets_are_served_byte_for_byte(self) -> None:
        self.start(frontend_root=self.dist)
        status, headers, body = self.get("/assets/app.js")
        self.assertEqual(status, 200)
        self.assertEqual(headers["Content-Type"], "text/javascript; charset=utf-8")
        self.assertEqual(body.decode("utf-8"), ASSET)

    def test_unknown_route_falls_back_to_the_app_shell(self) -> None:
        """React owns client-side routing; the server must not invent a page."""
        self.start(frontend_root=self.dist)
        status, _, body = self.get("/models")
        self.assertEqual(status, 200)
        self.assertEqual(body.decode("utf-8"), INDEX)

    def test_api_routes_take_precedence_over_static_files(self) -> None:
        self.start(frontend_root=self.dist)
        status, headers, body = self.get("/api/v1/snapshot")
        self.assertEqual(status, 200)
        self.assertTrue(headers["Content-Type"].startswith("application/json"))
        payload = json.loads(body)
        self.assertEqual(payload.get("schemaVersion"), "workflow/snapshot/v3")

    def test_path_escape_is_refused_and_never_reads_the_parent(self) -> None:
        self.start(frontend_root=self.dist)
        with self.assertRaises(urllib.error.HTTPError) as caught:
            self.get("/../secret.txt")
        self.assertEqual(caught.exception.code, 403)
        self.assertNotIn(OUTSIDE, caught.exception.read().decode("utf-8", "replace"))

    def test_read_only_contract_holds_for_static_paths(self) -> None:
        self.start(frontend_root=self.dist)
        request = urllib.request.Request(self.base + "/", data=b"{}", method="POST")
        with self.assertRaises(urllib.error.HTTPError) as caught:
            urllib.request.urlopen(request, timeout=5)
        self.assertEqual(caught.exception.code, 405)

    def test_without_a_static_root_the_sidecar_stays_api_only(self) -> None:
        """The default must not change for existing callers."""
        self.start()
        with self.assertRaises(urllib.error.HTTPError) as caught:
            self.get("/")
        self.assertEqual(caught.exception.code, 404)
        status, _, _ = self.get("/api/v1/snapshot")
        self.assertEqual(status, 200)

    def test_a_static_root_without_an_index_is_not_fabricated(self) -> None:
        empty = self.root / "empty-dist"
        empty.mkdir()
        self.start(frontend_root=empty)
        with self.assertRaises(urllib.error.HTTPError) as caught:
            self.get("/")
        self.assertEqual(caught.exception.code, 404)


if __name__ == "__main__":
    unittest.main()
