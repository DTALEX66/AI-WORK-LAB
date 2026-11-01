\
$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root
python .\scripts\verify_complete_taskpack.py
python .\scripts\apply_unified_overlay.py 'D:\All projects\OPEN-DESIGN-Assistance' --plan
Write-Host 'Plan completed. No target files were changed.'
