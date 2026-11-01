---
name: web-dashboard-delivery
version: 1.0.0
author: "UNKNOWN"
license: UNKNOWN
platforms: [windows, linux, macos]
workflow_software: hermes
archived_at: 2026-08-21
source_path: C:/Users/ALEX/AppData/Local/hermes/skills/software-development/web-dashboard-delivery/SKILL.md
---

---
name: web-dashboard-delivery
description: Build and deliver local web dashboards for this user.
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [windows, linux, macos]
metadata:
  hermes:
    tags: [dashboard, ui, web, observer, design-system, delivery]
    related_skills: [provider-routing-safety, python-testing, user-facing-ingestion-workflows]
---

# Web Dashboard Delivery

Use when building or delivering a local web dashboard / observer UI for this user
(read-only projections, metrics pages, observer panels). This is the "how to do it
for THIS user" skill — it carries the style, language, and visibility preferences
they have corrected me on, so a future session starts already knowing them instead
of being corrected again.

## Non-negotiables (user corrections that fired)

0. **When authority fixture images exist, READ them — never improvise the shell
   from memory.** If the user hands you a spec pack with `UI-FIXTURE-*.png`
   (or any design reference images), the approved visual direction lives in
   those files, NOT in your memory of "Apple/Linear/Vercel". Building from
   memory produced a UI the user rejected outright:
   "这特么跟给你的任务包的UI完全不一样啊" and the correction
   "看不了图就调用技能啊" (get vision working, don't guess). The #1 rule:
   **get real vision on the fixtures, or extract their layout by pixel/ASCII-grid
   analysis, BEFORE writing any dashboard markup.** Only when you can see the
   actual design should you build. See "Reading authority fixture images" below.
1. **Carry the approved design shell — never a plain preview.** The user has an
   approved visual vocabulary: Apple (glass navigation, black/light-gray rhythm,
   generous whitespace), Linear (near-black `#08090a`, translucent panels, indigo
   `#5e6ad2`/`#7170ff`, 590-weight type, mono technical labels), Vercel
   (shadow-as-boundary restraint), optionally Sentry-style data-dense status pills.
   Deliver a real shell (glass nav + hero + metric cards + panels + footer), NOT a
   bare table or a generic admin-template look. No purple gradient, no plain
   "background panel" chrome. NOTE: this vocabulary is a starting point — if the
   user provides actual fixture images, the fixtures override it; do not apply
   the vocabulary as if it were the design itself.
2. **UI copy is in Chinese.** All user-visible labels, headings, and notes are
   Chinese. Keep English only where it is a data value / technical identifier
   (e.g. `source-exact`, `telemetry.summary`, `/api/dashboard`) or part of the mono
   design language.
3. **The target is four views sharing one Projection** (Full/Compact × Dark/Light),
   driven by deterministic JSON fixtures — never four hand-copied pages. Apple
   liquid-glass is for the shell/nav/hierarchy only; data cards stay clear,
   near-solid surfaces so text contrast is never sacrificed. No hero, neon,
   rainbow gradient, thick shadow, Emoji, or black-box health score.
4. **User visual confirmation is a hard gate.** Do NOT declare the UI final until
   the user has looked at a rendered view and confirmed it. "It renders" / "tests
   pass" / "fixture generated" is not completion — the user has repeatedly rejected
   background-only or unconfirmed delivery.
5. **Make it actually visible.** Do NOT end with "the service is running in the
   background." Open it for the user: `open_preview` to the local URL, confirm it
   renders, and tell them where to look. The user explicitly rejected
   "服务在后台你让我去哪看" (background-only delivery).
6. **Empty state is real, not a bug.** A read-only dashboard with no events shows
   zeroes / "暂无观测事件". Say so plainly instead of treating it as a failure.
7. **Demo data on request.** If the user wants to see it populated, feed
   schema-valid fixture events through the module's own adapter (never raw blobs),
   and label it demo/演示 data. It lives in ignored runtime paths, not Git.
8. **Real data first — never show fixture demo data as the default running view.**
   A user correction fired: "AGENT里哪有CURSOR 和WORKDADDY啊 你这显示的都不对啊" —
   the fixture JSON contained fabricated projects/agents (Cursor, WorkBuddy,
   Automation Sandbox, Cognitive-Loop-OS) that had no real basis, and they were
   rendered as the live view. The default mode must be LIVE (real observed events),
   NOT FIXTURE. See "Real-data-first projection" below.

## Data consistency: KPI counts MUST derive from the same project list (no phantom tasks)

A user correction fired: "运行全景里的任务不完全对，是不是有假的任务" — the KPI strip
("运行任务 7 / 等待 3 / 阻塞 2") disagreed with the project table (which listed only
4 projects). Root cause: the KPI read a separately-hardcoded `summary.tasks`
(`running:7, completed:28`), while the project table rendered the `projects` array
(4 entries with states `waiting_external/running/blocked/idle`). The two were never
reconciled → numbers that contradicted the visible rows looked like phantom tasks.

Rule: **derive aggregate task counts from the SAME `d.projects` array the table
renders.** In the KPI renderer, count by `p.state` over `d.projects` (running =
`running`+`queued`, waiting, blocked, completed, idle, unknown) instead of trusting
a separate `summary.tasks` block that may be stale or over-counted. Fall back to
`summary.activeProjects` only when the array is empty. This guarantees the header
numbers always match the rows on screen — no fabricated states, no contradiction.
(Keep the raw `summary.tasks` for a compact "completed" stat if desired, but the
running/waiting/blocked KPI must come from the live project list.)

## Real-data-first projection: never default the running view to fixture demo data

A hard user correction fired: the component shell rendered fixture JSON that
contained fabricated projects/agents (`Cursor`, `WorkBuddy`, `Automation Sandbox`,
`Cognitive-Loop-OS`) as if they were real, and the user called it out: "AGENT里哪有
CURSOR 和WORKDADDY啊 你这显示的都不对啊". Fixture/demo data must NEVER be the default
view. It is only a test/empty-state stand-in. The default must be **real observed
data** (LIVE), so the component shows the user's actual tasks — not invented ones.

Concrete recipe (frontend + backend):

- **Backend derives projects from real events only.** The authority projection
  must aggregate by actual `taskId`/`sourceModule` from the event store — no
  hardcoded project/agent names. State per task comes from its last event type
  (block→blocked, unverified→waiting_external, pass/verified→completed,
  run/usage/telemetry→running, else unknown). `agentPlatform` = the real
  `sourceModule`, never a fabricated client name.
- **Default mode is LIVE, not FIXTURE.** In `state.js`, `normalizeMode("")` /
  `normalizeMode(undefined)` must return `"LIVE"` (real data first); only an
  explicit `?mode=fixture` selects the fixture. A default of `"FIXTURE"` is what
  rendered the fake agents.
- **In a portable shell there is no live backend, so bundle a REAL snapshot.**
  Generate `web/assets/live-snapshot.json` from the backend authority projection
  over the real event store (a few KB), and have `app.js` load order be:
  `GET /api/dashboard` (if a backend exists) → `assets/live-snapshot.json`
  (bundled real data) → FIXTURE (last resort only). Do NOT jump straight to
  FIXTURE when the fetch fails.
- **Keep the fixture JSON clearly labeled and out of the default path.** The
  `mode` badge must show `LIVE` (real) when real data rendered, and only show
  `FIXTURE` when it actually fell back. A fabricated agent showing under a LIVE
  badge is the exact bug the user rejected.

Full recipe (backend state-map + frontend load order + bundled real snapshot +
test changes) in `references/real-data-first-projection.md`.

### Main projects from `projects.json`, not stage-level taskIds (WA/WL rejection)

A second correction fired after the fake-agent fix: "WA WL都是什么玩意？不要执行项目
里面的详细阶段任务" — deriving the project panorama by `taskId` still showed
stage-level WORK-LAB task IDs (WA-ADAPTER, WL-USAGE…), which the user reads as
noise, not the main projects to monitor. The project panorama must list the
**registered main modules** from `00-governance/projects.json` (`modules[].id`),
one row each, state derived from events whose `sourceModule` matches that module.
And the **governance board (Rules/Skills/Adapters/Memory) must show REAL inventory
counts** from repo artifacts (CURRENT_STATE skills, adapter-registry entries,
`00-governance/rules`), not ship all-zeros — the user explicitly demanded the
management plane be monitored. Full recipe appended to
`references/real-data-first-projection.md`.

## Layout convergence: fewer, larger blocks beat a dense 8-card dashboard

Another correction: "布局结构还是不合理，太多了，收敛点，不需要这么细化，太拥挤了".
The first full view had ~8 sibling cards (KPI, projects, blocker, usage, trend, CI,
governance, quality) — too busy. The accepted shape collapses to ~5 core blocks with
roomy gaps:
- KPI strip (one row)
- 项目运行全景 (wide) + 关键阻塞 (narrow) on one row
- 用量与趋势 (usage + trend merged into one full-width block)
- 健康摘要 (a compact 6-cell strip folding CI + governance + quality into
  `exact-SHA / CI queued-no-job / source coverage / governance drift / freshness /
  unknown`) — implement as a `renderHealthStrip(d)` helper rather than three cards.
Reach for merge-then-truncate before adding a card. A component-form HUD wants
whitespace and few blocks, not information density.

### Project table: main project + status only (drop branch/task/stage/duration detail)

A follow-up correction fired: \"任务全景 显示主项目就行各个状态就行，分支或者更细节的项目
任务旧不要展示了\" (the project panorama should show only the main project and its
status — drop the branch, task, stage, duration, last-event detail). The first
project table had ~9 columns (项目/仓库, Agent 平台, 任务, 生命周期, 阶段, 耗时,
Blocker/CI, 最后事件, 来源质量) — far too fine-grained for a component HUD.

