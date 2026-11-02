$ErrorActionPreference = 'Continue'
$wsh = New-Object -ComObject WScript.Shell

function Show-Lnk($p) {
  if (-not (Test-Path -LiteralPath $p)) { Write-Output "  (shortcut file missing)"; return }
  try {
    $lnk = $wsh.CreateShortcut($p)
    $tp = $lnk.TargetPath
    $arg = $lnk.Arguments
    $wd = $lnk.WorkingDirectory
    Write-Output "  Target      : $tp"
    Write-Output "  Arguments   : $arg"
    Write-Output "  WorkingDir  : $wd"
    $ok = $false
    if ($tp) { $ok = Test-Path -LiteralPath $tp }
    Write-Output "  TargetExists: $ok"
    if (-not $ok -and $tp) {
      $parent = Split-Path $tp -Parent
      if (Test-Path -LiteralPath $parent) {
        Write-Output "  (parent exists, siblings:)"
        Get-ChildItem -LiteralPath $parent -ErrorAction SilentlyContinue | ForEach-Object { Write-Output ("    " + $_.Name) }
      } else {
        Write-Output "  (parent missing too: $parent)"
      }
    }
  } catch {
    Write-Output "  (read error: $($_.Exception.Message))"
  }
}

$desktop = [Environment]::GetFolderPath('Desktop')
Write-Output "=== Desktop folder: $desktop ==="
Get-ChildItem -LiteralPath $desktop -Filter '*.lnk' -ErrorAction SilentlyContinue |
  Where-Object { $_.Name -match 'dsh|DeepSeek|Deep Seek' } |
  ForEach-Object { Write-Output "--- $($_.Name) ---"; Show-Lnk $_.FullName }

$smRoots = @()
if ($env:APPDATA) { $smRoots += (Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu\Programs') }
if ($env:ProgramData) { $smRoots += (Join-Path $env:ProgramData 'Microsoft\Windows\Start Menu\Programs') }
foreach ($root in $smRoots) {
  if (-not (Test-Path -LiteralPath $root)) { continue }
  Write-Output "=== Start Menu: $root ==="
  Get-ChildItem -LiteralPath $root -Filter '*.lnk' -Recurse -ErrorAction SilentlyContinue |
    Where-Object { $_.Name -match 'dsh|DeepSeek|Deep Seek' } |
    ForEach-Object { Write-Output "--- $($_.Name) ---"; Show-Lnk $_.FullName }
}

Write-Output "=== Candidate official exe locations ==="
$locs = @('D:\All projects\DSH\DSH Desktop.exe')
foreach ($l in $locs) { Write-Output ("{0}  exists={1}" -f $l, (Test-Path -LiteralPath $l)) }
Write-Output "LOCALAPPDATA DSH programs:"
Get-ChildItem -LiteralPath $env:LOCALAPPDATA -Filter '*dsh*' -Directory -ErrorAction SilentlyContinue | ForEach-Object { Write-Output ("  " + $_.FullName + "  exists=" + (Test-Path -LiteralPath $_.FullName)) }

Write-Output "=== D:\All projects\DSH top-level (names only) ==="
Get-ChildItem -LiteralPath 'D:\All projects\DSH' -ErrorAction SilentlyContinue | ForEach-Object { Write-Output ("  " + $_.Name) }

Write-Output "=== DSH processes ==="
$procs = Get-Process -ErrorAction SilentlyContinue | Where-Object { $_.Name -match 'DSH|dsh' }
if ($procs) { $procs | ForEach-Object { Write-Output ("  " + $_.Id + " " + $_.Name + "  " + $_.Path) } } else { Write-Output "  (none running)" }

Write-Output "=== Port 43120 listeners ==="
$ls = netstat -ano | Select-String '43120'
if ($ls) { $ls | ForEach-Object { Write-Output ("  " + $_.Line) } } else { Write-Output "  (nothing listening)" }

Write-Output "=== DSH_HOME registry (HKCU\Environment) ==="
$envVar = Get-ItemProperty -Path 'HKCU:\Environment' -Name 'DSH_HOME' -ErrorAction SilentlyContinue
if ($envVar) { Write-Output ("  DSH_HOME = " + $envVar.DSH_HOME) } else { Write-Output "  (not set)" }

Write-Output "=== .dsh data root ==="
$dr = $envVar.DSH_HOME
if ($dr -and (Test-Path -LiteralPath $dr)) {
  Write-Output ("  $dr exists; sessions dir:" )
  $sess = Join-Path $dr 'sessions'
  if (Test-Path -LiteralPath $sess) { Write-Output ("    sessions count: " + ((Get-ChildItem -LiteralPath $sess -ErrorAction SilentlyContinue | Measure-Object).Count)) }
}
