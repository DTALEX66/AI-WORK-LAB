$ErrorActionPreference = "Continue"
$ex = @(Get-Process explorer -ErrorAction SilentlyContinue)
Write-Output ("explorer_now=" + (($ex | ForEach-Object ProcessId) -join ","))
if ($ex.Count -eq 0) {
  try {
    Start-Process -FilePath "$env:SystemRoot\explorer.exe" -WorkingDirectory "$env:USERPROFILE" -ErrorAction Stop
    Write-Output "start_attempt=ok"
  } catch {
    Write-Output ("start_attempt_err=" + $_.Exception.Message)
  }
  Start-Sleep -Seconds 8
  $ex2 = @(Get-Process explorer -ErrorAction SilentlyContinue)
  Write-Output ("explorer_after=" + (($ex2 | ForEach-Object ProcessId) -join ","))
}
