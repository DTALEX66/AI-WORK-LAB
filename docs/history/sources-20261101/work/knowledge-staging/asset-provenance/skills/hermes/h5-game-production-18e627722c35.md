---
name: h5-game-production
version: 1.0.0
author: "UNKNOWN"
license: UNKNOWN
platforms: [windows, linux, macos]
workflow_software: hermes
archived_at: 2026-08-21
source_path: C:/Users/ALEX/AppData/Local/hermes/skills/software-development/h5-game-production/SKILL.md
---

---
name: h5-game-production
description: "Use when building or iterating on H5/Canvas indie games with AI. Covers phase-prioritized development (P0→P3), design-first workflow, architecture patterns, and platform adaptation for WeChat/Douyin mini-games."
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [game-dev, h5, canvas, indie-game, skinning, mini-game, iad]
    related_skills: [plan, codebase-inspection, systematic-debugging]
---

# H5 Indie Game Production System

## Overview

Build and iterate on single-player H5 Canvas indie games with AI assistance. The methodology prioritizes fast MVP delivery → monetization → skinning → platform expansion.

**Core principle:** The game is not a single title but a **reproducible production system** for generating IAA-monetized mini-games.

## When to Use

- Starting a new H5 Canvas game project
- Iterating on an existing game (new features, balance, content)
- Preparing for WeChat/Douyin mini-game deployment
- Adding IAA (激励视频广告) monetization
- Creating a skinning system for game template reuse

## Phase Framework (P0→P3)

Every feature falls into one of four phases. Work through them in order — each phase unlocks the next.

| Phase | Focus | Gate |
|---|---|---|
| **P0** | MVP polish: configurable balance, event variety, audio/visual feedback | MVP design doc's acceptance criteria all met |
| **P1** | Monetization loop: hidden logs (ad unlock), fake endings (consecutive failure → ad truth) | At least 2 ad touchpoints working |
| **P2** | Skinning system: externalize ALL content text to skin JSON, skin manager, second skin proof | Second skin loads with zero code changes |
| **P3** | Platform adaptation: Canvas renderer, platform abstraction (wx/tt/browser), build script | Mini-game project opens in dev tools |

## Workflow (per phase)

For the compact evidence contract used by unattended or “继续下一步” iterations, load [`references/evidence-driven-game-iteration.md`](references/evidence-driven-game-iteration.md). It complements the deeper overnight-loop reference by emphasizing full data→scheduler→runtime→renderer reachability and generated project-config authority.

### 0. Active skill/plugin use during autonomous loops

When the user says "继续", "开启循环", "睡觉模式", or asks to keep advancing autonomously, do not merely mention skills. Actively load and apply the relevant skill(s) at each phase boundary:

- `h5-game-production` for game-production cadence and platform gates.
- `project-gap-analysis` when choosing the next real task from design-vs-implementation gaps.
- `systematic-debugging` when a test/build/runtime symptom appears; build a tight feedback loop before fixing.
- GitHub workflow skills when committing/pushing/PR work is part of the task.

A loop iteration should be: skill context → scan real evidence → pick one task → implement → run the acceptance gate → commit/push.

**Sleep-mode / autonomous loop pattern:** when the user says "睡觉模式" or "开启循环" + "跑通为止", follow a pre-defined roadmap (e.g. `docs/NEXT_TASKS.md`) and work through tasks one by one without waiting for user steering. Each task follows: load relevant skills → implement → test → commit → push → verify sync. A `todo` list tracks progress across rounds. Stop only when the roadmap is exhausted or the user interrupts.

### 1. Analyze Current State
```
- Read PROJECT_CONTEXT.md, GAME_DESIGN.md (project docs)
- Read all src/*.js to understand what's implemented
- Compare against design doc's acceptance criteria
- Check repository entrypoint docs (README, platform README, handoff docs) for drift against shipped commands/features
- Report: what ✅ exists vs what ❌ is missing
```

### 2. Design First
```
- Write docs/P<N>_<DESCRIPTION>.md before any code
- Cover: data design, interaction flow, UI changes, config changes
- Include acceptance criteria checklist
- Keep it actionable (not academic)
```

### 3. Implement (One Feature at a Time)
```
- For each design item:
  1. Update gameConfig.js if balance parameters change
  2. Update state.js if new state fields needed
  3. Update actions.js / events.js / feedback.js for logic
  4. Update game.js for UI binding
  5. Update index.html + styles.css for DOM changes
  6. Update tests
  7. Verify: node -e "import(...)" for module loading
```

### 4. Test
```
- Run: node -e "global.structuredClone=obj=>JSON.parse(JSON.stringify(obj)); Promise.all([import(...)]).then(...)"
- Verify all modules load, exports match expectations
- For Node 16 (no --test): manual assertion via node -e
```

### 5. Git Commit
```
git add -A && git commit -m "feat(P<N>): <short description>

=== P<N> — <phase name> ===

Bulleted details of each sub-feature"
git push
```

## Architecture Patterns

### Core Systems (keep separate modules)

```
src/
├── gameConfig.js    ← Balance parameters (ONE config source)
├── state.js         ← State machine: init, clone, tick, failure, snapshot, revive
├── actions.js       ← Action system: performAction(), AVAILABLE_ACTIONS[]
├── events.js        ← Event system: anomaly definitions + apply/pick logic
├── feedback.js      ← Feedback: log formatting, failure summary, tone detection
├── game.js          ← Game loop + UI binding (DOM or Canvas)
├── audio.js         ← Web Audio API procedural sounds
├── skinManager.js   ← Skin loader + t() template string replacement
└── skins/
    ├── elevator/skin.json  ← Skin A
    └── security/skin.json  ← Skin B
```

### Skinning Rules

1. ALL display text goes in skin JSON (never hardcoded in JS)
2. `skinManager.t('dot.key.path', {param})` for template strings
3. Game logic stays in JS (state machine, conditions, calculations)
4. Second skin must prove zero code changes

### IAA Ad Touchpoints

| Type | Trigger | Ad Unit |
|---|---|---|
| Revive | Game over → click revive | Rewarded video |
| Hidden log | Anomaly trigger → locked log | Rewarded video |
| Fake ending | Consecutive failures → truth | Rewarded video |

### Platform Abstraction (P3)

