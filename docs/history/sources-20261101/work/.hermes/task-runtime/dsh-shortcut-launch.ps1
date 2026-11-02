$ErrorActionPreference = 'Continue'
$official = 'D:\All projects\DSH\DSH Desktop.exe'
$procName = 'DSH Desktop'

# launch
Start-Process -LiteralPath $official
Write-Output "launched official exe"

# wait for port 43120 + process, up to ~30s (Electron cold start)
$deadline = (Get-Date).AddSeconds(40)
$portUp = $false
$procOk = $false
while ((Get-Date) -lt $deadline -and (-not $portUp -or -not $procOk)) {
  Start-Sleep -Seconds 3
  $ls = netstat -ano | Select-String ':43120.*LISTENING'
  if ($ls) { $portUp = $true }
  $procs = Get-Process -ErrorAction SilentlyContinue | Where-Object { $_.Name -match 'DSH' }
  if ($procs) { $procOk = $true }
}
Write-Output ("port 43120 LISTENING: {0}" -f $portUp)
$procs = Get-Process -ErrorAction SilentlyContinue | Where-Object { $_.Name -match 'DSH' }
if ($procs) { $procs | ForEach-Object { Write-Output ("process: {0} pid={1} mainTitle='{2}'" -f $_.Name, $_.Id, $_.MainWindowTitle) } } else { Write-Output "process: none" }

# re-verify shortcuts end-to-end
$wsh = New-Object -ComObject WScript.Shell
foreach ($p in @((Join-Path ([Environment]::GetFolderPath('Desktop')) 'DSH Desktop.lnk'),
                 'C:\Users\ALEX\AppData\Roaming\Microsoft\Windows\Start Menu\Programs\DSH Desktop.lnk')) {
  $lnk = $wsh.CreateShortcut($p)
  $ok = Test-Path -LiteralPath $lnk.TargetPath
  Write-Output ("shortcut {0} -> {1} exists={2}" -f (Split-Path $p -Leaf), $lnk.TargetPath, $ok)
}