Converge the project table to **4 columns: 项目 · Agent · 状态 · Blocker/CI**.
- 项目 = `displayName || projectId` (drop the second-line repository sub-label).
- 状态 = the existing `chipFor(state)` (icon + text + color).
- Blocker/CI = the `ciState` chip only; drop `blockerSummary`, task, stage,
  duration, lastEventAt, quality-dot columns.
- Keep the blocked→waiting→failed→running→completed sort (SORT_ORDER).
A component-form HUD shows the WHAT (which project, what state), not the
per-project operational detail; that belongs behind a read-only expand, never as
default columns.

## Build notes (stdlib http.server)

- `BaseHTTPRequestHandler` subclass built in a factory closure (to capture a
  store/config) MUST `return TheClass` — forgetting it yields
  `'NoneType' object is not callable` at request time. **This is a recurring
  trap with full-file `write_file` rewrites**: when you rewrite the whole
  server script in one shot, the `return` line is easy to drop. After ANY
  full rewrite, verify the factory ends in `return HandlerClass` (the runtime
  symptom is `RequestHandlerClass -> None` from `make_handler`), and confirm
  with the server test — a passing `py_compile` does NOT catch it.
- Override `log_message` to a no-op to keep a threaded stdlib server quiet in tests.
- When the visual shell changes label casing, update any `assertIn(...)`
  assertions to stable structural markers, not exact wording a redesign moves.

