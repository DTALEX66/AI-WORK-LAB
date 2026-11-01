# Obsidian-Assistance helper repo cloud-hygiene workflow

Use this when the helper repository risks leaking generated artifacts, Obsidian runtime state, or formal-vault material into GitHub.

## Boundary model

- Helper repo: `D:/All projects/Obsidian-Assistance/` — GitHub-safe automation, examples, scripts, docs.
- Formal vault: `E:/BaiduSyncdisk/Obsidian知识库` — local-only knowledge base; inspect read-only unless user explicitly asks to modify it.
- Generated exports, Open Design metadata, ZIPs, PDFs/media, nested `.obsidian/`, `.smart-env/`, and large files do not belong in the helper repo.
- Public-safe CSS snippets may be preserved, but move them out of `.obsidian/snippets/` into a neutral example directory such as `Obsidian - Front-end Assistance/obsidian-snippets/` with a README explaining that they are examples, not runtime vault state.

## Clean-up pattern

1. Start from current `main`, branch (for example `fix/cloud-hygiene-boundary`), and check status.
2. Identify tracked boundary violations with `git ls-files` patterns for archives, artifact metadata, media, DBs, and runtime paths.
3. Back up anything removed to a directory outside the repo before removing from Git tracking.
4. Use `git rm` / `git mv` for tracked files. Do not rely on `.gitignore` to remove already-tracked files.
5. Preserve reusable snippet examples outside `.obsidian/` and document their purpose.
6. Strengthen `Obsidian - Backend Assistance/scripts/v4/obsidian_v4_audit.py` so both backend-scoped and repository-root audits pass.
7. Add regression tests before production code for new audit behavior.
8. Add or update CI so the repo blocks forbidden tracked files and large files on future PRs.
9. Open a PR, wait for GitHub Actions, merge only after green checks, then pull `main` and re-run local verification.

## Verification commands used successfully

From backend directory:

```bash
python -m py_compile scripts/*.py scripts/v4/*.py pytest.py
python -m pytest tests -q
python scripts/v4/obsidian_v4_audit.py .
```

From repo root:

```bash
python "Obsidian - Backend Assistance/scripts/v4/obsidian_v4_audit.py" .
```

Tracked boundary check:

```bash
forbidden=$(git ls-files '*.zip' '*.artifact.json' '*.ARTIFACT.JSON' '*.mp4' '*.pdf' '*.pptx' '*.sqlite' '*.db' '.obsidian/*' '**/.obsidian/*' '*/.obsidian/*' || true)
if [ -n "$forbidden" ]; then echo "$forbidden"; exit 1; else echo 'forbidden tracked files: <none>'; fi
python - <<'PY'
from pathlib import Path
import subprocess
large=[]
for line in subprocess.check_output(['git','ls-files'], text=True).splitlines():
    p=Path(line)
    if p.exists() and p.is_file() and p.stat().st_size > 1_000_000:
        large.append(f'{line}\t{p.stat().st_size} bytes')
if large:
    print('\n'.join(large)); raise SystemExit(1)
print('tracked files >1MB: <none>')
PY
```

## Audit hardening details

- `.artifact.json` detection should be case-insensitive: use `p.name.lower().endswith((".artifact.json",))`.
- Runtime path checks should flag files under `.obsidian` and `.smart-env` parts.
- If the audit script skips itself for dangerous-delete regexes, keep that exemption narrow:
  - backend-root run: `scripts/v4/obsidian_v4_audit.py`
  - repo-root run: `Obsidian - Backend Assistance/scripts/v4/obsidian_v4_audit.py`
- Add a test proving unrelated same-named `other_project/scripts/v4/obsidian_v4_audit.py` is still scanned.
- Also test nested/copy paths such as `archive/Obsidian - Backend Assistance/scripts/v4/obsidian_v4_audit.py`; self-exemption must use exact relative-path membership, not `endswith(...)` or `parts[-4:]`, because suffix matching can silently skip copied scripts under arbitrary prefixes.

## PR discipline

Independent code-review suggestions, even if non-blocking, should be either explicitly deferred or implemented in a follow-up PR with TDD. After merge, verify on `main`, not only on the feature branch.

Hermes `delegate_task` review is asynchronous. If you dispatch an independent reviewer, do not merge while its result is still outstanding. If the reviewer result arrives after merge with `passed=false`, treat it as active: create a focused follow-up branch, add a RED regression test for the exact blocker, fix, rerun the full verification checklist, open PR, wait for CI, merge, and verify again on `main`.