# WORK-LAB Observer Visual Assets R2 — Desktop Component Status

> Status: `PRODUCTION_ARTIFACT_AND_GIT_DELIVERY_VERIFIED`
>
> This document records the repository implementation of
> `WORK-LAB-OBSERVER-VISUAL-ASSETS-R2.zip`. It is a current implementation
> summary, not a release approval and not permission to perform live/global
> mutation.

## User requirement reconciled

The intended product surface is a **portable desktop component**, not a browser
website:

- Tauri owns the desktop shell, tray entry, borderless window, and floating panel.
- The local `web/` tree is the embedded WebView rendering layer; it is not the
  distribution surface users must open in a browser.
- The visual shell is stable after approval. Future updates should normally be
  projection data/parameters delivered through the read-only API, not frontend
  redesigns.
- Observer remains a strictly read-only consumer of the canonical projection.

## Implemented desktop contract

| Surface | Entry | Window contract |
|---|---|---|
| Main | `index.html?view=full&mode=UNKNOWN&theme=dark` | 1280x820, borderless, opaque, resizable |
| Panel | `index.html?view=compact&mode=UNKNOWN&theme=dark` | 440x780, fixed size, borderless, opaque, always-on-top, skip-taskbar |

The panel remains hidden until opened from the tray. Closing either surface
hides the application to the tray rather than executing an external action.

Relevant source:

- `30-observer/work-lab-observer/src-tauri/tauri.conf.json`
- `30-observer/work-lab-observer/src-tauri/src/lib.rs`
- `30-observer/work-lab-observer/src-tauri/capabilities/default.json`

## R2 visual implementation

Checked-in brand assets:

- `web/assets/brand/app-icon-512.png`
- `web/assets/brand/design-tokens.json`
- `web/assets/brand/observer-icons.svg`
- `web/assets/brand/work-lab-observer-symbol.svg`
- `web/assets/brand/work-lab-observer-tray.svg`

The Compact component now has:

- fixed 440px component width;
- truthful transport verdict and approved-project facts;
- dense read-only project list without unsupported KPI placeholders;
- no `0/0`, fake LIVE, fake CI, or unknown-cost decoration;
- dark/light theme tokens and R2 status colors;
- no mutation controls or external runtime assets.

## Data boundary

The frontend consumes the canonical projection through `GET /api/v1/snapshot` and subscribes to the loopback-only `GET /api/v1/events` SSE stream.

- POST/PUT/PATCH/DELETE are rejected by the client boundary.
- Unknown projection fields are ignored for forward compatibility.
- Unknown cost remains unknown; subscription usage remains `not-metered`.
- Last-good retains only a previously successful sidecar snapshot. Initial GET
  and SSE recovery use bounded retry; production never silently falls back to
  the bundled fixture.
- No credentials, prompt/response bodies, private session data, or provider
  auth state are read.

## Issues found and corrected during implementation

1. The Compact header inherited the shell's column direction and expanded
   vertically. It now has an explicit horizontal fixed component header.
2. Compact health cells read `v` while the source objects used `value`, causing
   blank values. The renderer now reads and escapes `value`.
3. Compact token values were formatted as strings and then passed through the
   integer formatter, producing `—`. The renderer now applies the explicit token
   formatter before escaping.
4. The visual asset contract test initially treated SVG's standard XML namespace
   as a remote asset. It now rejects only remote runtime/image references.
5. The desktop component contract test initially lacked the repository runner's
   `run()` export and overmatched the descriptive word `shell`. Both test-only
   false positives are corrected.
6. Initial Snapshot failure previously stayed offline forever. The product now
   retries GET with capped exponential backoff while retaining last-good.
7. SSE replacement previously reset the reconnect delay before every attempt.
   Resource close and retry-state reset are now separate operations.
8. Concurrent SSE clients previously shared one boolean connection flag. The
   sidecar now derives connection truth from a thread-safe client count.
9. Transport now projects the actual SSE connection state and timestamps.
   Sidecar startup no longer invents heartbeat or writer freshness; both remain
   null until the corresponding real event is observed.
