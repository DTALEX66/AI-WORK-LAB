$ErrorActionPreference = 'Continue'
$wsh = New-Object -ComObject WScript.Shell
$official = 'D:\All projects\DSH\DSH Desktop.exe'
$ded = 'D:\All projects\DSH\desktop-user-data'
$dshHome = 'D:\All projects\DSH\.dsh'
$arg = '--user-data-dir="' + $ded + '"'

# 1) kill current instances (running on the C: default user-data-dir)
Get-Process -Name 'DSH Desktop' -ErrorAction SilentlyContinue | Stop-Process -Force
Start-Sleep -Seconds 3

# 2) re-point both .lnk WITH the --user-data-dir argument
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
  Write-Output ("LNK {0} -> target={1} args='{2}'" -f (Split-Path $p -Leaf), $c.TargetPath, $c.Arguments)
}

# 3) launch WITH DSH_HOME + --user-data-dir so the real D: state is read
[Environment]::SetEnvironmentVariable('DSH_HOME', $dshHome, 'Process')
$before = (Get-Item -LiteralPath $dshHome).LastWriteTime
Start-Process -FilePath $official -ArgumentList $arg -WorkingDirectory 'D:\All projects\DSH'
Start-Sleep -Seconds 25
$after = (Get-Item -LiteralPath $dshHome).LastWriteTime

$procs = Get-Process -Name 'DSH Desktop' -ErrorAction SilentlyContinue | Sort-Object Id
$main = $procs | Where-Object { $_.MainWindowTitle -ne '' } | Select-Object -First 1
Write-Output ("DSH processes: {0}" -f @($procs).Count)
if ($main) {
  Write-Output ("main window title = '{0}'" -f $main.MainWindowTitle)
  $stillSetup = ($main.MainWindowTitle -match 'Set up|setup|配置|设置|onboard')
  Write-Output ("still-onboarding-screen = {0}" -f $stillSetup)
} else {
  Write-Output "no titled main window (may still be cold-starting)"
}

$ls = netstat -ano | Select-String ':43120'
$listen = @($ls | Where-Object { $_.Line -match 'LISTENING' })
Write-Output ("port 43120 LISTENING: {0}" -f $listen.Count)

$sess = Join-Path $dshHome 'sessions'
$sc = if (Test-Path -LiteralPath $sess) { (Get-ChildItem -LiteralPath $sess | Measure-Object).Count } else { 0 }
Write-Output ("D:.dsh sessions count: {0}" -f $sc)
Write-Output ("D:.dsh root mtime advanced: {0} (before={1} after={2})" -f ($before -lt $after), $before, $after)

# confirm the running main proc actually got the D: user-data-dir
$mainpid = if ($procs) { $procs[0].Id } else { 0 }
if ($mainpid) {
  $cl = (Get-CimInstance Win32_Process -Filter ("ProcessId={0}" -f $mainpid) -ErrorAction SilentlyContinue).CommandLine
  Write-Output ("main cmdline: {0}" -f $cl.Substring(0,[Math]::Min(200,$cl.Length)))
}
Write-Output "=== verify-done ==="
