# Illustrator text placement and conservative failed-task recovery

Status: local implementation and controlled evidence; no release or exact-SHA
cloud CI claim. The overall real-reference reconstruction remains PARTIAL.

## Measured cause, not guessed offsets

The full-poster candidates showed misplaced captions. A diagnostic derivative
of the fixed bridge recorded position before font/size changes, after those
changes, and after native reopen. Illustrator 29.5.1 retained the baseline
while changing the point-text geometric bounds:

| Requested size | Requested Y | Y after font/size | Y after reopen |
|---|---:|---:|---:|
| 12pt | 330 | 329.7373046875 | 329.7373046875 |
| 24pt | 230 | 240.03515625 | 240.03515625 |
| 48pt | 130 | 160.630859375 | 160.630859375 |

Root fix: set font, size and color before assigning the requested position.
The real JSX reader now checks live text position within 0.02 points, and
rejects nonfinite/missing numeric readback. Unit RED proved the previous
reader accepted shifted positions; a second RED exposed NaN/undefined acceptance.

## Diagnostic failure and recovery are retained

Run root: `.project-local/task-artifacts/text-position-probe-20260908/run-752fbabb7d704289966b0d2685b88b70/`.
The derivative generated native artifacts but failed writing its JSON probe:
the actual ExtendScript environment returned `JSON=undefined` and
`STRINGIFY=absent`. Its zero-byte output was preserved. A read-only follow-up
recovered the already collected numeric observations from the same host; no
second generation was dispatched. `readonly-diagnostic.json` preserves raw
output, including a harmless diagnostic label mangled by an overly broad
literal substitution; the follow-up script now uses a unique placeholder.
An earlier shell quoting failure also occurred before any host call; no
execution-policy override or alternate host was used to bypass it.

Original attempt `att-f1e6d74abb744c638f9f63c42def0695` entered OUTCOME_UNKNOWN
and retained the host guard, as required. The new internal quiescence entry:

- accepts only a guarded Illustrator OUTCOME_UNKNOWN attempt and scoped
  project-native-test authorization;
- claims recovery durably, refuses a concurrent or repeated recovery;
- synchronously targets only that job's saved AI document, refuses ambiguous
  or unsaved matching documents, leaves unrelated documents untouched;
- checks existing artifact hashes before/after, saves/overwrites/deletes no file;
- stores acknowledgement and changes the attempt to RECONCILING and operation
  to PAUSED_NEEDS_USER; it does NOT mark outputs accepted, publish an asset,
  assert effect_not_started, or retry the original attempt;
- releases the host guard only after verified quiescence. A failed recovery
  retains both the guard and recovery claim without automatic retry.

Actual recovery closed one saved diagnostic document (1 → 0). AI/PNG/SVG
hashes were unchanged. `quiescence-readback.json` is the immutable receipt.
AI SHA256: `d2080f9b21778109656ad2f7af4833664514ccc6275aa80a528cf01cc1f3cc29`.
This is safe host cleanup and preserved evidence, NOT native asset rollback
or completion of the failed diagnostic. Unsaved-document recovery and crashed
recovery reconciliation remain manual/unsupported; no global mutex guarantee
against external Adobe automation is claimed.

## Real poster after the placement fix

Candidate 3 run: `.project-local/task-artifacts/real-poster-20260908/run-b06126a08d8a42f6a98b985555d9cac3/`.
651 objects, 99 live text objects, same reference RIR as candidate 2.
Actual native execution, save/reopen/readback (now including text position),
local version publication and idempotent replay succeeded: one dispatch,
zero guards, documents 0 → 0.

- AI SHA256 `37d95c18dcbd5a96c4b99473192efb68511a57c0bcfdb51eabbc9110a2c611b1`.
- PNG SHA256 `94f7dec69c87f5959b27b10e649b1c44a6fe98079582536be66d5a0a7bf2765e`.
- Bridge at this run: `3f1a5d01b9731895d749831fd7c0f80ed6b2e725242589c8f211daf1a99a258f`.
- Foreground IoU increased from 0.707125 to 0.784866; MAE fell from
  15.9334 to 11.7168/255. These are image differences, not acceptance rates.
- Visually inspected: caption positions improved, but OCR inaccuracies,
  substitute fonts, mixed bold typography and the lower-right logo remain.

Source base during this work: `7759c808eac1fbbdc91e90ac3e93e6ef7c3be330` plus
uncommitted changes. Final native repeat after nonfinite-readback and negative
document-count hardening completed at
`.project-local/task-artifacts/real-poster-20260908/run-3bc50140e7f44caca5393c29002c43f9/`:

- Final bridge SHA256 `5b20d7bc078d6cb3bfba1f48668ed86bed5964796d005b010f9a81ba5e754c99`.
- NativeTasks SHA256 `d5685fc2ac79f7796cc752df627b3cf37061f8933173fe6aabe9e47c72fec207`.
- Adapter SHA256 `b117e304243a53ac864fbdfa74ebd5f5bbaa6deaa9a24fc5d6a9c43d5b134be1`.
- AI SHA256 `4bd448b71b026118ab19bab3e249b97d2d37c7d9fc73328a7a6302bf600e89a2`.
- PNG and SVG hashes equal candidate 3 exactly. AI bytes differ; no claim of
  deterministic AI serialization is made.
- One dispatch, zero host guards, documents 0 → 0, native text positions
  verified after reopen. Attempt ran 20:48:33.311848Z → 20:49:54.948089Z.

Canonical `design-lab/scripts/verify_design_lab.py` completed exit 0,
`VERIFY_DESIGN_LAB=OK total=49 failed=0` (session 29954). These are repository
gates, not proof of live Comfy/H3 inference despite legacy verifier wording.
The old derivative probe deliberately source-checks its insertion point and
must not be rerun against this changed bridge; its failure/raw evidence remains
historical and its known JSON serializer assumption is not production code.

## Tests and remaining gates

Focused commands use `.venv/Scripts/python.exe -B -m unittest discover -s design-lab/tests -p <file>`:
`test_illustrator_text_readback.py` 1 PASS; `test_native_quiescence.py` 3 PASS;
`test_native_tasks.py` 12 PASS; `test_reconstruction_adobe_job.py` 8 PASS;
`test_illustrator_local_patch.py` 1 PASS before the final numeric hardening.

Remaining: real-poster object-local edits and rollback, correct typography and
transcription, PSD counterpart, additional reference types, installed-package
requalification, Human Jury/rights, exact-SHA CI and publication. Host recovery
does not waive any of these. Knowledge migration stays deferred.
