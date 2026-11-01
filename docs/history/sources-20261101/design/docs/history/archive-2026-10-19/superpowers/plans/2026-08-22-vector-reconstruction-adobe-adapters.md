# Vector Reconstruction Adobe Adapters Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Assemble verified RIR into native Illustrator `.ai`, reopen and inspect it, export a verification preview/SVG, and optionally prepare complex raster layers through Photoshop UXP.

**Architecture:** A Python manifest builder emits a closed, immutable host job. Illustrator JSX and Photoshop UXP consume only that job and run-specific assets. Host execution is separated from local CI and requires a single-session authorization plus live read-back.

**Tech Stack:** Python 3.12, JSON Schema, Illustrator JavaScript/ExtendScript (JSX), Photoshop UXP/PSJS, Windows PowerShell launch wrapper, deterministic core metrics.

**Spec:** `docs/superpowers/specs/2026-08-22-pixel-perfect-vector-reconstruction-design.md`

## Global Constraints

- Never open, close, save, or overwrite an unidentified user document.
- External Illustrator script warnings remain enabled.
- Host writes target only `.hermes/task-artifacts/reconstruction/<run-id>/` until the user accepts delivery.
- A three-run fixture must save, close, reopen, read back, export, restore, and verify residue.
- Screen automation can launch an approved job but is never correctness evidence.
- Missing/uninstalled Adobe runtimes are `BLOCKED` or `NOT EXECUTED`, not test failures.

---

### Task 1: Closed host-job manifest

**Files:**
- Create: `design-lab/schemas/reconstruction/adobe-host-job.schema.json`
- Create: `packages/capabilities/reconstruction/adobe_job.py`
- Test: `design-lab/tests/test_reconstruction_adobe_job.py`

**Interfaces:**
- Produces: `build_adobe_job(rir: dict, run_dir: Path) -> AdobeHostJob`.
- Produces immutable fields `jobId`, `rirHash`, `artboard`, `layers`, `assets`, `targets`, and `authorization`.

- [ ] **Step 1: Write failing path, hash, and operation-allowlist tests**

```python
def test_job_targets_are_run_relative_and_hash_bound(self):
    job = build_adobe_job(self.rir, self.run_dir)
    self.assertEqual(job.rir_hash, canonical_rir_hash(self.rir))
    self.assertTrue(all(path.is_relative_to(self.run_dir) for path in job.target_paths()))

def test_unknown_host_operation_is_rejected(self):
    with self.assertRaises(ContractError):
        validate_adobe_job(job_with_operation("runMenuCommand"))
```

- [ ] **Step 2: Run tests and confirm RED**

Run: `python -m unittest discover -s design-lab/tests -p "test_reconstruction_adobe_job.py" -v`
Expected: FAIL because the host job does not exist.

- [ ] **Step 3: Implement the closed job schema and canonical hash**

```python
ALLOWED_OPERATIONS = {"createDocument", "createLayer", "placePath", "placeText", "placeRaster", "applyMask", "saveAI", "reopen", "readback", "exportPNG", "exportSVG"}

def build_adobe_job(rir, run_dir):
    validate_rir(rir)
    job = _project_rir_to_job(rir, run_dir.resolve())
    validate_adobe_job(job.to_dict())
    return job
```

- [ ] **Step 4: Run tests for traversal, stale RIR hash, asset hash mismatch, and expired authorization**

Expected: PASS with all four cases failing closed.

- [ ] **Step 5: Commit the host boundary**

```bash
git add -- design-lab/schemas/reconstruction/adobe-host-job.schema.json packages/capabilities/reconstruction/adobe_job.py design-lab/tests/test_reconstruction_adobe_job.py
git commit -m "feat(reconstruction): define closed Adobe host jobs"
```

### Task 2: Illustrator JSX assembly and structural read-back

