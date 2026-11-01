# Vector Reconstruction Deterministic Core Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a local, deterministic pipeline that validates an image, represents editable objects in RIR, emits sanitized SVG, renders it reproducibly, and reports pixel metrics and resumable run state.

**Architecture:** A new `reconstruction` Python package owns versioned contracts and pure pipeline logic. Runtime artifacts stay under `.hermes/`; canonical schemas, tests, fixtures, and verifiers stay tracked. AI providers and Adobe hosts are not dependencies of this plan.

**Tech Stack:** Python 3.12, `unittest`, `jsonschema`, Pillow, NumPy, scikit-image, pinned `resvg` CLI, JSON Schema Draft 2020-12.

**Spec:** `docs/superpowers/specs/2026-08-22-pixel-perfect-vector-reconstruction-design.md`

## Global Constraints

- Pixelmatch-equivalent match ratio gate: `>= 0.995` at color threshold `0.1` with anti-alias classification.
- SSIM gate: `>= 0.995` on normalized sRGB RGB output.
- Default maximum input axis: `4096` pixels; larger images retain a global coordinate system and use tiles.
- Canonical schema ID: `design-lab/reconstruction-ir/v1`.
- Runtime files: `.hermes/task-runtime/reconstruction/<run-id>/`; accepted local evidence: `.hermes/task-artifacts/reconstruction/<run-id>/`.
- No full-canvas reference overlay, executable SVG, external SVG URL, silent resolution reduction, remote inference, or Adobe write.
- Tests use the exact project interpreter and the repository's `unittest` conventions.

---

### Task 1: Versioned RIR and run-contract schemas

**Files:**
- Create: `design-lab/schemas/reconstruction/reconstruction-ir.schema.json`
- Create: `design-lab/schemas/reconstruction/reconstruction-run.schema.json`
- Create: `packages/capabilities/reconstruction/__init__.py`
- Create: `packages/capabilities/reconstruction/contracts.py`
- Test: `design-lab/tests/test_reconstruction_contracts.py`

**Interfaces:**
- Produces: `validate_rir(value: dict) -> None`, `validate_run_contract(value: dict) -> None`, `ContractError(ValueError)`.
- Produces schema constants `RIR_SCHEMA_ID` and `RUN_SCHEMA_ID` used by every later task.

- [ ] **Step 1: Write failing schema and API tests**

```python
class ReconstructionContractTests(unittest.TestCase):
    def test_minimal_rir_validates(self):
        validate_rir({
            "schemaVersion": "design-lab/reconstruction-ir/v1",
            "canvas": {"width": 64, "height": 64, "colorSpace": "srgb"},
            "layers": [],
        })

    def test_external_raster_reference_is_rejected(self):
        value = minimal_rir()
        value["layers"] = [{"id": "x", "type": "raster", "href": "https://example.test/x.png"}]
        with self.assertRaises(ContractError):
            validate_rir(value)
```

- [ ] **Step 2: Run the tests and confirm RED**

Run: `python -m unittest discover -s design-lab/tests -p "test_reconstruction_contracts.py" -v`
Expected: FAIL because `reconstruction.contracts` and the schemas do not exist.

- [ ] **Step 3: Implement closed schemas and validator wrappers**

```python
RIR_SCHEMA_ID = "design-lab/reconstruction-ir/v1"

class ContractError(ValueError):
    pass

def _validate(value: dict, schema_path: Path) -> None:
    try:
        jsonschema.Draft202012Validator(json.loads(schema_path.read_text("utf-8"))).validate(value)
    except jsonschema.ValidationError as exc:
        raise ContractError(exc.message) from exc
```

Require positive integer canvas dimensions; unique object IDs; allowlisted layer types
`group`, `path`, `primitive`, `text`, and `raster`; project-relative raster references; explicit
opacity, bounds, inferred state, and z-order; and `additionalProperties: false` on contract nodes.

- [ ] **Step 4: Run targeted tests and the existing schema-dependent suite**

