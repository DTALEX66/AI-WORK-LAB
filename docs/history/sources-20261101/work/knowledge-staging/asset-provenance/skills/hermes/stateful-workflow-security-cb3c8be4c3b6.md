---
name: stateful-workflow-security
version: 1.0.0
author: "UNKNOWN"
license: UNKNOWN
platforms: [windows, linux, macos]
workflow_software: hermes
archived_at: 2026-08-21
source_path: C:/Users/ALEX/AppData/Local/hermes/skills/software-development/stateful-workflow-security/SKILL.md
---

---
name: stateful-workflow-security
description: Secure stateful schedulers and workflow execution against authorization bypasses, stale leases, and review drift.
version: 1.0.0
author: Hermes Agent
---

# Stateful Workflow Security

## Use when

Use for schedulers, queues, job runners, task graphs, leases, durable workflow
state, or any runtime where a task is claimed and later causes effects.

## Core rule

The durable store is the authorization authority. Payloads, DTOs, callback
arguments, and in-process private objects are not proof of permission.

## Workflow

1. **Map every effectful port.** Trace public adapters, facades, CLI/API paths,
   callbacks, and executor entry points. Do not assume a composition root is
   the only path to effectful execution.
2. **Build adversarial RED tests.** Cover forged dependency/completion fields,
   direct public-facade invocation, stale lease tokens, and lease expiry during
   execution.
3. **Validate against durable state.** Immediately before effects, load the
   task's persisted identity, dependencies, status, ownership/token, and expiry.
   Require payload/proof/persisted fields to agree exactly; query dependency
   terminal state from the same durable run.
4. **Bind terminal transitions too.** Every success, retry, blocked, or archive
   update must include task state, lease token/owner, and unexpired lease in its
   SQL/transaction predicate. If no row updates, fail closed as `lease_lost`.
5. **Protect façade boundaries.** A generic runtime may remain generic, but any
   task marked as workflow-derived must require revalidated scheduler context
   before it is executed. Rebuild and compare the canonical runtime projection
   from durable source data when payload substitution is possible.
6. **Freeze and review.** Stage only intended paths, record `git write-tree`,
   have reviewers audit that exact tree, then re-check the staged tree before
   commit. Run targeted RED/GREEN, full tests, lints, and relevant runtime smoke.

## Long-lived handler / SSE lifecycle hardening

For stateful HTTP surfaces (SSE streams, event hubs, sidecar loops) whose
handlers outlive the server object, four fail-closed rules (validated
2026-08-15, WORK-LAB observer WL3-600/605):

1. **Persist the cursor, seed the restart.** A revision/cursor hub that starts
   at 0 on every boot lets `Last-Event-ID` cursors go BACKWARDS after a
   restart. Keep the last cursor in a tiny KV table
   (`sse_state(key TEXT PRIMARY KEY, value INTEGER)`), write it on every
   publish (`record_revision`, upsert), and seed the hub from it on startup
   (fall back to the old source for pre-migration DBs).
2. **Serve loop must observe server closure.** After `server_close()` the
   store is already shut down, but a serving handler thread keeps running:
   it must check `server._closed` each loop and break (no more heartbeats, no
   refreshing shared timestamps), and the endpoint must reject new
   connections with 503 once closed.
3. **Readback freshness, not thread liveness, gates LIVE.** A watcher thread
   whose canonical readback keeps raising must invalidate its last-ok
   timestamp (`_last_canonical_ok_at = None`) so the verdict cannot stay LIVE
   on liveness alone; keep the mode gate at STALE until a fresh readback.
4. **Capability-level read-only opens skip every write surface.** For a
   strictly-read-only consumer: SQLite URI `mode=ro`, no `mkdir`, no schema
   migration, no `PRAGMA journal_mode=WAL` — any write then fails closed with
   `OperationalError`.

Pitfall: a background loop with a catch-all `except: continue` swallows real
bugs (e.g. a call to a method that was never implemented) and leaves only
contradictory observable state (revision advancing, watermark rolled back).
Instrument the REAL code path with a probe script (monkeypatch the method,
print caller + timestamp, wrap the real implementation to print
`RAISED <Type>: <msg>`) instead of re-deriving the logic.

## Pitfalls

- Verifying only the recommended scheduler path leaves public adapters or
  runtime facades available as bypasses.
- Comparing a proof only to caller-provided dependency IDs preserves forged
  empty-dependency bypasses; use persisted dependency data as the authority.
- Checking lease expiry before runtime but not in the terminal `UPDATE` permits
  stale workers to publish success after expiry.
- Python underscore/private symbols and module-global sentinels are not a
  security boundary against same-process callers.

## Verification checklist

- [ ] Forged payload dependencies cannot replace persisted dependencies.
- [ ] Direct facade execution of workflow-derived tasks requires durable proof.
- [ ] All referenced dependencies are in the same run and terminally complete.
- [ ] Every terminal transition fails closed when lease is expired or lost.
- [ ] Normal scheduler → runtime execution remains green.
- [ ] Review and CI use an exact frozen tree/commit SHA.
