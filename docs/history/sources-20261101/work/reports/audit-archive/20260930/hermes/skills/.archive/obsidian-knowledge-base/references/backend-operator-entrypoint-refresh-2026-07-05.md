# Backend operator entrypoint refresh — 2026-07-05

Context: while continuing Obsidian-Assistance helper-repo backend work, the code/tooling was healthy but the backend operator docs had drifted from the actual repository shape.

## Durable lesson

For helper-repo backend enhancement loops, treat README/operator-doc drift as an implementation gap, not cosmetic cleanup. The docs are the next agent/operator's entrypoint and should be regression-tested when stale paths or commands are discovered.

## Drift found

- `Obsidian - Backend Assistance/README.md` still referenced the old workflow path `.github/workflows/v4-validation.yml` even though the real root workflow is `.github/workflows/repo-validation.yml`.
- README and reports still used root-spill demo vault examples such as `D:/OBS-V4-DEMO`; the preferred workspace-contained location is `D:/All projects/Obsidian-Assistance/demo-vaults/OBS-V4-DEMO`.
- `scripts/README_SCRIPTS.md` still described an old 01–06 OCR/ASR PowerShell pipeline as the main entrypoint, while the actual backend had V4–V9 Python tools.

## Pattern that worked

1. Load `obsidian-knowledge-base`, `test-driven-development`, `github-pr-workflow`, and `requesting-code-review` because this is helper-repo engineering with TDD + PR flow.
2. Start from clean `main`, branch e.g. `docs/backend-operator-entrypoints`.
3. Add a doc-drift regression test before changing docs, e.g. `tests/v4/test_backend_docs_entrypoints.py`:
   - README must mention `.github/workflows/repo-validation.yml`.
   - README must not mention `v4-validation.yml`.
   - README/scripts README must use `D:/All projects/Obsidian-Assistance/demo-vaults/OBS-V4-DEMO`, not `D:/OBS-V4-DEMO`.
   - scripts README must mention V4–V9 and contain `python -m pytest tests -q`, `python scripts/v4/obsidian_v4_audit.py .`, `--dry-run`, and `--apply`.
4. Verify RED first: targeted doc test should fail for the stale docs.
5. Update docs:
   - Backend README: current CI path, workspace demo-vault path, V4–V9 test directories, verification commands.
   - scripts README: operator index by V4/V5/V6/V7/V8/V9, dry-run/apply semantics, evidence boundary, and old OCR/ASR pipeline demoted to legacy ingestion notes.
6. Verify GREEN and full gates:
   - `python -m pytest tests/v4/test_backend_docs_entrypoints.py -q`
   - `python -m pytest tests -q`
   - `python -m py_compile scripts/*.py scripts/v4/*.py scripts/v5/*.py scripts/v6/*.py scripts/v7/*.py scripts/v8/*.py scripts/v9/*.py pytest.py`
   - Backend scoped audit and repo-root audit.
   - forbidden tracked files / tracked files >1MB checks.
7. PR, wait for `Repository Validation`, squash merge, pull main, and re-run final smoke gates.

## Acceptance shape

A good backend entrypoint refresh leaves future agents with:

- One obvious validation command block.
- One current CI path.
- One workspace-contained demo-vault path.
- V4–V9 scripts explained by function and safety default.
- Explicit statement that candidates are not verified evidence.
- Regression tests preventing the docs from drifting back to stale paths.
