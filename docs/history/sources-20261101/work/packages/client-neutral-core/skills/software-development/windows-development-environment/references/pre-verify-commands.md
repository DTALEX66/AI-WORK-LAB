# Pre-Verify Commands Before Delivery

**Source**: WORK-LAB session 2026-08-26
**Requirement**: verify a command before delivering it. First-attempt failures erode trust, so syntax, path and environment assumptions are checked up front.

## Problem

First-attempt commands frequently fail due to:
- Wrong executable name (e.g. `hermes` vs `hermes.exe` vs `node .../cli.js`)
- Missing quotes around paths with spaces
- MSYS path vs Windows native path confusion
- Wrong flag syntax (e.g. `--server` vs `server` subcommand)
- Environment variable not set (PATH, HTTPS_PROXY)
- Port already in use

## Solution: Pre-Verification Pattern

Before delivering ANY command to the user:

1. **Syntax check**: `command --help` or `command --version` (never runs destructive action)
2. **Existence check**: `which command` / `where command` / `ls path/to/exe`
3. **Dry run**: `command --dry-run` or `command --check` if available
4. **Port check**: `netstat -ano | grep ':PORT'` before assuming a port is free
5. **Test in execute_code first**: run the command yourself, verify output, then give to user

## Common First-Command Failures on Windows

| Pattern | Example | Fix |
|---------|---------|-----|
| npm global not in PATH | `dagu: command not found` | Use full shim path or `node node_modules/.../cli.js` |
| Wrong subcommand | `dagu --server` (flag) | `dagu server` (subcommand) |
| Port conflict | `port 3000 already in use` | Use offset: `-p 3001` |
| MSYS path to native | `git -C /c/Users/...` | `git -C C:/Users/...` |
| Env var not set | `$HTTPS_PROXY` empty | Set explicitly or use `-x http://127.0.0.1:7890` |
| PS5.1 encoding | UTF-8 CJK truncated | Use `pwsh.exe` (PS 7) or add BOM |

## Rule

**Every command delivered to the user must be tested in execute_code or terminal first.** If you can't test it (e.g. it kills your own process), do a dry-run of the syntax and confirm the executable exists. The user's trust depends on first-attempt success.
