---
name: full-stack-absorption-verification
version: 1.0.0
author: "UNKNOWN"
license: UNKNOWN
platforms: [windows, linux, macos]
workflow_software: hermes
archived_at: 2026-08-21
source_path: C:/Users/ALEX/AppData/Local/hermes/skills/software-development/full-stack-absorption-verification/SKILL.md
---

---
name: full-stack-absorption-verification
description: "Use when proving every real case is wired frontend-to-backend end to end."
version: 1.1.1
author: Hermes Agent
license: MIT
platforms: [windows, linux, macos]
metadata:
  hermes:
    tags: [full-stack, backend, frontend, tauri, exact-sha, open-source-absorption, verification]
    related_skills: [agent-workflow-fortress, project-data-boundary, windows-development-environment, project-gap-analysis]
---

# Full-Stack Absorption Verification

## Trigger

Load this skill when a user asks to run a repository's backend, frontend, desktop shell, and exact-SHA gates end-to-end before executing an attached or repository-local open-source absorption pack, release checklist, or migration task pack.

## Principle

A source file, unit test, browser preview, or historical test count is not proof that the current product stack runs. Close the chain in this order:

```text
current tree → local gates → isolated runtime → real API readback
→ real browser evidence → current-tree desktop process → task-pack boundary
```

### Mandatory meaning of “frontend/backend connected”

When the user says “前端后端打通”, “frontend and backend are connected”, or “all real cases pass”, interpret it as a strict acceptance contract—not as “the API is reachable”:

```text
one named real case
  → one real user-facing frontend action
  → one real HTTP request
  → one persisted domain transition
  → one backend lifecycle result
  → one frontend readback of that same case
  → success + rejection/failure/retry evidence where the lifecycle supports it
```

Build a case/lifecycle matrix before claiming completion. Every backend chain must have a normal-user product entry point, a server-owned DTO/action reference (never raw persistence IDs), a browser replay against the same database, and a readback assertion. Backend E2E coverage never inherits frontend coverage. A page that exists in navigation but renders “not connected” is not a delivered lifecycle surface. Before declaring all frontend/backend work complete, enumerate every claimed lifecycle node—not just intake and learning—including Evidence, governance/Permission, Execution, Trace, Evaluation, Lesson, and delivery recovery. Each node must have either a real user-facing action plus persisted/readback evidence or an explicit blocked row in the matrix; backend-only endpoints and navigation placeholders do not count.

For stateful flows, assert convergence after each action: the source leaves the pending queue after approval, the next projection gains exactly that source, repeated clicks are idempotent or explicitly rejected, and failure responses leave the database unchanged. Test semantic source-bound actions rather than positional buttons or hidden database IDs. If multiple cases share a generated title or label, make the product projection source-specific before testing multi-case approval.

For Job/Outbox/Receipt chains, a single `delivery_state` field is not enough. Add a safe projection that separately reports Job state, Outbox state, attempt counts, Receipt presence, and dispatcher availability without IDs, payloads, or lease tokens. If a dispatcher exists in backend code but is not exposed through the product, it is not frontend coverage: add a controlled action that executes the real lease → consumer → receipt path, plus a requeue/retry action only for failed events. Verify both the initial pending/missing-receipt state and the converged delivered/recorded state through the UI and SQLite readback. When SQLite runs in WAL mode, do not feed an immutable sidecar-free reader to any live internal projection or consumer: retain strict checkpoint-only readers for offline/external read-only projections, but give internal Job Center/runtime graph reads and lease-fenced consumers a query-only live-WAL connection. Add a regression test that keeps a WAL writer/sidecar alive while the internal projection reads the same database. A real HTTP intake → subsequent `/api/jobs` read is the tight product-boundary repro; a direct service test alone is insufficient. Preserve the fail-closed sidecar rejection for immutable readers and do not solve the problem by forcing a checkpoint or deleting sidecars from a live server.

