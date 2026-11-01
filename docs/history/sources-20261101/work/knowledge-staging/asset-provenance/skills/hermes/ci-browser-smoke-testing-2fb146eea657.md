---
name: ci-browser-smoke-testing
version: 1.0.0
author: "UNKNOWN"
license: UNKNOWN
platforms: [windows, linux, macos]
workflow_software: hermes
archived_at: 2026-08-21
source_path: C:/Users/ALEX/AppData/Local/hermes/skills/software-development/ci-browser-smoke-testing/SKILL.md
---

---
name: ci-browser-smoke-testing
description: "Use when CI browser-smoke/E2E jobs fail or need coverage."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [windows, linux]
tags: [ci, playwright, browser-smoke, e2e, github-actions, accessibility, keyboard-testing]
metadata:
  hermes:
    tags: [ci, playwright, browser-smoke, e2e, github-actions, accessibility, keyboard-testing]
---

# CI Browser Smoke Testing

Use when a CI browser-smoke / E2E job fails, is silently skipped, needs new
coverage, or when adding Playwright tests that must pass in CI as well as
locally. Covers the environment traps that make CI differ from a local run,
gate-trigger mechanics, diagnostics without log access, and keyboard
accessibility testing. Validated on ArcheAxis-Knowledge-OS CI (2026-08-14/15,
first real browser-smoke execution after 15 historically-skipped runs).

## Core environment facts

1. **CI runs scripts with system python and NO project package.**
   `uv export --no-emit-project` + `python scripts/x.py` means
   `sys.path[0]` = `scripts/` and `import app.*` fails with
   `ModuleNotFoundError: No module named 'app'`. Scripts directly run by CI
   must anchor the repo root at the top (before any project import):

   ```python
   import sys
   from pathlib import Path
   sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
   ```

   If the repo has an architecture guard that whitelists sys.path mutations
   (e.g. `check_architecture.py` `_GRANDFATHERED_SYS_PATH_CALLS`), the new
   call must be added there with its exact `(path, lineno, mutation)` tuple
   or the lint job fails — and the lineno drifts if you edit the file later.
   Note `python scripts/x.py` does NOT put cwd on `sys.path`; `python -m app.x`
   DOES (cwd becomes `sys.path[0]`).
