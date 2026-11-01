"""Unit tests for parallel dispatch P1 core (spec P1 核心 test list).

Deterministic and environment-safe: fan-out runs against a minimal fake
federation of stub adapters — no process is ever spawned, no credentials
are read, and the stubs (not the adapters' launch decisions) control
each route's outcome.  One read-only smoke test drives the *real*
``default_federation()``: its ``new()`` degrades without launching
anything, so no real process or file access is involved.

Loading convention mirrors test_execution_federation.py: service modules
load via ``importlib`` spec under the stable ``sys.modules`` names so the
shared ``Op`` / ``ExecResult`` / ``Capability`` enums stay singletons.
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
_FED_MOD = "services_execution_federation_federation"


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


# -- stub adapters: deterministic, launch-free --------------------------

class OkAdapter(acp.ExecutorAcpAdapter):
    """Route that always succeeds and records every call it receives."""

    def __init__(self, name: str) -> None:
        self.executor = name
        self.new_calls: list[dict] = []
        self.prompt_calls: list[tuple[str, str]] = []

    def new(self, **kw):
        self.new_calls.append(dict(kw))
        return acp.ExecResult(acp.Op.NEW, self.executor, ok=True, status="OK",
                              payload={"echo": dict(kw)})

    def prompt(self, session_id: str, text: str):
        self.prompt_calls.append((session_id, text))
        return acp.ExecResult(acp.Op.PROMPT, self.executor, ok=True, status="OK",
                              payload={"session_id": session_id, "chars": len(text)})


class RaisingAdapter(acp.ExecutorAcpAdapter):
    """Route whose new() raises -> dispatcher must isolate it as FAILED."""

    def __init__(self, name: str) -> None:
        self.executor = name
        self.new_calls: list[dict] = []

    def new(self, **kw):
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
    dispatcher uses.  It stays passive — it registers stubs, it never
    launches."""

    def __init__(self, adapters: dict) -> None:
        self._adapters = dict(adapters)

    def get(self, name: str):
        return self._adapters.get(name)


def _ok_fed(*names: str):
    adapters = {n: OkAdapter(n) for n in names}
    return FakeFederation(adapters), adapters


# ------------------------------------------------------------------------

class FanoutSuccessTests(unittest.TestCase):
    def test_fanout_all_ok_status_ok_succeeded_equals_executors(self):
        fed, _ = _ok_fed("a", "b", "c")
        d = pd.ParallelDispatcher(fed, max_workers=4)
        r = d.fanout(acp.Op.NEW, ["a", "b", "c"], {"project_id": "p1"})
        self.assertTrue(r.ok)
        self.assertEqual(r.status, "OK")
        self.assertEqual(r.executor, "*")
        self.assertEqual(r.payload["succeeded"], ["a", "b", "c"])
        self.assertEqual(r.payload["failed"], [])
        self.assertEqual(r.payload["timed_out"], [])
        self.assertEqual(r.payload["unknown"], [])
        self.assertEqual(set(r.payload["per_executor"]), {"a", "b", "c"})
        for name in ("a", "b", "c"):
            self.assertTrue(r.payload["per_executor"][name]["ok"])

    def test_single_executor_fanout_degrades_to_single_route(self):
        fed, adapters = _ok_fed("solo")
        d = pd.ParallelDispatcher(fed, max_workers=4)
        r = d.fanout(acp.Op.NEW, ["solo"], {"project_id": "x"})
        self.assertEqual(r.status, "OK")
        self.assertEqual(r.payload["succeeded"], ["solo"])
        # equivalent to the serial single route: exactly one adapter call
        self.assertEqual(len(adapters["solo"].new_calls), 1)
        self.assertEqual(adapters["solo"].new_calls[0], {"project_id": "x"})
        self.assertEqual(
            r.payload["per_executor"]["solo"]["ok"], True)