Keep browser and desktop evidence as separate acceptance rows. A real Chromium run cannot inherit Tauri coverage, and a Tauri executable that starts is not enough: verify the current binary, supervised Core child, actual loopback port, `/version`, `/health`, Workspace HTML, the new API projection/action, and clean child-process shutdown. When desktop readiness fails, preserve the exact process/port diagnosis and report the desktop row as blocked rather than converting the browser pass into a desktop pass.

Do not begin absorption implementation while the attachment is unread or while a claimed gate is represented only by stale history.

When driving a native desktop UI through Computer Use/UIA rather than WebDriver, treat every click as provisional until a fresh accessibility snapshot shows the expected semantic state transition. Re-capture after navigation, scrolling, modal open/close, or async refresh; element indexes are not stable across captures and foreground screen coordinates may be transformed by the desktop viewport. Record `unverifiable` as unverified, not as success. A successful Tauri happy path does not imply the failure→retry→replay branch: keep separate rows and continue only when the controlled failure is actually visible through the same product projection.

### Desktop bundle provenance before acceptance

For a Tauri smoke, build and launch only after running the repository's real bundle-preparation/staging step from the same worktree. Verify the staged runtime identity against the current product contract and reject stale identity payloads. A standalone `cargo build --release` is Rust-build evidence, not proof that the bundled Python runtime/resources are current. Keep the prepared bundle, target runtime, smoke root, and logs under the project data boundary; never repair a stale bundle by copying global Hermes resources.



- Read repository policy and the project-local data-boundary skill.
- Record `git status --short --branch`, `git rev-parse HEAD`, `git write-tree`, remote branch SHA, and the exact-SHA CI/workflow result.
- Treat a cancelled, skipped, stale, or different-SHA workflow as not passing.
- Create the task branch only after the current tree is clean and implementation is authorized.
- Keep one writer for the checkout; do not run write-capable schedulers or agents concurrently.

### 2. Inspect the task pack safely

- Read the ZIP/file inventory, manifest, instructions, risk/License material, contracts, scripts, and machine-readable tables before executing anything.
- Extract only to the project's ignored task-artifact directory.
- Never execute an unknown attachment script during inspection.
- Classify every candidate as reference-only, benchmark, sidecar, adapter, or core provider.
- Treat GPL/AGPL and unclear/commercial licenses as isolated or reference-only until separate legal and dependency review proves otherwise.
- When multiple packs describe the same product, reconcile them before editing: record the current-tree baseline, identify frozen decisions versus planned targets, list contradictions (for example default theme or product-center positioning), and choose the smallest reversible route that preserves the existing truth boundary. Do not implement every pack item just because it is present in an archive; attach each accepted item to a real current route, DTO, test, or explicit future boundary. Use [`references/attachment-pack-reconciliation.md`](references/attachment-pack-reconciliation.md).

### 2.5 Reconcile versioned packs and target state

When the user supplies replacement or suffixed archives (for example `v1.0-2` and `v1.0-3`), treat the external archive filename, SHA-256, generated timestamp, and the archive's internal root directory as separate identity fields. Do not assume the internal root name matches the attachment filename or reuse an older extracted path without inventorying it. Read the newest pack's decision register and target configuration, but check their state markers (`frozen`, `planned`, `design-target-not-applied`, `prototype`) before treating a recommendation as current implementation. If an older desktop pack and a newer positioning/configuration pack conflict, record the conflict explicitly and prefer the newer explicit decision for future work; do not silently rewrite a verified current tree or mix target configuration changes into an unrelated UI PR. Report both: (a) the package target, and (b) the current-tree fact.

### 3. Run local gates independently

Run and preserve separate results for root tests, subproject/integration tests, Ruff/type/syntax checks, architecture and repository-convention checks, whitespace/diff checks, browser JavaScript smoke, and desktop Rust tests/build.

