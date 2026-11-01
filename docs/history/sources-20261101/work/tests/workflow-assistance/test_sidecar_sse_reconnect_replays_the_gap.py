"""Mandatory gate: a connection that DIES mid-stream comes back with its cursor and loses no event.

The sidecar has implemented `Last-Event-ID` replay since `services/orchestration/sse_revision.py:75-122`
(a 1000-frame ring, replay of `seq > cursor`, and three named `resync_required` reasons). What was never
proved is the case the header exists for: every existing check opens a NEW connection and asks for a cursor
(`tests/workflow-assistance/test_sidecar.py:59-64` sends `Last-Event-ID: 0` on a fresh request), so the
scenario "the stream was up, then it was not, and events happened in the gap" had no readback. The CDP
instrument for this round used a stub server whose `id:` was a per-connection counter decoupled from the
revision, and it never dropped the connection — it proved browser-side revision ordering and nothing about
reconnection.

Everything here runs against the real `WorkflowSidecar` + real `SseRevisionHub` + real HTTP, and the socket is
closed by the test to create the outage.

One asymmetry worth stating because a reader will hit it: the client-side `EventSource` handles the reconnect
itself (the browser sends the last `id:` it saw), and the Observer re-reads the snapshot on every `open`
(`apps/observer/frontend/src/lib/api.ts`), so a resumed stream is conservative by design. This gate proves the
server half is real — which is what makes that conservative path cheap enough to keep.
"""
from __future__ import annotations

import http.client
import json
import sys
import threading
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "packages" / "client-neutral-core" / "scripts"))
sys.path.insert(0, str(ROOT / "services" / "orchestration"))

import project_temp  # noqa: E402
from canonical_store import CanonicalStore  # noqa: E402
from sidecar import WorkflowSidecar, create_server  # noqa: E402


def parse_frames(blob: bytes) -> list[dict]:
    """Split an SSE body into `{event, id, data}` dicts, keeping order."""
    frames = []
    for chunk in blob.decode("utf-8", "replace").split("\n\n"):
        if not chunk.strip():
            continue
        event, ident, data_lines = None, None, []
        for line in chunk.splitlines():
            if line.startswith("event:"):
                event = line.split(":", 1)[1].strip()
            elif line.startswith("id:"):
                ident = line.split(":", 1)[1].strip()
            elif line.startswith("data:"):
                data_lines.append(line.split(":", 1)[1].lstrip())
        frames.append({"event": event, "id": ident, "data": "\n".join(data_lines)})
    return frames


class Stream:
    """One live HTTP connection the test can kill without asking the server's permission.

    The timeout is set on the connection, which is also the per-`readline` socket timeout:
    `http.client.HTTPConnection.sock` is not reliably populated after `getresponse()`, so there is no second
    place to set it.
    """

    def __init__(self, port: int, last_event_id: str | None = None, timeout: float = 8.0) -> None:
        self.connection = http.client.HTTPConnection("127.0.0.1", port, timeout=timeout)
        headers = {"Last-Event-ID": last_event_id} if last_event_id is not None else {}
        self.connection.request("GET", "/api/v1/events", headers=headers)
        self.response = self.connection.getresponse()
        self.buffer = b""

    def read_frames(self, count: int) -> list[dict]:
        frames: list[dict] = []
        while len(frames) < count:
            chunk = self.response.readline()
            if not chunk:
                break
            self.buffer += chunk
            if chunk in (b"\n", b"\r\n"):
                frames.extend(parse_frames(self.buffer))
                self.buffer = b""
        return frames

    def kill(self) -> None:
        """Drop the connection the way a real outage does: no goodbye, socket closed on our side."""
        try:
            self.connection.close()
        except OSError:
            pass


class ReconnectReplayTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fixture = project_temp.fixture_dir("sse-reconnect-")
        self.sidecar = WorkflowSidecar(ROOT, self.fixture)
        self.server = create_server(self.sidecar)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.port = self.server.server_port

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.sidecar.store.close()
        project_temp.force_release(self.fixture)

    def publish(self, note: str) -> int:
        """Write a fact, publish it, and return the SSE CURSOR — which is not what `publish_observed`
        returns: that answers with the legacy hub's UUID, while `/api/v1/events` frames carry the
        persistent revision (`sidecar.py:231-240`). Reading the wrong one is exactly how a cursor test
        can look meaningful and prove nothing."""
        self.sidecar.store.upsert_task({"task_id": f"task-{note}", "project_id": "work-lab",
                                        "status": "RUNNING"})
        self.sidecar.publish_observed()
        return self.sidecar.revision_hub.current_revision

    def test_a_dropped_connection_replays_every_event_from_the_gap_and_keeps_streaming(self) -> None:
        first = Stream(self.port)
        self.assertEqual(first.response.status, 200)
        bootstrap = first.read_frames(1)
        self.assertEqual([f["event"] for f in bootstrap], ["snapshot"])
        cursor_at_open = int(bootstrap[0]["id"])
        self.assertTrue(cursor_at_open >= 0)

        held = self.publish("held")
        live = first.read_frames(1)
        self.assertEqual([f["id"] for f in live], [str(held)],
                         "the live frame did not carry the revision the publish returned")
        first.kill()

        # Everything published while nobody was connected must arrive after the cursor, in order, once.
        during_outage = [self.publish(f"gap-{index}") for index in range(2)]
        self.assertTrue(all(seq > held for seq in during_outage))

        resumed = Stream(self.port, last_event_id=str(held))
        frames = resumed.read_frames(len(during_outage))
        replayed = [int(f["id"]) for f in frames]
        self.assertEqual(replayed, during_outage,
                         f"replay must be exactly the gap, in order: got {replayed}")
        self.assertEqual([f["event"] for f in frames], ["observed"] * len(during_outage))
        self.assertNotIn(str(held), [f["id"] for f in frames],
                         "the cursor itself was re-sent: a reader applying frames idempotently would not "
                         "notice, but a counter would double-count")

        after = self.publish("post-resume")
        continued = resumed.read_frames(1)
        self.assertEqual([int(f["id"]) for f in continued], [after],
                         "the resumed connection stopped after the replay — a replay-once stream is not a "
                         "live subscription")
        resumed.kill()

    def test_a_non_numeric_cursor_is_answered_with_a_named_resync_not_silence(self) -> None:
        current = self.publish("baseline")
        stream = Stream(self.port, last_event_id="not-a-sequence")
        frames = stream.read_frames(1)
        self.assertEqual([f["event"] for f in frames], ["resync_required"], frames)
        payload = json.loads(frames[0]["data"])
        self.assertEqual(payload["reason"], "invalid_cursor")
        self.assertEqual(int(payload["revision"]), current,
                         "the resync must hand the reader the watermark it can trust")
        stream.kill()

    def test_a_cursor_from_the_future_is_refused_by_name(self) -> None:
        current = self.publish("baseline")
        stream = Stream(self.port, last_event_id=str(current + 5000))
        frames = stream.read_frames(1)
        payload = json.loads(frames[0]["data"])
        self.assertEqual(frames[0]["event"], "resync_required")
        self.assertEqual(payload["reason"], "cursor_ahead_of_watermark")
        stream.kill()

    def test_a_cursor_whose_history_was_pruned_names_the_gap_instead_of_shipping_a_partial_tail(self) -> None:
        hub = self.sidecar.revision_hub
        oldest = self.publish("oldest")
        for index in range(1100):  # the ring keeps 1000 (sse_revision.py:71-72)
            hub.publish("observed", {"note": f"trim-{index}"})
        stream = Stream(self.port, last_event_id=str(oldest))
        frames = stream.read_frames(1)
        payload = json.loads(frames[0]["data"])
        self.assertEqual(payload["reason"], "history_gap",
                         f"a pruned cursor produced {frames}")
        resumed_cursor = int(frames[0]["id"])
        self.assertGreater(resumed_cursor, oldest)
        stream.kill()

    def test_no_cursor_means_no_replay_and_a_full_snapshot_instead(self) -> None:
        # Absent header is "first connect", which is a different statement from "cursor 0": with no cursor
        # the server must not claim to replay history it never promised, it sends the current projection.
        self.publish("before-first-connect")
        stream = Stream(self.port)
        frames = stream.read_frames(1)
        self.assertEqual([f["event"] for f in frames], ["snapshot"])
        stream.kill()

    def test_a_heartbeat_carries_the_current_revision_without_advancing_it(self) -> None:
        hub = self.sidecar.revision_hub
        sequence_before = self.publish("before-heartbeat")
        frame = hub.heartbeat_frame()
        self.assertEqual(parse_frames(frame.encode("utf-8"))[0]["id"], str(sequence_before),
                         "a heartbeat that advances the cursor makes every reconnect replay a frame that "
                         "carried no new fact")


class RestartedHubTests(unittest.TestCase):
    """A restarted sidecar keeps the watermark and loses the ring — which must be said, not swallowed.

    `sidecar.py:50` seeds `SseRevisionHub(seed_revision=self._revision)` from the persisted revision, so the
    cursor a returning client holds is valid while the history it refers to is gone. The branch that handled
    that answered `[]`, which reads on the client as "nothing happened" and leaves a stale projection on
    screen with no reason and no resync — one of the four state classes WUI-11 refuses to conflate.
    """

    def frames(self, hub, cursor):
        from sse_revision import SseRevisionHub  # noqa: F401  (documenting the type under test)
        client = hub.connect("restart-client", last_event_id=str(cursor))
        return parse_frames("".join(hub.frames_for(client)).encode("utf-8")), client

    def test_an_empty_ring_beside_a_real_cursor_names_the_missing_history(self) -> None:
        from sse_revision import SseRevisionHub

        first = SseRevisionHub()
        one = first.publish("observed", {"n": 1})
        two = first.publish("observed", {"n": 2})
        restarted = SseRevisionHub(seed_revision=first.current_revision)
        self.assertEqual(restarted.current_revision, two, "the seed must carry the watermark across restarts")

        frames, client = self.frames(restarted, one)
        self.assertEqual([f["event"] for f in frames], ["resync_required"],
                         "silence where a reason is owed")
        payload = json.loads(frames[0]["data"])
        self.assertEqual(payload["reason"], "history_unavailable_after_restart")
        self.assertEqual(int(payload["revision"]), two)
        self.assertEqual(client.last_event_id, str(two), "the cursor must be moved to the watermark")

    def test_a_cursor_already_at_the_watermark_is_honestly_silent(self) -> None:
        from sse_revision import SseRevisionHub

        original = SseRevisionHub()
        latest = original.publish("observed", {"n": 1})
        restarted = SseRevisionHub(seed_revision=original.current_revision)
        frames, _ = self.frames(restarted, latest)
        self.assertEqual(frames, [], "nothing was missed, so nothing may be claimed")

    def test_a_future_cursor_is_still_named_after_a_restart(self) -> None:
        from sse_revision import SseRevisionHub

        original = SseRevisionHub()
        latest = original.publish("observed", {"n": 1})
        restarted = SseRevisionHub(seed_revision=original.current_revision)
        frames, _ = self.frames(restarted, latest + 500)
        self.assertEqual(json.loads(frames[0]["data"])["reason"], "cursor_ahead_of_watermark",
                         "the empty-ring branch must not swallow the more precise diagnosis")


if __name__ == "__main__":
    unittest.main(verbosity=2)
