---
name: library-adapter-absorption
version: 1.0.0
author: "UNKNOWN"
license: UNKNOWN
platforms: [windows, linux, macos]
workflow_software: hermes
archived_at: 2026-08-21
source_path: C:/Users/ALEX/AppData/Local/hermes/skills/software-development/library-adapter-absorption/SKILL.md
---

---
name: library-adapter-absorption
description: "Use when absorbing a lib into an existing adapter contract."
version: 1.1.0
author: Hermes Agent
metadata:
  hermes:
    tags: [adapter, open-source, absorption, contract, registry, integration, autonomous-loop]
    related_skills: [agent-workflow-fortress, project-gap-analysis, full-stack-absorption-verification]
---

# Library Adapter Absorption Workflow

Use this when implementing a specific open-source Python library as a typed adapter
within an existing adapter-contract framework.  Each autonomous-loop cycle implements
exactly one library — the concrete per-project execution for items marked
`adapter_contract_pending` in an absorption registry.

## Trigger

- A project has an existing adapter contract framework (`AdapterCapability`,
  `AdapterInput`, `AdapterResult`, `AdapterStatus`, registry).
- An open-source library from the project's absorption registry or "第一批 Adapter"
  list needs a concrete adapter, fixture, and tests.
- The absorption matrix already classifies the library as `adapter_contract_pending`.

Do NOT use this skill for:
- First-time framework setup (that's a different skill class)
- High-risk / `deferred_review` projects (those need independent security audit)
- `reference_only` projects (design/architecture absorption only, no code)

## Prerequisites

Before starting, confirm:

1. The project has an adapter contract framework with: `AdapterKind`, `AdapterStatus`,
   `AdapterCapability`, `AdapterInput`, `AdapterResult`, `register_adapter()`,
   `lookup_adapter()`, and a populated registry in `adapter_fixtures.py` or equivalent.
2. The candidate library is listed in the project's absorption registry as
   `adapter_contract_pending` and is on the "第一批 Adapter" or equivalent priority list.
3. Read-only verification confirms the library's GitHub source, license (MIT/Apache/BSD
   preferred), current version, PyPI availability, and basic API surface.

## Workflow

### 1. Read Contract Structures

Read these files before any edits:

- `shared/adapter_contract.py` — `AdapterKind`, `AdapterStatus`, `AdapterCapability`,
  `AdapterInput`, `AdapterResult`, registry functions.
- `shared/adapter_fixtures.py` — importability helpers (`_*_importable()`),
  the `_register_all()` function with existing registrations and priorities,
  fallback handlers.
- `tests/test_adapter_contract.py` — existing test classes: registry lookup,
  unavailable returns non-success, real URL/file smoke.

### 2. Install and Smoke

```bash
pip install <library>
python -c "import <module>; print(<module>.__version__); # quick API test"
```

**If install fails:** document exact blocker (missing system dep, Python version
incompatibility, not on PyPI), skip implementation, register as `UNAVAILABLE` only.
Do NOT vendor from source or use `--find-links` without explicit authorization.

**For external binaries** (ffmpeg, tesseract): verify via `which <binary>` and
`<binary> --version` instead of pip install. The importability checker uses
`shutil.which()`, not a try/except ImportError.

### 3. Add Importability Checker

In `shared/adapter_fixtures.py`, near the other `_*_importable()` helpers:

```python
def _<library>_importable() -> bool:
    try:
        import <module>  # noqa: F401
        return True
    except ImportError:
        return False
```

**For external binary adapters** (ffmpeg, tesseract):

```python
def _<binary>_available() -> bool:
    import shutil
    return shutil.which("<binary>") is not None
```

### 4. Write Adapter Function

A function taking `AdapterInput` → returning `AdapterResult`:

```python
def convert_<library>(input_: AdapterInput) -> AdapterResult:
    try:
        import <module>
    except ImportError:
        return AdapterResult(
            success=False, content="", engine="<library>",
            error="<library> is not installed. Run: pip install <library>",
        )
    try:
        # library API call
        ...
        return AdapterResult(
            success=True, content=..., engine="<library>",
            metadata={"key": value},
        )
    except Exception as exc:
        return AdapterResult(
            success=False, content="", engine="<library>",
            error=f"<library> conversion failed: {exc}",
        )
```

