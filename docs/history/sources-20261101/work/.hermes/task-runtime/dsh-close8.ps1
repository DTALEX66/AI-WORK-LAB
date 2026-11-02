$ErrorActionPreference = "Continue"
$repo = "D:\All projects\WORK-LAB"
$ds = "D:\All projects\DSH"
$cBak = "C:\Users\ALEX\.dsh-skeleton-backup-20260924"
$dest = "$ds\.migration\20260924\c-dsh-skeleton-backup-20260924"
$out = "$repo\.hermes\task-runtime\dsh-close8.out.txt"
$lines = New-Object System.Collections.Generic.List[string]
function L($m) { $lines.Add($m) }

L "=== CLOSE8 @ $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') ==="
L ("cSource=" + (Test-Path $cBak) + " dest=" + (Test-Path $dest))
foreach ($p in @($cBak, $dest)) {
  if (Test-Path $p) {
    $files = @(Get-ChildItem $p -Recurse -File -ErrorAction SilentlyContinue)
    L ("  " + $p + " files=" + $files.Count + " bytes=" + (($files | Measure-Object Length -Sum).Sum))
    Get-ChildItem $p -File -ErrorAction SilentlyContinue | ForEach-Object { L ("     " + $_.Name + " " + $_.Length + " " + $_.LastWriteTime) }
  }
}
# if both exist with content: finish the job -- compare counts; if dest complete, remove C source
if ((Test-Path $cBak) -and (Test-Path $dest)) {
  $sc = @(Get-ChildItem $cBak -Recurse -File -ErrorAction SilentlyContinue).Count
  $dc = @(Get-ChildItem $dest -Recurse -File -ErrorAction SilentlyContinue).Count
  L ("srcFiles=" + $sc + " destFiles=" + $dc)
  if ($sc -gt 0 -and $dc -ge $sc) {
    Remove-Item $cBak -Recurse -Force -ErrorAction SilentlyContinue
    L ("removedCSource=" + (-not (Test-Path $cBak)))
  } else {
    Move-Item $cBak $dest -Force -ErrorAction SilentlyContinue
    L ("retryMove cGone=" + (-not (Test-Path $cBak)) + " destOk=" + (Test-Path $dest))
  }
}
L ("final: cSource=" + (Test-Path $cBak) + " dest=" + (Test-Path $dest))
L ("cDriveCleanCheck: C:\\Users\\ALEX\\.dsh = " + (Test-Path "C:\Users\ALEX\.dsh"))

$lines | Out-File -FilePath $out -Encoding utf8
Write-Output "CLOSE8_DONE $out"