Run: `python -m unittest discover -s design-lab/tests -p "test_reconstruction_contracts.py" -v`
Expected: PASS.
Run: `python scripts/run_python_tests.py`
Expected: PASS with no existing regression.

- [ ] **Step 5: Commit the independently reviewable contract**

```bash
git add -- design-lab/schemas/reconstruction packages/capabilities/reconstruction/__init__.py packages/capabilities/reconstruction/contracts.py design-lab/tests/test_reconstruction_contracts.py
git commit -m "feat(reconstruction): define closed RIR contracts"
```

### Task 2: Immutable intake and sRGB normalization

**Files:**
- Create: `packages/capabilities/reconstruction/requirements-core.in`
- Create: `packages/capabilities/reconstruction/intake.py`
- Test: `design-lab/tests/test_reconstruction_intake.py`
- Create: `design-lab/tests/fixtures/reconstruction/flat-64.png`

**Interfaces:**
- Consumes: `validate_run_contract` from Task 1.
- Produces: `IntakeResult(source_sha256: str, normalized_sha256: str, width: int, height: int, mode: str, normalized_path: Path)`.
- Produces: `normalize_reference(source: Path, run_dir: Path, max_axis: int = 4096) -> IntakeResult`.

- [ ] **Step 1: Add failing immutability, alpha, and oversize tests**

```python
def test_normalization_preserves_source_and_writes_srgb_copy(self):
    before = sha256(FIXTURE)
    result = normalize_reference(FIXTURE, self.run_dir)
    self.assertEqual(sha256(FIXTURE), before)
    self.assertEqual((result.width, result.height), (64, 64))
    self.assertTrue(result.normalized_path.is_relative_to(self.run_dir))

def test_zero_dimension_and_unsupported_mode_fail_closed(self):
    with self.assertRaises(IntakeError):
        normalize_reference(self.invalid_fixture, self.run_dir)
```

- [ ] **Step 2: Run the intake tests and confirm RED**

Run: `python -m unittest discover -s design-lab/tests -p "test_reconstruction_intake.py" -v`
Expected: FAIL because `normalize_reference` is missing.

- [ ] **Step 3: Implement deterministic normalization**

```python
def normalize_reference(source: Path, run_dir: Path, max_axis: int = 4096) -> IntakeResult:
    source = source.resolve(strict=True)
    run_dir = run_dir.resolve()
    with Image.open(source) as image:
        image.load()
        if image.width <= 0 or image.height <= 0:
            raise IntakeError("invalid dimensions")
        normalized = ImageCms.profileToProfile(image.convert("RGBA"), _source_profile(image), _srgb_profile(), outputMode="RGBA")
        destination = run_dir / "reference.normalized.png"
        destination.parent.mkdir(parents=True, exist_ok=True)
        normalized.save(destination, format="PNG", optimize=False, compress_level=9)
    return _build_result(source, destination)
```

Declare `Pillow>=11.3,<13`, `numpy>=2.2,<3`, and `scikit-image>=0.25,<0.27` in the
feature-specific input file. Installation and locking occur only in a project-local environment
when execution begins.

- [ ] **Step 4: Run the tests twice and compare normalized hashes**

Run the targeted command twice.
Expected: PASS both times and identical `normalized_sha256` values.

- [ ] **Step 5: Commit intake as a separate capability**

```bash
git add -- packages/capabilities/reconstruction/requirements-core.in packages/capabilities/reconstruction/intake.py design-lab/tests/test_reconstruction_intake.py design-lab/tests/fixtures/reconstruction/flat-64.png
git commit -m "feat(reconstruction): add immutable image intake"
```

### Task 3: Safe RIR-to-SVG serialization

**Files:**
- Create: `packages/capabilities/reconstruction/svg.py`
- Create: `packages/capabilities/reconstruction/svg_safety.py`
- Test: `design-lab/tests/test_reconstruction_svg.py`

