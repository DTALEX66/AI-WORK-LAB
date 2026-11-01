"""Negative-control tests for parallel dispatch P1 core.

Complements test_parallel_dispatch.py: each test pins one *boundary* of
the aggregation contract — what the status must NOT be when a given mix
of routes settles.  Deterministic stub adapters; nothing here spawns a
process or touches credentials.
"""
from __future__ import annotations

import importlib.util
import sys
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


# -- stubs (same deterministic, launch-free shape as the unit tests) ----

class OkAdapter(acp.ExecutorAcpAdapter):
    def __init__(self, name: str) -> None:
        self.executor = name
        self.new_calls: list[dict] = []

    def new(self, **kw):
        self.new_calls.append(dict(kw))
        return acp.ExecResult(acp.Op.NEW, self.executor, ok=True, status="OK")


class RaisingAdapter(acp.ExecutorAcpAdapter):
    def __init__(self, name: str) -> None:
        self.executor = name
        self.new_calls: list[dict] = []

    def new(self, **kw):
        self.new_calls.append(dict(kw))
        raise RuntimeError(f"{self.executor} hard failure (stub)")


class SlowAdapter(acp.ExecutorAcpAdapter):
    def __init__(self, name: str, delay: float = 0.4) -> None:
        self.executor = name
        self._delay = delay
        self.new_calls: list[dict] = []

    def new(self, **kw):
        import time as _t
        _t.sleep(self._delay)
        self.new_calls.append(dict(kw))
        return acp.ExecResult(acp.Op.NEW, self.executor, ok=True, status="OK")


class FakeFederation:
    def __init__(self, adapters: dict) -> None:
        self._adapters = dict(adapters)

    def get(self, name: str):
        return self._adapters.get(name)


def _dispatch(adapters: dict, names: list[str], **kw):
    d = pd.ParallelDispatcher(FakeFederation(adapters),
                              max_workers=kw.pop("max_workers", 4))
    return d.fanout(acp.Op.NEW, names, {}, **kw)


# ------------------------------------------------------------------------

class OneFailureIsPartialNotOkOrFailed(unittest.TestCase):
    def test_one_of_many_routes_failing_is_partial(self):
        r = _dispatch({"a": OkAdapter("a"), "b": OkAdapter("b"),
                       "c": RaisingAdapter("c")},
                     ["a", "b", "c"])
        self.assertEqual(r.status, "PARTIAL")
        self.assertNotEqual(r.status, "OK")
        self.assertNotEqual(r.status, "FAILED")
        self.assertEqual(r.payload["succeeded"], ["a", "b"])
        self.assertEqual(r.payload["failed"], ["c"])


class AllFailuresIsFailedNotPartial(unittest.TestCase):
    def test_every_route_failing_is_failed_not_partial(self):
        r = _dispatch({"a": RaisingAdapter("a"), "b": RaisingAdapter("b")},
                     ["a", "b"])
        self.assertEqual(r.status, "FAILED")
        self.assertNotEqual(r.status, "PARTIAL")
        self.assertFalse(r.ok)
        self.assertEqual(sorted(r.payload["failed"]), ["a", "b"])
        self.assertEqual(r.payload["succeeded"], [])


class UnknownExecutorIsQuarantinedNotFatal(unittest.TestCase):
    def test_unknown_route_marks_itself_no_exception_no_batch_death(self):
        ok_a = OkAdapter("a")
        r = _dispatch({"a": ok_a}, ["a", "ghost", "phantom"])
        # batch survived: no exception, well-formed aggregate
        self.assertEqual(r.status, "PARTIAL")
        self.assertEqual(r.payload["unknown"], ["ghost", "phantom"])
        for name in ("ghost", "phantom"):
            entry = r.payload["per_executor"][name]
            self.assertEqual(entry["status"], "UNKNOWN_EXECUTOR")
            self.assertFalse(entry["ok"])
        self.assertEqual(r.payload["succeeded"], ["a"])

    def test_all_unknown_is_failed(self):
        r = _dispatch({}, ["g1", "g2"])
        self.assertEqual(r.status, "FAILED")
        self.assertEqual(r.payload["unknown"], ["g1", "g2"])


class TimeoutIsolation(unittest.TestCase):
    def test_slow_route_times_out_normal_route_stays_ok(self):
        good = OkAdapter("good")
        r = _dispatch({"good": good, "slow": SlowAdapter("slow", 0.4)},
                     ["good", "slow"], per_executor_timeout=0.05)
        self.assertEqual(r.payload["per_executor"]["slow"]["status"], "TIMEOUT")
        self.assertFalse(r.payload["per_executor"]["slow"]["ok"])
        self.assertEqual(r.payload["per_executor"]["good"]["status"], "OK")
        self.assertTrue(r.payload["per_executor"]["good"]["ok"])
        self.assertEqual(r.payload["timed_out"], ["slow"])
        self.assertEqual(r.payload["succeeded"], ["good"])
        self.assertEqual(len(good.new_calls), 1)


class EventCompleteness(unittest.TestCase):
    def test_every_route_emits_started_plus_exactly_one_terminal(self):
        adapters = {f"e{i}": OkAdapter(f"e{i}") for i in range(4)}
        adapters["f0"] = RaisingAdapter("f0")
        r = _dispatch(adapters, ["e0", "e1", "e2", "e3", "f0"])
        events = r.payload["events"]
        for name in adapters:
            started = [e for e in events
                       if e["executor"] == name and e["phase"] == "STARTED"]
            terminals = [e for e in events
                         if e["executor"] == name
                         and e["phase"] in ("DONE", "FAILED", "TIMEOUT")]
            self.assertEqual(len(started), 1, f"{name} missing STARTED")
            self.assertEqual(len(terminals), 1, f"{name} missing terminal")
            if name == "f0":
                self.assertEqual(terminals[0]["phase"], "FAILED")
                self.assertIs(terminals[0]["ok"], False)
            else:
                self.assertEqual(terminals[0]["phase"], "DONE")
                self.assertIs(terminals[0]["ok"], True)


class ZeroExecutorIsDegradedNotOk(unittest.TestCase):
    def test_empty_fanout_degraded_with_note(self):
        r = _dispatch({}, [])
        self.assertEqual(r.status, "DEGRADED")
        self.assertNotEqual(r.status, "OK")
        self.assertFalse(r.ok)
        self.assertIn("no executors in fanout", r.notes)


if __name__ == "__main__":
    unittest.main(verbosity=2)
