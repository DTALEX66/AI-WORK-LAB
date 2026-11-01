# Vector Reconstruction AI Decomposition Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add bounded local AI providers that convert a normalized reference into semantic, editable vector and transparent-raster RIR layers without weakening deterministic fidelity gates.

**Architecture:** Model workers implement a provider SPI and write only proposal JSON and run-relative assets. A deterministic fusion layer validates, scores, and selects proposals; model output never directly becomes trusted SVG or PASS evidence.

**Tech Stack:** Python 3.12, LayerD, SAM 2, BiRefNet, PaddleOCR, OmniParser for UI profiles, StarVector 1B, VTracer, Pillow/NumPy, existing deterministic core.

**Spec:** `docs/superpowers/specs/2026-08-22-pixel-perfect-vector-reconstruction-design.md`

## Global Constraints

- Default execution must fit an RTX 5060 with 8 GB VRAM; 4B/8B models remain optional.
- Inputs remain local unless a per-file run contract explicitly permits a remote provider.
- Every model and binary requires version, source, license, checksum, storage class, and commercial-use status.
- Provider absence or OOM produces an explicit fallback event, never silent resolution loss.
- AI output is untrusted and must pass RIR/SVG validation and deterministic comparison.

---

### Task 1: Provider SPI, registry, and preflight

**Files:**
- Create: `packages/capabilities/reconstruction/providers/__init__.py`
- Create: `packages/capabilities/reconstruction/providers/base.py`
- Create: `packages/capabilities/reconstruction/providers/registry.py`
- Create: `design-lab/config/reconstruction-models.json`
- Test: `design-lab/tests/test_reconstruction_providers.py`

**Interfaces:**
- Produces: `Provider.describe() -> ProviderDescriptor`, `Provider.preflight() -> PreflightResult`, and `Provider.propose(request: ProposalRequest) -> ProposalResult`.
- Produces: `load_enabled_providers(contract: dict, registry: dict) -> list[Provider]`.

- [ ] **Step 1: Write failing registry and boundary tests**

```python
def test_unregistered_weight_is_rejected(self):
    with self.assertRaises(ProviderRegistryError):
        load_enabled_providers(self.contract_for("unknown-model"), self.registry)

def test_remote_provider_requires_per_file_consent(self):
    with self.assertRaises(RemoteProviderDenied):
        load_enabled_providers(self.remote_contract(consent=False), self.registry)
```

- [ ] **Step 2: Run the provider tests and confirm RED**

Run: `python -m unittest discover -s design-lab/tests -p "test_reconstruction_providers.py" -v`
Expected: FAIL because the SPI is absent.

- [ ] **Step 3: Implement typed provider results and fail-closed loading**

```python
@dataclass(frozen=True)
class ProposalResult:
    provider_id: str
    provider_version: str
    proposal_path: Path
    asset_paths: tuple[Path, ...]
    warnings: tuple[str, ...]

class Provider(Protocol):
    def describe(self) -> ProviderDescriptor: ...
    def preflight(self) -> PreflightResult: ...
    def propose(self, request: ProposalRequest) -> ProposalResult: ...
```

Registry loading verifies SHA-256, license status, enabled task types, device policy, and that
all emitted paths resolve below the current run directory.

- [ ] **Step 4: Run tests with present, missing, OOM, and denied providers**

Expected: PASS; each fallback is represented as a structured event.

- [ ] **Step 5: Commit the provider boundary**

```bash
git add -- packages/capabilities/reconstruction/providers design-lab/config/reconstruction-models.json design-lab/tests/test_reconstruction_providers.py
git commit -m "feat(reconstruction): define bounded model provider SPI"
```

### Task 2: OCR, UI parsing, and deterministic primitive analysis

**Files:**
- Create: `packages/capabilities/reconstruction/providers/paddleocr_provider.py`
- Create: `packages/capabilities/reconstruction/providers/omniparser_provider.py`
- Create: `packages/capabilities/reconstruction/geometry.py`
- Create: `packages/capabilities/reconstruction/font_match.py`
- Test: `design-lab/tests/test_reconstruction_semantics.py`

**Interfaces:**
- Produces: `TextHypothesis(text, polygon, confidence, direction)`.
- Produces: `PrimitiveHypothesis(kind, bounds, fill, stroke, radius, confidence)`.
- Produces: `match_font(text: str, crop: Path, candidates: Sequence[FontFace]) -> FontMatch`.

- [ ] **Step 1: Write failing text, geometry, and font-fallback tests**

