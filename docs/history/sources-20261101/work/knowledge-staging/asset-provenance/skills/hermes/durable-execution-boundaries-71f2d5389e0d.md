---
name: durable-execution-boundaries
version: 1.0.0
author: "UNKNOWN"
license: UNKNOWN
platforms: [windows, linux, macos]
workflow_software: hermes
archived_at: 2026-08-21
source_path: C:/Users/ALEX/AppData/Local/hermes/skills/software-development/durable-execution-boundaries/SKILL.md
---

---
name: durable-execution-boundaries
description: "Design, debug, test, and release scheduler/worker authorization boundaries using durable claims, leases, receipts, and execution-time revalidation."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [scheduler, worker, queue, authorization, leases, sqlite, concurrency, testing]
    related_skills: [systematic-debugging, test-driven-development, agent-workflow-fortress]
---

# Durable Execution Boundaries

## Purpose

Use this skill when a scheduler, queue worker, job runner, or runtime adapter uses a proof, receipt, claim, dependency list, capability, or token to decide whether an action may execute.

The governing rule is:

> Authorization for a side effect must be verified from current durable state at the execution seam, not inferred from caller-controlled payload or an in-memory object alone.

## Trigger conditions

Load this skill for work involving:

- task dependencies and “all prerequisites complete” checks;
- SQLite/Postgres/Redis job claims, leases, heartbeats, attempts, or receipts;
- duplicate execution, stale/replayed worker messages, or crash recovery;
- a runtime adapter that receives scheduler-generated task data;
- queue authorization represented by Python objects, JSON, headers, or message metadata;
- review findings that say a capability/proof can be forged or replayed.

## Threat model and boundary

Treat these as untrusted until revalidated:

- task payload fields, including `dependencies`, `status`, and completed IDs;
- caller-supplied capability/proof instances;
- module-private names or sentinel tokens in the same process;
- stale task snapshots from before a requeue/reclaim;
- a proof for one task/run/attempt replayed against another.

Private Python names are encapsulation, not an authorization boundary. A shape check, `isinstance`, or private singleton check can improve API hygiene but cannot substitute for durable state.

## Required durable proof contract

At the side-effecting execution seam, fail closed unless all required facts are read from current durable state and agree:

1. **Identity** — proof task ID and run/queue ID equal the task being executed.
2. **Dependency set** — proof dependencies equal the durable task dependency set.
3. **Task state** — durable task is in the expected claimed/running state.
4. **Attempt ownership** — proof, task snapshot, and durable row contain the same nonempty current lease/attempt token.
5. **Freshness** — lease/attempt is unexpired and has not been superseded by requeue/reclaim.
6. **Dependency state** — each dependency exists in the same run and is durably terminal-success (`done` or project equivalent).
7. **Atomic issuance** — issue the proof only after the atomic claim transaction has written and read back the unique lease/attempt token.

A requeue or reclaim must change the durable token so all old proofs become invalid.

## TDD workflow

Use one vertical RED→GREEN slice at a time.

### 1. Raw payload bypass

Create a failing test where a caller provides a complete-looking dependency list directly to the runtime adapter. It must fail closed.

### 2. Constructed capability bypass

Create a failing test that directly constructs the capability/proof, including importing supposedly private module symbols if applicable. It must still fail unless current durable state authorizes execution.

### 3. Lease replay bypass

Create a failing test against a real currently-running task—especially a zero-dependency task—with a forged or stale lease/attempt token. It must fail closed.

### 4. Normal path

Create or retain an end-to-end scheduler → claim → runtime execution test. It must pass with the genuine current lease.

Only after each RED test fails for the expected missing behavior should production code be changed.

## Implementation pattern

1. Determine dependency readiness while selecting an eligible pending task.
2. Atomically claim it: set running state, owner, unique lease/attempt token, expiry, and attempt receipt.
3. Read back the claimed durable row.
4. Construct the in-memory proof from the read-back run/task/dependency set and current lease token.
5. At runtime execution, query durable state again before mapping to or invoking the side-effecting adapter.
6. Reject any mismatch with a clear fail-closed error; do not silently downgrade to an empty dependency set or retry with a caller value.
7. On heartbeat, expiry, recovery, requeue, or terminal completion, require the exact token **and a currently unexpired lease** in every mutation. A terminal `UPDATE` that checks only `status` + token permits a worker whose lease expired during execution to record `done`.
   - Audit generic task upserts carefully: an `ON CONFLICT ... lease_expires_at=excluded.lease_expires_at, fencing_token=excluded.fencing_token` update will erase a live lease when a status-only caller omits those fields. Use narrowly scoped state-transition statements, or preserve lease columns unless the exact fenced transition owns them.
   - Reclaim on `lease_expires_at < database_now`, not `database_now - ttl`; subtracting the TTL delays recovery by a second full lease period.
   - Retry/block budgets advertised as durable must be restored from durable attempt/checkpoint rows. A process-local dictionary that also writes an `attempts` field but never reloads it resets policy after every restart.
