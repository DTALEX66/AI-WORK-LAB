"""Unit tests for P3/sub_F streaming-events enhancement.

Covers the *new only* streaming surface of the parallel dispatcher
(spec P3/sub_F):

* ``ParallelDispatcher.fanout_stream(...)`` — a real-time generator
  that yields one event dict ``{executor, phase, ts, ok, status}``
  per phase transition (STARTED as each route begins, then that
  route's terminal DONE / FAILED / TIMEOUT);
* ``parallel_dispatch_stream(...)`` — the module-level convenience
  that yields the same stream.

Deterministic and environment-safe, mirroring test_parallel_dispatch.py
(P1 core tests): the fan-out runs against a minimal fake federation of
stub adapters (Ok / Raising / Slow) — no process is ever spawned and
the stubs (not the adapters' launch decisions) control each route's
outcome.  The shared ``_RunState`` / lock / collector machinery is the
same one batch ``fanout()`` uses, so stream and batch stay consistent.

Hard constraint honoured: the existing ``fanout()`` /
``dispatch_events()`` / ``parallel_dispatch_of()`` signatures and
return contracts are untouched; these tests only exercise the newly
added generator surface, plus one regression guard on ``fanout()``
itself.
"""
from __future__ import annotations

import importlib.util
import sys
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FED = ROOT / "services" / "execution-federation"
_ACP_MOD = "services_execution_federation_acp_adapter"
_PD_MOD = "services_execution_federation_parallel_dispatch"


def _load(name: str, module_name: str):
    if module_name in sys.modules:
        return sys.modules[module_name]
    spec = importlib.util.spec_from_file_location(module_name, FED / name)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


acp = _load("acp_adapter.py", _ACP_MOD)
pd = _load("parallel_dispatch.py", _PD_MOD)


# -- stub adapters: deterministic, launch-free (same pattern as P1) ----

class OkAdapter(acp.ExecutorAcpAdapter):
    """Route that always succeeds."""

    def __init__(self, name: str, start_delay: float = 0.0) -> None:
        self.executor = name
        self._start_delay = start_delay
        self.new_calls: list[dict] = []

    def new(self, **kw):
        if self._start_delay:
            time.sleep(self._start_delay)
        self.new_calls.append(dict(kw))
        return acp.ExecResult(acp.Op.NEW, self.executor, ok=True, status="OK")


class RaisingAdapter(acp.ExecutorAcpAdapter):
    """Route whose new() raises -> dispatcher isolates it as FAILED."""

    def __init__(self, name: str, start_delay: float = 0.0) -> None:
        self.executor = name
        self._start_delay = start_delay
        self.new_calls: list[dict] = []

    def new(self, **kw):
        if self._start_delay:
            time.sleep(self._start_delay)
        self.new_calls.append(dict(kw))
        raise RuntimeError(f"{self.executor} hard failure (stub)")


class SlowAdapter(acp.ExecutorAcpAdapter):
    """Route that sleeps past the per-executor deadline -> TIMEOUT."""

    def __init__(self, name: str, delay: float = 0.4) -> None:
        self.executor = name
        self._delay = delay
        self.new_calls: list[dict] = []

    def new(self, **kw):
        time.sleep(self._delay)
        self.new_calls.append(dict(kw))
        return acp.ExecResult(acp.Op.NEW, self.executor, ok=True, status="OK")


class FakeFederation:
    """Minimal fake federation: only the ``.get()`` surface the
    dispatcher uses.  Passive — registers stubs, never launches."""

    def __init__(self, adapters: dict) -> None:
        self._adapters = dict(adapters)

    def get(self, name: str):
        return self._adapters.get(name)


def _streamed(federation, *args, **kwargs) -> list[dict]:
    """Drain a fanout_stream generator into a plain event list."""
    return list(federation.fanout_stream(*args, **kwargs))


def _partitions(result) -> dict:
    """The four final partition lists of a batch aggregate payload."""
    return {
        "succeeded": result.payload["succeeded"],
        "failed": result.payload["failed"],
        "timed_out": result.payload["timed_out"],
        "unknown": result.payload["unknown"],
    }