```
platform/
├── platform.js          ← Unified API: env detection, ads, storage, canvas, touch
├── canvasRenderer.js    ← Canvas rendering (replaces DOM for mini-games)
└── build.js             ← ESM → IIFE bundler for WeChat/Douyin
```

## Common Pitfalls

1. **Skipping the design doc.** Always write docs first — the model's implementation quality drops without design context.
2. **Modifying more than one thing per commit.** One feature = one commit. Keeps rollback clean.
3. **Hardcoding text in JS.** Every string should live in a skin JSON or gameConfig. Replace strings while you're touching the file.
4. **Forgetting the skin lookup for `emergencyStop_fail`.** It's easy to add a fail variant for an action but forget the corresponding skin key.
5. **Node 16 test limitations.** If the repo provides a compatibility launcher such as `npm test`, `scripts/run-tests.cjs`, or `npm run verify`, use that first so the project can route to a modern bundled Node. If no launcher exists, use `node -e` with `global.structuredClone` polyfill instead of `node --test`.
6. **StructuredClone in objects.** The effects-based anomaly system (events.js) must use `clamp((next[field] ?? 0) + value, 0, 100)` not `structuredClone` + assignment, because the state object is shared.
7. **Mixing dev verification with release credentials or project identity.** Keep `npm run verify`/local acceptance green without secrets, and add a separate release gate that fails on placeholder AppID/adUnitId. Store tokens, secrets and ad-unit configuration in ignored private overlays. However, do not assume `project.private.config.json` alone controls the Douyin Developer Tool: if the build keeps regenerating the main `project.config.json` as `touristappid`, UI edits are overwritten and the tool can remain in Lite mode. When a local release overlay supplies a real AppID, propagate that public project identifier into the generated main project config as well, while retaining a tourist fallback for CI/fresh clones. See `references/douyin-project-config-authority.md`.
8. **Fresh clones may miss ignored portable Android toolchains.** If `npm run verify` fails with `.tools/java/jdk-17`, `.tools/android-sdk`, or `.tools/gradle/gradle-8.10.2` missing, restore/install the ignored `.tools/` stack before judging the repo broken: JDK 17, Gradle 8.10.2, Android commandline-tools, `platform-tools`, `platforms;android-35`, and `build-tools;35.0.0`. On Windows Git-Bash, avoid piping `yes` into `sdkmanager.bat` via `cmd.exe` (it can loop with `'y' is not recognized`); either pre-create SDK license hash files or call the SDK manager Java main directly from Git-Bash.
9. **Self-contained schema validators.** When adding validation for JSON data (skins, configs, content packs), write a lightweight inline validator that walks the schema object tree — do not pull in `ajv` or other npm deps. The validator lives in `scripts/validate-<thing>.mjs` and is invoked via `npm run <thing>:check`. This keeps `npm install` unnecessary and CI lightweight.
10. **Skin data shape surprises.** Hidden logs are often keyed objects (by anomaly ID), not arrays. Effects fields like `floor` can be strings (e.g. `"+4"`) rather than integers. Adjust the schema to match the actual data, not the other way round.
11. **Reward wrappers bound to mutable global attempts.** A persistent SDK handler that reads a replaceable `attempt` variable can let a delayed callback from attempt A settle attempt B. Bind handlers to immutable per-attempt objects, clean them up at settlement, propagate a run-generation token, and revalidate the requested reward against current state. Use the retained-old-handler probe in `references/settlement-ads-and-artifact-review.md`.
12. **Derived visual state that one renderer ignores.** Calling a shared `deriveVisualState()` is not integration evidence. Verify every renderer actually consumes important outputs such as `cctvState`, terminal result, tone, and highlighted action; add pure treatment/mapping tests plus source or behavior tests for DOM and Canvas paths.
13. **Treating a generated PNG pack as runtime-ready because it has a `Transparent_PNG` folder.** Audit logical duplication, effective alpha bounds, border contact, hidden RGB under alpha 0, baked pseudo-text, dimensions, and decoded GPU cost before import. "Text-free" is not the same as "production-safe"; if every candidate is clipped or lacks alpha-safe padding, report zero direct-safe candidates and separate any repair-only shortlist. Use `references/png-ui-asset-pack-audit.md` for the deterministic audit and reporting method.
14. **Serializing a broad release effort that has independent audits.** At kickoff, dispatch parallel read-only workers for generated-bundle/runtime review, official release/compliance review, and gameplay/UX review while keeping all shared-tree edits in one main thread. Do not wait until final verification to parallelize: late findings such as omitted callback dependencies can invalidate an apparently green bundle. Continue implementation and tests in the main thread while workers run, then reconcile their evidence before commit.
15. **Passing startup smoke while delayed platform paths are broken.** Generated-bundle smoke must exercise Touch fields used by the target (`screenX/screenY` as well as compatible fallbacks), completed/cancelled/error rewarded-ad callbacks, active ad pause/resume, terminal-state precedence, and mandatory capability probes such as Douyin `checkScene` before `navigateToScene`. Static keyword checks are supplemental, never sufficient.
16. **Treating a private AppID overlay as archive proof, or deleting shared generated assets during parallel tests.** Patch the archived `project.config.json` in memory from the ignored private config, reopen the ZIP and assert identity, then remove all synthetic release artifacts and regenerate the public tourist project. Make generated-asset copying concurrency-safe (lock, isolated temp output, or overwrite-plus-stale-cleanup) instead of recursively deleting a directory another test may be using. See `references/douyin-generated-bundle-audit.md`.
17. **Adding an asset-loader import without closing the custom-bundler and copy pipeline.** If the bundler strips ESM imports, the loader module must be ordered before the renderer in the generated IIFE; every manifest path must also be copied into the package. Audit reachable state IDs instead of copying an entire art pack, measure decoded RGBA memory as well as PNG bytes, avoid duplicating baked overlays, inject `api.createImage()` from the same host that created the Canvas, and retain a procedural fallback for pending/error loads. See `references/douyin-canvas-asset-integration.md`.
18. **Replacing supplied production art with a code-drawn placeholder without explicit approval.** Package-size, alpha-bound, or baked-text findings justify processing and selection—not silently discarding the user's visual direction. Treat provided UI/component assets as an acceptance requirement: inventory them, classify direct/repair/reference-only candidates, crop/compress/atlas or load on demand, map each shipped state/action, and prove use with an official Developer Tool or device screenshot. A green test suite and a procedural fallback do not establish visual completion. If only a subset can ship, report exactly which assets are live and why the rest are excluded.
19. **Integrating assets while preserving the inferior old layout.** Drawing supplied PNGs is not art-direction compliance. Compare the target against the strongest supplied/H5 reference and preserve its hierarchy: dominant play surface, compact primary action deck, contextual recommended action, paged secondary controls, short telemetry/log regions, semantic sprite mapping, aspect-safe image cropping, and host-chrome clearance. Never use a mismatched action sprite as generic decoration or paint over the authored component until its design disappears. When the user rejects the visual result, acknowledge the composition failure before discussing tests or package size, then iterate from official-tool screenshots. Use `references/canvas-ui-art-direction-recovery.md`.
20. **Calling a static state-image swap “CCTV animation” or “publishable”.** A manifest, `deriveVisualState()` mapping, 60 FPS redraw, green tests, and one screenshot do not prove visible machine behavior. Audit reachability and precedence of intermediate states, ensure movement terminates, lock stacked actions while preserving emergency interruption, and pause the motion timeline with lifecycle/ads. The sampled motion object must carry the pausable frame timestamp into the renderer: direct `Date.now()` calls in scanlines, tears, jitter, reticles, or fallback art let effects run behind ads and jump on resume even when transition progress is paused. In the official target runtime, capture pre/intermediate/final/recovery frames and inspect the door/floor/entity/light subject—not merely noise, borders, logs, or labels. Mask baked answers and fixed floor values, replacing them with runtime-owned clues before classification. When challenged on visual quality, lead with the visual defect and evidence; do not answer with package size or unit-test counts. Use `references/cctv-motion-and-state-transition-validation.md`.
22. **Normal variants that share anomaly surface features.** When an anomaly is defined by screen-vs-panel conflict (e.g. CCTV shows floor 13 but panel says floor 1), include normal variants that share the same floor number (13) with data consistent. This prevents players from pattern-matching on a single surface value. Test that at least one normal variant floor overlaps with anomaly floor ranges. See `references/anomaly-content-schema.md`. Four permanent hardware keys, telemetry grids, multiple meters, logs, micro-English, and paged controls may be technically reachable yet fail mobile comprehension. Convert design coordinates to CSS pixels before approving legibility; make one dominant play surface, one sentence rule, 2–3 comparable readings, two thumb-sized decisions, and one-line feedback. The first run must use a deterministic progression: guided normal → fixed concrete anomaly → unhighlighted independent judgment, with non-punitive retries on the first two and state-machine tests proving the tutorial exits. Run the same sequence with **zero player input**: normal-teaching timeout must still lead to the fixed anomaly, anomaly timeout must auto-resolve and clear `activeAnomaly`, and the third class must appear neutral and unprompted. A pure expiry unit test is insufficient—execute the generated bundle with an injectable clock to prove scheduling continues. If observation/classification is the core fun, auto-execute the mapped operational response after classification instead of adding a low-value second control layer; reserve complex treatment for an advanced mode. Do not let titles, red frames, anomaly-only sounds, resource drops, recommendation keys, stale feedback, an uncleared anomaly, or residual glitch/reboot motion behind the next normal class or settlement reveal or contradict state. Reference art compliance means reproducing hierarchy, material weight, spacing, and button count—not merely its palette. When the user says the result is small, abstract, AI-like, or ignores references, acknowledge the product/composition failure and rebuild before citing tests. Keep release notes, store copy, and actual review screenshots synchronized with the rebuilt loop. Use `references/portrait-observation-minigame-ux-recovery.md`.