## Read-only REST endpoint set + 405 guard

When an authority spec (e.g. R2 M-310.1) requires a versioned read-only API
surface, expose a fixed set of GET endpoints — e.g. `/api/dashboard`,
`/api/projects`, `/api/tasks`, `/api/usage`, `/api/quality`, `/api/ci`,
`/api/governance`, `/healthz` — all derived from the SAME projection (no
per-endpoint recomputation of unrelated data). Key points:

- **All non-GET verbs must return explicit `405`.** Add `do_POST`, `do_PUT`,
  `do_PATCH`, `do_DELETE` methods that all call a shared `_send_405()` helper
  (they do NOT exist on `BaseHTTPRequestHandler`, which would otherwise 501).
- Keep endpoints inside the one `do_GET` route block; a small `_send(status,
  content_type, body)` helper avoids repetition.
- **Test 405 with `http.client`, not `urllib.request`.** `urllib` on Windows
  raises `ConnectionAbortedError: WinError 10053` on a 405 rather than
  surfacing the status. Use `http.client.HTTPConnection(...).request(method,
  path, body=b"{}")` and assert `resp.status == 405`.
- **Add a single regression test that iterates the full endpoint list.** One
  test loops `["/api/dashboard","/api/projects","/api/tasks","/api/usage",
  "/api/quality","/api/ci","/api/governance","/healthz"]`, asserts each returns
  200 AND parses as JSON (`json.load(r)`), and that `/api/tasks` reflects a
  seeded event. Add a sibling negative test that asserts `POST/PUT/PATCH/DELETE`
  all return 405. These two tests catch a dropped route, a broken JSON body, or
  a lost 405 guard in one pass — a plain `py_compile` will not.
