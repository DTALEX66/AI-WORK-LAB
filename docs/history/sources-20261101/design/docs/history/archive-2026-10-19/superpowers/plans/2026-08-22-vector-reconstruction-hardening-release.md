# Vector Reconstruction Hardening and Release Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Qualify the complete reconstruction system as mature by proving security, six-case quality, reproducibility, interruption recovery, performance behavior, rights lineage, and exact-SHA delivery evidence.

**Architecture:** Hardening adds no alternate success path. It attacks the same contracts through adversarial fixtures, repeated clean runs, forced interruption, capability fallbacks, and live Adobe qualification, then publishes only evidence that passed at the correct lifecycle layer.

**Tech Stack:** Existing reconstruction package, `unittest`, canonical DESIGN-LAB verifiers, GitHub Actions, local Adobe fixtures, JSON evidence contracts.

**Spec:** `docs/superpowers/specs/2026-08-22-pixel-perfect-vector-reconstruction-design.md`

## Global Constraints

- Six rights-cleared golden cases: logo/icon, UI, poster, flat illustration, complex illustration, mixed-media commercial layout.
- Three consecutive clean runs must produce identical deterministic SVG previews and equivalent Illustrator read-back.
- Failed, skipped, cancelled, stale-SHA, or missing required checks never count as PASS.
- Runtime, CI, publication, merge, and installed-host evidence are reported separately.
- No test fixture may contain credentials, private prompts, unlicensed stock, or a disguised full-canvas reference overlay.

---

### Task 1: Adversarial SVG, path, and evidence safety suite

**Files:**
- Create: `design-lab/tests/fixtures/reconstruction/adversarial/manifest.json`
- Create: `design-lab/tests/test_reconstruction_security.py`
- Create: `design-lab/scripts/verify_reconstruction_security.py`
- Modify: `design-lab/scripts/verify_design_lab.py`

**Interfaces:**
- Produces verifier summary `RECONSTRUCTION_SECURITY=PASS fixtures=<n>`.
- Consumes the sanitizer, contracts, provider registry, rollback boundary, and evidence packager.

- [ ] **Step 1: Add failing adversarial tests**

```python
ATTACKS = ("script-element.svg", "event-handler.svg", "external-href.svg", "entity-expansion.svg", "parent-raster-path.json", "full-canvas-overlay.json", "stale-authorization.json")

def test_every_attack_is_rejected_before_render_or_host_launch(self):
    for name in ATTACKS:
        with self.subTest(name=name):
            self.assertEqual(run_attack(name).phase, "PRE_RENDER_REJECTED")
```

- [ ] **Step 2: Run tests and confirm at least one fixture fails before hardening**

Run: `python -m unittest discover -s design-lab/tests -p "test_reconstruction_security.py" -v`
Expected: FAIL naming the unhandled attack class.

- [ ] **Step 3: Close each proven gap at its owning boundary**

```python
def assert_run_relative(path: Path, run_root: Path) -> Path:
    resolved = path.resolve(strict=False)
    root = run_root.resolve(strict=True)
    if not resolved.is_relative_to(root) or any(p.is_symlink() for p in _existing_parents(resolved, root)):
        raise BoundaryViolation(str(path))
    return resolved
```

Fix only the sanitizer, schema, registry, or boundary function that owns the failing case; do not
add attack-specific bypasses.

- [ ] **Step 4: Run targeted security, full Python, and canonical gates**

Expected: all PASS and canonical verifier total increases by one.

- [ ] **Step 5: Commit the adversarial gate**

```bash
git add -- design-lab/tests/fixtures/reconstruction/adversarial design-lab/tests/test_reconstruction_security.py design-lab/scripts/verify_reconstruction_security.py design-lab/scripts/verify_design_lab.py packages/capabilities/reconstruction
git commit -m "test(reconstruction): enforce adversarial safety gates"
```

### Task 2: Rights-cleared six-case golden corpus and quality profiles

**Files:**
- Create: `design-lab/evals/reconstruction/golden-corpus.json`
- Create: `design-lab/evals/reconstruction/cases/<case-id>/reference.png`
- Create: `design-lab/evals/reconstruction/cases/<case-id>/expectations.json`
- Create: `design-lab/scripts/verify_reconstruction_golden_corpus.py`
- Test: `design-lab/tests/test_reconstruction_golden_corpus.py`

**Interfaces:**
- Produces `GoldenExpectation(profile, pixelmatch_min, ssim_min, raster_budget, required_editable_types, rights_status)`.
- Produces verifier summary `RECONSTRUCTION_GOLDEN=PASS cases=6`.

- [ ] **Step 1: Write failing corpus topology and anti-baseline tests**

