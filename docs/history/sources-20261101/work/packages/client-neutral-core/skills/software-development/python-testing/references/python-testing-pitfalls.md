# Python Testing Pitfalls — Full Write-ups

Companion reference for `python-testing`. The SKILL.md keeps a symptom→cause
index; the full case studies, WRONG/RIGHT code, and dated evidence live here,
organised under the same § numbers the index points at. Nothing was deleted —
every pitfall from the original SKILL.md is preserved verbatim below.

---

## §1 `uv.lock` drift: phantom dependency names and never-locked new deps

A dependency group in `pyproject.toml` can carry a package name that does not
exist on PyPI (`httpx2` — the real package is `httpx`). uv keeps the phantom
name in `uv.lock`'s group metadata while the real package arrives transitively
(via `fastapi[standard]` etc.), so code, tests, and CI all stay green and
nothing flags the wrong declaration. Separately, deps added to `pyproject.toml`
without re-running `uv lock` (e.g. installed manually to try them) silently
stay out of the lock — the lock misses them until something regenerates it.
2026-08-12 in Cognitive-Loop-OS (#123): both at once — `httpx2` phantom AND
`rapidocr-onnxruntime`/`faster-whisper` (added in earlier PRs) never locked.

- Grep the lock for the declared name: a name listed in the group metadata but with NO package stanza below means the declaration is wrong or the dep was never locked.
- Fix: `uv lock` — it drops the phantom and picks up the missed deps in one pass. Then `uv sync --frozen <groups>` and re-run the full suite.
- **A manifest/lock-digest test is the tripwire, not a code bug.** Projects that assert a sha256 of `uv.lock` in a release manifest (Cognitive-Loop-OS: `app/release-manifest.json`, checked by `tests/test_release_manifest.py`) fail after every lock regeneration until the digest is recomputed (`hashlib.sha256(lock_bytes).hexdigest()` + revision bump). Expect that failure; it is the sync signal.
- **Rewriting JSON manifests: a missing trailing LF is a CI gate failure that local runs miss.** `Path.write_text(json.dumps(...))` without a trailing `\n` passes locally but CI lint fails with `missing-final-newline: text must end with LF`. Also, convention gates that CI runs with `--source head` check the committed BLOB, while a bare local run checks the WORKSPACE — so a local "passed" on a freshly-written file proves nothing until committed; the failure appears only in CI after push. Ensure trailing LF, then commit/amend + force-push the PR branch. If lint and a downstream gate (e.g. a0-gates) both fail, they are usually ONE root cause cascading — fix the file once, not twice.

## §2 Dependency-declaration audits: imports alone don't prove a dep is used — or unused

When auditing whether a declared dependency is dead weight (import-scan says "never imported"), two classes of false conclusions bite:

- **Framework-runtime deps are used indirectly.** `python-multipart` never appears in any `import` because FastAPI needs the PACKAGE to handle `UploadFile = File(...)` multipart forms — the framework imports it internally. Before flagging a dependency as unused, grep the framework-facing API usage (`File(`, `UploadFile`, `Form(`, `Response(...)` for fastapi; `jinja2` autoescaping etc.), and check whether the framework's own extra/feature set pulls it in.
- **Frozen-baseline-approved planned deps must NOT be removed even with zero imports.** 2026-08-12 (Cognitive-Loop-OS): `crawl4ai` / `langfuse` / `promptfoo` in the `ingestion` optional group had zero import references, yet the frozen baseline addendum (`MANDATORY_WEB_KNOWLEDGE_INGESTION_ADDENDUM`) explicitly approves Crawl4AI as a mandatory-integration candidate and openly states the adapter "has no direct call to Crawl4AI — do not treat the dependency as a real integration proof". Removing them violates the frozen baseline (immutable). The honest state is: declared-as-planned, documented-as-unimplemented — which is the correct engineering posture, not cruft.

Audit order before touching any dependency:
1. Import scan (AST or grep) → list of zero-import declared deps.
2. For each: does a framework/CLI consume it internally (UploadFile→multipart, liteLLM extras, pytest plugins)? Check the actual framework usage in the repo, not just imports.
3. Does a FROZEN baseline / addendum / taskpack approve it as a planned capability? Grep `docs/` (taskpacks, addenda, blueprints) for the name BEFORE proposing removal. `uv.lock` presence + zero imports is not enough to call it dead.
4. Only a dependency with no framework use AND no governance approval is a removal candidate — and even then, prefer documenting the plan over deleting if a roadmap mentions it.

## §3 `assertIn` on Lists is Element Membership, Not Substring

```python
# WRONG — this FAILS:
self.assertIn('missing reasoning', result.gaps)
# Checks exact element match, not substring!

# RIGHT — check for substring across elements:
self.assertTrue(any('missing reasoning' in g for g in result.gaps))
```

## §4 `assertEqual` with Floats

```python
# Use assertAlmostEqual for floats:
self.assertAlmostEqual(0.1 + 0.2, 0.3, places=6)
```

## §5 `assertRaises` Requires Context Manager

```python
# RIGHT:
with self.assertRaises(ValueError):
    int('abc')
```

## §6 Fixture Scoping

| Scope | Method | When |
|-------|--------|------|
| Per-test | `setUp()` / `tearDown()` | Every test needs isolation |
| Per-class | `setUpClass()` / `tearDownClass()` | Once per test class |
| Per-module | `setUpModule()` / `tearDownModule()` | Once per test file |

## §7 Python `re` — Variable-Width Lookbehind Error

Python's `re` module does NOT support variable-width lookbehinds.

```python
# WRONG — Python 3.11+ raises:
re.findall(r'(?<!\w)(?<!\n\s*)(?<!#)#([\w\-/]+)', text)

# RIGHT — merge into fixed-width:
re.findall(r'(?<![#\w])#([\w\-/]+)', text)
```

## §8 `\s` in Character Classes Matches Newlines

```python
# WRONG — \s inside [...] matches \n too
re.compile(r'^([\w\s]+)::\s*(.+)$', re.MULTILINE)

# RIGHT — use only space:
re.compile(r'^([\w ]+)::\s*(.+)$', re.MULTILINE)
```

## §9 S-V-O regex extractors: passive-voice be-verbs get swallowed into the subject

When testing a regex triple extractor (subject–verb–object), a pattern like
`r"(.+?)\s+(created|built|designed)\s+..."` silently captures the be-verb:
`"Python was created by Guido"` → subject becomes `"Python was"` (the `.+?`
greedily backtracks past `was` to the first verb). 2026-08-12: first-ever
tests for `shared/fact_extractor.py` caught exactly this — the fix is an
optional passive-voice group before the verb:

```python
r"(.+?)\s+(?:(?:was|were|is|are|has been)\s+)?(created|developed|built|made)\s+(?:by\s+)?(.+?)..."
```

- Add a test per relation pattern (`is_a`, `created_by`, `uses`, `contains`,
  `causes`, `part_of`, `depends_on`, `of`-pattern) with a real sentence — the
  first coverage pass is where these latent regex defects surface.
- Also test `max_facts` limiting, empty input, and that extracted entities
  are stripped of trailing punctuation — cleaning and limiting are as much
  contract as the pattern matches themselves.

## §10 WindowsPath Missing `is_relative()`

Python 3.11+ Windows: `WindowsPath` has NO `is_relative()`.

```python
# RIGHT — use try/except:
try:
    rel_path = resolved_path.relative_to(PROJECT_ROOT)
except ValueError:
    rel_path = str(resolved_path)
```

## §11 Monorepo Testing & Dedup Patterns

Key patterns:
- Subdirectory test imports with `sys.path` for hyphen-named directories
- SQL-free service module testing (pass `list[dict]` instead of querying DB)
- OS-specific `pytest.raises` match patterns
- Dataclass with defaults — no TypeError on empty init
- Hyphenated test directories (`tests/workflow-assistance/`…) cannot be dotted module paths: `python -m unittest tests.workflow-assistance.test_x` dies with `ModuleNotFoundError` (a hyphen is not a Python identifier, and the package chain is missing). Run the test FILE directly instead — a file that self-resolves the repo root via `Path(__file__).resolve().parents[N]` is standalone-runnable: `python tests/workflow-assistance/test_x.py`.
- When a test file imports a module that lives in a sibling directory (`from canonical_store import ...` where the module sits in a `scripts/` dir), set `PYTHONPATH` to that directory for the run (Windows `;`-separator even from Git-Bash). Without it the run fails at import even though the test file itself is fine.

## §12 Similarity / Vector Search Tests Need Strong Anchors

Embedding and vector-search tests can be flaky when the "relevant" sample does not actually share query terms or strong semantic anchors. Hash/ngram embedders especially may rank an unrelated short text above a vaguely related text.

```python
# WEAK — query terms are absent from the expected top document; ranking may drift:
index_card("c1", "backpropagation algorithm explained")
index_card("c2", "how to make pizza dough")
results = search_cards("neural network training", top_k=2)
assert results[0][0] == "c1"

# STRONG — expected document contains the query anchors being asserted:
index_card("c1", "neural network training backpropagation algorithm explained")
index_card("c2", "how to make pizza dough")
results = search_cards("neural network training", top_k=2)
assert results[0][0] == "c1"
```

If a test is meant to verify no-error behavior rather than exact ranking, assert shape/count or membership instead of first-place ordering.

## §13 Full-suite warnings: probe with `-W error::DeprecationWarning` before deciding they matter

A green suite can carry warning noise that is either (a) a real contract defect
your code causes, or (b) an upstream library's deprecation you cannot fix.
Before ignoring or chasing them, re-run the suite with deprecations escalated
to errors to see WHICH tests break and whether the raise site is yours:

```bash
pytest -q --tb=no -W error::DeprecationWarning
```

2026-08-12 (Cognitive-Loop-OS): this surfaced one failing test —
`TestReadabilipyAdapter` failed with
`readabilipy conversion failed: Call to deprecated method findAll. (Replaced by find_all)`.
The raise site was **inside the readabilipy package** calling BeautifulSoup's
deprecated `findAll` — an upstream-library/bs4-compat issue, NOT a project
defect. Normal runs pass (warning, not error); the project never runs `-W
error`. Verdict: benign upstream noise — do not "fix" it (you cannot patch the
dependency; a warning filter would mask real future deprecations).

- Run the probe first, then classify each break: raise site in YOUR code →
  fix; raise site in a dependency's internals → record as upstream noise.
- The other warning class you will see is "optional feature unavailable"
  (e.g. `nltk is not installed. Some NLP features will be unavailable`) —
  that's a missing optional extra, not a defect; decide per-package whether
  the optional feature matters for the suite's assertions.

## §14 Registry-driven compliance assertions: derive the blocked set from the source of truth

When a test enforces a compliance boundary (e.g. components marked
`REVIEW-BLOCK` must not appear in a default engine chain), drive the assertion
from the authoritative registry (ledger JSON / manifest), not a hardcoded
list. 2026-08-12 (Cognitive-Loop-OS #128): the test computed
`blocked = {c["name"].lower() for c in _ledger()["components"] if c["disposition"] == "REVIEW-BLOCK"}`
then asserted every name absent from the engine map — this immediately exposed
that `marker-pdf` (ledger entry B003, code Apache-2.0 but weights a modified
OpenRAIL-M) was registered in the default PDF engine chain. The old hardcoded
`{"mineru", "funasr", "searxng", "zotero"}` list had never caught it.

- **A registry-driven failure is a bug report — but verify the guard list
  first.** When the new assertion fails, compute the actual blocked set and
  diff it against BOTH the engine chain and the hardcoded guard. The failure
  can be the code leaking (marker in chain → fix the code) OR the guard list
  being stale (zotero was never REVIEW-BLOCK → fix the test's expectation).
  In #128 both were true at once: one leaked name needed a code fix, the
  guard needed a test fix. Never assume which side is wrong without printing
  the actual set.
- Fix style for a blocked-but-implemented engine: remove it from the DEFAULT
  chain but KEEP the function defined, with a comment citing the ledger entry
  and the re-entry condition (e.g. weight license resolved). A future
  reviewer sees both the exclusion and the path back in.
- Assert both directions: every blocked name absent from the chain AND the
  historical blockers still flagged in the ledger (guards against the ledger
  silently losing entries).
- Update the module's ASCII header diagram in the same commit — it documents
  the default chain and goes stale the moment an engine is removed.

## §15 Hard-coded schedule constants in a lifecycle INSERT = the feature is a stub

When a feature claims a lifecycle (spaced repetition, scheduling, review
cadence), grep its INSERT for the schedule columns — a literal default like
`VALUES (?, ?, ?, 1, 2.5, ?, ?)` means the loop never actually schedules.
2026-08-12 (#125, Cognitive-Loop-OS): `record_practice_evidence` wrote
`kb_reviews` with hard-coded `interval_days=1, ease_factor=2.5,
next_review_at=now` — every practice "reviewed tomorrow", the SM-2 claim was a
stub. Fix: wire the pure scheduling function
(`knowledge_base.reviews._sm2_interval(quality, prev_interval, prev_ease)`),
querying the card's previous review first.

- Assert interval GROWTH in the test, not just "review recorded": three
  consecutive quality-5 reviews must produce `[1, 6, 16]`. A test that only
  checks a row exists passes on a stub.
- **Compute the expected sequence with the real function before hard-asserting
  exact numbers** — rounding differs from intuition: `round(6 * 2.7) = 16`,
  not 15. One `python -c` call with the actual `_sm2_interval` prevents a
  wrong-assertion red run.
- Ease factors should also be asserted (`>= 2.5` and rising with quality) —
  a stub leaves ease constant.

## §16 CLI scripts that import library helpers: verify the function name exists first

A new CLI (`scripts/run_bakeoff.py` style) that imports helpers from a library
module fails at IMPORT time if the name is wrong — `ImportError: cannot import
name 'enumerate_fixtures'` when the real function is `load_fixtures`. The
failure is instant but wastes a run and reads like a packaging problem.

- Before writing the CLI's imports, `grep -n "^def \|^    def " <module>` the
  exact public names; don't guess from memory of the module's purpose.
- After fixing imports, run the CLI once with real fixtures to prove the
  full path (engine discovery → run → CSV/JSON report), not just `--help`.

## §17 CI ruff scope often EXCLUDES tests/ — fix only your own violations

CI's ruff invocation usually lists explicit paths
(`python -m ruff check app shared knowledge_base inspiration_research scripts`)
and may NOT include `tests/`. A local `ruff check .` then finds I001/F841 in
test files that CI never checks. 2026-08-12 (#120): 7 findings in tests/,
all CI-invisible.

- Read the workflow's ruff command scope BEFORE "fixing" lint findings in
  files outside it — they are hygiene noise, not CI gates.
- Fix violations YOU introduced in new/edited test files (auto-fix + manual);
  leave pre-existing ones in files you did not touch (out-of-scope churn).
- Verify the CI-scoped paths separately: `ruff check app shared ... scripts`
  must be clean even when tests/ has leftover findings.

## §18 Optional network stage in a pipeline: opt-in only, never in defaults

Adding a stage that calls external APIs (EvidenceConnectors/Crossref/OpenAlex)
to an orchestrator: gate it on explicit opt-in
(`if "evidence" in actions and content:`), NEVER in the default action list —
defaults stay offline and deterministic. 2026-08-12 (#124): the pipeline's
`evidence` stage extracts a DOI from content via regex
(`r"10\.\d{4,9}/[^\s]+"`, rstrip trailing `.,;:`), queries it directly, and
falls back to an OpenAlex claim-text search of the first 300 chars.

- **When the called wrapper doesn't accept the kwarg you need (e.g.
  `enrich_with_public_sources` was doi-only but the stage wants
  claim_text/qid), EXTEND the wrapper to forward all three to the underlying
  query function** — do not drop the call or inline a different path.
- Pin all three behaviors in tests: DOI path (classification echoed,
  `verified=False`, DOI value asserted), claim-text fallback (capture the
  kwargs the fake receives and assert them), and absent-by-default (stage key
  not present when action omitted).
- The `classification` + `verified=False` contract (heuristic never promoted
  to evidence state) is the same pattern as a legacy-heuristic sibling stage —
  assert both stages carry it.

## §19 SQLite Testing: Persistent State Across Tests

When testing SQLite-backed code, the database file persists across test runs.
Searches may return stale data from previous test executions, causing
`results[0]["id"] == expected_id` to fail even when your test correctly
inserted the record.

**Fix**: use `any()` for existence checks instead of positional assertions, and make the query window large enough for persistent DB tables:

```python
# WRONG — fails when previous runs left data in the DB or limit is too small:
results = search_core_objects("MVP development", top_k=5)
assert results[0]["id"] == "test_obj_001"

traces = list_traces_db(limit=10)
assert any(t["id"] == "trace_test_001" for t in traces)  # may be crowded out

# RIGHT — checks that your record exists somewhere in a wide enough result set:
results = search_core_objects("MVP development", top_k=50)
assert any(r["id"] == "test_obj_001" for r in results)

traces = list_traces_db(limit=500)
assert any(t["id"] == "trace_test_001" for t in traces)
```

**Alternative**: clean the database in `setUp()` or use an in-memory SQLite
(`:memory:`) for isolated test runs:

```python
class TestSQLite:
    def setup_method(self):
        # Use in-memory DB or delete the file before each test
        import app.memory.database as db
        db.DB_PATH = Path(":memory:")  # or temp file
        db.init_db()
```

## §20 Windows: SQLite temp files lock `TemporaryDirectory` cleanup (WinError 32)

On Windows, an open SQLite connection holds an exclusive file handle, so a test
that creates a store inside `tempfile.TemporaryDirectory` and does NOT close
every connection before the block exits fails in `__exit__` with
`PermissionError: [WinError 32] 另一个程序正在使用此文件` during `cleanup()`.
The traceback points at `tempfile.py` `_rmtree` — misleading, the real culprit
is the leaked connection.

- **Close every connection in `tearDown()`** (store + reader + any writer),
  before `TemporaryDirectory` cleanup runs.
- **Wrap raw `INSERT`/write statements in `try/finally: conn.close()`** — if
  the execute raises (e.g. `IntegrityError: NOT NULL constraint failed` on a
  column you forgot, like `quality`), the connection stays open and the file
  stays locked until the test crashes the cleanup too. The NOT NULL failure
  and the WinError 32 are the SAME bug in two symptoms.
- **Prefer a short-lived writer connection for seeding** in read-only
  projection tests: open → execute → commit → close, then let the reader
  (long-lived) pick up the committed row. Sharing the reader's transaction
  state for writes leaves the projection seeing stale or uncommitted data.

## §21 Editing test files: `patch` old_string must be UNIQUE

Hermes `patch` (mode=replace) replaces the FIRST match of `old_string` when the
string appears multiple times — it does not error on ambiguity. Test files
often contain near-identical blocks (e.g. several `html = mod._render_full(...)`
+ `assertIn(...)` pairs in a render test class). A short `old_string` copied
from one block can silently land in a DIFFERENT block, corrupting an unrelated
test's assertions while reporting "1 replacement" as success. This happened
2026-08-11: an assertion upgrade meant for the LAST render test replaced the
FIRST one instead, and the file's other tests were only discovered broken on
the next full run.

- Before patching a test file, `read_file` the target region and pick an
  `old_string` with enough surrounding context to be unique (include the test
  method name line if in doubt).
- After any patch to a test file, immediately `read_file` the changed region
  and confirm the edit landed in the intended method — do not trust the diff
  summary alone.
- If the same region must be edited twice and the first attempt drifted,
  re-read the file before the second attempt rather than re-issuing a stale
  patch.

## §22 Blind `sed -i` across a whole file when introducing a helper closure

Wrapping return values through a helper (e.g. adding a quality report via a
`_return(text, engine)` closure) and applying it with a global `sed -i
's/return X, Y/return _return(X, Y)/g'` silently rewrites EVERY matching return
in the FILE — including sibling functions where the helper is not defined. The
result compiles and local tests may pass, but the NameError surfaces in CI on
the first code path that hits the sibling function (2026-08-12: `convert_url`
was rewritten to call `_return` which only exists inside `convert_file`; the
YouTube adapter test failed with `NameError: name '_return' is not defined`).

- Scope the sed to the target function's line range (e.g. `sed -i
  '375,430s/return .../.../g'`), or better, use `patch` per call site.
- After a global rewrite, `grep -n '_return' file.py` and confirm every call
  site is inside a function where the name is defined.
- Same trap applies to renaming a parameter/variable that exists in multiple
  functions: verify scope at each replaced site.

## §23 "Pre-existing failures" can be a missing dependency group, not code/network

Before recording repeated failures as "pre-existing / network-dependent" and
moving on, verify the test command actually installs the dependencies those
tests exercise. 2026-08-12 in Cognitive-Loop-OS: three adapter tests
(`youtube-transcript-api`, `readabilipy`, `newspaper4k`) failed for weeks and
were logged as "3 pre-existing network failures". The real cause: the local
run used `uv run --only-group ci`, but CI's workflow installs BOTH `ci` and
`ci-adapters` groups (separate `uv export --only-group ...` steps). Once the
run included `--group ci --group ci-adapters`, all 3 passed — 1244 passed, 0
failed. The code was never broken.

- When a test suite needs optional extras, `--only-group X` in one tool may
  NOT match the CI install matrix. Read the workflow file's install steps and
  mirror ALL groups.
- Quick probe: `python -c "import importlib.util; print(importlib.util.find_spec('youtube_transcript_api'))"`
  before blaming network or adapter code.
- A "pre-existing failure" claim is itself evidence to audit: it hides
  environment drift until someone re-runs with the right dependency set.

### §23.1 `uv pip install` may target a DIFFERENT venv than `uv run` uses

When a session exports `UV_PROJECT_ENVIRONMENT` (to force tests into a shared
CI venv), a bare `uv pip install <pkg>` installs into the project's default
`.venv` — the package reports "installed successfully" but is invisible to
`uv run --frozen` invocations, which use the other venv. 2026-08-12
(Cognitive-Loop-OS): `rapidocr-onnxruntime` installed fine, yet
`importlib.util.find_spec("rapidocr_onnxruntime")` returned None inside the
test command, and the engine's availability probe stayed False.

- Pin the install target explicitly when the env is customized:
  `uv pip install --python "<UV_PROJECT_ENVIRONMENT>/Scripts/python.exe" <pkg>`
  (Windows layout; `bin/python` on POSIX).
- If an "installed" package is not importable in the test run, compare
  `uv pip show <pkg>` (default venv) against `sys.prefix` printed by
  `uv run ... python -c "import sys; print(sys.prefix)"` — mismatch means
  the install landed in the wrong venv, not that the import is broken.

## §24 `uv run ... pytest` → "uv trampoline failed to canonicalize script path": use `python -m pytest`

When `UV_PROJECT_ENVIRONMENT` points at an externally-relocated venv (or the
project `.venv` was deleted and uv fell back to a shared CI venv), the venv's
`Scripts/pytest.exe` is a **uv trampoline** that embeds a canonicalized script
path. Invoking it via `uv run --frozen --group ci --group ci-adapters pytest`
fails with `error: uv trampoline failed to canonicalize script path` — while
the same command with the plain Python entrypoint works fine:
`uv run --frozen ... python -m pytest`. 2026-08-13 (ArcheAxis-Knowledge-OS,
after relocating the external config root).

- `uv run python -c "import sys; print(sys.version)"` succeeding is the
  first tell that only the `pytest.exe` trampoline is broken, not the venv
  or the uv wrapper. Retrying the `pytest` form does NOT help — switch to
  `python -m pytest` and it runs.
- A single `uv trampoline failed` can be transient (a just-deleted `.venv`
  mid-rebuild); but if `python -m pytest` runs the full suite green while
  the bare `pytest` form keeps failing, the trampoline is the culprit and
  `python -m pytest` is the stable invocation for that venv.
- The same pattern applies to any console-script entrypoint that is a uv
  trampoline (`uvicorn`, `ruff`, `pytest`): `python -m <module>` bypasses
  the trampoline and is immune to its path-canonicalization assumptions.

## §25 Amended PR branch after CI already passed: force-push, then wait for a NEW green run

A PR branch that goes green in CI is not a license to touch it and merge on the
old result. If you edit ANYTHING after the green run — even a comment line, a
module docstring, a trailing newline — the pushed HEAD no longer matches what
CI verified. 2026-08-12 (#128, Cognitive-Loop-OS): the fix PR went green, then
the module's ASCII header diagram was corrected post-CI; the commit was amended
and force-pushed, and merge waited for the NEW run (a second desktop-build
cycle) to go green before `gh pr merge`.

- After a green run, any edit to the branch means: `git add` → `git commit
  --amend --no-edit` (or a new commit) → `git push origin HEAD:<branch>
  --force` → poll `gh run list --branch <branch>` for the new run → wait for
  `success` → only then merge.
- Update the PR body to mention the amend (`gh pr edit <n> --body "...amend..."`)
  so reviewers/auditors see why the head SHA changed.
- The workflow worktree must also resync after the force-push:
  `git fetch origin <branch>` + `git reset --hard origin/<branch>` before
  running `gh pr merge` from that worktree — a stale worktree at the old SHA
  merges fine but leaves your local view misleading.
- Do NOT merge on the pre-amend green run "plus a tiny comment fix" — CI gates
  (lint, manifest digest, architecture guard) can legitimately flip on a
  whitespace/doc change (e.g. `missing-final-newline`), so the new run is the
  only valid evidence.

## §26 CI test job fails at the toolchain-SETUP step → infrastructure, rerun, don't debug code

When a GitHub Actions `test` job fails at an early install step (e.g.
`astral-sh/setup-uv`, `actions/setup-python`, `actions/checkout`) while every
other job passes, the failure is runner infrastructure, not your PR.
2026-08-12: `setup-uv` failed with `##[error]Github API request failed while
getting latest release` + `self-signed certificate; if the root CA is
installed locally, try running Node.js with --use-system-ca` — the runner
could not reach the GitHub API over TLS. All 9 other jobs (incl.
desktop-build) were green; `gh run rerun --failed` passed on the retry.

- Diagnose BEFORE touching code: fetch the failing job's log even while the
  run is still in progress — `gh run view --log-failed` refuses
  ("logs will be available when it is complete") but the job-scoped API
  works immediately:
  `JOB_ID=$(gh run view <RUN> --json jobs --jq '.jobs[] | select(.name=="test (3.12)") | .databaseId')`
  then `gh api "repos/<owner>/<repo>/actions/jobs/$JOB_ID/logs"`.
- Look at WHICH step failed, not just which job: `gh run view <RUN> --json
  jobs --jq '.jobs[] | select(.name=="test") | .steps[] | select(.conclusion=="failure") | .name'`
  → "Set up uv" failing means uv never installed; no test even ran.
- `gh run rerun <RUN> --failed` is refused with "cannot be rerun; This
  workflow is already running" until EVERY job finishes — a slow
  `installer-lifecycle`/`desktop-build` job can hold the run open. Wait for
  `status == completed`, then rerun.
- This is the retry pattern, not a code fix: never open a "fix CI" PR off a
  setup-step TLS/API failure, and never mark it "flaky, ignoring" — rerun,
  confirm green, and record the infrastructure blip.

## §27 A persistent `pytest.skip("...not produced in this environment")` can mask a real stage bug

A test that silently skips every run is not harmless — it can be the ONLY
observer of a broken contract. 2026-08-12 in Cognitive-Loop-OS:
`test_pipeline_crossref_stage_is_not_verified` ran
`pipeline.run_pipeline(actions=["crossref"], auto_ingest=False)` and skipped
with `"crossref stage not produced in this environment (kb_id absent)"` for a
long time. The skip was NOT an environment limitation: the crossref stage
required `kb_id`, which is only produced by the `index` stage AND only when
`auto_ingest=True`. So offline runs silently skipped the credibility stage
forever — the skip message pointed at the environment when the real bug was a
stage depending on an artifact that an earlier stage never produced.

- Treat `pytest.skip("... not produced in this environment")` as a **bug
  report**, not a pass: find which stage produces the missing artifact and
  why it did not run, then decide whether the dependency is legitimate.
- A stage that only needs content (e.g. a credibility heuristic) should not
  depend on a sibling stage's side-effect artifact (e.g. a KB id). Decouple
  it: run whenever its real input exists; fall back to derived values
  (tag keywords) instead of requiring the sibling.
- After decoupling, the previously-skipped test runs for real and exercises
  the contract — confirm it now passes and add the count to the evidence
  (1247 passed after the fix; the skipped count dropped by 1).

## §28 `--run-network`-style flags: register options before skipif references them

A test file that gates live-API tests with
`pytest.mark.skipif("not config.getoption('--run-network', default=False)")`
will silently skip (default False) forever — AND, if the option was never
registered via `pytest_addoption`, passing it explicitly fails with
`pytest: error: unrecognized arguments: --run-network`. 2026-08-12 in
Cognitive-Loop-OS: `tests/test_evidence_connectors.py` used the flag in a
skipif for weeks before anyone tried to run it; only then did the missing
registration surface. The skipif's `default=False` masks the defect because
`getoption` does not validate the name.

- When a test module references a custom option, add the `pytest_addoption`
  hook in `conftest.py` (top-level or `tests/conftest.py`):

  ```python
  def pytest_addoption(parser: pytest.Parser) -> None:
      parser.addoption("--run-network", action="store_true", default=False,
                       help="Run live-network tests (DOI/API connector calls).")
  ```

- After registering, verify BOTH modes: default run still skips (CI behavior
  unchanged) and `--run-network` actually executes the live tests. Confirm
  the network endpoint is reachable first (`curl -o /dev/null -w "%{http_code}"`)
  so a 404/unreachable endpoint is not misread as a test regression.
- Audit all `config.getoption('--foo')` references with a grep for
  `getoption` vs registered options when adding new flags — the default
  argument makes the reference silently valid even when the option is absent.

## §29 Multi-provider aggregators: fake each provider's REAL response shape

When a module aggregates several external APIs (e.g. `shared/public_evidence.py`
queries Crossref + DataCite for a DOI, OpenAlex for text, Wikidata for an
entity), a single unified parser can silently produce all-`None` fields for
providers whose response shape differs. 2026-08-12: `_query_doi` parsed DataCite
as if it were Crossref (`{"message": ...}`), but DataCite returns
`{"data": {"attributes": ...}}` — DataCite hits always carried
`title=None, year=None, authors=None`. `_extract_year` also missed Crossref's
`issued.date-parts` and DataCite's `publicationYear`, so real Crossref years
were always `None`. The bug shipped for weeks because no test asserted the
parsed field values — only hit presence.

- When adding first coverage to an aggregator, build **one fake client per
  provider using the provider's REAL documented response shape** (Crossref
  `message`, DataCite `data.attributes`, OpenAlex `{"results": [...]}`,
  Wikidata `get_entity` → `entities`), and `monkeypatch.setattr` each connector
  class onto the module (e.g. `"shared.public_evidence.CrossrefClient"`).
- Assert **field values** (title/year/authors), not just hit count — a
  `len(hits) == 1` assertion passes on an all-`None` hit and hides the parse bug.
- Check the exact method name each connector exposes before writing the fake:
  one aggregator called `WikidataClient.get_entity(qid)` and
  `OpenAlexClient.search(text, per_page=3)` — a fake with the wrong method
  name fails loudly, which is the fake's job, but match the real signature so
  the passing test actually exercises the production call path.
- After mock tests pass, verify against real APIs (`--run-network`) with one
  known DOI per provider (Crossref: `10.1038/nature12373`; DataCite-prefixed:
  `10.5284/...`) and confirm fields parse — mocks catch logic, live calls catch
  shape drift.
- Fakes that raise on failure should raise the connector's own exception type
  (e.g. `EvidenceConnectorError`), not a bare `RuntimeError`, or the
  `except (ConnectorError, OSError)` in the module under test will not swallow
  them and the test fails on an exception the production path never surfaces.

### §29.1 Cheap zero-coverage sweep before feature work

Before extending a package, find modules with no test references in one loop:

```bash
git ls-files shared/*.py | grep -v __pycache__ | while read f; do \
  base=$(basename "$f" .py); \
  hits=$(grep -rln "$base" tests/ --include="*.py" 2>/dev/null | wc -l); \
  [ "$hits" -eq 0 ] && echo "NO-TEST: $f"; done
```

In this session it surfaced 13 zero-coverage `shared/` modules; the first one
covered (`public_evidence`) immediately exposed the silent parsing bug above —
zero coverage is the strongest predictor of a latent defect. The full campaign
(2026-08-12, #101-#116) closed all of them plus `schemas.py`/`daily_notes.py`
(15/15 `shared/*.py` modules have test coverage), surfacing one real bug per
module on average (public_evidence DataCite shape, fact_extractor be-verb,
Magika double-softmax, source_discovery/obsidian_importer temp-root trap). The
sweep is worth re-running before any feature work — a module that loses its
last test is a regression risk.

**The grep sweep only finds ZERO-reference modules — it misses core
orchestrators with only INDIRECT coverage.** After the shared/ sweep returned
clean, `shared/pipeline.py` still had no `test_pipeline.py` even though 7 test
files referenced it (`test_mfx012_legacy_credibility_isolation`,
`test_phase4_research_github`, etc.). Indirect tests exercise a pipeline as a
side effect of other contracts; they never pin the stage-composition contract
itself. Add direct tests for any core orchestrator that only appears in other
files' imports:

```bash
# find modules referenced somewhere but with no dedicated test file:
git ls-files 'shared/*.py' | while read f; do base=$(basename "$f" .py); \
  [ -f "tests/test_${base}.py" ] || echo "NO-DIRECT-TEST: $f"; done
```

The direct pipeline test file pins exactly what indirect tests leave
unasserted: full action-chain output (each stage present with the right keys,
crossref carrying `classification=legacy_heuristic` + `verified=False`),
minimal-action subsets (only requested stages emitted), guard rails
(external-source + auto_ingest raises; file source requires
`COGNITIVE_APPROVED_SOURCE_ROOTS`), and empty-input short-circuit (only
extract stage, no downstream stages). 2026-08-12: the direct tests also caught
a real defect in `scripts/batch_score_registry.category_key` — combined
category labels like `"RAG / AI Platform"` never matched the table key
`"RAG/AI Platform"` because slash/whitespace spacing was not normalized, so
combined categories silently fell back to the default score row.

### §29.2 The sweep generalizes to other packages — and to FUNCTION-level gaps

The `git ls-files shared/*.py` sweep works unchanged against `knowledge_base/`,
`app/`, and `scripts/` — but "module has some test reference" is NOT the same
as "every function in the module is covered". 2026-08-12 (#117): the
`shared/` sweep was clean, yet `search_vault` (app/workspace/vault.py:64) was
the last uncovered function — the workspace module had API-contract tests
(`test_workspace_vault_api.py`, one test asserting the read-only endpoints
happy path) that never exercised the function's error paths.

- Module-level gap check (no test file at all):
  `git ls-files '<pkg>/*.py' | while read f; do base=$(basename "$f" .py); [ -f "tests/test_${base}.py" ] || echo "NO-DIRECT-TEST: $f"; done`
- Function-level gap check (module has tests, individual public functions
  don't): enumerate the module's public API and grep tests for each name:
  `grep -n "^def " app/workspace/vault.py` then
  `grep -rln "search_vault" tests/` → empty = untested function.
- API-contract tests (FastAPI TestClient) cover the happy path through the
  router; they rarely cover function-level edge cases (empty query, missing
  dir, case-insensitivity, no-match). When a function is only exercised via
  its API, add a function-level test file for the error/edge paths — the two
  layers are complementary, not redundant.
- The error message you assert against must match the REAL raise site: the
  missing-dir case raised `ApprovedRoots`' "approved Vault root must be an
  existing directory" (match `existing directory`), NOT the caller's generic
  "not a directory" — read the exception source before writing the `match`
  string, or the first run fails on the message, not the behavior.

## §30 `testpaths` can silently exclude an entire test package — and inclusion exposes DB pollution

A package-internal test dir (`knowledge_base/tests/` in Cognitive-Loop-OS) can
hold dozens of green tests that pytest NEVER runs. 2026-08-12 (#119): the dir
had 5 files / 38 tests (cards, taskpack, context_pack, fts_rebuild,
vector_search) that `pytest knowledge_base/tests/` ran fine standalone — but
`pyproject.toml` set `testpaths = ["tests"]`, so the full suite never
collected them. That's dead coverage: tests that assert contracts but never
execute, in CI or locally.

- Sweep for it once when evaluating coverage: list every `*/tests/` dir in
  the repo and compare against `testpaths` in `pyproject.toml` /
  `pytest.ini`. A test dir existing but not collected is a silent gap the
  zero-reference grep sweep (above) does NOT catch — those tests reference
  their own modules, they just never run.
- Fix: `testpaths = ["tests", "knowledge_base/tests"]`.
- EXPECT the newly-included tests to fail under the full suite on the first
  run. Tests written in isolation assume a clean DB; once collected they share
  the real `data/*.sqlite` with `tests/`, whose tests leave rows behind. The
  symptom is order/count-sensitive: FTS-candidate tests asserting
  `object_ids == (new_doc_id,)` fail with extra IDs from other test files'
  leftovers, and it reproduces with `-p no:randomly`.
- **DB-isolation trap: copying the real DB copies the pollution.** The first
  isolation attempt copied the migrated `data/cognitive_os.sqlite` to a temp
  file and pointed `storage.DB_PATH` at it — still failed, because the copy
  already contained the leftover rows. The working pattern is a FRESH empty
  DB + the module's own schema init:

  ```python
  # knowledge_base/tests/conftest.py
  @pytest.fixture(autouse=True)
  def _isolated_db(tmp_path: Path) -> None:
      real = Path(storage.DB_PATH)
      storage.DB_PATH = tmp_path / "cognitive_os_test.sqlite"
      storage.init()          # CREATE TABLE IF NOT EXISTS incl. FTS5 virtual tables — idempotent
      yield
      storage.DB_PATH = real  # restore module default so later tests are unaffected
  ```

  This works because the schema DDL is `CREATE IF NOT EXISTS` — no migration
  chain needed for the tables the tests touch. If the module under test lacks
  an idempotent init, you need the real migration chain (or assert on
  membership instead of exact counts — see "SQLite Testing" above). After the
  fix: full suite went 1420 → 1458 (all 38 kb tests now running and green),
  0 failures.

## §31 Function-local imports change the monkeypatch target

A module that does `from shared.storage import select_one` INSIDE a function
(instead of at module top) has no `select_one` attribute on the module object —
`monkeypatch.setattr("shared.block_refs.select_one", fake)` raises
`AttributeError: module ... has no attribute 'select_one'`. 2026-08-12: first
tests for `shared/block_refs.py` hit exactly this; the fix is to patch the
import SOURCE, which is re-resolved on every call:

```python
# WRONG — AttributeError, the name exists only inside the function:
monkeypatch.setattr("shared.block_refs.select_one", fake)

# RIGHT — patch where the function-local import pulls from:
monkeypatch.setattr("shared.storage.select_one", fake)
```

- Grep for `from X import Y` inside the function body before choosing the
  patch target; function-local imports are common in lazy-import modules
  (heavy deps like torch, or storage accessors pulled only when needed).
- Same applies to `sys.modules` injection: if the module under test imports
  `torch` inside a function, `monkeypatch.setitem(sys.modules, "torch", fake)`
  works because the import re-reads `sys.modules` at call time — see the
  Silero VAD stub pattern in `ocr-asr-bakeoff`.

## §32 Module-TOP imports: patch the CONSUMING module, not the source

The mirror case of function-local imports: a name bound at module top
(`from shared.storage import select_all` in the file header) lives as an
attribute of the CONSUMING module. `monkeypatch.setattr("shared.storage.select_all", fake)`
is a **no-op** — the consuming module already holds its own reference. You
must patch `shared.diversity_audit.select_all` instead. 2026-08-12: first
tests for `shared/diversity_audit.py` silently returned 0 radar rows until
the patch target was switched from the source module to the consuming module.

- Decide per-name: `grep -n "from X import" <file>` — imports inside function
  bodies → patch `X.name`; imports at module top → patch `module.name` (the
  file's own module).
- A test that "passes" while the module under test silently uses the real
  dependency (e.g. radar returns 0 because the real `select_all` hit an empty
  DB) is the failure mode — assert on observed behavior (row count, ordering),
  not just "no exception".
- When faking a storage accessor, the fake's SIGNATURE must accept every
  argument the production call site passes, including keyword args. 2026-08-12
  (#118): `get_due_reviews` calls `select_all("kb_reviews", limit=500,
  order="created_at DESC")` while `schedule_review` calls `select_all(...)`
  bare — a fake written as `lambda table, limit: ...` raises TypeError on the
  `order=` kwarg. Write the fake as `def fake_select_all(table, limit=500,
  order=""): ...` and sort by `order` inside so due-review ordering is
  actually exercised. Grep every call site's arguments before writing the fake.

### §32.1 Module-level singleton INSTANCES: patch the attribute, and reset the init flag

A module may hold lazily-initialized module-level *instances* (not just imported
names) — e.g. `shared/graph_rag.py` creates `_embedder = SimpleTextEmbedder(...)`,
`_gdb = GraphDB(...)`, `_graph_vdb = VectorDB(...)` at import time, plus a
`_graph_initialised = False` latch consumed by `_ensure_init()`. 2026-08-12:
first tests for `shared/graph_rag.py` hit exactly this class.

```python
# WRONG — these trigger real sqlite-vec / on-disk DB init:
# (no import to patch; the instances were constructed at module import)

# RIGHT — replace the module attributes with fakes:
import shared.graph_rag as gr
monkeypatch.setattr(gr, "_gdb", _FakeGraph())
monkeypatch.setattr(gr, "_graph_vdb", _FakeVDB())
monkeypatch.setattr(gr, "_embedder", _FakeEmbedder())
monkeypatch.setattr(gr, "_graph_initialised", False)   # force lazy init path
```

- The fake only needs the surface the code path touches: `add_entity`,
  `add_relation`, `query_neighbors` for a graph; `init()`, `insert`,
  `search_by_text` for a vector DB; `embed(text)` for an embedder.
- Reset the `_*_initialised` latch too — leaving it `True` from a prior test
  skips `_ensure_init()` entirely and your fake's `init()` recording is never
  exercised (and a `True` left from the real module can call into the real DB).
- Module-level instances are a stronger form of the module-top-import case:
  there is no source module to patch, only the attribute on the consuming
  module. Grep for the module-level assignments (`grep -n "^_gdb\|^_graph_vdb"`)
  to enumerate what must be replaced.

## §33 conftest TMPDIR redirection breaks path-scanning tests (fake file tree instead)

A project conftest may redirect `TMP`/`TEMP`/`TMPDIR` into a hidden runtime
tree (Cognitive-Loop-OS does: `tests/conftest.py` sets them to
`.hermes/task-runtime/pytest-tmp`). Any module under test that scans a
directory AND skips hidden path parts — e.g. `if any(p.startswith(".") for p
in fpath.parts)` — will silently find **0 files** because every
`tempfile.TemporaryDirectory()` lands under the hidden `.hermes/` root.
2026-08-12: first tests for `shared/source_discovery.py` and
`shared/obsidian_importer.py` both hit this; direct `python -c` repro worked
while pytest returned `total_found: 0` — the first symptom that it's the temp
root, not the code.

- Don't fight the conftest: monkeypatch `Path.rglob` and `Path.exists` with a
  fake file tree rooted at a non-hidden path (`C:/tmp_test/...`). The module
  under test only touches `parts`, `suffix`, `name`, `is_file()`, `stat()`,
  `str()`, and `relative_to()` — a minimal stand-in suffices:

  ```python
  class _FakeFile:
      # Take RELATIVE paths (as the scanner would see them); the module's
      # rglob results always go through relative_to()/str() filters.
      def __init__(self, rel_path: str, size: int = 100):
          self._rel = rel_path.replace("\\", "/")   # normalize for Windows
          self._p = Path(self._rel)

      @property
      def parts(self): return self._p.parts        # MUST be relative parts!
      @property
      def suffix(self): return self._p.suffix.lower()
      @property
      def name(self): return self._p.name
      def is_file(self): return True
      def stat(self):
          class _S: st_size = self._size
          return _S()
      def __str__(self): return self._rel          # str() used for folder filters

  def _patch_rglob(monkeypatch, files):
      monkeypatch.setattr(Path, "rglob", lambda self, pat: iter(_FakeFile(f) for f in files))
      monkeypatch.setattr(Path, "exists", lambda self: True)  # root.exists() gate
  ```

- **The fake tree is only needed when the module under test FILTERS hidden
  path parts** (`if any(p.startswith(".") for p in fpath.parts)`). If the
  scanner walks the directory directly with no hidden-path skip, real
  `tempfile.TemporaryDirectory()` vaults work fine even under the redirected
  TMPDIR — 2026-08-12 (#117) `search_vault` tests used real temp vault dirs +
  a real sqlite store successfully because `ImportSession` has no hidden-path
  filter. Check the module's scan loop for a `startswith(".")` filter before
  investing in the fake-tree machinery.

- `relative_to()` and `__str__` must yield **relative** paths — the scanner
  checks `str(rel)` for folder names (`"90_模板" in str(rel)`) and
  `rel.parts[0]` for classification; a fake returning the full absolute path
  breaks both and the skip/filter counts come out wrong.
- Debugging tell: if the count is exactly 0 while a standalone script with
  `tempfile` works, print `result` — the `root` in the pytest run will point
  into the hidden runtime tree. That's the conftest, not your code.

## §34 Vendored ONNX models often ALREADY output probabilities — verify before softmax

When wrapping a vendored ONNX model (no pip dependency), do NOT assume the
raw output needs your own `softmax`. Check once: `raw.sum()` ≈ 1.0 means the
graph ends in softmax. 2026-08-12: `shared/file_detection.py` (vendored
Magika) applied `_softmax(raw[0])` to an output that was already normalized —
`markdown` at 0.889 collapsed to 0.011, every label fell under its threshold,
and **every file detected as `unknown`** with near-identical ~0.01 confidence.
The model was never broken; the wrapper flattened it.

- Probe the raw output before trusting a wrapper: `raw[0].sum()`, then
  `np.sort(raw[0])[-5:]` — sum≈1 with a clear max means skip your softmax.
- Constant low confidence across ALL inputs (~1/num_labels + noise) is the
  double-softmax fingerprint.
- Padding semantics: the wrapper padded short content with `b"\x00"` via
  `bytes.ljust`, but the model's config specified `padding_token: 256` — 0 is
  not a valid token and corrupted features. Mirror the upstream feature
  extraction exactly (`beg_ints = list(beg_raw[:beg_size]); if short: += [padding] * n`),
  never invent your own fill value. Assert on padding in tests
  (`(features[0] == 256).all()` for empty input).
- A fix that makes content detection ACCURATE can expose latent downstream
  mapping bugs: once Magika correctly labeled JSON Canvas files as `json`,
  the `json -> generic text` format map silently demoted `.canvas` files to
  passthrough and an existing test failed (`engine == "json-canvas"`).
  Content-type maps need an extension fallback for JSON-like labels so
  `.canvas`/`.ipynb`/`.geojson` keep their dedicated handlers. Run the full
  suite after any detection fix, not just the detector's own tests.

## §35 Windows: user-owned WIP fixtures get their line endings normalized by tests

On Windows, a test that opens a fixture with default text mode (or any
toolchain touching it) can silently normalize a user-owned WIP fixture's line
endings, making `git status` show it modified with a trivial CRLF/LF diff.
2026-08-12: `tests/fixtures/readability_article.html` (user WIP, twice
restored from `origin/main`) kept re-dirtying after test runs.

- Before committing, `git status --short` and `git checkout -- <user-fixture>`
  to restore the user's copy; never `git add .`.
- When a fixture keeps re-dirtying with only line-ending changes, check for
  `git diff --ignore-space-at-eol` to confirm it is normalization noise, not
  a real edit.

## §36 Windows: convention-gate CRLF findings can be checkout artifacts, not real issues

A repository convention checker that scans WORKING-TREE files (e.g.
Cognitive-Loop-OS `scripts/check_repository_conventions.py` run bare) will
flag CRLF on every text file on Windows — but the git BLOB may be pure LF.
`core.autocrlf=true` converts LF→CRLF on checkout and CRLF→LF on commit, so
the working tree carries CRLF that never reaches the repository. 2026-08-12:
the gate reported 5 test files as `crlf: only Windows command files may use
CRLF`, yet `git show HEAD:<file> | od -c` showed no `\r` — and CI's gate step
passes because it runs with `--source head` (checks the BLOB, not the tree).

- Verify before "fixing": `git show HEAD:<file>` and inspect for `\r` — LF
  in the blob means the finding is local-only noise.
- Check how CI invokes the gate (`.github/workflows/*.yml`: often
  `--source head`); if CI checks the blob, the local bare-run findings are
  false positives — do NOT open a CRLF-normalization PR (it will be
  "nothing to commit" anyway, since git stores LF).
- When the local run of a gate disagrees with CI's verdict on the SAME
  commit, suspect working-tree vs blob divergence before suspecting the
  committed content.

## §37 Class/enum identity breaks across `spec_from_file_location` module copies

Services loaded with `importlib.util.spec_from_file_location` (no package
`__init__.py`) re-execute on every load, so the SAME `.py` can hold TWO
distinct class objects — the provider's copy and the caller's/test's copy.
`isinstance`/`assertIs`/enum-identity checks compare object identity, so a
record built from one copy is "not an instance" of the class in the other.
2026-09 (WORK-LAB memory/security/knowledge gates): two cost test bugs.

- **`isinstance(record, MemoryRecord)` fails on the right shape** because the
  record came from a different module copy than the one `isinstance` names.
  Fix: duck-type — check the required attribute/shape, reject only raw-session
  payloads — instead of the class.
- **Enum / `assertIs(kind, MemoryKind.KNOWLEDGE)` fails on the object, not the
  value.** Across copies `K` is a different `Enum` member. Compare `.value`
  (`assertEqual(kind.value, "knowledge")`), never `is`/`isinstance`.
- **Reach for module-local constants, not cross-module class introspection.**
  `ExtensionType._MEMBERS`-style reads from a re-loaded copy can miss or break;
  mirror the data locally or read it duck-typed so a second load cannot defeat
  the gate.
- **Ordering interaction:** when a gate checks BOTH "is this a raw-session
  payload" and "does this have the record shape", run the raw-session detection
  FIRST — a `Mapping`/`list` has no `record_id`, so the shape check would hit
  first and make the raw-session branch unreachable.

Rule: at any spec-loaded service boundary, write cross-object checks as shape /
value tests, not identity tests; if a gate does `isinstance` on a loaded module's
class, prove the check still holds when the module is loaded twice. New service
modules must be self-contained (no `from services.x.y import …` absolute imports,
which NameError under spec loading) — use duck typing + local constants instead.
