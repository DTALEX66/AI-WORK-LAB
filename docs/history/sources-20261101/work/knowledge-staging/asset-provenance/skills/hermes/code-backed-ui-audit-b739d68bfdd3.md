---
name: code-backed-ui-audit
version: 1.0.0
author: "UNKNOWN"
license: UNKNOWN
platforms: [windows, linux, macos]
workflow_software: hermes
archived_at: 2026-08-21
source_path: C:/Users/ALEX/AppData/Local/hermes/skills/quality-assurance/code-backed-ui-audit/SKILL.md
---

---
name: code-backed-ui-audit
description: Read-only UI/UX audits for web games and applications where browser behavior must be reconciled with source, assets, responsive CSS, tests, and alternate runtimes such as Canvas, WebView, or mini-game platforms.
version: 1.0.0
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [ui-audit, ux, responsive, canvas, webview, accessibility, read-only]
---

# Code-Backed UI Audit

Use this skill when a UI/UX review requires both live visual inspection and source-level evidence, especially for games with DOM, Canvas, mobile WebView, or mini-game builds.

## Core principle

Do not equate “selector exists,” “test passes,” or “asset is referenced” with a working experience. Reconcile four layers:

For a user-facing observer, dashboard, or status surface, add a fifth non-negotiable layer: **the user-visible entry and its visual language**. A skeleton, projection function, or passing test is not an observable product until a documented start command, URL/route, and real browser/runtime smoke exist. Preserve the approved design direction from handoff (for example, Apple whitespace/glass navigation, Linear precision dark surfaces, or Vercel restrained boundaries); do not substitute a generic admin template or a decorative gradient. Capture both semantic/browser evidence and a visual screenshot, and make the page's truthful boundary explicit (read-only, unverified, partial, or live).

1. intended design contract and handoff documents;
2. effective source behavior after cascade/runtime logic;
3. actual browser/device geometry and visual states;
4. parity across packaged runtimes.

## Read-only discipline

1. Record the initial repository status before running commands.
2. Inspect test/build scripts for writes before executing them. Test suites may regenerate tracked bundles or copied platform assets.
3. Prefer non-writing checks where possible.
4. If the request is specifically for the **staged diff**, treat the Git index—not the working tree—as the source of truth. Export it with `git checkout-index --all --force --prefix="C:/.../staged-review/"` (the trailing slash is required), then run tests and builds in that temporary copy. This prevents concurrent editor or agent changes from contaminating the audit.
5. If an authorized verification command rewrites generated files during a read-only audit, record the generated diff as evidence if relevant, then restore only those side effects and verify the final repository status matches the initial state.
6. Never leave reports, screenshots, generated bundles, or formatting changes inside the audited repository unless explicitly requested.
7. When comparing tracked generated bundles to a clean rebuild on Windows, distinguish semantic drift from CRLF-only drift: use `diff --strip-trailing-cr` or hash streams after removing `\r`. A raw SHA-256 mismatch alone is not evidence that the bundle is stale.
8. When the user prohibits **any** writes, inspect test entrypoints before running them. Do not run a smoke suite that migrates, writes fixtures, or writes an isolated data directory merely because it cleans up afterward. Instead, for a focused DOM/accessibility behavior proof, run a real headless browser entirely in memory: read HTML/CSS/JS from the audited index/tree, fulfill page/assets/API requests with Playwright routes, and close the browser. Report that this is an in-memory staged-browser proof, not a full persistence/runtime smoke.

## Audit workflow

### 1. Inventory and contracts

- Identify H5/DOM, CSS, game/runtime state, Canvas renderer, platform entrypoints, packaging scripts, asset manifests, handoff documents, and responsive tests.
- Extract explicit claims: one-screen layout, minimum touch size, primary visual surface, platform parity, orientation, safe-area behavior, and required flows.
- Note contradictory documents instead of silently choosing one.

### 2. Effective source review

- Read the end of long CSS files: later override passes often invalidate earlier responsive rules.
- Trace state → visual model → DOM/Canvas output rather than checking class names alone.
- Check success, failure, not-started, anomaly, ad/reward, empty, and modal states.
- Treat source-string tests as contract smoke tests only; they do not prove the winning CSS declaration, rendered geometry, or click behavior.
- Audit delegated event handlers in ancestor order. A broad early selector can consume unrelated actions when a container carries the same attribute—for example, `event.target.closest('[data-theme]')` matches `body[data-theme]` for every click. Match the actionable element (`button[data-theme]`) or bind explicit handlers, then prove nav/modal/refresh controls with real clicks.
- **Dead-feature static cross-checks** (fast screen before browser work; a feature can be fully "implemented" in source yet unusable — e.g. an annotation button hardcoded `disabled` with NO enablement logic anywhere because the dependent capability was impossible):
  - Every `data-action="X"` in HTML must have a handler. Beware two binding styles: event-delegation `switch (el.dataset.action)` cases AND `if (action.dataset.action==='X')` chains — grep the bare action name (no quotes) to catch both, then verify each handler exists.
  - Every `disabled` button in HTML must have JS that clears `disabled` on some event/state. A permanently-disabled button with no enablement code is a dead feature.
  - Every `getElementById(id)` in JS must have a matching `id=` in HTML.
  - **Canvas-rendered content is not selectable text.** Any feature needing text selection/annotation (PDF evidence pinning, quote extraction) requires an overlay text layer (PDF.js: `getTextContent` spans positioned via `Util.transform(viewport.transform, item.transform)`); canvas alone silently breaks every selection-dependent feature. Verify by selecting in a real browser, not by reading code.