On Windows Git-Bash, verify interpreter provenance before treating a worktree test result as valid. Hermes may inject its own interpreter and `PYTHONPATH`; an isolated worktree `.venv` can still import global Hermes packages and fail on binary extensions. Prefer a project-local `.venv` created with `uv venv` and run commands with `env -u PYTHONPATH .venv/Scripts/python.exe ...`; record `sys.executable`, `sys.prefix`, and the imported package path when diagnosing an import failure. This is an environment setup correction, not a product failure. Never switch branches or reset the canonical user worktree to prepare a task worktree; create/operate in a separate worktree and recheck the canonical branch/status after setup.

Do not collapse failures into one opaque shell chain. A wrapper that reports only an exit code is not enough when a gate fails; rerun the failing gate alone and preserve its error text.

### 4. Start an isolated backend

- Create a project-local runtime root and run the real migration before starting Core.
- Use a separate database for each smoke class; never test against the user's runtime database.
- **Trace every adapter/plugin from its registry entry or fixture to the product's engine chain or routing table.** An adapter that exists in a registry with working tests but was never added to the product's call-routing graph (`_ENGINES`, handler map, provider chain) is a real gap, not a delivered capability. Search for where the product actually dispatches to adapters by format/kind and cross-reference against the full set of registered adapters. If the registry has N entries but the engine chain only contains M < N, the difference is unbundled feature content — no tests against the product boundary exist for those M+1 through N entries. See `references/adapter-wiring-gap-pattern.md`.
- On Windows Git-Bash, pass `COGNITIVE_DATA_DIR` using an explicit native path (`D:/...`) or verified `cygpath -w` output. Do not assume `$PWD` survives MSYS conversion into native Python.
- Use loopback binding and bypass the local proxy with `curl --noproxy '*'` or an equivalent HTTP-client setting.
- Read `/version`, `/health`, Workspace status, jobs/receipts, and relevant Research/Knowledge read-only endpoints. Check status codes, response shape, and that internal IDs, payloads, tokens, and correlation fields are not exposed.
- Separate real API readback from a browser smoke that mocks API responses.

### 4.5 Audit the smallest real HTTP→SQLite→Chromium delivery slice

When a repository already contains delivery routes, a dispatcher, a SQLite projection, and UI buttons, do not immediately recommend implementing another backend layer. First separate **implementation coverage** from **automated product evidence**:

1. Search tracked tests/scripts for the concrete delivery endpoints and UI actions (`/workspace/api/delivery`, `/dispatch`, `/retry`, `delivery-dispatch`). If the hits exist only under `app/` and service-level tests, classify the source/service boundary as present but the real browser gate as missing.
2. Run one isolated live replay against the current tree: fresh migration/data root → real Core server → real HTTP intake through the product boundary → SQLite assertion of `Job=succeeded`, `Outbox=pending`, `Receipt=missing` → real Chromium page readback → semantic UI click → real dispatch HTTP request → same page refresh without process restart → `Outbox=delivered`, `Receipt=recorded` and matching SQLite readback.
3. Seed through the actual product action (for example a file-upload control), not direct SQL or a service helper. Direct SQL is acceptable only for a controlled negative/failure fixture after the success path is proven.
4. In Playwright, wait for semantic convergence (`Outbox pending：0`, `Receipt missing：0`, or a closed DOM state), not any pre-existing text such as the first `Receipt：recorded`; otherwise a stale row can make a race look green.
5. Keep real HTTP evidence, Chromium evidence, and direct SQLite readback as separate acceptance rows. A manual replay proves the capability on that run, but it does not become repository evidence until the replay is encoded in a tracked browser script and invoked by CI.
6. If an existing browser smoke uses `page.route()` mocks for status/intake/research, do not count it as delivery coverage. Extend it with a fresh context or add a focused real-delivery script, then add a static CI guard so the real path cannot silently regress to mocks.

See [`references/real-http-sqlite-chromium-delivery.md`](references/real-http-sqlite-chromium-delivery.md) for the boundary matrix, replay recipe, and minimum acceptance assertions.

### 5. Validate the frontend

