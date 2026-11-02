$ErrorActionPreference = "Continue"
$out = "D:\All projects\WORK-LAB\.hermes\task-runtime\dsh-diag2.out.txt"
$lines = New-Object System.Collections.Generic.List[string]
function L($m) { $lines.Add($m) }

$shell = New-Object -ComObject WScript.Shell

L "===== 1. DSH entry points (.lnk) ====="
$desktop = [Environment]::GetFolderPath("Desktop")
$startmenu = [Environment]::GetFolderPath("Programs")
$candidates = @()
$candidates += @(Get-ChildItem -Path $desktop -Filter "*.lnk" -ErrorAction SilentlyContinue | Where-Object { $_.Name -match "DSH|Harness" })
$candidates += @(Get-ChildItem -Path $startmenu -Filter "*.lnk" -ErrorAction SilentlyContinue | Where-Object { $_.Name -match "DSH|Harness" })
$pintask = Join-Path $env:APPDATA "Microsoft\Internet Explorer\Quick Launch\User Pinned\TaskBar"
if (Test-Path $pintask) {
  $candidates += @(Get-ChildItem -Path $pintask -Filter "*.lnk" -ErrorAction SilentlyContinue | Where-Object { $_.Name -match "DSH|Harness" })
}
L "desktop dir: $desktop"
L "startmenu dir: $startmenu"
if ($candidates.Count -eq 0) { L "NO DSH .lnk FOUND in desktop/startmenu/taskbar-pin" }
foreach ($lnk in $candidates) {
  $s = $shell.CreateShortcut($lnk.FullName)
  $parent = $lnk.DirectoryName.Split('\')[-2]
  L ("[{0}] {1}" -f $parent, $lnk.FullName)
  $tgt = $s.TargetPath
  $icon0 = if ($s.IconLocation -match '^"?(.+?)"?,') { $Matches[1] } else { $s.IconLocation }
  L ("   target      = {0}  (exists: {1})" -f $tgt, (Test-Path -LiteralPath $tgt))
  L ("   args        = '{0}'" -f $s.Arguments)
  $iconExists = if ($icon0) { Test-Path -LiteralPath $icon0 } else { "n/a" }
  L ("   iconloc     = {0}  (exe exists: {1})" -f $s.IconLocation, $iconExists)
}

L ""
L "===== 2. DSH install dir + migrations ====="
$ds = "D:\All projects\DSH"
if (Test-Path $ds) {
  $exe = Join-Path $ds "DSH Desktop.exe"
  if (Test-Path $exe) {
    $v = (Get-Item $exe).VersionInfo
    L ("official exe: {0} productver={1} filever={2} mtime={3}" -f $exe, $v.ProductVersion, $v.FileVersion, (Get-Item $exe).LastWriteTime)
  } else { L "official exe ABSENT: $exe" }
  $mig = Join-Path $ds ".migration"
  if (Test-Path $mig) {
    L ".migration dirs (newest first):"
    @(Get-ChildItem $mig -Directory -ErrorAction SilentlyContinue | Sort-Object Name -Descending | Select-Object -First 6) | ForEach-Object {
      $tmpexe = Join-Path $_.FullName "restore-tmp\install\DSH Desktop.exe"
      L ("   {0}  (restore-tmp exe exists: {1})" -f $_.Name, (Test-Path $tmpexe))
    }
  }
} else { L "DSH root ABSENT: $ds" }

L ""
L "===== 3. user-data + config state ====="
$ud = "D:\All projects\DSH\desktop-user-data"
if (Test-Path $ud) {
  $it = Get-Item $ud
  L ("desktop-user-data mtime={0}" -f $it.LastWriteTime)
  $sess = @(Get-ChildItem $ud -Recurse -File -ErrorAction SilentlyContinue | Where-Object { $_.Name -match "session" })
  L ("session-ish files: {0}" -f $sess.Count)
  $setup = @(Get-ChildItem $ud -Recurse -File -ErrorAction SilentlyContinue | Where-Object { $_.Name -match "setup|onboard|wizard" })
  L ("setup-marker files: {0}" -f $setup.Count)
  $du = @(Get-ChildItem $ud -Directory -ErrorAction SilentlyContinue | Select-Object -First 12)
  L ("top dirs: {0}" -f (($du | ForEach-Object { $_.Name }) -join ","))
} else { L "desktop-user-data ABSENT: $ud" }
$dshcfg = "D:\All projects\DSH\.dsh"
if (Test-Path $dshcfg) {
  $item = Get-Item $dshcfg -Force
  if ($item.PSIsContainer) {
    $fc = @(Get-ChildItem $dshcfg -Recurse -File -ErrorAction SilentlyContinue)
    L (".dsh is a dir, mtime={0}, filecount={1}" -f $item.LastWriteTime, $fc.Count)
    @(Get-ChildItem $dshcfg -Recurse -File -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending | Select-Object -First 8) | ForEach-Object {
      L ("   {0}  {1}  {2}B" -f $_.LastWriteTime, $_.FullName.Replace($dshcfg,''), $_.Length)
    }
  } else {
    L (".dsh is a file, mtime={0}, size={1}" -f $item.LastWriteTime, $item.Length)
  }
} else { L ".dsh ABSENT: $dshcfg" }

L ""
L "===== 4. DSH_HOME registry pins (HKCU) ====="
@(Get-ChildItem "HKCU:\Software" -ErrorAction SilentlyContinue | Where-Object { $_.PSChildName -match "DeepSeek|DSH|Harness" }) | ForEach-Object {
  L "HKCU key found: $($_.PSPath)"
  Get-ItemProperty $_.PSPath | ForEach-Object {
    $_.PSObject.Properties | Where-Object { $_.Value -ne $null } | ForEach-Object {
      L ("   {0} = {1}" -f $_.Name, $_.Value)
    }
  }
}
L "(no DSH/DeepSeek/Harness HKCU key if nothing above)"

L ""
L "===== 5. running DSH processes ====="
$procs = @(Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object { $_.Name -match "DSH|Harness|harness" })
if ($procs) {
  foreach ($p in $procs) {
    L ("pid={0} {1}" -f $p.ProcessId, $p.Name)
    L ("   cmdline: {0}" -f $p.CommandLine)
  }
} else { L "no DSH processes running" }

$lines | Out-File -FilePath $out -Encoding utf8
Write-Output "DIAG2_DONE"
