# Source-bound delivery verification pattern

Use this reference when a local-first workspace has multiple real sources and a durable Job/Outbox/Receipt chain.

## Replay order

1. Create a fresh project-local data root and run migration before starting the real API.
2. Exercise each source type through its actual frontend control (for example web URL, GitHub URL, local file); do not seed only through service functions.
3. Read the review queue and approve by a semantic source value. After each approval, assert the source leaves the queue and appears in the next projection.
4. Start learning, record repeated practice, and approve runtime candidates through the UI. Read back each aggregate after the action.
5. In the Runtime page, assert the initial `Job succeeded + Outbox pending + Receipt missing` projection. Click the real dispatch action once per pending event; assert `Outbox delivered + Receipt recorded` after each refresh.
6. Exercise an invalid source or retry-with-no-failed-event path and assert the response is rejected or idle without changing the database.
7. Serialize the rendered page body and reject internal persistence identities, raw payloads, tokens, and correlation fields.

## Safe projection shape

Use human-readable activity/source/title fields and aggregate state only. A useful delivery item contains `activity`, `job_state`, `job_attempts`, `outbox_state`, `outbox_attempts`, and `receipt_state`. It must not contain `job_id`, `command_id`, `package_id`, `event_id`, `aggregate_id`, `payload_json`, or lease data.

## Desktop row

Browser evidence does not satisfy the desktop row. For the current Tauri executable, independently verify the executable, supervised Core child, actual loopback listener, `/version`, `/health`, Workspace HTML, the delivery projection, and the dispatch action. If the executable exists but no Core port appears, record the exact process/port diagnosis and keep the desktop row blocked; do not convert a browser pass into a desktop pass.

## Evidence template

```text
case/source | frontend action | HTTP endpoint | persisted transition | readback | failure/retry | browser | Tauri
```

Each row must be backed by current-run output, not a historical test count.
