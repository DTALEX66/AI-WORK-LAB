---
name: workflow-assistance-observer-delivery
version: 1.0.0
author: "UNKNOWN"
license: UNKNOWN
platforms: [windows, linux, macos]
workflow_software: codex
archived_at: 2026-08-21
source_path: D:/All projects/WORK-LAB/10-workflow/workflow-assistance/codex-assets/skills/workflow-assistance-observer-delivery/SKILL.md
---

---
name: workflow-assistance-observer-delivery
description: "Use for WORK-LAB Observer UI / read-only projection work and delivery verification."
---

# Observer UI Delivery & Verification (WORK-LAB)

## When to use
- Changing the Observer dashboard (web/ frontend, `src/observer_store.py`, sidecar v3 snapshot/SSE)
- Adding workspace discovery / active-project detection (`active_projects.py`, `project_registry.py`)
- User reports "Observer 没显示 X" / "全景是假的吗" — trace the real data path before answering
- Publishing any Observer change (PR / merge / release)

## User rule (hard, first-class)
**发布前必须实测 UI 所有内容能显示**：不做实时就做延迟，但绝不能空、不能错、不能缺。只看 API 返回、只跑自动化测试、口头说"测过了"都不是验收——必须实际打开页面（浏览器），确认 projects / tasks / usage / ci 全部真实渲染。这条适用于任何 Observer/观测类 UI 交付。

## Workflow
1. **Verify the data source first** — canonical SQLite is the single source of truth:
   - Read tables directly: `SELECT COUNT(*)` on projects / tasks / telemetry_events / usage_samples / ci_runs
   - If the store HAS data but the UI shows empty → schema drift, NOT missing data. Never call it "fake" without proof.
2. **Find existing services before starting new ones**:
   - `sidecar_already_running` error → read `.hermes/task-runtime/workflow/sidecar-process.json` and `.hermes/task-runtime/observer/dashboard-process.json` for PID / URL / port
   - `wmic process get processid,commandline` finds actual listeners; `netstat -ano | grep <port>` maps port→PID
   - **Zombie lock via PID reuse (Windows)**: if `sidecar_already_running` fires but `netstat` shows the port is NOT listening, the lock's PID may have been recycled by an unrelated process (e.g. a Codex desktop renderer took over the old sidecar's PID). Prove it with `wmic process where "ProcessId=<lockpid>" get commandline` — if it's not `sidecar.py`, the lock is stale. Fix: confirm no real sidecar process exists, then `rm` the stale `sidecar.lock` + `sidecar-endpoint.json` and restart. Never kill the unrelated PID.
   - Restart after code changes: kill the PID on the port, relaunch with `--canonical-store`
3. **Browser-verify the real rendered page** (not just the JSON API):
   - `browser_navigate http://127.0.0.1:<port>/?view=full` AND `?view=compact`
   - `browser_console` fetch `/api/v1/snapshot` (canonical v3, schema `workflow/snapshot/v3`) to confirm the API payload shape
   - Assert the DOM shows project names, states, token values (browser_snapshot / innerText)
   - If the page looks stale, `location.reload(true)` — old cached JS can mask fixes
4. **Verify the LIVE push chain, not just the display** (when user asks "可以实时监控了吗"):
   - Sidecar endpoint lives in `.hermes/task-runtime/workflow/sidecar-endpoint.json` (`eventsUrl`, `pid`); check the PID is alive before trusting it.
   - Subscribe: open a background process on `http://127.0.0.1:<port>/api/v1/events` with a bounded read timeout (e.g. `--max-time 20`).
   - Write a probe record into the canonical store (`append_telemetry` with a distinct `event_id` like `live-test-001`), then re-check the SSE frames / `/api/v1/snapshot`: the `revision` must increment (13→14→15). No increment = real-time chain broken (sidecar not watching the WAL), do NOT claim live.
   - Sample `/api/v1/snapshot` several times and confirm `transport.transportState == "LIVE"` (LIVE requires schema valid + SSE connected + heartbeat fresh + cursor valid + writer watermark fresh + coverage met — see `live_gate.py`).
   - **freshness label semantics**: `freshness.state` may read `STALE` even when data is genuinely live — the dashboard freshness tag is a snapshot-semantics label, not a liveness signal. Do not report "not live" based on the freshness label alone.