10. The normal sidecar lifecycle now supervises the Workflow-owned durable
    producer. An unhandled tick failure is recorded and retried rather than
    silently killing the worker thread.
11. Collector event identities are deterministic. Re-polling unchanged Task,
    Git, source-quality, growth, or usage inputs updates freshness without
    duplicating additive usage or canonical facts.
12. Collector health is persisted and drives one 6/6 coverage contract (five
    collectors plus worker loop); freshness is independently projected as
    `FRESH`, `STALE`, or `UNKNOWN`.
13. EventSource failure previously retained last-good content while still
    rendering `Sidecar 已连接`. Local transport failure now overrides the stale
    copy to `OFFLINE`; the final production WebView2 was verified through
    DOM readback, reload console, real scrolling, and normal-mode `LIVE/FRESH`.

## Evidence and verification

Fresh local verification after the implementation:

```text
JS UI + desktop component tests: 58 passed, 0 failed
Collector/durable/snapshot/endpoint focused tests: 49 passed
Error Ledger: 77 entries, 13 classifications, raw_sensitive_data=false, counts_consistent=true
Production build command: cargo tauri build --no-bundle
Production artifact: src-tauri/target/release/app.exe (9,539,072 bytes; SHA-256 a20fc3de9a0ff9111bc210f9854c373f330818b083aacf3a49335aeeb167b420)
Production build: cargo tauri build --no-bundle, 18.58s final incremental build; temporary Cargo patches removed and lockfile restored to the branch HEAD
Real WebView2: Snapshot 200, named SSE snapshot + heartbeat, 28/28 TaskPack, 6/6 coverage, reload console 0 errors, real scrolling, no horizontal overflow
Final runtime target: one sidecar, one app.exe, no temporary static server, no CDP listener
```

The plain browser was used only for early frontend QA. Final acceptance used the
actual production Tauri/WebView2 process; browser-only evidence is not being
substituted for the desktop runtime.

## Remaining publication boundaries

The host still has no complete system Visual Studio/MSVC toolchain. The verified
build uses project-local xwin SDK/CRT plus Rust `rust-lld` and temporary
runtime-local build-dependency patches; those Cargo patches are removed after
the build. This is sufficient for the verified production EXE and does not
claim a signed installer, ZIP bundle, commercial release, or a globally
installed toolchain. Exact-SHA source CI is independently complete.

## Delivery state

- R2 implementation and production EXE: complete and verified in the local working tree.
- Required tests and focused verification: passed.
- External provider/live mutation: not executed.
- Source Git delivery and exact-SHA CI: complete through controlled PRs and independent candidate/merge-SHA runs; the latest identity is read from GitHub history rather than self-declared here.
- Human release approval, signing and publication: not executed and not implied by source delivery.
- R2 implementation commit/PR/CI/merge: PR `#30`, exact-head PR run
  `31251264323`, final main push run `31251306631`, merged implementation SHA
  `f141946bfa55fd77120443bacd45aee0049c16e2`.
- Final generated-state reconciliation: PR `#31`, exact-head PR run
  `31251503373`, final main push run `31251545134`, merged reconciliation SHA
  `5d2ceb264edf54c42e347acd1246202a0add31ac`.
- Local and remote `main` were read back equal after each merge. The two SHA
  values above remain historical implementation/reconciliation ancestry; PR
  #104 (`992e62b...` → `259fc210...`) is the later truth/recovery anchor. Any
  runtime-continuity delivery after that anchor is identified by GitHub PR,
  branch, and exact-SHA run history, not by a self-referential “latest PR” field
  in this file; no local dirty-tree claim is substituted for GitHub CI.

## Source and scope

- Source attachment: `.hermes/desktop-attachments/WORK-LAB-OBSERVER-VISUAL-ASSETS-R2.zip`
- Active modules remain exactly:
  - `10-workflow/workflow-assistance`
  - `30-observer/work-lab-observer`
- No second Observer UI, Agent/chat product, task runtime, memory service,
  provider gateway, or external mutation path was added.
