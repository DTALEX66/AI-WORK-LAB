# Live-WAL projection and structured delivery evidence

## Root cause pattern

A live FastAPI/SQLite server can keep `database-wal` and `database-shm` sidecars after an intake transaction. An immutable URI reader (`mode=ro&immutable=1`) must reject that state for offline/external read paths; silently checkpointing or deleting sidecars would weaken the boundary. Internal runtime projections that must observe the active database need a normal SQLite connection with `PRAGMA query_only=ON`, which can read the live WAL safely. Use that mode for Job Center/runtime graph reads and lease-fenced consumers, not for backup/rollback/external immutable projections.

## Tight reproduction

1. Create a fresh project-local database and apply migrations.
2. Start the real Core server.
3. Upload a real fixture through `/workspace/api/intake/upload`.
4. Immediately read `/workspace/api/jobs` while the server/database may still have WAL/SHM sidecars.
5. Assert HTTP 200, a succeeded job, and `delivery_state=pending`.
6. Keep a WAL writer connection open in a regression test and repeat the internal projection read.

The failed implementation used the default immutable Research reader in `workspace_jobs()` and returned a 422 sidecar error. The fixed implementation passes `live_wal=True` only for the internal projection; the immutable reader remains fail-closed.

## Evidence matrix rule

A lifecycle reporter must not derive matrix keys from human-readable step names. Use a structured evidence map, set only after the semantic assertion for that state passes, and copy that map into the final report. Minimum keys:

- `success`: baseline HTTP 200 plus valid schema
- `pending`: delivery summary has a pending outbox
- `failed`: controlled SQL failure fixture is visible through the real API
- `retry`: retry HTTP response is 200 and payload status is `requeued`
- `replay`: post-retry dispatch returns 200 and converges to delivered + recorded receipt
- `delivered`: delivery projection reports delivered and recorded receipt
- `restart_readback`: a second HTTP read equals the first full projection
- `network_failure`: unreachable request returns the explicit connection-failed result

Run both the standalone lifecycle script and the relevant pytest suite. Restore any tracked fixture modified by the standalone script before staging.

## Direct browser script entry

A tracked smoke that imports `tests.*` helpers should support both pytest and direct execution. When `__package__` is empty, insert the repository root (`Path(__file__).resolve().parents[1]`) into `sys.path` before importing sibling helpers. Validate the direct command, not merely pytest collection.