- `/api/ci` / `/api/governance` may return a read-only view object
  (`{"status": "read-only-view", "mutationSurface": ...}`) rather than fabricating
  external CI state — never claim live CI status you did not actually query.

## Editing a tracked JSON ledger surgically

When a single governance field (e.g. a `reviewedCommit` in a source-ledger JSON)
must change, use `patch` with an exact `old_string` — do NOT round-trip the file
through `json.dumps(..., indent=...)`. Re-serialization expands compact arrays
into multi-line and produces dozens of lines of unrelated diff (this happened:
one value changed, but the commit showed 52 insertions / 11 deletions and had to
be reverted). If a bad re-serialize commit already landed and is pushed, do not
force-push (branch protection forbids it): `git checkout main -- <file>` to
restore, re-apply the surgical patch, and add a follow-up fix commit.

## Cross-project projection (`/api/projects`)

When the R2/authority scope makes the observer cross-project (not just WORK-LAB
itself), expose a read-only project group endpoint (`GET /api/projects`) derived
purely from events:

- The event schema's `projectId` is optional and `type: string, minLength: 1` —
  it is NOT required, so a JSON `null` or empty string FAILS validation. Omit the
  key entirely for events that belong to the default project, and group by
  `event.get("projectId") or default_project` in the projection.
- Projection shape: `{count, projects:[{projectId, taskCount, eventCount, sources}]}`.
  Count tasks per project via a `set` of unique taskIds, and sources via a `set`
  of sourceModule — dedupe, never just increment per event.
- Pure projection, no mutation: it re-reads the store and returns sorted data;
  add a test that feeds a couple of default-project events plus one with an
  explicit `projectId` and asserts the grouped counts split correctly.
- Keep it a separate route from `/api/dashboard`; both are read-only GET.

## Responsibility-boundary contract (when full migration is too big)

When an authority spec says the observer must be a *consumer* of a telemetry
ledger owned elsewhere (e.g. R2 M-300.4: "Observer only reads the Projection,
never appends events"), but the full cross-module migration (make the producer
the single writer, point the observer at the new source) is too large or too
risky to land safely inside the current tool budget:

- Do NOT do a destructive half-migration. If the observer's store is
  currently `append`-capable and tests/dashboard rely on that write path,
  ripping out `append` mid-flight breaks the suite and fabricates a partial
  migration. Keep the write path; declare the *boundary* instead.

### Better than docs-only: a runtime-enforced read-only wrapper

Docs-only contracts are not proof. The strongest safe increment is to enforce
read-only at RUNTIME on the run surface while leaving the underlying writable
store intact for the producer/tests:

- Keep `ObserverStore.append` as-is (tests + workflow producer still use it).
- Add a thin wrapper the dashboard actually serves from — e.g.
  `ReadOnlyObserverStore(store)` exposing only `read_events()` /
  `rebuild_projection()` / `.path`, and whose `append(...)` raises
  `ObserverInputError("Observer is read-only: append is owned by the <producer>")`.
- Wire it into `create_server(...)`: `ThreadingHTTPServer(..., make_handler(ReadOnlyObserverStore(store)))`.
- The read surface (dashboard + all REST endpoints) is unchanged — verify it
  still renders with the seeded data after the switch.
- Add a negative test: constructing the wrapper over a real store, asserting
  reads work (`read_events()==[]`, projection has `eventCount`) and that
  `append([event])` raises. This turns the R2 "observer never appends" claim
  into a CI-enforced invariant, not a comment.
- Bump the source-ledger `reviewedCommit` and ship as its own PR (see below).
- Deliver the contract as a non-breaking increment:
  - `AGENTS.md`: state Observer is a strict read-only consumer of the Canonical
    Projection; the single producer/ledger owner is the workflow module.
  - `module-profile.json`: add fields `telemetryRole: "consumer"`,
    `telemetryProducer: "<module>"`, `telemetryLedgerOwner: "<module>"`,
    `observerWriteSurface: "derived-cache-projection-report-only"`.
