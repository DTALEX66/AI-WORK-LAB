$ErrorActionPreference = "Continue"
$out = "D:\All projects\WORK-LAB\.hermes\task-runtime\dsh-fix2.out.txt"
$lines = New-Object System.Collections.Generic.List[string]
function L($m) { $lines.Add($m) }

# ---------- A: persisted data-root selection state ----------
L "===== A. desktop-user-data: profile-setup / identity (persisted data-root selection?) ====="
$ud = "D:\All projects\DSH\desktop-user-data"
foreach ($sub in @("profile-setup","profile-preferences","identity","host-commands")) {
  $p = Join-Path $ud $sub
  if (Test-Path -LiteralPath $p) {
    L "[$sub] files:"
    @(Get-ChildItem $p -Recurse -File -ErrorAction SilentlyContinue | Select-Object -First 40) | ForEach-Object {
      L ("   {0}  {1}B" -f $_.FullName.Replace($ud,""), $_.Length)
      if ($_.Length -lt 4000 -and $_.Extension -in ".json",".yaml",".yml",".txt") {
        $content = Get-Content $_.FullName -Raw -ErrorAction SilentlyContinue
        if ($content -match "\.dsh|homeDir|dataRoot|selectedHome|rootPath") {
          L "   ...MATCH...: " + $content.Substring(0, [Math]::Min(500, $content.Length))
        }
      }
    }
  }
}

# ---------- B: source channelHomeResolution persistence mechanism ----------
L ""
L "===== B. source: channelHomeResolution / desktopChannelHome (how data root resolves + persists) ====="
$appRoot = "D:\All projects\DSH\resources\app"
$found = @(Get-ChildItem $appRoot -Recurse -File -Include "main.js","lib.js","index.js","*.cjs" -ErrorAction SilentlyContinue |
          Select-String -Pattern "channelHomeResolution|desktopChannelHome" -List -ErrorAction SilentlyContinue |
          Select-Object -First 6)
if ($found) {
  foreach ($m in $found) {
    L "file: {0}  line {1}" -f $m.Path.Replace($appRoot,""), $m.LineNumber
    # print ~30 lines of context
    $all = Get-Content $m.Path -ErrorAction SilentlyContinue
    $start = [Math]::Max(0, $m.LineNumber - 4)
    $end   = [Math]::Min($all.Count, $m.LineNumber + 30)
    for ($i = $start; $i -lt $end; $i++) {
      L ("   {0,4}: {1}" -f ($i+1), $all[$i])
    }
  }
} else {
  L "no channelHomeResolution match in main/index js (may be bundled/minified)"
}

# ---------- C: relaunch DSH with DSH_HOME injected ----------
L ""
L "===== C. relaunch DSH with DSH_HOME injected (verify data-root resolution) ====="
$env:DSH_HOME = "D:\All projects\DSH\.dsh"
L "current PS env DSH_HOME set to: D:\All projects\DSH\.dsh"
$dcfg = "D:\All projects\DSH\.dsh"
$dmtimeBefore = (Get-Item $dcfg).LastWriteTime
L ("D:\.dsh mtime BEFORE: {0}" -f $dmtimeBefore)
$croot = "C:\Users\ALEX\.dsh"
$cExistedBefore = Test-Path -LiteralPath $croot
L ("C:\.dsh existed before relaunch: {0}" -f $cExistedBefore)
try {
  $p = Start-Process -FilePath "D:\All projects\DSH\DSH Desktop.exe" -ArgumentList '--user-data-dir="D:\All projects\DSH\desktop-user-data"' -PassThru
  L ("launched pid={0}" -f $p.Id)
} catch {
  L ("launch FAILED: " + $_.Exception.Message)
}
L "waiting 25s for boot + session restore ..."
Start-Sleep -Seconds 25

# ---------- D: verify ----------
L ""
L "===== D. verification ====="
$procs = @(Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object { $_.Name -eq "DSH Desktop.exe" })
L ("DSH process count: {0}" -f $procs.Count)
$mainProc = $procs | Where-Object { $_.CommandLine -notmatch "--type=" } | Select-Object -First 1
if ($mainProc) {
  L ("main cmdline: {0}" -f $mainProc.CommandLine)
  L ("main window title: '{0}'" -f $mainProc.Name)
}
# window title via Get-Process
$gp = Get-Process -Name "DSH Desktop" -ErrorAction SilentlyContinue | Select-Object -First 1
L ("MainWindowTitle: '{0}'" -f $gp.MainWindowTitle)
# 43120
$listen = netstat -ano | Select-String "43120.*LISTENING"
L ("43120 LISTENING: {0}" -f (@($listen).Count))
# D mtime advanced?
$dmtimeAfter = (Get-Item $dcfg).LastWriteTime
L ("D:\.dsh mtime AFTER: {0}  (advanced: {1})" -f $dmtimeAfter, ($dmtimeAfter -gt $dmtimeBefore))
# C not recreated?
$cExistedAfter = Test-Path -LiteralPath $croot
L ("C:\.dsh exists after: {0}  (recreated: {1})" -f $cExistedAfter, ($cExistedAfter -and -not $cExistedBefore))

$lines | Out-File -FilePath $out -Encoding utf8
Write-Output "FIX2_DONE"
