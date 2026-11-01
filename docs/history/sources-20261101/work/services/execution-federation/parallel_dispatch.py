"""Parallel dispatch — P1 concurrency-orchestration layer for the
WORK-LAB Execution Federation.

Fans out one ACP operation (NEW / PROMPT) to several executor adapters
in parallel, streams real-time STARTED / DONE / FAILED / TIMEOUT events,
isolates per-route failures (one route's exception, timeout or unknown
executor never takes down the batch), and aggregates everything back
into the *existing* :class:`ExecResult` — no second result type, no
second ledger, no second runtime.

Iron rules honoured (spec §22 no second engine / §40 no second
updater-runtime, passive federation philosophy):

* the dispatcher is PASSIVE orchestration: it never launches, spawns,
  reads credentials, or applies policy.  Each route only invokes the
  existing adapter's ``new()`` / ``prompt()``; the adapter remains the
  source of launch decisions (launchable / not);
* the ``ThreadPoolExecutor`` is concurrency-shape orchestration only,
  not a new executor runtime;
* per-route results and the batch aggregate are the existing
  ``ExecResult``; receipt / evidence aggregation (services/receipts,
  execution_evidence, evidence_aggregator) consumes them unchanged;
* permissions still flow through the WORK-LAB Permission Gate — the
  dispatcher orchestrates and aggregates, it never authorises.

Loading convention matches the rest of services/: no package
``__init__.py``; the shared ACP base is loaded through the stable
``sys.modules`` name so ``Op`` / ``ExecResult`` stay singletons.
"""
from __future__ import annotations

import concurrent.futures
import importlib.util as _ilu
import json
import queue
import sys
import threading
import time
from pathlib import Path
from typing import Any, Iterator, Mapping

_HERE = Path(__file__).resolve().parent
_ACP_NAME = "services_execution_federation_acp_adapter"

#: route statuses that count as *hard* failures (trigger fail_fast, and
#: drive the aggregate toward FAILED).  Degraded adapter statuses such as
#: NOT_LAUNCHABLE / NOT_SUPPORTED / NOT_IMPLEMENTED are *not* hard.
HARD_FAILURE_STATUSES = frozenset({"FAILED", "TIMEOUT", "UNKNOWN_EXECUTOR"})

__all__ = [
    "ParallelDispatcher",
    "parallel_dispatch_of",
    "parallel_dispatch_stream",
    "HARD_FAILURE_STATUSES",
]


def _acp():
    existing = sys.modules.get(_ACP_NAME)
    if existing is not None and hasattr(existing, "ExecutorAcpAdapter"):
        return existing
    spec = _ilu.spec_from_file_location(_ACP_NAME, _HERE / "acp_adapter.py")
    module = _ilu.module_from_spec(spec)
    sys.modules[module.name] = module
    spec.loader.exec_module(module)
    return module


def _coerce_op(op: Any):
    acp = _acp()
    if isinstance(op, acp.Op):
        return op
    try:
        return acp.Op(op)
    except ValueError:
        raise ValueError(
            f"unknown ACP op {op!r}; expected one of {[o.value for o in acp.Op]}"
        ) from None


class _RunState:
    """Per-fanout shared state, guarded by one lock.

    ``events`` is filled *in real time* (STARTED when a route actually
    starts, terminal when it settles), so upper layers can observe
    progress instead of only the final aggregate.
    """

    def __init__(self, event_stream: "queue.Queue | None" = None) -> None:
        self.lock = threading.Lock()
        self.events: list[dict[str, Any]] = []
        self.results: dict[str, Any] = {}
        self.settled: set[str] = set()
        self.abort = threading.Event()
        # P3/sub_F: when a real-time stream is attached (fanout_stream),
        # every event appended below is also mirrored into this queue so
        # the generator can yield it the instant it happens — batch
        # (None) and stream runs share this exact same _RunState.
        self.event_stream = event_stream

    def append_event(self, event: dict[str, Any]) -> None:
        """Append ``event`` to the ordered list, and — when a stream is
        attached — mirror a copy into the queue immediately (P3/sub_F).

        ``fanout()`` callers pass no queue, so batch behaviour is
        byte-identical to the previous append-only semantics."""
        self.events.append(event)
        if self.event_stream is not None:
            self.event_stream.put(dict(event))