- Verify the contract addition does not break the skeleton verifier (it checks
  `id`/`externalMutationDefault`, extra fields are fine).
- Ship that increment with its own PR, then honestly mark the full ledger
  ownership migration as deferred in the report — never claim it closed.

## Source-ledger `reviewedCommit` bump after touching module code

A source ledger entry whose scope you modified degrades to
`STALE_REVIEW` (shows up as `blocked=1`) until its `reviewedCommit` is bumped to
the new commit. This is correct fail-closed behavior, not a bug. After you merge
a module-code change, update the affected entry's `reviewedCommit` to the new
HEAD as a separate small commit, using the surgical `patch` (see above) — never a
`json.dumps` round-trip. Verify with the ledger verifier that
`local_readback=N blocked=0` is restored.

### The freshness *test* must tolerate STALE_REVIEW (sibling-path CI red)

The ledger freshness **regression test** must not hard-assert `local-verified`
for a module scope, because a rebase merge (`gh pr merge --rebase`) shifts the
reviewed scope's SHA: the merged `main` commit differs from the pre-merge
`reviewedCommit` you recorded, so a fresh CI checkout legitimately sees
`STALE_REVIEW` and a strict `assertEqual(..., "local-verified")` goes red on
`main` even though nothing is wrong. This exact regression happened: observer
was loosened to `{local-verified, STALE_REVIEW}` in an earlier pass, but the
**workflow** entry still hard-asserted `local-verified`; the first post-merge
`main` run then failed `integration` → `aggregate` with
`AssertionError: 'STALE_REVIEW' != 'local-verified'`.

Fix the whole class, not one module: assert BOTH entries are in
`{"local-verified", "STALE_REVIEW"}` (STALE_REVIEW = "re-review required", a
legal fail-closed state, not a CI error), and keep the `not-in("open-design")`
negative control. Do not add a `assertEqual(... == "local-verified")` anywhere —
that reintroduces the brittle check. Then `git reset --hard origin/main`,
create a `fix/ci-...` branch, and land the test fix through its own PR.

## Canonical vocabulary must be mapped at the render boundary (freshness LIVE→"实时")

A real bug (ERR-044 pattern): the canonical projection outputs **mode vocabulary**
(`LIVE` / `STALE` / `SNAPSHOT` / `OFFLINE`), while the dashboard's renderer maps
only the **legacy dataQuality vocabulary** (`source-exact` / `partial` /
`deduplicated`). Result: a LIVE canonical state renders as raw gray text
(`LIVE`) with the default tone — no green, no Chinese label — and the user reads
it as "freshness stuck at STALE".

Rules that prevent the whole class:

- The renderer needs an explicit `_freshness_state(freshness)` mapping
  (canonical mode words → display vocabulary: `LIVE→fresh`, `STALE/SNAPSHOT→stale`,
  `OFFLINE→offline`, else `unknown`) applied in EVERY render path
  (`_render_full` AND `_render_compact`) before `_quality_tone` / `_quality_cn`.
- The tone and Chinese-label maps must cover the display vocabulary too
  (`fresh` → green `#10b981` + "实时", `stale` → yellow + "滞后", `offline`/`unknown`
  → gray + "离线/未知"), not only the old dataQuality words.
- Do NOT change the canonical projection's vocabulary to fix a display issue —
  the canonical layer is a tested contract (tests assert `LIVE`/`STALE`); map at
  the render boundary instead.
- Lock the mapping with render regression tests (assert `_freshness_state("LIVE")`
  == "fresh", and that a LIVE fixture renders the Chinese label + green tone), and
  keep a test proving canonical mode words never leak verbatim into the HTML.
- A fresh observer store with zero events legitimately shows `STALE`; that is a
  data-layer fact, not the same bug as the vocabulary mismatch — say so plainly.

### Map at the projection boundary, not only the renderer (ERR-044 blind spot)

The render-boundary fix above is NOT sufficient when the official UI consumes
the JSON API instead of the server-rendered HTML. Validated 2026-08-11: the
server-rendered dashboard had `_freshness_state`, but the official web UI
(`web/scripts/render.js`) fetches `/api/dashboard` — and the projection's
`freshness.state` came straight out of the canonical reader as **mode
vocabulary** (`"STALE"`), while `render.js` only recognizes
`fresh/delayed/stale`. Result: the official UI's freshness badge showed
"未知" forever, even though the debug HTML looked right. The render-boundary
map existed only in the debug entry point — the JSON API path had no mapping
at all.