- Run real Chromium/Playwright smoke, not only an HTML parser.
- Verify routes, visible Workspace entry points, import validation, queue/status projections, redaction, and responsive layout.
- Use a brand-new project-local data directory for each browser smoke replay unless the test explicitly proves restart/readback against the same database. Reusing a prior smoke directory can correctly trigger persisted-binding integrity guards and obscure the UI result; treat that as a fixture-isolation issue, not a reason to weaken the guard.
- Derive Playwright route patterns from a shared workspace prefix (for example `WORKSPACE_ROOT = "/" + "workspace"; JOBS_PATTERN = f"**{WORKSPACE_ROOT}/api/jobs"`) instead of embedding `**/workspace/...` literals when the repository architecture guard scans runtime strings for absolute paths.
- Keep business-data refresh distinct from `uvicorn --reload`; verify SSE/WebSocket/polling if the product claims real-time updates.
- If a wrapper redirects browser binaries to a project-local cache but reusable browsers intentionally live under an external toolchain root, keep test artifacts local and explicitly override only the browser-binary path to the validated external root. Do not copy the browser cache into the project.

### 6. Validate the real Windows desktop shell

- Build the current tree's Tauri executable.
- Start the actual `.exe`, not a browser preview or old portable artifact.
- Verify the Tauri process, WebView2 child, supervised Core child, loopback port, `/version`, `/health`, Workspace HTML, and redaction.
- Verify where SQLite and WebView/runtime state are written. Project-local test data does not automatically prove strict portable deployment; inspect `%LOCALAPPDATA%`/WebView2 state separately.
- Close the tracked process and independently verify that Tauri, Core, and WebView2 descendants are gone.

#### WebView click-runner prerequisite gate

A green Rust/backend lifecycle test is not WebView click evidence. Before reporting the desktop row as blocked or green, inspect the runner chain explicitly: (1) a runnable current-tree Tauri executable, (2) `tauri-driver` or an equivalent WebDriver bridge, (3) a native WebDriver binary compatible with the active WebView2/browser runtime, and (4) a tracked runner that performs semantic UI actions and durable readback. Installing `tauri-driver` alone is only setup evidence; it cannot attach without the native driver. If the native driver is absent, record the exact missing prerequisite and keep the acceptance row unexecuted—do not downgrade backend evidence into click evidence or fabricate a pass. Once all prerequisites exist, run a fresh isolated data root through upload → dispatch → failure → retry/replay → close/restart → readback, keeping the desktop result separate from Chromium evidence.

For the compact prerequisite/readback checklist, see `references/tauri-webview-runner-prerequisites.md`.

#### Windows WebDriver execution discipline

When native WebDriver becomes available, complete the runner instead of stopping at prerequisite discovery. Build and stage from the same worktree, create a W3C `tauri:options.application` session, and record the browser/driver versions. Require a non-zero element rectangle before clicking; hidden route elements are present in the DOM but are not actionable. Click the visible rail module first, then re-find the route element after navigation. Some tauri-driver/native-driver combinations reject an empty click body with `invalid argument: missing command parameters`; send a JSON WebDriver command body (for example `{"button": 0}`), then verify the semantic DOM transition. Treat element references as invalid after navigation, modal changes, or async refresh. Close the WebDriver session before stopping only the driver processes, and verify ports are closed without mass-killing unrelated WebView2 processes. The complete recipe and evidence matrix are in [`references/tauri-webdriver-windows-replay.md`](references/tauri-webdriver-windows-replay.md).

**When a desktop build is impractical** (e.g., 45+ minute Rust/Tauri build, missing toolchain, or the current branch is not CI-triggered): do not skip silently or fabricate evidence. Classify the desktop dimension as **partial** with the exact reason documented in the evidence matrix. The release manifest should truthfully report `public_installer: not_implemented` if public distribution also lacks a CI gate. A partial desktop row does not block the entire verification cycle — report it honestly and proceed to the next dependency-ready dimension.

