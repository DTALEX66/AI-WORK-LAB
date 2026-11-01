# Full-stack absorption verification reference

Use this as a compact execution record. Keep the actual report in the target project's ignored `.hermes/task-artifacts/` directory, not in the global skill library.

## Evidence table

| Slice | Required evidence | Do not claim from |
|---|---|---|
| Identity | branch, HEAD, write-tree, remote SHA, exact-SHA CI result | remembered SHA or stale workflow |
| Pack inspection | ZIP inventory, manifest, license/risk docs, script classification | filename alone |
| Local gates | separate command and exit/output per gate | one opaque chained exit code |
| Backend | isolated migration, Core process, real HTTP status/body-shape/redaction checks | browser mocks or unit tests |
| Frontend | real Chromium/Playwright route and interaction evidence | HTML fetch alone |
| Desktop | current-tree `.exe`, Tauri/WebView2/Core process tree, loopback readback, shutdown cleanup | old portable EXE or Rust tests alone |
| Portability | actual DB and WebView/runtime paths | project-local DB alone |

## Windows Git-Bash path pattern

For a native Windows child process, use an explicit native path or convert it before export:

```bash
export COGNITIVE_DATA_DIR='D:/path/to/project/.hermes/task-runtime/api-smoke'
# or: export COGNITIVE_DATA_DIR="$(cygpath -w "$PROJECT_ROOT/.hermes/task-runtime/api-smoke")"
```

Do not assume a Git-Bash `$PWD` export will remain a valid native Windows path. Verify the directory exists from the child interpreter before migration/startup.

For local loopback checks with a proxy configured:

```bash
curl --noproxy '*' -sS http://127.0.0.1:<port>/health
```

## Runtime sequence

1. Create a distinct project-local data root for each smoke class.
2. Run the real migration and capture its exit status.
3. Start Core with an explicit loopback host/port.
4. Poll `/version`, then read `/health`, `/workspace`, and relevant read-only APIs.
5. Parse only status/shape/redaction in the report; never print secrets, tokens, payloads, or internal IDs.
6. Stop the tracked process and verify descendants/listeners are gone.

## Browser binary cache

Generated browser test data and screenshots remain project-local. If a reusable Chromium installation is intentionally maintained under a validated external toolchain root, set `PLAYWRIGHT_BROWSERS_PATH` explicitly for that run instead of copying the cache into the project. This is a dependency-location choice, not permission to put test artifacts or runtime databases outside the project.

## Tauri evidence

A current-tree Tauri check should establish all of:

- actual `.exe` process is alive and responsive;
- WebView2 is a child of the Tauri process;
- supervised Core child is alive;
- a Core descendant owns a loopback listening port;
- `/version`, `/health`, and Workspace are readable;
- Workspace output is redacted;
- actual SQLite/WebView data roots are recorded;
- the process tree is reaped after the check.

If `computer_use` capture is unavailable, process hierarchy, window title/responding state, WebView2 child, loopback readback, and clean shutdown are still useful evidence, but report that a screenshot was not captured rather than claiming visual acceptance.

## Sprint 0 boundary

Sprint 0 is a contract/isolation deliverable. It should not install Docling, OCR-VL, embedding models, LanceDB, Ragas, Promptfoo, TinyCortex, or GPL projects. Add interfaces, empty providers, sanitized fixtures, disabled flags, license/provenance metadata, and an SBOM for what is actually enabled. Then prove that an optional provider can be absent while the core imports, migrates, starts, and passes its minimal tests.