23. **Custom IIFE bundlers need both dependency ordering and module lexical isolation.** Regex-stripping ESM means every dependency still must be registered before its consumer, but concatenating all stripped bodies into one scope creates a second failure mode: private top-level `const`, `let`, or `class` names can collide as modules are added. Do not “fix” this by converting declarations to `var`, which permits silent overwrites. Emit each JS module in its own lexical block, capture its declared exports into a module-unique export bag, then lift only public bindings for later modules. Preserve default identifier exports and `export { local as exported }`, and explicitly handle import aliases that previously relied on the shared scope. Acceptance must execute the generated target bundle in a VM/host mock and call exports from multiple modules; syntax checks and source-string assertions alone are insufficient. Rebuild and stage tracked platform bundles explicitly, and verify the documented modified-file list against `git status`. See `references/custom-iife-module-scope-isolation.md` for the implementation and TDD pattern.

24. **Anomaly-content-driven visual state delegation.** When visual states are sourced from anomaly content data (screenData/panelData/primaryConflict), the visualState module should delegate to the content module rather than maintaining a parallel map. `visualState.js` calls `getAnomalyCctvState(anomalyId)` from `anomalyContent.js` instead of maintaining its own `ACTIVE_ANOMALY_CCTV_STATES` map. Keep legacy fallback maps only for anomalies defined outside the content schema (cross-skin anomalies not yet migrated). Add CSV-like content validation tests that verify every anomaly's visualState maps correctly via `deriveVisualState()` with the anomaly active — a single async test loop across all anomalies catches regressions before bundle smoke. The `normalVariant` field on each anomaly entry also serves as a preservation hint: what the CCTV should show when that floor/state is normal.

25. **CCTV animation assets can contain baked floor numbers that conflict with runtime state.** First determine the exact requested scope. If the user identifies only a fixed label such as `7F→8F`, preserve the supplied elevator/CCTV artwork and remove only that label from the source asset using a tightly bounded pixel mask/inpainting pass; verify that the cabin, doors, arrows, scanlines, perspective and surrounding texture remain intact. A screenshot annotation or red circle is a local edit boundary, not permission to redesign the whole frame. Do not replace the whole image with a black procedural fallback, and do not add a broad black card/strip or duplicate runtime floor readout unless the user explicitly asks for one. Renderer overlays are a last resort because they obscure authored art. Keep runtime floor data in its existing dedicated HUD/reading location. Process all affected up/down and mobile/desktop variants, rebuild copied platform assets, and verify in the official Developer Tool screenshot. Use `references/surgical-baked-label-removal.md` for the scoped OpenCV inpainting workflow and acceptance checklist.