```python
def test_font_remains_text_only_when_rendered_crop_passes(self):
    result = match_font("DESIGN", CROP, [EXACT_FACE, WRONG_FACE])
    self.assertEqual(result.face, EXACT_FACE)
    self.assertTrue(result.keep_editable_text)

def test_uncertain_font_routes_to_outline(self):
    result = match_font("设计", CROP, [WRONG_FACE])
    self.assertFalse(result.keep_editable_text)
    self.assertEqual(result.fallback, "outline")
```

- [ ] **Step 2: Run semantic tests and confirm RED**

Run: `python -m unittest discover -s design-lab/tests -p "test_reconstruction_semantics.py" -v`
Expected: FAIL because semantic providers and matchers are missing.

- [ ] **Step 3: Implement proposal normalization**

```python
def normalize_text_detection(raw: dict, canvas: Size) -> TextHypothesis:
    polygon = clamp_polygon(raw["polygon"], canvas)
    confidence = float(raw["confidence"])
    if not 0.0 <= confidence <= 1.0:
        raise ProposalValidationError("OCR confidence outside [0,1]")
    return TextHypothesis(str(raw["text"]), polygon, confidence, raw.get("direction", "ltr"))
```

OmniParser runs only for `ui`; geometry analysis remains available without any model; font
matching rasterizes only enumerated local fonts and stores no font-file contents in evidence.

- [ ] **Step 4: Run fixture tests for Latin, Chinese, UI control, rectangle, circle, and gradient**

Expected: PASS with stable normalized coordinates and deterministic proposal JSON.

- [ ] **Step 5: Commit semantic analysis**

```bash
git add -- packages/capabilities/reconstruction/providers/paddleocr_provider.py packages/capabilities/reconstruction/providers/omniparser_provider.py packages/capabilities/reconstruction/geometry.py packages/capabilities/reconstruction/font_match.py design-lab/tests/test_reconstruction_semantics.py
git commit -m "feat(reconstruction): analyze text and design primitives"
```

### Task 3: Semantic RGBA layer decomposition

**Files:**
- Create: `packages/capabilities/reconstruction/providers/layerd_provider.py`
- Create: `packages/capabilities/reconstruction/providers/sam_birefnet_provider.py`
- Create: `packages/capabilities/reconstruction/matting.py`
- Test: `design-lab/tests/test_reconstruction_layers.py`

**Interfaces:**
- Produces: `LayerProposal(id, semantic_name, z_index, crop, alpha_bounds, asset_path, inferred, confidence)`.
- Produces: `decompose_layers(request: ProposalRequest, providers: Sequence[Provider]) -> list[LayerProposal]`.

- [ ] **Step 1: Write failing alpha, crop, z-order, and inference-label tests**

```python
def test_transparent_layer_is_tightly_cropped_and_recomposes(self):
    layers = decompose_fixture(COMPOSITE)
    self.assertTrue(all(layer.crop == alpha_crop(layer.asset_path) for layer in layers[1:]))
    self.assertLessEqual(pixel_error(composite(layers), COMPOSITE), 0.005)

def test_completed_occlusion_is_marked_inferred(self):
    self.assertTrue(any(layer.inferred for layer in decompose_fixture(OCCLUDED)))
```

- [ ] **Step 2: Run layer tests and confirm RED**

Run: `python -m unittest discover -s design-lab/tests -p "test_reconstruction_layers.py" -v`
Expected: FAIL because decomposition providers are missing.

- [ ] **Step 3: Implement profile routing and alpha normalization**

```python
def decompose_layers(request, providers):
    ordered = _providers_for_profile(request.profile, providers)
    for provider in ordered:
        result = _try_provider(provider, request)
        if result.ok:
            return validate_and_crop_layers(result.layers, request.run_dir)
    raise NoLayerProviderSucceeded(tuple(event_log()))
```

Use LayerD first for `flat`, `ui`, and `mixed`; use prompted SAM 2 plus BiRefNet for difficult
foreground mattes. Preserve the original visible pixels at alpha=1; label inpainted occlusions.

- [ ] **Step 4: Run synthetic recomposition, OOM fallback, and missing-model tests**

Expected: PASS; no output escapes the run root and no fallback changes canvas dimensions.

- [ ] **Step 5: Commit layer decomposition**

```bash
git add -- packages/capabilities/reconstruction/providers/layerd_provider.py packages/capabilities/reconstruction/providers/sam_birefnet_provider.py packages/capabilities/reconstruction/matting.py design-lab/tests/test_reconstruction_layers.py
git commit -m "feat(reconstruction): decompose semantic RGBA layers"
```

### Task 4: Vector candidates and hybrid fusion

**Files:**
- Create: `packages/capabilities/reconstruction/providers/vtracer_provider.py`
- Create: `packages/capabilities/reconstruction/providers/starvector_provider.py`
- Create: `packages/capabilities/reconstruction/vector_candidates.py`
- Create: `packages/capabilities/reconstruction/fusion.py`
- Test: `design-lab/tests/test_reconstruction_fusion.py`

