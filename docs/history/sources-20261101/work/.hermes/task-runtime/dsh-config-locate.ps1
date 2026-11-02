$ErrorActionPreference = 'Continue'
$dshRoot = 'D:\All projects\DSH'
$dshHome = 'D:\All projects\DSH\.dsh'
$ded = "$dshRoot\desktop-user-data"

Write-Output "=== 1. DSH data root ($dshHome) ==="
if (Test-Path -LiteralPath $dshHome) {
  $t = Get-Item -LiteralPath $dshHome
  Write-Output ("  exists=True  mtime={0}" -f $t.LastWriteTime)
  $sess = Join-Path $dshHome 'sessions'
  if (Test-Path -LiteralPath $sess) {
    $c = (Get-ChildItem -LiteralPath $sess -ErrorAction SilentlyContinue | Measure-Object).Count
    Write-Output ("  sessions: {0} entries" -f $c)
  } else { Write-Output "  sessions: MISSING" }
  Write-Output "  top entries:"
  Get-ChildItem -LiteralPath $dshHome -ErrorAction SilentlyContinue | Select-Object -First 12 | ForEach-Object { Write-Output ("    " + $_.Name) }
} else {
  Write-Output "  MISSING — data root not found!"
}

Write-Output ""
Write-Output "=== 2. profile-selection / identity ($ded) ==="
$ps = Join-Path $ded 'profile-selection'
if (Test-Path -LiteralPath $ps) {
  Get-ChildItem -LiteralPath $ps | ForEach-Object {
    Write-Output ("  " + $_.Name + " (mtime " + $_.LastWriteTime + ")")
    if ($_.Name -eq 'state.json') {
      $txt = Get-Content -LiteralPath $_.FullName -Raw -ErrorAction SilentlyContinue
      if ($txt) { Write-Output ("    content: " + $txt.Substring(0, [Math]::Min(300, $txt.Length))) }
    }
  }
} else { Write-Output "  profile-selection dir MISSING" }
$id = Join-Path $ded 'identity'
if (Test-Path -LiteralPath $id) {
  Get-ChildItem -LiteralPath $id | ForEach-Object {
    if ($_.Name -like '*.json' -or $_.Name -like '*.yaml') {
      $t2 = Get-Content -LiteralPath $_.FullName -Raw -ErrorAction SilentlyContinue
      Write-Output ("  identity/" + $_.Name + ": " + $t2.Substring(0,[Math]::Min(200,$t2.Length)))
    } else { Write-Output ("  identity/" + $_.Name) }
  }
}

Write-Output ""
Write-Output "=== 3. C:\Users\ALEX\.dsh (fallback skeleton?) ==="
$cDsh = 'C:\Users\ALEX\.dsh'
if (Test-Path -LiteralPath $cDsh) {
  $t3 = Get-Item -LiteralPath $cDsh
  $cSess = 'C:\Users\ALEX\.dsh\sessions'
  $cnt = if (Test-Path -LiteralPath $cSess) { (Get-ChildItem -LiteralPath $cSess | Measure-Object).Count } else { 0 }
  Write-Output ("  exists=True  mtime={0}  sessions={1}  -> {2}" -f $t3.LastWriteTime, $cnt, $(if ($cnt -eq 0) { "EMPTY SKELETON = app fell back to C:" } else { "has data" }))
} else { Write-Output "  does not exist (good — no C: fallback was created)" }

Write-Output ""
Write-Output "=== 4. DSH_HOME registry value (HKCU\Environment) ==="
$rv = Get-ItemProperty -Path 'HKCU:\Environment' -Name 'DSH_HOME' -ErrorAction SilentlyContinue
if ($rv) { Write-Output ("  DSH_HOME = {0}" -f $rv.DSH_HOME) } else { Write-Output "  NOT SET in registry" }

Write-Output ""
Write-Output "=== 5. Current DSH Desktop processes + their command lines (which DSH_HOME/args did they get?) ==="
Get-CimInstance Win32_Process -Filter "Name like '%DSH%'" -ErrorAction SilentlyContinue | ForEach-Object {
  Write-Output ("  pid={0}" -f $_.ProcessId)
  $cl = $_.CommandLine
  if ($cl) {
    Write-Output ("    cmdline: {0}" -f $cl.Substring(0, [Math]::Min(300, $cl.Length)))
  } else { Write-Output "    cmdline: (none readable)" }
}

Write-Output ""
Write-Output "=== 6. env DSH_HOME in THIS powershell session ==="
Write-Output ("  $env:DSH_HOME = '{0}'" -f $env:DSH_HOME)