26. **Absolute floor values in anomaly effects cause random-feeling jumps.** Setting `effects.floor = 13` (absolute) means the elevator jumps to floor 13 regardless of its current position. After a `floor_jump` (+4 from floor 5 → floor 9), hitting an absolute-value anomaly next produces 9→13 — a seemingly random jump that breaks the player's spatial sense. **Fix:** use delta values for all floor-changing anomalies (`"floor": "+2"` or `"floor": "-2"` instead of `"floor": 13`). This keeps floor changes sequential and believable. The anomaly's narrative context (e.g. "phantom floor") can still reference specific numbers in the hidden log and monitor text, but the runtime effect should be a relative offset so the progression always makes spatial sense. Only use absolute values when the intention is jarring disorientation (e.g. `negative_floor` jumping to `-1`). Update both `skin.json` effects and `anomalyContent.js` screenData/panelData when changing from absolute to delta.

27. **Clean replacement packs invalidate old-asset masking and cropping assumptions.** Inventory state IDs, counts, dimensions and audio format before copying. Replace only canonical source assets, preserve explicitly marked keep/reference/release folders, then regenerate all platform copies through the build pipeline. If new CCTV art is already text-free and safely cropped, delete legacy top/bottom crop and opaque HUD-mask code rather than carrying it forward. Verify source/output hashes and asset-family counts. For BGM, use a dedicated loop player/context, start only after a user gesture, switch calm/pressure from runtime state, and tie mute/ads/lifecycle/terminal states to pause/resume/stop without parallel loops. See `references/text-free-cctv-and-bgm-integration.md` for the deterministic workflow and evidence checklist.

28. **Repository size is usually dominated by caches/toolchains, not game code.** Before deleting assets or platform projects, measure top-level and nested sizes and classify each directory as runtime source, generated import-ready output, release evidence, reproducible cache, download archive, duplicate installed app, or required portable toolchain. Delete ignored caches and installed-tool archives first. Remove tracked reference assets only after a whole-repo reference scan and update manifests, docs and inventory tests in the same commit. Preserve release screenshots and required SDK/JDK/Gradle versions. For deterministic staging trees, prove regeneration from an absent directory, ignore/untrack the staging layer while retaining the native project shell, then remove the regenerated local copy again before final measurement. Avoid running a heavyweight build immediately after deleting caches if it would recreate hundreds of megabytes; use tests, target bundle checks and resource preparation, and state which heavyweight build was intentionally not rerun. Report before/after byte counts and explain remaining large directories. See `references/runtime-asset-replacement-and-cleanup.md` for the exact deletion safety and zero-state regeneration checklist.

29. **Adapting the viewport to the art instead of the art to the viewport.** When the user says an image does not fit or black edges must be filled, first establish which object is fixed. If the established CCTV window/layout must remain, do not shorten the viewport to the source aspect ratio: that moves readings/buttons upward and creates a large empty lower region. Do not stack a dim `cover` background behind a `contain` foreground; it creates duplicate subjects and seams. For an explicit “image fits the CCTV window” requirement, preserve layout and draw once into the full viewport (`ctx.drawImage(image, x, y, w, h)`), accepting non-uniform scale when the user prioritizes no crop/no bars. If shape distortion is not acceptable, explain the unavoidable trade-off among crop, letterbox, or source outpainting before editing. Validate in the user's already-open official Developer Tool project—never reopen or switch tools after they say it is already open—and click through the start gate before judging runtime composition. Also update generated-bundle touch smoke coordinates when layout truly changes; hard-coded interaction points can fail while rendering is correct. See `references/canvas-viewport-image-fit-and-live-devtools.md`.

30. **Treating visual freeze as either a full stop or permission for invisible UI work.** When the user says “先不改视觉，先执行其他的”, freeze renderer/layout/assets/screenshots, but continue independent gameplay logic, content, Schema, consequence, archive and test work. Keep the UI phase explicitly pending rather than cancelled. Register new modules in generated bundles when required, but do not claim runtime playability merely because logic is bundled: distinguish pure logic, content validity, bundle inclusion, runtime scheduling, player-visible entry and official screenshot proof. Commit by subsystem and keep reports explicit about what remains unreachable. For investigation games, require two independent evidence sources, deterministic protocol applicability, persistent event-chain flags, and wrong decisions that alter later information reliability instead of ending immediately. See `references/data-first-investigation-game-phases.md`.

31. **Shipping full-screen UI handoff renders or whole AI source panels as runtime art.** Treat complete 393×852/360×640 screens as pixel-layout references only: they bake dynamic text, buttons, answers and one fixed state. A “text-free” 1024×1536 source can still contain cabinet chrome and fixed control icons, so it is not automatically runtime-safe. Read the handoff compositor, reuse its exact scene crop coordinates, extract only the central CCTV content into a canonical reusable size, and check in the extraction script. Register the crops as their own manifest family; then verify copy/preload paths and update every semantic inventory contract (source pack, Canvas preload, generated bundle and Android/WebView counts). Record target package bytes because eight moderate PNGs can consume most of a 20 MB budget. Asset registration is not UI completion—renderer reachability, runtime state/click paths and official screenshots are still required. See `references/full-screen-ui-handoff-to-runtime-assets.md`.

32. **Treating a scheduled “sleep loop” status as proof of autonomous progress.** A scheduler can report `ok` after doing no meaningful product work. Admit tasks only from a code/design gap, failing gate, official-tool defect, or reachable progress-report item. Each tick completes one bounded vertical slice with a failing test, implementation, full target gates, package-byte check, report update, commit, push and clean-tree verification. After a tick, inspect the actual repository SHA/artifact rather than trusting scheduler status. For visual slices, use the user's already-open Developer Tool, capture before/after at the same preset, click through the real flow, and recapture to prove the click landed; an input event alone is not evidence. If no real evidenced task remains, stop instead of inventing work. Use a finite repeat count or explicit stop condition and show a visible cycle/task/evidence table. See `references/evidence-driven-overnight-game-loop.md`.

33. **Adding nested gameplay state without proving rollback isolation.** A field appearing in `createInitialState()` does not establish compatibility with snapshots, revive, rewind, save/load, or replay. First test two fresh initializations to catch shared nested objects. Then snapshot realistic nested session data, mutate the live copy after the snapshot, restore it, and prove both directions of isolation: late mutations do not enter the restored state, and mutations after restore do not rewrite snapshot history. Reuse the subsystem's state factory instead of duplicating tool defaults. Audit clone serialization before relying on JSON cloning: `Infinity` becomes `null`, while functions, Maps/Sets, class instances, typed arrays, and `undefined` may be lost or changed. Run state + subsystem + generated-bundle execution tests before full platform gates. See `references/rollback-safe-nested-game-state.md`.

