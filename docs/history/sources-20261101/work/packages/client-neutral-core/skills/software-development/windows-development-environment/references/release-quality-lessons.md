# Release Quality Lessons (validated 2026-08-30)

## Critical: Test the actual user-facing artifact

CI tests passing does NOT mean the exe works. For Tauri apps:
- `cargo build --release` does NOT embed frontend resources
- Only `cargo tauri build` embeds the frontend from `frontendDist`
- The exe will show `about:blank` in the WebView if frontend isn't embedded

**Always launch the built exe and verify the WebView shows the UI.**

For green/portable distributions:
- Verify the exe starts correctly with the data directory
- Check that the backend Python process starts and listens on a port
- Verify `workspace_root` points to the correct directory (not AppData)

## Version bump cascade from release script bugs

Before creating an immutable tag:
1. Run ALL verification scripts locally (NSIS lifecycle, zip distribution, wheel smoke)
2. A single bug forces a new version number (tags are protected)
3. v0.6.12 → v0.6.13 → v0.6.14 cascade from two script bugs:
   - `verify_zip_distributions.ps1` expected `/workspace` 200 (should be 410)
   - PowerShell 7 `Invoke-WebRequest` throws `HttpResponseException` not `WebException`

## Green version deployment sequence

1. Extract Green distribution
2. Create `data/` directory
3. Create empty SQLite database: `sqlite3 data/archeaxis.sqlite ""`
4. Apply migrations using bundled Python (not project Python)
5. Set `ARCHEAXIS_PORTABLE_ROOT` env var when launching exe
6. Verify backend starts and `workspace_root` is correct

## Migration API (correct usage)

```python
import os
os.environ["ARCHEAXIS_DATA_DIR"] = "/path/to/data"
from shared.migration_runner import MigrationOperator, default_registry
from pathlib import Path

db = Path("/path/to/data/archeaxis.sqlite")
db.touch()  # Must exist before MigrationOperator
operator = MigrationOperator(db_path=db, backup_dir=db.parent / "backups")
for owner in default_registry(db).owners:
    try:
        operator.apply(owner.owner)
    except Exception:
        pass  # vector indexes may skip
```

**NOT** `MigrationRunner` or `run_pending` — those don't exist in the API.
