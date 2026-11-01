# Windows boundary and publication evidence — 2026-07-28

## Project residuals found

- `C:\Users\ALEX\Cognitive-OS`: separate Git worktree with remote repository name `Cognitive-OS`, branch `codex/integrate-cognitive-runtime`, and dirty `.gitignore`. Preserve unless that exact path is separately authorized; it is not the current `Cognitive-Loop-OS` checkout.
- `C:\Users\ALEX\AppData\Local\Temp\pytest-of-ALEX`: project test spill containing `pytest-376`, `pytest-377`, and `pytest-378`. No pytest process was active; exact directories were removed with read-only attribute handling, then the empty root was removed and re-scanned.
- `C:\Users\ALEX\AppData\Local\com.archeaxis.cognitive-workspace`: inactive 10.8 MB WebView2 profile. No current WebView2 process used the profile; authoritative profiles already existed under project `.hermes/task-runtime/desktop-dev` and `desktop-installed`. The exact stale profile was removed and re-scanned absent.

## Pytest boundary reproduction

Before the fix, the regression observed `tmp_path` under `C:\Users\ALEX\AppData\Local\Temp\pytest-of-ALEX\...` and `tempfile.gettempdir()` equal to the Windows user Temp root despite `TMP`, `TEMP`, and `TMPDIR` being set. Setting `tempfile.tempdir` in the real `tests/conftest.py` fixed the issue.

Verified after the fix:

- boundary regression: `1 passed`
- full Python suite: `993 passed, 4 skipped`
- C pytest root: absent
- project `.hermes/task-runtime/pytest-tmp`: present
- project `.hermes/task-runtime/pycache`: present

## GitHub visibility reproduction

The commit `9394f36ace2c5e601914396644e7943f28d867fb` was present on `feat/absorption-roadmap-r0`, while the repository default branch was `main` at a different SHA. No PR existed. The repository description was updated globally, but default-branch README content remained old. Therefore a default-branch-indexed web connector could not be expected to see the feature-branch files until PR/merge and resync.

Do not record credential values from the old worktree, GitHub CLI, or browser state.
