# Real poster: checkpoint edits and restoration

Status: PARTIAL. Native object editing and checkpoint restoration were actually
executed. Strict text pixel-locality validation failed; no complete reference,
Human Jury, installed-package, UI, release or cloud consistency claim follows.

## Product implementation

The fixed Illustrator adapter now accepts the closed
`design-lab/adobe-patch-job/v1` job variant. It retains the baseline host object
graph and adds `checkpoint`, `checkpointSha256`, and one `patch` (text or path).
Its exact operations are openAI, readback, patchObject, saveAI, reopen,
readback, exportPNG, exportSVG. The source `rirHash` identifies the original
checkpoint design; patch payload and checkpoint bytes are additionally bound
by the coordinator request hash and native receipt, not mislabelled a new RIR.

The coordinator hashes the AI checkpoint before claiming the host and the
adapter rechecks it before/after dispatch. The native bridge validates the
closed object plan and target, refuses an already-open checkpoint, opens a
task-local copy, reads the whole design, edits only an existing object using
`applyApprovedPatch`, saves a new AI, reopens, reads the entire updated object
plan and exports previews. No arbitrary script/menu request is accepted.

Each edit is a separate durable native task and local asset publication in
the same project. Current publications have separate asset IDs; a unified
same-asset revision chain and workbench controls remain future integration.
This is not a claim that a public patch HTTP API or installer has shipped.

## Actual runs

Host: Windows Illustrator 29.5.1. Base HEAD during execution:
`ae409c5` plus this uncommitted slice. All run roots below are under
`.project-local/task-artifacts/real-poster-patches-20260908/`.
Each successful run preserved its original source bytes, completed native
save/reopen/full readback, returned documents 0 → 0, and replayed the same key
without a second edit or a new published result.

| Phase | Run directory | Actual change |
|---|---|---|
| Text | `text-c3c47522712c47bd9709fc76a8e95b71` | `ocr-100`: corrected `restrykycyjna` to `restrykcyjna` in an existing live text object |
| Path | `path-7ffb326d4e6042fdb1644eaf16205fc9` | In the text-edited AI, moved all anchors and handles of `r0-icon2-p1` 4 pixels right; preserved topology |
| Restore | `restore-ee917f7eb6034a508ec65d9bb6eac87f` | Loaded immutable original AI checkpoint and saved a new native version, not reverse-editing the changed file |

AI SHA256 by phase:

- Text: `af5b437612bea2565eea7c8ca2f77f00a289a88d877df4a1c946360f3ed5fc23`.
- Path: `4beab3f010f3c9d6b877142427a29028f3460ae8602570cc0af0a606d27b97f2`.
- Restore: `f8cbb30ca9cf05fb8d48f04e9da095395bab7de67b41d495db2720227a1d9612`.
- Preserved original: `4bd448b71b026118ab19bab3e249b97d2d37c7d9fc73328a7a6302bf600e89a2`.

Restored PNG SHA256 `94f7dec69c87f5959b27b10e649b1c44a6fe98079582536be66d5a0a7bf2765e`
and SVG `c1593c60103b4347b87331d9302e79b0669175c843536106596634af9651242e`
equal the original exactly. Native AI serialization is not byte-identical;
no deterministic AI-byte claim is made.

Source bindings:

- JSX: `4a6369fa5a5bb2d631d1a996ecdceac73eb2ba30653a8bb34d837a7a50cf2fc2`.
- Adapter: `174441fd3626267e8bba9a51c5cdb2ca2a9a82c1dfe1adee128439b8f4b594bb`.
- NativeTasks: `4f64d6ad1fb0b402c00ff7f9c9df9a0d85ea4649f66dfb02ce7fdca096cc1cd0`.

## Retained failures and strict independent verification

The first native patch preflight failed before opening the checkpoint:
`text-63d665ba24844f55bb6cb1220e0eacba`. Node reached the open boundary on
the same input, but the actual ExtendScript evaluator produced undefined
for a nested conditional selecting group children, even though the group
condition was true and its items were an object. The actual read-only probe
reported line 259; replacing only that selection with explicit if/else
branches produced PREFLIGHT_OK in the host. This is observed engine-specific
behavior, not a general claim about every ExtendScript conditional.

The failed attempt stayed RECONCILING/PAUSED_NEEDS_USER. Verified quiescence
observed zero documents, closed none, kept the checkpoint and all failure
evidence, and released the guard. No failed attempt was rewritten to success.

`verify_real_poster_edits.py` independently compared original → text → path
and restored pixels. It preserves an exit-1 JSON receipt in the restore run:

- Text changed 1,411 pixels, bbox `[1606,2663,1763,2684]`.
  Expected OCR-derived box `[170,2660,1766,2682]`; the difference extends
  2 pixels below it. Strict text locality FAIL. Font ink extent versus OCR
  geometry needs investigation; do not enlarge the box solely to pass.
- Path changed 336 pixels, bbox `[472,462,507,497]`, wholly inside the
  independently segmented icon `[442,342,651,552]`; outside unchanged PASS.
- Original/restored RGBA arrays equal exactly: PASS.
- Overall `FAILED_LOCALITY_OR_RESTORE` retained, not promoted to full acceptance.

## Checks and continuation

Project Python 3.13.14: adapter tests 7 PASS; native task tests 12 PASS;
real JSX patch-preflight test 1 PASS (valid open boundary + seven rejects);
existing local-patch test 1 PASS. Canonical gate session 28317 completed exit 0,
`VERIFY_DESIGN_LAB=OK total=49 failed=0`. The separate real-reference locality
check still failed as documented; canonical green does not override it.

Reproduce with `design-lab/tests/host_fixtures/qualify_real_poster_patch.py`
using `text`, then `path <text-run>`, then `restore`, and pass all three run
paths to `verify_real_poster_edits.py`. Each invocation creates new local
versions; do not rerun just to duplicate evidence. Quiescence of failures is
an explicit separate operation, never automatic retry or guard deletion.

Remaining: fix font/OCR geometry and quality gaps, other reference categories,
PSD edits, UI/API integration, general patch/asset lineage, installed-wheel
qualification, rights/Jury, exact-SHA CI and authorized branch publication.
Checkpoint-open failures may require additional owned-document reconciliation;
do not assume the quiescence entry closes an input checkpoint in all cases.
