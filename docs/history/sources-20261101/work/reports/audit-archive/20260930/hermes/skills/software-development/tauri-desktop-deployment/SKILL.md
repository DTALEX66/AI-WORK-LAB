---
name: tauri-desktop-deployment
description: "Tauri desktop build and portable deployment."
---

# Tauri Desktop Deployment

## Critical Pitfalls

### 1. `frontendDist` is baked into the exe at build time

Tauri's `frontendDist` in `tauri.conf.json` is **NOT** a runtime path — it's a build-time source that gets embedded into the exe's resources.

```json
// tauri.conf.json
"frontendDist": "../bootstrap"  // ← relative to desktop/src-tauri/, NOT the exe
```

**Consequence**: Copying files to the green version's `bootstrap/` directory does NOTHING. The frontend is already inside the exe. To update the frontend:
1. Copy new frontend to `desktop/bootstrap/` (the build-time source)
2. Rebuild the exe: `cargo build --release`
3. Copy new exe to green version directory

**Common symptom**: Blank white window with title bar only. The WebView loads but has no content.

### 2. `portable.flag` detection is NOT automatic in Tauri exe

The Tauri exe's `lib.rs` only checks **environment variables** for portable root:
- `ARCHEAXIS_PORTABLE_ROOT`
- `COGNITIVE_PORTABLE_ROOT`

It does **NOT** call `portable_root_from_marker()` which checks for `portable.flag`. This function exists but is only used by the standalone Python launcher.

**Fix**: Add `portable.flag` detection to `lib.rs` setup code:
```rust
let portable_root = std::env::var_os("ARCHEAXIS_PORTABLE_ROOT")
    .or_else(|| std::env::var_os("COGNITIVE_PORTABLE_ROOT"))
    .map(PathBuf::from)
    .or_else(|| {
        // Check for portable.flag beside the exe
        let exe = std::env::current_exe().ok()?;
        let distribution_root = exe.parent()?;
        distribution_root
            .join("portable.flag")
            .is_file()
            .then(|| distribution_root.join("data"))
    });
```

### 3. Database lock files block exe restart

When the exe crashes or is killed, lock files remain in the data directory:
- `.archeaxis.sqlite.runtime.lock`
- `.archeaxis.sqlite.*.lockdb/`

These block the next exe launch with `PermissionError: [Errno 13] Permission denied`.

**Fix**: Before restarting the exe:
```bash
rm -f data/.archeaxis.sqlite.runtime.lock
rm -rf data/.archeaxis.sqlite.*.lockdb
```

### 4. Exe uses random ports, not fixed 8000

The Tauri exe assigns a random port for the backend. Don't assume port 8000.

**Find the port**: `netstat -ano | grep LISTENING | grep <python_pid>`

### 5. PowerShell 7 exception types differ from PowerShell 5

`Invoke-WebRequest` in PowerShell 7 throws `[Microsoft.PowerShell.Commands.HttpResponseException]` for HTTP errors, NOT `[System.Net.WebException]`.

**Wrong** (fails silently in PS7):
```powershell
try { Invoke-WebRequest ... -ErrorAction Stop }
catch [System.Net.WebException] { ... }  # ← never catches in PS7
```

**Correct**:
```powershell
try { Invoke-WebRequest ... -ErrorAction Stop }
catch { ... }  # ← bare catch catches all exception types
```

### 6. GitHub tags are protected — cannot update after push

Once a tag is pushed to GitHub with branch protection rules, it cannot be deleted or force-updated. If a release verification fails after tagging, you MUST bump to a new version number.

**Lesson**: Run ALL verification scripts locally BEFORE tagging.

## Green Version Deployment Checklist

1. Create `portable.flag` in exe directory
2. Create `data/` directory
3. Apply all migrations using the green version's own Python (not project venv)
4. Copy frontend to `desktop/bootstrap/` (build-time source)
5. Rebuild exe with `cargo build --release`
6. Copy new exe to green version directory
7. Clean any lock files
8. Start exe and verify backend responds on the random port

## Version Bumping Touchpoints

When bumping version (e.g., 0.6.11 → 0.6.12), update ALL of these:

| File | Field |
|------|-------|
| `pyproject.toml` | `version` |
| `config/defaults.yaml` | `app.version` |
| `frontend/package.json` | `version` |
| `app/release-manifest.json` | `product.version`, `release.version` |
| `app/main.py` | Default version strings (3 places) |
| `desktop/package.json` | `version` |
| `desktop/package-lock.json` | `version` + `packages[""].version` |
| `desktop/src-tauri/Cargo.toml` | `version` |
| `desktop/src-tauri/Cargo.lock` | Root package version only (NOT dependencies) |
| `src-tauri/tauri.conf.json` | `version` |
| `src-tauri/Cargo.toml` | `version` |
| `src-tauri/Cargo.lock` | Root package version only |
| `README.md` | Current version line |
| `docs/PROJECT_STATUS.md` | Current version references |
| `tests/test_ci_a0_gates.py` | Version assertions |
| `tests/test_product_version_truth_contract.py` | `EXPECTED_DEVELOPMENT_VERSION` |
| `tests/test_release_manifest.py` | Version assertions |
| `tests/test_diagnostics_api.py` | Version assertions |
| `uv.lock` | Run `uv lock` to update |
| `app/release-manifest.json` | `dependency_lock.digest` (after uv.lock changes) |

**After bumping**: Run `uv lock` then update `release-manifest.json` digest.

## Release Verification Script Patterns

### Handle 410 retired endpoints
```powershell
$workspaceStatus = 0
try {
    $response = Invoke-WebRequest "$base/workspace" -UseBasicParsing -ErrorAction Stop
    $workspaceStatus = [int]$response.StatusCode
} catch {
    if ($_.Exception.Response) {
        $workspaceStatus = [int]$_.Exception.Response.StatusCode
    }
}
# 410 is expected for retired endpoints
if ($workspaceStatus -ne 410) { throw "expected 410" }
```

### Use API endpoints for version checks
Don't use retired UI endpoints. Use `/api/v1/setup/status` or `/workspace/api/status` instead.

## Vault CRLF Hash Bug

On Windows, `read_text(encoding="utf-8")` normalizes `\r\n` → `\n`, but `read_bytes()` preserves CRLF. If hash is computed from bytes but the API returns hash from text, every write reports 409 conflict.

**Fix**: Always hash from normalized text:
```python
current_text = target.read_text(encoding="utf-8")
current_hash = hashlib.sha256(current_text.encode("utf-8")).hexdigest()
```
