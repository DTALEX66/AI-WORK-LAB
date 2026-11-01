"""Contract tests for the real SSE hub (WL3-600)."""

from __future__ import annotations

import tempfile
import threading
import time
import unittest
from pathlib import Path

from canonical_store import CanonicalStore
from sse_hub import (
    EventHub,
    LiveProjection,
    SNAPSHOT,
    LIVE,
    VALID_STATES,
    render_sse_frames,
    start_heartbeat,
)


class EventHubTests(unittest.TestCase):
    def setUp(self) -> None:
        self.hub = EventHub(retention=10)

    def test_publish_and_replay(self) -> None:
        event_id = self.hub.publish("observed", {"n": 1})
        messages = self.hub.messages_since(None)
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0].event_id, event_id)
        # Resume from cursor sees nothing new.
        self.assertEqual(self.hub.messages_since(event_id), [])

    def test_retention_ring(self) -> None:
        for index in range(15):
            self.hub.publish("observed", {"n": index})
        messages = self.hub.messages_since(None)
        self.assertEqual(len(messages), 10)  # ring cap
        self.assertEqual(messages[0].data["n"], 5)

    def test_subscriber_receives_published_events(self) -> None:
        subscriber = self.hub.subscribe()
        self.hub.publish("observed", {"n": 1})
        message = subscriber.get(timeout=2)
        self.assertEqual(message.data["n"], 1)
        self.hub.unsubscribe(subscriber)

    def test_sse_frame_rendering(self) -> None:
        event_id = self.hub.publish("observed", {"n": 1})
        messages = self.hub.messages_since(None)
        frame = render_sse_frames(messages, include_retry=True)
        self.assertIn("retry: 2000", frame)
        self.assertIn(f"id: {event_id}", frame)
        self.assertIn('event: observed', frame)
        self.assertIn('data: {"n":1}', frame)


class LiveProjectionTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temporary = tempfile.TemporaryDirectory()
        self.store = CanonicalStore(Path(self._temporary.name) / "canonical.sqlite")
        self.projection = LiveProjection(self.store)

    def tearDown(self) -> None:
        self.store.close()
        self._temporary.cleanup()

    def test_initial_mode_is_snapshot_not_live(self) -> None:
        self.assertEqual(self.projection.mode(), SNAPSHOT)
        snapshot = self.projection.snapshot()
        self.assertEqual(snapshot["freshness"], "STALE")
        self.assertNotEqual(snapshot["mode"], LIVE)

    def test_mode_transitions_are_validated(self) -> None:
        self.projection.set_mode(LIVE)
        self.assertEqual(self.projection.mode(), LIVE)
        with self.assertRaises(ValueError):
            self.projection.set_mode("BOGUS")

    def test_subscriber_receives_observed_event_while_connected(self) -> None:
        subscriber = self.projection.subscribe()
        self.projection.publish_observed()
        message = subscriber.get(timeout=2)
        self.assertEqual(message.event_type, "observed")
        self.projection.unsubscribe(subscriber)

    def test_valid_states(self) -> None:
        self.assertEqual(
            VALID_STATES,
            {"LIVE", "STALE", "SNAPSHOT", "FIXTURE", "OFFLINE", "UNKNOWN"},
        )

    def test_heartbeat_thread_emits_pings(self) -> None:
        subscriber = self.projection.subscribe()
        thread = start_heartbeat(self.projection, seconds=0.2)
        try:
            found = False
            deadline = time.time() + 3
            while time.time() < deadline and not found:
                try:
                    message = subscriber.get(timeout=0.5)
                    if message.event_type == "heartbeat":
                        found = True
                except Exception:  # noqa: BLE001
                    break
            self.assertTrue(found)
        finally:
            self.projection.unsubscribe(subscriber)


if __name__ == "__main__":
    unittest.main()
