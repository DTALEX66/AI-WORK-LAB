# Live runtime and UI evidence recipe

Use this reference when a full-stack replay has a backend/API pass but the browser or desktop row is still uncertain.

## Recovery baseline

1. Read live `git status --short`, branch, HEAD, active processes, and scheduler list.
2. Treat handoff values for job IDs, ports, test counts, and prior output as historical only.
3. If the tree is dirty, prove the WIP belongs to the current writer before continuing; never reset/clean unknown changes.
4. Use a fresh project-local ignored data root and run migration before the isolated runtime.

## Browser diagnosis sequence

When a locator or fixed wait times out:

```python
page.on("request", lambda r: print("REQUEST", r.url))
page.on("requestfailed", lambda r: print("REQUEST_FAILED", r.url, r.failure))
page.on("console", lambda m: print("CONSOLE", m.type, m.text))
page.on("pageerror", lambda e: print("PAGE_ERROR", e))
```

A concrete failure pattern was a Machine page stuck in loading while `/workspace/api/runtime/candidates` was healthy. Console evidence showed `refreshMachine is not defined`; the correct fix was to restore the missing function, not to add longer waits. After fixing, remove diagnostics and replay the full flow.

Use `expect_response` for mutating actions and semantic DOM assertions for projections. For polling, leave the same page open, mutate state through a real same-origin HTTP request, and wait for the visible projection to converge. This proves no-restart refresh; a button's immediate `refreshRuntime()` call alone does not.

## Desktop separation

A Tauri `/version`, `/health`, `/workspace`, or Workspace API 200 proves Core readiness and HTML/API availability only. It does not inherit Chromium coverage and does not prove WebView clicks. Record separate rows for:

- actual current `.exe` and supervised Core port;
- Workspace page/API response and redaction;
- real WebView user action and readback;
- shutdown with child-process absence;
- portable/WebView2 data-root inspection.

## Minimum output contract

Preserve complete JSON/stdout for every claimed replay, including source-case statuses, lifecycle counts, delivery/outbox/receipt convergence, rejection-without-state-change, and redaction result. Never report only exit code 0 when the output is the acceptance evidence.

## Lifecycle matrix rule

An aggregate `Permission/Execution/Trace/Evaluation/Lesson` projection is useful privacy-safe readback, but it is not five independent frontend actions. Mark each lifecycle row independently as `frontend action`, `HTTP`, `persistence`, `readback`, and `failure/retry` with an exact evidence reference; leave unsupported rows blocked.
