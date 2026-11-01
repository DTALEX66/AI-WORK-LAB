# Pixel-Perfect Hybrid Vector Reconstruction — Design Specification

Status: approved for implementation planning
Date: 2026-08-22
Project: DESIGN-LAB
Target capability: reconstruct a supplied design image as an editable vector document,
using transparent raster layers only where pure vector reconstruction is unsuitable.

## 1. Objective

Build a production-capable reconstruction pipeline that accepts a raster reference image,
decomposes it with vision models, reconstructs editable design primitives, and drives Adobe
Illustrator to produce a native `.ai` document. The rendered result must achieve at least
99.5% pixel similarity to the reference under a fixed render profile.

The system must optimize for three qualities independently:

1. **Composite fidelity** — the final rendering matches the supplied reference.
2. **Editability** — text, geometric shapes, strokes, icons, gradients, groups, masks, and
   z-order remain editable when reliable reconstruction is possible.
3. **Operational integrity** — every host write is authorized, bounded, journaled,
   read back, and recoverable.

No AI model, generated SVG, document existence, or screenshot alone constitutes successful
reconstruction. Success requires deterministic rendering, numeric comparison, structural
inspection, and Illustrator read-back.

## 2. Product Scope

### 2.1 Supported inputs

- PNG, JPEG, and WebP reference images.
- RGB and RGBA images with an embedded or assumed color profile.
- UI screenshots, posters, logos, icons, flat illustrations, mixed-media designs, and
  photographic or highly textured compositions.
- Images up to 4096 pixels on either axis in the default profile. Larger inputs use tiled
  analysis while retaining one global coordinate space.

The original input is immutable. A normalized sRGB working copy is created for analysis and
comparison, while the original file hash and profile metadata are retained in provenance.

### 2.2 Required outputs

Each successful run produces a self-contained reconstruction bundle:

```text
reconstruction-<run-id>/
├── master.ai
├── master.svg
├── preview.png
├── reference.normalized.png
├── layers/
│   └── <semantic-layer>.png
├── manifest.json
├── structure-report.json
├── metrics.json
├── diff.png
└── provenance.json
```

- `master.ai` is the primary editable Illustrator deliverable.
- `master.svg` is the canonical portable vector representation and is self-contained.
- `layers/` contains tightly cropped transparent raster assets used by the composition.
- Reports contain no credentials, model prompts containing private session data, or unrelated
  filesystem information.

### 2.3 Explicit non-goals

- Recovering the original author's exact layer structure from a flattened image.
- Proving the true appearance of content hidden behind an opaque foreground object.
- Guaranteeing identical rendering at every zoom level, operating system, font rasterizer,
  or color-management configuration.
- Treating a full-canvas copy of the reference as a legitimate reconstruction.
- Automatically acquiring fonts, stock assets, or other content without verified rights.

Hidden content may be plausibly completed for editability, but it is labeled as inferred and
is not included in pixel-fidelity claims for the visible composite.

## 3. Acceptance Contract

### 3.1 Fixed render profile

Pixel claims are valid only under a recorded render profile:

- canvas dimensions equal to the normalized reference;
- sRGB IEC61966-2.1 working space;
- transparent canvas composited over the recorded reference background;
- deterministic SVG rendering through a pinned `resvg` build;
- Illustrator preview exported at the same pixel dimensions;
- no scaling, cropping, hidden reference overlay, or post-comparison substitution.

### 3.2 Composite-fidelity gates

A run passes composite fidelity only when all required gates pass:

- Pixelmatch match ratio is at least `0.995` with threshold `0.1` and anti-alias detection
  enabled.
- SSIM is at least `0.995` on the normalized RGB composite.
- Mean absolute RGBA error is recorded and does not exceed the calibrated golden-corpus limit.
- There is no unresolved high-density diff region larger than 32×32 pixels.
- The deterministic SVG preview and Illustrator-exported preview both pass; a pass from only
  one renderer is insufficient.

The RGBA error limit is calibrated from the first approved golden corpus and then versioned.
Until calibration exists, that metric is informative and cannot override the two fixed gates.

### 3.3 Editability gates

- Recognized text is editable text when an exact font match is available and glyph geometry
  passes comparison; otherwise it is converted to vector outlines and labeled accordingly.
- Regular geometry is represented by native paths or SVG primitives.
- Raster layers are tightly cropped, named, positioned, and associated with a semantic object.
- UI/logo/flat-design profiles allow no more than 5% raster-covered canvas area, excluding
  explicitly photographic source regions.
- Mixed-media profiles allow raster coverage only for regions classified as photographic,
  textured, translucent, or not representable within the vector complexity budget.
