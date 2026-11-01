[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$PackRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$Verifier = Join-Path $PackRoot "scripts\verify_taskpack.py"

Write-Host "OPEN-DESIGN-Assistance Authoritative TaskPack V4.1" -ForegroundColor Cyan
Write-Host "Read-only task-pack verification; the target repository will not be modified."

$Python = Get-Command python -ErrorAction SilentlyContinue
if (-not $Python) {
    throw "Python was not found on PATH. Install or expose Python, then rerun this script."
}

& $Python.Source $Verifier
if ($LASTEXITCODE -ne 0) {
    throw "Task-pack verification failed. Do not start repository work."
}

Write-Host ""
Write-Host "Verification passed." -ForegroundColor Green
Write-Host "Give 01_MASTER_HERMES_TASKPACK.md to HERMES in full."
Write-Host "HERMES must also read 02_CLOUD_DRIFT_AUDIT_20260808.md, tasks\phases.json, and tasks\task-cards.json."
Write-Host "Start at ODA4-0001, execute the ODA4-0110..0118 correction wave, then move directly to Phase 04/05."
Write-Host "Default mode: audit/plan/staging; no commit, push, PR, merge, ruleset, tag, or release."