def _stream_partition_from_events(events: list[dict], names: list[str]) -> dict:
    """Rebuild the four partitions from a stream's terminal events.

    Each route's terminal phase determines its bucket exactly as the
    batch aggregator does: DONE -> succeeded, TIMEOUT -> timed_out,
    UNKNOWN_EXECUTOR terminal -> unknown, FAILED terminal -> failed
    (routes dropped by fail_fast settle as SKIPPED_FAILFAST on the
    batch side and fall in 'failed'; they never appear in the stream
    at all, so their absence from the stream is accounted for below).
    """
    succeeded: list[str] = []
    failed: list[str] = []
    timed_out: list[str] = []
    unknown: list[str] = []
    for name in names:
        terminals = [e for e in events
                     if e["executor"] == name
                     and e["phase"] in ("DONE", "FAILED", "TIMEOUT")]
        terminal = terminals[-1] if terminals else None
        if terminal is None:
            # no terminal in the stream: either degraded-adapter (the
            # terminal still carries its status) or fail_fast-dropped
            # (SKIPPED_FAILFAST -> failed bucket on the batch side).
            failed.append(name)
            continue
        if terminal["phase"] == "DONE":
            succeeded.append(name)
        elif terminal["phase"] == "TIMEOUT":
            timed_out.append(name)
        elif terminal["status"] == "UNKNOWN_EXECUTOR":
            unknown.append(name)
        else:
            failed.append(name)
    return {
        "succeeded": succeeded,
        "failed": failed,
        "timed_out": timed_out,
        "unknown": unknown,
    }


# ------------------------------------------------------------------------

class StreamEventOrderTests(unittest.TestCase):
    def test_every_started_precedes_its_own_terminal(self):
        names = ["a", "b", "c", "d"]
        adapters = {n: OkAdapter(n, start_delay=0.05 * i)
                    for i, n in enumerate(names)}
        fed = FakeFederation(adapters)
        d = pd.ParallelDispatcher(fed, max_workers=4)
        events = _streamed(d, acp.Op.NEW, names, {"project_id": "p1"})
        for name in names:
            started = [e for e in events
                       if e["executor"] == name and e["phase"] == "STARTED"]
            terminals = [e for e in events
                         if e["executor"] == name
                         and e["phase"] in ("DONE", "FAILED", "TIMEOUT")]
            self.assertEqual(len(started), 1)
            self.assertEqual(len(terminals), 1)
            # a terminal can never precede its own STARTED (coarse
            # clock: fast routes may share the same time.time() tick)
            self.assertLessEqual(started[0]["ts"], terminals[0]["ts"])
            # and within the chronological stream the STARTED record
            # itself must sit before the terminal record
            self.assertLess(events.index(started[0]), events.index(terminals[0]))
        # every yielded record carries the five required fields
        for e in events:
            self.assertEqual(
                set(e), {"executor", "phase", "ts", "ok", "status"})


class StreamFailFastTests(unittest.TestCase):
    def test_fail_fast_emits_no_started_for_dropped_routes(self):
        bad = RaisingAdapter("bad")
        g1, g2 = OkAdapter("good1"), OkAdapter("good2")
        # max_workers=1 makes the queue FIFO: 'bad' settles first and
        # sets the abort flag before either good route even starts
        # (same determinism trick as the P1 fail_fast test).
        d = pd.ParallelDispatcher(
            FakeFederation({"bad": bad, "good1": g1, "good2": g2}),
            max_workers=1)
        events = _streamed(d, acp.Op.NEW, ["bad", "good1", "good2"], {},
                           fail_fast=True)
        started = [e["executor"] for e in events if e["phase"] == "STARTED"]
        self.assertEqual(started, ["bad"])
        # un-started routes: no STARTED and no terminal of their own
        self.assertNotIn("good1", started)
        self.assertNotIn("good2", started)
        self.assertFalse(any(e["executor"] in ("good1", "good2")
                             for e in events))
        # and their adapters were never invoked
        self.assertEqual(g1.new_calls, [])
        self.assertEqual(g2.new_calls, [])


class StreamTimeoutTests(unittest.TestCase):
    def test_slow_route_yields_timeout_event_under_small_deadline(self):
        good = OkAdapter("good")
        slow = SlowAdapter("slow", delay=0.4)
        d = pd.ParallelDispatcher(
            FakeFederation({"good": good, "slow": slow}), max_workers=2)
        events = _streamed(d, acp.Op.NEW, ["good", "slow"], {},
                           per_executor_timeout=0.05)
        slow_events = [e for e in events if e["executor"] == "slow"]
        phases = [e["phase"] for e in slow_events]
        self.assertEqual(phases, ["STARTED", "TIMEOUT"])
        timeout_event = slow_events[-1]  # the terminal record
        self.assertEqual(timeout_event["phase"], "TIMEOUT")
        self.assertIs(timeout_event["ok"], False)
        self.assertEqual(timeout_event["status"], "TIMEOUT")
        # it is part of the same chronological stream
        self.assertIn(timeout_event, events)