- No raster layer may contain an unchanged full-canvas reference or act as an opaque global
  correction layer.
- Layer order, bounds, opacity, blend mode, masks, text disposition, vector/raster type, and
  inferred status are present in `structure-report.json`.

### 3.4 Operational gates

- The source and output roots pass allowlist checks.
- The run has a single-session write authorization naming exact targets.
- A source hash, normalized-reference hash, SVG hash, AI hash, and preview hashes are recorded.
- Illustrator reopens `master.ai`, reads the artboard and layer tree, and exports the preview.
- Failed or cancelled runs never report PASS and retain a resumable journal.
- A rollback removes only artifacts created by the run and verifies their absence.

## 4. Architecture

```text
Reference image
   ↓
Intake & normalization
   ↓
Semantic scene analysis ───────┐
   ↓                           │
Layer decomposition            │
   ↓                           │
Reconstruction IR  ◀───────────┘
   ↓
Vector/raster candidate generation
   ↓
Deterministic render → metric/diff → targeted repair loop
   ↓                                      ↑
   └──────────────────────────────────────┘
   ↓
Illustrator assembly and native read-back
   ↓
Evidence and delivery bundle
```

The pipeline is built around a versioned Reconstruction Intermediate Representation (RIR).
Models propose objects and repairs; only deterministic validators and host read-back can
promote a run to PASS.

## 5. Components

### 5.1 Intake and normalization

Responsibilities:

- validate file type, dimensions, alpha, color profile, and input hash;
- create the normalized sRGB reference;
- classify the reconstruction profile as `flat`, `ui`, `mixed`, or `photographic`;
- allocate a run directory below the project's ignored `.hermes/task-runtime/` and a final
  evidence directory below `.hermes/task-artifacts/` until explicitly accepted for delivery;
- record model and tool versions before inference.

It does not modify the source image or contact a remote model unless the run contract permits
that provider and the user has approved transmission of the specific input.

### 5.2 Semantic scene analyzer

The analyzer produces object hypotheses rather than artwork.

- PaddleOCR provides text strings, confidence, polygons, writing direction, and line grouping.
- OmniParser is used only for UI-like references to identify controls and icon regions.
- Grounding DINO and SAM 2 provide open-vocabulary object boxes and masks.
- Classical computer vision detects lines, rectangles, circles, repeated spacing, dominant
  colors, gradients, corner radii, and alignment grids.
- A vision-language model may classify composition roles, but it may not invent final
  coordinates without geometric verification.

Each hypothesis carries confidence, provenance, and an overlap relationship. Conflicting
hypotheses remain separate until the decomposition or repair stages resolve them.

### 5.3 Layer decomposer

The default graphic-design path uses LayerD because it produces an ordered combination of text,
vector, and raster elements and supports SVG/PSD export. General images use SAM 2 plus BiRefNet
matting. Qwen-Image-Layered is an optional enhancement for difficult semantic RGBA separation,
not a mandatory runtime dependency.

The decomposer works front-to-back:

1. select the most confident visible foreground;
2. estimate a high-resolution alpha matte;
3. extract the visible RGBA layer;
4. complete the newly exposed background only for editability;
5. repeat until the residual background is structurally simple;
6. preserve the visible-composite constraint after every extraction.

Every generated or inpainted pixel is labeled `inferred`. Visible pixels retain a mapping to
the normalized reference.

### 5.4 Reconstruction Intermediate Representation

RIR is a JSON document with schema ID `design-lab/reconstruction-ir/v1`. It contains:

- canvas and color-profile metadata;
- ordered layers and nested groups;
- object IDs stable across repair iterations;
- geometry in reference-pixel coordinates;
- vector paths, primitive parameters, fill/stroke/gradient definitions, and clipping masks;
- text content, font candidates, typography, and outline fallback;
- raster asset references, crop rectangles, alpha bounds, and source mappings;
- blend modes, opacity, visibility, lock state, and inferred flags;
- per-object confidence, renderer error, and repair history.

The RIR does not contain arbitrary executable code. SVG and JSX are generated from validated
RIR nodes.

### 5.5 Candidate generators

Candidate generation is routed by object type:

- **Text:** OCR plus local font matching; candidate fonts are rendered and compared at the
  detected bounds. Exact matches remain text; otherwise the best candidate is outlined or the
  glyph region is traced.
- **Primitive geometry:** deterministic reconstruction from edges, corners, repeated sizes,
  and sampled colors.
- **Icons and flat illustrations:** StarVector 1B, VTracer, and Illustrator Image Trace produce
  candidates. The smallest editable candidate that passes local error checks wins.
