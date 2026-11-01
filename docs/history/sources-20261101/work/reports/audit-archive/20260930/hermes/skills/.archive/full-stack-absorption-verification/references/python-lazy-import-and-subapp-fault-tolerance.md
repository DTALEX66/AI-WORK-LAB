# Python Lazy Import & Sub-App Fault Tolerance

Patterns for keeping a Python/FastAPI project testable when heavy transitive dependencies (numpy, torch, etc.) are optional or not yet installed.

## Problem

A workspace/service module imports `app.facades.research` at module level, which chains through `knowledge_base.search.vector_search` → `app.memory.vector_db` → `import numpy`. If numpy is not installed, the **entire** module (including unrelated delivery functions) cannot be imported. This blocks CI, isolated tests, and partial deployments.

The same pattern applies to `app.main` mounting sub-applications via module-level imports:

```python
# ❌ Brittle — a single missing dep in ANY sub-app blocks Core startup
from inspiration_research.api import app as research_app
from knowledge_base.api import app as kb_app
```

## Fix 1: Lazy Service Imports

Replace module-level heavy imports with a lazy-loading function inside the module:

```python
# At module top — replace heavy imports with a lazy loader
_HEAVY_IMPORTED = None

def _import_heavy() -> None:
    \"\"\"Lazy-import heavy research/knowledge/ingestion dependencies.\"\"\"
    global _HEAVY_IMPORTED
    if _HEAVY_IMPORTED is not None:
        return
    from app.facades.research import research_github_repository
    from app.ingestion.multi_format import convert_file, convert_url, detect_format
    from app.knowledge.closed_loop import (
        approve_learning_artifact, audit_closed_loop,
        record_practice_evidence, start_and_approve_learning_candidate,
    )
    from app.research.document import persist_workspace_document
    from shared.research_store import ResearchPackageGraph, load_research_package
    _HEAVY_IMPORTED = {
        "research_github_repository": research_github_repository,
        "convert_file": convert_file,
        "convert_url": convert_url,
        "detect_format": detect_format,
        "persist_workspace_document": persist_workspace_document,
        "ResearchPackageGraph": ResearchPackageGraph,
        "load_research_package": load_research_package,
    }
```

Then at the top of each function that needs heavy deps:

```python
def intake_url(*, url: str, db_path: str | Path, fetcher=None) -> dict:
    _import_heavy()
    research_github_repository = _HEAVY_IMPORTED["research_github_repository"]
    convert_url = _HEAVY_IMPORTED["convert_url"]
    persist_workspace_document = _HEAVY_IMPORTED["persist_workspace_document"]
    # ... rest of function
```

Delivery/test functions (`workspace_delivery`, `workspace_jobs`, `dispatch_delivery_once`, `workspace_status`) that only use `sqlite3` remain importable without triggering the heavy chain.

## Fix 2: Fault-Tolerant Sub-App Mounts

Replace module-level sub-app imports with guarded try/except:

```python
# In app.main.py
from app.workspace.router import router as workspace_router  # lightweight, always works

_research_app = None
_kb_app = None
try:
    from inspiration_research.api import app as research_app
    _research_app = research_app
except ImportError:
    pass
try:
    from knowledge_base.api import app as kb_app
    _kb_app = kb_app
except ImportError:
    pass

if _research_app is not None:
    app.mount("/internal/research", _research_app)
if _kb_app is not None:
    app.mount("/kb", _kb_app)
app.include_router(workspace_router)
```

## Verification

After applying either fix, verify the import works without the heavy dependency:

```bash
# Should succeed — delivery path functions import without numpy
python -c "from app.workspace.service import workspace_delivery; print('OK:', workspace_delivery.__name__)"

# Core app should start even when sub-apps unavailable
COGNITIVE_DATA_DIR=/tmp/test-data python -c "from app.main import app; print('APP OK')"
```

## Pitfalls

- **Forgotten functions** — when adding `_import_heavy()` to new functions that use the heavy deps, it's easy to miss one. Run the full test suite after the refactor to catch undeclared references.
- **Dict keys must match** — the `_HEAVY_IMPORTED` dict keys must match the exact variable names used in the function bodies. A typo produces a `KeyError` at runtime.
- **Performance** — the first call to `_import_heavy()` blocks on importing heavy modules. This is acceptable since the heavy path is inherently slower (file conversion, research analysis). The dict cache ensures it happens only once.
- **Type annotations** — remove type annotations that reference the heavy imports in function signatures of non-heavy functions. E.g., change `graph: ResearchPackageGraph` to just `graph`.