34. **Wiring new gameplay controls to one generic click cue.** Functional buttons can still feel unfinished when camera switching, evidence tools, classification, and high-risk treatment all sound identical. Define a pure semantic feedback-profile map (`interaction → { cue, haptic }`) and let runtime handlers consume it: routine navigation gets light click/震动, scans and classification entry get a warning cue/medium haptic, errors get heavy haptic, and high-risk resolution gets the strongest existing alarm/lockdown cue. Reuse short local cues before adding assets when the package is near its platform cap, but test every mapping and rerun package-byte gates. Audio playback still starts only after user gesture and follows mute/ad/lifecycle rules.

35. **Event-chain state augmentation: spread engine output first, add view fields after; readers must consume the writer's canonical history path.** When wrapping a pure engine (e.g. `advanceEventChain`) into night state, write `next.chains[id] = { ...result.state.chains[id], history: filteredView }` — spreading the OLD progress first keeps `stepIndex` stale and the chain replays stage 1 forever. Also verify the engine's call signature: passing a chain-id string where the engine expects the chain object silently no-ops every advance. Symmetrically, when a debrief/timeline reader flattens `Object.values(chains).flatMap(c => c.history)` while the writer appends to a flat `night.eventChainHistory`, completed stages silently vanish from the report. Pick one canonical history path: the writer derives both the flat log and the per-chain view from the SAME engine result, and the reader prefers the flat log with the per-chain view as fallback. Regression-test that a fully completed chain's stages actually appear in the debrief timeline and that a wrong-stage flag drives its consequence exactly once.

36. **Token-sensitive audit delegation needs visible checkpoints, not silent waits.** When the user says "省TOKEN / save tokens", dispatch read-only audits to ONE background subagent with a tightly scoped goal (exact files, measured dimensions, required report shape) and pre-loaded skill references, then immediately tell the user what was delegated and the live-transcript path. If the user asks "还没好?" before completion, read the transcript tail and surface measured partial findings (geometry numbers, confirmed defects with file:line) instead of a bare "still running" — a silent 15-minute subagent run reads as wasted tokens and burns trust. Prefer one focused goal over broad multi-part goals; the narrower the audit contract, the faster and cheaper the report.

37. **Browser/H5 canvas harnesses can render every acceptance screenshot with zero real images.** If the renderer's image factory only probes `tt.createImage`/`wx.createImage`/`canvas.createImage`, a plain-browser harness silently marks every asset record failed and ALL captures show the procedural fallback — screens look "fine" but states are pixel-identical, and this can survive for months behind a green existence+size screenshot test. Detect by diffing the CCTV/scene region across rounds (diff ≈ 0 across states = fallback, not asset proof) or with an `Image` probe reporting `naturalWidth` into a DOM dataset attribute. Fix with an injectable factory — `init(canvas, systemInfo, { imageFactory })` supplied by the harness — never a `document.createElement('img')` fallback inside the shipped renderer: the WeChat/Douyin no-DOM static gate scans bundle TEXT and blocks even a `typeof document`-guarded reference. Give the harness a re-render loop (N setTimeout frames after `load`) so async image loads land before capture, plus `<base href>` when manifest paths are package-relative. See `references/canvas-acceptance-screenshot-pipeline.md`.

38. **"主要把画面改好看，别的暂时不用管" reorders the fix queue, not the gates.** When the user redirects a visual round, visual-fidelity fixes (aspect-ratio distortion, handoff art never drawn, static effects that should move, missing press states, undefined treatment colors) outrank the audit's P0/P1 items (package size, telemetry, hit-area compliance) — defer those explicitly to a later round. Tests/bundle/strict gates and commit+push still apply to the visual round; only the fix selection changes.

39. **A loaded asset is not an atmosphere pass.** For CCTV/monitor horror games, distinguish three states explicitly: asset registered, asset drawn, and composed as a living surveillance surface. A scene PNG plus clean panels can still look like a generic admin dashboard if the supplied CRT frame, scanlines, vignette, sweep, recording indicator, and threat treatment are only preloaded or referenced in a manifest. Before declaring visual improvement, inspect the actual render order and prove the layers are drawn inside the CCTV clip, use the same pausable frame clock for motion, and keep runtime HUD semantic (REC/camera/watch status) without baking answers into art. When the user says “不好看/没有氛围,” acknowledge the composition failure first; do not lead with tests, package size, or asset-load claims. Use `references/cctv-atmosphere-acceptance.md` for the layer reachability and screenshot-diff checklist.

## Mini-Game Full-Stack Reachability and Package Gates

For Canvas mini-games with multiple generated targets, treat a feature as complete only when the same real case is reachable through the player path and present in the generated artifacts:

```text
content → state/clone/rollback → scheduler → pending inspection
→ visible semantic button → runtime decision handler → chain/history/consequence
→ debrief/ending → Canvas visual/audio feedback → generated WeChat/Douyin bundle
```

A scheduler writing `currentShift` is not enough: the runtime must open the next pending inspection, the renderer must mark quick/identity/classification/high-risk controls with semantic decision metadata, and the click branch must call the decision handler rather than a generic legacy action dispatcher. Teaching handoff is a special boundary: install the first event-chain step without advancing it; only later accepted decisions or timeouts advance the chain.

Keep event-chain flags and next-shift modifiers separate. Ending selectors read canonical chain flags; modifiers need an explicit consumer at next-shift installation, an observable effect, and one-time consumption. If a state field is added, update clone/rollback tests and exact initial-state assertions in the same RED→GREEN cycle.

For generated WeChat/Douyin projects, measure package layers separately instead of reporting only total bytes:

- main package bytes (bundle, audio, config, runtime files);
- subpackage bytes (large visual assets);
- total package bytes;
- stale legacy output directories;
- generated project-config identity.

Use native subpackage configuration for large visual families while keeping manifest paths and build copy paths consistent. The development fallback may use `touristappid`, but release readiness must fail closed until a real private AppID/ad-unit overlay is injected; never confuse a passing runtime checker with publish readiness. Rebuild both targets after source changes and audit generated bundles for source/WIP drift.

