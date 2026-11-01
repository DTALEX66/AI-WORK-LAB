"""Passive receipts-evidence adapter for P1 parallel-dispatch fanout.

P3 sub_C — 可观测闭环（receipts 证据对接）.

Turns the *existing* :class:`ExecResult` aggregate that
``services/execution-federation/parallel_dispatch.py`` returns from
``ParallelDispatcher.fanout()`` (``executor='*'``; payload
``{per_executor, succeeded, failed, timed_out, unknown, events}``)
into the *existing* WORK-LAB receipts evidence structures from
``services/receipts/execution_evidence.py`` — no second ledger, no
second runtime.

Mapping (one :class:`ExecutionEvidence` row per executed route, plus
one batch row)::

    route ok=True / status OK      -> execution_completed
    route FAILED / TIMEOUT /
    UNKNOWN_EXECUTOR / SKIPPED...  -> execution_failed
    degraded adapter status
    (NOT_LAUNCHABLE / NOT_SUPPORTED
    / NOT_IMPLEMENTED / ...)       -> execution_failed (route-level)

The batch row's *event type* follows the batch status, so an all-
degraded batch (every route NOT_LAUNCHABLE / NOT_SUPPORTED, no hard
failure, status DEGRADED) is reported as execution_completed
*with reportedState=DEGRADED* — never execution_failed.  The
real-time fanout events (STARTED / DONE / FAILED / TIMEOUT,
{executor, phase, ts, ok, status}) are preserved **verbatim** as the
trace attachment — the adapter adds, reorders or drops nothing.

PASSIVE guarantees (spec §22 / §40, passive federation philosophy):

* read-only: the fanout ``ExecResult`` is the only input;
* no process spawn, no credential access, no new ledger file, no
  ReceiptLedger write, no policy application — a pure mapping into
  the existing receipts types;
* failures are never dropped or coerced: an UNKNOWN_EXECUTOR or
  FAILED route stays a failure row in the output.

Module loading mirrors the services/ convention: no package
``__init__.py``; receipts modules load under stable ``sys.modules``
names so the ``ExecutionEvidence`` type stays a singleton across
imports, and the federation module is resolved relative to this
file.
"""
from __future__ import annotations

import importlib.util as _ilu
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_HERE = Path(__file__).resolve().parent
_EFFED = _HERE.parent / "execution-federation"

_EE_NAME = "services_receipts_execution_evidence"
_PD_NAME = "services_execution_federation_parallel_dispatch"

#: route statuses that count as *hard* failures (mirrors
#: parallel_dispatch.HARD_FAILURE_STATUSES).  Everything else that
#: is not ok=True is a degraded adapter status — still a *route*
#: failure row, but never enough to mark the batch FAILED.
HARD_FAILURE_STATUSES = frozenset({"FAILED", "TIMEOUT", "UNKNOWN_EXECUTOR"})

BATCH_EVENT_TYPE = "execution_completed"

__all__ = [
    "ParallelDispatchEvidence",
    "HARD_FAILURE_STATUSES",
    "BATCH_EVENT_TYPE",
]


def _load(name: str, module_name: str, directory: Path):
    existing = sys.modules.get(module_name)
    if existing is not None:
        return existing
    path = directory / name
    spec = _ilu.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {module_name} from {path}")
    module = _ilu.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _ee() -> Any:
    """The existing receipts execution-evidence module (read-only use)."""
    return _load("execution_evidence.py", _EE_NAME, _HERE)


def _pd_module() -> Any:
    """The P1 parallel-dispatch module, loaded through the same stable
    ``sys.modules`` names it uses, so ``ExecResult`` stays a singleton."""
    if _PD_NAME in sys.modules:
        return sys.modules[_PD_NAME]
    # _acp() registers the shared ACP base first — required so the
    # module-level ``_acp()`` calls inside parallel_dispatch resolve.
    _load("acp_adapter.py", "services_execution_federation_acp_adapter", _EFFED)
    return _load("parallel_dispatch.py", _PD_NAME, _EFFED)


def _acp_module() -> Any:
    """The shared ACP base (``Op`` / ``ExecResult``) through the same
    stable ``sys.modules`` names the federation uses.

    ``parallel_dispatch`` itself does not re-export ``ExecResult`` at
    module level (it calls ``_acp()`` internally); the type check below
    must use the same class the fanout results were built from."""
    return _pd_module()._acp()


def _route_outcome(row: dict[str, Any]) -> str:
    """Classify one route row: succeeded | timed_out | unknown |
    failed | degraded — mirroring the fanout partition rules."""
    if row.get("ok") is True:
        return "succeeded"
    status = str(row.get("status") or "")
    if status == "TIMEOUT":
        return "timed_out"
    if status == "UNKNOWN_EXECUTOR":
        return "unknown"
    if status in HARD_FAILURE_STATUSES:
        return "failed"
    return "degraded"


def _route_event_type(outcome: str) -> str:
    return "execution_completed" if outcome == "succeeded" else "execution_failed"


