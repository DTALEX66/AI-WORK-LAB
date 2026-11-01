"""Durable local worker loop for the Workflow Assistance control plane.

Single-instance, resumable background worker. Uses the canonical SQLite WAL
store for leases, checkpoints, heartbeats and fencing. Drives the task loop:

    acquire -> heartbeat -> checkpoint -> intent -> side effect
    -> readback -> reconcile -> release / defer / retry / block

and runs bounded collectors (task / git-ci / usage / source-quality) that only
write canonical facts. No model dependency, no cloud database; degraded to
UNAVAILABLE/OFFLINE/STALE when a collector's source is missing.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import sys
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

# CLI may run this file directly (python durable_worker.py ...); resolve the
# shared module roots (canonical_store / sidecar_lock live under
# packages/client-neutral-core/scripts after the directory convergence).
_ROOT = Path(__file__).resolve().parents[2]
_CNC = _ROOT / "packages" / "client-neutral-core" / "scripts"
if str(_CNC) not in sys.path:
    sys.path.insert(0, str(_CNC))

from canonical_store import CanonicalStore, RETAINABLE_TABLES
from project_temp import require_runtime_root
from sidecar_lock import SingleInstanceLock

DEFAULT_TICK_SECONDS = 30.0
MAX_RETRIES_PER_FINGERPRINT = 3
WINDOW_SECONDS = 3600.0


class CollectorError(RuntimeError):
    pass


@dataclass
class CollectorResult:
    kind: str
    ok: bool
    records: list[dict[str, Any]] = field(default_factory=list)
    error: str | None = None
    degraded: str | None = None
    # Rows the collector read but could not turn into a fact, counted by named reason. Without this, an
    # empty `records` list from a source that plainly had lines is indistinguishable from "source empty",
    # which is the silent-filtering failure the old batch-abort was accidentally protecting against.
    refusals: dict[str, int] = field(default_factory=dict)
    refusal_samples: dict[str, str] = field(default_factory=dict)


CollectorFn = Callable[[CanonicalStore, str], CollectorResult]


def fingerprint(cause: str) -> str:
    import hashlib

    return hashlib.sha256(cause.encode("utf-8", errors="replace")).hexdigest()


def _row_location(record: dict[str, Any]) -> str:
    """Where a refused row came from, down to the line when the collector knew it.

    A file name alone makes the reader open the file and hunt; the line number is the difference between a
    traceable refusal and a rumour. `source_line` is a diagnostic key the store never persists.
    """
    where = str(record.get("source_ref") or record.get("row_id")
                or record.get("sample_id") or "<unnamed row>")
    line = record.get("source_line")
    return f"{where}:{line}" if line is not None else where


def _first_reason_text(counts: dict[str, int], samples: dict[str, str], *, limit: int = 4) -> str | None:
    """Name EVERY refusal cause this tick carried, with its count and the first place it happened.

    An earlier draft kept only the most frequent cause, which on a tick with two causes (a truncated line and
    a credential-bearing row, the exact mixed file the canary fixture models) counted both and named one — the
    reader could not tell that a second cause existed. A cap is kept because one pathological source could
    otherwise emit a hundred distinct messages, and the truncation is stated rather than hidden.
    """
    if not counts:
        return None
    total = sum(counts.values())
    ordered = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    shown = [f"{reason} ×{count} @ {samples.get(reason) or '<no location reported>'}"
             for reason, count in ordered[:limit]]
    tail = f"；另有 {len(ordered) - limit} 类原因未列出" if len(ordered) > limit else ""
    return (f"{total} row(s) refused: " + "；".join(shown) + tail)[:600]


class DurableWorker:
    """Runs one bounded worker tick; safe to call from a thread or process."""

    def __init__(
        self,
        store: CanonicalStore,
        project_id: str = "work-lab",
        tick_seconds: float = DEFAULT_TICK_SECONDS,
        lease_ttl_seconds: int = 300,
        collectors: list[CollectorFn] | None = None,
        task_handler: Callable[[CanonicalStore, dict[str, Any]], None] | None = None,
    ) -> None:
        self.store = store
        self.project_id = project_id
        self.tick_seconds = tick_seconds
        self.lease_ttl_seconds = lease_ttl_seconds
        self.holder = f"worker-{uuid.uuid4().hex[:12]}"
        self.collectors = collectors or []
        self.task_handler = task_handler
        self._retries: dict[str, int] = {}
        self._stopped = False

    def stop(self) -> None:
        self._stopped = True

    def run_once(self) -> dict[str, Any]:
        """Execute one tick: reclaim zombies, run collectors, drive one task."""
        results: dict[str, Any] = {"tick": time.time(), "holder": self.holder}

        reclaimed = self.store.claim_expired_tasks(self.holder, self.lease_ttl_seconds)
        results["zombie_reclaimed"] = reclaimed

        collector_outcomes: list[dict[str, Any]] = []
        for collector in self.collectors:
            name = str(getattr(collector, "collector_name", getattr(collector, "__name__", "unknown")))
            try:
                outcome = collector(self.store, self.project_id)
                stored, ingest_refusals, ingest_samples = self._write_records(outcome.kind, outcome.records)
                refusal_counts: dict[str, int] = dict(outcome.refusals)
                for reason, count in ingest_refusals.items():
                    refusal_counts[reason] = refusal_counts.get(reason, 0) + count
                refused_total = sum(refusal_counts.values())
                # One bad row no longer aborts the tick. What must not be lost is the fact that it was
                # refused: a collector whose every row was refused did not deliver its source, so that is
                # a failed run for health and breaker purposes, not a success with a footnote.
                ok = outcome.ok and not (stored == 0 and bool(outcome.records))
                self._record_collector_health(
                    name, ok=ok, refused_total=refused_total, delivered_total=stored,
                    last_refusal_reason=_first_reason_text(refusal_counts, {**outcome.refusal_samples,
                                                                            **ingest_samples}),
                )
                collector_outcomes.append(
                    {
                        "kind": outcome.kind,
                        "ok": ok,
                        "records": len(outcome.records),
                        "stored": stored,
                        "refused": refused_total,
                        "refusalReasons": refusal_counts,
                        "refusalSamples": {**outcome.refusal_samples, **ingest_samples},
                        "degraded": outcome.degraded,
                    }
                )
            except Exception as exc:  # noqa: BLE001 - one source must not kill the durable loop
                self._record_collector_health(name, ok=False)
                collector_outcomes.append({"kind": name, "ok": False, "error": str(exc)[:500]})
        results["collectors"] = collector_outcomes

        if self.task_handler is not None:
            results["task"] = self._drive_task()
        return results

    def _write_records(self, kind: str, records: list[dict[str, Any]]
                       ) -> tuple[int, dict[str, int], dict[str, str]]:
        """Write row by row, so one refused row cannot take the rest of the batch down with it.

        Returns (stored, refusals_by_reason, first_sample_per_reason). The reason key is the exception
        class plus the leading clause of its message, because "ValueError" alone would not distinguish a
        sensitive-name refusal from a shape refusal, and the count is only useful if it is attributable.
        """
        stored = 0
        refusals: dict[str, int] = {}
        samples: dict[str, str] = {}
        for record in records:
            try:
                self._write_record(kind, record)
                stored += 1
            except Exception as exc:  # noqa: BLE001 - a refused row is data, not a crashed tick
                reason = f"{type(exc).__name__}: {str(exc)[:120]}"
                refusals[reason] = refusals.get(reason, 0) + 1
                samples.setdefault(reason, _row_location(record))
        return stored, refusals, samples

    def _write_record(self, kind: str, record: dict[str, Any]) -> None:
        if kind == "telemetry":
            self.store.append_telemetry(record)
        elif kind == "usage":
            self.store.record_usage_sample(record)
        elif kind == "ci":
            self.store.record_ci_run(record)
        elif kind == "quality":
            self.store.append_quality(record)

    def _record_collector_health(self, name: str, *, ok: bool, refused_total: int | None = None,
                                 delivered_total: int | None = None,
                                 last_refusal_reason: str | None = None) -> None:
        previous = {row["name"]: row for row in self.store.list_collector_health()}.get(name, {})
        now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        failures = 0 if ok else int(previous.get("consecutive_failures") or 0) + 1
        record: dict[str, Any] = {
            "name": name,
            "totalRuns": int(previous.get("total_runs") or 0) + 1,
            "lastRunAt": now,
            "lastSuccessAt": now if ok else previous.get("last_success_at"),
            "consecutiveFailures": failures,
            "circuitOpenUntil": previous.get("circuit_open_until"),
            "droppedCount": int(previous.get("dropped_count") or 0),
        }
        # Refusals ACCUMULATE rather than describe one tick: a reader who asks "how many rows has this
        # source never managed to turn into a fact" wants the running total, and a single-tick number
        # would be overwritten by the next clean tick and hide the debt.
        if refused_total is not None:
            record["refusedRows"] = int(previous.get("refused_rows") or 0) + int(refused_total)
        if delivered_total is not None:
            record["deliveredRows"] = int(previous.get("delivered_rows") or 0) + int(delivered_total)
        if last_refusal_reason is not None:
            record["lastRefusalReason"] = last_refusal_reason
        self.store.upsert_collector_health(record)

    def _drive_task(self) -> dict[str, Any]:
        """Pick one ready task, lease it transactionally, run, reconcile."""
        ready = [task for task in self.store.list_tasks() if task["status"] in {"PENDING", "RETRYING", "RUNNING", "FAILED_RECOVERABLE"}]
        if not ready:
            return {"status": "idle", "holder": self.holder}
        task = ready[0]
        task_id = task["task_id"]
        acquired = self.store.acquire_lease(task_id, self.holder, self.lease_ttl_seconds)
        if not acquired:
            return {"status": "lease_busy", "task": task_id}
        try:
            # Heartbeat before side effect so a slow handler keeps the lease.
            self.store.heartbeat(task_id, self.holder, self.lease_ttl_seconds)
            checkpoint = task.get("checkpoint") or {}
            checkpoint["last_attempt_holder"] = self.holder
            self.store.upsert_task(
                {
                    "task_id": task_id,
                    "project_id": task.get("project_id", self.project_id),
                    "status": "RUNNING",
                    "checkpoint": checkpoint,
                    "lease_holder": self.holder,
                }
            )
            self.task_handler(self.store, task)
            self.store.upsert_task(
                {
                    "task_id": task_id,
                    "project_id": task.get("project_id", self.project_id),
                    "status": "COMPLETED_LOCAL",
                    "checkpoint": {**checkpoint, "completed_by": self.holder},
                }
            )
            self._retries.pop(fingerprint(task_id), None)
            return {"status": "completed", "task": task_id}
        except Exception as exc:  # noqa: BLE001 - worker must never die
            cause = f"{task_id}:{type(exc).__name__}:{exc}"
            fp = fingerprint(cause)
            attempts = self._retries.get(fp, 0) + 1
            self._retries[fp] = attempts
            new_status = "FAILED_RECOVERABLE" if attempts <= MAX_RETRIES_PER_FINGERPRINT else "BLOCKED_POLICY"
            self.store.upsert_task(
                {
                    "task_id": task_id,
                    "project_id": task.get("project_id", self.project_id),
                    "status": new_status,
                    "checkpoint": {
                        **checkpoint,
                        "last_error": str(exc)[:500],
                        "error_fingerprint": fp,
                        "attempts": attempts,
                    },
                }
            )
            return {"status": new_status, "task": task_id, "attempts": attempts}
        finally:
            self.store.release_lease(task_id, self.holder)

    def run_forever(self) -> None:
        while not self._stopped:
            try:
                self.run_once()
                self._record_collector_health("worker_loop", ok=True)
            except Exception:  # noqa: BLE001 - supervisor loop must recover on the next tick
                try:
                    self._record_collector_health("worker_loop", ok=False)
                except Exception:
                    pass
            deadline = time.time() + self.tick_seconds
            while time.time() < deadline and not self._stopped:
                time.sleep(0.25)


class WorkerSupervisor:
    """Owns the single-instance lock and the worker; runs one supervisor."""

    def __init__(self, runtime_root: Path, worker: DurableWorker) -> None:
        self.runtime_root = runtime_root.resolve()
        self.worker = worker
        self._lock = SingleInstanceLock(self.runtime_root / "worker.lock")

    def start(self) -> None:
        self._lock.acquire()

    def stop(self) -> None:
        self._lock.release()


def make_worker(
    store: CanonicalStore,
    *,
    project_id: str = "work-lab",
    tick_seconds: float = DEFAULT_TICK_SECONDS,
    collectors: list[CollectorFn] | None = None,
    task_handler: Callable[[CanonicalStore, dict[str, Any]], None] | None = None,
) -> DurableWorker:
    return DurableWorker(
        store,
        project_id=project_id,
        tick_seconds=tick_seconds,
        collectors=collectors,
        task_handler=task_handler,
    )


def parse_retention(args: Any) -> dict[str, int] | None:
    """`--retention-rows table=N[,table=N]` -> {table: N}, or None when the operator granted nothing.

    Refusing a non-retained table *here* is the point: a ceiling that silently skipped `schema_migrations`
    would leave the operator believing the disk was bounded while the version record stayed whole and the
    ledger kept growing. The store refuses the same names, but a bad flag should fail at the CLI.
    """
    raw = getattr(args, "retention_rows", None)
    if not raw:
        return None
    limits: dict[str, int] = {}
    for chunk in str(raw).split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        table, _, value = chunk.partition("=")
        if table not in RETAINABLE_TABLES:
            raise ValueError(f"RETENTION_TABLE_NOT_PERMITTED {table}; retainable set is "
                             f"{sorted(RETAINABLE_TABLES)}")
        try:
            ceiling = int(value)
        except ValueError as exc:
            raise ValueError(f"RETENTION_CEILING_INVALID {chunk!r} is not table=rows") from exc
        if ceiling < 1:
            raise ValueError(f"RETENTION_CEILING_INVALID {table}={ceiling} would empty a table")
        limits[table] = ceiling
    if not limits:
        raise ValueError("RETENTION_CEILING_INVALID --retention-rows carried no table=rows pair")
    return limits


def apply_retention(store: CanonicalStore, limits: dict[str, int] | None) -> dict[str, Any] | None:
    if not limits:
        return None
    return store.enforce_retention(limits, allow_prune=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the durable Workflow Assistance worker")
    parser.add_argument("--runtime-root", type=Path, required=True)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--project-id", default="work-lab")
    parser.add_argument("--tick", type=float, default=DEFAULT_TICK_SECONDS)
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--retention-rows", default=None,
                        help="cap append-only tables, e.g. telemetry_events=200000,usage_samples=50000; "
                             "applied at startup and after a --once tick (a daemon tick has no post-hook "
                             "to run it from)")
    args = parser.parse_args()
    limits = parse_retention(args)
    # The store holds leases, checkpoints and collected facts: a root outside the repository is invisible
    # to the boundary sweep and outlives the checkout, so the declared runtime root is enforced here.
    runtime_root = require_runtime_root(args.runtime_root, "workflow-assistance-worker")
    project_root = args.project_root.resolve()
    store = CanonicalStore(runtime_root / "canonical.sqlite")
    store.register_project(args.project_id, str(project_root), display_name=project_root.name)
    retention_report = apply_retention(store, limits)
    from collectors import build_standard_collectors

    worker = make_worker(
        store,
        project_id=args.project_id,
        tick_seconds=args.tick,
        collectors=build_standard_collectors(project_root),
    )
    supervisor = WorkerSupervisor(runtime_root, worker)
    supervisor.start()
    try:
        if args.once:
            payload = worker.run_once()
            after_tick = apply_retention(store, limits)
            if limits:
                payload["retention"] = {"atStartup": retention_report, "afterTick": after_tick}
            print(json.dumps(payload, ensure_ascii=False, default=str))
        else:
            print(f"WORKFLOW_WORKER_READY holder={worker.holder} tick={args.tick} "
                  f"retention={limits or 'UNSET'}")
            worker.run_forever()
    finally:
        worker.stop()
        supervisor.stop()
        store.close()