2. **Full Chromium vs headless-shell console noise differs.** CI installs the
   full browser; local may use headless-shell. Favicon 404s and other noise
   appear in only one of them. Assert on invariants ("at least one
   ERR_CONNECTION_FAILED exists"), never `all(...)` over console messages.
3. **Gate triggers are path-classified.** A `browser-smoke` job may only
   trigger on `app/workspace/ui/**` changes (see the repo's
   `.worklab/project-validation*.yaml` → `gates:` mapping, `scripts/ci/classify.py`).
   Script-only fixes will NOT retrigger it — use a harmless UI-file comment
   change to force a run. `CI_FORCE_FULL` needs a PAT (treat as unavailable);
   `full-qualification` is a logical RC-stage profile (AXC-060 pattern), never
   the unknown-path fallback — do not force it in dev.
4. **Diagnostics without log access.** No admin → GitHub logs API returns 403,
   and `gh` may be uninstalled. Surface failures via `::error::` workflow
   commands — they land in the checks API annotations:
   - smoke entrypoint: wrap `main()` in `_main()`; print
     `::error::SMOKE-FAIL: <type>: <msg>` on any exception before exiting 1;
   - pytest: add a `pytest_sessionfinish` hook in `tests/conftest.py` that
     prints `::error::PYTEST-FAILED <nodeid>` + `::error::PYTEST-FAIL-REASON`
     lines (see references for the hook).
5. **Reproduce CI locally before pushing (CI-SIM).** Create a separate venv,
   install the exact locked groups the CI job uses (`uv export --only-group
   ci --only-group browser --output-file reqs.txt` — Windows pip cannot read
   `-r -` from stdin), run the script from the repo root with plain `python`
   (no project package), and iterate until it passes there. One local
   round-trip beats three blind pushes. Local browser cache may be redirected
   into the project by the wrapper: run `playwright install chromium` /
   `chromium-headless-shell` (through the proxy if configured) before CI-SIM.
6. **Pick ONE interpreter model per job — venv vs `pip --system`, never a
   mix.** A smoke script that spawns `sys.executable -m <entrypoint>` (it
   starts its own server) inherits the interpreter it was launched under.
   Mixing models (deps in the venv via `uv sync`, but the script launched
   with system `python` because only the browser group was
   `pip install --system`) makes the spawned migrate crash with missing
   deps — `SMOKE-FAIL: CalledProcessError ... sys.executable -m
   app.runtime_entrypoint migrate` (LOG-167). A fast gate that installs
   everything with `pip --system` masks this; a nightly job that uses
   `uv sync` for some groups does not. For an all-venv job: `uv sync
   --frozen --group ci --group ci-adapters --group browser`, then run the
   smoke with `env -u PYTHONPATH uv run --frozen ... python scripts/smoke.py`
   so `sys.executable` IS the venv python. Verify locally with the EXACT
   command before dispatching.

## Smoke script hygiene

- **Idempotent**: clean state dirs at startup (stale DB/PDF state from a
  previous run poisons later sections — e.g. "persisted bindings are
  invalid" on a second run).
- **Real-browser exercises, not DOM-only assertions**: generate real fixtures
  (e.g. pymupdf PDFs with a searchable text layer), drive the UI (open →
  paginate → zoom → search → annotate → jump-back), assert on resulting UI
  state (anchors, page numbers, enabled buttons).
- Async search/select races: wait for the dialog event
  (`page.expect_event("dialog")`) rather than a fixed timeout — a
  re-rendered layer can clear the selection after your select.

## Keyboard accessibility testing (Playwright)

Prove keyboard-only flows with focus assertions, not tab counts:

- **Semantic audit first** (catches dead UI): every `input` needs
  `aria-label` or an associated `<label>`; icon-only buttons need
  `aria-label`; toggle buttons carry `aria-pressed`; all buttons need an
  explicit `type` (default `submit` is harmless outside forms but sloppy);
  error/status regions use `aria-live="polite"` (or `role="alert"` for
  urgent). Cross-check every `data-action` in HTML against JS bindings
  (bound via `dataset.action === 'x'` — search both quoted and unquoted
  forms), and scan for `disabled` buttons no code ever enables.
- **Dialog focus flow**: focus the trigger, press `Enter` → assert
  `document.activeElement` lands on the dialog's first input; `Tab` +
  `Shift+Tab` cycle inside (focus trap); `Escape` closes it and returns
  focus to the trigger (`document.activeElement.dataset.action`).
- **Drive with `page.keyboard.press(...)` after `.focus()`** — validates real
  key handling. For theme/toggle state, assert BOTH the `data-*` attribute
  and `aria-pressed`.
- **PDF reader controls are keyboard-reachable too** (AXW-096B): `focus()` +
  `Enter` on `#pdf-prev` / zoom buttons / the search Tab-chain, asserting the
  resulting UI state (page number flips, zoom % changes, search jumps to the
  match page). Three traps: (1) zoom buttons often have NO `id` — locate via
  `button[data-action="pdf-zoom-out"]`; (2) `page.keyboard.type()` APPENDS to
  whatever is already in the input — `fill("")` first or the query won't
  match and the search silently no-ops; (3) if search renders no DOM
  highlight (only jumps pages + alerts), assert the page-number jump, never
  a highlight element that cannot exist.
- Playwright locator note: assert `aria-hidden` state via
  `get_attribute("aria-hidden") == "false"` while the dialog is open.
- When a keyboard step times out, extend the failure `state_dump` with
  `activeElement` (data-action/id/tagName) and the input's `value` — one
  run then shows whether focus landed where you think or the value is
  double-entered instead of guessing blind.

## Feature reachability: library → API → UI (the 022B lesson)

A feature is not "done" when its library function exists — it must be
reachable by the user through the UI. Audit every new capability in three
layers and add UI coverage for the last one (validated 2026-08-14/15,
AXW-094A/B exchange/backup, AXW-096C batch control):

1. **Three-layer chain:** library function (unit-tested) → Workspace API
   endpoint (TestClient round-trip) → user-visible UI entry (browser-smoke
   clicks the real button). Audit every new capability across all three.
2. **Exercise pattern for UI entries — "never a dead button":** for each
   `data-action` button, click it and assert the result area transitions
   from its placeholder (`尚未执行...`) through the in-flight state
   (`执行中…`) to a CONCRETE verdict: either success JSON (`{`) or an
   explicit failure (`操作失败: ...` with the 422 detail). An empty store
   legitimately 422s ("nothing to export") — that is still a live round-trip
   verdict, not a dead button. Never assert "no error" on a button that
   errors by design; assert "the UI surfaced the API's verdict".
3. **The API surface needs user-facing buttons even when the acceptance
   criteria only mention the API** — reachability is the product's own
   bar; a feature visible only in docs is a dead feature (this is the
   AXW-022B PDF-annotate lesson generalized).

## SPA hash-routing trap (visible sections vs default page)

Single-page apps with multiple `<section class="page">` containers boot to a
DEFAULT section (e.g. `page-overview`); target content (PDF reader, exchange
card) lives in another section that is `display:none` until hash-routed
(`/workspace#evidence`). Traps when smoke-testing these:

- `page.goto(base_url + "/workspace/")` shows the DEFAULT page — headings in
  the target section will `wait_for()` TIMEOUT, and `body.innerText` EXCLUDES
  `display:none` content (so `innerText.includes('目标卡片')` returns False
  even though the DOM contains it — a confusing double-negative).
- Navigate with the hash the app itself uses (`#evidence`), and diagnose
  visibility explicitly per section:
  `[...document.querySelectorAll('section.page')].map(s => s.id + ':' + (s.offsetParent !== null))`
  — `offsetParent === null` means `display:none`.
- A heading that `wait_for()`'d on FIRST load does not prove the section is
  visible after a RE-navigation — re-assert section visibility after every
  `goto`. (Validated while adding an exchange/backup card to the Evidence
  page: first `goto` found the PDF card, a second `goto` of the same URL
  landed on overview and both cards vanished from `innerText`.)

## Pitfalls

- **GitHub API rate limit (403 `rate limit exceeded`)** on unauthenticated
  requests (60/hr per IP) can hit mid-debugging. Do not retry in a loop —
  check the run state via the browser instead: `browser_navigate` to
  `https://github.com/<owner>/<repo>/actions/runs/<run_id>` renders the run
  graph (per-job pass/skip status) and the "Status: Success" summary line
  without authentication. The page snapshot also shows skip reasons for
  gated jobs, which the API summaries do not.
- Only `app/workspace/ui/**` changes retrigger browser-smoke; push a UI
  comment change or accept the skip.
- Console-noise assertions on full Chromium fail on favicon 404s — assert
  invariants, not cleanliness.
- A script passing locally on headless-shell can fail on CI's full chromium —
  run CI-SIM with full chromium before pushing.
- `::error::` lines only help if they appear BEFORE the step's stdout is
  truncated; keep them short and put them at the failure point.
- Dependencies for the smoke job live in their own group (e.g. `browser =
  ["playwright>=1.61,<1.62", "pymupdf>=1.24"]`); changing group membership
  requires `uv lock` and may require refreshing the release manifest's
  `dependency_lock.digest` (sha256 of uv.lock) if the repo tracks it.
- **Never-run scheduled workflows carry dead selector defects.** A workflow
  that has "no runs yet" (nightly/schedule workflows — GitHub shows
  "This workflow has no runs yet.") has NEVER exercised its commands.
  Audit every job command BEFORE relying on it: 2026-08-15 the nightly
  browser-smoke job used `pytest tests/test_workspace_api.py -m "browser or
  workspace"`, but no test in the file had a marker and `pyproject.toml`
  registered none → ZERO tests collected → pytest exit 5 → the first real
  schedule run would have failed. Local-simulate every never-run job's exact
  command (compileall + the listed test files with the same flags) and check
  marker selectors against actually-registered markers (`grep pytest.mark`,
  `pytest --collect-only -q -m "<selector>"` and confirm nonzero collection).
  A fixed never-run workflow still only proves itself on its next real tick
  (e.g. the 03:17 UTC schedule) — say so in the report instead of claiming
  the run happened.
- **Schedule ticks can look SKIPPED — first verify timezone + file-add
  timeline; the "skipped tick" conclusion itself was once a misread.**
  A never-run `schedule:` workflow has three benign explanations before
  anything external. VERIFY ALL, in this order (2026-08-14/15, the nightly
  03:17 UTC case):
  1. **Timezone conversion — the #1 trap.** The Actions page displays
     LOCAL time (browser/committer tz, e.g. +08:00), while cron
     expressions are UTC. `03:17 UTC` = `11:17 +08:00`. An observation
     window at local 03:17-05:00 (UTC 19:17-21:00) never reached the
     tick — concluding "scheduler skipped" from that window is WRONG.
     Prove the page's timezone: `git log -1 --format=%cI <commit>` prints
     e.g. `2026-08-14T03:21:35+08:00`; if the Actions page shows the same
     wall-clock "03:21", the page is local-time. Relative times
     ("2 minutes ago") carry NO timezone — always cross-check with a
     commit timestamp.
  2. **File-add timeline.** `git log --format=%cI -- .github/workflows/x.yml`
     — if the workflow file was first added AFTER the last tick and the
     next tick hasn't arrived, "no runs yet" is fully explained: the file
     simply has never been present at a tick. No anomaly at all.
  3. **Default branch + cron validity.** `schedule` only fires for the
     default branch's file; confirm the default branch off the repo page,
     and confirm the cron string parses.
  Only after 1-3 all hold may the skip be attributed to GitHub's scheduler
  (documented as not-guaranteed) — record it once in the status log and
  STOP re-checking; `workflow_dispatch` needs auth. If a prior session
  concluded "skipped tick" without step 1, treat that conclusion as
  suspect and re-derive it (this skill's earlier wording was corrected
  after LOG-161 retracted exactly such a misread).

See `references/ci-browser-smoke-recipes.md` for the full debugging recipe:
sys.path whitelist entry format, pytest_sessionfinish hook, CI-SIM venv
setup, gate-trigger mapping, and the PDF-reader exercise skeleton.