class ParallelDispatcher:
    """Fan one ACP operation out to several executors, in parallel.

    ``federation`` is the existing :class:`ExecutorFederation` (real or
    a test double with the same ``get()`` surface).  The dispatcher adds
    *only* concurrency orchestration on top of it — every route result
    and the batch aggregate are the existing ``ExecResult``.
    """

    def __init__(self, federation: Any, max_workers: int = 4,
                 default_timeout: float | None = None) -> None:
        if federation is None:
            raise ValueError("ParallelDispatcher requires an ExecutorFederation")
        self._federation = federation
        self._max_workers = max(1, int(max_workers))
        self._default_timeout = default_timeout
        # idempotence: repeated fanout of the same (op, executors,
        # payload, adapter_kind) does not re-spawn the routes (minimal
        # receipts-style dedup marker, spec P1).
        self._dedup: dict[tuple[str, ...], Any] = {}

    # ------------------------------------------------------------------
    # route execution (worker threads)
    # ------------------------------------------------------------------
    def _route_task(self, name: str, op: Any, payload: Any, adapter_kind: str,
                    state: _RunState, fail_fast: bool) -> None:
        acp = _acp()
        # fail_fast: once the first hard failure settled, routes that
        # have not started yet are dropped without even a STARTED event.
        if state.abort.is_set():
            with state.lock:
                if name not in state.settled:
                    state.results[name] = acp.ExecResult(
                        op, name, ok=False, status="SKIPPED_FAILFAST",
                        notes=["route not started: fail_fast aborted after an earlier hard failure"],
                    )
                    state.settled.add(name)
            return

        with state.lock:
            state.append_event({
                "executor": name, "phase": "STARTED", "ts": time.time(),
                "ok": None, "status": None,
            })

        # The dispatcher only *invokes* the adapter; the adapter stays
        # the source of launch / capability decisions (passive rule).
        adapter = self._federation.get(name)
        if adapter is None:
            res = acp.ExecResult(
                op, name, ok=False, status="UNKNOWN_EXECUTOR",
                notes=[f"executor {name!r} not registered in federation"],
            )
        else:
            try:
                if adapter_kind == "prompt":
                    data = payload or {}
                    res = adapter.prompt(
                        data.get("session_id", ""),
                        data.get("text", data.get("prompt", "")),
                    )
                else:
                    res = adapter.new(**(payload or {}))
            except Exception as exc:  # noqa: BLE001 - per-route isolation
                res = acp.ExecResult(
                    op, name, ok=False, status="FAILED",
                    notes=[f"{name} raised {exc!r}"],
                )
            else:
                if not isinstance(res, acp.ExecResult):
                    res = acp.ExecResult(
                        op, name, ok=False, status="FAILED",
                        notes=[f"{name} returned {res!r}, expected ExecResult"],
                    )

        hard = not res.ok and res.status in HARD_FAILURE_STATUSES
        phase = "DONE" if res.ok else "FAILED"
        with state.lock:
            if name in state.settled:
                # the collector already timed this route out — keep its
                # verdict, do not emit a late DONE after a TIMEOUT.
                return
            state.results[name] = res
            state.settled.add(name)
            state.append_event({
                "executor": name, "phase": phase, "ts": time.time(),
                "ok": res.ok, "status": res.status,
            })
        if hard and fail_fast:
            state.abort.set()

    # ------------------------------------------------------------------
    # aggregation
    # ------------------------------------------------------------------
    def _aggregate(self, op: Any, names: list[str], results: dict[str, Any],
                   events: list[dict[str, Any]], extra_notes: list[str]) -> Any:
        acp = _acp()
        per_executor = {
            n: results[n].to_dict() for n in names if results.get(n) is not None
        }
        succeeded: list[str] = []
        failed: list[str] = []
        timed_out: list[str] = []
        unknown: list[str] = []
        degraded: list[str] = []
        notes: list[str] = []
        for n in names:
            r = results.get(n)
            if r is None:
                continue
            if r.ok:
                succeeded.append(n)
            elif r.status == "TIMEOUT":
                timed_out.append(n)
            elif r.status == "UNKNOWN_EXECUTOR":
                unknown.append(n)
            elif r.status in HARD_FAILURE_STATUSES or r.status == "SKIPPED_FAILFAST":
                failed.append(n)
            else:
                degraded.append(n)
            if not r.ok:
                detail = "; ".join(r.notes)
                notes.append(f"{n}: {r.status}" + (f" ({detail})" if detail else ""))

        if not names:
            status = "DEGRADED"
        elif len(succeeded) == len(names):
            status = "OK"
        elif not succeeded and not degraded:
            # every route hard-failed (incl. all UNKNOWN_EXECUTOR)
            status = "FAILED"
        elif not succeeded:
            # all routes degraded (NOT_LAUNCHABLE etc.) but no hard failure
            status = "DEGRADED"
        else:
            status = "PARTIAL"

        payload = {
            "per_executor": per_executor,
            "succeeded": succeeded,
            "failed": failed,
            "timed_out": timed_out,
            "unknown": unknown,
            "events": events,
        }
        notes.extend(extra_notes)
        return acp.ExecResult(op, "*", ok=(status == "OK"), status=status,
                              payload=payload, notes=notes)

    @staticmethod
    def _dedup_key(op: Any, names: tuple[str, ...], payload: Any,
                   adapter_kind: str) -> tuple[str, ...]:
        return (
            op.value,
            *names,
            adapter_kind,
            json.dumps(payload, sort_keys=True, default=str),
        )

    # ------------------------------------------------------------------
    # public API
    # ------------------------------------------------------------------
    def fanout(self, op: Any, executors: list[str], payload: Mapping[str, Any],
               *, per_executor_timeout: float | None = None,
               fail_fast: bool = False, adapter_kind: str = "new") -> Any:
        """Run ``op`` on every executor in ``executors`` concurrently.

        * ``adapter_kind='new'`` calls ``adapter.new(**payload)``;
          ``adapter_kind='prompt'`` calls
          ``adapter.prompt(session_id, text)`` from ``payload``
          (``session_id`` / ``text`` (or ``prompt``)).
        * each route settles into its own ``ExecResult``; a per-route
          exception -> that route ``ok=False, status='FAILED'``, a
          deadline miss -> ``status='TIMEOUT'``, an unregistered name ->
          ``status='UNKNOWN_EXECUTOR'``; the other routes continue.
        * the batch aggregate is one ``ExecResult(op, executor='*')``
          with ``status`` in ``{OK, PARTIAL, DEGRADED, FAILED}`` and
          payload ``{per_executor, succeeded, failed, timed_out,
          unknown, events}`` where events stream
          STARTED/DONE/FAILED/TIMEOUT per route.
        * ``fail_fast=True``: after the first hard failure, routes that
          have not started are dropped (started ones run to completion).
        * edge cases: zero executors -> DEGRADED with a note; a repeated
          identical fanout returns the cached aggregate (no re-spawn).
        """
        acp = _acp()
        op = _coerce_op(op)
        names = list(dict.fromkeys(list(executors or [])))
        timeout = (per_executor_timeout if per_executor_timeout is not None
                   else self._default_timeout)

        key = self._dedup_key(op, tuple(names), payload, adapter_kind)
        cached = self._dedup.get(key)
        if cached is not None:
            return cached

        state = _RunState()
        if not names:
            result = self._aggregate(op, [], {}, [], ["no executors in fanout"])
            self._dedup[key] = result
            return result

        results, events = self._run_routes(
            state, names, op, payload, adapter_kind, timeout, fail_fast)
        result = self._aggregate(op, names, results, events, [])
        self._dedup[key] = result
        return result

    # ------------------------------------------------------------------
    # shared route execution / collection (used by fanout() and by the
    # P3/sub_F streaming generator fanout_stream() — one _RunState, one
    # collector, so batch and stream stay consistent by construction)
    # ------------------------------------------------------------------
    def _run_routes(self, state: "_RunState", names: list[str], op: Any,
                    payload: Any, adapter_kind: str,
                    timeout: float | None, fail_fast: bool) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        """Submit every route, collect terminals, record per-route TIMEOUT
        events for routes still pending at the deadline.  Shared by the
        batch API and the streaming generator so both observe the same
        ``_RunState`` events."""
        acp = _acp()
        with concurrent.futures.ThreadPoolExecutor(
            max_workers=self._max_workers, thread_name_prefix="pd-route-"
        ) as pool:
            futures = [
                pool.submit(self._route_task, n, op, payload, adapter_kind,
                            state, fail_fast)
                for n in names
            ]
            fut_name = {f: n for f, n in zip(futures, names)}
            deadline = (time.monotonic() + timeout
                        if timeout is not None else None)
            pending = set(futures)
            while pending:
                if deadline is not None:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        break
                    try:
                        done = next(
                            concurrent.futures.as_completed(
                                pending, timeout=remaining
                            )
                        )
                    except concurrent.futures.TimeoutError:
                        break
                else:
                    done = next(concurrent.futures.as_completed(pending))
                pending.discard(done)
                # each route task settled itself (results/events guarded
                # by state.lock); the loop only drives collection order.
            if deadline is not None and pending:
                with state.lock:
                    for fut in sorted(pending, key=lambda f: names.index(fut_name[f])):
                        name = fut_name[fut]
                        if name in state.settled:
                            continue
                        state.results[name] = acp.ExecResult(
                            op, name, ok=False, status="TIMEOUT",
                            notes=[f"{name} did not settle within {timeout}s"],
                        )
                        state.settled.add(name)
                        state.append_event({
                            "executor": name, "phase": "TIMEOUT", "ts": time.time(),
                            "ok": False, "status": "TIMEOUT",
                        })
            with state.lock:
                results = {n: state.results.get(n) for n in names}
                events = [dict(e) for e in state.events]
        return results, events

    def dispatch_events(self, op: Any, executors: list[str],
                        payload: Mapping[str, Any], *, adapter_kind: str = "new",
                        per_executor_timeout: float | None = None,
                        fail_fast: bool = False) -> list[dict[str, Any]]:
        """Run the fanout and return its real-time event list.

        Minimal streaming surface (spec: "list, 按最简实现"): events are
        populated in real time *during* the fanout (STARTED at route
        start, terminal when the route settles); this method returns the
        final ordered list so upper layers can monitor progress cheaply.
        """
        result = self.fanout(
            op, executors, payload, adapter_kind=adapter_kind,
            per_executor_timeout=per_executor_timeout, fail_fast=fail_fast,
        )
        return list(result.payload.get("events", []))

    def fanout_stream(self, op: Any, executors: list[str],
                      payload: Mapping[str, Any], *,
                      per_executor_timeout: float | None = None,
                      fail_fast: bool = False, adapter_kind: str = "new") -> Iterator[dict[str, Any]]:
        """Yield fanout events in real time as routes start and settle.

        P3/sub_F streaming surface: yields one event dict
        ``{executor, phase, ts, ok, status}`` per phase transition —
        STARTED as each route begins, then that route's terminal
        DONE / FAILED / TIMEOUT — in real time, so callers (SSE /
        live monitors) can consume progress without waiting for the
        final aggregate.  Built on the *same* ``_RunState`` / lock
        machinery as :meth:`fanout`: the collector pushes each event
        into a queue as it happens, and this generator drains that
        queue until every route has settled.

        Semantics mirror :meth:`fanout` exactly — per-route isolation,
        per-route TIMEOUT on deadline miss, ``fail_fast`` (routes that
        never start emit no STARTED and no terminal of their own),
        degraded adapter statuses, unknown executors — the only
        difference is *when* the events become visible.  This method
        adds no new API of its own to :meth:`fanout` /
        :meth:`dispatch_events` / ``parallel_dispatch_of``.

        Yielded event list == the ``payload['events']`` of a batch
        ``fanout()`` over the same inputs (consistency by construction,
        verified by tests/workflow-assistance/
        test_parallel_dispatch_stream.py).

        Zero executors yields no events at all (same as the batch
        DEGRADED aggregate carrying an empty ``events`` list).

        Real-time: the shared collector (:meth:`_run_routes`) runs on
        a worker thread; every event is pushed into the queue the
        instant it happens, and this generator drains the queue in
        parallel — a consumer sees STARTED while routes are still
        running, not after the batch has finished.  When the collector
        settles every route it signals the end-of-stream sentinel and
        the generator terminates.
        """
        op = _coerce_op(op)
        names = list(dict.fromkeys(list(executors or [])))
        timeout = (per_executor_timeout if per_executor_timeout is not None
                   else self._default_timeout)

        if not names:
            return  # batch aggregate would be DEGRADED with events == []

        state = _RunState(event_stream=queue.Queue())
        stream = state.event_stream
        done_sentinel = object()

        def _collector() -> None:
            try:
                self._run_routes(state, names, op, payload, adapter_kind,
                                 timeout, fail_fast)
            finally:
                stream.put(done_sentinel)

        worker = threading.Thread(
            target=_collector, name="pd-stream-collector", daemon=True)
        worker.start()
        while True:
            item = stream.get()
            if item is done_sentinel:
                break
            yield item
        worker.join()


