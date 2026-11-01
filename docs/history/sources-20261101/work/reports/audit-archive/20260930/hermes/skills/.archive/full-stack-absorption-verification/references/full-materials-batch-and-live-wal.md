# Full-material batch and live-WAL reference

Use this reference when a real local Markdown/Canvas vault must be tested in one batch and the runtime persists SQLite WAL sidecars.

## Batch invariants

1. Enumerate the source read-only and record extension counts, total candidates, and a deterministic ordered path list before making HTTP calls.
2. Fail closed if the candidate count changes between the inventory pass and the batch runner. Persist path, relative path, size, SHA-256, HTTP status, and response/error for every candidate.
3. Apply hidden/config exclusions to directory components, not the filename component. A legitimate learning file may begin with dots (for example `....md`).
4. Use one writer and the product's real HTTP intake route. Respect the product rate limiter; do not bypass it with parallel writers or forged identity headers.
5. After intake, dispatch and read back Job, Outbox, command receipt, and delivery receipt separately. A successful upload response alone is not closed-loop evidence.

## Windows isolated environment

When using Git-Bash on Windows, Hermes may inject a global `PYTHONPATH`. Run the isolated project command as:

```bash
export UV_CACHE_DIR='D:/All projects/OS configuration/uv-cache'
export UV_PROJECT_ENVIRONMENT='D:/All projects/OS configuration/cognitive-loop-os-ci-venv'
env -u PYTHONPATH uv run --frozen --only-group ci ...
```

Before trusting a failure, print `sys.executable`, `sys.prefix`, and the imported package paths. Do not repair the global Hermes environment for a project test.

## Internal live-WAL rule

Keep immutable sidecar-free readers for offline/external read-only consumers. Internal runtime paths that read after a write must use a query-only live-WAL connection. Audit the complete chain, not only the first Research reader:

```text
Research package load
→ governance migration status/require_applied
→ Research approval/promotion
→ Learning artifact creation/approval
→ practice/mastery and versioning
```

A regression should create WAL/SHM sidecars, invoke the real internal operation, and assert the operation succeeds. Do not force a checkpoint or delete sidecars from a live server to hide the defect.

## JSON Canvas boundary

MarkItDown is not a JSON Canvas parser. For `.canvas`, register an explicit native adapter that:

- parses JSON and validates a `nodes` array;
- projects text nodes and safe labels only;
- never opens file nodes, follows URLs, or executes embedded content;
- rejects malformed or unsupported node types deterministically.

Keep Canvas engine identity distinct (for example `json-canvas`) so the batch report proves the actual path used.