**Interfaces:**
- Consumes: a Task 1 validated RIR and run-relative raster assets.
- Produces: `serialize_svg(rir: dict, asset_root: Path) -> bytes`.
- Produces: `sanitize_svg(svg: bytes) -> bytes` and `UnsafeSVGError(ValueError)`.

- [ ] **Step 1: Write failing serialization and adversarial tests**

```python
def test_primitive_serializes_with_exact_viewbox(self):
    svg = serialize_svg(rectangle_rir(), FIXTURES)
    self.assertIn(b'viewBox="0 0 64 64"', svg)
    self.assertIn(b'<rect', svg)

def test_script_event_and_external_href_are_rejected(self):
    for payload in (b"<svg><script/></svg>", b'<svg onload="x()"/>', b'<svg><image href="https://x"/></svg>'):
        with self.assertRaises(UnsafeSVGError):
            sanitize_svg(payload)
```

- [ ] **Step 2: Run the SVG tests and confirm RED**

Run: `python -m unittest discover -s design-lab/tests -p "test_reconstruction_svg.py" -v`
Expected: FAIL because serializers are missing.

- [ ] **Step 3: Implement a generated allowlist, not string concatenation**

```python
ALLOWED_ELEMENTS = {"svg", "g", "path", "rect", "circle", "ellipse", "line", "polyline", "polygon", "text", "defs", "linearGradient", "radialGradient", "stop", "clipPath", "mask", "image"}
FORBIDDEN_ATTRIBUTES = {"onload", "onclick", "onerror"}

def sanitize_svg(svg: bytes) -> bytes:
    root = DefusedET.fromstring(svg)
    for node in root.iter():
        if local_name(node.tag) not in ALLOWED_ELEMENTS:
            raise UnsafeSVGError(f"forbidden element: {node.tag}")
        _validate_attributes(node)
    return canonical_xml(root)
```

Raster data is embedded from validated run-relative files as `data:image/png;base64,...` only;
SVG input never reads an arbitrary `href`.

- [ ] **Step 4: Run tests and inspect canonical bytes**

Run the targeted tests twice.
Expected: PASS and byte-identical output for the same RIR.

- [ ] **Step 5: Commit SVG safety and serialization**

```bash
git add -- packages/capabilities/reconstruction/svg.py packages/capabilities/reconstruction/svg_safety.py design-lab/tests/test_reconstruction_svg.py
git commit -m "feat(reconstruction): emit sanitized deterministic SVG"
```

### Task 4: Deterministic renderer and fidelity metrics

**Files:**
- Create: `design-lab/config/reconstruction-tools.json`
- Create: `packages/capabilities/reconstruction/render.py`
- Create: `packages/capabilities/reconstruction/metrics.py`
- Test: `design-lab/tests/test_reconstruction_metrics.py`

**Interfaces:**
- Produces: `render_svg(svg_path: Path, output_path: Path, profile: RenderProfile) -> RenderResult`.
- Produces: `compare_images(reference: Path, actual: Path) -> FidelityMetrics`.
- `FidelityMetrics` exposes `match_ratio`, `ssim`, `mean_rgba_error`, `max_diff_window`, and `passed`.

- [ ] **Step 1: Write failing exact-match and localized-diff tests**

```python
def test_identical_images_pass(self):
    metrics = compare_images(FIXTURE, FIXTURE)
    self.assertEqual(metrics.match_ratio, 1.0)
    self.assertEqual(metrics.ssim, 1.0)
    self.assertTrue(metrics.passed)

def test_32_pixel_dense_error_fails(self):
    metrics = compare_images(FIXTURE, altered_square(33))
    self.assertFalse(metrics.passed)
    self.assertGreater(metrics.max_diff_window, 0)
```

- [ ] **Step 2: Run tests and confirm RED**

Run: `python -m unittest discover -s design-lab/tests -p "test_reconstruction_metrics.py" -v`
Expected: FAIL because metrics and render profile are missing.

- [ ] **Step 3: Implement pinned-tool checks and metrics**

