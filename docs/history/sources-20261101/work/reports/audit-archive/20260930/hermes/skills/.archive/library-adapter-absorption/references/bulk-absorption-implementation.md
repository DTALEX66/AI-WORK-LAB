# Bulk Absorption Implementation Pattern

Use when absorbing multiple ADOPT-recommended libraries from the absorption atlas
into real code (not just registration). This is the "from analysis to integration"
step — 8 libraries absorbed in one batch.

## Trigger

- Absorption atlas v2 exists with ADOPT items that are "absorb now" (small,
  permissive licence, no models/bake-off needed).
- User says "能吸收的全部吸收并入到项目里" — move from documents to code.

## Pattern

### 1. Identify "absorb now" vs "defer"

From the ADOPT list, separate into:
- **Now**: Pure Python libs with MIT/Apache-2.0, no models, no bake-off needed
  (JiWER, RapidFuzz, py-fsrs, JSON Canvas spec, public HTTP APIs)
- **Defer**: Needs model infra (faster-whisper, Silero VAD), needs bake-off
  (PaddleOCR vs EasyOCR vs RapidOCR), dev-tools (Syft, Gitleaks)

### 2. Add dependencies to BOTH sections of pyproject.toml

```toml
[project]
dependencies = [
    # ... existing ...
    "jiwer>=3.1",
    "rapidfuzz>=3.9",
    "fsrs>=5.0",
]

[dependency-groups]
ci = [
    # ... existing ci deps ...
    "jiwer>=3.1",
    "rapidfuzz>=3.9",
    "fsrs>=5.0",
]
```

CRITICAL: CI runs `uv run --frozen --only-group ci` which only installs from
`[dependency-groups] ci`. Dependencies in `[project] dependencies` ARE NOT
installed in CI mode.

### 3. Resolve and verify

```bash
uv lock                    # resolve new packages (no --frozen)
uv sync --frozen           # install
uv run python -c "import jiwer, rapidfuzz, fsrs; print('OK')"
# Check actual API surface — don't trust docs:
uv run python -c "from fsrs import Card, Scheduler, State; print([s for s in State])"
```

### 4. Create integration modules (each independent)

Each library gets its own integration module in `shared/`:

```
shared/text_quality.py      — JiWER (CER/WER) + RapidFuzz (alignment, spans)
shared/json_canvas.py       — JSON Canvas format validator (no lib dep)
shared/evidence_connectors.py — Crossref/DataCite/OpenAlex/Wikidata clients
shared/learning_scheduler.py  — FSRS v6 wrapper
```

Each module:
- Has a docstring with ADS-ID and licence note
- Exports `__all__` with the public API
- Uses only stdlib where possible (evidence connectors use only `urllib`)
- Has guardrails enforced (CER/WER requires truth; engine confidence != accuracy)

### 5. Write tests (one file per module)

```bash
tests/test_text_quality.py           — 9 tests
tests/test_json_canvas.py            — 11 tests
tests/test_evidence_connectors.py    — 7 tests (2 network tests skip in CI)
tests/test_learning_scheduler.py     — 6 tests
```

Network tests: decorate with `@pytest.mark.skipif("not config.getoption('--run-network')")`.

### 6. Verify with CI-mode pytest

```bash
uv run --frozen --only-group ci pytest tests/test_*.py -q
# Must pass with --only-group ci (simulates CI environment)
```

### 7. Sync requirements.txt and release manifest

After adding deps, two files MUST be updated or CI fails:

```bash
# requirements.txt — must list the new dep
echo "jiwer>=3.1" >> requirements.txt
echo "rapidfuzz>=3.9" >> requirements.txt
echo "fsrs>=5.0" >> requirements.txt

# app/release-manifest.json — recompute lock digest
python -c "
import json, hashlib
from pathlib import Path
m = json.loads(Path('app/release-manifest.json').read_text())
m['dependency_lock']['digest'] = hashlib.sha256(Path('uv.lock').read_bytes()).hexdigest()
Path('app/release-manifest.json').write_text(json.dumps(m, indent=2, ensure_ascii=False)+'\n')
"
```

