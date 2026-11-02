$ErrorActionPreference = "Continue"
$repo = "D:\All projects\WORK-LAB"
$ds = "D:\All projects\DSH"
$cRoot = "C:\Users\ALEX\.dsh"
$out = "$repo\.hermes\task-runtime\dsh-reaudit.out.txt"
$lines = New-Object System.Collections.Generic.List[string]
function L($m) { $lines.Add($m) }
function FLUSH() { $lines | Out-File -FilePath $out -Encoding utf8 }

try {
L "=== DSH RE-AUDIT (GOAL doc, read-only) @ $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') ==="

L "--- 1) .lnk three fields (desktop + start menu) ---"
$shell = New-Object -ComObject WScript.Shell
$targets = @("$env:USERPROFILE\Desktop\DSH Desktop.lnk", "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\DSH Desktop.lnk")
foreach ($p in $targets) {
  if (Test-Path $p) {
    $l = $shell.CreateShortcut($p)
    $tOK = Test-Path -LiteralPath $l.TargetPath
    $iOK = $false
    if ($l.IconLocation) { $iconExe = ($l.IconLocation -split ',')[0]; $iOK = Test-Path -LiteralPath $iconExe }
    L ("[lnk] " + [System.IO.Path]::GetFileName($p))
    L ("  target=" + $l.TargetPath + " exists=" + $tOK)
    L ("  args=" + $l.Arguments)
    L ("  icon=" + $l.IconLocation + " exists=" + $iOK)
  } else { L ("[lnk MISSING] " + $p) }
}

L "--- 2) official install identity ---"
$exe = "$ds\DSH Desktop.exe"
L ("exe_exists=" + (Test-Path $exe))
if (Test-Path $exe) { L ("exe_product_version=" + (Get-Item $exe).VersionInfo.ProductVersion) }
$uninst = Get-ChildItem $ds -Filter "Uninstall DSH Desktop.exe" -ErrorAction SilentlyContinue
L ("nsis_uninstaller_present=" + ($null -ne $uninst))

L "--- 3) running DSH (tasklist CSV, ASCII-safe) ---"
$csv = & tasklist /FI "IMAGENAME eq DSH Desktop.exe" /FO CSV /NH 2>$null
$dsRows = @($csv | Where-Object { $_ -match 'DSH Desktop\.exe' })
L ("tasklist_DSH_rows=" + $dsRows.Count)
$pids = @($dsRows | ForEach-Object { ($_ -split '","')[1] })
if ($pids.Count -gt 0) {
  $cim = Get-CimInstance Win32_Process -Filter ("ProcessId IN (" + ($pids -join ",") + ")") -ErrorAction SilentlyContinue
  $bad = @($cim | Where-Object { $_.CommandLine -notmatch "user-data-dir=.D:.All projects.DSH.desktop-user-data" -and $_.CommandLine -notmatch "DSH Desktop.exe.*--user-data-dir" })
  $main = @($cim | Where-Object { $_.CommandLine -notmatch "type=" })
  L ("main_instances=" + $main.Count)
  if ($main.Count -gt 0) {
    $ver = ($main[0].CommandLine -match 'crashpad')
    L ("main[0]_cmd=" + $main[0].CommandLine)
  }
  $crash = @($cim | Where-Object { $_.CommandLine -match "crashpad" })
  if ($crash.Count -gt 0) {
    $mv = [regex]::Match($crash[0].CommandLine, "ver=([0-9.]+)")
    L ("crashpad_ver=" + $(if ($mv.Success) { $mv.Groups[1].Value } else { "unknown" }))
  }
}

L "--- 4) port 43120 ---"
$ln = Get-NetTCPConnection -LocalPort 43120 -State Listen -ErrorAction SilentlyContinue
L ("43120_listening=" + ($null -ne $ln))

L "--- 5) data roots ---"
$dRoot = "$ds\.dsh"
L ("dRoot_exists=" + (Test-Path $dRoot) + " mtime=" + $(if (Test-Path $dRoot) { (Get-Item $dRoot).LastWriteTime } else { "" }))
if (Test-Path "$dRoot\sessions") {
  $dirs = @(Get-ChildItem "$dRoot\sessions" -Directory -ErrorAction SilentlyContinue)
  L ("dRoot_session_projects=" + $dirs.Count + " names=[" + (($dirs | ForEach-Object { $_.Name }) -join ",") + "]")
}
L ("cFallback_live=" + (Test-Path $cRoot) + "  (must be False)")
L ("cSkeleton_archive=" + (Test-Path "$ds\.migration\20260924\c-dsh-skeleton-backup-20260924"))

L "--- 6) DSH_HOME env layers ---"
$uk = Get-ItemProperty -Path 'HKCU:\Environment' -Name DSH_HOME -ErrorAction SilentlyContinue
L ("HKCU_DSH_HOME=" + $(if ($uk) { $uk.DSH_HOME } else { "MISSING" }))
$mk = Get-ItemProperty -Path 'HKLM:\SYSTEM\CurrentControlSet\Control\Session Manager\Environment' -Name DSH_HOME -ErrorAction SilentlyContinue
L ("HKLM_DSH_HOME=" + $(if ($mk) { $mk.DSH_HOME + " (machine level)" } else { "NOT SET (open boundary; HKCU applies at next logon)")))

L "--- 7) explorer + pending reboot ---"
$ex = @(Get-Process explorer -ErrorAction SilentlyContinue)
L "explorer_pids=" + $(if ($ex.Count -gt 0) { (($ex | ForEach-Object { $_.ProcessId }) -join ",") } else { "DEAD" }))
L ("pendingFileRename=" + (Test-Path 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\PendingFileRenameOperations'))
} catch {
  L ("ERROR: " + $_.Exception.Message + " at line " + $_.InvocationInfo.LineNumber)
  L ("ERROR script line: " + $_.InvocationInfo.ScriptLineNumber)
}
$lines | Out-File -FilePath $out -Encoding utf8
Write-Output "REAUDIT_DONE"
