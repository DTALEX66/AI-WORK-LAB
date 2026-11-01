"""CL-06: the sidecar's read-only solution-library route.

The route is the only browser-facing read of the solution library. These tests pin that an empty
library is a measured EMPTY (not a missing field), that imported material is returned with its own
UNVERIFIED status and the version relation spelled out, and that an unreadable store is typed
SOURCE_ABSENT rather than an empty list that would read as "nothing to apply".
"""
from __future__ import annotations

import json
import sys
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "packages" / "client-neutral-core" / "scripts"))
sys.path.insert(0, str(ROOT / "services" / "orchestration"))

import project_temp
import solution_library
from sidecar import WorkflowSidecar, create_server

PROJECT_ROOT = ROOT


def _document(*, solution_id: str, title: str, keywords: list[str], version: str,
              issue_refs: list[str], steps: list[str]) -> dict:
    return solution_library.build_solution(
        solution_id=solution_id,
        title=title,
        software={"softwareId": "dsh", "softwareVersion": version, "platform": "windows",
                  "versionSource": "MEASURED"},
        source={"kind": "MANUAL", "ref": "owner-note-20261023", "updatedAt": "2026-10-23T06:00:00Z"},
        steps=steps,
        verification_steps=["重启客户端后从桌面快捷方式启动，确认窗口出现"],
        keywords=keywords,
        changes="第一版人工记录",
        issue_refs=issue_refs,
        limits=["只在 Windows 10.0.26100 上实测过"],
    )


class SolutionsViewTests(unittest.TestCase):
    def setUp(self) -> None:
        self.runtime = Path(project_temp.fixture_dir(prefix="sidecar-cl06-"))
        self.sidecar = WorkflowSidecar(PROJECT_ROOT, self.runtime)

    def tearDown(self) -> None:
        self.sidecar.close()
        project_temp.force_release(self.runtime)

    def _import(self, document: dict) -> dict:
        return solution_library.import_unverified(self.sidecar.store, document)

    def test_empty_library_is_a_measured_zero(self) -> None:
        view = self.sidecar.solutions_view()
        self.assertEqual(view["schemaVersion"], "worklab/solution-search/v1")
        self.assertEqual(view["status"], "EMPTY")
        self.assertEqual(view["results"], [])
        self.assertEqual(view["summary"]["solutionsRead"], 0)
        self.assertEqual(view["summary"]["mode"], "BROWSE")
        self.assertFalse(view["summary"]["aaosRequired"])
        self.assertIsNone(view["summary"]["modelUsed"])
        self.assertFalse(view["summary"]["inferencePerformed"])
        self.assertIn("实测的 0", view["reason"])

    def test_imported_solution_is_found_with_status_version_and_fingerprint(self) -> None:
        imported = self._import(_document(
            solution_id="sol-dsh-startup-crash", title="DSH 启动即崩溃的恢复步骤",
            keywords=["启动", "崩溃", "恢复"], version="0.2.0", issue_refs=["fp-dsh-startup"],
            steps=["结束残留进程", "从官方安装目录启动", "确认版本号"]))
        self.assertEqual(imported["status"], "IMPORTED")
        self._import(_document(
            solution_id="sol-codex-wrapper", title="Codex 包装器版本解析",
            keywords=["包装器", "版本"], version="1.0.0", issue_refs=[],
            steps=["检查 PATH"]))

        view = self.sidecar.solutions_view(
            query="崩溃", current_version="0.2.1", fingerprints=["fp-dsh-startup"])
        self.assertEqual(view["status"], "OK")
        self.assertEqual(len(view["results"]), 1)
        hit = view["results"][0]
        self.assertEqual(hit["solutionId"], "sol-dsh-startup-crash")
        self.assertEqual(hit["status"], "UNVERIFIED")
        self.assertFalse(hit["recommended"])
        self.assertTrue(hit["issueMatch"])
        self.assertEqual(hit["versionHint"]["state"], solution_library.VERSION_CHANGED)
        self.assertIn("0.2.0", hit["versionHint"]["message"])
        self.assertIn("0.2.1", hit["versionHint"]["message"])
        self.assertEqual(hit["limits"], ["只在 Windows 10.0.26100 上实测过"])
        self.assertEqual(view["summary"]["solutionsRead"], 2)
        self.assertEqual(view["summary"]["issueMatches"], 1)
        self.assertFalse(view["summary"]["truncated"])

    def test_unreadable_store_is_typed_source_absent(self) -> None:
        with mock.patch.object(self.sidecar.store, "list_solutions",
                               side_effect=RuntimeError("db locked")):
            view = self.sidecar.solutions_view(query="启动")
        self.assertEqual(view["status"], "SOURCE_ABSENT")
        self.assertEqual(view["results"], [])
        self.assertIsNone(view["summary"])
        self.assertIn("RuntimeError", view["reason"])

    def test_http_route_is_get_only_and_refuses_a_bad_limit(self) -> None:
        self._import(_document(
            solution_id="sol-dsh-startup-crash", title="DSH 启动即崩溃的恢复步骤",
            keywords=["启动", "崩溃"], version="0.2.0", issue_refs=["fp-dsh-startup"],
            steps=["结束残留进程"]))
        server = create_server(self.sidecar, port=0)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()

        def stop() -> None:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

        self.addCleanup(stop)
        port = int(server.server_address[1])
        url = (f"http://127.0.0.1:{port}/api/v1/solutions?q=%E5%90%AF%E5%8A%A8"
               f"&version=0.2.1&fingerprint=fp-dsh-startup")
        with urllib.request.urlopen(url, timeout=10) as response:
            body = json.loads(response.read().decode("utf-8"))
            self.assertEqual(response.headers["Cache-Control"], "no-store")
        self.assertEqual(body["status"], "OK")
        self.assertEqual(body["summary"]["currentVersion"], "0.2.1")
        self.assertEqual(body["summary"]["issueMatches"], 1)
        self.assertEqual(body["results"][0]["versionHint"]["state"], solution_library.VERSION_CHANGED)

        request = urllib.request.Request(
            f"http://127.0.0.1:{port}/api/v1/solutions", method="POST",
            data=b"{}", headers={"Content-Type": "application/json"})
        with self.assertRaises(urllib.error.HTTPError) as caught:
            urllib.request.urlopen(request, timeout=10)
        self.assertEqual(caught.exception.code, 405)

        with self.assertRaises(urllib.error.HTTPError) as caught:
            urllib.request.urlopen(
                f"http://127.0.0.1:{port}/api/v1/solutions?limit=abc", timeout=10)
        self.assertEqual(caught.exception.code, 400)
        refused = json.loads(caught.exception.read().decode("utf-8"))
        self.assertEqual(refused["status"], "REFUSED")
        self.assertIn("limit", refused["reason"])


if __name__ == "__main__":
    unittest.main()