CI tests that break if these are missed:
- `test_runtime_operations.py::test_requirements_txt_matches_pyproject_runtime_dependencies` (requirements.txt ≠ declared deps)
- `test_release_manifest.py::test_release_manifest_is_packaged_truth_and_matches_dependency_lock` (manifest digest ≠ sha256(uv.lock))
- `test_mfx001_supply_chain_ledger.py::test_ledger_exists_and_is_valid_json` (if schema_version changed from 1→2)

### 8. Ruff + conventions check

```bash
uv run --frozen --only-group ci ruff check shared/ tests/ --output-format=concise
uv run --frozen --only-group ci python scripts/check_repository_conventions.py
```

Common fixes: remove unused imports (`import math`, `from datetime import ...`),
remove undefined names from `__all__`, normalize line endings (CRLF→LF),
ensure trailing newline.

### 8. Commit and push

```bash
git add -A
git commit -m "feat(absorption): absorb N ADOPT items from atlas v2"
git push origin HEAD:feat/<branch>
```

If CI fails (test/ruff), fix, `git commit --amend --no-edit`,
`git push --force-with-lease`.

### 9. Open PR and wait for CI

```bash
gh pr create --base main --head feat/<branch>
gh pr checks <num> --watch
```

Expected: gateplan pass, lint pass, test pass, a0-gates pass, rest skipping.

## Absorbed libraries (session example, 2026-08-11)

| ID | Library | Licence | Module |
|---|---|---|---|
| ADS-001 | JiWER | Apache-2.0 | `shared/text_quality.py` |
| ADS-002 | RapidFuzz | MIT | `shared/text_quality.py` |
| ADS-003 | JSON Canvas | MIT format | `shared/json_canvas.py` + `docs/truth/JSON_CANVAS_ADOPTION.md` |
| ADS-004 | Crossref | public API | `shared/evidence_connectors.py` |
| ADS-005 | DataCite | public API | `shared/evidence_connectors.py` |
| ADS-006 | OpenAlex | freemium API | `shared/evidence_connectors.py` |
| ADS-007 | Wikidata | CC0 data | `shared/evidence_connectors.py` |
| ADS-008 | py-fsrs v6 | MIT | `shared/learning_scheduler.py` |

| ADS-009 | Magika (vendored) | Apache-2.0 | `shared/file_detection.py` (ONNX model + inference) |

36 tests passed (plus network), 2 skipped, ruff clean, CI pending.

## Deep vs shallow absorption (user-corrected, 2026-08-12)

The user explicitly corrected the approach: absorption should NOT stop at
\"add pip dep + thin wrapper\". When a component's source code is small,
permissively licensed, and self-contained, **vendor the source directly** —
copy inference code, bundle model files, remove the pip dependency.

Deep absorption signals:
- Library < 1000 lines of pure Python (e.g. Magika inference ~200 lines)
- Model file < 5MB (e.g. Magika standard_v3_0 ~3.1MB ONNX)
- Apache-2.0 / MIT licence (allow vendoring)
- No heavy framework dependency (only onnxruntime/numpy)

When these hold, do NOT `pip install` the library. Instead:
1. Clone the upstream repo at a fixed tag
2. Copy the inference code and model files into `shared/`
3. Adapt to project conventions (`__all__`, type hints, guardrails)
4. Add only the minimal runtime dep (e.g. `onnxruntime`)

See `references/magika-onnx-vendoring.md` for the full recipe.

Shallow absorption (pip + deep integration module) is still correct when:
- The library is large/complex (JiWER, RapidFuzz, py-fsrs are 1000s of lines)
- Vendoring would create maintenance burden > value
- The pip package already bundles models and provides a stable API
