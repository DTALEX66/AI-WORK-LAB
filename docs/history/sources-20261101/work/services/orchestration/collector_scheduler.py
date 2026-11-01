"""Non-interfering collector scheduler (WLGM-070).

A low-priority, budgeted, circuit-broken scheduler for evidence collectors.

- each collector runs in the scheduler's worker loop with a hard timeout,
  backoff and a circuit breaker (3-5 consecutive failures -> open, 1-5 minute
  cool-down with exponential backoff capped);
- under resource pressure, E/D-level collectors are suspended first while
  A/B/C events keep flowing;
- heartbeats use a bounded async queue; when full, OLD heartbeats are dropped
  but terminal-state events are never dropped;
- collector health is recorded as facts, never faked as project state;
- a stuck/failed collector never blocks the canonical writer.
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable

TERMINAL_EVENT_TYPES = {
    "execution_completed",
    "execution_failed",
    "execution_cancelled",
    "execution_lost",
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


@dataclass
class CollectorHealth:
    name: str
    total_runs: int = 0
    last_run_at: str | None = None
    last_success_at: str | None = None
    consecutive_failures: int = 0
    circuit_open_until: float | None = None
    dropped_count: int = 0

    def to_record(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "totalRuns": self.total_runs,
            "lastRunAt": self.last_run_at,
            "lastSuccessAt": self.last_success_at,
            "consecutiveFailures": self.consecutive_failures,
            "circuitOpenUntil": self.circuit_open_until,
            "droppedCount": self.dropped_count,
        }


class BoundedEventQueue:
    """Bounded queue: terminal events never dropped; heartbeats drop oldest."""

    def __init__(self, max_size: int = 1000) -> None:
        self.max_size = max_size
        self._items: list[dict[str, Any]] = []
        self.dropped = 0

    def push(self, event: dict[str, Any]) -> bool:
        event_type = event.get("eventType", "")
        if len(self._items) >= self.max_size:
            if event_type in TERMINAL_EVENT_TYPES:
                # Keep terminal events: evict oldest non-terminal if possible.
                for index, item in enumerate(self._items):
                    if item.get("eventType") not in TERMINAL_EVENT_TYPES:
                        self._items.pop(index)
                        self.dropped += 1
                        break
                else:
                    return False  # queue is all terminal events; refuse new
            else:
                self.dropped += 1
                return False  # heartbeat dropped, never evict terminal
        self._items.append(event)
        return True

    def drain(self) -> list[dict[str, Any]]:
        items, self._items = self._items, []
        return items

    def __len__(self) -> int:
        return len(self._items)


class Collector:
    """A single evidence collector: ``run_once`` returns a list of events."""

    def __init__(
        self,
        name: str,
        run_once: Callable[[], list[dict[str, Any]]],
        *,
        evidence_level: str = "C",
        timeout_seconds: float = 5.0,
        backoff_seconds: float = 10.0,
    ) -> None:
        self.name = name
        self.run_once = run_once
        self.evidence_level = evidence_level
        self.timeout_seconds = timeout_seconds
        self.backoff_seconds = backoff_seconds
        self.health = CollectorHealth(name=name)


class CollectorScheduler:
    """Serial, non-blocking scheduler with circuit breaker and load shedding."""

    def __init__(
        self,
        collectors: list[Collector] | None = None,
        queue: BoundedEventQueue | None = None,
        *,
        breaker_threshold: int = 3,
        breaker_cooldown_seconds: float = 60.0,
        max_backoff_seconds: float = 300.0,
        load_level: int = 0,  # 0=idle, 1=busy, 2=critical
    ) -> None:
        self.collectors = collectors or []
        self.queue = queue or BoundedEventQueue()
        self.breaker_threshold = breaker_threshold
        self.breaker_cooldown_seconds = breaker_cooldown_seconds
        self.max_backoff_seconds = max_backoff_seconds
        self.load_level = load_level
        self._lock = threading.RLock()

    def run_once(self) -> dict[str, int]:
        """Run every eligible collector once. Never raises; never blocks writer."""
        ran = 0
        failed = 0
        for collector in self.collectors:
            if not self._eligible(collector):
                continue
            ran += 1
            if not self._run_collector(collector):
                failed += 1
        return {"ran": ran, "failed": failed}

    def _eligible(self, collector: Collector) -> bool:
        if self.load_level >= 2 and collector.evidence_level in ("D", "E"):
            return False  # shed weak-evidence collectors first
        with self._lock:
            health = collector.health
            if health.circuit_open_until and time.monotonic() < health.circuit_open_until:
                return False
            if health.consecutive_failures > 0:
                delay = min(collector.backoff_seconds * (2 ** (health.consecutive_failures - 1)), self.max_backoff_seconds)
                if health.last_run_at and self._age_seconds(health.last_run_at) < delay:
                    return False
        return True

    def _run_collector(self, collector: Collector) -> bool:
        """Run one collector with timeout; returns True on success."""
        events: list[dict[str, Any]] = []
        error: Exception | None = None

        def target() -> None:
            try:
                events.extend(collector.run_once())
            except Exception as exc:  # noqa: BLE001
                nonlocal error
                error = exc

        worker = threading.Thread(target=target, daemon=True)
        worker.start()
        worker.join(timeout=collector.timeout_seconds)
        timed_out = worker.is_alive()

        with self._lock:
            health = collector.health
            health.total_runs += 1
            health.last_run_at = _now_iso()
            if timed_out or error is not None:
                health.consecutive_failures += 1
                if health.consecutive_failures >= self.breaker_threshold:
                    health.circuit_open_until = time.monotonic() + self.breaker_cooldown_seconds
                return False
            health.consecutive_failures = 0
            health.last_success_at = _now_iso()
            health.circuit_open_until = None
            for event in events:
                accepted = self.queue.push(event)
                if not accepted and event.get("eventType") in TERMINAL_EVENT_TYPES:
                    health.dropped_count += 1
            return True

    @staticmethod
    def _age_seconds(iso_value: str) -> float:
        try:
            parsed = datetime.fromisoformat(iso_value.replace("Z", "+00:00"))
            return (datetime.now(timezone.utc) - parsed).total_seconds()
        except ValueError:
            return 0.0
