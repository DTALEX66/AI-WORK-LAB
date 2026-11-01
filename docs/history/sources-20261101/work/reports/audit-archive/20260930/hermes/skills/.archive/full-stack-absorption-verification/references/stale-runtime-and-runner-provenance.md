# Stale Runtime and Runner Provenance

Use this reference when a real browser runner reaches an unexpected projection error, especially a live-WAL/checkpoint/schema failure.

## Provenance sequence

1. Record the runner worktree path, `git status --short --branch`, `git rev-parse HEAD`, and the remote/current target SHA.
2. Record the exact server launch command, imported module path, `COGNITIVE_DATA_DIR`, migration/schema revision, and bundled runtime identity.
3. Run the failing HTTP action directly and capture status plus redacted response body before changing waits or locators.
4. Compare the loaded source/runtime with the worktree where the claimed fix was verified. `origin/main` or a separate readiness worktree does not affect a server started from an older checkout.
5. Re-run the browser script only from a fresh project-local ignored data root; prefer a clean task worktree so fixture writes cannot contaminate user WIP.
6. Verify both module and direct script entry. A direct-entry `ModuleNotFoundError` is a script-delivery defect, not evidence that the browser path is unavailable.
7. Recheck canonical `git status` and process ownership after the run. Restore only fixtures created by the runner; never touch pre-existing user WIP.

## Classification

- HTTP error caused by old checkout or stale staged bundle: provenance mismatch, not a product regression.
- HTTP success but no semantic DOM convergence: capture request/response, console, and page errors before changing timing.
- Different worktrees producing different results: keep acceptance rows tied to exact worktree/runtime identity; do not inherit the newer worktree's PASS.
- A browser PASS on Chromium does not upgrade Tauri/WebView or current-tree desktop evidence.

Never mark a matrix row PASS from a claimed fix, branch name, or CI history alone; require the exact runtime action and durable same-case readback.