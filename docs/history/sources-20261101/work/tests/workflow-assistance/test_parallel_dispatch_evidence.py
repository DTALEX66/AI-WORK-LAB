"""Unit tests for P3 sub_C: ParallelDispatchEvidence.from_fanout.

Builds *synthetic* fanout ExecResults (the real
``services/execution-federation/parallel_dispatch.py`` ``_acp()`` /
``acp_adapter.py`` types, loaded through the P1 scratch-runner
pattern so no real federation is involved) and asserts the mapping
into the existing receipts evidence structures:

* one ExecutionEvidence row per executed route (mirror of how
  execution_evidence records per-action rows);
* the succeeded / failed / timed_out / unknown partition lists are
  preserved on the batch row;
* the real-time fanout events are kept verbatim as the trace
  attachment;
* an all-success batch -> OK rows all execution_completed;
* a PARTIAL batch (one hard failure) -> failed row + PARTIAL batch;
* a DEGRADED batch (all routes NOT_LAUNCHABLE) -> reportedState
  DEGRADED, never reported as FAILED;
* an UNKNOWN_EXECUTOR route and a TIMEOUT route stay failure rows.
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


# The real P1 _acp() base — synthetic results use the genuine
# ExecResult/Op types, exactly what fanout() returns.
acp = _load(FED / "acp_adapter.py", _ACP_MOD)
pde = _load(REC / "parallel_dispatch_evidence.py", _PDE_MOD)


def _fanout_result(*, executors_status: dict[str, tuple[bool, str]],
                   events: list[dict] | None = None,
                   notes: list[str] | None = None) -> object:
    """Assemble the exact fanout ExecResult shape P1's _aggregate()
    produces: per_executor dicts + partition lists + events."""
    per_executor: dict[str, dict] = {}
    succeeded: list[str] = []
    failed: list[str] = []
    timed_out: list[str] = []
    unknown: list[str] = []
    degraded: list[str] = []
    all_notes: list[str] = []
    for name, (ok, status) in executors_status.items():
        all_status = "OK" if ok else status
        per_executor[name] = acp.ExecResult(
            acp.Op.NEW, name, ok=ok, status=all_status,
            notes=([f"{name} note"] if not ok else []),
        ).to_dict()
        if ok:
            succeeded.append(name)
        elif status == "TIMEOUT":
            timed_out.append(name)
        elif status == "UNKNOWN_EXECUTOR":
            unknown.append(name)
        elif status in ("FAILED", "SKIPPED_FAILFAST"):
            failed.append(name)
        else:
            degraded.append(name)
        if not ok:
            all_notes.append(f"{name}: {all_status}")
    if not executors_status:
        batch = "DEGRADED"
    elif len(succeeded) == len(executors_status):
        batch = "OK"
    elif not succeeded and not degraded:
        batch = "FAILED"
    elif not succeeded:
        batch = "DEGRADED"
    else:
        batch = "PARTIAL"
    if events is not None:
        ev = [dict(e) for e in events]
    else:
        ev = []
        for i, (n, (ok, s)) in enumerate(executors_status.items()):
            ev.append({"executor": n, "phase": "STARTED", "ts": 1000.0 + i,
                       "ok": None, "status": None})
            ev.append({"executor": n, "phase": "DONE" if ok else "FAILED",
                       "ts": 1001.0 + i, "ok": ok, "status": "OK" if ok else s})
    return acp.ExecResult(acp.Op.NEW, "*", ok=(batch == "OK"), status=batch,
                          payload={
                              "per_executor": per_executor,
                              "succeeded": succeeded,
                              "failed": failed,
                              "timed_out": timed_out,
                              "unknown": unknown,
                              "events": ev,
                          },
                          notes=notes or all_notes)


class FromFanoutMappingTests(unittest.TestCase):
    """The five requested fanout shapes -> receipts rows + partitions + trace."""

    def test_ok_all_success_batch_ok_rows_all_completed(self):
        r = _fanout_result(executors_status={"a": (True, "OK"),
                                              "b": (True, "OK")})
        ev = pde.ParallelDispatchEvidence.from_fanout(r)
        self.assertEqual(r.status, "OK")
        self.assertEqual([row.adapter_id for row in ev.rows], ["a", "b"])
        self.assertTrue(all(row.event_type == "execution_completed"
                           for row in ev.rows))
        self.assertTrue(all(row.payload["outcome"] == "succeeded"
                           for row in ev.rows))
        self.assertEqual(ev.batch_row.reported_state, "OK")
        self.assertEqual(ev.batch_row.payload["succeeded"], ["a", "b"])
        self.assertEqual(ev.batch_row.payload["failed"], [])
        self.assertEqual(ev.batch_row.payload["timed_out"], [])
        self.assertEqual(ev.batch_row.payload["unknown"], [])

    def test_partial_one_failure_failed_row_kept_batch_partial(self):
        r = _fanout_result(executors_status={"a": (True, "OK"),
                                              "b": (False, "FAILED")})
        ev = pde.ParallelDispatchEvidence.from_fanout(r)
        self.assertEqual(r.status, "PARTIAL")
        rows = {row.adapter_id: row for row in ev.rows}
        self.assertEqual(rows["a"].event_type, "execution_completed")
        self.assertEqual(rows["b"].event_type, "execution_failed")
        self.assertEqual(rows["b"].payload["outcome"], "failed")
        self.assertEqual(rows["b"].reported_state, "FAILED")
        bp = ev.batch_row.payload
        self.assertEqual(bp["succeeded"], ["a"])
        self.assertEqual(bp["failed"], ["b"])
        self.assertEqual(bp["batch_status"], "PARTIAL")

    def test_degraded_all_not_launchable_batch_not_failed(self):
        r = _fanout_result(executors_status={"a": (False, "NOT_LAUNCHABLE"),
                                              "b": (False, "NOT_SUPPORTED")})
        self.assertEqual(r.status, "DEGRADED")
        ev = pde.ParallelDispatchEvidence.from_fanout(r)
        self.assertEqual(ev.batch_row.reported_state, "DEGRADED")
        # the DEGRADED batch must NOT be an execution_failed record
        self.assertNotEqual(ev.batch_row.event_type, "execution_failed")
        self.assertEqual(ev.batch_row.payload["failed"], [])
        self.assertEqual(ev.batch_row.payload["unknown"], [])
        # every route row is still a failure row (route-level outcome),
        # classified as degraded, none coerced to success
        rows = {row.adapter_id: row for row in ev.rows}
        self.assertEqual(rows["a"].event_type, "execution_failed")
        self.assertEqual(rows["b"].event_type, "execution_failed")
        self.assertTrue(all(row.payload["outcome"] == "degraded"
                           for row in ev.rows))

    def test_route_unknown_executor_stays_failure_row(self):
        r = _fanout_result(executors_status={"a": (True, "OK"),
                                              "ghost": (False, "UNKNOWN_EXECUTOR")})
        ev = pde.ParallelDispatchEvidence.from_fanout(r)
        rows = {row.adapter_id: row for row in ev.rows}
        self.assertIn("ghost", rows)
        self.assertEqual(rows["ghost"].event_type, "execution_failed")
        self.assertEqual(rows["ghost"].payload["outcome"], "unknown")
        self.assertEqual(rows["ghost"].reported_state, "UNKNOWN_EXECUTOR")
        self.assertEqual(ev.batch_row.payload["unknown"], ["ghost"])

    def test_route_timeout_stays_failure_row_partition_preserved(self):
        r = _fanout_result(executors_status={"a": (True, "OK"),
                                              "slow": (False, "TIMEOUT")})
        ev = pde.ParallelDispatchEvidence.from_fanout(r)
        rows = {row.adapter_id: row for row in ev.rows}
        self.assertEqual(rows["slow"].event_type, "execution_failed")
        self.assertEqual(rows["slow"].payload["outcome"], "timed_out")
        self.assertEqual(ev.batch_row.payload["timed_out"], ["slow"])
        self.assertEqual(ev.batch_row.payload["succeeded"], ["a"])

    def test_events_trace_attached_verbatim(self):
        custom_events = [
            {"executor": "a", "phase": "STARTED", "ts": 1.0, "ok": None, "status": None},
            {"executor": "a", "phase": "DONE", "ts": 2.0, "ok": True, "status": "OK"},
        ]
        r = _fanout_result(executors_status={"a": (True, "OK")},
                           events=custom_events)
        ev = pde.ParallelDispatchEvidence.from_fanout(r)
        self.assertEqual(len(ev.trace), 2)
        self.assertEqual(ev.trace[0]["phase"], "STARTED")
        self.assertEqual(ev.trace[1], {"executor": "a", "phase": "DONE",
                                        "ts": 2.0, "ok": True, "status": "OK"})
        self.assertIn("trace", ev.to_dict())
        self.assertEqual(ev.to_dict()["trace"], custom_events)

    def test_source_label_applies_to_records(self):
        r = _fanout_result(executors_status={"a": (True, "OK")})
        ev = pde.ParallelDispatchEvidence.from_fanout(
            r, source="wf-2026-09-20")
        self.assertEqual(ev.source, "wf-2026-09-20")
        rec = ev.batch_row.as_record()
        self.assertEqual(rec["adapterId"], "*")
        self.assertTrue(rec["eventId"].startswith("pd-wf-2026-09-20-batch-"))
        self.assertEqual(rec["sourceRef"], "parallel-dispatch/wf-2026-09-20")


if __name__ == "__main__":
    unittest.main()
