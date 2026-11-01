# Lifecycle UI E2E Evidence Pattern (Playwright + Real Server)

Use this reference when you need to write a real-browser E2E test that proves a workspace API projection is wired to the UI — lifecycle evidence, status projections, aggregate state cards. The pattern is: seed real database data, start the real server, use Playwright to read back the DOM, and assert both aggregate state and desensitization.

## Procedure

### 1. Choose a data root

Use the project's ignored runtime directory so cleanup doesn't fight subprocess file locks:

```python
runtime_root = project_root / ".hermes" / "task-runtime" / "tmp" / "e2e-test"
data_dir = runtime_root
```

On Windows, set `COGNITIVE_DATA_DIR` in `os.environ` so all subprocesses (migrate, uvicorn) use the same path:

```python
os.environ["COGNITIVE_DATA_DIR"] = str(data_dir.resolve())
```

### 2. Run migration first

Always migrate before seeding. The real schema has NOT NULL columns, CHECK constraints, and UUID PKs:

```python
subprocess.run(
    [sys.executable, "-m", "app.runtime_entrypoint", "migrate"],
    capture_output=True, check=True, cwd=project_root,
)
```

### 3. Seed data against the migrated schema

Use `uuid.uuid4()` for primary keys. Insert directly into the tables the API reads from. Here is the pattern for lifecycle evidence tables (the exact column set depends on the project's migration):

```python
# execution_traces: id, task_id, events_json, result_json, success, created_at
connection.execute(
    "INSERT INTO execution_traces(id, task_id, events_json, result_json, success, created_at) "
    "VALUES (?, ?, ?, ?, ?, ?)",
    (str(uuid4()), "task-1", json.dumps([...]), "{}", 0, now),
)

# evaluation_candidates_v1: id, trace_id, evaluation_json, status, reviewer_id, rationale, reviewed_at
connection.execute(
    "INSERT INTO evaluation_candidates_v1(id, trace_id, evaluation_json, status) "
    "VALUES (?, ?, ?, 'candidate')",
    (str(uuid4()), str(uuid4()), json.dumps({"score": 0.6})),
)

# machine_lessons: id, pattern, lesson_type, future_constraint, evidence_trace_id, created_at
connection.execute(
    "INSERT INTO machine_lessons(id, pattern, lesson_type, future_constraint, evidence_trace_id, created_at) "
    "VALUES (?, ?, 'failure', ?, ?, ?)",
    (str(uuid4()), "blocked_access", "description", str(uuid4()), now),
)
```

### 4. Start server + browser

Use the project's `running_core()` context manager (from `runtime_http_smoke.py`). It starts uvicorn on a random loopback port and terminates cleanly on exit:

```python
from runtime_http_smoke import running_core
from playwright.sync_api import sync_playwright

with running_core() as base_url, sync_playwright() as playwright:
    browser = playwright.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1440, "height": 1000})
    # test body here
    browser.close()
```

### 5. Verify with Playwright

Navigate to the evidence/lifecycle page, wait for the UI to load from the real API, then assert DOM text:

```python
page.goto(f"{base_url}/workspace#evidence", wait_until="networkidle")
page.get_by_role("heading", name="证据中心·生命周期").wait_for()

permission_text = page.locator("#lifecycle-permission").inner_text()
assert "blocked" in permission_text
assert "2" in permission_text  # 2 permission gates

# Full-page desensitization check
page_text = page.locator("main").inner_text()
assert "lesson-internal-id" not in page_text
import re
uuid_pattern = r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
assert not re.findall(uuid_pattern, page_text)
```

### 6. Clean up

After `running_core()` exits, the server process is dead. Clean the runtime data:

```python
import shutil
shutil.rmtree(data_dir, ignore_errors=True)
```

## Key pitfalls

- **Migrate before seed.** Without migration the schema is empty; CREATE TABLE IF NOT EXISTS produces a narrower incompatible schema.
- **Subprocess DB lock on Windows.** `tempfile.TemporaryDirectory` cleanup fails when the server subprocess still holds a SQLite handle. Use project-local `.hermes/task-runtime/` and manual cleanup.
- **`COGNITIVE_DATA_DIR` must be in `os.environ`.** The `running_core()` subprocess copies `os.environ`. A local variable won't propagate.
- **Use the project venv's Python.** Global/system Python lacks project dependencies (playwright, app modules).
- **Assert desensitization independently.** An ID in the page is a regression even if aggregate counts are correct.
- **Collect console and page errors.** Without `page.on("console")` / `page.on("pageerror")`, silent JS failures hide defects.
