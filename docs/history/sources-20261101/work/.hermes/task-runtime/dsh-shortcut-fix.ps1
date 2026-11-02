$ErrorActionPreference = 'Continue'
$wsh = New-Object -ComObject WScript.Shell

$official = 'D:\All projects\DSH\DSH Desktop.exe'
if (-not (Test-Path -LiteralPath $official)) { Write-Output "ABORT: official exe missing"; exit 1 }

$sm = 'C:\Users\ALEX\AppData\Roaming\Microsoft\Windows\Start Menu\Programs'
$smDsh = Get-ChildItem -LiteralPath $sm -Filter '*.lnk' -Recurse -ErrorAction SilentlyContinue |
  Where-Object { $_.Name -match 'DSH' } | Select-Object -First 1

$targets = @()
$desk = [Environment]::GetFolderPath('Desktop')
$targets += (Join-Path $desk 'DSH Desktop.lnk')
if ($smDsh) { $targets += $smDsh.FullName }

foreach ($p in $targets) {
  $lnk = $wsh.CreateShortcut($p)
  $lnk.TargetPath = $official
  $lnk.WorkingDirectory = 'D:\All projects\DSH'
  $lnk.Description = 'DSH Desktop (official community desktop)'
  $lnk.Save()
  # re-read end to end
  $check = $wsh.CreateShortcut($p)
  $ok = Test-Path -LiteralPath $check.TargetPath
  Write-Output ("{0}" -f $p)
  Write-Output ("  Target={0} Args='{1}' WorkDir={2}" -f $check.TargetPath, $check.Arguments, $check.WorkingDirectory)
  Write-Output ("  TargetExists={0}" -f $ok)
}
