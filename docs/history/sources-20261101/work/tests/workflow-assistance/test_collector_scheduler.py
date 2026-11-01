"""WLGM-070 tests: non-interfering collector scheduler."""
from __future__ import annotations

import time
import unittest

from collector_scheduler import BoundedEventQueue, Collector, CollectorScheduler


def heartbeat(event_id: str) -> dict:
    return {"eventId": event_id, "eventType": "execution_heartbeat"}


def terminal(event_id: str) -> dict:
    return {"eventId": event_id, "eventType": "execution_completed"}


class BoundedEventQueueTests(unittest.TestCase):
    def test_full_queue_drops_heartbeat_keeps_terminal(self) -> None:
        queue = BoundedEventQueue(max_size=3)
        queue.push(heartbeat("h1"))
        queue.push(heartbeat("h2"))
        queue.push(heartbeat("h3"))
        # Full; a new heartbeat is dropped.
        self.assertFalse(queue.push(heartbeat("h4")))
        self.assertEqual(queue.dropped, 1)
        # A terminal event evicts the oldest heartbeat.
        self.assertTrue(queue.push(terminal("t1")))
        drained = queue.drain()
        self.assertIn("t1", [e["eventId"] for e in drained])
        self.assertEqual(len(drained), 3)

    def test_terminal_never_evicted_by_heartbeat(self) -> None:
        queue = BoundedEventQueue(max_size=2)
        queue.push(terminal("t1"))
        queue.push(terminal("t2"))
        self.assertFalse(queue.push(heartbeat("h1")))
        drained = queue.drain()
        self.assertEqual({e["eventId"] for e in drained}, {"t1", "t2"})


class CollectorSchedulerTests(unittest.TestCase):
    def test_happy_path_collects_events(self) -> None:
        collector = Collector("ok", lambda: [heartbeat("h1")])
        scheduler = CollectorScheduler([collector])
        result = scheduler.run_once()
        self.assertEqual(result, {"ran": 1, "failed": 0})
        self.assertEqual(collector.health.consecutive_failures, 0)
        self.assertEqual(len(scheduler.queue.drain()), 1)

    def test_failing_collector_degrades_without_killing_worker(self) -> None:
        def boom() -> list[dict]:
            raise RuntimeError("collector exploded")

        collector = Collector("boom", boom)
        scheduler = CollectorScheduler([collector])
        result = scheduler.run_once()
        self.assertEqual(result["failed"], 1)
        self.assertEqual(collector.health.consecutive_failures, 1)
        self.assertIsNone(collector.health.circuit_open_until)

    def test_circuit_breaker_opens_after_threshold(self) -> None:
        def boom() -> list[dict]:
            raise RuntimeError("explode")

        collector = Collector("boom", boom, backoff_seconds=0)
        scheduler = CollectorScheduler([collector], breaker_threshold=2, breaker_cooldown_seconds=3600)
        scheduler.run_once()
        scheduler.run_once()
        self.assertEqual(collector.health.consecutive_failures, 2)
        self.assertIsNotNone(collector.health.circuit_open_until)
        # Circuit is open: next run skips the collector.
        result = scheduler.run_once()
        self.assertEqual(result, {"ran": 0, "failed": 0})

    def test_backoff_delays_retry(self) -> None:
        calls = {"n": 0}

        def flaky() -> list[dict]:
            calls["n"] += 1
            if calls["n"] == 1:
                raise RuntimeError("first try fails")
            return [heartbeat("h1")]

        collector = Collector("flaky", flaky, backoff_seconds=60)
        scheduler = CollectorScheduler([collector])
        scheduler.run_once()  # fails, backoff 60s
        result = scheduler.run_once()  # skipped due to backoff
        self.assertEqual(result, {"ran": 0, "failed": 0})
        self.assertEqual(calls["n"], 1)

    def test_stuck_collector_times_out(self) -> None:
        def stuck() -> list[dict]:
            time.sleep(5)
            return [heartbeat("late")]

        collector = Collector("stuck", stuck, timeout_seconds=0.1)
        scheduler = CollectorScheduler([collector])
        started = time.monotonic()
        scheduler.run_once()
        elapsed = time.monotonic() - started
        self.assertLess(elapsed, 2.0)
        self.assertGreaterEqual(collector.health.consecutive_failures, 1)

    def test_load_shedding_drops_de_levels(self) -> None:
        collector_e = Collector("proc", lambda: [heartbeat("e1")], evidence_level="E")
        collector_a = Collector("api", lambda: [heartbeat("a1")], evidence_level="A")
        scheduler = CollectorScheduler([collector_e, collector_a], load_level=2)
        result = scheduler.run_once()
        self.assertEqual(result["ran"], 1)
        self.assertEqual(collector_a.health.total_runs, 1)
        self.assertEqual(collector_e.health.total_runs, 0)

    def test_health_record_shape(self) -> None:
        collector = Collector("ok", lambda: [heartbeat("h1")])
        scheduler = CollectorScheduler([collector])
        scheduler.run_once()
        record = collector.health.to_record()
        self.assertEqual(record["name"], "ok")
        self.assertEqual(record["totalRuns"], 1)
        self.assertIn("lastSuccessAt", record)


if __name__ == "__main__":
    unittest.main()
