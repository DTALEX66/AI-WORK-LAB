$ErrorActionPreference = "Continue"
$out = "D:\All projects\WORK-LAB\.hermes\task-runtime\dsh-diag3.out.txt"
$lines = New-Object System.Collections.Generic.List[string]
function L($m) { $lines.Add($m) }

L "===== A. DSH_HOME registry (HKCU\Environment) ====="
$envKey = "HKCU:\Environment"
if (Test-Path $envKey) {
  $p = Get-ItemProperty $envKey
  $ds = $p.DSH_HOME
  if ($ds) {
    L "DSH_HOME = '$ds'  (registry type: user env var)"
    L ("   target dir exists: {0}  filecount: {1}" -f (Test-Path -LiteralPath $ds), (if (Test-Path -LiteralPath $ds) { @(Get-ChildItem $ds -Recurse -File -ErrorAction SilentlyContinue).Count } else { 'n/a' }))
  } else {
    L "DSH_HOME = **NOT SET** in HKCU:\Environment  <-- ROOT CAUSE if sessions missing"
  }
  L "(all HKCU\Environment keys: " + (($p.PSObject.Properties | Where-Object { $_.Value -ne $null } | ForEach-Object { $_.Name }) -join ", ") + ")"
} else { L "HKCU:\Environment ABSENT" }

L ""
L "===== B. C-drive fallback root (recreated when DSH_HOME missing in session) ====="
$croot = "C:\Users\ALEX\.dsh"
if (Test-Path -LiteralPath $croot) {
  $ci = Get-Item $croot
  $cf = @(Get-ChildItem $croot -Recurse -File -ErrorAction SilentlyContinue)
  $csess = @(Get-ChildItem $croot -Recurse -File -ErrorAction SilentlyContinue | Where-Object { $_.Name -match "session" })
  L "C:\Users\ALEX\.dsh EXISTS  mtime=$($ci.LastWriteTime)  files=$($cf.Count)  session-files=$($csess.Count)"
  L "  -> mtime recent + 0 sessions = fallback recreation (DSH_HOME not in session env)"
} else {
  L "C:\Users\ALEX\.dsh ABSENT (good — no C-drive fallback)"
}
# also check Roaming DSH Desktop user data (Electron default)
$croam = "C:\Users\ALEX\AppData\Roaming\DSH Desktop"
if (Test-Path -LiteralPath $croam) { L "C:\Users\ALEX\AppData\Roaming\DSH Desktop EXISTS (Electron default user-data, the 'no setup-complete marker' root)"; } else { L "C:\...\Roaming\DSH Desktop ABSENT" }

L ""
L "===== C. active profile + identity (desktop-user-data) ====="
$ps = "D:\All projects\DSH\desktop-user-data\profile-selection\state.json"
if (Test-Path $ps) { L ("state.json: " + (Get-Content $ps -Raw -ErrorAction SilentlyContinue)); } else { L "profile-selection/state.json ABSENT: $ps" }
$ident = "D:\All projects\DSH\desktop-user-data"
L ("desktop-user-data top dirs: " + (@(Get-ChildItem $ident -Directory -ErrorAction SilentlyContinue | ForEach-Object { $_.Name }) -join ","))

L ""
L "===== D. C vs D session count comparison (definitive) ====="
$dcfg = "D:\All projects\DSH\.dsh"
if (Test-Path $dcfg) {
  $df = @(Get-ChildItem $dcfg -Recurse -File -ErrorAction SilentlyContinue)
  $dsess = @(Get-ChildItem $dcfg -Recurse -File -ErrorAction SilentlyContinue | Where-Object { $_.Name -match "session" })
  L ("D:\.dsh   files=$($df.Count)  session-files=$($dsess.Count)  (the REAL data)")
}
L "if C-root sessions=0 AND D-root sessions>0 AND DSH_HOME unset-in-session -> DSH UI reads empty C-root = 'no config'"

$lines | Out-File -FilePath $out -Encoding utf8
Write-Output "DIAG3_DONE"
