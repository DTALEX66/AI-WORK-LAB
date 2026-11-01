from __future__ import annotations

import json
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "packages" / "client-neutral-core" / "scripts"))
sys.path.insert(0, str(ROOT / "services" / "orchestration"))
from sidecar import WorkflowSidecar, create_server  # noqa: E402
from canonical_store import CanonicalStore  # noqa: E402

class SidecarTests(unittest.TestCase):
    def test_health_and_projection_are_get_only(self):
        with tempfile.TemporaryDirectory() as raw:
            sidecar = WorkflowSidecar(ROOT, Path(raw))
            sidecar.store.append_telemetry({"event_id": "evt-1", "project_id": "work-lab", "producer": "fixture", "outcome": "completed"})
            sidecar.store.upsert_task({"task_id": "task-1", "project_id": "work-lab", "status": "QUEUED"})
            first_event_id = sidecar.publish_observed()
            server = create_server(sidecar)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                base = f"http://127.0.0.1:{server.server_port}"
                with urlopen(base + "/healthz") as response:
                    self.assertEqual(response.status, 200)
                    self.assertEqual(json.load(response)["ledgerOwner"], "workflow-assistance")
                blocked = Request(base + "/healthz", headers={"Origin": "https://external.invalid"})
                with self.assertRaises(Exception):
                    urlopen(blocked)
                evil_suffix = Request(base + "/healthz", headers={"Origin": "http://127.0.0.1.evil.invalid"})
                with self.assertRaises(Exception):
                    urlopen(evil_suffix)
                allowed = Request(base + "/healthz", headers={"Origin": "http://localhost:8765"})
                with urlopen(allowed) as response:
                    self.assertEqual(response.headers["Access-Control-Allow-Origin"], "http://localhost:8765")
                with urlopen(base + "/api/projection") as response:
                    self.assertEqual(response.status, 200)
                    projection = json.load(response)
                    self.assertEqual(projection["schema_version"], "workflow/sidecar-projection/v1")
                    self.assertEqual(projection["tasks"], {"count": 1, "by_status": {"QUEUED": 1}})
                with urlopen(base + "/api/v1/events") as response:
                    self.assertEqual(response.headers["Content-Type"].split(";")[0], "text/event-stream")
                    self.assertIsNone(response.headers.get("Content-Length"))
                    initial = b"".join(response.readline() for _ in range(5))
                    # P0-4: first frame is the v3 snapshot event (named event),
                    # not the legacy anonymous observed message.
                    self.assertIn(b"event: snapshot", initial)
                    sidecar.store.upsert_task({"task_id": "task-2", "project_id": "work-lab", "status": "RUNNING"})
                    sidecar.publish_observed()
                    delta = b"".join(response.readline() for _ in range(4))
                    # P0-4: revision hub publishes a named observed frame after a write.
                    self.assertIn(b"event: observed", delta)
                reconnect = Request(base + "/api/v1/events", headers={"Last-Event-ID": "0"})
                with urlopen(reconnect) as response:
                    body = b"".join(response.readline() for _ in range(3))
                    # P0-4: reconnect replays persisted frames past the cursor
                    # (observed, revision 1) — never the empty legacy array.
                    self.assertIn(b"event: observed", body)
                request = Request(base + "/healthz", method="POST")
                with self.assertRaises(Exception):
                    urlopen(request)
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)

    def test_bind_lock_descriptor_and_get_projection_are_fail_closed(self):
        with tempfile.TemporaryDirectory() as raw:
            runtime = Path(raw)
            sidecar = WorkflowSidecar(ROOT, runtime)
            with self.assertRaises(ValueError):
                create_server(sidecar, host="0.0.0.0")

            server = create_server(sidecar)
            endpoint = runtime / "sidecar-endpoint.json"
            self.assertTrue(endpoint.is_file())
            descriptor = json.loads(endpoint.read_text(encoding="utf-8"))
            self.assertEqual(descriptor["schemaVersion"], "workflow/sidecar-endpoint/v1")
            self.assertEqual(descriptor["port"], server.server_port)
            with self.assertRaises(RuntimeError):
                create_server(WorkflowSidecar(ROOT, runtime))

            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                with urlopen(f"http://127.0.0.1:{server.server_port}/api/projection") as response:
                    projection = json.load(response)
                self.assertEqual(projection["tasks"], {"count": 0, "by_status": {}})
                self.assertTrue((runtime / "canonical.sqlite").exists())
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)
            self.assertFalse(endpoint.exists())

            replacement = create_server(WorkflowSidecar(ROOT, runtime))
            replacement.server_close()

    def test_live_watcher_publishes_an_external_writer_delta(self):
        with tempfile.TemporaryDirectory() as raw:
            runtime = Path(raw)
            sidecar = WorkflowSidecar(ROOT, runtime)
            sidecar.start_live_updates(interval_seconds=0.02)
            subscriber = sidecar.live.subscribe()
            writer = CanonicalStore(runtime / "canonical.sqlite")
            try:
                # P0-4: watcher no longer declares LIVE; the v3 transport
                # verdict comes only from the live gate.
                self.assertEqual(sidecar.projection()["mode"], "SNAPSHOT")
                self.assertEqual(sidecar.v3_snapshot()["transport"]["transportState"], "OFFLINE")
                writer.upsert_task({"task_id": "external-1", "project_id": "work-lab", "status": "RUNNING"})
                deadline = time.monotonic() + 2.0
                message = None
                while time.monotonic() < deadline:
                    try:
                        candidate = subscriber.get(timeout=0.1)
                    except Exception:
                        continue
                    if candidate.data.get("tasks", {}).get("count") == 1:
                        message = candidate
                        break
                self.assertIsNotNone(message, "external canonical write did not produce an SSE delta")
                # P0-4: watcher no longer flips to LIVE; legacy projection stays SNAPSHOT.
                self.assertEqual(message.data["mode"], "SNAPSHOT")
            finally:
                writer.close()
                sidecar.live.unsubscribe(subscriber)
                sidecar.close()

if __name__ == "__main__":
    unittest.main()