Do not stop at targeted tests. A targeted green result can hide stale exact-count assertions, generated-artifact regressions, or state-shape failures. The completion gate is the project’s full test command plus each target build, strict checker, diff check, package-byte report, screenshot/runtime evidence, and exact current-tree identity. If any full gate fails, report the exact failures and keep the task open.

See [`references/minigame-event-chain-and-package-gates.md`](references/minigame-event-chain-and-package-gates.md) for the reusable boundary matrix, package measurement recipe, and failure taxonomy.

## Generated Mini-Game Artifact and Upload Closeout

When a Canvas mini-game has multiple generated targets, package size and upload truth are part of the feature—not a final afterthought. Preserve runtime manifest paths whenever possible: if large assets already live under a canonical `visual/` directory, declare that directory as a native subpackage in generated `game.json` rather than moving files and silently breaking relative asset paths. Measure logical main-package bytes (excluding the subpackage) and total bytes; also scan for stale legacy output directories that strict checkers may include.

For event-chain work, the minimum reachable slice is:

```text
content → initial state/clone → scheduler currentShift
→ runtime openInspection(pending) → renderer semantic decision button
→ onDecision handler → advance chain/history/flags
→ consequence/modifier consumer → next shift/debrief
```

Teaching handoff is special: schedule the first chain step without advancing it. Only a later accepted decision or timeout advances the chain. `eventChainFlags` select endings; `nextShiftModifiers` must be consumed at next-shift installation, produce an observable effect, and then be cleared. Direct scheduler/engine tests are insufficient without the Runtime boundary and generated-bundle path.

Closeout sequence:

1. Fix the smallest RED regression at the unreachable seam.
2. Run the full project test command, not only targeted tests; update exact-count/state-shape assertions in the same RED→GREEN cycle.
3. Rebuild every tracked target bundle after source changes.
4. Run each strict target checker, `git diff --check`, and a package report split into main/subpackage/total/stale-legacy bytes.
5. Stage only intended files; explicitly reject `release.config.json`, `project.private.config.json`, and `.tmp/` from the index.
6. Commit, push, then compare `git rev-parse HEAD` with `git ls-remote` for the exact branch ref. A local commit or passing check is not upload evidence until the remote SHA matches.
7. Record real gates and exact SHA in the project evidence document. Keep real AppID/ad-unit and Developer Tool/device validation separate; tourist fallback is development evidence, never release readiness.

See [`references/v5-event-chain-package-upload.md`](references/v5-event-chain-package-upload.md) for the reusable boundary matrix, subpackage strategy, package measurement, and upload checklist.

## Full-Stack Vertical-Slice Recovery

When the user asks to “全量推进前端后端” or equivalent, treat it as an execution directive, not a request for a gap report. Trace one real gameplay path end to end: content/state → scheduler/event-chain consequences → platform runtime handler → Canvas renderer/hit regions/audio → generated bundle. Start with a failing regression for the highest-impact unreachable path, implement the smallest vertical fix, then continue to the next evidenced gap. Do not stop at targeted tests or say “not fully complete” while the requested gates remain runnable; run the full project tests, platform build, strict checks, screenshot/runtime acceptance, diff check, commit, push, and exact local/remote SHA verification before finalizing. A user complaint such as “不好看，没有一点氛围” is a composition failure signal: acknowledge it first and inspect render order, not just asset manifests or unit-test counts. For compact Canvas controls, separate visual bounds from touch bounds; for state resources, render live telemetry where decisions occur; for interaction audio, use semantic profiles instead of one generic click cue. See `references/full-stack-game-vertical-slice.md` for the reusable audit and acceptance matrix.

## Content Schema Pattern (Clue-Hunting / Observation Games)

For games where the core loop is "observe → compare → decide" (e.g. anomaly-finding), define a formal content schema that makes every clue checkable without leaking the answer through UI chrome:

### `screenData` / `panelData` / `primaryConflict` Triad

Each anomaly entry captures **what the player sees** vs **what the system says** vs **the specific contradiction**:

```js
{
  id: 'phantom_floor',
  screenData: { floor: 4, passengers: 1, door: 'closed', direction: 'idle' },
  panelData:  { floor: 2, passengers: 1, door: 'closed', direction: 'idle' },
  primaryConflict: '画面楼层比控制台高 2 层（画面层 4，控制台层 2）',
  correctDecision: 'lockdown',      // always lockdown for anomalies
  difficulty: 1,                    // 1=obvious, 2=needs checking, 3=needs context
  visualState: '16_wrong_floor',
  audioCue: 'anomaly',
  resolutionAction: 'restartSystem',
  normalVariant: { floor: 2, passengers: 1, door: 'closed', direction: 'idle' },
}

// Another example with field-level contradiction:
{
  id: 'floor_jump',
  screenData: { floor: 9, passengers: 1, door: 'closed', direction: 'up' },
  panelData:  { floor: 5, passengers: 1, door: 'closed', direction: 'up' },
  primaryConflict: 'CCTV 层 9 ≠ 控制台层 5（非连续移动，帧丢失）',
  correctDecision: 'lockdown',
  difficulty: 2,
  visualState: '16_wrong_floor',
  audioCue: 'anomaly',
  resolutionAction: 'inspectLog',
  normalVariant: { floor: 5, passengers: 1, door: 'closed', direction: 'up' },
}
```

**Rules:**
- All entries share the same 3–4 key fields (floor, passengers, door, direction)
- A single-field difference = simplest anomaly (difficulty 1)
- Three-field identity but non-field clue (log echo, auto-buttons, power drain) = compound anomaly (difficulty 2–3), the `primaryConflict` must name a specific observable keyword
- `correctDecision` is always `lockdown` for anomalies (the binary is "is there a conflict or not")
- `normalVariant` describes what a matching *non-anomalous* frame looks like for that floor/state
- `primaryConflict` must name an observable, specific clue — not a tautology
- **Floor effects must be relative deltas, not absolute values** (`"floor": "+2"` not `"floor": 13`). Absolute values cause the floor counter to jump to an arbitrary number regardless of elevator position, creating a random-feeling progression that breaks spatial comprehension. Only use absolute values for intentionally disorienting exceptions (e.g. `negative_floor` → `-1`). The anomaly's narrative (hidden logs, monitor text) can reference specific story numbers — the runtime effect must be a delta so consecutive anomalies produce sequential, trackable changes. When changing from absolute to delta, update both `skin.json` effects and `anomalyContent.js` screenData/panelData (e.g. for `phantom_floor`: effects from `"floor": 13` to `"floor": "+2"`, screenData from `{floor: 13, …}` to `{floor: 4, …}`, panelData from `{floor: 1, …}` to `{floor: 2, …}`).

