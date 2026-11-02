$ErrorActionPreference = 'Continue'
$wsh = New-Object -ComObject WScript.Shell
$official = 'D:\All projects\DSH\DSH Desktop.exe'
$ded = 'D:\All projects\DSH\desktop-user-data'
$arg = "--user-data-dir=`"$ded`""

# kill current DSH Desktop processes
Get-Process -Name 'DSH Desktop' -ErrorAction SilentlyContinue | Stop-Process -Force
Start-Sleep -Seconds 2

function Dump-PS($dir, $label) {
  Write-Output ("--- {0} : {1} ---" -f $label, $dir)
  if (-not (Test-Path -LiteralPath $dir)) { Write-Output "  MISSING"; return }
  $pss = Join-Path $dir 'profile-selection'
  $id = Join-Path $dir 'identity'
  $states = @()
  if (Test-Path -LiteralPath $pss) {
    $states = Get-Content -LiteralPath (Join-Path $pss 'state.json') -Raw -ErrorAction SilentlyContinue
    Write-Output ("  profile-selection/state.json = {0}" -f $states)
  } else { Write-Output "  profile-selection: MISSING" }
  if (Test-Path -LiteralPath $id) { Write-Output ("  identity: {0}" -f ((Get-ChildItem -LiteralPath $id | Select-Object -First 4 | ForEach-Object Name) -join ', ')) }
  else { Write-Output "  identity: MISSING" }
}

Dump-PS 'C:\Users\ALEX\AppData\Roaming\DSH Desktop' "C-Roaming-default (Electron default, what no-arg launch hits)"
Dump-PS $ded "D-drive (your configured desktop-user-data)"

# fix both shortcuts: keep official D: target, restore --user-data-dir argument
$targets = @()
$desk = [Environment]::GetFolderPath('Desktop')
$targets += (Join-Path $desk 'DSH Desktop.lnk')
$sm = 'C:\Users\ALEX\AppData\Roaming\Microsoft\Windows\Start Menu\Programs'
$smDsh = Get-ChildItem -LiteralPath $sm -Filter '*.lnk' -Recurse -ErrorAction SilentlyContinue | Where-Object { $_.Name -match 'DSH Desktop' } | Select-Object -First 1
if ($smDsh) { $targets += $smDsh.FullName }

foreach ($p in $targets) {
  $lnk = $wsh.CreateShortcut($p)
  $lnk.TargetPath = $official
  $lnk.Arguments = $arg
  $lnk.WorkingDirectory = 'D:\All projects\DSH'
  $lnk.Save()
  $c = $wsh.CreateShortcut($p)
  Write-Output ("FIXED {0} : target={1} args='{2}' exists={3}" -f (Split-Path $p -Leaf), $c.TargetPath, $c.Arguments, (Test-Path -LiteralPath $c.TargetPath))
}
Write-Output "=== done ==="
