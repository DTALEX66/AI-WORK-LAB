---
name: desktop-runtime-provenance
version: 1.0.0
author: "UNKNOWN"
license: UNKNOWN
platforms: [windows, linux, macos]
workflow_software: hermes
archived_at: 2026-08-21
source_path: C:/Users/ALEX/AppData/Local/hermes/skills/software-development/desktop-runtime-provenance/SKILL.md
---

---
name: desktop-runtime-provenance
description: "Prove desktop bundle provenance before readiness acceptance."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [windows, linux, macos]
metadata:
  hermes:
    tags: [desktop, tauri, runtime, bundle, provenance, readiness, webview]
    related_skills: [desktop-build-verification, systematic-debugging, project-data-boundary]
---

# Desktop Runtime Provenance

## When to Use

Use when a native desktop shell launches a Python/Node backend and the shell reports readiness timeout, identity mismatch, or an unexpected UI even though the loopback endpoint returns `200`. Use before changing validators, increasing timeouts, or accepting legacy product names.

## Core Rule

A successful HTTP response from the wrong packaged runtime is still a failed desktop acceptance. Prove the exact backend source/package used by the current executable.

## Workflow

1. **Capture the exact response first.** From the owned loopback port, record status, headers, byte count, transfer/content framing, and a schema-only body shape. Never print launch tokens, credentials, prompts, or cookies.
2. **Classify the rejection layer.** Separate connect/write/read/UTF-8/header/status/body/identity failures. `200 + identity failure` means the transport worked; do not weaken the identity predicate.
3. **Compare source and bundle.** Inspect the checkout route and the exact bundled `site-packages/app` (or equivalent package) loaded by the executable. Check the product/workspace identity and module path, not only import success.
4. **Rebuild through the project packaging path.** Use the repository's normal wheel and `prepare_bundle`/staging command. Keep the fresh runtime under the project-owned ignored runtime boundary. Do not copy Hermes global resources or patch global state.
5. **Verify provenance before launch.** Run the staged interpreter in isolation, import the backend entrypoint, and print only the resolved module path and a safe identity marker. Verify the bundle contains the current source, not a stale release package.
6. **Build the EXE, then verify again.** Tauri/Cargo build scripts can recreate or overwrite `target/release/runtime`; a symlink or manual package replacement that worked before the final build is not durable evidence. Re-check the runtime after the final build.
7. **Cold-launch and accept in layers.** Require backend lifecycle, native shell lifecycle, WebView navigation, then real WebView interaction. HTTP `200`, a native window, Rust tests, or Chromium smoke cannot substitute for WebView evidence.
8. **Separate Rust compilation from resource packaging.** `cargo build --release` may leave `target/release/runtime` unchanged; use the repository's actual Tauri packaging command (`npm run tauri -- build ...` or its CI equivalent) after `prepare_bundle`, then read back the packaged runtime. A manual target-directory copy is smoke setup only, not reproducible delivery evidence.
9. **Exercise security policy, not around it.** For URL intake, use only policy-allowed schemes, addresses, and ports. Treat `blocked address`/`blocked port` as valid controlled-failure evidence; never expand an allowlist merely to make a local fixture pass.
10. **Record residual gaps honestly.** If upload, dispatch, retry/replay, or restart readback was not exercised in the Tauri WebView, mark it not executed/partial rather than inheriting browser-layer evidence.

## Windows/Tauri Readiness Notes

- If HTTP/1.1 repeatedly returns `200` but native readiness does not accept, capture the exact response before changing protocol versions. On Windows/Uvicorn, a controlled HTTP/1.0 `Connection: close` probe may be a valid compatibility fix, but it must retain strict status, token, schema, and identity checks and be covered by a real cold launch.
- A stale package commonly returns an older product/workspace identity while the checkout source and Rust unit tests are current. This is runtime provenance drift, not proof that the validator should accept both names.
- Build artifacts and stale runtime backups belong under the project ignored runtime directory, with clear names; never mass-kill unrelated WebView2 processes.

## Evidence Checklist

- [ ] Raw response captured from the exact owned port.
- [ ] Rejection layer identified.
- [ ] Checkout identity and bundled identity compared.
- [ ] Fresh current wheel/runtime staged under project boundary.
- [ ] Module path verified in isolated bundled interpreter.
- [ ] Provenance rechecked after final EXE build.
- [ ] Current-tree cold launch passed.
- [ ] WebView page and semantic interaction separately verified.
- [ ] Upload/dispatch/retry/replay/restart gaps explicitly recorded.

See `references/stale-bundle-readiness.md` for the reusable diagnostic recipe and evidence shape.

## Pitfalls

