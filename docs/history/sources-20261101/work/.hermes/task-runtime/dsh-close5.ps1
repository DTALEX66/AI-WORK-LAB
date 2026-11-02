$ErrorActionPreference = "Continue"
$repo = "D:\All projects\WORK-LAB"
$out = "$repo\.hermes\task-runtime\dsh-close5.out.txt"
$lines = New-Object System.Collections.Generic.List[string]
function L($m) { $lines.Add($m) }

L "=== CLOSE5 @ $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') ==="

L "--- 1) explorer state ---"
$ex = Get-Process explorer -ErrorAction SilentlyContinue
L ("explorer_running=" + $(if ($ex) { ($ex | ForEach-Object ProcessId) -join "," } else { "DEAD" }))
if (-not $ex) {
  Start-Process explorer.exe
  Start-Sleep -Seconds 3
  $ex2 = Get-Process explorer -ErrorAction SilentlyContinue
  L ("explorer_restarted=" + $(if ($ex2) { "YES pid=" + (($ex2 | ForEach-Object ProcessId) -join ",") } else { "FAILED" }))
}

L "--- 2) machine-level DSH_HOME (needs UAC) ---"
$mk = Get-ItemProperty -Path 'HKLM:\SYSTEM\CurrentControlSet\Control\Session Manager\Environment' -Name DSH_HOME -ErrorAction SilentlyContinue
if ($mk) { L ("machine.DSH_HOME=" + $mk.DSH_HOME + " (already set)") }
else {
  L "triggering elevated write (UAC prompt will appear on desktop)"
  Start-Process -FilePath powershell -Verb RunAs -ArgumentList @('-NoProfile','-ExecutionPolicy','Bypass','-File',"$repo\.hermes\task-runtime\dsh-elev.ps1")
  $ok = $false
  for ($i=1; $i -le 15; $i++) {
    Start-Sleep -Seconds 2
    $mk2 = Get-ItemProperty -Path 'HKLM:\SYSTEM\CurrentControlSet\Control\Session Manager\Environment' -Name DSH_HOME -ErrorAction SilentlyContinue
    if ($mk2) { $ok = $true; L ("machine.DSH_HOME set after " + ($i*2) + "s: " + $mk2.DSH_HOME); break }
  }
  if (-not $ok) { L "machine.DSH_HOME still NOT set after 30s poll -- awaiting user UAC click" }
}

L "--- 3) DSH health (should still be D-root) ---"
$procs = Get-CimInstance Win32_Process -Filter "Name='DSH Desktop.exe'" -ErrorAction SilentlyContinue
L ("runningInstances=" + ($procs.Count))
$ln = Get-NetTCPConnection -LocalPort 43120 -State Listen -ErrorAction SilentlyContinue
L ("43120_listening=" + ($null -ne $ln))
$dRoot = "D:\All projects\DSH\.dsh"
L ("dRootExists=" + (Test-Path $dRoot))
L ("cSkeletonExists=" + (Test-Path "C:\Users\ALEX\.dsh") + " (archived backup kept)")

L "--- 4) reboot-pending ---"
$pfr = Test-Path 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\PendingFileRenameOperations'
L ("pendingFileRename=" + $pfr + " (we did NOT schedule any reboot)")

$lines | Out-File -FilePath $out -Encoding utf8
Write-Output "CLOSE5_DONE $out"
