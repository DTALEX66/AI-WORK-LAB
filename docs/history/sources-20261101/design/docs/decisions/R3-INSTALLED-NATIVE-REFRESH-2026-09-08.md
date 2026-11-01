# Installed native package refresh

Status: local wheel/install/resource and RIR conversion checks PASS.
New native host execution, release, exact-SHA CI and cloud consistency are
NOT VERIFIED by this record.

Source SHA: `f2f8c799f50c820c3218d69e08669c782177f89b`.
Wheel: `.project-local/task-artifacts/wheel-f2f8c79/design_lab-0.1.0a0-py3-none-any.whl`.
SHA256: `c562d0ec87ecd6676053a0288f5a0a7069d96ce22bfa0ee4e589abd570dd0518`.

## Execution

Built using existing uv with `build --offline --wheel --python
.venv/Scripts/python.exe --out-dir .project-local/task-artifacts/wheel-f2f8c79`.
`UV_CACHE_DIR` was the existing project-local wheel-build cache,
`UV_PYTHON_DOWNLOADS=never`, and TEMP/TMP were process-scoped to the existing
`.project-local/task-runtime/tmp`. No new download or global installation.

uv warned that its cache was inside the source directory. The actual wheel
was inspected: 56 entries, no `.project-local`, `.hermes`, bytecode cache or
`.env` entries. Forty-two selected source modules, explicit single-file
resources and converter files were compared byte-for-byte with wheel members.

Reinstalled only into `.project-local/task-runtime/workbench-installed` using
`uv pip install --offline --no-deps --reinstall --python <environment python>
<wheel>`. All 50 installed `design_lab/` member files then matched the wheel
byte-for-byte, including packaged resources. Existing dependency versions
were retained; this is not a fresh-machine full-dependency install test.

## Installed behavior

From a non-source cwd, the installed interpreter with `-I -B` ran
`test_reconstruction_explicit_owner.py` with `DL_TEST_INSTALLED_RIR=1`:
1 PASS. Its subprocess uses the installed converters, both host job formats,
real synthetic PNG and an independent project root, rejecting path escapes.

Additional installed isolated-process checks:

- `design_lab.__file__` resolved to this environment's site-packages;
- compound relative/absolute path helper returned two contours for a fixed
  two-contour example;
- `NativeTasks.quiesce_illustrator` is present (presence only, not new recovery);
- packaged Photoshop bridge SHA256:
  `9833b5cd855b5d0aa3245f5cd52330481ff4ba090b8e009b5749d49708eddc18`;
- packaged Illustrator bridge SHA256:
  `4a6369fa5a5bb2d631d1a996ecdceac73eb2ba30653a8bb34d837a7a50cf2fc2`.

No host call was dispatched through this newly installed wheel. The pending
Photoshop original run uses source bytes captured before the scaling fix;
upgrading this isolated environment does not change that running script.

## Rollback and continuation

Previous wheel remains at
`.project-local/task-artifacts/rir-installed-wheel/design_lab-0.1.0a0-py3-none-any.whl`,
SHA256 `c630dbe77f5559c98e017c79d3de8d60bc46f32bb25245a424ba0c14398c711c`.
Rollback can explicitly reinstall it into this same isolated environment
without deleting project assets or database. Rollback itself was not run.

Photoshop original attempt `att-52901594c1684782a99b689538aaebf3` retains its
OUTCOME_UNKNOWN guard; read-only query session `20260` was still pending at
this checkpoint. No new generation or guard clearing occurred. Next native
qualification must wait for actual quiescence and retain the old failure.