- **Complex illustration:** OmniSVG may propose a structural candidate when hardware permits,
  but its output is subjected to the same validation.
- **Photographic, textured, translucent, or hair regions:** a cropped RGBA layer with a refined
  matte is preferred over path explosion.

Model-generated SVG is parsed through an allowlisted SVG subset. Scripts, event handlers,
external URLs, filters outside the supported profile, and filesystem references are rejected.

### 5.6 Render-and-repair optimizer

The optimizer is an iterative state machine:

```text
DRAFT → RENDERED → MEASURED → REPAIR_PLANNED → REPAIRED
   ↑                                             │
   └─────────────────────────────────────────────┘
```

Each iteration:

1. serializes validated RIR to SVG;
2. renders with pinned `resvg`;
3. calculates Pixelmatch, SSIM, RGBA error, edge error, and a diff heatmap;
4. associates high-error regions with RIR objects;
5. chooses one bounded repair class: geometry, color, typography, path, matte, layer order, or
   raster fallback;
6. applies the repair to a copy of the RIR;
7. accepts it only if required metrics improve without violating editability gates.

Optimization proceeds coarse-to-fine: canvas/background, large geometry, text, icons, fine
paths, alpha edges, then residual complex regions. It terminates on PASS, no measurable
improvement, iteration budget exhaustion, cancellation, or invalid output.

Default budgets are 20 global iterations and 10 local iterations per unresolved region. A run
that exhausts either budget is `PARTIAL`, never PASS.

### 5.7 Adobe host adapters

#### Illustrator

Illustrator is the final authority for `.ai` delivery. A repository-owned JSX script consumes a
validated, immutable assembly manifest and performs only these operations:

- create the document and exact artboard;
- create named groups and layers in z-order;
- place vector paths, text, masks, and cropped raster layers;
- save to a run-specific `.ai` target;
- close and reopen the file;
- read back dimensions, layer names, object counts, links/embeds, and save state;
- export the verification preview and editable SVG.

The external-script warning remains enabled. Computer-use automation may navigate the explicit
user approval and launch the script, but screen automation is not accepted as proof that the
document is correct.

#### Photoshop

Photoshop is optional for high-quality matting, PSD inspection, and raster-layer preparation.
A UXP plugin or `.psjs` script uses DOM APIs first and `batchPlay` only inside
`executeAsModal`. It may create a layered PSD companion, but Photoshop output does not replace
the Illustrator `.ai` read-back requirement.

### 5.8 Evidence packager

The packager validates the bundle topology, strips transient logs and private runtime data,
and writes machine-readable lifecycle states:

- `ANALYZED`
- `RECONSTRUCTED_LOCAL`
- `PIXEL_VERIFIED_DETERMINISTIC`
- `ILLUSTRATOR_ASSEMBLED`
- `ILLUSTRATOR_READBACK_VERIFIED`
- `DELIVERY_READY`

Only `DELIVERY_READY` maps to a successful user-facing completion claim.

## 6. Model and Runtime Strategy

The verified workstation GPU is an NVIDIA GeForce RTX 5060 with 8 GB VRAM. The default stack
therefore avoids a mandatory 4B/8B model:

- LayerD and BiRefNet for layer decomposition;
- SAM 2 for prompted masks;
- PaddleOCR for text;
- OmniParser only for UI profiles;
- StarVector 1B and VTracer for vector candidates;
- deterministic geometry reconstruction for common primitives;
- `resvg`, Pixelmatch, and scikit-image metrics for the feedback loop.

OmniSVG 4B/8B and Qwen-Image-Layered are optional enhancement workers using quantization,
CPU offload, a separately approved remote provider, or stronger future hardware. Failure or
absence of an optional model must degrade to another candidate path rather than block basic
reconstruction.

Models, weights, datasets, and binaries require a registry entry with version, source URL,
license, checksum, local storage class, and allowed commercial-use status before use.

## 7. Failure Handling and Recovery

- Invalid input: stop before inference and report exact validation failures.
- Missing optional model: route to the next candidate generator and record the fallback.
- Out-of-memory: reduce tile size or move the optional worker to CPU; do not silently lower
  output resolution.
- Invalid SVG: reject the candidate, retain the previous RIR, and continue with another route.
- Metric regression: discard the repair and restore the last accepted RIR checkpoint.
- Font uncertainty: outline the text and mark it `font-unresolved`.
- Illustrator dialog or unsaved document: pause host writes and request explicit user action;
  never close an unidentified document.
- Host crash or RPC disconnect: preserve the journal, wait for a clean host restart, and resume
  from the last pre-host checkpoint.
