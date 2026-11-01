# Relative and compound paths: current native qualification

Status: IMPLEMENTED_LOCAL / TESTED_LOCAL for this bounded source-tree slice.
Not a complete reference reconstruction, installed-wheel qualification, Human
Jury acceptance, release, or cloud publication.

## Source binding and scope

Observed base HEAD: `2e53d2ca15de67db6f88509fcabceecf4489b60f`, with the
compound changes uncommitted during both host runs. Evidence must not treat
that clean commit as containing this implementation.

- Illustrator bridge SHA256: `ba568181074ae8559676f1b094d51c77ac7dadf1c39ddf701115f0c57ca873e0`.
- Lowerer SHA256: `05b4b62366c3d9d0b7779b796bd35e757d67b1962d05eca25582e1d99c92e1aa`.
- Adobe job producer SHA256: `c58809651fb69bef944e4af24aa5782e206dc3a525564faa493d9db94e740848`.

Supports absolute and relative M/L/C/Z, multiple closed contours, native
nonzero compound paths, preserved contour winding and cubic handles. Open or
degenerate compound contours, evenodd, arc commands and compound clipping masks
remain unsupported. Photoshop explicitly rejects compound paths; it does not
silently flatten them. A new regression first reproduced KeyError('position'),
then passed after the explicit rejection was added.

## Actual Windows Illustrator 29.5.1 runs

All paths below are relative to `.project-local/task-artifacts/compound-native-20260908/`.
Both runs used the source-tree service and durable NativeTasks coordinator,
not the previously installed wheel. Each created a new isolated project,
saved/reopened/read back native geometry, published a local asset version,
then replayed the same idempotency key: one dispatch event, zero remaining
host guards, documents before/after both zero. No existing user file overwritten.

1. `run-acad679be43643e0ab51caad90e38656/native-task-readback.json`
   - Synthetic two-contour ring on contrasting background.
   - AI SHA256 `32c20389c0e757829891d6fe701e94e234e0d63735b08170b1fe051a107d400a`.
   - Export pixels: outside and hole `[224,80,48]`, ring `[18,52,86]`.
   - `hole-pixel-readback.json` preserves these independent sample checks.
2. `run-b555fabbdac0452cab85937525dc1204/native-task-readback.json`
   - Fixed real Behance poster icon crop, previously traced by VTracer.
   - Input trace SHA256 `c23ed50452d78f74cabe971d55945b689c6e8e80e92399fe51543fae8b9aa4e8`.
   - AI SHA256 `70e0d594a645276f21ee4f41a86fafeae9c29e791274d5413e652e25ba9a1d3c`.
   - Native PNG visually inspected: stacked sheets and triangle survived;
     right/top crop clipping remains. This is a diagnostic, NOT accepted artwork.

Reference provenance and clipping limitations remain in
[the first-reference report](R3-REAL-REFERENCE-FIRST-2026-09-08.md).
Original source typography was not converted to outlines. The trace is only
an icon crop, not an entire poster pasted as an editable object.

## Commands and remaining work

- Project interpreter: `.venv/Scripts/python.exe`, Python 3.13.14.
- `-B -m unittest discover -s design-lab/tests -p test_reconstruction_compound_paths.py`: 4 PASS.
- `-B -m unittest discover -s design-lab/tests -p test_reconstruction_photoshop_job.py`: 4 PASS after observed RED.
- `-B -m unittest discover -s design-lab/tests -p test_reconstruction_adobe_job.py`: 8 PASS.
- `-B -m unittest discover -s design-lab/tests -p test_illustrator_job_validation.py`: 1 PASS.
- `-B design-lab/tests/host_fixtures/qualify_compound_native.py`: actual native ring PASS.
- Same fixture with `--real-trace`: actual native diagnostic trace PASS.

Remaining: clean segmentation, OCR correction/font matching, full-reference
assembly, object patch/recovery integration, 5–10 reference acceptance,
installed-package requalification, current exact-SHA CI and publication.
Two local changes/recovery were not tested for these compound objects.
The canonical `-B design-lab/scripts/verify_design_lab.py` completed with
`VERIFY_DESIGN_LAB=OK total=49 failed=0` (session 91171, exit 0). These are
repository gates, not 49 actual host workflows. In particular the legacy
Comfy verifier's printed E3 wording does not qualify current model inference.

Rollback: retain qualification projects and immutable asset versions; revert
only this bounded source change through a reviewed commit if needed. Do not
delete user data or claim an untested native rollback for compound objects.
