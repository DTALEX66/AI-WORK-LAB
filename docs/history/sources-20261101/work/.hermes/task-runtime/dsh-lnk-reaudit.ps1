$ErrorActionPreference = "Continue"
$shell = New-Object -ComObject WScript.Shell
$out = "D:\All projects\WORK-LAB\.hermes\task-runtime\dsh-reaudit-lnk.txt"
Set-Content -Path $out -Value "" -Encoding utf8
$paths = @("$env:USERPROFILE\Desktop\DSH Desktop.lnk", "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\DSH Desktop.lnk")
foreach ($p in $paths) {
  if (Test-Path $p) {
    $l = $shell.CreateShortcut($p)
    $tOK = Test-Path -LiteralPath $l.TargetPath
    $iOK = $false
    if ($l.IconLocation) { $iconExe = ($l.IconLocation -split ',')[0]; $iOK = Test-Path -LiteralPath $iconExe }
    Add-Content $out "[$p]"
    Add-Content $out "  target=$($l.TargetPath) exists=$tOK"
    Add-Content $out "  args=$($l.Arguments)"
    Add-Content $out "  icon=$($l.IconLocation) exists=$iOK"
  } else {
    Add-Content $out "[$p] MISSING"
  }
}
Write-Output "LNK_DONE"
