"""Negative controls for P3 sub_C: ParallelDispatchEvidence.

The nf_* gates the spec requires — each asserts the adapter does NOT
silently distort the fanout facts:

* a hard-failed route is NOT coerced to success;
* an all-degraded batch is NOT reported FAILED;
* an UNKNOWN_EXECUTOR route is NOT dropped from the evidence;
* the events trace is NOT silently lost.

Synthetic fanout ExecResults are built from the real P1
``_acp()`` / ``acp_adapter.py`` types (scratch-runner pattern), so no
real federation is involved.
"""
from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FED = ROOT / "services" / "execution-federation"
REC = ROOT / "services" / "receipts"

_ACP_MOD = "services_execution_federation_acp_adapter"
_PDE_MOD = "services_receipts_parallel_dispatch_evidence"


def _load(path: Path, module_name: str):
    if module_name in sys.modules:
        return sys.modules[module_name]
    spec = importlib.util.spec_from_file_location(module_name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


acp = _load(FED / "acp_adapter.py", _ACP_MOD)
pde = _load(REC / "parallel_dispatch_evidence.py", _PDE_MOD)


def _route(name: str, ok: bool, status: str) -> dict:
    return acp.ExecResult(acp.Op.NEW, name, ok=ok, status=status,
                          notes=[f"{name} {status}"]).to_dict()


def _batch(*routes: tuple[str, bool, str], evts: list[dict] | None = None,
           succeeded: list[str] | None = None, failed: list[str] | None = None,
           timed_out: list[str] | None = None, unknown: list[str] | None = None,
           status: str = "PARTIAL") -> object:
    per = {n: _route(n, ok, s) for n, ok, s in routes}
    if succeeded is None:
        succeeded = [n for n, ok, _ in routes if ok]
    if failed is None:
        failed = [n for n, ok, s in routes
                  if not ok and s in ("FAILED", "SKIPPED_FAILFAST")]
    if timed_out is None:
        timed_out = [n for n, ok, s in routes if not ok and s == "TIMEOUT"]
    if unknown is None:
        unknown = [n for n, ok, s in routes if not ok and s == "UNKNOWN_EXECUTOR"]
    return acp.ExecResult(
        acp.Op.NEW, "*", ok=(status == "OK"), status=status,
        payload={
            "per_executor": per,
            "succeeded": list(succeeded),
            "failed": list(failed),
            "timed_out": list(timed_out),
            "unknown": list(unknown),
            "events": [dict(e) for e in (evts or [])],
        },
        notes=["batch note"],
    )


class HardFailureNotCoercedTests(unittest.TestCase):
    """a hard-failed route must stay a failure row, never success."""

    def test_nf_hard_failed_route_not_coerced_to_success(self):
        r = _batch(("a", True, "OK"), ("b", False, "FAILED"))
        ev = pde.ParallelDispatchEvidence.from_fanout(r)
        rows = {row.adapter_id: row for row in ev.rows}
        rec_b = rows["b"].as_record()
        self.assertEqual(rec_b["eventType"], "execution_failed")
        self.assertEqual(rec_b["payload"]["outcome"], "failed")
        self.assertEqual(rec_b["reportedState"], "FAILED")
        self.assertNotIn("b", ev.batch_row.payload["succeeded"])
        # and the success route stays a success row
        self.assertEqual(rows["a"].as_record()["eventType"], "execution_completed")

    def test_nf_failed_route_never_reports_success_outcome(self):
        r = _batch(("b", False, "FAILED"),)
        ev = pde.ParallelDispatchEvidence.from_fanout(r)
        self.assertTrue(all(row.payload["outcome"] != "succeeded"
                           for row in ev.rows))


class AllDegradedNotFailedTests(unittest.TestCase):
    """all routes degraded, no hard failure -> batch is DEGRADED,
    never reported FAILED."""

    def test_nf_all_degraded_batch_not_reported_failed(self):
        r = _batch(
            ("a", False, "NOT_LAUNCHABLE"),
            ("b", False, "NOT_SUPPORTED"),
            status="DEGRADED",
        )
        ev = pde.ParallelDispatchEvidence.from_fanout(r)
        rec = ev.batch_row.as_record()
        self.assertEqual(rec["reportedState"], "DEGRADED")
        self.assertNotEqual(rec["eventType"], "execution_failed")
        self.assertEqual(rec["payload"]["batch_status"], "DEGRADED")
        # degraded routes stay visible as failure rows, not dropped
        self.assertEqual(len(ev.rows), 2)
        self.assertTrue(all(row.event_type == "execution_failed"
                           for row in ev.rows))

    def test_nf_degraded_batch_failed_list_empty(self):
        r = _batch(("a", False, "NOT_LAUNCHABLE"), status="DEGRADED")
        ev = pde.ParallelDispatchEvidence.from_fanout(r)
        self.assertEqual(ev.batch_row.payload["failed"], [])
        self.assertEqual(ev.batch_row.payload["succeeded"], [])


class UnknownExecutorNotDroppedTests(unittest.TestCase):
    """an UNKNOWN_EXECUTOR route must remain a failure row — never
    dropped or silently coerced to success."""

    def test_nf_unknown_executor_route_not_dropped(self):
        r = _batch(("a", True, "OK"), ("ghost", False, "UNKNOWN_EXECUTOR"))
        ev = pde.ParallelDispatchEvidence.from_fanout(r)
        ids = [row.adapter_id for row in ev.rows]
        self.assertEqual(ids, ["a", "ghost"])
        rec = {row.adapter_id: row for row in ev.rows}["ghost"].as_record()
        self.assertEqual(rec["eventType"], "execution_failed")
        self.assertEqual(rec["reportedState"], "UNKNOWN_EXECUTOR")
        self.assertEqual(rec["payload"]["outcome"], "unknown")

    def test_nf_unknown_executor_partition_preserved(self):
        r = _batch(("a", True, "OK"), ("ghost", False, "UNKNOWN_EXECUTOR"))
        ev = pde.ParallelDispatchEvidence.from_fanout(r)
        self.assertEqual(ev.batch_row.payload["unknown"], ["ghost"])
        self.assertNotIn("ghost", ev.batch_row.payload["succeeded"])


class EventsTraceNotLostTests(unittest.TestCase):
    """the fanout events trace must not be silently lost."""

    def test_nf_events_trace_preserved(self):
        events = [
            {"executor": "a", "phase": "STARTED", "ts": 1.0, "ok": None, "status": None},
            {"executor": "a", "phase": "DONE", "ts": 2.0, "ok": True, "status": "OK"},
            {"executor": "b", "phase": "STARTED", "ts": 3.0, "ok": None, "status": None},
            {"executor": "b", "phase": "FAILED", "ts": 4.0, "ok": False, "status": "FAILED"},
        ]
        r = _batch(("a", True, "OK"), ("b", False, "FAILED"), evts=events)
        ev = pde.ParallelDispatchEvidence.from_fanout(r)
        self.assertEqual(ev.trace, events)
        out = ev.to_dict()
        self.assertEqual(out["trace"], events)
        self.assertEqual(len(out["trace"]), 4)

    def test_nf_empty_events_trace_still_present(self):
        r = _batch(("a", True, "OK"), evts=[])
        ev = pde.ParallelDispatchEvidence.from_fanout(r)
        self.assertEqual(ev.trace, [])
        self.assertIn("trace", ev.to_dict())


if __name__ == "__main__":
    unittest.main()