**Rules:** (1) Catch `ImportError` first, return non-success with install hint.
(2) Catch all `Exception` around the real API call. (3) Format output as Markdown
when possible. (4) Include rich metadata (char_count, title, authors, etc.).

**For subprocess-based adapters** (ffmpeg/ffprobe), use a different pattern with
multiple exception branches:

```python
def convert_<binary>(input_: AdapterInput) -> AdapterResult:
    if not _<binary>_available():
        return AdapterResult(
            success=False, content="", engine="<binary>",
            error="<binary> is not installed or not in PATH.",
        )
    source = input_.source
    if not source:
        return AdapterResult(
            success=False, content="", engine="<binary>",
            error="Empty source — provide a file path",
        )
    path = Path(source)
    if not path.is_file():
        return AdapterResult(
            success=False, content="", engine="<binary>",
            error=f"File not found: {source}",
        )
    try:
        import subprocess, json
        result = subprocess.run(
            ["<binary-probe>", ...],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode != 0:
            return AdapterResult(...)
        data = json.loads(result.stdout)
        return AdapterResult(success=True, content=..., engine="<binary>", metadata={...})
    except subprocess.TimeoutExpired:
        return AdapterResult(..., error=f"<binary> timed out processing {source}")
    except json.JSONDecodeError as exc:
        return AdapterResult(..., error=f"Failed to parse output: {exc}")
    except Exception as exc:
        return AdapterResult(..., error=f"<binary> failed: {exc}")
```

The bare `Exception` catch serves as a safety net — every recoverable failure
path should be caught specifically.

### 5. Register in the Registry

In `shared/adapter_fixtures.py` → `_register_all()`, add:

```python
available = _<library>_importable()
register_adapter(
    AdapterCapability(
        kind=AdapterKind.<CATEGORY>,
        format="<format>",
        engine="<library>",
        status=AdapterStatus.INSTALLED if available else AdapterStatus.UNAVAILABLE,
        priority=<N>,
        requires_network=True,  # if it fetches remote data
        notes="pip install <library>" if not available else "",
    )
)
```

**For multi-format engines**, loop over the supported formats:

```python
available = _<library>_importable()
for fmt in ("pdf", "docx", "pptx", "xlsx"):
    register_adapter(
        AdapterCapability(
            kind=AdapterKind.DOCUMENT, format=fmt,
            engine="<library>",
            status=AdapterStatus.INSTALLED if available else AdapterStatus.UNAVAILABLE,
            priority=30,
        )
    )
```

**Priority convention for WEBPAGE adapters:**
- 10: trafilatura (best HTML→MD)
- 15–25: newspaper4k (20), scrapling (25), etc.
- 30: readabilipy
- 50: safe-http+raw (last-resort HTML fallback)

### 6. Write Focused Tests

Add a new `Test<Library>Adapter` class to `tests/test_adapter_contract.py`.

Minimum 4 tests:

| Test | Purpose |
|---|---|
| `test_registry_contains_<library>` | Registry populated correctly; `lookup_adapter()` finds it |
| `test_convert_<library>_not_installed_returns_unavailable` | Fail-closed when import missing (use `builtins.__import__` monkeypatch) |
| `test_convert_<library>_empty_input_fails_gracefully` | Empty source doesn't crash |
| `test_convert_<library>_real_<fixture>` | Real URL/file produces expected content |

**Real-content test with `pytest.skip()` for optional libraries:**

```python
def test_convert_<library>_real_content(self, tmp_path):
    from shared.adapter_fixtures import convert_<library>, _<library>_importable
    if not _<library>_importable():
        pytest.skip("<library> not installed — cannot test real conversion")
    f = tmp_path / "test.ext"
    f.write_text("...", encoding="utf-8")
    result = convert_<library>(AdapterInput(source=str(f)))
    assert result.success
    assert result.engine == "<library>"
```

