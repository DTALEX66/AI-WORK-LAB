# Pixel-Perfect Vector Reconstruction — Execution Rulings

Status: binding implementation addendum
Date: 2026-08-23
Authority: the approved design specification remains primary; these rulings resolve omissions in the four implementation plans.

## Contract and intake rulings

1. Deterministic-core Task 1 owns closed RIR and run contracts, canonical RIR hashing, provider consent, profile, authorization, lifecycle, provenance/source-mapping and artifact-declaration fields needed by downstream stages.
2. Deterministic-core Task 2 also implements deterministic profile classification and tiled-analysis metadata for inputs above 4096 pixels while retaining one global coordinate system.
3. `defusedxml` is part of the core dependency contract. Pinned `resvg` remains a separately acquired and checksum-verified external binary; absence must fail its runtime preflight rather than trigger an implicit download.

## Rendering and delivery rulings

1. Deterministic-core Task 4 is the sole owner of the fixed render profile. Its evidence includes recorded background compositing, Pixelmatch-equivalent threshold and anti-alias behavior, SSIM, mean RGBA error metadata, edge error, diff heatmap and a defined 32×32 high-density-region rule.
2. Add deterministic-core Task 6 after Task 5: implement the evidence packager and complete bundle validator for `manifest.json`, `structure-report.json`, `metrics.json`, `diff.png`, `provenance.json`, lifecycle promotion, hashes and transient-data stripping. This is the twentieth executable task.
3. A deterministic-only pass can promote at most `PIXEL_VERIFIED_DETERMINISTIC`; only validated Illustrator read-back plus all release evidence can promote `DELIVERY_READY`.

## Model and host rulings

1. AI-decomposition Task 3 includes a bounded Grounding DINO proposal adapter for open-vocabulary boxes; it is optional at runtime and cannot award PASS.
2. Adobe Tasks 1 and 2 include an allowlisted Illustrator Image Trace candidate route, bound to the exact host job and subjected to the same sanitizer, rendering and editability checks.
3. Photoshop-prepared layers have an explicit run-relative handoff into the Adobe host job; Photoshop output never replaces Illustrator read-back.

## Qualification rulings

1. Hardening Task 2 owns tracked original programmatic/vector source definitions, a corpus loader and deterministic generator before freezing the six PNG hashes.
2. Hardening Task 3 compares deterministic preview identity, equivalent Illustrator read-back and exact rollback/residue outcomes across all three clean runs.
3. Hardening Task 4 defines typed hardware, runtime-plan and timed-event contracts; thresholds may be populated only from observed matched samples.
4. Local tests, CI, publication, merge, live Adobe execution and newly installed runtime evidence remain separate lifecycle layers. No layer may be inferred from another.

## Data-boundary ruling

Short-lived execution ledgers, reports, briefs and review packages stay below ignored
`.hermes/task-runtime/reconstruction-dev/`. The canonical verifier's ignored
`design-lab/config/.verify-chain-ok` marker remains an exact project-local side effect; release evidence independently binds the checked-out SHA.