```python
def test_exactly_six_required_profiles_exist(self):
    corpus = load_corpus(CORPUS)
    self.assertEqual({c.kind for c in corpus.cases}, {"logo", "ui", "poster", "flat-illustration", "complex-illustration", "mixed-media"})

def test_reference_cannot_be_registered_as_output_layer(self):
    for case in load_corpus(CORPUS).cases:
        self.assertNotIn(case.reference_sha256, case.allowed_output_asset_hashes)
```

- [ ] **Step 2: Run tests and confirm RED**

Expected: FAIL because the corpus is absent.

- [ ] **Step 3: Add six original synthetic references and explicit expectations**

```json
{
  "caseId": "ui-settings-001",
  "profile": "ui",
  "pixelmatchMin": 0.995,
  "ssimMin": 0.995,
  "rasterBudget": 0.05,
  "requiredEditableTypes": ["text", "primitive", "path"],
  "rights": {"status": "cleared", "source": "DESIGN-LAB synthetic fixture"}
}
```

Generate the fixture artwork from tracked source definitions, review it visually, then freeze its
hash. Do not use third-party design references as committed golden assets.

- [ ] **Step 4: Run corpus verifier and all six reconstruction cases**

Expected: topology PASS. Individual cases may remain `PARTIAL` until implementation quality
reaches their gates; release remains blocked until all six PASS.

- [ ] **Step 5: Commit rights-cleared golden inputs and expectations**

```bash
git add -- design-lab/evals/reconstruction design-lab/scripts/verify_reconstruction_golden_corpus.py design-lab/tests/test_reconstruction_golden_corpus.py
git commit -m "test(reconstruction): add rights-cleared golden corpus"
```

### Task 3: Reproducibility, forced interruption, and residue qualification

**Files:**
- Create: `packages/capabilities/reconstruction/qualification.py`
- Create: `design-lab/scripts/qualify_reconstruction_runtime.py`
- Test: `design-lab/tests/test_reconstruction_qualification.py`

**Interfaces:**
- Produces: `qualify_case(case_id: str, repeats: int = 3, inject_failure_at: str | None = None) -> QualificationReport`.
- Produces states `PASS`, `PARTIAL`, `NOT_EXECUTED`, and `BLOCKED` with per-layer lifecycle evidence.

- [ ] **Step 1: Write failing three-repeat, interruption, and residue tests**

```python
def test_two_successes_do_not_qualify(self):
    self.assertEqual(aggregate([run_pass(), run_pass()]).status, "PARTIAL")

def test_resume_preserves_output_identity(self):
    clean = qualify_case("logo-001", repeats=1)
    resumed = qualify_case("logo-001", repeats=1, inject_failure_at="MEASURED")
    self.assertEqual(clean.svg_sha256, resumed.svg_sha256)
    self.assertEqual(resumed.residue, ())
```

- [ ] **Step 2: Run qualification tests and confirm RED**

Expected: FAIL because the qualification aggregator is missing.

- [ ] **Step 3: Implement exact-state aggregation**

```python
def aggregate(runs):
    if len(runs) != 3:
        return QualificationReport(status="PARTIAL", reason="requires exactly three clean passes")
    if any(run.status != "PASS" or run.residue for run in runs):
        return QualificationReport(status="PARTIAL", reason="run or residue failure")
    if len({run.deterministic_preview_sha256 for run in runs}) != 1:
        return QualificationReport(status="PARTIAL", reason="non-deterministic preview")
    return QualificationReport(status="PASS")
```

- [ ] **Step 4: Execute every interruption boundary and three clean deterministic runs**

Expected: resume preserves output identity; rollback removes only run-owned paths; all exact
targets are absent after cleanup; permission or lock failures report `BLOCKED`.

- [ ] **Step 5: Commit qualification logic**

```bash
git add -- packages/capabilities/reconstruction/qualification.py design-lab/scripts/qualify_reconstruction_runtime.py design-lab/tests/test_reconstruction_qualification.py
git commit -m "test(reconstruction): qualify repeatability and recovery"
```

### Task 4: Performance budgets and capability fallbacks

**Files:**
- Create: `design-lab/config/reconstruction-performance.json`
- Create: `packages/capabilities/reconstruction/performance.py`
- Create: `design-lab/scripts/benchmark_reconstruction.py`
- Test: `design-lab/tests/test_reconstruction_performance.py`

**Interfaces:**
- Produces timed JSON events for intake, model load, inference, render, compare, repair, host wait, and host execution.
- Produces: `select_runtime_plan(hardware: HardwareProfile, profile: str) -> RuntimePlan`.

- [ ] **Step 1: Write failing 8 GB routing and timing-schema tests**