### 7. Execute Sprint 0 conservatively

Before heavy dependencies or external services, implement only a baseline audit document, stable Provider/data contracts, empty/no-op providers with safe defaults, sanitized fixtures and contract tests, explicit disabled-by-default Feature Flags, a License Manifest with source/tag/commit/license/risk/absorption mode, and an SBOM or dependency inventory for the actually enabled runtime.

SQLite remains the source of truth. Derived vector, summary, and retrieval indexes must be rebuildable. Removing an optional provider must leave the core importable and startable. No agent or provider may auto-promote knowledge or alter security policy.

## Evidence and reporting

### Workspace delivery and failure-matrix audit

For Workspace reviews covering HTTP/SQLite/Chromium/Tauri, Outbox/Receipt, retry/replay, fail-closed behavior, or public redaction, separate **implementation coverage** from **product-boundary coverage**. A service-level test of `dispatch_once()` or `workspace_delivery()` does not prove that a real user-facing HTTP route, browser action, or Tauri WebView action reaches the same SQLite state.

Build a boundary matrix with separate rows for:

```text
real intake HTTP → Job + Outbox + Command Receipt → public pending projection
public UI dispatch → lease/consumer → Delivery Receipt → public delivered projection
failure → public failed projection → retry → replay → receipt convergence
SQLite tamper/orphan/malformed binding → fail-closed HTTP response → safe UI empty/error state
Chromium evidence
Tauri backend HTTP evidence
Tauri WebView click evidence
```

Use repository searches to prove the distinction: enumerate `/workspace/api/delivery`, `/dispatch`, and `/retry` references in tests/scripts, then compare them with direct service calls. A browser smoke that mocks `/api/status` or `/api/intake` is not real backend coverage; a lifecycle browser script that seeds unrelated tables is not Outbox/Receipt coverage; a Tauri process/readiness or NSIS installer smoke is not WebView click coverage.

For public delivery projections, require stricter evidence than “no ID appears in `repr(payload)`”. The server-side projection must validate one-to-one Job/Outbox/Command Receipt/Delivery Receipt bindings, canonical payload and event type, allowed state combinations, malformed JSON, and orphan rows. Corruption must fail closed before returning an aggregate. The frontend validator should reject unexpected fields or, at minimum, the server DTO must be closed and separately tested through `TestClient`.

For retry/replay, test the crash boundary where a Delivery Receipt is committed but Outbox finalization is not. A valid existing receipt must be replayable without duplication; a conflicting receipt, stale lease, expired lease finalization, orphan event, or mismatched payload must not be silently requeued or reported as delivered. Prefer injectable clocks/lease durations over real sleeps.

**Testing failure-path endpoints (retry, requeue, replay):** The success path must be proven through real HTTP → persistence → readback first. For states that cannot be reached naturally through the product UI (e.g., an outbox row in `failed` state because the handler succeeds by default), seed the failure state via **controlled direct SQL against the isolated test database** before hitting the retry/replay endpoint. The sequence is:
1. Prove the success path (real HTTP upload → job created → dispatch → delivered → receipt recorded).
2. Force one row to `failed` via direct SQL (`UPDATE workspace_outbox_v1 SET state='failed' WHERE state='delivered'`).
3. Verify the failure projection appears through the real API (`GET /api/delivery` shows `outbox: {failed: 1}`).
4. Call the retry endpoint (`POST /api/delivery/retry`) and assert `status: requeued`.
5. Verify the pending projection reappears through the real API.
6. Dispatch again and verify delivered + receipt recorded convergence.
7. Assert restart readback from a new HTTP connection returns identical state.
This pattern is also referenced in step 4.5 item 3 ("Direct SQL is acceptable only for a controlled negative/failure fixture after the success path is proven").

Keep product-truth drift in the matrix: compare the release manifest, README/handoff, UI copy, route implementation, and current tests. Do not let a stale “dispatcher not implemented” sentence coexist with an `available` capability and live dispatch/retry buttons without classifying it as a release-truth gap.

