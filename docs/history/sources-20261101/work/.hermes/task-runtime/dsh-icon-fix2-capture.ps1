$out = & (Get-ChildItem ".hermes\task-runtime\dsh-icon-fix2.ps1").FullName 2>&1 | Out-String
[System.IO.File]::WriteAllText(".hermes\task-runtime\dsh-icon-fix2.out.txt", $out, [System.Text.Encoding]::UTF8)
exit 0