Rules that prevent the class (upgrades the render-boundary rule above):

- **Do the vocabulary mapping ONCE at the projection output boundary**
  (`to_dashboard()` in the canonical adapter), with a single source map:
  `LIVE→fresh`, `STALE/SNAPSHOT/FIXTURE→stale`, `OFFLINE→offline`,
  `UNKNOWN→unknown` — then every consumer (JSON API, web UI, server HTML)
  sees the same UI vocabulary and needs no per-renderer translation.
  Renderers may keep a defensive fallback, but the projection output is the
  single authoritative mapping point. Mapping only at one renderer leaves the
  JSON API (and any other consumer) exposed to raw mode words.
- **Internal snapshots keep the raw mode vocabulary** (`read_snapshot()`
  returns `LIVE`/`STALE`); the *projection* is the contract boundary that
  translates. Tests must lock BOTH: snapshot asserts mode words, projection
  asserts UI words (`freshness.state == "stale"`, `mode == "SNAPSHOT"`), plus
  a mode→freshness matrix test for LIVE/OFFLINE too.
- **Dual projection implementations must be kept in sync.** The Observer
  production path reads through its own `SQLiteReadOnlyStore` SQL while tests
  often exercise the Workflow-owned `CanonicalStore.projection()` (because it
  can write seed data). They are TWO separate queries — adding a column to one
  and not the other makes tests green while production stays broken (observed
  live: series bucket was `None` until BOTH `observer_canonical.py` and
  `canonical_store.py` SQL got `MAX(observed_at)` and split input-output
  sums). Grep both files for the same SELECT when changing either.
- **Usage-series semantics:** SQL must select a time column
  (`MAX(observed_at)`) or the trend chart buckets are all `None`; and
  `inputTokens`/`outputTokens` must be split sums — mirroring `total_tokens`
  into both is a silent data-semantics bug (input and output both showing the
  total). Lock it with a test that inserts one usage row and asserts
  `series[0]` carries the bucket and split values.
- **Compact-view task count ≠ project count.** Derive task metrics from
  `summary.tasks` (sum of the state buckets), never `len(projects)` — using
  the project list length fabricates a phantom task number (1 project with 3
  tasks must render 3). Assert the rendered number, not the implementation.

## Verify before claiming done

- `py_compile` the server script.
- Run the dashboard HTTP test (`test_observer_dashboard.py`-style): GET `/`,
  `/api/dashboard`, `/healthz` all return 200 with the expected structural markers.
- `open_preview` the URL and confirm it renders (browser snapshot shows the shell).
- For a read-only observer: confirm `external mutation: false` boundary is visible.
- When the user drops fixture PNGs, READ them FIRST per "Reading authority
  fixture images" below — do NOT improvise the shell from memory and do NOT loop
  a failing vision call. Enable KIMI vision (`auxiliary.vision` →
  `moonshot-v1-128k-vision-preview`) for real text/label reading, or fall back
  to PIL pixel/ASCII-grid layout extraction + `MEDIA:<path>` for the user's
  visual confirmation. The user confirming the rendered view is the gate;
  metadata is supporting evidence, not a substitute.
- **When no vision provider is configured, read screenshot/window TEXT with
  tesseract OCR** (scoop `tesseract` + `tessdata_fast` `eng`+`chi_sim`
  `.traineddata` from the GitHub tessdata_fast repo — the tessdata dir ships
  empty). Combined with PIL pixel stats (transparent %, unique-color count,
  per-cell grid luminance/std) this identifies "what interface is this" from a
  PNG (Edge ERR_CONNECTION_REFUSED page vs Hermes window vs blank frame) and
  verifies a window really rendered (content-rich PNG > ~100KB vs blank ~7KB).
  For window text, PowerShell `PrintWindow` → PNG → tesseract works on normal
  windows; for WebView2 use CDP captureScreenshot or `CopyFromScreen` (see the
  Tauri reference).

## Reading authority fixture images

