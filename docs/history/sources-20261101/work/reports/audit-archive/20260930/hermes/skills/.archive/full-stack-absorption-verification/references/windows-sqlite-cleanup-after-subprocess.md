# Windows SQLite Cleanup After Subprocess Kill

When running FastAPI/uvicorn integration tests on Windows, `shutil.rmtree` on the data directory frequently fails after killing the server process. The error is `PermissionError: [WinError 32] 另一个程序正在使用此文件` on the SQLite file.

## Root Cause

Windows holds file locks on SQLite databases even after the owning process has been killed. The OS takes 1–3 seconds to fully release the locks. `shutil.rmtree` retries immediately and fails.

## Fix: Graceful Cleanup

### Pattern 1: Best-effort per-file unlink

```python
import time
from pathlib import Path

def cleanup_best_effort(path: Path):
    \"\"\"Remove a directory tree, ignoring locked-file errors on Windows.\"\"\"
    if not path.exists():
        return
    # Wait for OS to release SQLite locks
    time.sleep(1.5)
    # Unlink files first (catch PermissionError for locked ones)
    for p in path.rglob("*"):
        if p.is_file():
            try:
                p.unlink(missing_ok=True)
            except PermissionError:
                pass
    # Then rmdir from deepest first
    for p in sorted(path.rglob("*"), key=lambda x: len(str(x)), reverse=True):
        try:
            p.rmdir()
        except (PermissionError, OSError):
            pass
    try:
        path.rmdir()
    except (PermissionError, OSError):
        pass
```

### Pattern 2: Suppress rmtree failure

If you must use `shutil.rmtree` directly, wrap it with `ignore_errors=True`:

```python
shutil.rmtree(TASK_RUNTIME, ignore_errors=True)
```

This is simpler but may leave residual locked files behind. Acceptable for CI/temp directories that get cleaned at next run.

## Critical Rule

**Never let a cleanup failure override a green test matrix.** Always report the matrix first, then clean up. Structure the test flow as:

```python
try:
    # ... main test logic recording RECORDS ...
except:
    pass  # capture exception but keep going
finally:
    # Stop server
    proc and proc.kill()
    proc and proc.wait()

# Report matrix from RECORDS (always runs)
print(matrix_report(RECORDS))

# Cleanup (best-effort, after report)
cleanup_best_effort(TASK_RUNTIME)

sys.exit(0 if all_matrix_states_ok else 1)
```

## Verification

After cleanup, verify the runtime directory is gone (or only locked files remain):

```bash
ls -la .hermes/task-runtime/m001-lifecycle-smoke/   # should be empty or gone
```