### Timeline / Archive / Telemetry (Observation Games)

For games with player judgments, store each decision in a timeline that survives until reset:

```js
// src/anomalyArchive.js
let timeline = [];

function recordDecision({ elapsed, kind, anomalyId, playerChoice, correctChoice, timedOut }) {
  const correct = !timedOut && playerChoice === correctChoice;
  const entry = { elapsed, kind, anomalyId, playerChoice, correctChoice, correct, timedOut, ... };
  timeline.push(entry);
  return entry;
}
```

Expose these query functions:
- `getTimeline()` — full history for post-game review UI
- `getLastDecision()` — most recent entry (for feedback display)
- `getDecisionStats()` — `{ total, correct, wrong, timeout, accuracy }`
- `getArchiveEntry(anomalyId)` — structured anomaly data (for anomaly database)
- `getArchiveIndex()` — all anomalies, summary fields (for archive list UI)
- `serializeTimelineForTelemetry()` — normalized events for analytics pipeline

The timeline integrates with the game runtime at each decision point (player click, timeout) but is decoupled from the renderer — it can feed a DOM-based review screen, a Canvas overlay, or a telemetry endpoint without changing the core module.

### Teaching Flow (First-Run Onboarding)

For observation/classification games, the first run must use a **deterministic progression** that teaches through real gameplay, not tutorials:

1. **First inspection: normal baseline.** Send an empty/easy normal inspection (e.g. empty elevator, consistent data). Guide the correct action with a hint. Wrong taps are non-punitive — the inspection stays pending, scores/resources untouched.
2. **Second inspection: fixed concrete anomaly.** Override the random scheduler to guarantee a specific, easily observable anomaly (e.g. floor_jump with two clearly different floor numbers). Guide the correct action. Wrong taps remain non-punitive. The teaching message should name the specific contradiction.
3. **Third inspection: independent judgment.** Remove all hints, answer highlights, and pedagogical coaching. The player must use only the core rule ("consistent → release, contradictory → lockdown"). The inspection label should be the same neutral text as post-tutorial gameplay.
4. **Exit.** After the third inspection is accepted or times out, set `tutorialStep = 4` (or equivalent). Future restarts do not re-enter the tutorial.

Key rules:
- First two inspections fix the anomaly ID (no randomness).
- Timeouts during teaching advance `tutorialStep` without resource penalty — a first-inspection timeout must still lead to the fixed second inspection.
- The teaching timeout path must be tested via the generated bundle with injectable clock, not just unit tests.
- The scheduler must prevent random normal inspections from inserting between teaching steps.

### Normal Variant Anti-Pattern Matching

Generate 10+ normal variants that:
- Share floor numbers appearing in anomaly screenData/panelData (so floor 13 alone is not a signal)
- Cover empty, single-passenger, and multi-passenger states
- Include door-open and door-closed variants
- Include moving variants (up/down)
- Prevent "the CCTV looks different = anomaly" conditioning

See `references/anomaly-content-schema.md` for the full reference pattern.

### Visual State Pattern (Observation Games)

For CCTV / observation displays, derive visual state from a single source of truth:

```
anomalyContent.js (visualState per anomaly ID)
        ↓
visualState.js (getCctvState → getAnomalyCctvState + runtime conditions)
        ↓
drawCctvScene → assetStore.getCctv(cctvState)
```

**Critical: isNormalRunning() guard**

During normal play (no active anomaly, not game-over, not settled), CCTV must show the state that *matches the panel data*, not residual resource values. Without this guard, auto-resolving an anomaly leaves low power/high anomalyLevel on the state object, causing `getCctvState()` to return `07_power_outage` or `10_signal_lost` even though the current inspection is perfectly normal — leaking false alarm signals to the player.

```js
function isNormalRunning(state) {
  return !state.gameOver
    && state.result !== 'success'
    && !state.activeAnomaly
    && !state.fakeEndingCooldownRemaining;
}

function getCctvState(state, anomalyLevel) {
  if (state.result === 'success') return '19_stabilized';
  if (state.gameOver || anomalyLevel >= 5) return '20_threat_high';
  if (state.activeAnomaly) { /* use anomaly-specific visualState */ }
  if (state.fakeEndingCooldownRemaining > 0) return '23_cooldown_safe';

  // Normal running: reflect panel data (direction → door → idle), not residuals
  if (isNormalRunning(state)) {
    if (state.direction === 'up') return '04_moving_up';
    if (state.door === 'open') return '01_door_open';
    if (state.stability >= 92 && state.elapsed > 0) return '19_stabilized';
    return '00_idle_closed';
  }

  // Anomaly active period: power/anomalyLevel warnings are valid here
  if (state.power <= 5) return '07_power_outage';
  if (state.power <= 22) return '06_power_low';
  if (anomalyLevel >= 3) return '13_entity_near';
  return '00_idle_closed';
}
```

