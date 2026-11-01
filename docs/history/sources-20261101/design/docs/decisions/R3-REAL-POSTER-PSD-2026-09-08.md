# Real poster PSD counterpart: pending native outcome

Status: PARTIAL / HOST OUTCOME_UNKNOWN. This is not a completed reference,
PSD editability acceptance, release, or cloud-consistency claim.

## Fixture and scope

Base source HEAD: `2d90f66e555ea53c6d8cbd468639aae65c724e31`.
`design-lab/tests/host_fixtures/prepare_real_poster_ps.py` prepares the same
fixed Behance Creative Commons poster as the Illustrator candidate. It keeps
99 OCR text objects with substituted Arial fonts, 89 independent rectangular
pixel fills (not vector shapes), and 44 independent transparent graphic crops.
No whole-reference backing image is inserted. This is a fixed-reference
fixture, not a general segmentation implementation.

Input root:
`.project-local/task-artifacts/real-poster-20260908/run-3bc50140e7f44caca5393c29002c43f9/`.
Source crop hashes must match its `segmentation.json` before preprocessing.

Output root:
`.project-local/task-artifacts/real-poster-ps-20260908/run-2d83da284b144263ab26ab00028cbd64/`.

The inferred white matte preserves RGB channel differences: alpha is
255 minus the minimum RGB channel, and foreground RGB is solved against a
white background. Each exported crop is independently recomposited on white,
with maximum channel error limited to 1/255. `alpha-evidence.json` records
44 input/output hash pairs and alpha extrema. This is not recovery of the
original alpha: intentional white inside a logo also becomes transparent.
Other backgrounds therefore require separate visual acceptance.

Photoshop point-text baseline positions are estimated from substituted-font
PIL ink bounds, recorded in `baseline-estimates.json`; these are not native
geometry readback or recovered original font metrics. OCR errors remain.

## Actual execution and unfinished recovery

Command:
`.venv/Scripts/python.exe -B -X utf8 design-lab/tests/host_fixtures/prepare_real_poster_ps.py --execute`.

NativeTasks dispatched the closed Photoshop job once. Its COM transport
exceeded the adapter's 120-second deadline. Durable attempt
`att-52901594c1684782a99b689538aaebf3` is `OUTCOME_UNKNOWN`; the Photoshop
host guard remains owned. No replay, manual guard deletion, process kill,
or second fixture dispatch was performed.

After that timeout Photoshop PID 14148 remained present and its CPU time
increased (154.12 to 284.97 seconds observed). A read-only COM query for
version and document count was still pending in tool session `20260` at
this checkpoint. A timeout does not prove the Adobe script has stopped.
Neither `master.psd` nor a completed native-task receipt was observed yet.

Next action: poll that existing read-only query and inspect this exact output
root. Do not rerun `--execute` while the guarded outcome is unknown. If files
appear later, they are candidate outputs, not a received successful attempt;
independent readback and an explicit reconciliation path are still required.
Current product quiescence is Illustrator-only, not Photoshop recovery.

## Checks and retained errors

- Alpha test initially failed to import the missing fixture helper, then
  passed against the implemented helper: 1 test.
- Photoshop RIR producer: 4 tests passed.
- Photoshop COM adapter: 6 tests passed.
- Canonical verifier: 49 gates passed, exit 0, with process-local
  `PYTHONUTF8=1` and `PYTHONDONTWRITEBYTECODE=1`.
- First canonical invocation using only Python `-X utf8` failed because
  child-process encoding was not inherited: UTF-8 decode error followed by
  `NoneType.strip`. It was not a successful gate or a Photoshop regression.
- First read-only COM probe used `Marshal.GetActiveObject` in a shell where
  that API was absent. A requested shell override did not change that result.
  Explicitly invoking Windows PowerShell launched the pending query above.
- `measure_real_poster_ps.py` is prepared but NOT EXECUTED: it requires the
  successful native receipt, rejects modified source/preview bytes, checks
  exact dimensions and opaque full preview, then measures unregistered pixels.

The previous Illustrator text-locality failure remains open. This PSD run
does not offset it. Two PSD local edits, checkpoint restoration, complex-set
coverage, Human Jury, rights approval, installed-package integration and
workbench operation all remain unverified for this reference.
