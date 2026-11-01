# Obsidian-Assistance helper repo cloud-hygiene audit hardening

Use this when cleaning or hardening the public helper repository while keeping the formal Obsidian vault local-only.

## Boundary pattern

- Work in `D:/All projects/Obsidian-Assistance/` and verify with `git status -sb` before editing.
- Do not upload formal vault runtime state, course materials, generated archives, Open Design `.artifact.json`, nested `.obsidian/`, `.smart-env/`, media, PDFs, SQLite/DB files, or large exports.
- If tracked generated artifacts already exist, back them up outside the repo first, then remove from tracking/current tree; keep public-safe CSS snippets under a neutral folder such as `Obsidian - Front-end Assistance/obsidian-snippets/` rather than under `.obsidian/`.

## Audit-script hardening lessons

- Audit both the backend subdirectory and the repository root:
  - `python scripts/v4/obsidian_v4_audit.py .` from `Obsidian - Backend Assistance/`
  - `python "Obsidian - Backend Assistance/scripts/v4/obsidian_v4_audit.py" .` from the repo root
- Detect forbidden metadata case-insensitively: use `p.name.lower().endswith((".artifact.json",))` rather than exact-case suffix checks.
- Avoid broad suffix-based self-exemptions such as `rel.endswith("scripts/v4/obsidian_v4_audit.py")`; they can miss nested copied scripts.
- Prefer dynamic self-identification for the audit script:
  - `SELF_AUDIT_SCRIPT = Path(__file__).resolve()`
  - compare `path.resolve() == SELF_AUDIT_SCRIPT` inside a small helper that catches `OSError`.
- Keep test fixtures honest: a temporary file named `obsidian_v4_audit.py` is not the actual running audit script and should not be exempted unless its resolved path equals `Path(__file__).resolve()`.

## Regression tests to preserve

- RED test for uppercase artifact metadata, e.g. `preview.HTML.ARTIFACT.JSON`.
- RED test for unrelated same-named `scripts/v4/obsidian_v4_audit.py` being scanned.
- RED test for nested `archive/Obsidian - Backend Assistance/scripts/v4/obsidian_v4_audit.py` being scanned.
- RED test for the actual imported audit module being exempted by resolved path even when the provided relative path contains a different audit-root prefix.

## Verification gate

Run before PR/merge:

```bash
python -m py_compile scripts/*.py scripts/v4/*.py pytest.py
python -m pytest tests/v4/test_obsidian_v4_audit.py -q
python -m pytest tests -q
python scripts/v4/obsidian_v4_audit.py .
python "Obsidian - Backend Assistance/scripts/v4/obsidian_v4_audit.py" .
```

Then verify tracked-boundary state:

```bash
git ls-files '*.zip' '*.artifact.json' '*.ARTIFACT.JSON' '*.mp4' '*.pdf' '*.pptx' '*.sqlite' '*.db' '.obsidian/*' '**/.obsidian/*' '*/.obsidian/*'
```

Expected output: no forbidden tracked files and no tracked file over 1MB.
