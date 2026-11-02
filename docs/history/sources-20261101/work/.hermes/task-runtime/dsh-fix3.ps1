$ErrorActionPreference = "Continue"
$out = "D:\All projects\WORK-LAB\.hermes\task-runtime\dsh-fix3.out.txt"
$lines = New-Object System.Collections.Generic.List[string]
function L($m) { $lines.Add($m) }
$DSH = "D:\All projects\DSH\.dsh"

# ---- 1) user-level re-affirm + machine-level (HKLM) DSH_HOME via UAC ----
L "===== 1. DSH_HOME env: user + machine level ====="
L "HKCU DSH_HOME (before) = '$((Get-ItemProperty 'HKCU:\Environment').DSH_HOME)'"
setx DSH_HOME $DSH 2>&1 | ForEach-Object { L "   user setx: " + $_ }
L "HKCU DSH_HOME (after)  = '$((Get-ItemProperty 'HKCU:\Environment').DSH_HOME)'"

# machine-level: needs admin. Attempt an elevated setx (one UAC prompt, user clicks Yes).
$hl = (Get-ItemProperty "HKLM:\SYSTEM\CurrentVersion\Environment" -Name DSH_HOME -ErrorAction SilentlyContinue).DSH_HOME
L "HKLM DSH_HOME (before) = '$hl'"
try {
  # spawn elevated setx /M; -Wait returns when done. Pops a single UAC prompt.
  $proc = Start-Process -FilePath "setx" -ArgumentList @("/M","DSH_HOME",$DSH) -Verb RunAs -Wait -PassThru
  L ("   elevated setx /M exit={0}" -f $proc.ExitCode)
} catch {
  L ("   elevated setx /M FAILED (UAC declined or not interactive): " + $_.Exception.Message)
}
Start-Sleep -Seconds 2
$hl2 = (Get-ItemProperty "HKLM:\SYSTEM\CurrentVersion\Environment" -Name DSH_HOME -ErrorAction SilentlyContinue).DSH_HOME
L "HKLM DSH_HOME (after)  = '$hl2'"
if ($hl2 -eq $DSH) { L "   -> MACHINE-LEVEL DSH_HOME SET: every future session's base env now carries it." }
else { L "   -> machine-level NOT set (needs admin/UAC). user-level is set; current session still frozen until relog/broadcast." }

# ---- 2) broadcast WM_SETTINGCHANGE to the current interactive session (best-effort no-relog refresh) ----
L ""
L "===== 2. broadcast env refresh to current session (best-effort) ====="
$u32 = Add-Type -Namespace N -Name U32 -MemberDefinition '
[DllImport("user32.dll", SetLastError=true)]
public static extern IntPtr SendMessage(IntPtr hWnd, uint Msg, IntPtr wParam, IntPtr lParam);
[DllImport("user32.dll", SetLastError=true)]
public static extern IntPtr FindWindow(string cls, string title);
[DllImport("user32.dll", SetLastError=true)]
public static extern IntPtr GetParent(IntPtr hWnd);
' -ReferencedAssemblies System.Windows.Forms -ErrorAction SilentlyContinue
try {
  $WM_SETTINGCHANGE = 0x001A
  # HWND_BROADCAST = 0xFFFF
  $HWND_BROADCAST = [IntPtr]0xFFFF
  $h = [N.U32]::SendMessage($HWND_BROADCAST, $WM_SETTINGCHANGE, [IntPtr]::Zero, [IntPtr]::Zero)
  L ("   SendMessage(HWND_BROADCAST, WM_SETTINGCHANGE) returned 0x{0:X} (0=delivered ok)" -f $h.ToInt64())
} catch {
  L ("   broadcast best-effort: " + $_.Exception.Message)
}
L "note: user env vars are frozen at logon; broadcast refreshes Explorer's block best-effort. Machine-level set (step1) is the durable guarantee for all sessions."

# ---- 3) archive + remove the C:\.dsh empty fallback skeleton (evidence-gated) ----
L ""
L "===== 3. C:\Users\ALEX\.dsh fallback skeleton (archive + remove, gated on 0 sessions) ====="
$croot = "C:\Users\ALEX\.dsh"
if (Test-Path -LiteralPath $croot) {
  $cf = @(Get-ChildItem $croot -Recurse -File -ErrorAction SilentlyContinue)
  $csess = @($cf | Where-Object { $_.Name -match "\.jsonl|session.*\.zstd|/sessions/" })
  L ("   C:\.dsh files={0} session-data-files={1} (mtime={2})" -f $cf.Count, $csess.Count, (Get-Item $croot).LastWriteTime)
  if ($csess.Count -eq 0) {
    $park = "D:\All projects\DSH\.migration\20260924\c-dsh-skeleton-archived"
    New-Item -ItemType Directory -Path $park -Force | Out-Null
    Copy-Item -Path "$croot\*" -Destination $park -Recurse -Force
    L ("   parked {0} files -> {1}" -f (@(Get-ChildItem $park -Recurse -File).Count), $park)
    Remove-Item -LiteralPath $croot -Recurse -Force
    L ("   C source removed; now exists: {0}" -f (Test-Path -LiteralPath $croot))
    L "   (real data/sessions stay on D:\.dsh; C skeleton had 0 sessions — only auto-created .credentials/settings)"
  } else {
    L "   C:\.dsh HAS session data — NOT removing, parked a copy only (reversible)."
  }
} else {
  L "   C:\.dsh already absent"
}

# ---- 4) verify the currently-running DSH is still healthy on D: ----
L ""
L "===== 4. running DSH health (should still be on D:, untouched by this fix) ====="
$procs = @(Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object { $_.Name -eq "DSH Desktop.exe" })
L ("   DSH process count: {0}" -f $procs.Count)
$gp = Get-Process -Name "DSH Desktop" -ErrorAction SilentlyContinue | Select-Object -First 1
L ("   MainWindowTitle: '{0}'" -f $gp.MainWindowTitle)
$listen = @(netstat -ano | Select-String "43120.*LISTENING")
L ("   43120 LISTENING lines: {0}" -f $listen.Count)
$dm = (Get-Item "D:\All projects\DSH\.dsh").LastWriteTime
L ("   D:\.dsh mtime: {0}" -f $dm)

$lines | Out-File -FilePath $out -Encoding utf8
Write-Output "FIX3_DONE"
