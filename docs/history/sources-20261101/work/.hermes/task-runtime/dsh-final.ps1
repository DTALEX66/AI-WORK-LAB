$ErrorActionPreference = "Continue"
$repo = "D:\All projects\WORK-LAB"
$ds   = "D:\All projects\DSH"
$cRoot = "C:\Users\ALEX\.dsh"
$bak = "$cRoot-skeleton-backup-20260924"
$out  = "$repo\.hermes\task-runtime\dsh-final.out.txt"
$lines = New-Object System.Collections.Generic.List[string]
function L($m) { $lines.Add($m) }

L "=== DSH FINAL CLOSE-OUT @ $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') ==="

L "--- A) DSH_HOME registry values (the real check) ---"
$mk = Get-ItemProperty -Path 'HKLM:\SYSTEM\CurrentControlSet\Control\Session Manager\Environment' -Name DSH_HOME -ErrorAction SilentlyContinue
L ("HKLM.machine.DSH_HOME=" + $(if ($mk) { $mk.DSH_HOME } else { "NOT SET" }))
$mkd = Get-ItemProperty -Path 'HKLM:\SYSTEM\CurrentControlSet\Control\Session Manager\Environment' -Name DSH_DESKTOP_USER_DATA -ErrorAction SilentlyContinue
L ("HKLM.machine.DSH_DESKTOP_USER_DATA=" + $(if ($mkd) { $mkd.DSH_DESKTOP_USER_DATA } else { "NOT SET" }))
$uk = Get-ItemProperty -Path 'HKCU:\Environment' -Name DSH_HOME -ErrorAction SilentlyContinue
L ("HKCU.user.DSH_HOME=" + $(if ($uk) { $uk.DSH_HOME } else { "NOT SET" }))
$ukd = Get-ItemProperty -Path 'HKCU:\Environment' -Name DSH_DESKTOP_USER_DATA -ErrorAction SilentlyContinue
L ("HKCU.user.DSH_DESKTOP_USER_DATA=" + $(if ($ukd) { $ukd.DSH_DESKTOP_USER_DATA } else { "NOT SET" }))

L "--- B) explorer.exe alive? ---"
$ex = Get-Process explorer -ErrorAction SilentlyContinue
L ("explorer_pid=" + $(if ($ex) { ($ex | ForEach-Object ProcessId) -join "," } else { "DEAD" }))

L "--- C) archive + remove C skeleton (DSH now runs on D root; skeleton is orphaned fallback) ---"
if (Test-Path $cRoot) {
  if (-not (Test-Path $bak)) {
    $r = Rename-Item $cRoot $bak -ErrorAction SilentlyContinue
    L ("cSkeletonArchived=" + $(if (Test-Path $bak) { "YES -> $bak" } else { "NO (rename failed)" }))
  } else { L "cSkeletonAlreadyArchived=YES" }
} else { L "cSkeletonGone=YES" }
if (Test-Path $bak) {
  L ("cSkeletonBackup=" + "$bak (kept as evidence; removable later)")
}
L ("cSkeletonNowExists=" + (Test-Path $cRoot))

L "--- D) DSH process health (should be D-root + DSH_HOME injected) ---"
$procs = Get-CimInstance Win32_Process -Filter "Name='DSH Desktop.exe'" -ErrorAction SilentlyContinue
L ("runningInstances=" + ($procs.Count))
$main = $procs | Where-Object { $_.CommandLine -notmatch '--type=' } | Select-Object -First 1
if ($main) {
  $injected = ($main.CommandLine -match 'DSH_HOME=D:') -or ((Get-Process -Id $main.ProcessId -ErrorAction SilentlyContinue).Parent -ne $null)
  L ("main_pid=" + $main.ProcessId + " cmd=[" + $main.CommandLine + "]")
  L ("main_parent_env_has_DSH_HOME=" + $(
    try { $pp = (Get-CimInstance Win32_Process -Filter "ProcessId=$($main.ParentProcessId)").CommandLine; if ($pp -match 'DSH_HOME') { 'YES (launcher injected)' } else { 'NO (check D root writes below)' } } catch { 'unknown' }
  ))
}
$listening = Get-NetTCPConnection -LocalPort 43120 -State Listen -ErrorAction SilentlyContinue
L ("43120_listening=" + ($null -ne $listening))

L "--- E) D data root liveness (mtime should advance after my restart) ---"
$dRoot = "$ds\.dsh"
L ("dRootMtime=" + $(if (Test-Path $dRoot) { (Get-Item $dRoot).LastWriteTime } else { "GONE" }))
L ("dRootSessions=" + $(if (Test-Path "$dRoot\sessions") { (Get-ChildItem "$dRoot\sessions" -Directory -ErrorAction SilentlyContinue).Count } else { "n/a" }))

L "--- F) reboot-pending recheck (read-only) ---"
$pfr = Test-Path 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\PendingFileRenameOperations'
$wu = (Get-CimInstance -Namespace root\CIMV2 -Query "SELECT RebootPending FROM Win32_OperatingSystem" -ErrorAction SilentlyContinue).RebootPending
L ("pendingFileRename=" + $pfr + " wmiRebootPending=" + $wu)
if ($pfr -or $wu) { L "!! a reboot IS pending -- system will restart soon; that is what refreshes session env" }
else { L "no pending reboot; the durable machine-level value will apply at NEXT logon/reboot" }

$lines | Out-File -FilePath $out -Encoding utf8
Write-Output "FINAL_DONE $out"