Do NOT use `pytest.importorskip()` because it runs a real import at module-
discovery time, which defeats the adapter's runtime-detection pattern.
Use the project's own `_<library>_importable()` helper instead.

**Handle stale-registry pitfall in the registry test:**

```python
def test_registry_contains_<library>(self):
    from shared.adapter_fixtures import ensure_registered
    import shared.adapter_fixtures as fixtures
    import shared.adapter_contract as contract
    if not contract._ADAPTER_REGISTRY:
        fixtures._registered = False
    ensure_registered()
    cap = lookup_adapter(...)
    assert cap is not None
```

**Monkeypatch clean-up for import simulation:**

```python
real_import = builtins.__import__
try:
    def fake_import(name, *args, **kwargs):
        if name == "<module>":
            raise ImportError("<module> not available")
        return real_import(name, *args, **kwargs)
    builtins.__import__ = fake_import
    # test assertions
finally:
    builtins.__import__ = real_import
```

**For external binary adapters** (ffmpeg, tesseract), mock `shutil.which` instead:

```python
import shutil
from unittest.mock import patch
from shared.adapter_fixtures import convert_<binary>

with patch.object(shutil, "which", return_value=None):
    result = convert_<binary>(AdapterInput(source="test.mp4"))
    assert not result.success
    assert "not installed" in (result.error or "").lower()
```

### 7. Update Registry Count Assertions

Find the minimum-count assertion for the adapter's category and bump it:

```python
# e.g. for WEBPAGE adapters:
html_keys = [k for k in registry if k.startswith("webpage:html:")]
assert len(html_keys) >= <old_count + 1>
```

### 8. Run Full Adapter Suite

```bash
python -m pytest tests/test_adapter_contract.py -v --tb=short
```

Expected: zero NEW failures. Only pre-existing documented gaps (e.g. optional
engines not installed) may remain. Any new failure is a blocker.

### 9. Preserve Optional Dependency Status

Do NOT add the library to `pyproject.toml` core dependencies. It is discovered
at runtime via the importability check. If the user explicitly wants it as a
default dependency later, they add it.

### 10. Record Evidence for Autonomous Loops

When running inside a sleep-mode or continuous-loop cycle, record completion
evidence after all tests pass:

```python
# In activity.jsonl (append only, never write_file):
entry = {
    "event": "cycle_<library>_adapter_complete",
    "mode": "active",
    "head": "<current SHA>",
    "branch": "<current branch>",
    "task": "O-<N>",
    "title": "<library> adapter absorption",
    "evidence": {
        "<library>_tests": "N/N passed",
        "full_adapter_tests": "X/Y passed, Z skipped (documented engine gaps: ...)",
        "adjacent_gates": "A/B passed = no regression",
        "new_files_modified": [
            "shared/adapter_fixtures.py (+ convert_<library>)",
            "tests/test_adapter_contract.py (+ Test<Library>Adapter: N tests)",
        ],
        "features": ["...", "..."],
        "head_unchanged": True,
        "tree_unchanged": True,
        "single_writer": True,
        "controlled_wip_preserved": True,
    },
    "next_task": "O-<N+1>",
    "at": "<ISO-8601>",
}
```

Update `state.json` via `Path.replace()` pattern (not `Path.rename()` on Windows):

```python
tmp_path = state_path.with_suffix(".json.tmp")
tmp_path.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")
json.loads(tmp_path.read_text(encoding="utf-8"))  # verify parseable
tmp_path.replace(state_path)  # Windows-safe atomic replace
```

## Cross-cutting integration boundaries

- **Cold-path initialization is part of the adapter contract:** when a service keeps heavy adapter dependencies as module-level `None` seams and initializes them lazily, every public command that dereferences those seams must call the initializer at entry. Never rely on an earlier intake/import call in the same process. Add a test that invokes approval, learning, practice, audit, retry, or replay from a cold module state.
- **Keep semantic compatibility parsing explicit:** for Markdown checklists and similar low-entropy syntax, a line/token parser is often safer than a heavily escaped regex, especially on Windows editing paths where backslashes can be double-encoded. Preserve read-only behavior, path containment, idempotency, semantic diff, and explicit loss reporting.
- **Existing code still needs delivery-grade verification:** if the adapter or projection already exists on `main`, run its real contract tests and record it as verified; do not create a no-op PR. If a cold-path or integration regression is found, make the smallest root-cause fix and verify exact-head CI plus merge-SHA main CI.