See [`references/workspace-failure-matrix-audit.md`](references/workspace-failure-matrix-audit.md) for the reusable command/evidence pattern and next-cycle task template.

### Browser delivery evidence: async intake and modal lifecycle

For a real Chromium intake-to-delivery test, treat the browser as asynchronous at both UI boundaries: after submitting a file/URL, wait for the result projection to leave its initial `处理中…` state before asserting success; after the intake assertion, close the modal through its real accessible close control before navigating or clicking controls behind it. Otherwise a test can read a transient loading state or time out because the open modal intercepts pointer events. Use semantic convergence (`Receipt recorded：1`, `Outbox pending：0`, or an equivalent closed DOM state) rather than fixed sleeps, then reload the same page and assert the persisted projection again. Keep the isolated database and Playwright browser cache under the project-data wrapper.

For tracked browser smoke scripts that import sibling test helpers, keep both entry modes valid: run under pytest with the repository `pythonpath`, and run directly from Git-Bash/Windows Python by inserting the repository root when `__package__` is empty. Verify the direct entry itself, not only collection. A `ModuleNotFoundError` at direct execution is a script-delivery defect, not evidence that the browser path is unavailable.

### Evidence matrix implementation rule

Build the matrix from structured evidence written immediately after the real response/state assertion. Do not infer coverage from step names, log labels, or a successful HTTP status alone. For each key, record the exact semantic predicate (for example `status == -1 and error == connection_failed`, `outbox.failed > 0`, `status == requeued`, or delivered plus receipt recorded). A final report must copy the evidence table, and a failed/raised step must leave later keys false. Run the standalone lifecycle reporter as well as pytest so the executable evidence path is verified.



See [`references/live-wal-and-structured-matrix.md`](references/live-wal-and-structured-matrix.md) for the live-WAL reproduction, semantic evidence map, and direct browser-script entry pattern.

When the task is driven by a sleep queue or cron, an accepted job, `execution_success`, a zero exit code, or a heartbeat is not proof of progress. Re-read the live project state/activity ledger and scheduler list, verify the claimed file/test/API artifact, and advance the queue only from that evidence. If a previous handoff has a stale branch, HEAD, port, job ID, or test count, rebuild the baseline from the current checkout before resuming. A dirty checkout may be continued only when the current session can prove the WIP is its controlled change and no other writer is active; unknown or concurrent WIP is a blocker.

For a repeated browser timeout, do not keep changing fixed sleeps or locator waits. First capture request/response, console, and page-error events. A missing request or `ReferenceError` is a runtime defect, not a slow test. After the root cause is fixed, use a real API response or semantic DOM state as the gate and remove temporary diagnostics before the final replay. A page that is static in HTML but has an undefined refresh function is not frontend coverage.

**Current-tree/runtime provenance gate:** Before diagnosing a live-WAL, schema, or projection failure from a browser runner, record the runner worktree HEAD, `git status`, imported module paths, `COGNITIVE_DATA_DIR`, migration/schema revision, and the exact server command. A fix present in `origin/main` or a separate readiness worktree does not change a runner launched from an older canonical checkout. Re-run the failing HTTP action directly and capture status/body before changing waits or UI locators; classify a stale checkout or stale bundled runtime as provenance failure, not product regression. Run tracked browser scripts from a fresh project-local ignored data root and a clean task worktree when possible, then recheck the canonical checkout status. If a script imports sibling test helpers, verify both module and direct entry; direct-entry import failures are script-delivery defects. See `references/stale-runtime-and-runner-provenance.md`.

Real-time claims require an explicit no-restart test: leave the page open, change state through the real HTTP/UI path, and assert the same page reads back the new projection through polling/SSE/WebSocket. Keep this separate from a button handler that calls refresh immediately. Tauri Core HTTP and Workspace HTML checks are necessary but do not prove a real Tauri WebView click path; keep Chromium and Tauri rows separate in the matrix.

 State separately what passed on the current tree, what passed only historically, what was blocked by setup/environment, and what was not executed.

