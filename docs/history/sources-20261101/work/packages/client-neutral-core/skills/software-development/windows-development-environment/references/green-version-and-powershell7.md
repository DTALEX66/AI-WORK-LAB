# Green Version Deployment & PowerShell 7 Issues

Companion reference for `windows-development-environment`. Covers green (no-install) Tauri app deployment and PowerShell 7 exception handling.

---

## Green version portable.flag deployment (validated 2026-08-30)

When deploying a green (no-install) version of a Tauri app on Windows, the exe checks for `portable.flag` beside the executable to determine the data directory. Without it, the exe falls back to `AppData/Local` as the data root.

**Root cause of startup failure**: No `portable.flag` → exe uses AppData → no migrations applied → Python backend fails with "SQLite schema has not been migrated" or "runtime data root is not configured; set ARCHEAXIS_DATA_DIR".

**Fix sequence**:
1. Create `portable.flag` beside the exe (empty file is sufficient)
2. Create `data/` directory (exe uses `<exe_dir>/data/` when portable.flag present)
3. Apply ALL migrations using the bundled Python (not the project's Python — different version)
4. Restart the exe

**Critical**: Use the green version's own Python for migrations. The project's Python 3.13 cannot load numpy compiled for 3.12:
```bash
# WRONG: uses project Python 3.13
python -c "from shared.migration_runner import MigrationOperator; ..."

# RIGHT: uses green version's bundled Python 3.12
"D:/path/to/green/runtime/python/python.exe" apply_migrations.py
```

Migration script (run with green version's Python):
```python
import os
os.environ["ARCHEAXIS_DATA_DIR"] = "D:/path/to/green/data"
from shared.migration_runner import MigrationOperator, default_registry
from pathlib import Path
db = Path("D:/path/to/green/data/archeaxis.sqlite")
db.touch()
operator = MigrationOperator(db_path=db, backup_dir=db.parent / "backups")
for owner in default_registry(db).owners:
    try:
        operator.apply(owner.owner)
    except Exception:
        pass  # vector indexes may skip if numpy unavailable
```

## PowerShell 7 Invoke-WebRequest exception type (validated 2026-08-30)

PowerShell 7 throws `HttpResponseException` (not `System.Net.WebException`) for non-2xx responses from `Invoke-WebRequest -ErrorAction Stop`. A `catch [System.Net.WebException]` clause will NOT catch the 410/404/500 response — the exception escapes and the script fails.

**Symptom**: Release workflow fails at "Verify Green and Portable lifecycle" step. The script uses `catch [System.Net.WebException]` but PowerShell 7 throws a different exception type.

**Fix**: Use bare `catch` (no type filter):
```powershell
$statusCode = 0
try {
    $response = Invoke-WebRequest "$base/workspace" -UseBasicParsing -ErrorAction Stop
    $statusCode = [int]$response.StatusCode
} catch {
    # PowerShell 7+ throws HttpResponseException (not WebException) for
    # non-2xx responses from Invoke-WebRequest -ErrorAction Stop.
    $resp = $_.Exception.Response
    if ($resp -and $resp.StatusCode) {
        $statusCode = [int]$resp.StatusCode
    }
}
```

The NSIS lifecycle script (`verify_nsis_install.ps1`) already uses bare `catch`. The zip distribution script (`verify_zip_distributions.ps1`) needed the same fix — validated on v0.6.12/v0.6.13 release failures.

## Suspected file-sync race on the project drive (observed 2026-08-30, cause unverified)

Files on `D:\All projects` (BaiduSyncdisk sync directory) can be modified by the sync engine between read and write operations. This causes vault write_file to report "expected-hash mismatch" even when no user edit occurred.

**Suspected cause (unverified)**: a background file-sync client appears to touch files shortly after they are created. This was not isolated experimentally, so no drive or path can be concluded safe from it. The vault's `write_file` reads bytes → computes hash → compares with expected hash. If the sync engine modified the file between the read and the comparison, the hash mismatches.

**Fix**: use the project-approved temporary root (`.project-local/runs/tmp`) for tests that need write-then-read consistency, so the data stays inside the project write boundary, and re-verify the hash after the write instead of assuming the file is stable.

**Detection**: a repeated "expected-hash mismatch" on a file this tool has just written is a hash-instability symptom. Treat the environmental explanation as an unverified hypothesis and do not conclude which drives or paths are affected.