See `references/cold-path-and-semantic-parser.md` for the condensed reproduction patterns.
For verifying that user-submitted open-source projects were actually registered in
the absorption ledger (reconciliation, drift detection), see
`references/absorption-ledger-reconciliation.md`.
For the three honest-capability fixes (metadata-only fake success, legacy
heuristic isolation, supply-chain licence-gate ledger) plus the worktree
pytest-tmp collision trap, see `references/mfx-honest-capability-patterns.md`.
For the **absorption atlas analysis workflow** — taking a master atlas of
hundreds of candidates and producing real disposition decisions (ledger v2,
matrix v2, licence corrections), not just registration — see
`references/absorption-atlas-analysis.md`.
For the **bulk absorption implementation pattern** — moving multiple ADOPT items
from analysis to real code (deps, modules, tests, CI fix) in one batch — see
`references/bulk-absorption-implementation.md`.
For the **deep vs shallow absorption decision** — when the user wants source vendoring
(not pip + wrapper) and how to execute it — see `references/deep-vs-shallow-absorption.md`.
For the **external dependency documentation workflow** — producing a comprehensive
registry with download links, synced to both project repo and OS configuration
directory — see `references/external-dependency-documentation.md`.
For the **gh pr merge benign main-worktree warning** when
a local worktree holds main, see `references/gh-pr-merge-worktree-warning.md`.
For the **H2 pipeline integration pattern** — wiring absorbed modules into the
actual processing chain (routing, quality gate, cross-validation, canvas,
learning) — see `references/h2-pipeline-integration.md`.
For **absorbing an agent runtime / external executor** (e.g. DeepSeek Harness,
or any CLI/Web agent workbench) rather than a data-conversion library — read-only
discovery, path-mapping PLAN_ONLY, separate agent-runtime schema (strict
`additionalProperties:false` registry), loopback/scope/secret rejection tests,
`.cmd` shim detection, and the gated install checklist — see
`references/agent-runtime-adapter-absorption.md`.

## Pitfalls

### Stale-registry test pollution

A prior test (`test_registry_idempotent`) may clear `_ADAPTER_REGISTRY` without
resetting the `_registered` guard flag in `adapter_fixtures.py`. Any registry-
lookup test running after it will find an empty registry. Always check
`contract._ADAPTER_REGISTRY` emptiness before calling `ensure_registered()`.

### Idempotency guard at module level

`adapter_fixtures.py` calls `ensure_registered()` at import time. Once
`_registered` is True, subsequent calls are no-ops. A fresh Python process
is the only reliable reset — tests cannot re-register by re-importing alone.

### `builtins.__import__` cleanup discipline

When simulating an unavailable library via monkeypatching `builtins.__import__`,
restore it in a `try/finally` block. A failed restoration poisons ALL imports
in the test process — not just yours.

### Runtime detection, not config flags

Do NOT add config file toggles or environment variables to enable/disable the
adapter. The `_*_importable()` runtime check is the single source of truth.
Config-based toggles rot when the library is installed but the config says
disabled, or vice versa.

### Fake success: metadata-only adapters must not satisfy content conversion

A fallback chain that returns the FIRST `AdapterResult(success=True)` is only
safe if every adapter in the chain actually produces **content**. If a
metadata/probe adapter (Pillow image dimensions+EXIF, FFprobe container info,
file-size/label sniffers) sits *before* the real extractor (OCR, ASR, text
parser), it returns `success=True` with metadata text and the chain **silently
stops before ever running the content engine**. The result is a false
"converted" record: an image "succeeds" with `width=800,height=600` and no OCR
text; media "succeeds" with container metadata and no transcript.