**Files:**
- Create: `design-lab/adapters/creative-tools/adobe/illustrator/reconstruction-assemble.jsx`
- Create: `design-lab/adapters/creative-tools/adobe/illustrator/README.md`
- Create: `design-lab/tests/fixtures/reconstruction/adobe/synthetic-host-job.json`
- Create: `design-lab/scripts/verify_illustrator_reconstruction_adapter.py`
- Test: `design-lab/tests/test_reconstruction_illustrator_adapter.py`

**Interfaces:**
- Consumes: an exact host-job JSON path selected through Illustrator's script picker.
- Produces: `master.ai`, `illustrator-preview.png`, `master.illustrator.svg`, and `illustrator-readback.json`.

- [ ] **Step 1: Write failing static and fixture tests**

```python
def test_jsx_has_no_arbitrary_menu_or_shell_execution(self):
    source = JSX.read_text("utf-8")
    self.assertNotIn("executeMenuCommand", source)
    self.assertNotIn("system.callSystem", source)

def test_fixture_requires_reopen_and_readback(self):
    result = run_static_verifier(FIXTURE_JOB)
    self.assertEqual(result.required_operations[-3:], ["reopen", "readback", "exportPNG"])
```

- [ ] **Step 2: Run adapter tests and confirm RED**

Run: `python -m unittest discover -s design-lab/tests -p "test_reconstruction_illustrator_adapter.py" -v`
Expected: FAIL because JSX and verifier are absent.

- [ ] **Step 3: Implement bounded Illustrator assembly**

```javascript
function assertInside(child, root) {
    var c = File(child).fsName.toLowerCase();
    var r = Folder(root).fsName.toLowerCase() + "\\";
    if (c.indexOf(r) !== 0) throw new Error("target outside run root");
}

function createDocument(job) {
    var doc = app.documents.add(DocumentColorSpace.RGB, job.artboard.width, job.artboard.height);
    doc.artboards[0].artboardRect = [0, job.artboard.height, job.artboard.width, 0];
    return doc;
}
```

Use native text frames, path items, compound paths, clipping groups, placed raster `File`
objects, and explicit z-order. Never assign a COM string to `PlacedItems.File`.

- [ ] **Step 4: Pass static tests, then run one explicitly authorized synthetic host job**

Local structural command: `python design-lab/scripts/verify_illustrator_reconstruction_adapter.py --structural`
Expected: PASS.
Live result: artboard, layer names, object counts, embedded assets, save state, and exported files
match the job and are recorded in `illustrator-readback.json`.

- [ ] **Step 5: Commit structural adapter code and synthetic fixture, excluding runtime artifacts**

```bash
git add -- design-lab/adapters/creative-tools/adobe/illustrator design-lab/tests/fixtures/reconstruction/adobe/synthetic-host-job.json design-lab/scripts/verify_illustrator_reconstruction_adapter.py design-lab/tests/test_reconstruction_illustrator_adapter.py
git commit -m "feat(reconstruction): assemble native Illustrator documents"
```

### Task 3: Authorized launcher, three-run protocol, and preview comparison

**Files:**
- Create: `design-lab/scripts/run_illustrator_reconstruction.ps1`
- Create: `packages/capabilities/reconstruction/adobe_readback.py`
- Modify: `design-lab/adapters/creative-tools/adobe/E3_FIXTURE_PROTOCOL.md`
- Test: `design-lab/tests/test_reconstruction_adobe_readback.py`

**Interfaces:**
- Produces PowerShell parameters `-JobPath`, `-AuthorizationPath`, and `-RunRoot`.
- Produces: `verify_illustrator_readback(job: AdobeHostJob, result_path: Path) -> HostVerification`.

- [ ] **Step 1: Write failing authorization and three-run tests**

```python
def test_expired_authorization_blocks_before_host_launch(self):
    with self.assertRaises(AuthorizationExpired):
        verify_launch_authorization(self.expired, self.job)

def test_e3_requires_three_clean_readbacks(self):
    result = qualify_host([passing_run(), passing_run()])
    self.assertEqual(result.state, "PARTIAL")
```

- [ ] **Step 2: Run read-back tests and confirm RED**

