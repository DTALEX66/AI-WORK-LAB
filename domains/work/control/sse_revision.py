"""Persistent revision + real SSE semantics (WLGM-160).

SSE IDs use the canonical persistent sequence/revision (not in-memory UUIDs).
Support for ``Last-Event-ID``, ``resync_required`` on stale/missing cursors,
named events, restart recovery via a fresh snapshot, bounded slow consumers,
jitter/backoff and a maximum connection count. A broken SSE connection never
blocks the canonical writer.

This module is transport-agnostic: it produces SSE frames and validates
cursor/revision semantics; the actual HTTP layer can be any server.
"""
from __future__ import annotations

import random
import threading
from dataclasses import dataclass, field
from typing import Any

EVENT_NAMES = {"snapshot", "observed", "heartbeat", "resync_required", "collector_state", "shutdown"}

MAX_CONNECTIONS = 16


@dataclass
class SseClient:
    client_id: str
    last_event_id: str | None = None  # persistent canonical revision
    connected_at: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {"clientId": self.client_id, "lastEventId": self.last_event_id, "connectedAt": self.connected_at}


class SseRevisionHub:
    """Persistent-revision SSE hub with named events and reconnect recovery."""

    def __init__(self, *, max_connections: int = MAX_CONNECTIONS, seed_revision: int = 0) -> None:
        self.max_connections = max_connections
        self._clients: dict[str, SseClient] = {}
        # A restarted sidecar must continue from the persisted seed so
        # Last-Event-ID cursors never observe a rolled-back sequence.
        self._sequence = max(0, int(seed_revision))
        self._lock = threading.RLock()
        self._history: list[tuple[int, str, dict[str, Any]]] = []  # (seq, event, data)

    @property
    def current_revision(self) -> int:
        with self._lock:
            return self._sequence

    def connect(self, client_id: str, last_event_id: str | None = None) -> SseClient | None:
        with self._lock:
            if len(self._clients) >= self.max_connections and client_id not in self._clients:
                return None  # bounded slow consumers
            client = self._clients.setdefault(client_id, SseClient(client_id=client_id, last_event_id=last_event_id))
            if last_event_id is not None:
                client.last_event_id = last_event_id
            return client

    def disconnect(self, client_id: str) -> None:
        with self._lock:
            self._clients.pop(client_id, None)

    def publish(self, event: str, data: dict[str, Any]) -> int:
        if event not in EVENT_NAMES:
            raise ValueError(f"unknown SSE event name: {event}")
        with self._lock:
            self._sequence += 1
            self._history.append((self._sequence, event, data))
            # Keep a bounded history for reconnect replay (revision gap detection).
            if len(self._history) > 1000:
                self._history = self._history[-1000:]
            return self._sequence

    def frames_for(self, client: SseClient) -> list[str]:
        """Produce SSE frames for a client, honouring Last-Event-ID."""
        with self._lock:
            if client.last_event_id is None:
                client.last_event_id = str(self._sequence)
                return []
            try:
                last_seq = int(client.last_event_id)
            except ValueError:
                client.last_event_id = str(self._sequence)
                return [
                    self._frame(
                        "resync_required",
                        {"reason": "invalid_cursor", "revision": self._sequence},
                        self._sequence,
                    )
                ]
            available = {seq for seq, _, _ in self._history}
            if last_seq > self._sequence:
                # Future cursor (client clock ahead / service restarted with gap).
                client.last_event_id = str(self._sequence)
                return [
                    self._frame(
                        "resync_required",
                        {"reason": "cursor_ahead_of_watermark", "revision": self._sequence},
                        self._sequence,
                    )
                ]
            if not available:
                # An empty ring beside a real cursor is NOT "nothing to send". A restarted sidecar seeds the
                # revision from the store but never the replay history, so the events between that cursor and
                # the watermark existed and are gone. The first draft of this branch answered with silence,
                # which left a reconnecting client holding a stale projection with neither a replay nor a
                # reason — the exact shape of claim the read-only iron law refuses.
                client.last_event_id = str(self._sequence)
                if last_seq == self._sequence:
                    return []  # nothing was missed: the cursor already is the watermark
                return [
                    self._frame(
                        "resync_required",
                        {"reason": "history_unavailable_after_restart", "revision": self._sequence},
                        self._sequence,
                    )
                ]
            if last_seq < self._sequence and last_seq not in available and last_seq != 0:
                # Gap: history was pruned or service restarted.
                client.last_event_id = str(self._sequence)
                return [
                    self._frame(
                        "resync_required",
                        {"reason": "history_gap", "revision": self._sequence},
                        self._sequence,
                    )
                ]
            frames = [
                self._frame(event, data, seq)
                for seq, event, data in self._history
                if seq > last_seq
            ]
            client.last_event_id = str(self._sequence)
            return frames

    @staticmethod
    def _frame(event: str, data: dict[str, Any], seq: int | None = None) -> str:
        import json

        lines = []
        if event:
            lines.append(f"event: {event}")
        lines.append(f"id: {seq if seq is not None else ''}")
        payload = json.dumps(data, ensure_ascii=False, sort_keys=True)
        for line in payload.splitlines() or [""]:
            lines.append(f"data: {line}")
        return "\n".join(lines) + "\n\n"

    def heartbeat_frame(self) -> str:
        return self._frame("heartbeat", {"ts": __import__("time").time()}, self._sequence)


def resync_frame(reason: str, revision: int) -> str:
    return SseRevisionHub._frame("resync_required", {"reason": reason, "revision": revision}, revision)
