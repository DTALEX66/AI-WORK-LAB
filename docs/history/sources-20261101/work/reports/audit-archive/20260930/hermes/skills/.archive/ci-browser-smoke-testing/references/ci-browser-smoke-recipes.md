# CI Browser Smoke — debugging recipes

Concrete recipes validated on ArcheAxis-Knowledge-OS (2026-08-14/15). Adjust
paths/groups to the repo you're working in.

## 1. Architecture-guard whitelist entry for the sys.path anchor

`scripts/check_architecture.py` refuses new sys.path mutations unless they
appear in `_GRANDFATHERED_SYS_PATH_CALLS` as exact tuples:

```python
_GRANDFATHERED_SYS_PATH_CALLS = {
    ("scripts/sleep_loop_worker.py", 18, "sys.path.insert(0, str(PROJECT_ROOT))"),
    (
        "scripts/a0_browser_smoke.py",
        14,
        "sys.path.insert(0, str(Path(__file__).resolve().parents[1]))",
    ),
}
```

- The line number must match exactly; it drifts if you edit the file above
  the call — re-check after any edit (lint fails with a message about a new
  sys.path mutation).
- Repo convention: the guard checks git HEAD, not the working tree — commit
  before verifying (`check_repository_conventions.py --source head`).

## 2. pytest_sessionfinish hook that surfaces failures in CI annotations

