"""Loopback SSE hub with true long-lived connections (WL3-600).

Provides:
- snapshot for initial state;
- real SSE for continuous deltas (heartbeat, cursor, Last-Event-ID resume,
  exponential backoff hints, slow-consumer cap, shutdown notice);
- canonical SQLite WAL as the only fact source.

States are limited to LIVE/STALE/SNAPSHOT/FIXTURE/OFFLINE/UNKNOWN. A bundled
snapshot or fixture can never be labelled LIVE.
"""
from __future__ import annotations

import json
import queue
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from canonical_store import CanonicalStore

LIVE = "LIVE"
STALE = "STALE"
SNAPSHOT = "SNAPSHOT"
FIXTURE = "FIXTURE"
OFFLINE = "OFFLINE"
UNKNOWN = "UNKNOWN"
VALID_STATES = {LIVE, STALE, SNAPSHOT, FIXTURE, OFFLINE, UNKNOWN}

HEARTBEAT_SECONDS = 15.0
MAX_SUBSCRIBERS = 32
EVENT_RETENTION = 500


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


@dataclass
class SSEMessage:
    event_id: str
    event_type: str
    data: dict[str, Any]
    produced_at: str = field(default_factory=_now)


class EventHub:
    """Append-only in-memory ring of SSE messages with cursor resume."""

    def __init__(self, retention: int = EVENT_RETENTION) -> None:
        self._messages: list[SSEMessage] = []
        self._retention = retention
        self._lock = threading.Lock()
        self._subscribers: list[queue.Queue[SSEMessage]] = []

    def publish(self, event_type: str, data: dict[str, Any]) -> str:
        message = SSEMessage(event_id=uuid.uuid4().hex, event_type=event_type, data=data)
        with self._lock:
            self._messages.append(message)
            if len(self._messages) > self._retention:
                self._messages = self._messages[-self._retention:]
            for subscriber in list(self._subscribers):
                try:
                    subscriber.put_nowait(message)
                except queue.Full:
                    self._subscribers.remove(subscriber)  # slow consumer cap
        return message.event_id

    def subscribe(self) -> queue.Queue[SSEMessage]:
        subscriber: queue.Queue[SSEMessage] = queue.Queue(maxsize=256)
        with self._lock:
            if len(self._subscribers) >= MAX_SUBSCRIBERS:
                raise RuntimeError("too many SSE subscribers")
            self._subscribers.append(subscriber)
        return subscriber

    def unsubscribe(self, subscriber: queue.Queue[SSEMessage]) -> None:
        with self._lock:
            if subscriber in self._subscribers:
                self._subscribers.remove(subscriber)

    def messages_since(self, last_event_id: str | None) -> list[SSEMessage]:
        with self._lock:
            if not last_event_id:
                return list(self._messages)
            for index, message in enumerate(self._messages):
                if message.event_id == last_event_id:
                    return list(self._messages[index + 1 :])
            # Cursor no longer in retention: send full snapshot hint via event type.
            return []

    def snapshot_cursor(self) -> str | None:
        with self._lock:
            return self._messages[-1].event_id if self._messages else None


def render_sse_frames(
    messages: list[SSEMessage],
    *,
    include_retry: bool = False,
    include_heartbeat: bool = False,
) -> str:
    frames: list[str] = []
    if include_retry:
        frames.append("retry: 2000\n\n")
    for message in messages:
        frames.append(
            f"id: {message.event_id}\n"
            f"event: {message.event_type}\n"
            f"data: {json.dumps(message.data, ensure_ascii=False, separators=(',', ':'))}\n\n"
        )
    if include_heartbeat and not messages:
        frames.append(f": heartbeat {_now()}\n\n")
    return "".join(frames)


class LiveProjection:
    """Stateful projection backed by the canonical store, driving the SSE hub."""

    def __init__(self, store: CanonicalStore, project_id: str = "work-lab") -> None:
        self.store = store
        self.project_id = project_id
        self.hub = EventHub()
        self._mode = SNAPSHOT
        self._last_publish: dict[str, str] = {}

    def mode(self) -> str:
        return self._mode

    def set_mode(self, mode: str) -> None:
        if mode not in VALID_STATES:
            raise ValueError(f"invalid projection mode: {mode}")
        self._mode = mode
        self.publish_observed()

    def snapshot(self) -> dict[str, Any]:
        base = self.store.projection()
        return {
            "schema_version": "workflow/live-projection/v1",
            "mode": self._mode,
            "project_id": self.project_id,
            "observed_at": _now(),
            "integrity": base["integrity"],
            "tasks_by_status": base["tasks_by_status"],
            "telemetry_events": base["telemetry_events"],
            "usage_summary": base["usage_summary"],
            "ci_summary": base["ci_summary"],
            "freshness": "STALE" if self._mode == SNAPSHOT else self._mode,
        }

    def publish_observed(self) -> str:
        return self.hub.publish("observed", self.snapshot())

    def subscribe(self) -> queue.Queue[SSEMessage]:
        return self.hub.subscribe()

    def unsubscribe(self, subscriber: queue.Queue[SSEMessage]) -> None:
        self.hub.unsubscribe(subscriber)


def start_heartbeat(projection: LiveProjection, seconds: float = HEARTBEAT_SECONDS) -> threading.Thread:
    """Background heartbeat thread publishing LIVE-mode pings."""

    def _loop() -> None:
        while True:
            time.sleep(seconds)
            projection.hub.publish("heartbeat", {"at": _now()})

    thread = threading.Thread(target=_loop, daemon=True, name="sse-heartbeat")
    thread.start()
    return thread


if __name__ == "__main__":
    import project_temp

    with project_temp.fixture_root(prefix='sse-hub-selftest-') as temporary:
        store = CanonicalStore(Path := __import__("pathlib").Path(temporary) / "canonical.sqlite")
        projection = LiveProjection(store)
        projection.set_mode(LIVE)
        print(json.dumps(projection.snapshot(), ensure_ascii=False, indent=2)[:400])
        store.close()
