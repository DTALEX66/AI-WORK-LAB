$ErrorActionPreference = "Continue"
$repo = "D:\All projects\WORK-LAB"
$ds = "D:\All projects\DSH"
$out = "$repo\.hermes\task-runtime\dsh-close7.out.txt"
$lines = New-Object System.Collections.Generic.List[string]
function L($m) { $lines.Add($m) }

L "=== CLOSE7 @ $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') ==="

L "--- 1) stray elevated powershell procs (from UAC attempts)? ---"
$ev = @(Get-CimInstance Win32_Process -Filter "Name='powershell.exe'" -ErrorAction SilentlyContinue |
       Where-Object { $_.CommandLine -match 'dsh-elev' })
L ("elev_powershell_stragglers=" + $ev.Count)
if ($ev.Count -gt 0) {
  foreach ($e in $ev) {
    L ("killing stray pid=" + $e.ProcessId)
    Stop-Process -Id $e.ProcessId -Force -ErrorAction SilentlyContinue
  }
  Start-Sleep -Seconds 1
  $ev2 = @(Get-CimInstance Win32_Process -Filter "Name='powershell.exe'" -ErrorAction SilentlyContinue |
          Where-Object { $_.CommandLine -match 'dsh-elev' })
  L ("stragglers_after_kill=" + $ev2.Count)
}

L "--- 2) move C-drive skeleton backup into D-drive migration archive (09-20 precedent) ---"
$cBak = "C:\Users\ALEX\.dsh-skeleton-backup-20260924"
$dest = "$ds\.migration\20260924\c-dsh-skeleton-backup-20260924"
if (Test-Path $cBak) {
  New-Item -ItemType Directory -Path $ds\.migration\20260924 -Force | Out-Null
  Move-Item $cBak $dest -ErrorAction SilentlyContinue
  L ("moved=" + (Test-Path $dest) + " cRemnant=" + (Test-Path $cBak))
} else { L "cBakMissing (already moved or never existed)" }

L "--- 3) DSH + data + shortcut final health ---"
$procs = @(Get-CimInstance Win32_Process -Filter "Name='DSH Desktop.exe'" -ErrorAction SilentlyContinue)
L ("dsh_instances=" + $procs.Count)
$ln = Get-NetTCPConnection -LocalPort 43120 -State Listen -ErrorAction SilentlyContinue
L ("43120_listening=" + ($null -ne $ln))
$dRoot = "$ds\.dsh"
L ("dRoot=" + (Test-Path $dRoot) + " sessions=" + $(if (Test-Path "$dRoot\sessions") { (Get-ChildItem "$dRoot\sessions" -Directory).Count } else { 0 }))
$shell = New-Object -ComObject WScript.Shell
$lnk = $shell.CreateShortcut("$env:USERPROFILE\Desktop\DSH Desktop.lnk")
L ("lnk=" + $lnk.TargetPath + " | " + $lnk.Arguments + " | exists=" + (Test-Path -LiteralPath $lnk.TargetPath))

$lines | Out-File -FilePath $out -Encoding utf8
Write-Output "CLOSE7_DONE $out"
