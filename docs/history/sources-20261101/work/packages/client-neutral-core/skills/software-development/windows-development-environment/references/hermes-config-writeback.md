# Hermes Config Write-Back Mechanism

**Source**: WORK-LAB session 2026-08-26
**Pitfall**: This is a core mechanism that will bite any session modifying Hermes config.

## Problem

The Hermes desktop app (Electron) holds config.yaml in memory state. Every conversation turn, it writes its memory state back to disk. Any manual edit to config.yaml during a live session gets **overwritten within seconds**.

## Evidence

```
22:38  guard writes: max_concurrent_children=6 → disk shows 6 ✅
22:39  (next conversation turn) → disk shows 3 again ❌ (desktop overwrote)
```

## Root Cause

Hermes desktop = Electron app with 5 processes (main + renderers). The main process holds config in memory and writes it to disk on every conversation event (turn end, session save, etc.). This is a **feature** (user preferences persist), not a bug — but it means manual config edits during a live session are futile.

## Solution: The Exit Window

Config changes can only survive if applied when **no Hermes process is running**:

1. **Login guard** (`HermesUpdateGuard.lnk` in Startup folder) — runs at Windows logon via `pwsh.exe` (PS 7.6.3, UTF-8 native). Applies config before desktop starts.

2. **Exit watcher** (WMI-detached pwsh process) — monitors for Hermes process count going to 0. When detected, applies config. Survives parent death via `Win32_Process.Create`.

## Key Insight: Watcher Must Be Detached

A watcher started via `terminal(background=true)` is a **child of Hermes**. When Hermes exits, the watcher dies too — it never gets to apply config. The correct approach:

```python
# Launch via WMI — creates process outside Hermes' Job Object
$w = [WMIClass]'Win32_Process'
$r = $w.Create('"C:\path\to\pwsh.exe" -NoProfile -File "watcher.ps1"')
# ReturnValue 0 = success
```

See `references/wmi-detached-process.md` for the full pattern.

## Verification

After applying config and waiting for Hermes restart:
1. `hermes config get` — reads from file (may show new values even if memory is old)
2. Check engine behavior — delegation/checkpoints/fallback actually working = memory loaded new values
3. `cat config.yaml | grep max_concurrent_children` — disk truth

## Dagu/TokenTelemetry Port Conflicts

Hermes gateway uses port 3000. FastAPI project gateway uses port 8000. New tools must use offset ports:
- Dagu: `dagu server -p 8080` (default)
- TokenTelemetry: `node bin/cli.js -p 3001 -a 8001`