Symptoms: a format's docstring/README claims `OCR`/`ASR` but the actual chain
never reaches it; a pure metadata call short-circuits the pipeline; CI "passes"
because the metadata call returns success.

Fix rules:
- Metadata/probe adapters must return a **distinct success kind** (e.g.
  `metadata_only`, `degraded`, `unavailable`) that the orchestrator treats as
  *not content-success*. Do not let a metadata call satisfy a content
  conversion contract.
- Order the chain content-extractor-first when a real extractor exists, OR gate
  so metadata-only never blocks the content engine.
- Add a **content postcondition** to every `success=True` path: at minimum the
  returned text must be non-trivial (non-empty, non-metadata-only). If a format
  has no content engine installed, report `degraded`/`unavailable` — never
  "success".
- Test with a real image/scan/audio/video where the content engine is missing:
  assert the format reports degraded/unavailable, not success.
- When a vendored third-party JS/py asset is added, run the repo's repository-
  convention check (`missing-final-newline` fails minified single-line files —
  append a trailing LF) before opening the PR, not after CI does.

### Vendored worker-spawning JS: lazy-init the worker, not on page load

A vendored JS library that spawns a Web Worker at init (e.g. PDF.js
`GlobalWorkerOptions.workerSrc`) must NOT configure that worker in an inline
`<script>` on page load. PDF.js probes/touches the worker during library init,
and a browser-smoke test that asserts **all** console errors are
`ERR_CONNECTION_FAILED` (or that there are **no** console errors after
navigation) will fail because the worker fetch/init emits a non-whitelisted
console error that pollutes the collected list — even though the reader itself
works. The failure is a false regression against your UI change.

Fix: set the worker source lazily *inside* the reader's closure, so it is
assigned only when a document is actually opened (a static string assignment,
no worker spawn on page load):

```js
// page-load-safe: no worker spawn until a PDF is opened
try { if (pdfjsLib) pdfjsLib.GlobalWorkerOptions.workerSrc = "/workspace/assets/pdf.worker.min.js"; } catch (e) {}
```

And keep the worker-load config in `app.js` (or your asset script), NOT in the
HTML `<script>` block. Verify by running the real browser-smoke locally after
starting the server, not just unit tests.

### Content-addressed evidence anchor HTTP API (AXW-022B pattern)

When a reader needs to let users pin a selection and jump back, expose a
content-addressed anchor over HTTP reusing an existing anchor backend
(`build_evidence_anchor(raw_sha256, source_revision, locator)` /
`store` / `resolve`):

- `POST /api/evidence/anchor` — body `{raw_sha256, source_revision, locator}`
  (Pydantic model with `extra="forbid"`, sha length ≥ 40, revision ≥ 1).
  Returns the stable `anchor_id`. Reuse the workspace DB path so anchors
  persist across restarts.
- `GET /api/evidence/anchor/{anchor_id}` — resolve back to raw source +
  locator for jump-back; `404` fail-closed when missing.
- Type-annotate with the imported `EvidenceAnchor` class directly — do NOT
  `import ... as _EA` (ruff N814 flags CamelCase aliased as a constant), and do
  not re-import inside the handler body (F401 unused).
- Test: roundtrip (create→resolve), missing-field fail-closed, missing-anchor
  404, bad sha-shape rejected.

### CI: new deps must be in BOTH [project] dependencies AND [dependency-groups] ci

When adding a new Python library as a core dependency, it MUST be listed in
**both** `[project] dependencies` **and** `[dependency-groups] ci` (the ci key
inside `[dependency-groups]` in pyproject.toml). CI runs `uv run --frozen
--only-group ci pytest`, which installs ONLY what is declared in the ci group —
it ignores `[project] dependencies` entirely. A new dep declared only in
`[project] dependencies` will cause `ModuleNotFoundError` in CI even though
local `uv run pytest` passes.