def _occurred_iso(ts: Any) -> str:
    """Event timestamp -> ISO-8601 (UTC).  Falls back to now for
    malformed values — the timestamp is recorded, never fabricated
    into the outcome."""
    if ts:
        try:
            return datetime.fromtimestamp(float(ts), tz=timezone.utc).isoformat().replace("+00:00", "Z")
        except (ValueError, OSError, OverflowError, TypeError):
            pass
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class ParallelDispatchEvidence:
    """Receipts-side projection of one P1 fanout batch.

    * :attr:`rows`          — one existing ``ExecutionEvidence`` record
      per executed route (the per-action rows);
    * :attr:`batch_row`     — one record for the batch aggregate
      (status + succeeded/failed/timed_out/unknown partitions);
    * :attr:`trace`         — the fanout's real-time events list,
      preserved verbatim (STARTED / DONE / FAILED / TIMEOUT).

    Built strictly from the fanout ``ExecResult``; never touches
    adapters, processes, credentials, ledgers or policy.
    """

    def __init__(self, rows: list[Any], batch_row: Any,
                 trace: list[dict[str, Any]], *, source: str) -> None:
        self.rows = list(rows)
        self.batch_row = batch_row
        self.trace = list(trace)
        self.source = source

    # ------------------------------------------------------------------
    @classmethod
    def from_fanout(cls, result: Any, *, source: str = "parallel-dispatch") -> "ParallelDispatchEvidence":
        """Map a P1 fanout ``ExecResult`` into existing receipts
        evidence.  ``result`` is the aggregate returned by
        ``ParallelDispatcher.fanout()``: ``executor='*'`` with payload
        ``{per_executor, succeeded, failed, timed_out, unknown,
        events}`` (or a synthetic object with the same surface)."""
        ee = _ee()
        if not isinstance(result, _acp_module().ExecResult):
            raise TypeError("from_fanout() expects a P1 fanout ExecResult")

        payload = dict(getattr(result, "payload", None) or {})
        batch_status = str(getattr(result, "status", "") or "")
        partitions = {
            "succeeded": [str(x) for x in payload.get("succeeded") or []],
            "failed": [str(x) for x in payload.get("failed") or []],
            "timed_out": [str(x) for x in payload.get("timed_out") or []],
            "unknown": [str(x) for x in payload.get("unknown") or []],
        }
        events = payload.get("events")
        if not isinstance(events, list):
            raise TypeError("fanout payload must carry an 'events' list (trace)")
        trace = [dict(e) for e in events]

        rows: list[Any] = []
        seen_ids: set[str] = set()
        per_executor = payload.get("per_executor") or {}
        for name in per_executor:
            row = dict(per_executor.get(name) or {})
            outcome = _route_outcome(row)
            evidence = ee.ExecutionEvidence(
                event_id=f"pd-{source}-{name}-{batch_status}",
                event_type=_route_event_type(outcome),
                occurred_at=_now_iso(),
                collector_id=f"parallel-dispatch-{source}",
                adapter_id=str(name),
                execution_id=str(name),
                reported_state=str(row.get("status") or ""),
                source_ref=f"parallel-dispatch/{source}",
                evidence_level="C",
                quality="SOURCE_REPORTED",
                payload={
                    "op": row.get("op"),
                    "executor": row.get("executor", str(name)),
                    "ok": row.get("ok"),
                    "status": row.get("status"),
                    "outcome": outcome,
                    "notes": [str(n) for n in (row.get("notes") or [])],
                },
            )
            evidence.validate()
            if evidence.event_id in seen_ids:
                raise ValueError(f"duplicate evidence event_id: {evidence.event_id!r}")
            seen_ids.add(evidence.event_id)
            rows.append(evidence)

        batch_event_type = "execution_failed" if batch_status == "FAILED" else BATCH_EVENT_TYPE
        batch_row = ee.ExecutionEvidence(
            event_id=f"pd-{source}-batch-{batch_status}",
            event_type=batch_event_type,
            occurred_at=_now_iso(),
            collector_id=f"parallel-dispatch-{source}",
            adapter_id="*",
            reported_state=batch_status,
            source_ref=f"parallel-dispatch/{source}",
            evidence_level="C",
            quality="SOURCE_REPORTED",
            payload={
                "batch_status": batch_status,
                "succeeded": partitions["succeeded"],
                "failed": partitions["failed"],
                "timed_out": partitions["timed_out"],
                "unknown": partitions["unknown"],
                "route_count": len(rows),
            },
        )
        batch_row.validate()
        if batch_row.event_id in seen_ids:
            raise ValueError(f"duplicate evidence event_id: {batch_row.event_id!r}")

        return cls(rows, batch_row, trace, source=source)

    # ------------------------------------------------------------------
    def to_dict(self) -> dict[str, Any]:
        """Full projection as existing receipts records (batch row
        first, then the per-route rows; trace kept as a verbatim
        attachment)."""
        return {
            "source": self.source,
            "batch": self.batch_row.as_record(),
            "rows": [r.as_record() for r in self.rows],
            "trace": list(self.trace),
        }


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
