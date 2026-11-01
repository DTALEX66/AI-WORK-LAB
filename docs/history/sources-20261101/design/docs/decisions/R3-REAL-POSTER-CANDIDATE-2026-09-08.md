# First full-canvas real-reference AI candidate

Status: PARTIAL. This is a full poster candidate, not a qualified 1:1
reconstruction, final rights decision, or 5–10-reference acceptance.

## Source and method

Reference: Piotr Chuchla's Creative Commons poster, Behance project 5783221.
Use the source/rights caveats in
[first-reference provenance](R3-REAL-REFERENCE-FIRST-2026-09-08.md).
Only the already rasterized publisher image was analyzed; no PDF text or
vector extraction, no existing editable source copied into the deliverable.

Raster: 2155 × 3000, SHA256
`5e53676d6c62826d374e81b23958444250c3c7bd57015ff913e98c93b4307e43`.
The crop marks remain part of the comparison source but are not reconstructed.

The fixture detects six rows of raster grid lines and their vertical borders,
builds individual native rectangular rules, and crops/traces 44 separate
graphic regions using the previously hash-qualified VTracer executable.
Trace output is converted into absolute cubic contours with explicit offsets;
the native compound consumer preserves holes. There is no whole-reference
raster backing. 99 OCR observations outside those graphic regions become
live text objects, with explicit Arial/Arial Bold substitutions. Three brand
graphics retain outlined logo lettering; they are NOT counted as live text.
All body/label OCR remains a candidate transcription, not verified ground truth.

The complete object group contains 651 independently represented children;
grouping retains editability and respects the existing 100-layer limit.
The first preparation attempted 651 separate top-level layers and was correctly
rejected before host execution. Its inputs remain at
`.project-local/task-artifacts/real-poster-20260908/run-8139ef6705404872815fe8ccdc77e4e6/`.
No limit was disabled to obtain success.

## Candidate 1: native workflow observed

Run: `.project-local/task-artifacts/real-poster-20260908/run-17eace2eebe44ac288541d0bd82d6df3/`.
Base HEAD: `6025b26561292e0c8f140b42f0b8d9005c3e6a79`; preparation fixture
was uncommitted. Native bridge SHA256:
`ba568181074ae8559676f1b094d51c77ac7dadf1c39ddf701115f0c57ca873e0`.

- Actual Illustrator 29.5.1, source-tree NativeTasks coordinator.
- AI save, close/reopen, editable geometry/text readback, PNG/SVG export,
  final native reopen, local asset publication and idempotent replay completed.
- One RUNNING event, zero remaining host guards, documents 0 → 0.
- Native attempt start/end: 2026-09-07T20:32:19.994285Z → 20:33:37.199923Z.
- AI SHA256: `2b2c08e63b7f511b1bf2b4d64c133246afb0243a96453a7cb1702061db31e42b`.
- PNG SHA256: `18b9fa08702a0813660fb4a9aefa4aa0a33873cc96bddc2bab1aa4c72cc07281`.
- Full-canvas MAE 16.5232/255; ink-threshold foreground IoU 0.696132.
  Exact RGB fraction 0.775927 includes white background and is not an
  acceptance percentage. `pixel-metrics.json` also measures each graphic.

Visual inspection exposed typography too low, caption overflow, incorrect
OCR characters, missing original bold spans, and an imperfect lower-right
logo crop. These failures remain visible. Neither the successful native
receipt nor visual resemblance satisfies Human Jury/production acceptance.

## Candidate 2: width-fitted live typography

Run: `.project-local/task-artifacts/real-poster-20260908/run-2da53ed9a0aa4deb92c3dbe7493b1fff/`.
Same 651 children / 99 live text / 44 graphics regions. Native qualification
completed independently: one dispatch, zero remaining guards, documents 0 → 0.
Attempt: 2026-09-07T20:34:35.490117Z → 20:35:54.282049Z.

- Preparation script SHA256: `c2c6fcb78824e55ca3c48fcbb03044b1ea2cbd4ec352a3b45ff05a61f7e6ec8c`.
- AI SHA256: `2349134ee544141d82bd5dfe2aa8adf87bbeb515a9e17a44d0aeea5901401098`.
- PNG SHA256: `5cb7a16292e030d6cdb1d1ce1f54663df78457a2cd1baced026461ea8df650bd`.
- Full-canvas MAE 15.9334/255; foreground IoU 0.707125; exact RGB 0.777482.
- Metrics script SHA256: `5c93b6d5714a53c0fc89e799fdd91ffe8fb1face219773a78b181eed70158432`.

Visual readback confirms better line-width containment but captions now sit
too close to upper borders. The consumer sets text position before changing
font/size, and it does not read back text position: inspect this ordering and
add a behavior test before a production fix. Do not solve it only by repeatedly
guessing fixture Y offsets. Font family/weight and mixed bold runs still differ.
The metric improvement is modest and does not establish pixel-level fidelity.

## Reproduction and next work

- Preparation/explicit host execution:
  `.venv/Scripts/python.exe -X utf8 -B design-lab/tests/host_fixtures/prepare_real_poster.py --execute`.
- After a successful host receipt, measure its explicit run path:
  `.venv/Scripts/python.exe -X utf8 -B design-lab/tests/host_fixtures/measure_real_poster.py <run>`.
- All outputs and local published project assets stay in ignored `.project-local`.
- The script is a fixed-reference qualification fixture, not a universal
  segmentation algorithm, production UI action, or installed-package proof.
- Candidate regeneration is not an object-local patch. Two in-place local
  edits and rollback on this real poster remain NOT EXECUTED.
- PSD counterpart, other reference categories, rights/Jury, installation,
  exact-SHA cloud CI and publication remain separate outstanding gates.

Current preparation adjusts text to the OCR top bound and fits substituted
font sizes to reference line widths. Preserve each run; do not overwrite
candidate 1 or claim the newer candidate passed until its own native and
pixel evidence is read back.