class StreamBatchConsistencyTests(unittest.TestCase):
    def test_stream_yields_same_final_partition_as_batch(self):
        def partitions_for(names):
            adapters = {
                "good": OkAdapter("good"),
                "bad": RaisingAdapter("bad"),
                "slow": SlowAdapter("slow", delay=0.4),
            }
            # 'ghost' is deliberately NOT registered: it must land in
            # the 'unknown' bucket on both sides.
            kw = dict(per_executor_timeout=0.05)
            stream_d = pd.ParallelDispatcher(
                FakeFederation(dict(adapters)), max_workers=4)
            events = _streamed(stream_d, acp.Op.NEW, names, {}, **kw)
            batch_d = pd.ParallelDispatcher(
                FakeFederation(dict(adapters)), max_workers=4)
            batch = batch_d.fanout(acp.Op.NEW, names, {}, **kw)
            return _stream_partition_from_events(events, names), _partitions(batch)

        stream_parts, batch_parts = partitions_for(["good", "bad", "slow", "ghost"])
        for key in ("succeeded", "failed", "timed_out", "unknown"):
            self.assertEqual(sorted(stream_parts[key]), sorted(batch_parts[key]),
                             f"partition {key!r} diverges between stream and batch")
        self.assertEqual(batch_parts["succeeded"], ["good"])
        self.assertEqual(batch_parts["failed"], ["bad"])
        self.assertEqual(batch_parts["timed_out"], ["slow"])
        self.assertEqual(batch_parts["unknown"], ["ghost"])

    def test_all_ok_stream_partition_matches_batch(self):
        names = ["a", "b", "c"]
        fed = FakeFederation({n: OkAdapter(n) for n in names})
        events = _streamed(pd.ParallelDispatcher(FakeFederation(
            {n: OkAdapter(n) for n in names}), max_workers=4),
            acp.Op.NEW, names, {})
        batch = pd.ParallelDispatcher(FakeFederation(
            {n: OkAdapter(n) for n in names}), max_workers=4).fanout(
            acp.Op.NEW, names, {})
        self.assertEqual(_stream_partition_from_events(events, names),
                         _partitions(batch))


class ModuleLevelConvenienceTests(unittest.TestCase):
    def test_parallel_dispatch_stream_module_helper_yields_same_events(self):
        names = ["a", "b"]
        fed = FakeFederation({n: OkAdapter(n) for n in names})
        module_events = list(pd.parallel_dispatch_stream(
            fed, acp.Op.NEW, names, {"project_id": "p9"}, max_workers=2))
        method_events = _streamed(pd.ParallelDispatcher(
            FakeFederation({n: OkAdapter(n) for n in names}), max_workers=2),
            acp.Op.NEW, names, {"project_id": "p9"})
        # identical partition (fresh adapter sets keep runs independent)
        self.assertEqual(
            _stream_partition_from_events(module_events, names),
            _stream_partition_from_events(method_events, names))
        self.assertEqual(len(module_events), 4)
        self.assertEqual(
            [e["phase"] for e in module_events if e["executor"] == "a"],
            ["STARTED", "DONE"])


class BatchRegressionGuardTests(unittest.TestCase):
    def test_existing_fanout_signature_still_works_unchanged(self):
        # regression guard: the P1 batch contract is untouched — same
        # positional/keyword surface, same ExecResult aggregate shape.
        a, b = OkAdapter("a"), OkAdapter("b")
        d = pd.ParallelDispatcher(FakeFederation({"a": a, "b": b}), max_workers=2)
        r = d.fanout(acp.Op.NEW, ["a", "b"], {"project_id": "p1"})
        self.assertEqual(r.executor, "*")
        self.assertEqual(r.status, "OK")
        self.assertTrue(r.ok)
        self.assertEqual(set(r.payload.keys()),
                         {"per_executor", "succeeded", "failed", "timed_out",
                          "unknown", "events"})
        self.assertEqual(r.payload["succeeded"], ["a", "b"])
        # dispatch_events / parallel_dispatch_of still behave the same
        d2 = pd.ParallelDispatcher(
            FakeFederation({n: OkAdapter(n) for n in ("a", "b")}),
            max_workers=2)
        evs = d2.dispatch_events(acp.Op.NEW, ["a", "b"], {})
        self.assertEqual(len(evs), 4)
        spec_r = pd.parallel_dispatch_of(
            FakeFederation({n: OkAdapter(n) for n in ("a", "b")}),
            [{"name": "s1", "op": acp.Op.NEW, "executors": ["a"], "payload": {}}])
        self.assertEqual(spec_r.status, "OK")


if __name__ == "__main__":
    unittest.main(verbosity=2)
