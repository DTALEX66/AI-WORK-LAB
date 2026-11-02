$ErrorActionPreference = "Continue"
$repo = "D:\All projects\WORK-LAB"
$out  = "$repo\.hermes\task-runtime\dsh-close6.out.txt"
$lines = New-Object System.Collections.Generic.List[string]
function L($m) { $lines.Add($m) }

L "=== CLOSE6 @ $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') ==="

L "--- 1) restart explorer (taskbar/shell) ---"
$ex = @(Get-Process explorer -ErrorAction SilentlyContinue)
L ("explorer_procs_before=" + $ex.Count)
if ($ex.Count -eq 0) {
  try { Start-Process explorer.exe -ErrorAction Stop; L "explorer_start_requested=YES" } catch { L "explorer_start_failed=" + $_.Exception.Message }
  Start-Sleep -Seconds 4
}
$ex2 = @(Get-Process explorer -ErrorAction SilentlyContinue)
L ("explorer_procs_after=" + $ex2.Count + $(if ($ex2.Count -gt 0) { " pid=" + (($ex2 | ForEach-Object ProcessId) -join ",") + " shell back" } else { " STILL DEAD" }))

L "--- 2) machine-level DSH_HOME (HKLM, needs UAC) ---"
$mk = Get-ItemProperty -Path 'HKLM:\SYSTEM\CurrentControlSet\Control\Session Manager\Environment' -Name DSH_HOME -ErrorAction SilentlyContinue
if ($mk) {
  L ("HKLM.DSH_HOME=" + $mk.DSH_HOME + " (already written -- UAC was approved)")
} else {
  L "HKLM.DSH_HOME still missing -- triggering elevated write again (UAC prompt on desktop)"
  Start-Process -FilePath powershell -Verb RunAs -ArgumentList @('-NoProfile','-ExecutionPolicy','Bypass','-File',"$repo\.hermes\task-runtime\dsh-elev.ps1") -ErrorAction SilentlyContinue
  $ok = $false
  for ($i = 1; $i -le 22; $i++) {
    Start-Sleep -Seconds 2
    $mk2 = Get-ItemProperty -Path 'HKLM:\SYSTEM\CurrentControlSet\Control\Session Manager\Environment' -Name DSH_HOME -ErrorAction SilentlyContinue
    if ($mk2) { $ok = $true; L ("HKLM.DSH_HOME set after " + ($i*2) + "s = " + $mk2.DSH_HOME); break }
  }
  if (-not $ok) { L "HKLM.DSH_HOME still NOT set after 44s -- UAC pending: user must click Yes on the prompt" }
}

L "--- 3) user-level DSH_HOME (HKCU, already correct) ---"
$uk = Get-ItemProperty -Path 'HKCU:\Environment' -Name DSH_HOME -ErrorAction SilentlyContinue
L ("HKCU.DSH_HOME=" + $(if ($uk) { $uk.DSH_HOME } else { "MISSING" }))

L "--- 4) DSH running health (should stay on D root; 7 procs expected) ---"
$procs = @(Get-CimInstance Win32_Process -Filter "Name='DSH Desktop.exe'" -ErrorAction SilentlyContinue)
L ("dsh_instances=" + $procs.Count)
$main = $procs | Where-Object { $_.CommandLine -notmatch '--type=' } | Select-Object -First 1
if ($main) { L ("main_pid=" + $main.ProcessId + " cmd=[" + $main.CommandLine + "]") }
$ln = Get-NetTCPConnection -LocalPort 43120 -State Listen -ErrorAction SilentlyContinue
L ("43120_listening=" + ($null -ne $ln))

L "--- 5) data roots ---"
$dRoot = "D:\All projects\DSH\.dsh"
L ("dRoot_exists=" + (Test-Path $dRoot) + " mtime=" + $(if (Test-Path $dRoot) { (Get-Item $dRoot).LastWriteTime } else { "" }))
L ("dRoot_sessions=" + $(if (Test-Path "$dRoot\sessions") { (Get-ChildItem "$dRoot\sessions" -Directory -ErrorAction SilentlyContinue).Count } else { "n/a" }))
L ("cSkeleton_live=" + (Test-Path "C:\Users\ALEX\.dsh") + "  (archived evidence kept at C:\Users\ALEX\.dsh-skeleton-backup-20260924)")

L "--- 6) desktop shortcut still correct? ---"
$shell = New-Object -ComObject WScript.Shell
$lnk = $shell.CreateShortcut("$env:USERPROFILE\Desktop\DSH Desktop.lnk")
L ("lnk_target=" + $lnk.TargetPath + " exists=" + (Test-Path -LiteralPath $lnk.TargetPath))
L ("lnk_args=" + $lnk.Arguments)

$lines | Out-File -FilePath $out -Encoding utf8
Write-Output "CLOSE6_DONE $out"
