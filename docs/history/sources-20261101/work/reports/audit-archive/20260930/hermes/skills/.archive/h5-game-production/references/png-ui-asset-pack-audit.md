# PNG UI Asset-Pack Production Audit

Use this procedure when deciding whether a generated/sliced PNG UI pack is safe to import into an H5, Canvas, WebView, or mini-game production project.

## Scope and counting

Separate the package into runtime candidates and pipeline artifacts before judging cost:

- `Transparent_PNG` or equivalent runtime candidates
- original crops
- source sheets and numbered index/contact sheets
- manifests, previews, and documentation

Report both physical file count and logical asset count. A source crop and its alpha-processed derivative are one logical asset but two stored files.

## Deterministic checks

For every PNG, collect path, dimensions, mode, byte size, and decoded pixel cost. For runtime candidates, inspect alpha per pixel:

- bbox at `alpha > 0`, `alpha >= 8`, and optionally `alpha >= 128`
- margin on all four sides
- whether effective/high-alpha content touches the canvas border
- fraction of pixels with alpha 0, partial alpha, and alpha 255
- RGB values hidden under alpha 0

Treat high-alpha content touching an edge as a production warning even when a contact sheet looks acceptable. Hidden nonzero RGB beneath alpha 0 can bleed back under bilinear filtering, scaling, mip generation, or atlas extrusion.

Useful classification:

- fully opaque: no alpha variation
- nominal alpha only: alpha channel exists but transparent area is negligible
- meaningful cutout: transparent fraction is material and silhouette has safe padding
- clipped cutout: effective alpha bbox touches any side

## Duplication

Use two levels:

1. Exact comparison: normalized RGBA bytes plus dimensions, or content hash.
2. Near duplicate: perceptual hash on a consistent composite background; constrain by similar aspect ratio and optionally color histogram distance.

Do not confuse "no byte-identical duplicates" with "no package redundancy." Original crops, transparent derivatives, source sheets, and indexes are deliberate content redundancy and should not all enter Runtime.

## Baked text and AI gibberish

Use OCR only as a triage aid. Ornamental scratches and metal texture can produce large false-positive OCR counts. Final decisions require contact-sheet and single-asset visual inspection.

Reject or quarantine assets containing:

- unreadable pseudo-words or generated glyphs
- semantic labels baked into pixels
- document/log text that cannot be localized
- text-like micro-detail likely to become visible after scaling

Prefer explicit lower bounds and named examples over a fabricated exact percentage when classification is ambiguous. README statements admitting unreliable generated text are strong provenance evidence but do not replace visual confirmation.

## Runtime-cost estimates

Report at least:

- compressed package bytes
- RGBA32 base level: `width * height * 4`
- full mip chain approximation: base `* 4/3`
- optional worst case for individually padded next-POT textures

Separate all-package cost from runtime-candidate cost. State that atlasing/compression may reduce residency, but do not use optimistic compression assumptions to hide poor source hygiene.

## Candidate policy

"Text-free" does not imply "safe." A candidate must also pass alpha padding, clipping, background residue, resolution, and uniqueness checks.

When no asset passes all gates, report **0 direct-safe candidates**. It is still useful to provide a short, clearly separated "salvage/repair candidates" list with exact paths, dimensions, and required repairs. Never label repair inputs as production-safe.

Minimum repair guidance commonly includes:

- re-extract from source instead of expanding already-clipped pixels
- add 2–4 px or engine-appropriate alpha-safe padding
- edge-dilate RGB into transparent texels
- remove/repaint baked text
- normalize scale and pivot
- atlas only after visual and alpha QA

## Reporting format

Keep the report decision-oriented:

1. overall verdict
2. logical structure and redundancy
3. alpha/edge evidence
4. baked-text evidence with exact paths
5. exact/near duplicate findings
6. runtime cost
7. direct-safe candidate count
8. salvage list, if useful
9. explicit statement that the package/project was not modified for read-only audits

Use exact absolute paths when the user asks for precise paths. Clearly distinguish measured facts, conservative estimates, visual judgments, and conditional recommendations.
