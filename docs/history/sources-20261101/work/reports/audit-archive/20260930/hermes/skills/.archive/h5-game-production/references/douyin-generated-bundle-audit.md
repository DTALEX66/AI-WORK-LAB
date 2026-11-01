# Douyin / Mini-game Generated-Bundle Audit Pattern

Use this when a repository claims WeChat/Douyin mini-game support from one shared build script.

## Core rule

Never infer Douyin readiness from WeChat checks. Treat each target as a separate release artifact with its own build, config, runtime smoke test, IDE import, and real-device evidence.

## Required evidence ladder

1. Run the exact target build in an isolated clone/worktree: `node build.js douyin`.
2. Inventory generated files and byte sizes. Confirm the mandatory `game.js`, `game.json`, and `project.config.json` exist.
3. Parse target configs and inspect values, not just JSON validity. Catch copied WeChat placeholders, stale fields, wrong AppID labels, and create-only config generation that preserves obsolete files.
4. Run `node --check` on the bundle, but do not stop there.
5. Execute the generated bundle in a VM with a minimal target-host mock (`tt.createCanvas`, `tt.getSystemInfoSync`, `tt.requestAnimationFrame`, `tt.onTouchStart`, rewarded-ad object). Require startup, first render, frame scheduling, and touch registration.
6. Inspect the bundle for actual inclusion of persistence, analytics, audio, lifecycle, and ad paths. Source modules that are excluded from the target module list are not platform support.
7. Verify target-specific release gates. A generic release checker that validates a Douyin AppID but only builds/checks WeChat is not a Douyin gate.
8. Only after automated runtime smoke passes, record developer-tool import, preview/QR, real-device, real-ad-unit, privacy/filing, and upload evidence separately.

## High-value negative controls: stripped or omitted imports

Regex ESM strippers often delete:

```js
import { init as initCanvasRenderer } from './canvasRenderer.js';
```

while leaving calls to `initCanvasRenderer()`. A second common form is an explicit module allowlist that includes the importer but omits a dependency such as a reward/state guard. The generated bundle remains syntax-valid and may boot normally, yet crashes only when a delayed callback reaches the missing symbol.

Do both checks:

1. Search the generated artifact for every high-value imported identifier's definition as well as its call sites. A call-only symbol is a blocker.
2. Extend the untouched-bundle VM smoke beyond startup: retain SDK callbacks and execute at least completed rewarded-ad close, ad error, lifecycle hide/show, and a real touch-driven action. This catches `ReferenceError` failures hidden behind asynchronous paths.

The runtime smoke test must execute the untouched generated artifact. Instrument the host mock rather than patching the bundle. If continuing diagnosis after the first blocker, patch only an isolated artifact or smoke harness and clearly label subsequent findings as hypothetical-after-first-fix.

## Strict read-only worktree reviews

Build, release-check, package, and many test commands are mutating even when described as “checks”: they may regenerate tracked/untracked bundles, copy assets, create `.tmp`, or write `dist`. Before running any command in a user worktree that must remain read-only, inspect the command and all scripts it dispatches for filesystem writes.

For an unstaged review that includes untracked files, do not use an index-only snapshot. Materialize the complete working tree into an external temporary review directory, excluding `.git` and heavy caches, and run all mutating builds/tests there. Record hashes or `git status --short` before and after on the source tree. If policy or approval prevents creating/cleaning a temporary copy, restrict execution to demonstrably non-writing tests and report that the full mutating gate was not run. Never invoke a release checker in the source worktree merely because its name sounds read-only.

## Lifecycle, ad-cover, and terminal-state probes

Mini-game loops based on `Date.now()` must explicitly account for `tt.onHide` / `tt.onShow` and ad-induced JS suspension. Do not assume a rewarded-ad overlay always emits `onHide`: invoke a clock-pause hook when a real ad attempt starts, and resume from every completed, cancelled, load/show-error, and unavailable path. Use an ad-attempt settlement callback in `finally` so a reward-handler exception cannot leave the clock paused.

Test all of these against source units and the untouched bundle where practical:

- hide for 30 seconds then show;
- rewarded ad during an active run when no host hide event fires;
- completed, cancelled, duplicate, stale-run, show-error, and load-error callbacks;
- first frame after resume;
- no anomaly/timer/resource progression while paused;
- a success reached by `tickState` cannot be overwritten by inspection timeout or another same-tick failure check.

## Touch, capability, and target-size contract

A browser-style mock that sends only `clientX/clientY` does not establish Douyin Touch compatibility. Build a touch adapter with target-native fields (`screenX/screenY`) plus compatible fallbacks, and make the bundle smoke click the start gate, a classification choice, and at least one gameplay/ad control through those fields.

For mandatory sidebar revisit, verify both sides of the contract: probe support with `tt.checkScene({ scene: 'sidebar' })`, show/enable the entry only when supported, and then call `tt.navigateToScene({ scene: 'sidebar' })`. Refresh capability after foreground resume; a static `navigateToScene` keyword is not enough.

Convert design-space hitboxes to CSS pixels at representative widths. Primary controls, mute, settlement/restart, and ad CTA targets should remain about 44 CSS px high; expanding only the drawn rectangle or only the hitbox can create overlap, so test shared geometry and neighboring controls.

## Gameplay-answer concealment and resolution

A normal/anomaly decision is not meaningful if the pending UI prints the event title, exposes the answer-bearing event log, or highlights the exact corrective action before classification. While a decision is pending, use neutral inspection copy, conceal same-tick event details, and disable or de-emphasize operational controls. After a correct classification, reveal the evidence and require the mapped corrective action to clear or advance `activeAnomaly`; test every shipped anomaly has a valid resolution action and visible success feedback.

## Compliance claims that need semantic checks

File-exists checks for privacy, screenshots, and age-rating material are useful but incomplete. Validate screenshot dimensions and distinct gameplay states, reconcile store wording with age classification, and re-check current official rules. In particular, if official guidance classifies horror-themed games as 16+, do not leave a 12+ recommendation beside “horror” store copy. Keep account/AppID/ad-unit/operator/filing/IDE-upload blockers explicitly external rather than manufacturing values to make the gate green.

## Release archive identity and secret hygiene

A tracked import-ready project can safely keep `project.config.json.appid = "touristappid"`, but do not assume an ignored `project.private.config.json` will override that field in every target tool or archive consumer. At package time:

1. require the ignored private config and reject tourist/placeholder values;
2. patch the **in-memory archived copy** of `project.config.json` with the private AppID;
3. include the expected root files in the archive;
4. reopen the ZIP and assert `project.config.json.appid === project.private.config.json.appid`;
5. delete the temporary release config, private generated config, and archive, then regenerate the public tourist project;
6. search tracked files for synthetic AppIDs/ad-unit IDs before commit.

This proves the package path without dirtying the tracked public project with credentials. Never present a synthetic-config package hash as a real release artifact.

## Concurrent deterministic builds

Test runners may execute target-build tests in parallel against the same generated directory. A build that recursively deletes a shared asset directory before copying can race with another build and produce intermittent permission errors or partial artifacts. Prefer one of these class-level patterns:

- serialize same-target builds with a lock;
- build in unique temporary directories and atomically replace the target;
- for a fixed small asset set, copy with overwrite and remove only stale entries instead of deleting the whole shared directory.

Whichever pattern is used, retain deterministic repeated-build tests and run the full suite with its normal concurrency; a single serial build is not enough evidence.

## Storage and parity check

Check the actual mini-game entry module list. If browser-only modules provide archive, analytics, or audio, report mini-game absence even when a platform abstraction contains unused `tt.setStorageSync` wrappers. Quantify package size, but distinguish a small package caused by vector-only or omitted assets from true visual parity.

## Reporting language

Use precise states:

- `can generate directory`;
- `bundle syntax-valid`;
- `bundle runtime-smoke passed/failed`;
- `developer-tool import unverified`;
- `real-device/upload unverified`.

Never collapse these into “supports Douyin” or “publishable.”