Fix order: (1) add to `[project] dependencies`, (2) add same dep to
`[dependency-groups] ci`, (3) `uv lock` WITHOUT `--frozen` (to resolve new
packages), (4) `uv sync --frozen` (to install), (5) update `requirements.txt`
to match the new deps (test_runtime_operations.py asserts equality between
requirements.txt and pyproject.toml declared deps), (6) recompute and update
the lock digest in `app/release-manifest.json` (test_release_manifest.py
asserts it matches `sha256(uv.lock)`), (7) `uv run --frozen --only-group ci
pytest` to verify CI-mode works locally. If you catch this after the first CI
failure, git commit --amend and force-push the branch (branch is new —
--force-with-lease is safe).

After adding deps, these TWO files break silently in CI unless updated:
- `requirements.txt` — must list the new dep (test: asserts requirements == declared)
- `app/release-manifest.json` — the `dependency_lock.digest` field must match
  `hashlib.sha256(uv.lock).hexdigest()` (test: asserts manifest digest == computed)

### Library API changes across major versions

When adding a library as a dependency, the resolved version may differ from
what documentation/tutorials describe. Always smoke-test the ACTUAL installed
API: `uv run python -c "from lib import X; print(dir(X))"`. Specific traps:

- **fsrs v6**: `State.New` removed (new cards start `State.Learning=1`).
  `Card.scheduled_days` removed (compute from `card.due - card.last_review`).
  `Scheduler.review_card()` parameter is `review_datetime`, not `now`. Returns
  `tuple[Card, ReviewLog]`, not a single object.
- **jiwer v4**: No `jiwer.__version__` attribute. Import functions directly:
  `from jiwer import wer, cer`.

### Legacy heuristics must never masquerade as verification

A coarse domain/keyword credibility score (e.g. `score_credibility`: rewards a
trusted domain suffix, the words "peer-reviewed", or a DOI-shaped substring)
is an **internal sort hint**, not evidence that a claim is web-verified. If
such a score can reach a `verified` / `web-verified` / `EvidenceBundle` /
`CrossValidation` state, a fake fact can silently pass as authoritative.

Fix rules:
- Tag the return with an explicit classification so callers can't mistake it:
  `{"score": ..., "level": ..., "classification": "legacy_heuristic"}`.
- In the pipeline/consumer, force `verified=False` on the legacy stage and add
  a comment that real verification goes through the EvidenceConnector /
  web-crosscheck pipeline — never the heuristic.
- Docstring must state plainly: trusted domain / "peer-reviewed" / DOI-shaped
  text does NOT constitute claim verification.
- Test with a high-score case (trusted domain + "peer-reviewed" + DOI-looking
  URL): assert `classification == "legacy_heuristic"` and `verified is not True`.

### Optional extras of an approved base package are separate dependency decisions

A library's optional extras are NOT covered by approving the base package.
`markitdown[pdf]` installs the base + PDF readers (pdfminer-six, pdfplumber,
pypdfium2) but **cannot read DOCX** — the DOCX converter throws
`MissingDependencyException` telling you to install `markitdown[docx]` (which
pulls python-docx) or `markitdown[all]`. Same class of trap: an "approved"
image/ASR engine may only cover a subset of formats or need a model pack that
is itself a separate licence decision.

Fix rules:
- Treat every optional extra / model pack as its own supply-chain entry
  (own `gate` in the licence ledger), never inherited from the base package.
- If the extra is NOT approved, the adapter must **fail closed with a clear
  error naming the missing extra** (e.g. `"DOCX conversion requires
  markitdown[docx]"`), never fake success and never silently add the dep.
- Capture this as a test: with the extra absent, real .docx input returns
  non-success with an explanatory error; if the extra is present the same
  test asserts non-empty content (no metadata-only success).
- Only when the owner approves the extra dependency does the adapter upgrade
  from degraded to qualified.

### PR body backticks mangled by bash when using `gh pr create --body "..."`

