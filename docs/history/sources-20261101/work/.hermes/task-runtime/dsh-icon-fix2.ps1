$ErrorActionPreference = 'Continue'
$wsh = New-Object -ComObject WScript.Shell
$official = 'D:\All projects\DSH\DSH Desktop.exe'

# A) re-point BOTH shortcuts' icon to the official D-drive exe (IconLocation = "exe,0")
$targets = @()
$desk = [Environment]::GetFolderPath('Desktop')
$targets += (Join-Path $desk 'DSH Desktop.lnk')
$sm = 'C:\Users\ALEX\AppData\Roaming\Microsoft\Windows\Start Menu\Programs'
$smDsh = Get-ChildItem -LiteralPath $sm -Filter '*.lnk' -Recurse -ErrorAction SilentlyContinue | Where-Object { $_.Name -match 'DSH Desktop' } | Select-Object -First 1
if ($smDsh) { $targets += $smDsh.FullName }

foreach ($p in $targets) {
  $l = $wsh.CreateShortcut($p)
  $l.IconLocation = $official + ",0"
  $l.IconIndex = 0
  $l.Save()
  $c = $wsh.CreateShortcut($p)
  $iconFile = ($c.IconLocation -split ',')[0]
  Write-Output ("LNK {0} : icon={1}  icon-exists={2}" -f (Split-Path $p -Leaf), $c.IconLocation, (Test-Path -LiteralPath $iconFile))
}

# B) official exe icon health — extract, save PNG, measure distinct colors
$png = "D:\All projects\WORK-LAB\.hermes\task-runtime\dsh-exe-icon.png"
try {
  Add-Type -AssemblyName System.Drawing
  $ico = [System.Drawing.Icon]::ExtractAssociatedIcon($official)
  if ($ico -eq $null) {
    Write-Output "B: no associated icon extractable from official exe (would be a real broken-exe-icon symptom)"
  } else {
    $bmp = New-Object System.Drawing.Bitmap($ico.Width, $ico.Height, [System.Drawing.Imaging.PixelFormat]::Format32bppArgb)
    $g = [System.Drawing.Graphics]::FromImage($bmp)
    $g.DrawImage($ico, 0, 0, $ico.Width, $ico.Height)
    $g.Dispose()
    $bmp.Save($png, [System.Drawing.Imaging.ImageFormat]::Png)
    $distinct = @{}
    $step = [Math]::Max(1, [int]($bmp.Width / 24))
    $sampled = 0
    for ($x = 0; $x -lt $bmp.Width; $x += $step) {
      for ($y = 0; $y -lt $bmp.Height; $y += $step) {
        $px = $bmp.GetPixel($x, $y)
        $key = "{0},{1},{2},{3}" -f $px.R, $px.G, $px.B, $px.A
        if (-not $distinct.ContainsKey($key)) { $distinct[$key] = 0 }
        $distinct[$key]++
        $sampled++
      }
    }
    $opaque = ($distinct.Keys | Where-Object { ($_ -split ',')[-1] -ne '0' }).Count
    Write-Output ("B: exe icon {0}x{1}, sampled={2} distinct-colors={3} (opaque={4})" -f $bmp.Width, $bmp.Height, $sampled, $distinct.Count, $opaque)
    if ($opaque -le 1 -and $distinct.Values | Where-Object { $_ -gt 0 }) {
      $nonZero = $distinct.Keys | Where-Object { ($_ -split ',')[-1] -ne '0' } | Select-Object -First 3
      Write-Output ("B: VERDICT SUSPECT/BROKEN — opaque colors: {0}" -f ($nonZero -join '; '))
    } else {
      Write-Output "B: VERDICT OK — multi-color real icon"
    }
    $ico.Dispose()
    $bmp.Dispose()
    Write-Output ("B: icon png saved -> {0}" -f $png)
  }
} catch {
  Write-Output ("B: icon check error: {0}" -f $_.Exception.Message)
}

# C) accurate live-instance check: does ANY renderer carry the D: user-data-dir?
$procs = Get-CimInstance Win32_Process -Filter "Name='DSH Desktop.exe'" -ErrorAction SilentlyContinue
$carriers = @($procs | Where-Object { $_.CommandLine -match '--user-data-dir="D:\\All projects\\DSH\\desktop-user-data"' })
$win = Get-Process -Name 'DSH Desktop' -ErrorAction SilentlyContinue | Where-Object { $_.MainWindowTitle -ne '' } | Select-Object -First 1
Write-Output ("C: DSH Desktop.exe processes={0}  carrying-D-user-data-dir={1}" -f @($procs).Count, @($carriers).Count)
if ($win) { Write-Output ("C: main window title = '{0}'" -f $win.MainWindowTitle) }
$listen = @(netstat -ano | Select-String ':43120' | Where-Object { $_.Line -match 'LISTENING' })
Write-Output ("C: port 43120 LISTENING={0}" -f $listen.Count)
