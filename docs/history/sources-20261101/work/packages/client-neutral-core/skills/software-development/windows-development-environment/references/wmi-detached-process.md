# WMI Detached Process Pattern (Windows)

**Source**: WORK-LAB session 2026-08-26

> **Scope limit.** Detaching from the parent's Job Object also removes the automatic reclamation the Job Object provided: it can defeat task cancellation and leave child processes behind. This is **not** a routine recipe and must not be used to escape cancellation or to keep work alive that the user asked to stop. Use it only when a durable background service genuinely needs its own lifecycle, with an explicit lifecycle owner, an explicit stop path, and authorization for the persistence it creates.

## When to Use

A durable background service needs to outlive the session that started it, and its owner is named before it starts. On Windows, `terminal(background=true)` places children in a Job Object that is reclaimed with the parent; WMI creates processes outside that Job Object, which is exactly why the scope limit above applies.

## Method: Win32_Process.Create

```python
import os
import shutil
import subprocess

# Write launcher .ps1 (avoids -Command quoting hell)
launcher_ps1 = r"D:\path\to\launch_detached.ps1"
watcher_ps1 = r"D:\path\to\watcher.ps1"
pwsh = os.environ.get("PWSH_EXE") or shutil.which("pwsh")
if not pwsh:
    raise SystemExit("pwsh not found: set PWSH_EXE or install PowerShell 7")

# Build launcher content
cmdline = f'"{pwsh}" -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "{watcher_ps1}"'
ps_content = f"""
$w = [WMIClass]'Win32_Process'
$r = $w.Create('{cmdline}')
"Create return: $($r.ReturnValue)"
"""
open(launcher_ps1, 'w').write(ps_content)

# Run via PowerShell File mode (not -Command, avoids quoting issues)
r = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
    "-File", launcher_ps1], capture_output=True, text=True, timeout=60)
print(r.stdout.strip())  # "Create return: 0" = success
```

## ReturnValue Codes

- **0** = Success
- **2** = Access denied (need admin)
- **3** = Insufficient privilege
- **8** = Unknown failure
- **9** = Path not found (wrong exe path or bad quoting)

## Why terminal(background=true) Fails

Hermes places background terminal children in a Windows Job Object. When the parent process (Hermes) exits, the Job Object kills all children. WMI `Win32_Process.Create` creates processes outside any Job Object — they survive independently.

## Common Use Cases

1. **Config watcher**: detect when Hermes exits, apply config changes, wait for next launch
2. **Post-exit cleanup**: run cleanup script after user closes the app
3. **Long-running monitor**: watch for file changes, process events, etc.

## Pitfalls

1. **Quoting in WMI Create** — inner quotes conflict with outer quotes. Use a .ps1 launcher file instead of inline -Command.
2. **pwsh path** — WMI does not inherit the caller's PATH, so resolve the interpreter programmatically (`shutil.which("pwsh")` or an explicit `PWSH_EXE`) and fail clearly when it is absent, instead of hard-coding a user directory.
3. **Job Object inheritance** — `CreateProcess` with `CREATE_SUSPENDED` or job assignment inherits the parent's Job. WMI bypasses this.
4. **Process cleanup** — orphan processes run forever until manually killed or system shutdown. Always include a stop condition in the script.