- Pixel threshold not reached: deliver only if the user explicitly accepts `PARTIAL`; otherwise
  retain artifacts as diagnostic evidence.

All cleanup targets are exact run-relative paths. Cleanup verifies filesystem absence and never
uses a broad ignored-file deletion.

## 8. Security, Privacy, and Rights

- Inputs remain local by default.
- Remote inference is opt-in per file and provider.
- No credentials, `.env` files, auth stores, browser state, model prompts containing private
  session data, or unrelated files enter evidence or Git.
- Tools may write only to the current run directory and exact approved delivery targets.
- SVG is treated as untrusted XML and sanitized before rendering or opening in Adobe software.
- Raster assets retain source and license lineage. Unknown rights remain `UNVERIFIED` and block
  commercial-release claims.
- Reconstructing a design does not establish ownership or permission to use it.

## 9. Test Strategy

### 9.1 Unit and property tests

- color normalization and profile recording;
- RIR schema validation and stable object IDs;
- SVG sanitization and path bounds;
- crop/placement round trips;
- alpha compositing and blend ordering;
- metric calculations and threshold boundaries;
- repair acceptance/rejection;
- rollback target validation.

### 9.2 Golden corpus

The initial corpus contains rights-cleared references for:

1. logo/icon with solid fills;
2. UI screen with text and repeated components;
3. poster with typography, gradients, shadows, and a photograph;
4. flat illustration with overlapping shapes;
5. complex illustration with hair and translucent effects;
6. mixed-media commercial layout.

Every case records source rights, expected profile, minimum editability, expected raster budget,
and metric thresholds. Golden assets are immutable; new baselines require review.

### 9.3 Integration gates

- end-to-end RIR → SVG → deterministic preview without Adobe;
- clean-tree reproducibility from a fresh project-local environment;
- malformed/model-adversarial SVG rejection;
- cancellation and resume from every state boundary;
- Illustrator assembly, reopen/read-back, and preview export on a synthetic fixture;
- Photoshop UXP matting/PSD fixture where Photoshop is present.

### 9.4 Maturity criteria

The solution is mature only after:

- all unit and integration gates pass;
- all six golden cases meet their declared pixel and editability gates;
- three consecutive clean runs produce identical deterministic SVG previews and equivalent
  Illustrator read-back;
- a forced interruption resumes without corrupting or duplicating outputs;
- rollback removes only the run's artifacts;
- exact-SHA CI verifies the repository gates;
- a newly installed runtime is tested separately from source or CI claims.

## 10. Delivery Phases

### Phase 1 — Deterministic core

Implement intake, normalization, RIR, primitive reconstruction, SVG serialization, deterministic
rendering, metrics, diff maps, checkpoints, and the first flat/UI golden cases.

### Phase 2 — AI decomposition and hybrid layers

Integrate OCR, LayerD, SAM 2/BiRefNet, vector candidates, alpha-layer fallback, font matching,
and the complete six-case golden corpus.

### Phase 3 — Adobe production adapters

Install or verify supported Adobe runtimes, implement Illustrator JSX assembly/read-back,
implement optional Photoshop UXP preparation, and prove interruption recovery.

### Phase 4 — Optimization and hardening

Add bounded AI-assisted repairs, performance profiling, model fallbacks, license gates, SVG
security tests, reproducibility checks, and operator documentation.

### Phase 5 — Release qualification

Run all golden cases three times from clean state, verify exact-SHA CI, package a sample delivery,
and publish a truthful capability record distinguishing local, CI, host, and installed-runtime
evidence.

## 11. Architectural Decisions

1. SVG is the canonical intermediate; `.ai` is the authoritative editable delivery.
2. AI proposes structure and repairs but cannot award PASS.
3. Raster fallback is a first-class, bounded representation rather than a hidden failure mode.
4. Pixel fidelity and editability are separate gates.
5. Deterministic rendering precedes Adobe assembly to keep most iterations fast and reproducible.
6. Illustrator host read-back is mandatory because SVG success does not prove native `.ai`
   correctness.
7. The default runtime fits an 8 GB GPU; heavyweight models remain optional.
8. A visible-composite claim never implies that inferred hidden content is historically correct.

## 12. Definition of Done

The capability is complete when a user can supply a supported reference image and receive a
self-contained bundle whose `.ai` file is editable, whose visible rendering passes all fixed
pixel gates, whose transparent raster layers are semantic and bounded, whose reports expose all
fallbacks and uncertainties, and whose Illustrator read-back and evidence can be reproduced from
the same versioned inputs and runtime contract.