5. Run local suites after changes: Observer Python unittest (all tests/*.py), Node UI contract tests (`node tests/run_all_tests.js`), Workflow quality gate.

## Pitfalls
- **Schema drift between renderer and projection (the big one)**: dashboards may still read the retired event-rebuild schema (`overview` / `tasks` / `dataQuality`) while the canonical v3 snapshot (`workflow/snapshot/v3`) returns `projects` / `executions` / `tokenSummary` / `git` / `ci`. Symptom: empty tables ("暂无观测事件") while `/api/v1/snapshot` has data. The only canonical projection is `snapshot_api.build_snapshot` (WLGM-150); the web client normalizes it once in `api.js normalizeV3` — never build a second projection server-side. See `references/dashboard-schema-drift-2026-08.md`.
- **Legacy `/api/dashboard` is RETIRED (R2 third batch, 2026-08-14)**: `scripts/observer_dashboard.py`, `src/observer_canonical.py` and their tests are deleted; `allowedWrites` is removed (Observer owns no write surface). The only production surface is `/api/v1/snapshot` (v3) + `/api/v1/events` (SSE) served by the Workflow sidecar. Tauri rejects `/api/dashboard`. Do not reintroduce a server-rendered dashboard path; new work targets `web/index.html` + the v3 snapshot + SSE.
- **usage tokens null**: the canonical projection does `SUM(total_tokens)`; if callers of `record_usage_sample` omit `total_tokens`, the projection shows null/0. Auto-derive `total = input + output` when absent.
- **Workspace discovery ≠ active detection**: git-scan registration is separate from marking ACTIVE. Windows tasklist/wmic do NOT expose a process working directory — detect activity via: agent process running (tasklist) + fresh evidence files inside the project's `.hermes` / `.codex` / `.agents` (mtime within ~120 min). Never fabricate "active".
- **LF/CRLF noise on Windows**: the patch tool can rewrite files to CRLF; `.gitattributes * text=auto` + `core.autocrlf=true` then show phantom modifications. `git diff --ignore-all-space` empty ⇒ content identical; clear the noise with `git add <file> && git reset -- <file>`.
- **dashboard render tests need canonical.sqlite**: write regression tests to `SkipTest` when `canonical.sqlite` is absent (CI runners) so they don't fail on fresh checkouts.
- **Personal-use projects: don't block release on Authenticode code-signing certs**: for a user's own tooling, an unsigned installer is acceptable — Windows SmartScreen shows "未知发布者 / 仍要运行", which is normal, not a defect. Report it honestly once and move on; do not list "needs cert" as a standing blocker. MSI per-user install (`msiexec /i ... /qn`, installs to `%LOCALAPPDATA%`) needs no admin rights and is the verified install path for personal use; NSIS `/S /D=` custom-dir is NOT honored by tauri-generated installers — don't rely on it for contained install tests.

## Support files
- `references/dashboard-schema-drift-2026-08.md` — full debugging transcript: empty dashboard → API has data → schema drift root cause → projection-side fix (state mapping + usage series + total_tokens derivation).
- `references/rust-tauri-toolchain-floor.md` — Tauri native build: documented rust minimum is a floor not a guarantee (edition2024 crates need rustc ≥1.88); portable rustup install to a user dir; MSI vs NSIS scripted install behavior.
- `references/workspace-discovery-requirement-2026-08.md` — user's durable "total workspace" requirement (all projects under the root are candidates; detect Hermes/Codex loading/executing them and reflect in Observer) + active-projects.py implementation semantics (agent-running AND fresh-evidence conjunction, no cwd matching on Windows).