`tests/conftest.py` (works for any repo that can't read CI step logs):

```python
import pytest

def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    """Surface failing test ids as workflow annotations on CI (log-less)."""
    failed = [r.nodeid for r in session.items if r.nodeid in session.stash.get(pytest.StashKey(set()), set())]
    ...
```

Simpler variant (no stash bookkeeping — annotate on the fly):

```python
def pytest_runtest_makereport(item, call):
    if call.when == "call" and call.excinfo is not None:
        print(f"::error::PYTEST-FAILED {item.nodeid}")
        print(f"::error::PYTEST-FAIL-REASON {call.excinfo.value}")
```

- GitHub Actions prints `::error::` lines from step stdout into the check-run
  annotations, visible via the checks API (`GET .../check-runs/<id>/annotations`)
  even when the raw log endpoint 403s for non-admins.
- Keep the reason on ONE line; multi-line reasons get mangled.

## 3. CI-SIM: reproduce the CI environment locally

CI runs `python scripts/a0_browser_smoke.py` with a system python + only the
job's dependency groups exported (no project package installed):

```bash
# 1. export the job's locked groups into a requirements file
env -u PYTHONPATH uv export --frozen --only-group ci --only-group browser \
    --output-file .hermes/task-runtime/ci-sim-reqs.txt
#    (Windows pip cannot read `-r -` from stdin — always use --output-file)

# 2. create a CLEAN venv (no project package!) and install
python -m venv .hermes/task-runtime/ci-sim-venv
.hermes/task-runtime/ci-sim-venv/Scripts/python -m pip install -r .hermes/task-runtime/ci-sim-reqs.txt

# 3. run the script exactly like CI, from the repo root
cd <repo-root> && .hermes/task-runtime/ci-sim-venv/Scripts/python scripts/a0_browser_smoke.py
```

- If a local import fails with `ModuleNotFoundError: No module named 'app'`
  in this venv, you've reproduced the CI failure — the script needs the
  repo-root sys.path anchor (section 1).
- Local chromium binaries may be cached inside the project by a wrapper:
  run `playwright install chromium` and `playwright install chromium-headless-shell`
  once (through the proxy if configured) so both browser variants exist.
- Iterate in CI-SIM until green, then push once.

**Version-matrix simulation (py-compat jobs).** To prove a job that runs
under another Python version (e.g. nightly's 3.13 lane), simulate it with uv:

```bash
env -u PYTHONPATH uv export --frozen --only-group ci \
    --output-file .hermes/task-runtime/req-ci-313.txt
env -u PYTHONPATH uv run --python 3.13 --with-requirements \
    .hermes/task-runtime/req-ci-313.txt python -m compileall -q app shared knowledge_base scripts
env -u PYTHONPATH uv run --python 3.13 --with-requirements \
    .hermes/task-runtime/req-ci-313.txt python -m pytest tests/test_imported_modules.py -q --tb=short
```

- WARNING: `uv run --python <other>` REBUILDS the project `.venv` (deletes
  and recreates it with that interpreter + only the supplied groups).
  Restore the standard environment afterwards with `uv sync --frozen` and
  re-run one quick test to confirm (`uv run --frozen --group ci --group
  ci-adapters pytest tests/test_imported_modules.py -q`). A later "suddenly
  missing pytest / different interpreter" failure is usually this.
- The target version is the risky lane: if the repo targets py311, the 3.13
  lane is the one to simulate (3.11 is covered by `target-version`).

## 4. Gate-trigger mapping (browser-smoke)

- `.worklab/project-validation.v1.yaml` maps path globs → gate sets, e.g.
  `app/workspace/ui/**` → `gates: [static, lint, browser-smoke]`.
- `scripts/ci/classify.py` reads that profile (`PROFILE_PATH`) and emits the
  GatePlan; the browser-smoke job is skipped unless the plan includes it.
- Only changes under the mapped paths retrigger browser-smoke. Script-only
  fixes don't: append a harmless comment change to a mapped UI file
  (e.g. `app/workspace/ui/assets/app.js`) to force a run.
- `CI_FORCE_FULL` (repo variable) requires a PAT → unavailable. 
  `full-qualification` is a logical RC-stage profile (AXC-060) — never the
  unknown-path fallback; do not force it in dev.
- Job-level `skipped` is LEGITIMATE when the classifier correctly omits
  unrelated lanes (e.g. desktop-build skipped on a Python-only change).

## 5. PDF-reader exercise skeleton (real-browser regression)

```python
import pymupdf  # not fitz (deprecated alias)

def _make_two_page_pdf(path):
    doc = pymupdf.open()
    for text in ("Evidence Anchoring", "Reproducible Recall"):
        page = doc.new_page()
        page.insert_text((72, 72), text, fontsize=16)
    doc.save(path)
    doc.close()
```

Flow: store the PDF bytes in the serving root (`<data_dir>/data/pdf`),
open the Evidence page, enter the key, then:

1. assert the viewer renders (canvas + text layer present);
2. paginate (`pdf-next`/`pdf-prev`) and assert page label changes;
3. zoom in/out and assert scale changes;
4. search: type a term, submit, and **wait for the dialog event**
   (`page.expect_event("dialog")`) instead of polling — the async search
   loop fires `alert()` AFTER re-rendering the page, and a select performed
   before that gets wiped by the layer rebuild (real race found in AXW-022B);
5. select text (needs the text layer — canvas-only PDFs make the annotate
   button permanently disabled; that WAS the bug), press annotate, assert an
   `ev_...` anchor is created and "jump back" lands on the right page with
   `{page, selection}` echoed.

Idempotency: delete/recreate the smoke data dir at startup, or a stale DB
from a previous run poisons later sections ("persisted bindings are
invalid").

## 6. Console-noise invariants (full Chromium vs headless-shell)

Local runs often use `chromium-headless-shell`; CI installs full `chromium`.
Console noise differs (favicon 404s, devtools messages appear only in one).
Instead of asserting `all(msg matches expected)`:

```python
errors = [m.text for m in page.on("console") captured...]
assert any("ERR_CONNECTION_FAILED" in t for t in errors), errors
```

Assert the invariant you actually care about ("a real failure surfaced"),
not the absence of noise.

## 7. Keyboard/a11y regression (Playwright)

```python
# semantic audit assertions
assert page.evaluate("""() => [...document.querySelectorAll('input')]
    .filter(el => !(el.getAttribute('aria-label') || (el.labels && el.labels.length)))
    .length""") == 0
# theme buttons: aria-label + aria-pressed
# all buttons: explicit type attribute

# keyboard flow: focus trigger → Enter opens dialog
trigger.focus(); page.keyboard.press("Enter")
dialog = page.get_by_role("dialog", name="导入资料"); dialog.wait_for()
assert page.evaluate("document.activeElement?.id") == "intake-url"
page.keyboard.press("Tab"); page.keyboard.press("Shift+Tab")
assert page.evaluate("document.activeElement?.id") == "intake-url"  # trap holds
page.keyboard.press("Escape")
dialog.wait_for(state="hidden")
assert page.evaluate("document.activeElement?.dataset.action") == "intake"  # focus returns
```

- A11y gaps found in a real audit (AXW-096B): inputs without `aria-label`,
  theme swatches without `aria-pressed`, buttons without explicit `type`,
  no `role="alert"` on error regions. Fix the HTML, then lock with the
  browser test.

**PDF reader keyboard flow** (extend the PDF exercise after the annotate
step; the PDF is loaded, on page 2, text layer rendered):

```python
# prev: focus + Enter flips back a page (proves the control is keyboard-usable)
page.locator("#pdf-prev").focus()
page.keyboard.press("Enter")
page.wait_for_function("() => document.querySelector('#pdf-page-info')?.textContent.startsWith('1 /')")

# zoom: buttons often have NO id — locate by data-action
zoom_before = page.evaluate("document.querySelector('#pdf-zoom-info')?.textContent")
page.locator('button[data-action="pdf-zoom-out"]').focus()
page.keyboard.press("Enter")
page.wait_for_function(f"() => document.querySelector('#pdf-zoom-info')?.textContent !== {zoom_before!r}")

# search via Tab chain: fill() CLEARS the prior value — keyboard.type appends!
page.locator("#pdf-search-input").fill("")          # required: type() would append
page.locator("#pdf-search-input").focus()
page.keyboard.type("Reproducible")
page.keyboard.press("Tab")                          # input -> 搜索 button
page.keyboard.press("Enter")
# no DOM highlight exists (searchPdf jumps pages + alerts) — assert the JUMP:
page.wait_for_function("() => document.querySelector('#pdf-page-info')?.textContent.startsWith('2 /')")
```

Diagnostics: when a wait times out, read `document.activeElement`
(data-action || id || tagName) and the input's `value` in the failure
state-dump. That instantly distinguishes "focus never landed on the button"
from "the value is double-entered so the query can't match".
