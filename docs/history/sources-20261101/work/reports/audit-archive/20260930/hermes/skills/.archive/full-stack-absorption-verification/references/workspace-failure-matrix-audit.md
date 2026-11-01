# Workspace Failure-Matrix Audit Reference

Use this reference when a repository claims a local Workspace closed loop involving HTTP, SQLite, Chromium, Tauri, Outbox/Receipt, retry/replay, fail-closed reads, and public redaction.

## Evidence classification

Keep these rows separate:

| Boundary | What counts as evidence | What does not inherit coverage |
|---|---|---|
| Service | Direct service/dispatcher/consumer test with SQLite readback | HTTP route, browser, or desktop UI |
| HTTP | Real server, real migrated DB, real request/response, DB readback | TestClient-only service mocks or browser route mocks |
| Chromium | Real Playwright page action against the real HTTP server and same DB | Static HTML, mocked API, lifecycle seed unrelated to delivery |
| Tauri Core | Current installed/current-tree executable, supervised child, loopback HTTP and shutdown | Chromium pass or Rust unit test |
| Tauri WebView | Actual WebView click/action and page readback | Core readiness probe or NSIS install smoke |

## Fast repository audit commands

Run from the frozen Git root:

```bash
git status --short --branch
git rev-parse HEAD
git write-tree
git rev-parse HEAD^{tree}

git grep -n -E '/workspace/api/delivery|delivery/(dispatch|retry)' \
  -- 'tests/**' 'integration-tests/**' 'scripts/**'

git grep -n -E 'workspace_delivery\(|dispatch_once\(|retry_failed_delivery\(' \
  -- 'tests/**' 'integration-tests/**' 'app/**'

git grep -n -E 'chromium|playwright|WebView|workspace/api/status|workspace/api/delivery' \
  -- 'scripts/**' 'desktop/**' '.github/workflows/**'
```

Interpret the result by boundary. Direct `workspace_delivery()` calls prove projection logic only. Absence of `/workspace/api/delivery` in a browser script is a concrete product-coverage gap, not proof that the endpoint is broken.

## Minimum real delivery replay

Use an isolated data root and real migration:

```text
real upload/intake
→ HTTP response has no internal IDs
→ SQLite: Job succeeded, Outbox pending, Command Receipt present
→ browser runtime page shows pending/missing
→ click dispatch
→ SQLite: Delivery Receipt recorded, Outbox delivered
→ same page refresh/no process restart shows delivered/recorded
```

For failure/retry:

```text
controlled failed event in isolated DB
→ public failed projection
→ POST retry
→ public pending projection
→ real dispatch
→ public delivered/recorded projection
```

Do not add a production-only failure switch merely for the browser test. Seed a failed row in the isolated fixture or inject the handler only in service-level tests; keep the browser row HTTP-real.

## Projection fail-closed checklist

A public delivery projection should reject before returning aggregate data when any of these occur:

- missing Job, Outbox, Command Receipt, or required Delivery Receipt;
- duplicate or orphan binding;
- Job/Outbox payload mismatch;
- wrong event type or canonical fingerprint;
- malformed JSON;
- invalid state combination;
- stale or conflicting receipt proof;
- an unexpected public DTO field that could carry IDs, payloads, tokens, or correlation IDs.

Mirror the existing strict Job readback tamper matrix when adding Delivery tests. Assert both HTTP status and unchanged SQLite state.

## Crash/replay cases

The highest-value asynchronous boundary is:

```text
Delivery Receipt commit succeeds
→ Outbox finalization does not commit
→ process restarts
→ replay same event
```

Expected behavior:

- matching receipt is reused exactly once;
- Outbox can converge to delivered;
- conflicting receipt fails closed;
- stale lease token cannot finalize a newer lease;
- lease expiry during handler execution cannot be converted into a false delivered state.

Inject a clock or short lease duration for expiry tests. Never rely on a 30-second sleep in a regression suite.

## Truth-drift check

Compare these independently:

```text
release manifest capability
README/status/handoff prose
UI capability copy and buttons
route/service implementation
current tests and CI commands
```

A manifest saying `outbox_dispatcher=available` while README/UI says “dispatcher not implemented” is a release-truth gap. Split on-demand dispatcher, background worker, SSE, and interactive Job Center rather than collapsing them into one capability.

## Recommended next-cycle task order

1. Real HTTP + Chromium delivery E2E.
2. Strict server-side Delivery/Receipt projection and HTTP tamper matrix.
3. Retry binding validation and crash-window replay tests.
4. Installed Tauri Core HTTP delivery smoke.
5. Separate Tauri WebView click evidence.
6. Manifest/UI/docs truth reconciliation after tests are green.
