$ErrorActionPreference = "Continue"
$out = "D:\All projects\WORK-LAB\.hermes\task-runtime\dsh-fix1.out.txt"
$lines = New-Object System.Collections.Generic.List[string]
function L($m) { $lines.Add($m) }

L "===== STEP 0: kill running DSH (all 7 processes, currently reading C fallback) ====="
$procs = @(Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object { $_.Name -eq "DSH Desktop.exe" })
L ("DSH processes before kill: {0}" -f $procs.Count)
taskkill /F /IM "DSH Desktop.exe" 2>&1 | ForEach-Object { L ("   " + $_) }
Start-Sleep -Seconds 3
$still = @(Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object { $_.Name -eq "DSH Desktop.exe" })
L ("DSH processes after kill: {0}" -f $still.Count)

L ""
L "===== STEP 1: DSH_HOME env re-broadcast (per-user) + machine-level attempt ====="
$regVal = (Get-ItemProperty "HKCU:\Environment").DSH_HOME
L "HKCU:\Environment DSH_HOME (pre-setx) = '$regVal'"
setx DSH_HOME "D:\All projects\DSH\.dsh" 2>&1 | ForEach-Object { L "per-user setx: " + $_ }
try {
  $r = & setx /M DSH_HOME "D:\All projects\DSH\.dsh" 2>&1
  L "machine setx /M: " + ($r -join " ")
} catch {
  L ("machine setx /M FAILED: " + $_.Exception.Message)
}
$mk = (Get-ItemProperty "HKLM:\SYSTEM\CurrentVersion\Environment" -Name DSH_HOME -ErrorAction SilentlyContinue).DSH_HOME
L "HKLM DSH_HOME now = '$mk'"
# verify current user block re-read
L "HKCU:\Environment DSH_HOME (post-setx) = '$((Get-ItemProperty "HKCU:\Environment").DSH_HOME)'"

L ""
L "===== STEP 2: park + remove empty C-drive fallback roots (evidence-gated) ====="
$croot = "C:\Users\ALEX\.dsh"
if (Test-Path -LiteralPath $croot) {
  $cf = @(Get-ChildItem $croot -Recurse -File -ErrorAction SilentlyContinue)
  $csess = @($cf | Where-Object { $_.Name -match "session" })
  $ccred = @($cf | Where-Object { $_.Name -match "credential|\.key|token" })
  L ("C:\.dsh files={0} session-files={1} credential-ish={2}" -f $cf.Count, $csess.Count, $ccred.Count)
  $cf | ForEach-Object { L ("   " + $_.FullName.Replace("C:\Users\ALEX\.dsh","") + "  " + $_.Length + "B") }
  if ($csess.Count -eq 0 -and $ccred.Count -eq 0) {
    $park = "D:\All projects\DSH\.migration\20260924\c-dsh-skeleton-archived"
    New-Item -ItemType Directory -Path $park -Force | Out-Null
    Copy-Item -Path "$croot\*" -Destination $park -Recurse -Force
    $copied = @(Get-ChildItem $park -Recurse -File).Count
    L ("parked {0} files -> {1}" -f $copied, $park)
    Remove-Item -LiteralPath $croot -Recurse -Force
    L ("C source removed; now exists: {0}" -f (Test-Path -LiteralPath $croot))
  } else {
    L "C root has real data — DO NOT DELETE, parked only"
  }
} else { L "C:\.dsh already absent" }

$croam = "C:\Users\ALEX\AppData\Roaming\DSH Desktop"
if (Test-Path -LiteralPath $croam) {
  $rf = @(Get-ChildItem $croam -Recurse -File -ErrorAction SilentlyContinue)
  $rsess = @($rf | Where-Object { $_.Name -match "session" })
  L ("C Roaming 'DSH Desktop' files={0} session-files={1} (created by 2026-09-23 argless test instances)" -f $rf.Count, $rsess.Count)
  if ($rsess.Count -eq 0) {
    $park2 = "D:\All projects\DSH\.migration\20260924\c-roaming-dsh-desktop-archived"
    New-Item -ItemType Directory -Path $park2 -Force | Out-Null
    Copy-Item -Path "$croam\*" -Destination $park2 -Recurse -Force -ErrorAction SilentlyContinue
    $sz = (Get-ChildItem $croam -Recurse -File -ErrorAction SilentlyContinue | Measure-Object Length -Sum).Sum
    Remove-Item -LiteralPath $croam -Recurse -Force -ErrorAction SilentlyContinue
    L ("Roaming default user-data parked+removed ({0}B); now exists: {1}" -f $sz, (Test-Path -LiteralPath $croam))
  } else {
    L "Roaming root has session data — parked only, NOT removed"
  }
} else { L "C Roaming 'DSH Desktop' already absent" }

L ""
L "===== STEP 3: D-root baseline before relaunch ====="
$dcfg = "D:\All projects\DSH\.dsh"
$dmtime = (Get-Item $dcfg).LastWriteTime
L ("D:\.dsh mtime baseline: {0}" -f $dmtime)
$ud = "D:\All projects\DSH\desktop-user-data"
$hm = (Get-ChildItem "$ud\health-snapshots" -ErrorAction SilentlyContinue | Measure-Object).Count
L ("desktop-user-data health-snapshots count baseline: {0}" -f $hm)

$lines | Out-File -FilePath $out -Encoding utf8
Write-Output "FIX1_DONE"