8. Inventory all public effectful paths. A pure-looking projection/DTO adapter that accepts caller-supplied satisfied dependencies can become an authorization bypass if its output is accepted by a generic runtime facade. Keep such adapters non-effectful, or make the effectful seam require the durable authorization again.
9. When a generic facade must accept workflow-specific task packs, give those packs a recognizable workflow contract marker. At the facade, require the original ledger task and durable proof, revalidate them, rebuild the expected runtime projection from durable state, and reject unless the supplied pack exactly matches it. This prevents callers from retaining a valid task ID but replacing its tool, payload, or constraints.
10. For an outbox, distinguish a tested dispatcher primitive from a completed production consumer. A handler that only acknowledges an event, or a no-op handler used in tests, must never be wired as the production default and then mark a business event delivered. Before enabling automatic delivery, define the bounded effect contract, its idempotency key, durable success criterion, retry/failure semantics, and any external-write authorization. Require the handler to receive the durable event identity **and the current lease token** and produce an event-bound durable receipt/proof; a latest-worker checkpoint is not a substitute for one receipt per event. At receipt insertion, atomically re-read and require exact event ID, canonical event type/payload, `leased` state, matching token, and unexpired lease. Checking only `state='leased'` lets a stale worker write a receipt after the event has been reclaimed under a new token; a later worker can then incorrectly deliver based on that stale receipt. Include a replay test that lets lease A expire, claims lease B, then proves A cannot insert a receipt or contribute to `delivered`. If that receipt needs new SQLite schema, implement it as a compatibility-preserving incremental migration: retain and validate the recorded prior schema, append a new migration version/name and rollback provenance, and test both fresh creation and upgrade of an already-recorded database. Until then, expose the lease-fenced dispatcher only as a library/test seam and keep the product UI truthful (for example, a read-only job projection rather than an interactive asynchronous job center).

## Debugging checklist

- Trace task payload, claim row, attempt/receipt row, proof object, and adapter invocation.
- Check the exact time at which the proof is issued. Pending eligibility is too early.
- Test zero dependencies: an empty set can accidentally make shallow checks pass.
- Test a token from a prior attempt after requeue/reclaim.
- Verify that expiry is evaluated at execution time, not only at claim time.
- Confirm cross-run dependency lookup is impossible.
- Do not accept a synthetic local object test as proof that the real database seam is safe; use an actual durable row for replay tests.

## Runtime liveness, stream cursor, and shutdown negative controls

For sidecars and SQLite-backed watchers/workers, treat liveness as a durable evidence boundary, not merely a thread/process check:

1. Test both **dead watcher** and **alive-but-failing watcher** states. After establishing every LIVE input, force canonical readback to fail while the watcher thread remains alive; LIVE must drop immediately rather than waiting for a watermark timeout. A `STALE` flag does nothing if the authoritative gate never consumes it.
2. Bind persisted revision, in-memory SSE hub sequence, snapshot event ID, heartbeat ID, and post-restart publish ID into one monotonic contract. Persist revision `N`, restart, reconnect with `Last-Event-ID: N`, then require snapshot/resync and heartbeat IDs to remain `>= N` and the next publish to be `> N`. Seeding only an outer sidecar field while the hub restarts at zero creates `snapshot N -> heartbeat 0 -> publish 1` rollback.
3. Exercise open-stream shutdown: hold an SSE response open, close the server, verify handler/connection count reaches zero and no heartbeat can still be emitted, then attempt replacement lock acquisition. Releasing the singleton lock while a ghost SSE handler survives permits stale and replacement services to coexist.
4. With `check_same_thread=False`, verify every read, write, migration, and close path uses the same connection lock. Also decide whether a logical snapshot assembled from separately locked SELECTs requires one read transaction for consistency.
5. For read-only audits, use temporary or project-ignored runtime storage and deterministic executable probes. Report only actionable `file:line` findings plus the reproduction sequence and observed result when the user requests a narrow finding-only contract. Run changed tests serially before promoting a load-sensitive grouped-run failure to a product defect.

## Release gate

1. Run focused negative controls and the normal scheduler-to-runtime path.
2. Run the affected engine/runtime suite and full project gate.
3. Stage explicit intended files only; verify staged whitespace and record `git write-tree`.
4. Give an independent reviewer the tree hash and require attacks against the frozen candidate, including constructed-proof and stale-lease cases.
5. A review blocker invalidates the candidate: add a RED regression test, fix the root cause, restage, regenerate the tree hash, and re-review.
6. Commit only the reviewed tree. Push and judge CI against the resulting exact commit SHA.

## Reference

See [the durable-authorization reference](references/durable-authorization-execution.md) for a compact audit recipe and common failure sequence.

See [the sidecar/SSE lifecycle review probes](references/sidecar-sse-lifecycle-review.md) for deterministic alive-but-failing watcher, restart-cursor monotonicity, and ghost-stream shutdown reproductions.
