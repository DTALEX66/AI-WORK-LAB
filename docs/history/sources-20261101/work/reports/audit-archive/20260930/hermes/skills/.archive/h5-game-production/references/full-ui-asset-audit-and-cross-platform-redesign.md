# Full UI Asset Audit and Cross-Platform Redesign

Use this reference when a user supplies a large UI asset pack and asks whether it is production-ready, with authorization to replace it if not.

## Outcome contract

Do not stop at an aesthetic opinion. Deliver one of:

1. **Accept and integrate** — only when the assets pass visual, technical, responsive, state, and licensing checks; or
2. **Reject and rebuild** — create a working UI system, integrate it into every shipped runtime, capture real screenshots, run the complete verification gate, and commit/push when requested.

## 1. Inspect before judging

1. Extract outside the repository first.
2. Reject archive path traversal before extraction.
3. Inventory count, total bytes, formats, dimensions, alpha usage, and directory structure.
4. Read manifests and README files.
5. Generate or inspect contact sheets for every asset family.
6. Open representative full-resolution originals, not only thumbnails.
7. Quantify exact and near duplicates (SHA-256 plus dHash/pHash).
8. Check whether non-transparent pixels touch crop boundaries; zero safe padding is a common auto-slice defect.
9. Flag assets smaller than the minimum intended touch target.
10. Check for baked pseudo-text, watermarks, source-screen fragments, adjacent-component contamination, and inconsistent shadows/perspective.

## 2. Production-readiness gates

An asset pack is not production-ready unless it has:

- legible, editable copy or text-free components;
- complete default/hover/pressed/disabled/focus states where relevant;
- coherent scale and perspective;
- safe alpha padding and clean edges;
- explicit 9-slice or responsive behavior;
- a small, purposeful component set rather than hundreds of near-duplicates;
- matching desktop and portrait behavior;
- traceable source/license information;
- no UI reference screen used as a runtime background.

AI-generated sheets with decorative pseudo-labels should normally be treated as mood references, not runtime controls.

## 3. Prefer a system over more raster slices

When the supplied pack fails:

- Keep only verified text-free environmental art or CCTV states.
- Generate buttons, panels, meters, focus rings, labels, and states in CSS/SVG/Canvas.
- Render all player-facing copy at runtime.
- Use one semantic palette: base surfaces plus restrained success/warning/danger colors.
- Use small industrial radii for control consoles; avoid generic SaaS cards and decorative pills.
- Make the gameplay surface—not branding or chrome—the largest visual region.
- Write a design specification before implementation: surface, hierarchy, desktop grid, portrait order, tokens, component rules, motion, and acceptance metrics.

## 4. Cross-runtime parity

A “full UI” change is incomplete if it only changes browser CSS.

### DOM / H5 / WebView

- Implement the desktop layout and portrait layout explicitly.
- Ensure the start gate, more-actions sheet, archive, success, failure, and special endings share the same visual grammar.
- Keep the primary action row visible and complete.

### Canvas mini-game runtime

- Export a pure layout function such as `getCanvasLayout(height)`.
- Draw and hit-test from the same layout data.
- Size touch targets in design pixels so the scaled result remains at least 44 CSS px.
- Preserve CCTV-first hierarchy, state colors, result overlays, and action semantics.
- Remove debug controls from production rendering.

### Generated targets

Rebuild and verify generated WebView assets and mini-game bundles. Never assume source changes propagated.

## 5. Test-driven acceptance

Add failing contracts before production changes for:

- desktop gameplay-surface dominance;
- mobile four-key or equivalent primary action rail;
- minimum touch target size;
- start card within viewport bounds;
- no horizontal overflow;
- short-screen fallback;
- Canvas layout ordering;
- Canvas drawing/hitbox parity;
- explicit success/failure styling.

Then capture real browser evidence at representative sizes, at minimum:

- desktop around 1365×768;
- portrait around 390×844;
- short portrait around 360×640.

Use exact geometry probes (`scrollWidth`, `scrollHeight`, bounding rectangles), not screenshots alone. Headless Chrome’s `--window-size` can report/crop inconsistently; CDP `Emulation.setDeviceMetricsOverride` is the authoritative path for exact mobile viewport evidence.

## 6. Visual slop audit

Before delivery, explicitly reject:

- excessive pills;
- oversized hero titles that displace gameplay;
- decorative gradient text;
- neon borders on every surface;
- equal-weight card grids for critical and secondary telemetry;
- duplicate labels layered over the CCTV;
- unearned blur/glass effects;
- marketing-page composition in an in-game surface.

## 7. Verification and delivery

1. Run targeted tests after each structural change.
2. Run the repository’s complete verification command.
3. Verify generated bundles contain the new layout/tokens.
4. Verify Android/WebView asset rewriting is intentional; source and generated CSS may differ only by asset path transformation.
5. Run the release-readiness gate and preserve fail-closed placeholder blocking.
6. Run `git diff --check`, inspect tracked/generated files, and keep screenshots/extraction directories ignored.
7. Commit, push, fetch, and prove local HEAD equals remote HEAD.
8. Report separately: asset verdict, implemented system, measured geometry, tests/builds, release blockers, and commit SHA.