- Do not accept a legacy identity merely to turn readiness green.
- Do not trust a successful `cargo build` until the packaged backend source is read back.
- Do not trust a pre-build symlink or copied package after Cargo/Tauri packaging runs.
- Do not call a native error dialog, HTTP `200`, or Chromium result a Tauri WebView acceptance.
- Do not use real user vaults, `E:\`, credentials, or global Hermes state for the probe.


## 合并来源: desktop-build-verification (2026-08-21 合并优化)

---
name: desktop-build-verification
description: "Verify desktop builds across Rust+Python runtimes."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [windows, linux, macos]
metadata:
  hermes:
    tags: [desktop, build, verification, tauri, electron, multi-runtime, smoke]
    related_skills: [sleep-mode, python-testing, project-data-boundary, agent-workflow-fortress]
---

# Desktop Build Verification (Multi-Runtime)

## When to Use

- You need to verify the desktop build chain of a project that spans multiple language runtimes (Rust Tauri/Electron shell + Python backend)
- A sleep-mode cron cycle needs a bounded "browser/Tauri smoke" or "desktop build health" verification task
- You need to prove a desktop bundle compiles, builds, tests pass, and the packaged runtime is importable — all in one read-only cycle
- Before a release/CI exact-SHA gate to confirm the build chain is intact

Do NOT use this skill for:
- Pure Python projects with no desktop shell
- Build tasks that involve commit, push, merge, or release
- Installing new development dependencies or modifying the build chain

## Protocol

### 1. Toolchain Discovery

Inventory each language runtime and build tool before running commands. Record versions in evidence. Probe every command required by the repository's actual desktop gate **before** spending time on the full suite—especially Rust components that are separate from `cargo` itself:

```bash
rustc --version && cargo --version
rustfmt --version          # required when CI/release runs cargo fmt --check
cargo clippy --version     # only when the repository gate requires Clippy
node --version
npx tauri --version        # or electron --version
playwright --version       # if browser testing is needed
```

A missing optional tool degrades the pass to PARTIAL. A missing tool is BLOCKED when the repository or release contract names its command as required; do not run all expensive gates first and discover the unavailable formatter at the end. For a rustup-managed toolchain, the normal repair is `rustup component add rustfmt` (or `rustup component add clippy`), but this mutates the shared toolchain and therefore requires whatever machine/global-state authorization applies in the current task.

### 1a. Separate project-wide Linux coverage from Windows desktop prerequisites
A GitHub Actions job using `runs-on: ubuntu-latest` proves that the repository has a hosted Linux verification lane; it does not by itself prove that a Windows developer must install WSL. Audit the whole project as two independent axes:

| Axis | Typical evidence | What it proves |
|---|---|---|
| Linux application lane | hosted Ubuntu or local Linux/WSL2 run of Core, KB, integration, lint, wheel, and browser gates | Linux dependency and browser compatibility |
| Windows desktop lane | native MSVC Rust/Tauri/WebView2/NSIS and Windows runtime smoke | Windows packaging, process lifecycle, and installer behavior |

A complete project-level report must state both axes separately. For a Windows Tauri target, verify the native MSVC Rust toolchain, Cargo, Node/Tauri CLI, and Windows SDK/Visual Studio prerequisites, then run `cargo check --locked` followed by `cargo build --locked` from Windows. If both succeed and the project’s Windows CI/build job is green, classify WSL2 as optional for local reproduction of the Linux lane or Linux packaging—not as a fix for a browser/test failure. If native Windows linking fails, investigate MSVC/Windows SDK first; WSL2 cannot replace Windows desktop evidence.

### 1b. Windows WSL2 custom-distro installation and verification
When the user explicitly wants the Linux lane stored outside the system/user drive, distinguish the Windows-managed WSL engine from the distro data. Check `wsl.exe --status`, `wsl.exe --version`, `wsl.exe --list --verbose`, the target directory, and free space before mutation. After an elevated `wsl.exe --install --no-distribution` (reboot only with user approval), use the current CLI's supported location form, for example:

```powershell
wsl.exe --install --distribution Ubuntu-24.04 --location "D:\\All projects\\OS configuration\\wsl2\\Ubuntu-24.04" --version 2 --no-launch
```

Verify `wsl.exe --status` reports default version 2, `wsl.exe --list --verbose` reports the distro at version 2, and the target directory contains the distro VHDX. Do not claim the distro is ready until first-launch UNIX user initialization completes. Linux password prompts intentionally do not echo characters or `*`; explain this before asking the user to type, and never enter or request the password. A stopped, registered distro is installed but not yet initialized; a running distro after first launch is initialized evidence.

### 2. Compile Check Before Full Build

For compiled components (Rust, C++, Go), start with a lightweight type-check that resolves dependencies without producing a binary:

```bash
cd desktop/src-tauri && cargo check
```

Only after check passes, do the full build:

```bash
cd desktop/src-tauri && cargo build
ls -la target/debug/*.exe    # record binary path and size
```

**Distinction:** `cargo check` = dependency + type correctness only. `cargo build` = actual binary. Record which level was reached in evidence.

### 2a. Windows temporary-directory and bundle path control

Before native Rust/Tauri or NSIS commands from Git-Bash/MSYS, create an ignored project-local temp directory, convert it with `cygpath -w`, and export **both** `TMP` and `TEMP` to that native path. Do this before diagnosing compiler or bundler errors: an inherited/deleted Windows temp root can make Rust fail before product compilation, and a deeply nested bundled-runtime path can fail only during NSIS packaging. Preserve packaged runtime files and distinguish `cargo check`, binary build, NSIS bundle, and installed lifecycle as separate evidence; do not delete resources or alter product packaging to mask a path-boundary failure. See [`references/windows-tauri-temp-and-nsis-hygiene.md`](references/windows-tauri-temp-and-nsis-hygiene.md) for the reusable recipe and failure classification.

### 2a.1. NSIS runtime-resource closure

A successful Rust release binary and a Python import smoke do not prove that NSIS can package the staged runtime. Before bundling, enumerate the staged `site-packages` tree for generated frontend/proxy output, special characters, and Windows-long paths. If a dependency ships a clearly unused server/UI subtree, prove that the desktop imports and product paths do not reference it, then encode a narrow, reproducible exclusion in `prepare_bundle` (not an ad-hoc deletion after staging). On Windows, use extended-length paths only for cleanup of the exact project-owned generated subtree. Re-run runtime imports, the real Tauri/NSIS bundle, and installed lifecycle after the exclusion. Never classify a manual deletion or a successful `cargo build` as installer evidence.

### 2a.2. NSIS MAX_PATH (260-char) failure and CI cache-key traps

When `desktop-build` fails with `File: failed opening file "<path>"` + `Error in script "...installer.nsi" on line NNNN -- aborting creation process`, the file usually EXISTS — makensis cannot open it because the expanded path exceeds 260 chars (Windows MAX_PATH). A repo/checkout-dir rename that adds even a few characters can push a formerly-fine bundle over the line, and the failing file can differ run to run.

- **Junction to a short path does NOT fix it**: tauri/makensis resolves junctions back to the real path (log still shows `D:\a\<repo>\<repo>\...`).
- **`actions/checkout` `path: k` makes it WORSE**: the GitHub workspace is already two levels deep (`D:\a\<repo>\<repo>`), so a checkout subdir adds a third segment.
- **The fix is to shorten the resource tree itself** — rename the deep staging dir (e.g. `.hermes/desktop-runtime-v1` → `.hermes/rt`) and update every reference (tauri.conf.json resources, ci/release workflow destinations, release_inject_identity default, Rust and Python test paths). Verify final path length `< 260` programmatically before pushing.
- If the job sets `defaults.run.working-directory` to a not-yet-existing path, the step that creates it fails too — pin that one step to `working-directory: ${{ github.workspace }}`. `actions/cache`/`upload-artifact` `path` is relative to workspace, while explicit step `working-directory` overrides the job default; keep all three consistent.
- **restore-keys prefix must precede the hash**: key `${{ runner.os }}-cargo-${{ hashFiles('Cargo.lock') }}-suffix-vN` needs fallback `${{ runner.os }}-cargo-`; a `-suffix-` prefix never matches (hash sits between) and the fallback is silently dead.
- **Never merge cache keys across build profiles**: `cargo test` (debug) and `tauri build` (release) with one shared key = last-writer-wins mutual overwrite, zero speedup. Keep separate `-fast-` / `-build-` keys with a common prefix fallback.
- **Cache the uv wheel cache** (`.hermes/cache/uv-desktop`) in CI cache paths — `prepare_bundle` pip install drops from 10+ min to seconds after first fill.
- A single `installer-lifecycle` failure `did not exit after WM_CLOSE` at 15s on a slow runner is usually a timeout flake — bump `WaitForExit` to 30s and rerun before debugging the close handler.

Full recipe and log signatures: [`references/nsis-maxpath-and-ci-cache-keys.md`](references/nsis-maxpath-and-ci-cache-keys.md).

### 3. Per-Runtime Unit Tests

Each runtime's unit tests are independent and don't require the full binary:

```bash
# Rust
cargo test --lib

# Python — use project venv, not arbitrary python3
.venv/Scripts/python.exe -B -m pytest -x --no-header -q

# JS (if applicable)
npm test
```

### 4. Bundled Runtime Entry Smoke

If the desktop carries a packaged Python/Node runtime, verify it directly without triggering the full installer build:

```bash
# Python bundled runtime — -I flag activates isolation mode
.hermes/desktop-runtime-v1/runtime/python/python.exe -I -c \
  "import app.runtime_entrypoint, fastapi, uvicorn; print('bundled runtime imports passed')"
```

This is the cheapest packaging smoke available — faster than any CI/MSI build.

### 5. Static Frontend Asset Integrity

Verify the minimal frontend assets exist with measurable byte counts:

```bash
ls -la desktop/bootstrap/
wc -c < desktop/bootstrap/index.html
```

For Tauri projects, the frontend dist directory is declared in `tauri.conf.json` → `build.frontendDist`.

When you VENDOR minified client-side JS into the Python wheel (e.g. PDF.js) served from a static asset route, expect three distinct CI gates to fail on the first exact-head run: (1) lint `missing-final-newline` on the downloaded minified files, (2) a packaging test asserting the exact `package-data` string, and (3) browser-smoke console pollution from eagerly initializing the worker on page load. Fix all three locally before pushing, and verify the real browser smoke locally. Also beware the stale-server trap: killing the `runtime_entrypoint` parent can leave the uvicorn child alive on the port + DB lock, so the OLD code keeps serving (route returns 422 / restart says "database operator requires the app to be offline") — find and `taskkill /F /PID` the LISTENING pid. Full recipe: [`references/vendored-js-in-wheel-ci-gates.md`](references/vendored-js-in-wheel-ci-gates.md).

### 6. Windows desktop data-root readback

For Tauri/WebView2 on Windows, proving the Python backend `COGNITIVE_DATA_DIR` is project-local is not enough: WebView2 can maintain a separate profile. Set the Tauri window builder's `.data_directory(runtime.data_dir.clone())` (or the equivalent resolved project root) before building the window. After a cold launch, inspect only the exact shell process you started and its child tree; require every WebView2 child command line to contain `--user-data-dir=<allowed project runtime root>`. If an old WebView2 tree is still alive, close only the exact owned shell PID tree, then rebuild/launch once and repeat the readback—never mass-kill `msedgewebview2.exe`.

### 7. Cold-launch and native UI acceptance

A successful build is not a desktop acceptance result. For a Tauri/WebView2 shell, run a cold launch and inspect the exact process tree you started:

1. If an old owned shell/WebView2 tree exists, close only that exact shell PID tree; never mass-kill `msedgewebview2.exe`.
2. After launch, discover the backend's actual loopback port from the owned backend child environment or readiness signal; do not assume a fixed port across restarts.
3. Require every WebView2 child command line to contain `--user-data-dir=<allowed project runtime root>` and record the exact readback.
4. Enumerate the native window and walk its UIAutomation tree. Prefer `element_index`/`element_token` clicks over guessed coordinates; after every click, take a fresh UIA snapshot and verify the resulting page/state. A driver result of `unverifiable` is not acceptance evidence by itself.
5. Exercise the real UI state machine with an isolated fixture: pending → failed → retry/pending → delivered with a durable receipt; refresh/replay must not recreate dispatch or retry controls.
6. Close the native shell normally, verify its old backend port is unavailable, relaunch, rediscover the new port, and read back the same persisted job/delivery/receipt state.

If the embedded Computer Use MCP session is stale, use the installed `cua-driver` CLI as the same driver rather than changing the test target: declare a new session with `cua-driver call start_session`, then use `get_window_state`, `click`, and post-action `get_window_state` readback. Keep screenshots and traces under the project's ignored evidence directory. A concrete Windows/Tauri recipe is in [`references/tauri-webview2-native-acceptance.md`](references/tauri-webview2-native-acceptance.md).

### 7a. Native Tkinter / Python Desktop UI Smoke

For a Python/Tkinter desktop artifact, a successful `py_compile` or self-test is not enough. Start the real GUI with a project-local fixture path, verify the titled window exists, inspect the rendered layout with Computer Use or UIAutomation, and close that exact window normally. Keep the fixture under `.hermes/task-runtime/`; do not open a real user log during a smoke test. Native `tk.Frame` and `tk.Label` options do not always accept ttk-style values (for example, tuple-valued `pady` can raise `bad screen distance`), so GUI startup is a required compatibility check after styling changes.

Use this evidence split:

| Layer | Evidence |
|---|---|
| `python_compile` | source and tests compile |
| `logic_self_test` | parser/tailer behavior passes without GUI |
| `native_gui_launch` | actual window title, layout, and controls are visible |
| `native_gui_close` | exact owned window exits cleanly |

A screenshot of the initial empty state proves layout only; it does not prove real usage parsing. Use a synthetic project-local fixture for data-state screenshots and never paste real prompt/auth/log content into evidence.

### 7b. OSS-first LLM usage monitor reconnaissance

Before building or restyling a token/usage monitor, perform OSS and data-source reconnaissance. Search current projects by capability, then verify repository metadata, license, platform, release artifacts, supported clients, and the actual parser/source files. Treat README claims as leads, not evidence. A large generic log file does not prove it contains provider usage: run a secret-safe shape probe that reports only file names, JSON/plain counts, field names, and usage-record counts. Never print raw prompts, responses, credential values, OAuth data, or token values during diagnosis. Keep `exact usage`, derived totals, quota estimates, and `unknown` records visibly separate. See [`references/llm-usage-monitoring-oss-recon.md`](references/llm-usage-monitoring-oss-recon.md) for the reusable project comparison and staged architecture decision.

If the requirements include charts, session timelines, themes, tray/status-bar behavior, and multiple client adapters, stop expanding a Tkinter table and evaluate a Tauri 2 + React/TypeScript shell with a local parser/index service. Do not add a proxy or credential scan merely to obtain metrics from an OAuth client; live quota polling is a separate, explicitly consented capability.

### 7c. Real-time multi-provider usage-monitor acceptance

For a desktop usage monitor that claims GPT / DeepSeek / Kimi visibility, validate the complete path—not only the parser or empty shell:

1. Use a project-local, non-secret JSONL fixture containing one explicit usage record per provider. Include `model`, `input_tokens`/`prompt_tokens`, `output_tokens`/`completion_tokens`, and `total_tokens`.
2. Start the actual Tauri window, verify the title and initial explicit-consent state, then enter the fixture path through the UI and click the monitoring control. Do not open a real provider log for a layout smoke.
3. Require the rendered state to show provider cards, input/output totals, request count, `LIVE · EXACT USAGE` (or the equivalent), and a trend/bar state. An empty-state screenshot proves layout only.
4. Verify auto-refresh only starts after the user starts monitoring; a bounded interval such as three seconds is acceptable. Append a new fixture record and confirm the next refresh changes the aggregate without restarting the shell.
5. Keep provider usage, quota snapshots, estimates, and unknown records separate. Do not read provider credentials or enable quota network polling just to make the dashboard non-empty.
6. If the frontend is Vite and the Tauri Rust target is inside the same tree, exclude `src-tauri/**` from the Vite watcher. Otherwise Windows can raise `EBUSY` while Rust rebuilds DLLs under `target/debug`.
7. Record Rust unit tests, `cargo check`, frontend build, native launch, data-state screenshot, refresh readback, and normal close as separate evidence. Do not report "desktop works" from a successful compile alone. See [`references/realtime-usage-monitor-desktop.md`](references/realtime-usage-monitor-desktop.md) for the fixture and Windows smoke recipe.

8. Separate historical and live usage semantics. A full-directory scan is a historical aggregate, not proof of calls made during the current monitoring window. On monitor start, capture a baseline snapshot and make the default view show only the delta from subsequent scans; expose historical totals behind an explicit toggle. Label both views in the UI and keep provider cards, model rows, request counts, and trend data on the same basis. Reset or rebase the baseline on source changes, truncation, rotation, or monitor restart.

9. Keep local and cloud measurements separate. Explicit token fields in local session/JSONL/API response logs may be marked `exact`; absent fields must remain `unknown`. Account quota, balance, rate limits, or provider dashboard snapshots are cloud aggregates and must not be presented as request-level token usage. Cloud polling is opt-in and must not require reading or persisting credentials for a local-first monitor.

10. When a user reports "only provider X was called but several providers appear," audit the time window and source scope before changing provider classification: inspect whether the UI is showing historical files or a smoke fixture, verify the selected paths, and reproduce with a single-provider fixture plus an append-after-start refresh. Do not infer a provider call from a provider name alone.

See [`references/realtime-usage-monitor-desktop.md`](references/realtime-usage-monitor-desktop.md) for the fixture and Windows smoke recipe. For parser de-duplication, historical/live delta semantics, tray lifecycle, Apple-inspired local UI, and Windows Vite/Tauri input hardening, use [`references/desktop-usage-monitor-hardening.md`](references/desktop-usage-monitor-hardening.md).

### 7d. Windows Electron PTY handles and locked package outputs

For Electron/Hermes on Windows, a clean Git checkout and absent `.git/index.lock` do not prove that a directory can be renamed. A restored PTY child can keep the legacy project directory as its CWD and cause native `os.rename()` to return `WinError 32`. Diagnose process roles and descendant CWDs, move Desktop and helpers to a stable Hermes Home CWD, track PTY `launchCwd`, release only matching local sessions through graceful shell exit, and re-probe the native rename before reporting success. Never use `taskkill /F` or `TerminateProcess` as the normal release path.

If Electron Builder cannot clean a locked `release/win-unpacked`, preserve the active output and package into a fresh ignored output root with `--config.directories.output=release-verify`; verify the executable and identity readback, then remove only that fresh verification output. Do not conflate targeted tests, typecheck/build, full platform suites, packaged artifact evidence, and real cold-launch/rename evidence. The detailed Windows recipe is in [`references/windows-electron-pty-handle-archive.md`](references/windows-electron-pty-handle-archive.md).

### 7f. Borderless + transparent Tauri window shell

When building a portable Tauri 2 component with `decorations: false` and
`transparent: true` (Liquid Glass / HUD style), three traps recur: (1) the
window cannot be dragged unless you add `data-tauri-drag-region` in the HTML
AND `core:window:allow-start-dragging` in `capabilities/<name>.json` for every
window in scope; (2) `tauri.conf.json` `build.frontendDist` is resolved relative
to `src-tauri/`, so a frontend at `<project>/web/` must be `"../web"` — otherwise
the packaged EXE embeds empty assets and opens blank while the same `web/` serves
fine over `http.server`; (3) a transparent/borderless window often hides web
content from the AX/UIA tree, so an empty capture is a verification gap, NOT
proof of a white screen — confirm via a browser harness, a desktop screenshot,
and the backend projection, never from an empty AX tree alone. Full recipe and
symptom patterns: `references/tauri-borderless-transparent-shell.md`.

### 7h. Tauri 2 WebView blank/transparent-window debugging

Symptom: the Tauri window opens as a transparent border ("透明框"), pure black,
or empty — the user sees no menu/content, while the frontend serves fine in a
plain browser. **Diagnose with WebView2 remote debugging first** — never trust
a window screenshot alone:

1. **PrintWindow cannot capture WebView2 (Chromium GPU-rendered) content** — it
   returns a pure-black/empty image that looks like a blank screen but is only a
   capture artifact. `CopyFromScreen` captures the real desktop, but for a
   `transparent: true` window it shows whatever is BEHIND the window (often the
   chat app), not the page. Neither proves what the WebView rendered.
2. **Authoritative check — WebView2 CDP**: launch the EXE with
   `WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS="--remote-debugging-port=9222 --remote-allow-origins=*"`,
   then `curl http://127.0.0.1:9222/json` and read each page's real `url`.
   - `about:blank?api=...` → navigation bug (root cause #1)
   - `http://localhost:1420/...` (devUrl) with nothing listening → wrong build mode (root cause #3)
   - `http://tauri.localhost/index.html?...` → assets embedded correctly; if still empty, check fetch/CORS (root cause #2)
3. Then verify the rendered page via CDP WebSocket
   (`websocket.create_connection(webSocketDebuggerUrl)`): `Runtime.evaluate`
   `document.body.innerText` + `Page.captureScreenshot` for a true rendering
   proof. With no vision model, OCR the CDP PNG with tesseract.

Three root causes that produce this symptom and their fixes:

- **about:blank navigate trap**: calling `window.navigate()` on a Tauri
  `WebviewWindow` inside `setup()` navigates from `about:blank` (the URL is not
  loaded yet) and permanently strands the page on a blank URL. Fix: register
  the Tauri **Builder**-level hook
  `tauri::Builder::default().on_page_load(move |webview, payload| ...)` and
  inject query params only on `PageLoadEvent::Finished`, skipping `about:`
  URLs and pages that already carry the param (avoid navigate loops). Note
  Tauri 2's `on_page_load` is a builder method (consumes `self`) on
  `Builder`/`WebviewWindowBuilder` — it does NOT exist on `Webview`/
  `WebviewWindow` instances.
- **tauri.localhost CORS**: on Windows, the WebView2 frontend Origin is
  `http://tauri.localhost` (not `127.0.0.1`). A backend CORS allowlist that
  only admits loopback IPs + `localhost` returns 403 → the frontend fails
  closed to OFFLINE. Fix: also allow `.localhost` suffixes (RFC 6761 reserved
  TLD). Verify: `curl -H "Origin: http://tauri.localhost"` → 200, an external
  origin still 403.
- **cargo build --release vs cargo tauri build**: a bare `cargo build
  --release` can embed the dev server URL — the page URL becomes
  `localhost:1420` while nothing listens there → blank. Use the Tauri CLI
  (`cargo tauri build --no-bundle`) so `build.frontendDist` assets are embedded
  and the page loads from `http://tauri.localhost/index.html`. Confirm via CDP
  `/json`, not by assuming the binary is self-contained.

Also remember: an "数据源离线（OFFLINE，不加载假数据）" empty state is the
frontend's fail-closed design (no fake data when the backend is unreachable),
and empty counters (0 projects) are truthful — not a rendering bug.

### 7h.1. External sidecar recovery and portable Windows build

For a production Tauri/WebView2 shell that embeds frontend assets but depends
on a separately managed loopback sidecar, verify the product's own initial-GET
retry, true EventSource backoff, named SSE events, multi-client connection
counting, null-until-observed heartbeat/writer freshness, and recovery after a
real sidecar stop/restart while the app PID remains unchanged. If the project
uses a portable Windows toolchain, keep sysroots and patched build dependencies
inside the ignored runtime root, use temporary Cargo path patches only for the
build, then prove `Cargo.toml` and `Cargo.lock` are restored. Relaunch without
CDP and verify the debug/static ports are closed. Full protocol:
[`references/tauri-sidecar-recovery-and-portable-build.md`](references/tauri-sidecar-recovery-and-portable-build.md).

### 7i. Grid-span collapse (cards squeezed into ~60px vertical strips)

Symptom: the page loads (menu/sidebar render) but the central dashboard cards
collapse into narrow vertical strips (~60px, one grid column), CJK glyphs stack
one per line, and cards overlap — while `grid-template-columns:
repeat(12, minmax(0, 1fr))` is correct and the viewport width is fine. Root
cause: the grid's **direct children carry no span class** (`grid-column: auto`
→ every child takes exactly 1 column ≈ 60px). This happens when a render
function emits `<div class="wl-card">` without the `wl-col-X` classes the CSS
already defines — a refactor dropped the span classes.

Diagnose via WebView2 CDP: `Runtime.evaluate` reading
`getComputedStyle(child).gridColumn` (all `auto`) and
`child.getBoundingClientRect().width` (all ≈ one column) on
`document.querySelector('.wl-grid').children`. Before rebuilding, validate the
fix by injecting a `<style>` via CDP (instant feedback, no rebuild).

Fix in CSS (not by patching every render call): a fallback rule after
`.wl-grid` —
```css
.wl-grid > .wl-card, .wl-grid > .wl-grid, .wl-grid > .wl-state-note { grid-column: span 6; }
.wl-grid > .wl-global-bar, .wl-grid > .wl-kpi, .wl-grid > .wl-cols-2, .wl-grid > .wl-state-note { grid-column: 1 / -1; }
```
(semi-width for ordinary cards, full-width for self-gridding blocks). Then
rebuild with `cargo tauri build --no-bundle` so the edited CSS is embedded and
re-verify widths via CDP (`wl-global-bar=911px`, `wl-card=448px`, …).

Full session trace with the exact CDP recipe, symptom→root-cause table, and
the toolchain (Rust+MSVC+SDK env for PATH-with-spaces hosts):
[`references/tauri-webview-blank-debugging.md`](references/tauri-webview-blank-debugging.md).

### 7i.1. Whole render-file component CSS missing (broader than span collapse)

A broader failure than missing span classes: a refactor ships a NEW render
file (`render-v3.js`) that emits `<div class="wl-cols-2">`, `wl-global-bar`,
`wl-drift-grid`, `wl-proj-row`, `wl-kv-label`, `wl-section-title`, … but NONE
of these classes are ever defined in any CSS — the JS landed without its
stylesheet. Symptom: blocks whose classes already exist render fine, while
others collapse/overlap/stack CJK glyphs (e.g. the Token/CI two-column block
collapses because `.wl-cols-2` is undefined). This survives span-class
restoration and is a DIFFERENT root cause.

Audit in ONE pass — don't fix class-by-class. Extract every `class="…"`
token from the render JS, extract every `.className` selector from all CSS,
diff the two sets. Here `render-v3.js` used 51 classes, 30 missing (20 real
after discounting `${…}` JS template vars). Write the missing component CSS
in one batch, rebuild, re-verify. `git log -S <className>` points at the
commit that added the JS — usually the same commit never added the CSS.

### 7i.2. Frontend visual restyle — reuse a mature design system, don't hand-tune

When the user rejects the palette/spacing as "难看 / 乱 / 太紧凑 / 还是不对"
after the layout is fixed, STOP nudging individual tokens and restyle against
a proven design system instead. The user's stated preference (and their
"去多找几个牛逼的模板套" / "别一顿瞎分析又修不好" correction) is: load
`popular-web-designs`, pick Linear / Vercel / Apple templates, and offer
switchable dark+light themes — not hand-tune one's own CSS across many
rounds. Apple "Liquid Glass" is the WRONG default on Windows: `transparent:
true` + `backdrop-filter` blur is unreliable in WebView2 (semi-transparent
cards bleed into the desktop / behind-window), so a solid canvas + one
restrained accent reads premium where glass reads broken. Restyle = rewrite
the token file (canvas/surface/text/border/radius/shadow) in one batch, drop
the backdrop-filter, keep the accent singular (Linear `#08090a` + indigo
`#5e6ad2`; Vercel `#ffffff` + `#171717` shadow-as-border; Apple `#000000` +
`#0071e3`), and provide a theme toggle rather than a single fixed look.

### 7i.3. Collected-but-not-projected data (backend snapshot wiring gap)

When the UI renders real cards but specific fields stay `null`/UNKNOWN
(e.g. `git.localSha=null`, `coverage=null`, `transport=UNKNOWN`) even though
the collector DID capture the value, the data was written to the store but
not passed into the snapshot assembler. For the WORK-LAB Observer sidecar:
run `durable_worker.py --once --project-root … --runtime-root … --project-id
work-lab` to register the project + run collectors (this is what fills an
all-empty store — 25 tables, 0 rows means collectors never ran, not a render
bug); then check each snapshot field's source: `build_v3_snapshot` calls
`build_snapshot(...)` without `git_state=`, so `git.localSha` stays null even
though `collect_git_ci` wrote `head_sha` into `source_quality`. The generic
lesson: when a collector writes to table A but the projection reads table B,
add a read path (e.g. `list_source_quality()`) and thread it through the
assembler — don't assume "collected" implies "projected".

### 7e. Deterministic native close lifecycle debugging

When the Windows NSIS gate reports `desktop shell did not exit after WM_CLOSE`, do not treat a watcher timeout or a single rerun as proof of failure or success. Read the exact run's failed log, identify the `verify_nsis_install.ps1` line and owned PID/window handle, and compare the shell close handler with the native event semantics.

For a `CloseRequested` callback, the verified Tauri pattern is
`WindowEvent::CloseRequested { api, .. }`, followed by `api.prevent_close()`,
explicit `window.destroy()`, and `window.app_handle().exit(0)`. The
`prevent_close` guard prevents the explicit native destruction from re-entering
the close path; the existing `ExitRequested` hook remains the single backend
child-process reaper. Do not add a delayed thread or duplicate kill path, and
do not replace the graceful assertion with a force-kill fallback.

The earlier `prevent_close + app.exit`-only variant can leave the native shell
alive after `CloseMainWindow()` on the real NSIS runner; static Rust contracts
alone will not catch that. Lock the behavior with a source regression contract,
then run Rust format/unit tests and the real Windows NSIS lifecycle smoke. A
fix is not complete until PR exact-head CI reports `desktop-build`,
`installer-lifecycle`, and `a0-gates` successful; merged-main CI remains a
separate evidence layer. Do not treat watcher exit 124 or deprecation
annotations as conclusions.

See [`references/native-close-lifecycle-debugging.md`](references/native-close-lifecycle-debugging.md) for the reusable evidence sequence and close-handler contract. See [`references/readiness-identity-and-child-process-ci.md`](references/readiness-identity-and-child-process-ci.md) for readiness payload drift and separate-process CI configuration.

### 7g. Readiness payload identity, HTTP framing, and child-process test configuration

A readiness HTTP `200 OK` is not sufficient evidence when the desktop shell performs a second payload validation. Verify the complete contract: status line, JSON schema, exact product/workspace identity, launch-token behavior, and the Rust-side acceptance predicate. If the service returns `200` repeatedly but the shell reports `readiness timed out`, inspect the body validator and raw HTTP framing before changing identity strings or timeout values. Uvicorn/ASGI responses may use `Transfer-Encoding: chunked`; a minimal native probe that passes the raw body directly to JSON deserialization will reject an otherwise valid 200 response. Decode the transport framing (or use a real HTTP client), trim only framing/whitespace, then apply the existing closed-schema and exact identity validator. Add a unit fixture for a chunked JSON response and retain `deny_unknown_fields`/exact product checks; never broaden the validator to accept stale identities merely to make CI green.

**Diagnostic order for repeated `200` + timeout:** before changing polling, timeout, or response parsing, capture a secret-safe raw response from the exact owned loopback port using the same request shape. Record only status line, response headers, byte count, transfer/content framing, and a redacted or schema-only body shape; never print launch tokens or credentials. Compare this with the shell's read loop and predicate. Only then patch a proven framing mismatch, and add a regression fixture for the exact response form. Do not stack speculative fixes for chunked encoding, keep-alive, partial reads, or identity drift without first proving which layer rejects the response.

Readiness polling must also respect the server's ordinary-read rate budget. A 100ms loop over a 30-second timeout can issue roughly 300 requests and exceed a 200-per-minute limiter before a slow migration completes. Use a bounded interval that stays below the configured budget (for example 500ms, with margin for retries and other startup reads), or a retry/backoff schedule with the same budget calculation. Keep the launch token and loopback restriction unchanged; do not disable global rate limiting for convenience. Test both: repeated valid 200 responses remain below the rate limit, and invalid payloads still fail closed.

When the shell displays an error dialog after Core returns repeated `200`s, classify the result as **readiness acceptance failed**, not Core startup failed. Close only the owned shell/process tree before rebuilding; preserve the exact log and do not mass-kill shared WebView2 processes.

**Raw-response-first rule:** If the shell still times out after repeated 200 responses, stop stacking polling, HTTP-version, framing, timeout, and socket-read changes. Reproduce the exact migration → Core startup sequence in a fresh project-local data root with a known test-only launch token, then capture the raw response from the exact loopback port using `curl --noproxy '*' --http1.1 -i` and the matching token header. Record only status, headers, byte count, transfer/content framing, and the readiness JSON shape; never print production tokens or credentials. Compare those bytes with the Rust request, read loop, and predicate before changing code. A parser fixture is useful only after the real response framing is known. Rebuild and cold-launch the current executable after each evidence-backed change; a passing unit test or native error dialog does not prove WebView readiness.

Keep the readiness identity contract in one product-owned source and update the Rust protocol test whenever the display/product naming contract changes. Preserve compatibility names only where the contract explicitly requires them; do not broaden the validator to accept stale identities merely to make CI green.

**Chunked-body fixture hex length:** the Rust readiness test may embed a raw HTTP chunked response where the chunk-size prefix is the HEX byte length of the payload (e.g. `"63\r\n{...}\r\n0\r\n\r\n"`). Growing the product string (e.g. `ArcheAxis Workspace` → `ArcheAxis Learning Workspace`, payload 99→108 bytes) requires the prefix to become `6C` — forgetting this panics the test at the prefix position (`readiness_decodes_chunked_http_json_before_validation`). Compute with `len(payload.encode('utf-8'))` → `f"{n:X}"`, and re-run that single test (`cargo test --lib backend::tests::<name>`) after the edit. Also: the `patch` tool double-escapes escape sequences in Rust string literals (turns `\r\n` into `\\r\\n`), corrupting the fixture — rewrite escape-heavy Rust literals with execute_code/python, then verify with cargo test.

**Bundled-runtime provenance gate:** `cargo build --release` compiles the Rust shell but does not prove that Tauri resources were staged from the current Python source. Keep these layers separate: (1) build the current wheel, (2) run `prepare_bundle` into a project-local ignored runtime, (3) verify the staged `app/workspace/router.py` or equivalent package contains the current readiness identity and no stale identity, (4) run the repository's actual Tauri bundling command (`npm run tauri -- build ...` or the documented equivalent), and (5) inspect the copied `target/.../runtime` package before cold launch. If a shell gets repeated `200 OK` responses but fails exact identity acceptance, inspect the bundled package identity before changing the validator or stacking socket/timeouts. A manually replaced `target` runtime is only a local diagnostic; the durable fix is to make the documented bundle-preparation step feed the resource path consumed by Tauri and then verify the full bundle command.

Python `pytest` fixtures do not configure a separate Cargo test process or the backend child it launches. For desktop lifecycle/installer smoke, inject test-only runtime settings explicitly in the GitHub Actions step environment, and keep dedicated rate-limit tests on their real enforcement path. Verify the child-process logs after the change; do not infer inheritance from the parent test process.

### 7k. Browser smoke for static JavaScript previews

For a browser-based frontend or mini-game, static/unit tests are not enough. Add a bounded local HTTP smoke against the current checkout, keeping it separate from production or human visual acceptance:

1. Resolve the canonical project runtime first (`process.execPath`/the repository's runtime wrapper), and make the server's cwd the package root. Do not classify a shell shim, wrong cwd, or missing package-manager executable as an application defect before this separation.
2. Bind only to loopback and use a project-local launcher. Verify the home page returns `200`, at least one declared CSS/JS asset returns `200`, an unknown path returns `404`, the expected page title/identity is present, and the browser console has no errors.
3. Read back the actual listener before trusting the browser tab; use the current port and stop only the exact server process after the smoke. Never reuse a stale screenshot or old listener as evidence.
4. Record this as `browser_static_smoke`, not as Android/device, Host, Photoshop, Jury, Evidence Card, production, or human visual evidence. A passing browser smoke proves current local rendering and routing only.

If the package manager invokes child scripts through a different Windows shell, verify executable resolution and cwd separately; use a known-good direct runtime invocation for the browser smoke rather than changing product code to hide an environment-only shim problem. The npm/Node wrapper-specific recipes remain in `windows-development-environment`.

#### 7l. Windows Tauri rebuild on a relocated tree: cargo config, windres path spaces, window-icon API

Rebuilding a Tauri 2 shell after relocating its tree (e.g. to `D:\All projects\...`) hits three reproducible Windows traps:

1. **`~/.cargo/config.toml` unescaped backslashes corrupt the config.** A `linker = "D:\All projects\..."` line is invalid TOML (`\A` is not a valid escape); `cargo` then dies with `could not parse TOML configuration` on EVERY command. Fix: double the backslashes (`D:\\All projects\\...`). Verify with `cargo metadata --format-version 1` before building.
2. **windres chokes on a `CARGO_TARGET_DIR` containing spaces** — `tauri-winres` fails with `cc1.exe: fatal error: <...>\out: No such file or directory` / `windres: preprocessing failed`. Fix: map the tree to a no-space drive with `subst X: D:\All projects\<app>` and export `$env:CARGO_TARGET_DIR = 'X:\src-tauri\target'` inside the build script before `cargo tauri build`. The physical path still contains spaces, but the build sees only `X:\...`. After a rustup reset (`no installed toolchains`), reinstall with the rsproxy mirror: `RUSTUP_DIST_SERVER=https://rsproxy.cn RUSTUP_UPDATE_ROOT=https://rsproxy.cn/rustup rustup install stable-x86_64-pc-windows-gnu`, then `rustup default stable-x86_64-pc-windows-gnu`; `rustup toolchain list` may still print `no installed toolchains` while `rustc --version` works — trust rustc.
3. **Tauri 2 window icon: config field rejected, Builder has no setter.** `tauri.conf.json` `app.windows[].icon` → schema error `Additional properties are not allowed ('icon' was unexpected)`. `Builder::icon` / `Builder::default_window_icon` do NOT exist in tauri 2.11.x (those methods live on `Context`). Correct approach:
   ```rust
   use tauri::Manager;
   tauri::Builder::default()
       .setup(|app| {
           if let Some(win) = app.get_webview_window("main") {
               win.set_icon(tauri::include_image!("icons/icon.png"))?;
           }
           Ok(())
       })
       .run(tauri::generate_context!())
   ```
   `include_image!` resolves relative to `CARGO_MANIFEST_DIR` (`src-tauri/`), so `"icons/icon.png"`, not `"../icons/icon.png"`.

**Verifying the window icon is actually set:** `GetClassLongPtr(hwnd, GCLP_HICON=-14)` returns 0 even when `set_icon` worked (class icon ≠ instance icon). Use WM_GETICON instead: `SendMessage(hwnd, 0x007F, ICON_SMALL=0 or ICON_SMALL2=2, 0)` returns the instance icon; extract with `System.Drawing.Icon::FromHandle`, then pixel-analyze. A real icon has multiple quantized colors; a pure-white/1-color image means the icon asset itself is broken/empty.

**Broken icon assets:** if all icon files (exe-embedded, `src-tauri/icons/*`, `launch/*.png`) analyze as pure white, the icon source was empty at build time. Regenerate from the app's official SVG (favicon/logo) — cairosvg render of a white-fill variant + PIL composite on a brand-color rounded square + LANCZOS multi-size ICO. Quick exe-only swap without a full rebuild: `rcedit-x64.exe <exe> --set-icon <icon.ico>` (electron/rcedit releases). Full recipe + the DSH theme-token contrast lesson (dark themes invert `--brand-primary`; never hardcode `#fff` on it — use the theme's `--*-foreground`/`--*-contrast-fill` token): [`references/tauri-windows-rebuild-and-icons.md`](references/tauri-windows-rebuild-and-icons.md).

## 8. Layered Evidence Recording

Record each verification layer with a separate evidence key — never collapse into "build ok":

| Key | Meaning |
|---|---|
| `rust_cargo_build` | `cargo check` or `cargo build` result + binary path + size |
| `rust_unit_tests` | `cargo test --lib` results |
| `full_python_suite` | `pytest` results |
| `desktop_runtime_import_smoke` | bundled Python runtime import test |
| `bootstrap_frontend` | frontend static asset integrity |
| `tauri_cli` | Tauri CLI version |
| `head_unchanged` | confirmation that HEAD matches previous cycle |
| `working_tree` | git status clean/dirty evidence |

### 8. Pass/Fail Rules

- **GREEN:** All expected layers pass at their strongest level (build produces binary, all tests pass, runtime imports work)
- **PARTIAL:** One or more layers skipped due to missing optional tooling or dependencies — document each skip
- **BLOCKED:** `cargo check` fails, core tests fail, or bundled runtime path is declared but missing. Record exact error and stop

## Evidence Contract

When used inside a sleep-mode or autonomous loop cycle, append to `activity.jsonl` with each layer as a separate field under `evidence`:

### Two-axis and exact-SHA reporting

Always report native Windows desktop evidence and Linux/WSL application evidence as separate axes. A hosted Ubuntu CI lane proves Linux compatibility; it does not prove that WSL is installed, initialized, or required on a Windows machine. Conversely, a Windows Tauri/NSIS pass does not prove Linux dependencies. If WSL is present but lacks optional test dependencies, record it as a local reproduction limitation and use the hosted Ubuntu exact-SHA result for the Linux gate—never claim a local pass that was not run.

For Tauri projects with an intentionally minimal bootstrap, validate the configured `build.frontendDist` and the files actually present rather than assuming a React/Vite asset tree. A non-empty `index.html` can be the complete frontend contract when the project declares that architecture.

After implementation changes, the verification sequence is: local Rust/Python layers → wheel/package contents → documentation/index consistency → explicit commit/push → exact-SHA CI → structured PR status → merge only when the head SHA, checks, and mergeability all agree. Documentation-only commits still require exact-SHA CI: repository governance tests may assert that new handoff or feature documents are linked from the top-level README, not only from a subsystem document. If a post-push check fails, read the failed exact-SHA run log (for example with `gh run view <run-id> --log-failed`) before reporting status; distinguish the failed run from the previous successful SHA, patch the root cause, then push and re-check the new SHA. Watcher output and deprecation annotations are not substitutes for structured run conclusions.

For handoff-heavy desktop work, commit a concise repository-visible handoff under `docs/workflow/` with exact HEAD/branch/PR, implemented surface, resolved root causes, verification evidence, security/data boundaries, residual limitations, and the next maintainer sequence. Expose that handoff from both the subsystem documentation and the top-level README when governance tests treat README as the feature index. Never describe a pushed branch as merged, installed, signed, or published unless those separate evidence layers exist.

```json
{
  "evidence": {
    "rust_cargo_build": "archeaxis-desktop-shell v0.4.0 — binary 12.8 MB",
    "rust_unit_tests": "10/10 passed (0.01s)",
    "full_python_suite": "667 passed, 4 skipped (40.16s)",
    "desktop_runtime_import_smoke": "passed — bundled Python imports ok",
    "bootstrap_frontend": "intact — 157 bytes at desktop/bootstrap/",
    "tauri_cli": "tauri-cli 2.11.4 available"
  }
}
```

## Pitfalls

1. **Don't use the wrong Python.** The shell default `python3` may point to a different interpreter than the project venv. Always use `.venv/Scripts/python.exe` (Windows) or the project's declared Python path.
2. **Don't conflate check with build.** `cargo check` proving correctness is not the same as `cargo build` completing. A binary that compiled on the last full build may fail today due to a new dependency.
3. **Don't skip the bundled runtime smoke.** A green test suite doesn't prove the staged/bundled Python can import the app modules — only the direct import test does.
4. **Don't over-assume frontend build.** For Tauri projects with `frontendDist: "../bootstrap"`, a static HTML page is valid. Don't demand a full React/Vite build if the project deliberately ships a minimal bootstrap.
5. **Don't commit or push.** This skill is read-only verification. No source modifications should result from executing this protocol.
6. **Don't stream long-running progress.** Report one concise update at a bounded milestone; while a remote desktop job is still running, report only the remaining gate and its structured status instead of repeating watcher output.
7. **Don't test against a stale service.** After editing a static asset route or vendored JS, a leftover uvicorn child from a killed `runtime_entrypoint` parent keeps serving OLD code on the same port (a route edit may appear as 422; restart fails with "database operator requires the app to be offline"). Confirm the LISTENING pid on the port is gone before concluding your edit is wrong — kill it with `taskkill /F /PID <pid>` (never `//PID` in Git-Bash).
8. **Don't assume vendored minified JS passes the gate as-is.** Expect the three-part CI failure (final-newline lint, package-data string assert, browser-smoke console pollution from eager worker init) and fix all three before pushing — see `references/vendored-js-in-wheel-ci-gates.md`.
9. **Never delete the cargo `target/` cache before confirming the local MSVC toolchain is complete.** On a machine without a full MSVC/Windows SDK install (no `C:\Program Files (x86)\Windows Kits\10\Lib`, vswhere finds nothing), incremental builds work only because the cached build scripts don't need re-linking; deleting `target/` forces a full rebuild that fails (`link: extra operand` from Git's GNU `link.exe` shadowing in Git-Bash PATH; `rust-lld` also needs the SDK `.lib` files). Result: local Rust verification is permanently lost and falls back to CI only. Diagnose first: `where link` showing `C:\Program Files\Git\usr\bin\link.exe` (GNU link, not MSVC) + empty vswhere = no usable MSVC; keep the cache and rely on CI `desktop-fast`/`desktop-build` for Rust evidence.


## 合并来源: desktop-lifecycle-evidence (2026-08-21 合并优化)

---
name: desktop-lifecycle-evidence
description: "Use for desktop/WebView evidence separation."
version: 1.0.0
license: MIT
platforms: [windows, linux, macos]
metadata:
  hermes:
    tags: [desktop, tauri, webview, lifecycle, evidence]
    related_skills: [full-stack-absorption-verification, sleep-mode, project-data-boundary]
---

# Desktop Lifecycle Evidence

## Trigger
Use for desktop shell, Tauri/WebView, bundled runtime, or desktop failure/retry/replay verification.

## Core rule
Keep three acceptance rows separate: backend lifecycle (Core launch/readiness/shutdown), desktop process lifecycle (current executable/WebView2/child readiness and shutdown), and WebView product flow (real rendered UI action → real HTTP → persistence → reload/readback). A Rust test or `cargo test -- --ignored` can prove only backend lifecycle unless it explicitly drives a real desktop window.

## Procedure
1. Freeze branch, HEAD, tree, dirty ownership, and project-local runtime boundary.
2. Run ordinary Rust tests and explicitly intended ignored lifecycle tests; record exact command/counts.
3. Inspect for a runnable WebView harness. Ignored tests, mocked browser routes, and backend process tests are not WebView evidence.
4. With a harness, prepare/stage the current Python/runtime bundle before building or launching the desktop executable; `cargo build --release` alone does not refresh bundled runtime resources. Verify the staged identity against the current source contract and reject stale product/workspace identity. Use a fresh isolated data root and current executable; exercise launch → render → semantic action → real HTTP → persistence → reload/readback → shutdown.
5. After every WebView mutation, navigation, scroll, modal change, or asynchronous projection update, capture a fresh accessibility/SOM snapshot before using an element reference again. Element indexes and screen coordinates are ephemeral. A click result of `unverifiable` is not success; inspect the fresh rendered state and only record the semantic transition if it is visible.
6. Prove the product flow with a state ledger, not a button inventory: `upload`, `pending`, `job`, `dispatch`, `receipt`, `review`, `knowledge`, `reload/readback`, and any `failure/retry/replay` branch must each have a source-level or rendered-state observation. An intake rejection (for example DNS/address/port policy rejection) may be a valid controlled failure but is not automatically a retryable outbox job; do not claim retry/replay unless a durable failed job and its replay transition are visible.
7. Without a harness, preserve green backend evidence but mark WebView `partial`/`blocked`; create a bounded unblock task instead of rerunning the same backend test or claiming completion.
8. Ledger fields must remain separate: `backend_lifecycle`, `desktop_process`, `webview_click`, `durable_projection`, and `webdriver_acceptance`.

## Verification language
“Backend lifecycle passed” means Core only. “Desktop process readiness passed” requires the current executable and supervised child. “WebView click/readback passed” requires rendered UI interaction and persistence readback. Missing harnesses must remain partial/blocked.

## Native WebDriver route and overlay discipline
When a native WebDriver bridge is available, match the driver to the active WebView2/browser version exactly; a merely launchable driver with a warning is setup evidence, not a clean acceptance baseline. Create the W3C Tauri session against the current-tree executable and record both browser and driver versions. Treat navigation placeholders as non-delivered surfaces: if a rail entry renders a roadmap/unavailable page, locate the real action in the owning runtime page rather than forcing a hidden route element.

After every route change or asynchronous projection refresh, re-find the target element. Require a non-zero rectangle and inspect the native click error instead of retrying blindly. If WebDriver reports `element click intercepted`, inspect the named overlay, scroll the target into a centered viewport with `scrollIntoView({block: 'center'})`, re-find the element, and click again. This is still native WebDriver evidence; JavaScript-triggered clicks are not a substitute for the user action.

For controlled failure fixtures, prove the success path first, seed only the isolated database, and then verify that the running Core/WebView uses that exact data root. Live-WAL readers, startup migrations, workers, or a stale process can make a direct SQL mutation appear in a different projection. If the seeded row does not appear in the product projection, classify the failure branch as unverified and reconcile the data-root/WAL ownership before claiming failed→retry→replay. Restore or discard the fixture after the run.

See `references/tauri-webdriver-route-and-overlay.md` for the reusable checklist and evidence fields.

## Native close diagnostics and flaky triage
When a Windows verifier closes a Tauri/WebView shell, backend HTTP readiness is not native-window readiness. The verifier must wait for a non-zero native window handle (and, where available, an input-idle/message-loop signal) before sending `WM_CLOSE` via `CloseMainWindow()`. Treat the boolean return from `CloseMainWindow()` as evidence: record it, retry only within a bounded readiness window, and distinguish “close was not delivered” from “close was delivered but the process did not exit.” Do not hide this distinction by merely increasing the exit timeout.

For a suspected PR regression, first compare the exact PR head and post-merge tree and diff the entire causal surface: Tauri `lib.rs`, window builder, `tauri.conf`, verifier, workflow, lockfiles, and build inputs. If those files are unchanged and the same runner image/toolchain/cache keys produced one pass and one failure, classify the result as a timing/runner flake hypothesis—not a code regression—until a deterministic reproduction or a layer-specific log disproves it. Backend child readiness, native shell readiness, WebView interaction, and shutdown must remain separate evidence rows.

A real regression test must drive the current Windows shell executable, wait for the native window handle, assert `CloseMainWindow()` succeeds, assert shell exit, and then assert owned child/port cleanup. Backend-only Rust lifecycle tests do not cover this path. See `references/tauri-close-lifecycle-diagnostics.md` for the evidence matrix, minimal verifier probe, and RED-test contract.

## Read-only review of a Tauri close-lifecycle candidate
For an independent candidate review, inspect the exact dirty diff without editing, committing, pushing, or touching GitHub/Release state. Confirm Rust/Tauri compatibility with the repository's pinned dependency versions using `cargo check`, `cargo test`, `cargo fmt -- --check`, and `git diff --check`; compilation proves the handler's types and `Send` boundaries, but not native close behavior.

Trace the complete shutdown path, not only the close callback:

1. `WindowEvent::CloseRequested` must not synchronously re-enter `AppHandle::exit`; a bounded deferred call is a valid fix for native `WM_CLOSE` reentrancy.
2. Verify the deferred worker captures only an owned `AppHandle`, has a bounded lifetime, and cannot retain project state indefinitely.
3. Look for duplicate `CloseRequested` delivery. Multiple delayed workers can issue repeated `exit` requests; classify this as a robustness warning unless an atomic one-shot guard exists or the runtime contract proves exit idempotence. Confirm backend shutdown remains on `RunEvent::ExitRequested` and that the backend's shutdown path is itself safe on repeated entry.
4. Distinguish source/test proof from native proof: existing `CloseMainWindow()` → `WaitForExit()` → child/port cleanup in an installed Windows verifier is the relevant acceptance path. Backend-only Rust tests and ignored lifecycle tests do not replace it.
5. Do not require verifier changes when the verifier already exercises the exact native close path; instead, state whether a duplicate-close regression test is still a useful follow-up.

Report `Critical`, `Warning`, and `Suggestion` findings separately, state which gates were actually run, and bind the verdict to the unchanged diff. A bounded detached timer thread is not automatically a leak; prove leak risk by showing an unbounded wait, retained resource, or missing shutdown path rather than treating every `spawn` as a failure.

## Release-installed behavior gate
A release claim must begin with the user's installed artifact, not with repository CI. Before calling a format or desktop behavior available, exercise the exact installed path in a fresh isolated data root: launch the installed EXE, observe the native window, perform the real user action, read the persisted result back, close the app, relaunch, and read it back again. Keep separate evidence rows for source tests, wheel metadata, staged bundle, installer lifecycle, and installed user flow; a green CI job or a successful `prepare_bundle` is not an installed-feature PASS.

For Windows desktop shells, verify the release binary's PE subsystem as part of packaging acceptance. The release EXE must be a GUI subsystem binary; a Console subsystem binary can open a CMD window and make closing that console terminate the shell and its supervised backend. Use a release build plus a PE inspection (`file` on the produced EXE is a useful minimum; a PE-header tool is stronger) and retain the result. The normal fix is a release-only `windows_subsystem = "windows"` crate attribute, while debug may retain a console for diagnostics. Still run the real installed lifecycle after changing it; PE metadata alone does not prove startup, WebView, or shutdown.

For optional document formats, test a structurally valid fixture of the real format. Never use plain text saved with a `.pdf`/`.docx` suffix as the only adapter test. Inspect built wheel metadata and the staged runtime's installed packages for the optional extra (for example `markitdown[pdf]`) and then run the same conversion through the installed bundle. A converter's fallback error mentioning `marker` or `docling` does not prove those engines are required when the selected primary engine has a supported optional extra; fix the declared runtime dependency boundary and verify the actual bundle instead of adding heavyweight fallbacks speculatively. See `references/installed-artifact-format-and-shell-gate.md` for the compact checklist.

User-reported installed failures take priority over unrelated backend expansion. Stop adding or rerunning broad local workflows when the installed artifact is unusable; reproduce the exact failure, identify the missing packaged dependency or shell contract, fix it in an isolated worktree, and only then return to release qualification. Do not describe a release as usable until the reported user path itself passes.

## Pitfalls
- `cargo test -- --ignored` is not proof of a WebView.
- Chromium evidence does not inherit Tauri coverage.
- A starting executable does not prove a WebView click reached the product route.
- A successful compile does not prove that `WM_CLOSE` reentrancy is fixed.
- CI/source tests do not prove that an installed artifact carries optional format dependencies.
- Do not use a fake extension-only fixture as proof of a real document parser.
- Do not silently convert a possible duplicate `exit` request into a critical finding without a deterministic reproducer.
- Never fabricate harness, screenshot, click, or readback evidence.
- Keep outputs under the project data boundary.

See `references/desktop-evidence-matrix.md` for a reusable matrix. For a current WebView state ledger and restart-readback worksheet, see `references/tauri-webview-closed-loop-recipe.md`.
