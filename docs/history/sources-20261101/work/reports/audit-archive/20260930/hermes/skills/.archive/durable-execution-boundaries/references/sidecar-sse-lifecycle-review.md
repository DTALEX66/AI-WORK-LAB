# Sidecar lifecycle and SSE review probes

Compact reproduction recipes for read-only review of threaded sidecars.

## Alive-but-failing watcher

1. Start watcher and worker with complete fresh collector health.
2. Establish a nonzero revision, fresh heartbeat/writer watermark, and active SSE connection.
3. Assert transport is LIVE.
4. Make canonical fingerprint/readback fail continuously while leaving the watcher thread alive.
5. Wait until any internal stale/error marker is visible.
6. Read transport again.

Defect signature: internal state is STALE and watcher is alive, but transport remains LIVE. Root cause is usually `cursor_valid = revision > 0 and thread.is_alive()` without a current readback-success signal.

## Restart cursor monotonicity

1. Persist revision `N > 0` in the canonical store.
2. Reconstruct the service and its SSE hub.
3. Reconnect with `Last-Event-ID: N`.
4. Record IDs for resync/snapshot, the next heartbeat, and the next published delta.

Required invariant: IDs never decrease; the new delta is `> N`.

Defect signature: outer snapshot uses `N`, hub heartbeat uses `0`, then first publish advertises `1`. Seed the hub itself from durable revision, not only a sidecar field.

## Ghost stream after shutdown

1. Start the HTTP server and open SSE; keep the response open.
2. Stop and close the server.
3. Query connection state and try to acquire the same runtime singleton lock with a replacement.

Required invariant: old connection count is zero before replacement ownership is available.

Defect signature: serve loop is stopped, old SSE connection remains true, and replacement lock acquisition succeeds. Server shutdown must signal and join/retire active stream handlers before releasing ownership.

## Audit hygiene

- Inspect tracked paths only when foreign untracked files are forbidden.
- Use temp/project-ignored runtime roots; do not add fixtures during a read-only review.
- Run affected tests serially. A grouped run that fails only under concurrent audit probes is evidence to reproduce, not yet a product finding.
- A reportable finding includes exact source lines, deterministic steps, and actual observed output.