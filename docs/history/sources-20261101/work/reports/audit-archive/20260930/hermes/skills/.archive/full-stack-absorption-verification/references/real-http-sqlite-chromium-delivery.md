# Real HTTP→SQLite→Chromium delivery replay

Use this reference when delivery code exists but the repository may only have service-level tests or mocked browser smoke.

## Boundary matrix

| Boundary | Minimum evidence | Does not inherit coverage |
|---|---|---|
| Service | `dispatch_once()`/projection test with isolated SQLite readback | HTTP route or browser |
| HTTP | Real loopback server, migrated DB, real request/response | `TestClient` alone or mocked browser route |
| SQLite | Same run shows Job/Outbox/Receipt transition | DOM text without DB readback |
| Chromium | Real page action, real network request, same-DB readback | Static HTML or mocked API |
| CI | Tracked script invokes the replay on a fresh runtime | Manual shell transcript only |

## Minimal success replay

1. Capture `git status`, `HEAD`, and tree identity; use a fresh isolated `COGNITIVE_DATA_DIR`.
2. Run the repository migration before starting Core.
3. Start the actual server on loopback and bypass proxies for local requests.
4. Seed through the product UI, preferably a real file-upload control; do not insert a Job/Outbox row directly for the success path.
5. Assert the initial projection in both places:
   - Chromium shows `pending` and `receipt missing`.
   - SQLite shows `workspace_jobs_v1.state='succeeded'`, `workspace_outbox_v1.state='pending'`, and no delivery receipt.
6. Click the semantic delivery action, not a positional button. Capture the POST dispatch request and the subsequent projection refresh.
7. Wait for semantic convergence (`pending=0`, `missing=0`, `delivered/recorded`), not merely the first matching receipt label; existing rows can satisfy a weak locator before refresh completes.
8. Assert SQLite now shows Outbox `delivered` and exactly one matching Delivery Receipt. Assert the page contains no internal job, command, package, event, payload, or lease identifiers.
9. Keep the page and server alive during the transition to prove no-restart readback.
10. Encode the replay in a tracked Playwright script and invoke it from the existing CI browser job. Add a static CI test if the project is vulnerable to silently replacing real calls with `page.route()` mocks.

## Classify outcomes

- **Implemented, manual live pass, gate missing**: code and live boundary work, but the browser/CI product evidence is not yet released.
- **Service pass, HTTP/browser absent**: do not report frontend/backend connected.
- **Mocked browser pass**: useful for fail-closed UI behavior, not delivery coverage.
- **Failure/retry only at service level**: keep the real success slice separate; schedule a later HTTP/Chromium failure→retry→replay task.
- **Tauri process/HTTP pass**: not WebView click evidence; retain a separate desktop row.

## Useful repository search

```bash
git grep -n -E \
  'api/delivery|delivery-dispatch|delivery-retry|Receipt recorded|Outbox pending' \
  HEAD -- 'tests/**' 'integration-tests/**' 'scripts/**'
```

If this returns no tracked test/script hit while `app/` contains the routes, the likely next task is to encode the real browser replay—not to rewrite the router or dispatcher.