class FanoutIsolationTests(unittest.TestCase):
    def _mixed(self):
        good = OkAdapter("good")
        bad = RaisingAdapter("bad")
        return FakeFederation({"good": good, "bad": bad}), good, bad

    def test_single_route_failure_is_isolated_partial(self):
        fed, good, _ = self._mixed()
        d = pd.ParallelDispatcher(fed, max_workers=2)
        r = d.fanout(acp.Op.NEW, ["good", "bad"], {})
        self.assertEqual(r.status, "PARTIAL")
        self.assertFalse(r.ok)
        self.assertEqual(r.payload["succeeded"], ["good"])
        self.assertEqual(r.payload["failed"], ["bad"])
        self.assertFalse(r.payload["per_executor"]["bad"]["ok"])
        self.assertEqual(r.payload["per_executor"]["bad"]["status"], "FAILED")
        # the healthy route was unaffected by the failure on 'bad'
        self.assertEqual(len(good.new_calls), 1)

    def test_all_routes_failed_status_failed(self):
        a, b = RaisingAdapter("a"), RaisingAdapter("b")
        d = pd.ParallelDispatcher(
            FakeFederation({"a": a, "b": b}), max_workers=2)
        r = d.fanout(acp.Op.NEW, ["a", "b"], {})
        self.assertEqual(r.status, "FAILED")
        self.assertFalse(r.ok)
        self.assertEqual(sorted(r.payload["failed"]), ["a", "b"])
        self.assertEqual(r.payload["succeeded"], [])


class FanoutTimeoutTests(unittest.TestCase):
    def test_single_route_timeout_isolated(self):
        good = OkAdapter("good")
        slow = SlowAdapter("slow", delay=0.4)
        d = pd.ParallelDispatcher(
            FakeFederation({"good": good, "slow": slow}), max_workers=2)
        r = d.fanout(acp.Op.NEW, ["good", "slow"], {}, per_executor_timeout=0.05)
        self.assertEqual(r.payload["timed_out"], ["slow"])
        self.assertEqual(r.payload["succeeded"], ["good"])
        self.assertEqual(r.payload["per_executor"]["slow"]["status"], "TIMEOUT")
        self.assertFalse(r.payload["per_executor"]["slow"]["ok"])
        self.assertEqual(r.status, "PARTIAL")


class FanoutUnknownTests(unittest.TestCase):
    def test_unknown_executor_does_not_crash_batch(self):
        good = OkAdapter("good")
        d = pd.ParallelDispatcher(FakeFederation({"good": good}))
        r = d.fanout(acp.Op.NEW, ["good", "ghost"], {})
        self.assertEqual(r.status, "PARTIAL")
        self.assertEqual(r.payload["unknown"], ["ghost"])
        self.assertEqual(r.payload["succeeded"], ["good"])
        ghost = r.payload["per_executor"]["ghost"]
        self.assertEqual(ghost["status"], "UNKNOWN_EXECUTOR")
        self.assertFalse(ghost["ok"])
        # the batch itself survived (no exception, well-formed aggregate)
        self.assertEqual(r.executor, "*")


class FanoutEdgeTests(unittest.TestCase):
    def test_zero_executors_degraded_with_notes(self):
        d = pd.ParallelDispatcher(FakeFederation({}))
        r = d.fanout(acp.Op.NEW, [], {})
        self.assertEqual(r.status, "DEGRADED")
        self.assertFalse(r.ok)
        self.assertIn("no executors in fanout", r.notes)
        self.assertEqual(r.payload["succeeded"], [])
        self.assertEqual(r.payload["events"], [])


class FanoutFailFastTests(unittest.TestCase):
    def test_fail_fast_drops_unstarted_routes(self):
        bad = RaisingAdapter("bad")
        g1, g2 = OkAdapter("good1"), OkAdapter("good2")
        # max_workers=1 makes the queue FIFO: 'bad' settles first and
        # sets the abort flag before either good route even starts.
        d = pd.ParallelDispatcher(
            FakeFederation({"bad": bad, "good1": g1, "good2": g2}),
            max_workers=1)
        r = d.fanout(acp.Op.NEW, ["bad", "good1", "good2"], {}, fail_fast=True)
        self.assertEqual(r.status, "FAILED")
        events = r.payload["events"]
        started = [e["executor"] for e in events if e["phase"] == "STARTED"]
        self.assertIn("bad", started)
        # un-started routes: no later STARTED events at all
        self.assertNotIn("good1", started)
        self.assertNotIn("good2", started)
        # and their adapters were never invoked
        self.assertEqual(g1.new_calls, [])
        self.assertEqual(g2.new_calls, [])
        self.assertEqual(sorted(r.payload["failed"]),
                         ["bad", "good1", "good2"])

    def test_without_fail_fast_all_routes_run_despite_hard_failure(self):
        bad = RaisingAdapter("bad")
        g1 = OkAdapter("good1")
        d = pd.ParallelDispatcher(
            FakeFederation({"bad": bad, "good1": g1}), max_workers=2)
        r = d.fanout(acp.Op.NEW, ["bad", "good1"], {}, fail_fast=False)
        self.assertEqual(r.status, "PARTIAL")
        self.assertEqual(len(g1.new_calls), 1)
        self.assertEqual(r.payload["succeeded"], ["good1"])


