$ErrorActionPreference = "Continue"
$repo = "D:\All projects\WORK-LAB"
$ds   = "D:\All projects\DSH"
$out  = "$repo\.hermes\task-runtime\dsh-check4.out.txt"
$lines = New-Object System.Collections.Generic.List[string]
function L($m) { $lines.Add($m) }
function V($v,$label){ $s = if ($null -eq $v) { "MISSING" } else { [string]$v }; L("$label = $s") }

L "=== READ-ONLY STATE CHECK @ $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') ==="

L "--- 1) machine-level DSH_HOME (HKLM Session Manager\Environment) ---"
try { $mv = (Get-ItemProperty -Path 'HKLM:\SYSTEM\CurrentControlSet\Control\Session Manager\Environment' -Name DSH_HOME -ErrorAction Stop).DSH_HOME; A2 $mv "machine DSH_HOME" } catch { A2 "MISSING" "machine DSH_HOME"; L "   err=" + $_.Exception.Message }

L "--- 2) user-level DSH_HOME (HKCU\Environment) ---"
try { $uv = (Get-ItemProperty -Path 'HKCU:\Environment' -Name DSH_HOME -ErrorAction Stop).DSH_HOME; A2 $uv "user DSH_HOME" } catch { A2 "MISSING" "user DSH_HOME"; L "   err=" + $_.Exception.Message }

L "--- 3) C-drive skeleton: current + backup ---"
$cRoot = "C:\Users\ALEX\.dsh"
L ("cSkeletonExists=" + (Test-Path $cRoot))
$bak = "$cRoot-skeleton-backup-20260924"
L ("cSkeletonBackupExists=" + (Test-Path $bak))

L "--- 4) D:\ data root (.dsh) health ---"
$dRoot = "$ds\.dsh"
L ("dRootExists=" + (Test-Path $dRoot))
if (Test-Path $dRoot) { L ("dRootMtime=" + (Get-Item $dRoot).LastWriteTime) }
$sess = Join-Path $dRoot "sessions"
if (Test-Path $sess) { L ("dRootSessions=" + (Get-ChildItem $sess -Directory -ErrorAction SilentlyContinue).Count) }

L "--- 5) running DSH instances (alive? reading which data dir?) ---"
$procs = Get-CimInstance Win32_Process -Filter "Name='DSH Desktop.exe'" -ErrorAction SilentlyContinue
L ("runningInstances=" + ($procs.Count))
foreach ($p in $procs) {
  L ("   pid=" + $p.ProcessId + " parent=" + $p.ParentProcessId + " cmd=" + $p.CommandLine)
}
$listening = Get-NetTCPConnection -LocalPort 43120 -State Listen -ErrorAction SilentlyContinue
L ("43120_listening=" + ($null -ne $listening) + " (count=" + @($listening).Count + ")")

L "--- 6) reboot pending? (read-only; we do NOT schedule any) ---"
$pending = @()
if (Test-Path 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\PendingFileRenameOperations') {
  $pending += "PendingFileRenameOperations(PFR pending reboot)"
}
if (Test-Path 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\WindowsUpdate\AutoUpdate') {
  $au = (Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\WindowsUpdate\AutoUpdate' -Name RebootRequired -ErrorAction SilentlyContinue).RebootRequired
  if ($au) { $pending += "WU RebootRequired=$au" }
}
$wu = (Get-CimInstance -Namespace root\CIMV2 -Query "SELECT RebootPending FROM Win32_OperatingSystem" -ErrorAction SilentlyContinue)
if ($wu -and $wu.RebootPending) { $pending += "WMI Win32_OperatingSystem.RebootPending=true" }
L ("rebootPendingSignals=[" + ($pending -join " | ") + "] (count=" + $pending.Count + ")")
if ($pending.Count -eq 0) { L "   => no pending-reboot flag set (fix3's Restart-Computer did NOT actually schedule a reboot)" }

$lines | Out-File -FilePath $out -Encoding utf8
Write-Output "CHECK4_DONE $out"