**Interfaces:**
- Produces: `VectorCandidate(provider_id, object_id, svg_fragment, node_count, local_metrics)`.
- Produces: `fuse_scene(analysis: SceneAnalysis, layers: Sequence[LayerProposal], candidates: Sequence[VectorCandidate]) -> dict` containing validated RIR.

- [ ] **Step 1: Write failing candidate-selection and anti-cheat tests**

```python
def test_smallest_passing_vector_candidate_wins(self):
    selected = select_candidate([passing_large(), failing_small(), passing_small()])
    self.assertEqual(selected.node_count, passing_small().node_count)

def test_full_canvas_reference_layer_is_rejected(self):
    with self.assertRaises(ReferenceOverlayError):
        fuse_scene(analysis(), [opaque_full_canvas_reference()], [])
```

- [ ] **Step 2: Run fusion tests and confirm RED**

Run: `python -m unittest discover -s design-lab/tests -p "test_reconstruction_fusion.py" -v`
Expected: FAIL because candidate selection and fusion are missing.

- [ ] **Step 3: Implement bounded candidate evaluation**

```python
def select_candidate(candidates):
    passing = [c for c in candidates if c.local_metrics.match_ratio >= 0.995 and c.safe]
    if not passing:
        return None
    return min(passing, key=lambda c: (c.node_count, len(c.svg_fragment), c.provider_id))
```

VTracer runs as a pinned subprocess; StarVector 1B runs only after model preflight. Every fragment
passes the SVG sanitizer before local rendering. Fusion enforces the 5% flat/UI raster budget and
profile-specific semantic raster exceptions.

- [ ] **Step 4: Run flat icon, UI text, mixed poster, provider-failure, and raster-budget tests**

Expected: PASS and a valid RIR for every fixture.

- [ ] **Step 5: Commit vector fusion**

```bash
git add -- packages/capabilities/reconstruction/providers/vtracer_provider.py packages/capabilities/reconstruction/providers/starvector_provider.py packages/capabilities/reconstruction/vector_candidates.py packages/capabilities/reconstruction/fusion.py design-lab/tests/test_reconstruction_fusion.py
git commit -m "feat(reconstruction): fuse vector and transparent layer proposals"
```

### Task 5: Diff-guided repair loop and AI vertical slice

**Files:**
- Create: `packages/capabilities/reconstruction/repair.py`
- Modify: `packages/capabilities/reconstruction/pipeline.py`
- Modify: `design-lab/scripts/verify_reconstruction_pipeline.py`
- Test: `design-lab/tests/test_reconstruction_repair.py`

**Interfaces:**
- Produces: `plan_repair(rir: dict, metrics: FidelityMetrics, diff_map: Path) -> RepairPlan`.
- Produces: `apply_repair(rir: dict, plan: RepairPlan) -> dict` without mutating its argument.

- [ ] **Step 1: Write failing bounded-improvement tests**

```python
def test_regressing_repair_is_discarded(self):
    result = repair_once(self.rir, self.reference, regressing_planner)
    self.assertEqual(result.rir_hash, hash_rir(self.rir))

def test_iteration_budget_yields_partial_not_pass(self):
    result = optimize(self.rir, self.reference, global_budget=1)
    self.assertEqual(result.state, "PARTIAL")
```

- [ ] **Step 2: Run repair tests and confirm RED**

Run: `python -m unittest discover -s design-lab/tests -p "test_reconstruction_repair.py" -v`
Expected: FAIL because the repair state machine is missing.

- [ ] **Step 3: Implement deterministic repair acceptance**

```python
def accept_repair(before, after):
    return (after.match_ratio, after.ssim, -after.mean_rgba_error) > (
        before.match_ratio, before.ssim, -before.mean_rgba_error
    ) and after.editability_violations == ()
```

Repair order is geometry, color, typography, path, matte, z-order, then bounded raster fallback.
Budgets are 20 global iterations and 10 local iterations per region.

- [ ] **Step 4: Run all reconstruction tests and canonical project gates**

Run: `python -m unittest discover -s design-lab/tests -p "test_reconstruction_*.py" -v`
Run: `python scripts/run_python_tests.py`
Run: `python design-lab/scripts/verify_design_lab.py`
Expected: PASS; AI providers remain structural unless real runtime evidence is supplied.

- [ ] **Step 5: Commit the AI-assisted local pipeline**

```bash
git add -- packages/capabilities/reconstruction/repair.py packages/capabilities/reconstruction/pipeline.py design-lab/scripts/verify_reconstruction_pipeline.py design-lab/tests/test_reconstruction_repair.py
git commit -m "feat(reconstruction): add diff-guided repair loop"
```