Full recipe in `references/reading-fixture-images.md`: enable real vision via
Hermes auxiliary vision (KIMI `moonshot-v1-128k-vision-preview`; note `kimi-k3`
and `kimi-latest` both fail), turn it back off after use (KIMI is expensive),
and a PIL pixel/ASCII-grid fallback that extracts layout structure + palette
when no vision provider is available.

### `kimi-k3` reasoning model returns EMPTY content on long generation

When you call `kimi-k3` (a reasoning model) and get back `content == ""` with
`finish_reason == "length"`, that is NOT a network failure — the model spends
its entire `max_tokens` budget on `reasoning_content` and truncates before it
ever writes `content`. Observed twice this session while asking it to emit a
long Liquid-Glass CSS spec. This is why `kimi-k3`/`kimi-latest` are
unreliable for long text/CSS output (short brand-SVG generation worked only
when `max_tokens` was kept small).

- Do NOT keep retrying the same long prompt with the same budget.
- Raising `max_tokens` helps but is token-expensive (and timed out at 120s on a
  6000-token request here).
- **Default: route long CSS/implementation work to DeepSeek** (the user's stated
  preference: "DeepSeek 能解决就用 DeepSeek"), and reserve `kimi-k3` only for
  short, focused visual assets (a single brand SVG). Liquid-Glass CSS is a
  mature, well-understood technique — you do not need a model to generate it;
  write it directly.

## Handoff/交接 documents: write them into GIT-TRACKED dirs, never `.hermes/`

A hard correction fired: user said "更新云端 有交接总结" (update the cloud with
the handoff summary), and it turned out the handoff doc I'd written to
`.hermes/task-artifacts/observer-handoff-2026-08-08.md` was **never in git** —
`.hermes/` is in the root `.gitignore`, so nothing under it can be committed or
pushed. `.hermes/task-artifacts/` is for local working notes / task-runtime
evidence only, NOT for anything the user expects to reach the repo.

- **Handoff / 交接 / handover documents belong in the repo's tracked handoff
  dirs**, matching existing convention: `50-taskpacks/*-HANDOFF.md` and
  `90-archive-manifests/*-HANDOFF.md` (both tracked in this repo). Check what
  the repo already uses with `git ls-files | grep -i handoff`.