```python
def test_eight_gb_profile_never_requires_four_b_model(self):
    plan = select_runtime_plan(HardwareProfile(vram_mb=8151), "mixed")
    self.assertNotIn("omnisvg-4b", plan.required_providers)
    self.assertNotIn("qwen-image-layered", plan.required_providers)

def test_timing_event_has_observed_duration(self):
    self.assertGreater(validate_event(timed_event()).duration_ms, 0)
```

- [ ] **Step 2: Run tests and confirm RED**

Expected: FAIL because hardware routing and event schemas are missing.

- [ ] **Step 3: Implement measured routing without configuration inference**

```python
def select_runtime_plan(hardware, profile):
    required = ["geometry", "paddleocr", "layerd", "vtracer"]
    optional = ["sam2", "birefnet", "starvector-1b"] if hardware.vram_mb >= 7500 else ["sam2-cpu"]
    return RuntimePlan(tuple(required), tuple(optional), tile_size=1024 if hardware.vram_mb < 10000 else 2048)
```

Thresholds are set only after matched measurements on the six-case corpus; the config records
sample count, hardware ID, p50, p95, peak VRAM, and peak working-set memory.

- [ ] **Step 4: Benchmark matched cold/warm samples and verify no silent resolution reduction**

Expected: complete timed JSON events for at least three cold and five warm runs per profile;
quality metrics remain unchanged across runtime fallbacks.

- [ ] **Step 5: Commit performance routing and benchmark schema**

```bash
git add -- design-lab/config/reconstruction-performance.json packages/capabilities/reconstruction/performance.py design-lab/scripts/benchmark_reconstruction.py design-lab/tests/test_reconstruction_performance.py
git commit -m "perf(reconstruction): add measured capability routing"
```

### Task 5: Canonical release evidence and operator handoff

**Files:**
- Create: `design-lab/schemas/reconstruction/reconstruction-evidence.schema.json`
- Create: `design-lab/scripts/verify_reconstruction_release.py`
- Create: `design-lab/adapters/creative-tools/adobe/reconstruction-operator-guide.md`
- Create: `reports/current/RECONSTRUCTION_CAPABILITY.json`
- Modify: `design-lab/scripts/verify_design_lab.py`
- Test: `design-lab/tests/test_reconstruction_release.py`

**Interfaces:**
- Produces verifier summary `RECONSTRUCTION_RELEASE=PASS sha=<exact-sha>` only with exact-SHA CI and required live evidence.
- Produces lifecycle fields `implementedLocal`, `testedLocal`, `ciVerifiedExactSha`, `mergedMain`, and `installedRuntimeVerified`.

- [ ] **Step 1: Write failing stale-SHA and evidence-layer tests**

```python
def test_local_tests_cannot_fill_runtime_field(self):
    with self.assertRaises(EvidenceError):
        validate_release(evidence(installedRuntimeVerified=True, liveRuns=[]))

def test_ci_sha_must_equal_requested_release_sha(self):
    with self.assertRaises(EvidenceError):
        validate_release(evidence(releaseSha="a" * 40, ciSha="b" * 40))
```

- [ ] **Step 2: Run release tests and confirm RED**

Expected: FAIL because the evidence contract and verifier are absent.

- [ ] **Step 3: Implement fail-closed release verification and current projection**

```python
def verify_release(evidence, expected_sha):
    validate_schema(evidence)
    if evidence["releaseSha"] != expected_sha or evidence["ci"]["headSha"] != expected_sha:
        raise EvidenceError("exact SHA mismatch")
    if any(case["status"] != "PASS" for case in evidence["goldenCases"]):
        raise EvidenceError("golden corpus incomplete")
    if evidence["illustrator"]["status"] != "PASS":
        raise EvidenceError("Illustrator runtime not qualified")
```

The current projection is generated from validated evidence and marked non-current whenever its
bound SHA differs from the checked-out tree.

- [ ] **Step 4: Run final local gates, inspect diff/status, then perform separately authorized GitHub delivery**

Run: `python scripts/run_python_tests.py`
Run: `python design-lab/scripts/verify_design_lab.py`
Run: `git diff --check`
Expected: local PASS and clean generated-artifact state. After authorized push/PR/merge, verify
required CI against the merge SHA and re-read local `HEAD`, `origin/main`, and GitHub `main`.

- [ ] **Step 5: Commit release contracts and handoff documentation**

```bash
git add -- design-lab/schemas/reconstruction/reconstruction-evidence.schema.json design-lab/scripts/verify_reconstruction_release.py design-lab/adapters/creative-tools/adobe/reconstruction-operator-guide.md reports/current/RECONSTRUCTION_CAPABILITY.json design-lab/scripts/verify_design_lab.py design-lab/tests/test_reconstruction_release.py
git commit -m "feat(reconstruction): add release evidence gate"
```