# ----------------------------------------------------------------------
# P3/sub_F module-level streaming convenience (see fanout_stream)
# ----------------------------------------------------------------------

def parallel_dispatch_stream(federation: Any, op: Any,
                            executors: list[str], payload: Mapping[str, Any],
                            *, max_workers: int = 4,
                            per_executor_timeout: float | None = None,
                            fail_fast: bool = False,
                            adapter_kind: str = "new") -> Iterator[dict[str, Any]]:
    """Module-level convenience that yields the same real-time event
    stream as :meth:`ParallelDispatcher.fanout_stream` for a
    freshly-built dispatcher over ``federation``.

    The yielded event dicts are identical in shape, order and content
    to the batch ``payload['events']`` of :meth:`ParallelDispatcher.fanout`
    for the same inputs — only *visibility timing* differs (real time
    vs. after the batch settles).
    """
    dispatcher = ParallelDispatcher(
        federation, max_workers=max_workers,
        default_timeout=per_executor_timeout,
    )
    return dispatcher.fanout_stream(
        op, executors, payload,
        per_executor_timeout=per_executor_timeout,
        fail_fast=fail_fast, adapter_kind=adapter_kind,
    )


def parallel_dispatch_of(federation: Any, specs: list, *, max_workers: int = 4,
                         fail_fast: bool = False,
                         per_executor_timeout: float | None = None) -> Any:
    """Convenience wrapper: fan out several op/payload specs at once.

    Each spec is either a mapping
    ``{"op", "executors", "payload", optional: "name", "adapter_kind",
    "fail_fast", "per_executor_timeout"}`` or a 3-tuple
    ``(op, executors, payload)``.  All specs run simultaneously on one
    dispatcher; the returned single ``ExecResult`` aggregates every
    spec-level ``ExecResult`` under ``payload["per_spec"]`` with the
    same four-valued batch status.  Zero specs -> DEGRADED + note.
    """
    acp = _acp()
    specs = list(specs or [])
    if not specs:
        return acp.ExecResult(
            acp.Op.CAPABILITIES, "*", ok=False, status="DEGRADED",
            payload={"per_spec": {}, "succeeded": [], "failed": []},
            notes=["no specs supplied to parallel_dispatch_of"],
        )

    def _spec_fields(index: int, spec: Any):
        if isinstance(spec, Mapping):
            return {
                "name": spec.get("name", f"spec-{index}"),
                "op": _coerce_op(spec.get("op", acp.Op.NEW)),
                "executors": list(spec.get("executors") or []),
                "payload": spec.get("payload") or {},
                "adapter_kind": spec.get("adapter_kind", "new"),
                "fail_fast": bool(spec.get("fail_fast", fail_fast)),
                "per_executor_timeout": spec.get(
                    "per_executor_timeout", per_executor_timeout
                ),
            }
        seq = tuple(spec)  # (op, executors, payload)
        return {
            "name": f"spec-{index}",
            "op": _coerce_op(seq[0]),
            "executors": list(seq[1]),
            "payload": seq[2],
            "adapter_kind": "new",
            "fail_fast": fail_fast,
            "per_executor_timeout": per_executor_timeout,
        }

    dispatcher = ParallelDispatcher(
        federation, max_workers=max_workers, default_timeout=per_executor_timeout
    )

    def run_spec(index: int, spec: Any) -> tuple[str, Any]:
        f = _spec_fields(index, spec)
        return f["name"], dispatcher.fanout(
            f["op"], f["executors"], f["payload"],
            per_executor_timeout=f["per_executor_timeout"],
            fail_fast=f["fail_fast"], adapter_kind=f["adapter_kind"],
        )

    results: dict[str, Any] = {}
    if len(specs) == 1:
        name, res = run_spec(0, specs[0])
        results[name] = res
    else:
        with concurrent.futures.ThreadPoolExecutor(
            max_workers=max(1, min(len(specs), max_workers)),
            thread_name_prefix="pd-spec-",
        ) as pool:
            futs = {pool.submit(run_spec, i, s): i
                    for i, s in enumerate(specs)}
            for fut in concurrent.futures.as_completed(futs):
                name, res = fut.result()
                results[name] = res

    statuses = [r.status for r in results.values()]
    if all(s == "OK" for s in statuses):
        status = "OK"
    elif all(s == "FAILED" for s in statuses):
        status = "FAILED"
    elif all(s == "DEGRADED" for s in statuses):
        status = "DEGRADED"
    else:
        status = "PARTIAL"
    # Deterministic batch summary (P1 contract: spec order == input order).
    # ``results`` is populated via ``as_completed`` (L569) so its iteration
    # order is *completion* order, which is nondeterministic across thread
    # scheduling. Deriving the summary from it leaked that completion order
    # into ``succeeded``/``failed``/``notes`` and made the batch flaky (CI:
    # ['s2','s1'] vs ['s1','s2']). Reorder every summary field back to the
    # input spec order so the payload is stable regardless of when each spec
    # happens to finish.
    seen: set = set()
    names_in_order: list = []
    for index, spec in enumerate(specs):
        name = _spec_fields(index, spec)["name"]
        if name not in seen:
            seen.add(name)
            names_in_order.append(name)

    def _ok(name: str) -> bool:
        r = results.get(name)
        return bool(r and r.ok)

    notes = [f"{name}: {results[name].status}"
             for name in names_in_order
             if name in results and not results[name].ok]
    top_op = _spec_fields(0, specs[0])["op"]
    return acp.ExecResult(
        top_op, "*", ok=(status == "OK"), status=status,
        payload={
            "per_spec": {name: results[name].to_dict()
                         for name in names_in_order if name in results},
            "succeeded": [name for name in names_in_order
                          if name in results and _ok(name)],
            "failed": [name for name in names_in_order
                      if name in results and not _ok(name)],
        },
        notes=notes,
    )
