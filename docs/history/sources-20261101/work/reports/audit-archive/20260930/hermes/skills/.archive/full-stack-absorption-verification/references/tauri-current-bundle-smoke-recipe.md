# Tauri current-bundle smoke recipe

Use this as a compact, re-runnable acceptance checklist for a Windows Tauri/WebView smoke.

## Preconditions

- Work in an isolated project worktree and project-local `.hermes/task-runtime/` root.
- Preserve canonical checkout WIP and do not touch Hermes global resources.
- Create a fresh portable data root for the happy-path replay; reuse the same root only for the explicit restart/readback phase.

## Build and stage

1. Run the repository's real bundle preparation from the same worktree.
2. Verify the staged readiness identity is the current contract, not a stale prior product/workspace name.
3. Run `cargo fmt --all -- --check`, `cargo test --lib`, and `cargo build --release`.
4. Confirm the executable's staged `runtime/` contains the prepared current bundle. `cargo build --release` alone is insufficient because it does not refresh Python/resource staging.

## Happy path matrix

Record each row from a fresh semantic snapshot and real state change:

```text
launch/readiness       native title + current WebView document
intake                 URL/file submitted; real success projection
pending                job succeeded; outbox pending; receipt missing
owned dispatch         outbox delivered; receipt recorded; pending=0
review                 Research queue contains the same source
approval               queue empty; Knowledge candidate visible
restart                same portable root; job/receipt/candidate visible again
```

## Native interaction discipline

- After every click, navigation, scroll, modal transition, or async refresh, capture a fresh AX/SOM tree before using any element index.
- Never reuse an element index from an earlier capture.
- Treat `unverifiable` clicks as unverified until the next snapshot proves the semantic transition.
- Prefer semantic labels; use coordinates only after a fresh screenshot and record the coordinate transform risk.

## Failure branch

The happy path does not prove failure/retry/replay. Use a controlled failure that the product can actually project, then separately assert:

```text
failed projection → retry/requeue → pending projection → replay/dispatch → delivered + receipt
```

If the UI has no reachable failure/retry control, keep the Tauri failure row `NOT COMPLETED`; use the already-verified backend/Chromium matrix only as separate evidence.

## Cleanup

Stop only the smoke process tree owned by this run. Do not mass-kill unrelated WebView2 processes. Run `git diff --check` and `git status --short` after the smoke; no smoke artifact should be staged or committed.
