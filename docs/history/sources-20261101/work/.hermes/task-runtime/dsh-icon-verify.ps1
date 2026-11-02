$ErrorActionPreference = 'Continue'
$wsh = New-Object -ComObject WScript.Shell
$official = 'D:\All projects\DSH\DSH Desktop.exe'

$targets = @()
$desk = [Environment]::GetFolderPath('Desktop')
$targets += (Join-Path $desk 'DSH Desktop.lnk')
$sm = 'C:\Users\ALEX\AppData\Roaming\Microsoft\Windows\Start Menu\Programs'
$smDsh = Get-ChildItem -LiteralPath $sm -Filter '*.lnk' -Recurse -ErrorAction SilentlyContinue | Where-Object { $_.Name -match 'DSH Desktop' } | Select-Object -First 1
if ($smDsh) { $targets += $smDsh.FullName }

Write-Output "=== A. shortcut .lnk dump (target/args/icon) ==="
foreach ($p in $targets) {
  if (-not (Test-Path -LiteralPath $p)) { Write-Output "MISSING: $p"; continue }
  $l = $wsh.CreateShortcut($p)
  Write-Output "--- $p"
  Write-Output ("  TargetPath   = {0}" -f $l.TargetPath)
  Write-Output ("  Arguments    = {0}" -f $l.Arguments)
  Write-Output ("  WorkingDir   = {0}" -f $l.WorkingDirectory)
  Write-Output ("  IconLocation = '{0}'" -f $l.IconLocation)
  Write-Output ("  HotKey       = {0}" -f $l.IconIndex)
  Write-Output ("  TargetExists = {0}" -f (Test-Path -LiteralPath $l.TargetPath))
  # check the icon file the .lnk points to
  if ($l.IconLocation) {
    $icoPath = ($l.IconLocation -split ',')[0]
    Write-Output ("  IconFileExists = {0}  ({1})" -f (Test-Path -LiteralPath $icoPath), $icoPath)
  } else {
    Write-Output "  IconFileExists = (embedded in .lnk / inherited from exe — not a file ref)"
  }
}

Write-Output ""
Write-Output "=== B. official exe associated icon (broken-icon check) ==="
$iconOut = "D:\All projects\WORK-LAB\.hermes\task-runtime\dsh-exe-icon.png"
try {
  Add-Type -AssemblyName System.Drawing
  $ico = [System.Drawing.Icon]::ExtractAssociatedIcon($official)
  if ($ico) {
    $bmp = New-Object System.Drawing.Bitmap $ico
    $ico.Dispose()
    # save
    $bmp.Save($iconOut, [System.Drawing.Imaging.ImageFormat]::Png)
    # color diversity: sample distinct colors across the bitmap
    $distinct = @{}
    $step = [Math]::Max(1, [int]($bmp.Width / 32))
    $cnt = 0
    for ($x = 0; $x -lt $bmp.Width; $x += $step) {
      for ($y = 0; $y -lt $bmp.Height; $y += $step) {
        $px = $bmp.GetPixel($x, $y)
        $key = "{0},{1},{2}" -f $px.R, $px.G, $px.B
        if (-not $distinct.ContainsKey($key)) { $distinct[$key] = 0 }
        $distinct[$key]++
        $cnt++
      }
    }
    $bmp.Dispose()
    $nDistinct = $distinct.Count
    $isWhite = ($nDistinct -eq 1) -and ($distinct.Keys[0] -eq "255,255,255")
    Write-Output ("  icon size = {0}x{1}" -f ([int][Math]::Sqrt($bmp.Width * $bmp.Height)), $bmp.Height)
    Write-Output ("  sampled pixels = {0}, distinct colors = {1}" -f $cnt, $nDistinct)
    if ($isWhite) {
      Write-Output "  VERDICT: BROKEN (single pure-white color — icon asset lost, classic 1-quantized-color symptom)"
    } elseif ($nDistinct -le 2) {
      Write-Output "  VERDICT: SUSPECT (nearly single-color — likely damaged/placeholder)"
    } else {
      Write-Output "  VERDICT: OK (multi-color real icon rendered)"
    }
  } else {
    Write-Output "  no associated icon extractable from exe"
  }
} catch {
  Write-Output ("  icon extract error: {0}" -f $_.Exception.Message)
}

Write-Output ""
Write-Output "=== C. live instance check (correct user-data-dir?) ==="
$procs = Get-CimInstance Win32_Process -Filter "Name='DSH Desktop.exe'" -ErrorAction SilentlyContinue
$main = $procs | Where-Object { $_.CommandLine -match '--user-data-dir' } | Select-Object -First 1
if ($main) {
  $ud = [regex]::Match($main.CommandLine, '--user-data-dir=([^ "\s]+)').Groups[1].Value
  Write-Output ("  live renderer user-data-dir = {0}" -f $ud)
  Write-Output ("  points-to-D-drive-configured-state = {0}" -f ($ud -eq 'D:\All projects\DSH\desktop-user-data'))
} else {
  # maybe only the top-level proc has no --user-data-dir on cmdline; check main title
  $mp = Get-Process -Name 'DSH Desktop' -ErrorAction SilentlyContinue | Where-Object { $_.MainWindowTitle -ne '' } | Select-Object -First 1
  if ($mp) { Write-Output ("  main window title = '{0}'  (onboarding = Set up)" -f $mp.MainWindowTitle) }
  else { Write-Output "  no DSH Desktop process running" }
}