Markdown backticks (` ```python ` etc.) in a `--body` string are interpreted
by bash as command substitution. Symptoms: the PR body shows line-by-line
errors like `import: command not found`, `from: command not found`. The PR IS
created (URL appears at end), but the body is garbage.

Fix: use `--body-file` with a temporary file, or escape every backtick with
`\``. Prefer `--body-file /tmp/pr-body.md` for long multi-paragraph bodies.

Changing the package name in `pyproject.toml` (`name = "old"` → `name = "new"`)
cascades through the entire build chain: wheel filenames, importable package
names, editable installs, CI wheel-smoke, Windows runtime smoke, py-compat
matrix. A single name change can cause 5+ CI jobs to fail simultaneously.
**Always isolate naming changes in their own PR, never mix with feature
or absorption work.** When the user says pause on naming, revert immediately
in the feature branch and defer to a dedicated naming-only branch.

### Deep absorption: user may want source vendoring, not pip + wrapper

The default absorption workflow says \"do NOT vendor from source without
explicit authorization\" — but some users actively WANT deep source absorption.
When the user says \"能直接复用的源码等深度的内容也要吸收\", they mean:
clone the upstream, copy the inference code and model files directly into
`shared/`, remove the pip dependency. See `references/deep-vs-shallow-absorption.md`.



When a format has structure worth pinning later (paragraphs, headings,
tables, cells), the adapter should split extracted markdown into typed blocks
with a stable `source_md` anchor so future Claim/Evidence work can pin to a
location:

```python
def _to_blocks(markdown: str) -> list[dict[str, Any]]:
    # split on blank lines; '|...|' → kind="table", '#...' → kind="heading",
    # else kind="paragraph"; every block gets anchor={"source_md": line[:200]}
```

Persist via the project's conversion-run object (`create_conversion_run` +
`store_conversion_run` with the raw SHA-256, engine, version) so a document
has a replayable derived chain — blocks survive restarts and can be re-read.
A pure-function test on `_to_blocks` (heading/paragraph/table kinds present,
empty chunks dropped) costs almost nothing and locks the shape.

### Worktree pytest tmp-path collision: fails locally, passes in CI

Inside a git worktree created under the project's `.hermes/task-runtime/...`
directory, tests that use `tmp_path` fixtures can collide: pytest's tmp root
resolves under the worktree's `.hermes/task-runtime/pytest-tmp/...`, and a
backup/restore style test that writes then re-reads its own tmp files can get
`FileNotFoundError` (path mangled / cleaned between fixtures). This is an
environment artifact, NOT a regression in your change.

Diagnose before debugging your code:
- Run the failing test file in a **clean, untouched worktree** on the same base
  SHA. If it fails there too, it is pre-existing / environment — not your edit.
- Confirm by pushing the PR: CI uses an independent tmp dir, so the same test
  passes in CI (`test (3.12)` green) while it failed locally. That green CI is
  authoritative for gate purposes.

## Supply-chain licence gate ledger (MFX-001 pattern)

When absorbing many open-source components, keep a **structured, machine-readable
ledger** (JSON) rather than only a prose THIRD_PARTY_NOTICES. One entry per
component with: `code_license` AND `model_license` (kept separate — code and
model licences differ), `gate` ∈ {`approved`, `review_required`, `blocked`},
`revision_ref`, and `notes`. Rules:
- `approved` = reviewed for default use; `review_required` = capability probes
  must NOT default-enable it; `blocked` = licence-gated off (AGPL, GPL, custom
  model clauses, online-service terms) until a separate owner/legal decision.
- A validator test asserts: ledger is valid JSON, every gate is allowed,
  known `blocked` components are present-and-blocked, default engines are
  present-and-not-blocked, and blocked components are **absent from the default
  engine chain** (serialize `_ENGINES` and assert no blocked name leaks in).
- Keep code and model licence review separate — e.g. PyMuPDF is AGPL code;
  FunASR is MIT code but its model carries a custom modifiable protocol.

## Verification Checklist

- [ ] Library install smoke passed
- [ ] `_<library>_importable()` detects presence correctly
- [ ] Adapter function returns success/failure correctly
- [ ] Registry entry correct category, engine, priority
- [ ] Tests cover: registry presence, unavailable fallback, empty input, real fixture
- [ ] Full adapter suite: only pre-existing documented gaps fail
- [ ] No new core dependency in `pyproject.toml`
- [ ] Registry count assertions bumped