- Before declaring "交接/摘要已上传", verify the file is actually tracked:
  `git check-ignore <path>` (returns the path ⇒ ignored, won't upload) and
  `git ls-files <path>` (empty ⇒ not committed). A doc sitting under a
  gitignored dir is NOT uploaded, no matter how well-written.
- When you copy it into a tracked dir, update stale anchors (merged HEAD, PR#,
  CI status) before committing so the pushed doc reflects reality.

## git `reset --hard` silently destroys uncommitted tracked-file rewrites

This session, while resolving a stale branch, `git reset --hard origin/main`
wiped a previously-applied rewrite of `src/observer_runtime.py` (the Schema-v2
authority projection) because it had never been committed. The new files under
`web/` and `src-tauri/` survived (they were untracked), but the tracked-file
edit was reverted to HEAD. Cost a full re-apply of the function.

- Before any `git reset --hard`, `git checkout`, or branch-switch that could
  discard work, list uncommitted tracked modifications with
  `git status --short | grep '^ M'` and commit or stash them first.
- `reset --hard` does NOT delete untracked files — so a mix of "tracked edit +
  new untracked files" is the dangerous case: only the tracked edit is silently
  lost. Treat tracked modified files as fragile across resets.

## Formal authority UI pack (contract + Schema + Fixture + Tokens + PNG)

When the "design" arrives as a *formal pack* — a zip with a taskpack markdown
contract, a Projection JSON Schema, a JSON fixture, a tokens CSS, AND PNG
references — it is stricter than loose PNGs. Full recipe in
`references/authority-ui-pack.md`: the priority hierarchy (contract > Schema >
Fixture > Tokens > PNG; PNG is texture/layout reference only, never an OCR/text
source), the Schema-v2 projection shape to validate your backend output against
with `jsonschema`, the data-semantics display rules (cacheRead never double-
counted, `$4.29`=API estimate, `订阅未计量`≠0, no undefined "总 Token"), and the
**final-state gate**: honor a declared `UI_LOCAL_VERIFIED_READY_FOR_USER_VISUAL_REVIEW`
+ `EXPLICIT_USER_APPROVAL` — do not commit/push under a blanket "全量授权"; stop
and get explicit visual confirmation. That contract also mandates a vanilla
`web/` static directory (no framework/CDN/chart-lib) and native-SVG-only charts.

### Testing the vanilla web/ build (no browser)

Once the static `web/` exists, verify it with a pure-Node contract harness
before any browser work. Full recipe in
`references/vanilla-web-frontend-tests.md`: the global-mirroring trick to
`require` browser IIFEs in Node (set each namespace on `global` before loading
dependents), inline-the-icon-sprite (external `<use href="assets/...">` fails
over `file://`), assert read-only by CONTROLS not forbidden WORDS (labels like
"正在执行" legitimately contain 执行), strip comments+`xmlns` before static CDN/
API regexes, scan all CSS including tokens for reduced-motion, and treat the
Windows `write_file` `.js` lint MODULE_NOT_FOUND as a path-quirk false-positive
(confirm with the test runner, not the linter).

## Delivery form: web page vs component-form portable desktop shell

Ask or detect the delivery form before building. This user has explicitly
rejected a plain web page in favor of a **component-form desktop shell** ("观测模块
是类似组件形式的外壳，不是网页样式的，不安装只要便携绿色版，方便更新"; A = independent
portable window + B = system tray + floating panel, both requested). The static
`web/` frontend stays the render surface, but it gets wrapped in a Tauri v2
portable shell (single ~10 MB exe using system WebView2 — no installer,
copy-to-update) instead of being served as a browser page. Full working recipe:
`references/portable-tauri-shell.md`. When the user says "外壳/组件/便携绿色版",
default to the Tauri shell path, not a served page.

Two component-form refinements live in that reference: (1) the project panorama
shows only 项目·Agent·状态·Blocker/CI (see "Project table" above), and (2)
transparency/background must be **user-customizable** via a memory-only settings
panel (`data-bg` modes + `--wl-opacity` slider), never hardcoded. Two more
verified Tauri gotchas in that same reference: borderless windows
(`decorations:false`) become **unmovable** until you add `data-tauri-drag-region`
+ the `core:window:allow-start-dragging` capability, and the **light theme must
use near-opaque surfaces + dark text** or the user rejects it as ugly/unreadable.

Four more verified 2026-08-14 pitfalls are in that reference — read them before
debugging a blank/ugly shell:
- **Never navigate at setup** — `window.url()` is `about:blank` there; injecting
  `?api=` via `window.navigate` parks the page on blank → "透明框". Inject via the
  **Builder-level `.on_page_load`** hook (Finished event, skip about:/already-
  injected), NOT on the window (E0599).
- **WebView2 Origin is `http://tauri.localhost`** — backend CORS must allow
  `.localhost` (RFC 6761), else fetch 403 → OFFLINE.
- **Blank shell diagnosis = WebView2 CDP** (`WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS=
  "--remote-debugging-port=9222 --remote-allow-origins=*"`, then `/json` +
  websocket Runtime.evaluate / Page.captureScreenshot). PrintWindow is BLACK for
  WebView2 and misleads.
- **Grid collapse** (cards → ~60px vertical strips) = renderer dropped the
  `wl-col-X` span classes; diagnose `getComputedStyle(...).gridColumn` via CDP,
  restore the historical span map (`overview:12, projects:9, blocker:3, …`).
The Windows toolchain env recipe (RUSTUP_HOME/CARGO_HOME, MSVC/SDK manual env,
full-exe-path for spaced PATH, crates.io proxy) is also in that reference.

## Related

- **Delivering through a protected rebase-merged PR:** `references/protected-rebase-pr-delivery.md`
  — `gh pr merge` blocked with green checks usually means the PR is `BEHIND` (not a
  policy problem); `gh pr update-branch` → wait for the new run → re-check `CLEAN` →
  merge. After the rebase merge, `git pull --ff-only` fails → `git reset --hard
  origin/main`, and re-watch the post-merge `main` run because the rebase shifts the
  reviewed-scope SHA and can flip a ledger freshness test to `STALE_REVIEW`.
- Provider/auth smoke and 401 diagnosis: `provider-routing-safety`
  (incl. `references/api-key-401-stale-process.md`).
- Python/server test gotchas: `python-testing`.
- Design-system reference templates: `popular-web-designs` (bundled, read-only).
