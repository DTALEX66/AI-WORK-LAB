# CRLF Hash Normalization and PowerShell 7 Catch Pitfalls

## CRLF hash mismatch in vault/source writes (validated 2026-08-29)

**Symptom:** A `write_file` function that checks `expected_hash` against the current file content always returns 409 conflict on Windows for files that have CRLF line endings.

**Root cause:** Two different read methods produce different hashes for the same file:
- `Path.read_bytes()` preserves raw `\r\n` bytes → hash A
- `Path.read_text(encoding="utf-8")` normalizes `\r\n` to `\n` → hash B

If the read-side (which returns the hash to the client) uses `read_text` normalization, and the write-side (which validates the expected hash) uses `read_bytes`, every CRLF file is permanently rejected.

**Fix:** Always hash the canonical text form:
```python
current_text = target.read_text(encoding="utf-8")
current_hash = hashlib.sha256(current_text.encode("utf-8")).hexdigest()
```
Keep raw bytes separately for faithful backup:
```python
current_bytes = target.read_bytes()  # for backup only
backup.write_bytes(current_bytes)
```

**Where it appeared:** ArcheAxis vault `write_file` in `app/workspace/vault.py`. The `VaultFile.from_path` computed `source_hash` from `_sha256(text)` (normalized), but `write_file` used `hashlib.sha256(current).hexdigest()` where `current = target.read_bytes()` (raw). On Windows, any file with CRLF endings had a permanent hash mismatch.

## PowerShell 7 Invoke-WebRequest catch clause (validated 2026-08-29)

**Symptom:** A release verification script (`verify_zip_distributions.ps1`) fails at `Invoke-WebRequest "$base/workspace"` even though the try/catch block should handle the 410 response.

**Root cause:** PowerShell version difference in exception types:
- PowerShell 5.1: `Invoke-WebRequest -ErrorAction Stop` throws `[System.Net.WebException]` for non-2xx
- PowerShell 7+ (pwsh): throws `[Microsoft.PowerShell.Commands.HttpResponseException]` instead

A `catch [System.Net.WebException]` clause in pwsh silently misses the HttpResponseException — the error escapes, the script fails, and the status code is never captured.

**Fix:** Use a bare `catch` (no type filter):
```powershell
$workspaceStatus = 0
try {
    $workspaceResponse = Invoke-WebRequest "$base/workspace" -UseBasicParsing -ErrorAction Stop
    $workspaceStatus = [int]$workspaceResponse.StatusCode
} catch {
    # PowerShell 7+ throws HttpResponseException (not WebException)
    $resp = $_.Exception.Response
    if ($resp -and $resp.StatusCode) {
        $workspaceStatus = [int]$resp.StatusCode
    }
}
```

**Note:** The NSIS lifecycle verifier (`verify_nsis_install.ps1`) already used bare `catch` — only the zip distribution verifier needed patching. Always check both scripts when fixing one.

**Impact on release workflow:** The v0.6.12 release failed because of this. Had to bump to v0.6.13 (protected tags prevented re-tagging). Lesson: run ALL verification scripts locally before creating an immutable tag.
