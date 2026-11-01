# Tauri WebView runner prerequisites

Use this checklist before attempting a desktop click-level lifecycle gate.

## Evidence layers

Keep these rows separate:

1. Rust/backend lifecycle: Core launch, token-bound readiness, isolated data root, graceful shutdown.
2. Tauri shell lifecycle: current executable starts, WebView2 child exists, Core child/port are live, shutdown removes descendants.
3. WebView interaction: a real WebDriver client performs semantic upload/dispatch/retry/replay actions and reads the persisted projection after restart.

A passing row never implies the next row passed.

## Runner chain

Verify all four prerequisites before launching the test:

- Current-tree Tauri executable (not an old portable artifact).
- `tauri-driver` or an equivalent WebDriver bridge.
- A native WebDriver binary compatible with the active Windows WebView2/browser runtime (for example the matching Edge driver).
- A tracked runner using semantic locators, an isolated project-local data root, and durable readback assertions.

`tauri-driver --help` only proves the bridge is installed. It does not prove that a native driver can be spawned or that a Tauri window can be controlled.

## Blocked-state recording

If the native driver or GUI runner is absent, record:

- exact prerequisite missing;
- commands actually attempted and their exit results;
- backend/Tauri evidence that did pass;
- the WebView row as `not executed` or `partial`;
- current HEAD/tree and unchanged-WIP status.

Do not call this a product failure, and do not convert backend or Chromium evidence into WebView click evidence.

## Minimum real replay

With all prerequisites available, use a fresh project-local runtime root and prove:

```text
upload → pending projection → dispatch → delivered receipt
→ controlled failure → retry/replay → reload or restart → same durable projection
```

Capture process/port diagnostics, browser console/page errors, and cleanup independently. Keep generated logs and browser artifacts under `.hermes/task-runtime/`.