- For status dashboards, intercept partial HTTP 200 responses and wrong types after first rendering a valid state. Verify every dependent panel clears old values and becomes unavailable. For transport-failure tests, distinguish the one expected browser resource error caused by deliberate request abort from unrelated console/page errors, which must remain zero.
- Triangulate status contracts across **renderer reads → client normalization → production composition**, not merely renderer tests. Build an exhaustive field-path inventory from the active renderer, map every path to the normalized surface, then verify whether the real composition root emits it. Classify mismatches precisely: absent field, emitted-but-always-null/default, unhandled real enum, or source fact stored but not joined into the public projection.
- When a documented read-only endpoint descriptor exists, prefer a live GET of the currently running projection over fixtures before judging long-lived `UNKNOWN`, `0/0`, or empty cards. Render that real payload through the actual normalizer/renderer and record the resulting visible text; synthetic unit fixtures can otherwise prove a fantasy contract.
- Audit formatter/helper reuse for hidden sibling dependencies. A shared transport formatter that renders both transport and freshness will add a misleading extra `UNKNOWN` when a row supplies only transport. Likewise, verify stale/last-good transitions update the same status model the active renderer reads; updating a legacy `freshness` object does not make a v3 `transport` bar stale.

### 3. Live visual baselines

Capture at least:

- desktop initial state;
- desktop active/error/anomaly state;
- 390×844 portrait;
- 360×640 small portrait;
- open modal/bottom sheet;
- success and failure outcomes when reachable.

For visual gameplay, compare calm and active states. Query computed opacity/display/background values for each supposed anomaly layer. A normal state that already shows the clue is a gameplay defect, even when the active state adds more noise.

For Canvas games whose acceptance captures come from a browser harness, verify the harness actually loaded real image assets before trusting any screenshot: diff the scene region across two or more states — pixel-identical regions (diff ≈ 0) across supposedly different states mean procedural fallback art, not asset proof. Trace the renderer's image factory: if it only probes host APIs (`tt.createImage`/`wx.createImage`/`canvas.createImage`), a plain-browser harness loads zero images regardless of how complete the manifest and preload calls look. Screenshot byte size is a useful tell (identical or near-identical bytes across states), and a `document.documentElement.dataset` probe with `naturalWidth` confirms the load path.

When no image-analysis/vision channel is available for screenshots or bitmaps, substitute quantitative PIL probes — edge-band luminance (black-border/letterbox detection), per-region luminance stats, pairwise pixel diff with bounding boxes, and cross-image HUD-zone edge density — and declare the evidence boundary explicitly in the report rather than claiming visual confirmation.

### 4. Geometry evidence

Use browser-evaluated `getBoundingClientRect()`, computed styles, viewport size, `scrollWidth`, and `scrollHeight`. Report exact evidence such as:

- viewport and document height;
- y-position of primary action/start control;
- rendered button width/height;
- panels below the fold;
- horizontal overflow;
- modal bounds relative to viewport.

### Responsive drawers: semantic hiding is not visual hiding

For breakpoint-controlled drawers, inspectors, and side panels, pair semantic
checks with a final-layout geometry check. A desktop collapse selector can have
higher specificity than a mobile off-canvas selector, leaving a visible but
`inert`/`aria-hidden` strip that users cannot operate.

1. Reproduce each transition direction in the same page: mobile closed → desktop,
   then desktop collapsed → mobile. Inspect the final `aria-hidden`, `inert`,
   trigger visibility, and actionability after each change.
2. In the mobile closed state, evaluate `getBoundingClientRect()` and require the
   panel's left edge to be at or beyond `window.innerWidth` when the contract is
   fully off-canvas. Check the external reopen control can actionably reopen it.
3. Inspect CSS specificity and source order. A breakpoint-scoped override should
   match or exceed the desktop collapsed selector rather than relying on a weaker
   `.panel` mobile rule.