class FanoutEventTests(unittest.TestCase):
    def test_events_contain_started_and_terminal_per_route(self):
        names = ["a", "b", "c", "d"]
        fed, _ = _ok_fed(*names)
        d = pd.ParallelDispatcher(fed, max_workers=4)
        r = d.fanout(acp.Op.NEW, names, {})
        events = r.payload["events"]
        for name in names:
            started = [e for e in events
                       if e["executor"] == name and e["phase"] == "STARTED"]
            terminals = [e for e in events
                         if e["executor"] == name
                         and e["phase"] in ("DONE", "FAILED", "TIMEOUT")]
            self.assertEqual(len(started), 1)
            self.assertEqual(len(terminals), 1)
            self.assertEqual(terminals[0]["phase"], "DONE")
            # a terminal event can never precede its STARTED (coarse clock:
            # fast routes may share the same time.time() tick)
            self.assertLessEqual(started[0]["ts"], terminals[0]["ts"])
        # order matches concurrent completion: chronologically non-decreasing
        ts = [e["ts"] for e in events]
        self.assertEqual(ts, sorted(ts))
        # event records carry the five required fields
        for e in events:
            self.assertEqual(
                set(e), {"executor", "phase", "ts", "ok", "status"})

    def test_dispatch_events_returns_event_list(self):
        fed, _ = _ok_fed("a", "b")
        d = pd.ParallelDispatcher(fed)
        events = d.dispatch_events(acp.Op.NEW, ["a", "b"], {})
        self.assertIsInstance(events, list)
        phases = [e["phase"] for e in events]
        self.assertEqual(phases.count("STARTED"), 2)
        self.assertEqual(phases.count("DONE"), 2)
        self.assertEqual({e["executor"] for e in events}, {"a", "b"})


class AdapterKindPromptTests(unittest.TestCase):
    def test_prompt_kind_calls_adapter_prompt_not_new(self):
        a = OkAdapter("a")
        d = pd.ParallelDispatcher(FakeFederation({"a": a}))
        r = d.fanout(acp.Op.PROMPT, ["a"],
                     {"session_id": "s-1", "text": "hello"},
                     adapter_kind="prompt")
        self.assertEqual(r.status, "OK")
        self.assertEqual(a.prompt_calls, [("s-1", "hello")])
        self.assertEqual(a.new_calls, [])
        self.assertEqual(r.payload["per_executor"]["a"]["status"], "OK")
        self.assertEqual(
            r.payload["per_executor"]["a"]["payload"],
            {"session_id": "s-1", "chars": 5})


class IdempotencyTests(unittest.TestCase):
    def test_repeated_identical_fanout_does_not_respawn(self):
        a = OkAdapter("a")
        d = pd.ParallelDispatcher(FakeFederation({"a": a}))
        r1 = d.fanout(acp.Op.NEW, ["a"], {"project_id": "p"})
        r2 = d.fanout(acp.Op.NEW, ["a"], {"project_id": "p"})
        self.assertIs(r1, r2)          # cached aggregate, no re-spawn
        self.assertEqual(len(a.new_calls), 1)