The same `isNormalRunning()` guard must also control `highlightAction` (return null during normal running so residual anomalyLevel doesn't drive false recommendation highlights) and `deriveVisualState`'s `glitch`/`shake`/`tone` fields. Tests should verify:
- Pending normal inspection stays neutral despite prior pressure (anomalyLevel=2, power=18)
- No anomaly, no game-over: direction/door states override power-based CCTV states
- Active anomaly: power-based CCTV states still activate during the anomaly

### Timeline / Archive / Telemetry (Observation Games)

For games with player judgments, store each decision in a timeline that survives until reset:

```js
// src/anomalyArchive.js
let timeline = [];

function recordDecision({ elapsed, kind, anomalyId, playerChoice, correctChoice, timedOut }) {
  const correct = !timedOut && playerChoice === correctChoice;
  const entry = { elapsed, kind, anomalyId, playerChoice, correctChoice, correct, timedOut, ... };
  timeline.push(entry);
  return entry;
}
```

Expose these query functions:
- `getTimeline()` — full history for post-game review UI
- `getLastDecision()` — most recent entry (for feedback display)
- `getDecisionStats()` — `{ total, correct, wrong, timeout, accuracy }`
- `getArchiveEntry(anomalyId)` — structured anomaly data (for anomaly database)
- `getArchiveIndex()` — all anomalies, summary fields (for archive list UI)
- `serializeTimelineForTelemetry()` — normalized events for analytics pipeline

The timeline integrates with the game runtime at each decision point (player click, timeout) but is decoupled from the renderer — it can feed a DOM-based review screen, a Canvas overlay, or a telemetry endpoint without changing the core module.

## Content Data Integrity Tests

Every structured content dataset needs a pure-data validation test suite that runs independently of game logic:

```js
// tests/anomalyContent.test.js — 20 assertions

// Structural: every entry has all required fields
test('all entries have required fields');
test('each anomaly has at least one conflict field');
test('each normal variant has fully consistent data');
test('all value ranges are valid');

// Cross-reference: content ↔ skin.json
test('all content IDs match skin.json anomaly IDs');  // bi-directional
test('findAnomalyContent returns correct entry by ID');
test('findAnomalyContent returns null for unknown IDs');

// Anti-pattern matching: normal variants prevent surface-level cues
test('normal variants include anomaly-matching floor numbers');
test('normal variants are fully field-consistent');

// Semantic correctness
test('field-level anomalies have screen vs panel differences');
test('zero-field anomalies name a specific observable keyword');
test('correctDecision is lockdown for all anomalies');
test('isDataConsistent returns false for anomalies');

// Visual state mapping
test('getAnomalyCctvState returns correct state for all anomalies');
test('getNormalCctvStates and getAnomalyCctvStates are disjoint');
test('deriveVisualState returns correct cctvState for each active anomaly');

// Runtime integration
test('guided first class wrong tap keeps inspection pending');
test('guided second class wrong tap keeps inspection pending');
test('timeout penalizes exactly once');
```

Place assertions in domain-specific files (`tests/anomalyContent.test.js`, `tests/skinValiditiy.test.js`). They run as part of the standard suite and catch structural data errors before the game logic ever evaluates them.

## Verification Checklist

For reviews involving settlement state, rewarded ads, portrait layout, or generated bundles, use `references/settlement-ads-and-artifact-review.md` for staged-snapshot probes and callback/terminal-state matrices.

For Douyin or shared WeChat/Douyin release claims, use `references/douyin-generated-bundle-audit.md`. Build each target independently and execute the untouched generated bundle against a minimal host-API VM mock; syntax checks and WeChat-only strict checks cannot establish Douyin readiness.

- [ ] All src modules load without errors
- [ ] Skin JSON is valid JSON (`node -e "JSON.parse(...)"`)
- [ ] Every anomaly ID exists in both ANOMALIES and HIDDEN_LOGS
- [ ] `t()` calls don't reference missing skin keys
- [ ] Game runs start to finish (60s → game over → ad revive → continue)
- [ ] Build script produces valid output
- [ ] If the user supplied UI/visual assets, the target runtime actually draws a documented production subset (not only procedural placeholders)
- [ ] Official Developer Tool/device screenshots prove asset loading, representative states, readable dynamic labels, and no crop/overlap/black-frame regressions
- [ ] For stateful CCTV/machine visuals, a captured temporal sequence proves pre-action → intermediate → terminal → recovery behavior; physical subject changes are visible, motion terminates, and baked answers/fixed values remain hidden before classification
- [ ] Package-byte and decoded-memory measurements justify exclusions; optimization is preferred over silently dropping the supplied art direction
- [ ] Skin/data JSON validates against its schema (`npm run skins:check` or equivalent); see `references/schema-validator-pattern.md` for the self-contained validator approach
- [ ] README/platform handoff docs mention the current verified commands, build outputs, private release config flow, and recent UX fixes
- [ ] Add doc regression tests for public entrypoints when docs are part of the delivery path
- [ ] A one-command development gate exists when the project spans tests + platform bundles + APK metadata (e.g. `npm run verify`)
- [ ] A separate release-readiness gate fails closed on placeholder AppID/adUnitId values without blocking development iteration (e.g. `npm run release:check`)
- [ ] Tokens, secrets and adUnitId values live in ignored private overlays; if the Developer Tool requires the public AppID in generated `project.config.json`, the build propagates it from that overlay and tests both configured and tourist fallback paths
- [ ] Git commit is semantic-prefixed (feat/fix/docs)

## Release / publishing gates

For native Douyin Canvas projects, use `references/douyin-minigame-release-preflight.md` for the official-doc-backed checklist covering root structure, `game.json`, `project.config.json`, ordinary-game package limits, lifecycle/touch/safe area, ads, privacy, mandatory sidebar revisit, account/filing duties, and upload/review. Re-check upstream pages before repeating numeric limits or dated review policy, and label every item as code, Developer Tool, console/account, or joint responsibility. Pair it with `references/douyin-generated-bundle-audit.md` when reviewing actual generated artifacts.

For WeChat/Douyin/IAA packaging, split validation into two gates:

1. **Development acceptance**: tests, bundle build, runtime blocker checks, Android/WebView build and metadata checks. This must pass without real credentials.
2. **Release readiness**: real AppID and rewarded-video ad unit IDs are present via ignored private config; generated platform bundle has no runtime blockers; package metadata is valid. This should fail closed on placeholders.

Use the private config overlay pattern in `references/minigame-release-gates.md`: commit `release.config.example.json`, ignore `release.config.json` and platform `project.private.config.json`, let the build script inject private ad units only into generated outputs, and add regression tests that no private/test values remain in tracked files.

## Quick Reference

```bash
# Serve
python -m http.server 5173

# Build for WeChat
node build.js wechat

# Verify modules load
node -e "global.structuredClone=obj=>JSON.parse(JSON.stringify(obj)); Promise.all([import('./src/state.js'),import('./src/actions.js'),import('./src/events.js'),import('./src/skinManager.js')]).then(([s,a,e,m])=>{console.log('OK, anomalies:', e.ANOMALIES.length);}).catch(e=>console.error(e))"

# Git
git add -A && git commit -m "feat(P<N>): description" && git push
```