Run: `python -m unittest discover -s design-lab/tests -p "test_reconstruction_adobe_readback.py" -v`
Expected: FAIL because launcher verification is missing.

- [ ] **Step 3: Implement launch preflight and read-back validation**

```powershell
$job = (Resolve-Path -LiteralPath $JobPath -ErrorAction Stop).Path
$root = (Resolve-Path -LiteralPath $RunRoot -ErrorAction Stop).Path
if (-not $job.StartsWith($root + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
    throw 'Job path is outside run root'
}
```

The launcher verifies runtime presence and authorization, then opens the exact JSX/job workflow.
It never disables the external-script warning and never closes pre-existing documents.

- [ ] **Step 4: Execute the synthetic job three times in clean Illustrator sessions**

Expected per run: native save, close/reopen, matching read-back, preview export, deterministic
comparison PASS, backup restore PASS, zero unowned residue. Any failure leaves qualification
`PARTIAL` and records the exact phase.

- [ ] **Step 5: Commit launcher and qualification logic**

```bash
git add -- design-lab/scripts/run_illustrator_reconstruction.ps1 packages/capabilities/reconstruction/adobe_readback.py design-lab/adapters/creative-tools/adobe/E3_FIXTURE_PROTOCOL.md design-lab/tests/test_reconstruction_adobe_readback.py
git commit -m "feat(reconstruction): verify Illustrator host readback"
```

### Task 4: Optional Photoshop UXP layer-preparation adapter

**Files:**
- Create: `design-lab/adapters/creative-tools/adobe/photoshop-reconstruction/manifest.json`
- Create: `design-lab/adapters/creative-tools/adobe/photoshop-reconstruction/index.js`
- Create: `design-lab/adapters/creative-tools/adobe/photoshop-reconstruction/README.md`
- Create: `design-lab/scripts/verify_photoshop_reconstruction_adapter.py`
- Test: `design-lab/tests/test_reconstruction_photoshop_adapter.py`

**Interfaces:**
- Consumes: exact run-relative raster preparation jobs.
- Produces: cropped RGBA PNGs, optional companion PSD, hashes, and `photoshop-readback.json`.

- [ ] **Step 1: Write failing manifest, modal-write, and path-boundary tests**

```python
def test_all_document_mutations_are_modal(self):
    source = INDEX.read_text("utf-8")
    self.assertIn("executeAsModal", source)

def test_manifest_has_no_unrestricted_network_permission(self):
    manifest = json.loads(MANIFEST.read_text("utf-8"))
    self.assertNotIn("https://*", json.dumps(manifest))
```

- [ ] **Step 2: Run Photoshop adapter tests and confirm RED**

Run: `python -m unittest discover -s design-lab/tests -p "test_reconstruction_photoshop_adapter.py" -v`
Expected: FAIL because the UXP adapter is missing.

- [ ] **Step 3: Implement UXP preparation using DOM first**

```javascript
const { app, core } = require("photoshop");

async function executeJob(job) {
  return core.executeAsModal(async (executionContext) => {
    if (executionContext.isCancelled) throw new Error("cancelled");
    return await prepareRunRelativeLayers(app, job);
  }, { commandName: "DESIGN-LAB Reconstruction Layer Preparation" });
}
```

Use `batchPlay` only for capabilities absent from the DOM. Validate output hashes and reopen the
PSD companion when requested.

- [ ] **Step 4: Run structural tests and, when installed, the three-run synthetic fixture**

Expected: structural PASS in CI; live runtime state reported separately as PASS, NOT EXECUTED,
or BLOCKED.

- [ ] **Step 5: Commit the optional Photoshop adapter**

```bash
git add -- design-lab/adapters/creative-tools/adobe/photoshop-reconstruction design-lab/scripts/verify_photoshop_reconstruction_adapter.py design-lab/tests/test_reconstruction_photoshop_adapter.py
git commit -m "feat(reconstruction): prepare hybrid layers with Photoshop UXP"
```