```python
def compare_images(reference: Path, actual: Path) -> FidelityMetrics:
    ref, out = _load_rgba_pair(reference, actual)
    mismatch = perceptual_mismatch_mask(ref, out, threshold=0.1)
    match_ratio = 1.0 - float(mismatch.sum()) / mismatch.size
    score = structural_similarity(ref[..., :3], out[..., :3], channel_axis=2, data_range=255)
    window = max_window_density(mismatch, size=32)
    return FidelityMetrics(match_ratio, score, mean_abs_rgba(ref, out), window,
                           match_ratio >= 0.995 and score >= 0.995 and window == 0)
```

The tool registry stores an exact `resvg` version and SHA-256; `render_svg` rejects a missing or
mismatched binary rather than downloading one.

- [ ] **Step 4: Run metrics tests and one real render round trip**

Run the targeted suite.
Expected: PASS; a 64×64 rectangle RIR renders to 64×64 PNG and passes against its golden image.

- [ ] **Step 5: Commit rendering and metric gates**

```bash
git add -- design-lab/config/reconstruction-tools.json packages/capabilities/reconstruction/render.py packages/capabilities/reconstruction/metrics.py design-lab/tests/test_reconstruction_metrics.py
git commit -m "feat(reconstruction): add deterministic fidelity gates"
```

### Task 5: Resumable pipeline, CLI, and canonical verifier

**Files:**
- Create: `packages/capabilities/reconstruction/state.py`
- Create: `packages/capabilities/reconstruction/pipeline.py`
- Create: `design-lab/scripts/reconstruct_design.py`
- Create: `design-lab/scripts/verify_reconstruction_pipeline.py`
- Modify: `design-lab/scripts/verify_design_lab.py`
- Test: `design-lab/tests/test_reconstruction_pipeline.py`

**Interfaces:**
- Produces: `run_reconstruction(contract_path: Path) -> RunSummary`.
- Produces CLI subcommands `analyze`, `reconstruct`, `verify`, `resume`, and `rollback`.
- Produces verifier summary `RECONSTRUCTION_PIPELINE=PASS cases=<n>`.

- [ ] **Step 1: Write failing lifecycle, resume, and rollback tests**

```python
def test_interrupted_run_resumes_from_last_accepted_checkpoint(self):
    first = run_until(self.contract, stop_after="MEASURED")
    resumed = run_reconstruction(first.contract_path)
    self.assertEqual(resumed.transitions.count("ANALYZED"), 1)
    self.assertEqual(resumed.state, "PIXEL_VERIFIED_DETERMINISTIC")

def test_rollback_rejects_path_outside_run_root(self):
    with self.assertRaises(RollbackBoundaryError):
        rollback_run(self.run_dir, Path("..") / "reports")
```

- [ ] **Step 2: Run pipeline tests and confirm RED**

Run: `python -m unittest discover -s design-lab/tests -p "test_reconstruction_pipeline.py" -v`
Expected: FAIL because state transitions and CLI do not exist.

- [ ] **Step 3: Implement atomic checkpoints and the no-AI baseline pipeline**

```python
ALLOWED_TRANSITIONS = {
    "CREATED": {"ANALYZED", "FAILED"},
    "ANALYZED": {"RECONSTRUCTED_LOCAL", "FAILED"},
    "RECONSTRUCTED_LOCAL": {"PIXEL_VERIFIED_DETERMINISTIC", "PARTIAL", "FAILED"},
}

def write_checkpoint(path: Path, state: dict) -> None:
    temp = path.with_suffix(".new")
    temp.write_text(json.dumps(state, sort_keys=True, separators=(",", ":")), encoding="utf-8")
    temp.replace(path)
```

The baseline reconstructs flat primitives from an explicit RIR fixture, proving orchestration
without claiming model decomposition.

- [ ] **Step 4: Run targeted, full Python, and canonical verifier gates**

