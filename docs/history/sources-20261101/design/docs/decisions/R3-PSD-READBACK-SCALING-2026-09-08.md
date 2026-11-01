# Photoshop readback scaling and late-output checkpoint

Status: IMPLEMENTED_LOCAL / targeted tests PASS; new bridge host timing NOT
EXECUTED. This change is not proof that the full PSD workflow succeeded.

## Confirmed redundant traversal

`psReadback` called recursive `psFind` separately for every expected object.
A real-JSX Node test with 100 leaf layers observed 10,000 layer-name property
reads. This quadratic traversal is unnecessary at a native DOM boundary.
The failing regression asserted at most 400 reads and failed with 10,000.

The reader now indexes direct children once per parent and resolves expected
IDs from that index. A document-wide seen set rejects duplicate actual IDs.
Layer count, correct parent membership, group/mask type, text kind, contents,
font and size checks remain. `psFind` is retained for isolated patch lookup.
The scaling regression now passes, as do negative controls for changed text,
duplicate IDs, moved children and unexpected masks.

This is an isolated measured traversal fix, not a claim that traversal is
the only cause of the 120-second transport deadline failure. Building the
full document also took longer than that deadline. No deadline was raised,
history disabled, document flattened, or layer count reduced.

## Still-running original full fixture

Original run:
`.project-local/task-artifacts/real-poster-ps-20260908/run-2d83da284b144263ab26ab00028cbd64/`.
It was dispatched before this change; its script already captured the old
bridge bytes. The change cannot retroactively accelerate or validate it.

At this checkpoint the late candidate `master.psd` appeared:

- 6,061,730 bytes;
- SHA256 `97b0d40aca27686fd75113621ff50e5208769d18ba5f6b7d044e92bc53ffeff5`;
- Pillow header detection: PSD, RGB, 2155 x 3000.

Pillow layer enumeration failed with a short-buffer `struct.error`; this
does not distinguish an unsupported decoder feature from an incomplete or
invalid layered file. Header detection is not layer/editability acceptance.
No preview PNG or successful native receipt had appeared at the checkpoint.
The original Photoshop guard remains `OUTCOME_UNKNOWN` and no redispatch
was performed. Read-only COM query session `20260` remains pending.

Photoshop PID 14148 continued consuming CPU (395.27 → 626.03 seconds
across observations). Its private memory was 15,710,920,704 bytes; system
free physical memory observed was 21,719,792 KiB. These do not establish a
deadlock or out-of-memory failure. Do not kill the application or clear its
guard based on the response timeout.

## Checks

- `test_photoshop_readback_scaling.py`: 2 PASS after the measured RED case.
- `test_photoshop_legacy_native.py`: 3 PASS.
- `test_photoshop_com_adapter.py`: 6 PASS.
- Canonical `design-lab/scripts/verify_design_lab.py`: exit 0, session 73486,
  with process-local `PYTHONUTF8=1` and `PYTHONDONTWRITEBYTECODE=1`.
  This validates the local aggregate gates, not native timing or acceptance.

Next: poll the same query, observe the exact output root, and independently
read back late outputs once the host has finished. Preserve the failed
attempt; neither late file existence nor a new-reader unit test authorizes
publishing its asset or silently converting its state to success.

## Later preview observation (original attempt still unknown)

`photoshop-preview.png` subsequently appeared (19,413,204 bytes), SHA256
`53fe760caf72d6b0012cc7dfd27598311d225adaa3f440967d678c0c7202e7fd`.
Visual inspection shows the complete six-row poster, separate icon layout,
captions and paragraphs. This is a candidate preview, not proof of editable
layer structure or the final second reopen/readback.

Direct RGB comparison against the original 2155 x 3000 raster, without any
resampling or registration, measured MAE 11.0424629544/255 and foreground IoU
0.7670673130 (mean-channel threshold 128). These are diagnostics, not an
acceptance percentage or a pixel-exact match. The scripted accepted-receipt
measurement entry was deliberately not used: its required native receipt
does not exist. This observation does not fabricate or replace that receipt.

The original read-only COM query remains session `20260`; Photoshop PID
14148 continued accumulating CPU, so no second job was dispatched.

Publication was rechecked after `git fetch origin`: local
`e0e548c842db4c4aa997c7396bc6527cbc3ad6f4`, remote development branch
`ed8d45ab2857b312f6056c43f7bb5e19dd9b65eb`, main
`c4dccd58331bc4561eb89265283d924b7630d113`. The normal authorized push was
again rejected before execution with `approval required by policy, but
AskForApproval is set to Never`. No alternate transport or approval bypass
was attempted. This checkpoint is not cloud-synchronized.

## Prepared independent inspection

`design-lab/tests/host_fixtures/inspect_late_psd.py` is a fixed-run, no-argument
inspection entry. It reads the original request from the service database in
read-only mode, matches the job file and input hashes, rejects an already-open
target, then opens only the generated PSD, runs the current linear reader and
closes its own document. It checks output hashes remain unchanged and retains
all unrelated document IDs. Its success status explicitly says the artifact
is unpublished and the original guard is retained.

Preparation validation: Python AST parse PASS. Host execution NOT EXECUTED;
wait for original query `20260` to return before using it. Do not infer the
old native task's success from this future independent inspection.

## Independent host readback completed — 2026-09-09 local time

After interruption, the original observation handle was missing. A fresh
process check returned no Photoshop process and COM GetActiveObject returned
MK_E_UNAVAILABLE. This establishes that the old application instance was no
longer available; it does not establish whether it exited normally or crashed.
No application was killed by this recovery operation.

Executed `.venv/Scripts/python.exe -B -X utf8
design-lab/tests/host_fixtures/inspect_late_psd.py`. It launched the existing
installed Photoshop through the fixed COM entry, opened only the existing
generated PSD, checked native structure and editable text using the current
linear reader, and closed its own document. Exit code 0, host 26.7.0,
elapsed 9.9581 seconds, documents 0 → 0.

Receipt: original run directory `late-readonly-readback.json`, observation UTC
`2026-09-08T16:20:18.479050+00:00`. Status remains
`LATE_READBACK_ARTIFACT_UNPUBLISHED_GUARD_RETAINED`.
Reader hash `9833b5cd855b5d0aa3245f5cd52330481ff4ba090b8e009b5749d49708eddc18`.
Both PSD and preview hashes are unchanged from the late-output checkpoint.
Original input hashes also matched the stored request before inspection.

This proves an independent native reopen/readback of this candidate, despite
the earlier Pillow layer-decoder failure. It does not reconstruct the lost
original completion receipt, establish an old/new timing benchmark, clear the
guard, publish an asset, validate pixel geometry or authorize Human Jury.
Two PSD local edits and restoration remain required. R5-004 must provide
explicit durable reconciliation without inventing a successful original run.
