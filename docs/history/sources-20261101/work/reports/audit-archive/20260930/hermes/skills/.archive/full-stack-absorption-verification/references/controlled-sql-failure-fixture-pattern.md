# Controlled SQL Negative Fixture for Failure-Path Testing

Use this pattern when you need to test retry/requeue/replay endpoints but the happy-path handler always succeeds, making it impossible to reach `failed` state naturally.

## Sequence (proven in M-001 cycle)

```
real HTTP upload → job=succeeded, outbox=pending
real HTTP dispatch   → outbox=delivered, receipt=recorded
  ↓
direct SQL UPDATE    → outbox.state='failed' (controlled fixture)
  ↓
real HTTP delivery   → assert outbox.failed > 0
real HTTP retry      → assert status=requeued
real HTTP delivery   → assert outbox.pending > 0
real HTTP dispatch   → assert outbox=delivered
real HTTP delivery   → assert receipts.recorded == 1
new-connection HTTP  → assert state identical (restart readback)
```

## Rules

1. **Prove the success path first** — no SQL fixture until real HTTP → persistence → readback is green. This proves the contracts, the binding logic, and the projection code all work.
2. **Direct SQL only for the negative fixture** — seed exactly one row into the desired failure state. Never seed via SQL for the success path.
3. **Verify failure projection through the real API** — the retry endpoint is useless if the UI can't display the failure state.
4. **Test idempotency** — calling retry twice should return `idle` on the second call (no duplicate events).
5. **Verify restart readback** — the retry+dispatch cycle must survive a new database connection without state divergence.
6. **Keep the fixture isolated** — use a separate fresh database (under project-local ignored runtime). Never touch the project runtime database.

## Code sketch (Python)

```python
# Step 1: Success path (real HTTP)
assert http("POST", "/workspace/api/intake/upload", file=...).status == 200
assert http("GET", "/workspace/api/delivery").parsed["summary"]["outbox"]["pending"] == 1

# Step 2: Controlled SQL fixture
conn = sqlite3.connect(str(db_path))
conn.execute("BEGIN IMMEDIATE")
conn.execute(
    "UPDATE workspace_outbox_v1 SET state='failed', lease_token=NULL, "
    "lease_expires_at=NULL, updated_at=? WHERE state='delivered'",
    (now_iso,),
)
conn.commit()
conn.close()

# Step 3: Verify failure projection
r = http("GET", "/workspace/api/delivery")
assert r.parsed["summary"]["outbox"]["failed"] > 0

# Step 4: Retry
r = http("POST", "/workspace/api/delivery/retry")
assert r.parsed["status"] == "requeued"

# Step 5: Verify pending reappeared
r = http("GET", "/workspace/api/delivery")
assert r.parsed["summary"]["outbox"]["pending"] > 0

# Step 6: Re-dispatch and verify convergence
r = http("POST", "/workspace/api/delivery/dispatch")
time.sleep(0.5)
r = http("GET", "/workspace/api/delivery")
assert r.parsed["summary"]["outbox"]["delivered"] == 1
assert r.parsed["summary"]["receipts"]["recorded"] == 1

# Step 7: Restart readback
r2 = http("GET", "/workspace/api/delivery")
assert r2.parsed == r.parsed
```

## Pitfalls

- **SQLite WAL file-lock after server kill** — after killing uvicorn, SQLite files stay locked for ~1.5s on Windows. If your fixture runs in the teardown phase, wait or use `missing_ok=True` + PermissionError catch.
- **Shared database between test and server** — the server and your fixture must connect to the **same database file**. Use a project-local `.hermes/task-runtime/<test-name>/data/` path and pass it via `COGNITIVE_DATA_DIR`.
- **Don't fabricate matrix entries** — every state in the matrix must map to a real `record()` call that exercised the endpoint. The `failed` and `retry` rows are real only if you actually forced the state and called the endpoint; hardcoding `True` is not evidence.
