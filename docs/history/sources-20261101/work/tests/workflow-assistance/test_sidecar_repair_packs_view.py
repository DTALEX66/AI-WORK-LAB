"""CL-07: the sidecar's read-only handoff-material route.

The route exists so the browser copies the projection's OWN `render_handoff_text` output instead of a
TypeScript re-spelling. These tests pin the three statements the route may make — SOURCE_ABSENT,
NO_OPEN_ISSUES and OK — and prove a generated pack still reads 未发送.
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

import composition_root
import project_temp
import repair_pack_projection
from sidecar import WorkflowSidecar, create_server

PROJECT_ROOT = ROOT


class RepairPacksViewTests(unittest.TestCase):
    def setUp(self) -> None:
        composition_root.clear_issues_cache()

    def tearDown(self) -> None:
        composition_root.clear_issues_cache()

    def test_blocked_task_yields_a_manual_pack_with_its_own_handoff_text(self) -> None:
        runtime = project_temp.fixture_dir(prefix="sidecar-cl07-")
        sidecar = WorkflowSidecar(PROJECT_ROOT, runtime)
        sidecar.store.upsert_task({
            "task_id": "WL-CL07-1", "project_id": "work-lab", "status": "BLOCKED",
            "created_at": "2026-10-23T01:00:00Z", "updated_at": "2026-10-23T02:00:00Z",
        })
        composition_root.clear_issues_cache()
        view = sidecar.repair_packs_view()
        try:
            self.assertEqual(view["schemaVersion"], "worklab/repair-packs-view/v1")
            self.assertEqual(view["status"], "OK")
            self.assertEqual(len(view["packs"]), 1)
            pack = view["packs"][0]
            self.assertEqual(pack["target"]["kind"], "MANUAL_COPY")
            self.assertEqual(pack["target"]["projectId"], "work-lab")
            self.assertIsNone(pack["target"]["adapter"])
            self.assertFalse(pack["handoff"]["sent"])
            self.assertFalse(pack["handoff"]["dispatched"])
            self.assertIn("tasks:WL-CL07-1", pack["handoffText"])
            # The text the route hands the browser is the same text the CLI's guard reads.
            self.assertEqual(repair_pack_projection.validate_handoff_text(pack, pack["handoffText"]), [])
            self.assertEqual(view["summary"]["sent"], False)
            self.assertEqual(view["summary"]["dispatchPerformed"], False)
        finally:
            sidecar.close()

    def test_absent_issues_is_not_an_empty_pack_list(self) -> None:
        runtime = project_temp.fixture_dir(prefix="sidecar-cl07-absent-")
        sidecar = WorkflowSidecar(PROJECT_ROOT, runtime)
        try:
            with mock.patch.object(sidecar, "v3_snapshot", return_value={
                "schemaVersion": "workflow/snapshot/v3", "projects": [], "executions": [],
            }):
                view = sidecar.repair_packs_view()
            self.assertEqual(view["status"], "SOURCE_ABSENT")
            self.assertEqual(view["packs"], [])
            self.assertIsNone(view["summary"])
            self.assertIsNone(view["issuesSummary"])
            self.assertIn("没有来源作答", view["reason"])
        finally:
            sidecar.close()

    def test_empty_issues_with_a_complete_scope_is_no_open_issues(self) -> None:
        runtime = project_temp.fixture_dir(prefix="sidecar-cl07-empty-")
        sidecar = WorkflowSidecar(PROJECT_ROOT, runtime)
        try:
            view = sidecar.repair_packs_view()
            self.assertEqual(view["status"], "NO_OPEN_ISSUES")
            self.assertEqual(view["packs"], [])
            self.assertEqual(view["summary"]["openIssueCount"], 0)
            self.assertTrue(view["issuesSummary"]["complete"])
        finally:
            sidecar.close()

    def test_an_issue_without_a_project_names_the_refusal(self) -> None:
        runtime = project_temp.fixture_dir(prefix="sidecar-cl07-orphan-")
        sidecar = WorkflowSidecar(PROJECT_ROOT, runtime)
        sidecar.store.upsert_task({
            "task_id": "WL-CL07-ORPHAN", "project_id": "", "status": "BLOCKED",
            "created_at": "2026-10-23T01:00:00Z", "updated_at": "2026-10-23T02:00:00Z",
        })
        composition_root.clear_issues_cache()
        try:
            view = sidecar.repair_packs_view()
            self.assertEqual(view["status"], "NO_PACK")
            self.assertEqual(view["packs"], [])
            self.assertEqual(view["summary"]["issuesWithoutProject"], 1)
            self.assertIn("issue-has-no-project", view["summary"]["refusalReasons"])
        finally:
            sidecar.close()

    def test_http_route_is_get_only_and_carries_the_view(self) -> None:
        runtime = project_temp.fixture_dir(prefix="sidecar-cl07-http-")
        sidecar = WorkflowSidecar(PROJECT_ROOT, runtime)
        sidecar.store.upsert_task({
            "task_id": "WL-CL07-HTTP", "project_id": "work-lab", "status": "BLOCKED",
            "created_at": "2026-10-23T01:00:00Z", "updated_at": "2026-10-23T02:00:00Z",
        })
        composition_root.clear_issues_cache()
        server = create_server(sidecar, port=0)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()

        def stop() -> None:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

        self.addCleanup(stop)
        port = int(server.server_address[1])
        with urllib.request.urlopen(
                f"http://127.0.0.1:{port}/api/v1/repair-packs", timeout=10) as response:
            body = json.loads(response.read().decode("utf-8"))
            self.assertEqual(response.headers["Cache-Control"], "no-store")
        self.assertEqual(body["schemaVersion"], "worklab/repair-packs-view/v1")
        self.assertEqual(body["status"], "OK")
        request = urllib.request.Request(
            f"http://127.0.0.1:{port}/api/v1/repair-packs", method="POST",
            data=b"{}", headers={"Content-Type": "application/json"})
        with self.assertRaises(urllib.error.HTTPError) as caught:
            urllib.request.urlopen(request, timeout=10)
        self.assertEqual(caught.exception.code, 405)


if __name__ == "__main__":
    unittest.main()
