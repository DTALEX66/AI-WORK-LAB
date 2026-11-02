$ErrorActionPreference = 'Continue'
$dshRoot = 'D:\All projects\DSH'
$official = "$dshRoot\DSH Desktop.exe"

# relaunch (PS 5.1: positional arg + -WorkingDirectory)
$p = Start-Process -FilePath $official -WorkingDirectory $dshRoot -PassThru
Write-Output ("launched pid={0}" -f $p.Id)

Start-Sleep -Seconds 30

# child tree of DSH processes
$procs = Get-Process -ErrorAction SilentlyContinue | Where-Object { $_.Name -match 'DSH' }
Write-Output ("DSH process count: {0}" -f @($procs).Count)
if ($procs) {
  $procs | Sort-Object Id | ForEach-Object {
    $pp = (Get-CimInstance Win32_Process -Filter ("Id={0}" -f $_.Id) -ErrorAction SilentlyContinue).ParentProcessId
    Write-Output ("  {0} pid={1} parent={2} mainTitle='{3}'" -f $_.Name, $_.Id, $pp, $_.MainWindowTitle)
  }
}

$ls = netstat -ano | Select-String ':43120'
$listen = @($ls | Where-Object { $_.Line -match 'LISTENING' })
Write-Output ("port 43120 LISTENING lines: {0}" -f $listen.Count)
if ($listen) { $listen | Select-Object -First 3 | ForEach-Object { Write-Output ("  " + $_.Line) } }

# newest log line (today's)
$dud = Join-Path $dshRoot 'desktop-user-data'
$logDir = Join-Path $dud 'logs'
if (Test-Path -LiteralPath $logDir) {
  $today = Get-ChildItem -LiteralPath $logDir -File | Where-Object { $_.Name -like 'dsh-*.log' } |
    Sort-Object LastWriteTime -Descending | Select-Object -First 2
  foreach ($f in $today) {
    Write-Output ("=== {0} (last 8 lines, mtime {1}) ===" -f $f.Name, $f.LastWriteTime)
    Get-Content -LiteralPath $f.FullName -Tail 8 -ErrorAction SilentlyContinue | ForEach-Object { Write-Output ("  " + $_) }
  }
}
Write-Output "=== end ==="