### Partial desktop evidence must preserve scheduler continuity

When Rust/Tauri unit tests and builds pass but the real WebView/desktop lifecycle row is not executable because no harness or runner exists, classify the result as **partial** rather than green or failed. Preserve exact current-tree identity, report the missing harness as an unexecuted acceptance gate, and keep the bounded follow-up scheduled unless an explicit policy says to pause. Do not write `blocked` solely from missing execution infrastructure; reserve blocking for a real failure, unsafe ownership state, or policy gate.

Never convert a successful unit test into a claim that the production route, browser, desktop shell, or release artifact passed. If any matrix row is blocked or any claimed lifecycle node lacks frontend action/readback evidence, keep executing or report the exact blocker; do not send an interim “completed” response. The final response is allowed only after the current-tree gates and every acceptance row pass, with asynchronous/background capabilities clearly separated from the verified on-demand path.

## Common pitfalls

- Running Core before migration and mislabeling fail-closed startup as a product regression.
- Using `$PWD` in a Git-Bash export passed to native Windows Python and silently producing a malformed path.
- Treating a mocked browser API as backend verification.
- Reusing an old portable EXE instead of building the current tree.
- Calling a cancelled CI workflow green.
- Letting the task-pack ZIP execute before its manifest and license boundaries are reviewed.
- Adding a large provider dependency in Sprint 0 instead of proving the removable contract.
- **Reusing a stale smoke database.** A previous browser run may contain persisted command bindings or partial delivery state. Do not delete the integrity check or reuse the directory; create a fresh ignored child data root for the next replay, then separately test restart/readback when persistence is the subject.
- **Architecture-guard-incompatible Playwright patterns.** A runtime string such as `**/workspace/api/jobs` may be classified as an absolute path by repository policy even though it is a browser glob. Build the glob from the already-approved workspace prefix constant and rerun the architecture guard.
- **Implementing every attachment target at once.** A pack can contain future UI prototypes, contradictory theme defaults, and unimplemented backend contracts. Reconcile frozen/planned status first, then absorb only reversible current-tree changes with a real route and evidence row.
- **Hardcoded matrix entries without real execution.** Never set a verification-matrix cell to `True` (or `passed`) without a real tool call that exercises the exact endpoint, asserts the expected state transition, and records the response. A line like `matrix["failed"] = True` or `matrix["retry"] = True` next to a comment saying "endpoint exists" is not evidence — it is a fabricated completion that defeats the matrix's purpose. Every matrix row must map to a named test step whose `record()` call returned a real status code and passed a real assertion. When you discover such hardcoded rows during an audit, file them as a blocker: replace them with real endpoint calls before claiming the matrix is complete.
- **Python module-level imports cascade into unavailable dependencies.** A service module that imports `numpy` (or any heavy dep chain) at the top level prevents the entire app from loading if that dep is missing — even if the importing functions are never called. Fix: move heavy imports into a lazy `_import_heavy()` function with a dict cache, callable only from functions that need them. The delivery/test path must remain importable without the heavy chain.
- **Windows SQLite file-lock prevents `shutil.rmtree` after subprocess kill.** After killing a uvicorn subprocess on Windows, SQLite files stay locked for seconds. Fix: wait 1.5s after `proc.kill() + proc.wait()`, then clean per-file with `p.unlink(missing_ok=True) + PermissionError catch`, rmdir from deepest path first. Never let cleanup failure override a green test matrix.
- **Brittle sub-app mounts blocking Core startup.** A single missing transitive dep in any mounted sub-app (knowledge_base, research API) prevents Core from loading. Fix: wrap each sub-app import in `try/except ImportError` and mount conditionally. See `references/python-lazy-import-and-subapp-fault-tolerance.md`.
- **Optional-dependency test assertions that rely on a specific error message.** When writing adapter or provider tests for packages that may or may not be installed, an assertion like `assert "Empty source" in result.error` will fail if the "not installed" guard fires first — the code path never reaches the later check. Fix: for graceful-failure tests that don't care which guard triggered, assert only `not result.success`. Reserve exact-error-message assertions for the dedicated "not installed" test, which deliberately mocks the import to fail. For environment-conditional tests (real extraction, real network call), use `pytest.skip()` guarded by `try: import <pkg>` so they are silently skipped when the dependency is absent, not falsely red.
- **Adapters individually tested but never wired into the product engine chain.** A file called `adapter_fixtures.py` that registers 15 capabilities in the global registry, plus 15 test classes each with 4–10 green tests, can give a false sense of completeness. If the product's actual ingestion/format-dispatch pipeline (`_ENGINES` dict, handler map, or route table) only references 4 of those 15, the gap is product content, not just a missing install. Detection: search for the format kind (e.g. "image", "article") in the engine-chain data structure and compare against the registry. Every entry present in the registry but absent from the engine chain is an unbundled adapter — it exists as a standalone library call but the product never invokes it.
- **Import-time adapter function snapshots defeat runtime configuration and product-path tests.** A dispatch-map builder that stores `module.convert_x` in a local dictionary at module import captures the old callable forever; later monkeypatching, plugin reload, or configuration/skin loading may appear ineffective even though the registry changed. Keep heavy modules lazily imported, but resolve the named adapter callable at invocation time (for example, `getattr(adapter_module, adapter_name)(typed_input)`). Prove the seam RED→GREEN through the public product dispatcher: begin with a supported extension/kind, replace the adapter callable with a controlled result, call the real `convert_file`/route entrypoint, and assert the typed input, selected engine, and returned content. A direct adapter test or registry-count assertion does not cover this boundary.