Run: `python -m unittest discover -s design-lab/tests -p "test_reconstruction_pipeline.py" -v`
Run: `python scripts/run_python_tests.py`
Run: `python design-lab/scripts/verify_design_lab.py`
Expected: all PASS and the canonical total increases by one verifier.

- [ ] **Step 5: Commit the deterministic vertical slice**

```bash
git add -- packages/capabilities/reconstruction/state.py packages/capabilities/reconstruction/pipeline.py design-lab/scripts/reconstruct_design.py design-lab/scripts/verify_reconstruction_pipeline.py design-lab/scripts/verify_design_lab.py design-lab/tests/test_reconstruction_pipeline.py
git commit -m "feat(reconstruction): add resumable deterministic pipeline"
```

### Task 6: Evidence packager and complete bundle contract

**Files:**
- Create: `design-lab/schemas/reconstruction/reconstruction-bundle.schema.json`
- Create: `packages/capabilities/reconstruction/evidence.py`
- Create: `design-lab/scripts/verify_reconstruction_bundle.py`
- Modify: `design-lab/scripts/verify_design_lab.py`
- Test: `design-lab/tests/test_reconstruction_evidence.py`

**Interfaces:**
- Produces: `package_evidence(run_dir: Path, evidence_dir: Path) -> BundleSummary`.
- Produces: `validate_bundle(bundle_dir: Path) -> BundleSummary`.
- Produces verifier summary `RECONSTRUCTION_BUNDLE=PASS artifacts=<n> state=<state>`.

- [ ] **Step 1: Write failing topology, hash, lifecycle, and privacy tests**

```python
def test_bundle_requires_all_deterministic_artifacts_and_matching_hashes(self):
    summary = validate_bundle(complete_fixture_bundle())
    self.assertEqual(summary.state, "PIXEL_VERIFIED_DETERMINISTIC")

def test_deterministic_bundle_cannot_claim_delivery_ready(self):
    with self.assertRaises(EvidenceError):
        validate_bundle(bundle_with_state("DELIVERY_READY", illustrator_readback=None))

def test_transient_logs_and_unrelated_paths_are_rejected(self):
    with self.assertRaises(EvidenceError):
        package_evidence(run_with_private_or_transient_file(), self.evidence_dir)
```

- [ ] **Step 2: Run evidence tests and confirm RED**

Run: `python -m unittest discover -s design-lab/tests -p "test_reconstruction_evidence.py" -v`
Expected: FAIL because the packager and bundle schema do not exist.

- [ ] **Step 3: Implement fail-closed packaging and lifecycle promotion**

Require the normalized reference, canonical SVG, deterministic preview, manifest,
structure report, metrics, diff, provenance, run journal, run contract, and declared
semantic raster layers. Copy only declared run-relative artifacts, verify every hash after
copy, reject symlinks/reparse traversal and unknown files, and write reports atomically.

`PIXEL_VERIFIED_DETERMINISTIC` requires passing deterministic metrics. `DELIVERY_READY`
additionally requires a hash-bound native AI file, Illustrator preview, successful structural
read-back, all six golden cases, exact-SHA CI, and rights/installed-runtime evidence; local
packaging alone cannot synthesize those fields.

- [ ] **Step 4: Run targeted, full Python, bundle verifier, and canonical gates**

Run: `python -m unittest discover -s design-lab/tests -p "test_reconstruction_evidence.py" -v`
Run: `python scripts/run_python_tests.py`
Run: `python design-lab/scripts/verify_reconstruction_bundle.py --fixture`
Run: `python design-lab/scripts/verify_design_lab.py`
Expected: PASS with no runtime artifact entering Git.

- [ ] **Step 5: Commit the deterministic evidence boundary**

```bash
git add -- design-lab/schemas/reconstruction/reconstruction-bundle.schema.json packages/capabilities/reconstruction/evidence.py design-lab/scripts/verify_reconstruction_bundle.py design-lab/scripts/verify_design_lab.py design-lab/tests/test_reconstruction_evidence.py
git commit -m "feat(reconstruction): package verified reconstruction evidence"
```
