# Attachment Pack Reconciliation

Use this reference when two or more ZIP/task packs describe the same repository or product and the user asks to absorb, summarize, and execute them.

## Safe sequence

1. Record the current Git identity (`status`, branch, HEAD, write-tree) before interpreting the pack as current state.
2. Hash every supplied archive and extract only into the repository's ignored task-runtime/artifacts area.
3. Inventory files before opening large media or executing scripts. Read the start-here document, manifest, decision register, route/file map, contracts, acceptance matrix, and risk/license material first.
4. Build a small matrix with: pack claim, source file, current-tree evidence, route/API dependency, acceptance evidence, and disposition (`absorb`, `adapt`, `reference-only`, `defer`, `reject`).
5. Separate `frozen`, `current`, `planned`, `design-target-not-applied`, and `prototype` language. A prototype or historical task status is not a current capability, and a target manifest marked `design-target-not-applied` must not be reported as live configuration.
6. When packs conflict, compare external filename/version, SHA-256, generated timestamp, internal root directory, and the newest decision register. Prefer the latest explicit product decision only after checking whether it is marked planned rather than frozen. Record the conflict and the chosen precedence; if flipping the current default would break a verified path, implement the new option behind a reversible switch first and document the decision.
7. Do not assume an extracted archive path from a prior session. Inventory the actual extraction root because ZIPs commonly contain an additional product-named directory before `00_START_HERE.md`, manifests, or docs.
8. For frontend-first work, prefer a bounded slice that connects to an existing real API/DTO and adds a browser assertion. Do not create placeholder A2/A3 backend routes merely to make a prototype page look complete.
9. Write the route and disposition summary into a project-local intake note before changing source files.

## Frontend acceptance slice

For each accepted UI change, prove at least:

- visible user entry point;
- real route/state transition;
- closed DTO validation or fail-closed fallback;
- fresh isolated browser data root;
- semantic Chromium assertion;
- architecture/static checks after adding Playwright patterns.

If the UI only exposes `planned` or `unavailable`, keep it honest and add an explicit status marker rather than a fake count, progress bar, or action.

## Common Windows/Git-Bash details

- Use a project-local native path for `COGNITIVE_DATA_DIR`, such as `D:/All projects/<repo>/.hermes/task-runtime/<run>/data`.
- Avoid reusing a prior smoke directory when the product validates persisted command bindings; a stale directory can fail correctly before the UI path is exercised.
- If architecture policy scans runtime strings for external absolute paths, derive browser route globs from an approved prefix constant instead of writing `**/workspace/...` literally.

## Reporting

Report separately:

- what was absorbed and why;
- what was adapted due to current contracts;
- what was deferred because it needs A2/A3 backend support;
- current-tree verification;
- full-suite/environment failures that are not evidence of the accepted frontend slice;
- desktop/Tauri rows not executed.

Never summarize a historical package status as if it were a current commit, and never claim the whole product is complete because one browser slice passed.