class ParallelDispatchOfTests(unittest.TestCase):
    def test_two_specs_all_ok(self):
        a, b = OkAdapter("a"), OkAdapter("b")
        fed = FakeFederation({"a": a, "b": b})
        r = pd.parallel_dispatch_of(fed, [
            {"name": "s1", "op": acp.Op.NEW, "executors": ["a"], "payload": {}},
            {"name": "s2", "op": acp.Op.NEW, "executors": ["b"], "payload": {}},
        ])
        self.assertEqual(r.status, "OK")
        self.assertTrue(r.ok)
        self.assertEqual(r.payload["succeeded"], ["s1", "s2"])
        self.assertEqual(set(r.payload["per_spec"]), {"s1", "s2"})

    def test_mixed_specs_partial(self):
        a, b = RaisingAdapter("a"), OkAdapter("b")
        fed = FakeFederation({"a": a, "b": b})
        r = pd.parallel_dispatch_of(fed, [
            {"name": "s1", "op": acp.Op.NEW, "executors": ["a"], "payload": {}},
            {"name": "s2", "op": acp.Op.NEW, "executors": ["b"], "payload": {}},
        ])
        self.assertEqual(r.status, "PARTIAL")
        self.assertEqual(r.payload["failed"], ["s1"])
        self.assertEqual(r.payload["succeeded"], ["s2"])

    def test_zero_specs_degraded(self):
        r = pd.parallel_dispatch_of(FakeFederation({}), [])
        self.assertEqual(r.status, "DEGRADED")
        self.assertIn("no specs supplied to parallel_dispatch_of", r.notes)

    def test_summary_order_is_input_order_even_when_completion_is_reversed(self):
        """Regression: ``succeeded``/``failed``/``notes`` must follow the INPUT
        spec order, never the (nondeterministic) thread-completion order.

        ``s1`` uses a SlowAdapter so it finishes *after* the instant ``s2``; the
        old code built the summary from an ``as_completed``-filled dict, so the
        payload came back ``['s2', 's1']`` and CI flaked against the input-order
        expectation. Determinism must hold regardless of finish order.
        """
        slow_a = SlowAdapter("a", delay=0.25)   # spec s1 -> slow, finishes second
        fast_b = OkAdapter("b")                  # spec s2 -> fast, finishes first
        fed = FakeFederation({"a": slow_a, "b": fast_b})
        r = pd.parallel_dispatch_of(fed, [
            {"name": "s1", "op": acp.Op.NEW, "executors": ["a"], "payload": {}},
            {"name": "s2", "op": acp.Op.NEW, "executors": ["b"], "payload": {}},
        ])
        self.assertEqual(r.status, "OK")
        # input order, not completion order:
        self.assertEqual(r.payload["succeeded"], ["s1", "s2"])
        self.assertEqual(list(r.payload["per_spec"].keys()), ["s1", "s2"])
        self.assertEqual(r.payload["failed"], [])

    def test_failed_summary_stays_in_input_order(self):
        """A failing slow spec must still report in input order, and notes must
        be ordered by spec position (s1 fails, s2 ok)."""
        slow_raiser = RaisingAdapter("a")
        fast_b = OkAdapter("b")
        fed = FakeFederation({"a": slow_raiser, "b": fast_b})
        r = pd.parallel_dispatch_of(fed, [
            {"name": "s1", "op": acp.Op.NEW, "executors": ["a"], "payload": {}},
            {"name": "s2", "op": acp.Op.NEW, "executors": ["b"], "payload": {}},
        ])
        self.assertEqual(r.status, "PARTIAL")
        self.assertEqual(r.payload["succeeded"], ["s2"])
        self.assertEqual(r.payload["failed"], ["s1"])
        # only the failed spec appears in notes, by name:
        self.assertEqual([n.split(":")[0] for n in r.notes], ["s1"])


class RealFederationSmokeTests(unittest.TestCase):
    """Read-only smoke against the real registry: hermes new() degrades
    (NOT_LAUNCHABLE / NOT_IMPLEMENTED) on any machine — it never spawns,
    so the test stays deterministic and environment-safe."""

    def test_real_federation_fanout_degrades_without_spawning(self):
        fed_mod = _load("federation.py", _FED_MOD)
        fed = fed_mod.default_federation()
        d = pd.ParallelDispatcher(fed, max_workers=4)
        r = d.fanout(acp.Op.NEW, ["hermes"], {"project_id": "wl"})
        self.assertFalse(r.payload["per_executor"]["hermes"]["ok"])
        self.assertEqual(r.status, "DEGRADED")
        self.assertIn("hermes", r.payload["per_executor"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