## Reference

See [`references/full-stack-absorption-verification.md`](references/full-stack-absorption-verification.md) for a concise reusable evidence template and Windows command patterns.

For the source-bound Job/Outbox/Receipt replay sequence and safe DTO shape, use [`references/source-bound-delivery-pattern.md`](references/source-bound-delivery-pattern.md).

For the controlled SQL negative fixture pattern (prove success path first, then seed failure state via direct SQL, then test retry/replay through real HTTP), use [`references/controlled-sql-failure-fixture-pattern.md`](references/controlled-sql-failure-fixture-pattern.md).

For seeding the real migrated schema, starting the real server, and verifying aggregate-state + desensitization with Playwright/Chromium, use [`references/lifecycle-ui-e2e-evidence-pattern.md`](references/lifecycle-ui-e2e-evidence-pattern.md).

For live scheduler recovery, asynchronous browser diagnosis, no-restart polling evidence, and separate Tauri WebView rows, use [`references/live-runtime-ui-evidence.md`](references/live-runtime-ui-evidence.md).

For the three-dimension release gate evidence matrix (build / installer lifecycle / public distribution) with concrete acceptance criteria and partial-classification guidance, use [`references/release-gate-evidence-matrix.md`](references/release-gate-evidence-matrix.md).

For the current-bundle Tauri smoke sequence, semantic recapture discipline, and separate happy/failure branch matrix, use [`references/tauri-current-bundle-smoke-recipe.md`](references/tauri-current-bundle-smoke-recipe.md).

For the adapter-wiring gap pattern (registered adapters never wired into the product engine chain), see [`references/adapter-wiring-gap-pattern.md`](references/adapter-wiring-gap-pattern.md).

For module-level registry/test-isolation fixes (cached `ensure_registered()` flag vs external `_ADAPTER_REGISTRY.clear()`), see [`references/module-level-registry-test-isolation.md`](references/module-level-registry-test-isolation.md).

For full local Markdown/JSON Canvas batch testing, Windows external dependency isolation, candidate-count invariants, and auditing every internal live-WAL knowledge path, see [`references/full-materials-batch-and-live-wal.md`](references/full-materials-batch-and-live-wal.md).