4. Geometry sampled immediately after a resize can be an animation intermediate
   frame. If supported, emulate `prefers-reduced-motion: reduce` before the page
   is loaded, or await a stable observable completion condition; do not mistake a
   transitioning `transform` for a cascade failure.
5. When a repair changes the reviewed tree, freeze a new tree and repeat the
   targeted browser proof and independent review. Prior GO results do not carry
   across the new tree.

An iframe with an explicit width/height is a practical responsive probe when the browser tool cannot resize its outer viewport. Inspect the iframe document directly rather than judging only from a scaled screenshot. For observation games, measure the effective visual scene after captions/HUD—not only the outer panel—and compare nearby height classes to catch responsive cliffs where a fractional feed row absorbs all compression.

When checking supposedly hidden anomaly layers, record both computed opacity and `animation-name`: keyframes that animate opacity can override a static `opacity: 0` and leak clues into the clear baseline.

### 5. Platform parity

Build a matrix for each runtime covering:

- start gate and timer behavior;
- visible/available actions and grouping;
- touch hit regions;
- visual assets and anomaly identity;
- success/failure outcomes;
- accessibility/keyboard semantics;
- ads and reward gates;
- audio, analytics, persistence/archive;
- orientation, safe areas, and back navigation.

For fixed-design Canvas, convert design-pixel hitboxes into expected on-screen CSS pixels. A 40px design-space button on a 750px canvas displayed at 375px is only about 20px tall unless layout/scaling compensates.

### 6. Assets

- Verify dimensions, byte size, hashes, runtime references, package-copy lists, and visual content.
- For PNGs, also inspect color mode, alpha extrema, nontransparent bounding boxes, and transparent/partial/opaque pixel ratios. These expose hidden backdrops, clipped glows, inconsistent padding, and state-anchor jumps.
- Distinguish intentional state variants from duplicates using image comparison plus visual review.
- Identify assets referenced only by inactive skins or documentation and quantify package cost. Also grep the runtime render path for actual call sites of every manifest/preload getter: exported-but-never-called asset groups are dead package weight, and with `subPackages: []` the whole output directory counts as the platform main package (WeChat 4MB main / 20MB total) even when a project's own total-size budget passes.
- Check that normal assets do not already contain anomaly clues, baked text, watermarks, fake UI, fixed timecodes, camera IDs, floor IDs, or localized counters.
- Do not treat a contact sheet as a runtime atlas unless it has explicit frame coordinates or a verified uniform grid. Mixed frame sizes, preview labels, and irregular gutters are disqualifying.
- Check whether base monitor images already bake in the same frame, scanlines, vignette, glitch, or alert treatment shipped as overlays; double composition can darken clues, create moire, or duplicate HUD.
- Compare wide and mobile aspect ratios and, when relevant, pixel-test whether the mobile version is a deterministic crop/resize. Independently exported variants do not guarantee shared overlay coordinates.
- Separate “technically drawable with `drawImage`” from “safe as an observation baseline.” In find-anomaly games, explicit state labels may make an otherwise valid bitmap usable only for feedback or debugging.

### 7. Accessibility and feedback

Check focus visibility, keyboard completion, dialog semantics, focus trapping/restoration, reduced motion, live regions, color-only signals, touch target size, and Canvas alternatives. Verify that hints do not contradict rules or reveal the answer before the player observes the visual state.

For controls that trigger whole-root re-rendering, test focus with a real browser: focus the control, activate it, then inspect `document.activeElement`. Replacing the focused node commonly drops focus to `body` even when an identical button is rendered immediately. Require explicit focus restoration to the replacement control (or update the DOM without replacing it), and include both keyboard activation and assistive-name readback in the regression gate.

### 8. Windows Tauri WebView evidence boundary

When auditing a Windows Tauri shell, separate launch, render, interaction, and same-WebView readback evidence. A Tauri EXE starting, WebView2 rendering, a loopback HTTP probe, a headless Chromium Playwright test, or a screenshot alone does **not** prove real WebView interaction. Confirm which page is actually loaded: `frontendDist` may be a bootstrap placeholder while Rust redirects the runtime window to an external Loopback Workspace URL. Inspect the real UI source and action handlers, then use a true window/WebView automation channel for click → refresh → UI readback. If Windows UIAutomation exposes only `WRY_WEBVIEW`/`BrowserRootView` panes, do not infer that HTML buttons are available. Record the automation-channel blocker and use a fresh session or an explicit WebView2 DOM/CDP harness; never convert a browser smoke into Tauri evidence. See `references/tauri-windows-webview-evidence.md` for the evidence matrix, probes, minimal flow, and CI boundary.

## Reporting

Sort findings by user impact, not file order. For every issue include:

- severity and concise title;
- exact source/runtime evidence;
- user impact;
- concrete repair direction;
- measurable acceptance criteria.

Always distinguish verified facts from untested areas such as real-device installation or platform developer-tool execution. Include positive findings and final repository cleanliness.

See `references/staged-index-audit.md` for a staged-only export/test/rebuild recipe that remains correct when the working tree changes concurrently and when Windows line endings differ.

See `references/game-ui-platform-audit.md` for a condensed checklist and common failure patterns.

See `references/canvas-asset-suitability.md` for a focused Canvas asset-pack audit checklist covering alpha bounds, baked UI/text, atlas validity, duplicate overlays, mobile crop consistency, and the distinction between drawable assets and gameplay-safe observation baselines.

See `references/canvas-minigame-platform-bundle-audit.md` for read-only微信/抖音 Canvas 审计：主包/总包实测、残留输出、V5 内容字段真实接线、设计像素到触控像素换算、acceptance harness 证据门禁和 decoded-memory 估算。

See `references/mobile-cctv-control-audit.md` for exact portrait viewport probes, responsive-cliff detection, animation-leak checks, control-frequency analysis, settlement geometry, Canvas scaling, and text-baked asset pitfalls.

See `references/operational-truth-status-ui.md` when auditing dashboards that claim live counts, service health, job progress, provider availability, audit events, or successful controls. It covers frontend-call inventory, persisted-state-versus-active-service distinctions, minimal truthful status contracts, fail-closed UI wiring, public-brand/internal-term checks, concurrent-tree drift, and regression-test patterns.

See `references/observer-sidecar-sse-audit.md` for read-only release probes spanning telemetry ownership, sidecar startup locks, GET-path mutations, exact Origin/loopback controls, raw SSE framing and `Last-Event-ID`, rendered stale/offline truth, and CI-watcher degradation coverage.

See `references/observer-frontend-reconnect-negative-controls.md` for deterministic in-memory frontend probes covering rendered last-good downgrades, partial/old HTTP 200 rejection, named-event refresh coalescing, real cursor/backoff sequences, hidden multi-WebView connection ownership, and candidate-identity changes during concurrent review. Prefer these behavior probes over source-regex assertions.

See `references/observer-sse-resync-webview-ownership.md` for the server/client edge cases that ordinary reconnect tests miss: convergent `resync_required` cursors, hidden-WebView contamination of LIVE truth, and atomic snapshot/events endpoint identity changes.

See `references/observer-render-contract-triangulation.md` for snapshot-dashboard audits and repairs that reconcile production writers/collectors, canonical storage, composition, client normalization, active renderer reads, and a real loopback payload. It distinguishes schema/test-only capability from production observability, covers absent/default-only/stored-not-projected/writer-not-wired/sample-empty fields, defines remove-versus-conditionally-render decisions for repeated `UNKNOWN`/`0/0`, and closes with packaged Tauri/WebView/CDP readback rather than fixture-only proof.

See `references/truthful-job-center-audit.md` for a focused source-and-contract audit of Job Centers, unified audit timelines, and SSE. It distinguishes persisted synchronous Job/Outbox facts from active worker execution, derived per-case audit from a unified append-only timeline, and snapshot polling from replay-safe realtime streaming; it also defines the smallest safe redacted Job Center slice when no real cases are available.

See `references/browser-truth-boundary-regression-probes.md` when a green browser smoke must be checked for product-boundary false positives. It covers page-versus-nav counting, wire-level internal-ID scans, per-operation partial-2xx validation, stale/out-of-order refreshes, fixed-child clipping that document `scrollWidth` misses, modal focus behavior, stateful hash sequences, exact desktop/mobile geometry, and requirement-to-test coverage matrices.

See `references/playwright-regression-gate-pitfalls.md` when authoring or extending a real-browser regression gate (Playwright smoke) for a workspace/evidence UI. It captures the dead-PDF-annotation case, the static dead-feature scan, async-search dialog waits, selection-caching on button mousedown, page-variable shadowing, full-Chromium-vs-headless-shell divergence, idempotent data-root cleanup, and CI sys.path anchoring for scripts run without the installed project package.

See `references/douyin-minigame-product-review.md` when judging whether a Douyin mini-game is ready to submit. It adds first-run gating, real find-anomaly decision chains, rewarded-ad pause semantics, `tt.onHide`/`tt.onShow` lifecycle probes, sidebar/share/audio checks, privacy and minor-safety evidence, and fail-closed Douyin artifact gates. Treat an H5 start overlay or green unit tests as insufficient evidence for the Canvas mini-game runtime. For generated bundles, instrument only an in-memory copy to expose the runtime, then exercise full ad-close callbacks and 60-second/failure/revive paths; startup smoke alone can miss stripped-import `ReferenceError`s.